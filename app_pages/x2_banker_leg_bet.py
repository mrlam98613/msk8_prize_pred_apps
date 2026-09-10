import math

import pandas as pd
import streamlit as st


PRIZE_RULES = [
    {"prize": "1", "req_n": 6, "req_e": 0, "unit_10": None,  "pending": True},
    {"prize": "2", "req_n": 5, "req_e": 1, "unit_10": None,  "pending": True},
    {"prize": "3", "req_n": 5, "req_e": 0, "unit_10": None,  "pending": True},
    {"prize": "4", "req_n": 4, "req_e": 1, "unit_10": 9600,  "pending": False},
    {"prize": "5", "req_n": 4, "req_e": 0, "unit_10": 640,   "pending": False},
    {"prize": "6", "req_n": 3, "req_e": 1, "unit_10": 320,   "pending": False},
    {"prize": "7", "req_n": 3, "req_e": 0, "unit_10": 40,    "pending": False},
]

PRIZE_LEVEL_LABELS = {
    "1": "頭獎",
    "2": "二獎",
    "3": "三獎",
    "4": "四獎",
    "5": "五獎",
    "6": "六獎",
    "7": "七獎",
}

PAYOUT_RESULT_VERSION = 10

def _comb(n: int, r: int) -> int:
    if r < 0 or r > n:
        return 0
    return math.comb(n, r)


def _hits_to_prize_level(total_main_hits: int, has_special_hit: bool) -> str:
    key = (total_main_hits, bool(has_special_hit))
    mapping = {
        (6, False): "1",
        (5, True): "2",
        (5, False): "3",
        (4, True): "4",
        (4, False): "5",
        (3, True): "6",
        (3, False): "7",
    }
    return mapping.get(key, "-")


def calculate_banker_leg_summary(bankers: int, legs: int, bet_unit: int):
    total_bets = _comb(legs, 6 - bankers)
    total_cost = total_bets * bet_unit
    return total_bets, total_cost


def calculate_banker_leg_payout(
    bankers: int,
    legs: int,
    hit_banker_main: int,
    hit_legs_main: int,
    extra_in_banker: bool,
    extra_in_legs: bool,
    bet_unit: int,
):
    slots_from_legs = 6 - bankers
    normal_legs_total = legs - (1 if extra_in_legs else 0)
    normal_legs_miss = normal_legs_total - hit_legs_main

    def count_wins(req_n: int, req_e: int) -> int:
        needed_hit_legs = req_n - hit_banker_main
        if needed_hit_legs < 0 or needed_hit_legs > slots_from_legs:
            return 0
        needed_miss_legs = slots_from_legs - needed_hit_legs

        if req_e == 1:
            if extra_in_banker:
                return _comb(hit_legs_main, needed_hit_legs) * _comb(normal_legs_miss, needed_miss_legs)
            if extra_in_legs:
                return _comb(hit_legs_main, needed_hit_legs) * _comb(normal_legs_miss, needed_miss_legs - 1)
            return 0

        if extra_in_banker:
            return 0
        return _comb(hit_legs_main, needed_hit_legs) * _comb(normal_legs_miss, needed_miss_legs)

    rows = []
    total_win_bets = 0
    total_payout_confirmed = 0
    total_pending_win_bets = 0

    for rule in PRIZE_RULES:
        count = int(count_wins(rule["req_n"], rule["req_e"]))
        pending = bool(rule["pending"])

        if pending:
            payout_disp = "等待馬會公佈"
            total_pending_win_bets += count
        else:
            unit = rule["unit_10"] if bet_unit == 10 else rule["unit_10"] // 2
            payout = unit * count
            payout_disp = f"$ {payout:,}"
            total_payout_confirmed += payout
            total_win_bets += count

        total_balls = rule["req_n"] + (0.5 if rule["req_e"] else 0.0)
        rows.append({
            "中獎球數": str(int(total_balls)) if total_balls == int(total_balls) else str(total_balls),
            "獎級": PRIZE_LEVEL_LABELS.get(rule["prize"], rule["prize"]),
            "中獎注數": count,
            "每注派彩": "等待馬會公佈" if pending else f"$ {rule['unit_10'] if bet_unit == 10 else rule['unit_10'] // 2:,}",
            "派彩金額": payout_disp if not pending else "等待馬會公佈",
        })

    return total_win_bets, total_payout_confirmed, total_pending_win_bets, pd.DataFrame(rows)


def build_payout_detail_lines(prize_df: pd.DataFrame) -> list[str]:
    lines = []
    for row in prize_df.to_dict("records"):
        count = int(row["中獎注數"])
        if count <= 0:
            continue

        prize = row["獎級"]
        unit_payout = row["每注派彩"]
        payout = row["派彩金額"]

        if unit_payout == "等待馬會公佈":
            lines.append(f"{prize}: 等待馬會公佈 x {count:,} 注（獎金等馬會公佈）")
            continue

        unit_text = str(unit_payout).replace("$", "").strip()
        lines.append(f"{prize}: {unit_text} x {count:,} 注 = {payout}")
    return lines


def get_actual_prize_level(prize_df: pd.DataFrame) -> str:
    """由實際膽拖拆注結果取得最高中獎獎級，避免只用總球數誤判。"""
    for row in prize_df.to_dict("records"):
        if int(row["中獎注數"]) > 0:
            return str(row["獎級"])
    return "-"


def render_page_styles():
    st.markdown(
        """
        <style>
        .bk-wrap{max-width:520px;margin:0 auto;text-align:left;}
        .bk-note{font-size:14px;line-height:1.6;color:#555;margin:0 0 8px 0;}
        .bk-section{font-size:15px;font-weight:700;color:#1a56db;margin:8px 0 10px 0;}
        .bk-kpi{border:1px solid #e9e9e9;border-radius:12px;padding:10px 12px;background:#fff;margin-bottom:10px;}
        .bk-row{display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid #f2f2f2;}
        .bk-row:last-child{border-bottom:none;}
        .bk-label{font-size:14px;color:#666;}
        .bk-value{font-size:15px;color:#222;font-weight:700;}
        .bk-win{color:#0f766e;}
        .bk-pending{color:#d97706;}
        .bk-dashed{border:none;border-top:2px dashed #c7d2fe;margin:18px 0;}
        .bk-hint{font-size:12px;color:#888;margin:2px 0 6px 0;}
        .bk-rules{background:#f0f4ff;border-radius:8px;padding:8px 12px;margin:0 0 12px 0;font-size:12px;color:#444;line-height:1.8;}
        .bk-rule-note{margin:0 0 6px 0;color:#1f2937;font-weight:600;}
        .bk-rules-table{width:100%;border-collapse:collapse;font-size:12px;margin-top:6px;}
        .bk-rules-table th{background:#dce8ff;color:#1a3a7a;font-weight:700;padding:5px 8px;text-align:center;border:1px solid #b8cdf8;white-space:nowrap;}
        .bk-rules-table td{padding:4px 8px;border:1px solid #ccd9f5;color:#333;vertical-align:middle;}
        .bk-rules-table tr:nth-child(even) td{background:#eaf0ff;}
        .bk-rules-table td:first-child{white-space:nowrap;font-weight:600;}
        .bk-rules-table td:last-child{white-space:nowrap;text-align:center;}
        .bk-table-wrap{max-width:560px;margin:8px auto 0 auto;}
        .bk-toggle-hint{font-size:12px;color:#888;margin:4px 0 8px 0;line-height:1.5;}
        .bk-detail{font-size:14px;line-height:1.8;color:#222;margin:8px 0 10px 0;white-space:pre-wrap;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_banker_leg_page():
    render_page_styles()

    st.markdown('<div class="bk-wrap">', unsafe_allow_html=True)
    st.markdown('<p class="bk-note">六合彩膽拖投注查詢：計算投注注數 / 金額，及中獎派彩金額。</p>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="bk-rules">
        <b>膽拖中獎規則提示：</b>
        <p class="bk-rule-note">膽拖不同於單式、複式，不能只用總命中 5 球或 5.5 球直接判斷三獎、二獎派彩。系統會先按投注膽數及配腳數拆成多注單式，再以中膽數、配腳命中數及特號位置逐注計算注數及獎金。</p>
        <table class="bk-rules-table">
          <thead>
            <tr><th>投注種類</th><th>最低中獎條件</th><th>頭獎中(6個正號碼)</th></tr>
          </thead>
          <tbody>
            <tr><td>1 膽投注</td><td>可以不中膽，只需配腳號碼中 3 個正字</td><td>1膽 + 5 配腳</td></tr>
            <tr><td>2 膽投注</td><td>可以不中膽，只需配腳號碼中 3 個正字</td><td>2膽 + 4 配腳</td></tr>
            <tr><td>3 膽投注</td><td>可以不中膽，只需配腳號碼中 3 個正字</td><td>3膽 + 3 配腳</td></tr>
            <tr><td>4 膽投注</td><td>膽號最少要中 1 個正字 + 2 正字配腳</td><td>4膽 + 2 配腳</td></tr>
            <tr><td>5 膽投注</td><td>膽號最少要中 2 個正字 + 1 正字配腳</td><td>5膽 + 1 配腳</td></tr>
          </tbody>
        </table>
        </div>
        """,
        unsafe_allow_html=True,
    )


    # 已移除重複規則說明，避免 table 下方再出現一行重複提示
    # ── 區塊一：投注查詢 ──────────────────────────────
    st.markdown('<p class="bk-section"> 膽拖投注查詢</p>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        bankers = int(st.number_input(
            "投注膽數(1-5)",
            min_value=1, max_value=5, value=1, step=1,
        ))
    with col2:
        min_legs = 7 - bankers
        max_legs = 49 - bankers
        legs = int(st.number_input(
            f"投注配腳數（{min_legs}–{max_legs}）",
            min_value=min_legs, max_value=max_legs, value=min_legs, step=1,
        ))

    bet_unit = int(st.selectbox(
        "每注金額",
        options=[5, 10],
        index=0,
        format_func=lambda x: f"${x} / 注",
    ))

    total_bets, total_cost = calculate_banker_leg_summary(bankers, legs, bet_unit)

    st.markdown(
        f"""
        <div class="bk-kpi">
            <div class="bk-row"><span class="bk-label">投注方式</span><span class="bk-value">{bankers} 膽 + {legs} 配腳</span></div>
            <div class="bk-row"><span class="bk-label">投注注數</span><span class="bk-value">{total_bets:,} 注</span></div>
            <div class="bk-row"><span class="bk-label">投注金額</span><span class="bk-value">$ {total_cost:,}</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── 分隔線 ────────────────────────────────────────
    st.markdown('<hr class="bk-dashed">', unsafe_allow_html=True)

    # ── 區塊二：中獎派彩查詢 ──────────────────────────
    st.markdown('<p class="bk-section">膽拖中獎派彩查詢</p>', unsafe_allow_html=True)

    st.markdown(
        '<p class="bk-toggle-hint">輸入中獎球數（膽 / 配腳）。如其中一球是特號，請勾選對應位置（算 0.5 球）。設定完成後按「計算派彩」。</p>',
        unsafe_allow_html=True,
    )

    col3, col4 = st.columns(2)
    with col3:
        hit_banker_total = int(st.number_input(
            f"命中膽號數(0 - {bankers})",
            min_value=0,
            max_value=bankers,
            value=0,
            step=1,
            key="bk_hit_banker_total",
        ))
    with col4:
        hit_legs_total = int(st.number_input(
            f"命中配腳數(0 - {legs})",
            min_value=0,
            max_value=legs,
            value=0,
            step=1,
            key="bk_hit_legs_total",
        ))

    special_side = st.radio(
        "特號位置（只能擇一）",
        options=["無", "在膽號", "在配腳"],
        horizontal=True,
        index=0,
        key="bk_special_side",
    )

    current_signature = (PAYOUT_RESULT_VERSION, bankers, legs, bet_unit, hit_banker_total, hit_legs_total, special_side)
    last_signature = st.session_state.get("bk_last_calc_signature")

    # 只要條件有改，先清除舊結果，避免顯示過時派彩表
    if last_signature is not None and current_signature != last_signature:
        st.session_state.pop("bk_last_payout_result", None)

    no_input = (hit_banker_total == 0 and hit_legs_total == 0)
    is_locked = (last_signature == current_signature)
    submit_calc = st.button("計算派彩", type="primary", disabled=(no_input or is_locked))

    if is_locked:
        st.caption("本條件已計算。請先修改任一中獎條件，再按計算派彩。")

    if submit_calc:
        # 注意：這裏要對應 st.radio 的完整選項文字。
        # 若判斷錯誤，網頁會把「在膽號 / 在配腳」當成無特號，派彩就不會計算 0.5 半球。
        extra_in_banker = (special_side == "在膽號")
        extra_in_legs = (special_side == "在配腳")

        if extra_in_banker and hit_banker_total == 0:
            st.error("特號選在膽號時，命中膽號數至少要 1。")
            st.markdown('</div>', unsafe_allow_html=True)
            return
        if extra_in_legs and hit_legs_total == 0:
            st.error("特號選在配腳時，命中配腳數至少要 1。")
            st.markdown('</div>', unsafe_allow_html=True)
            return

        # 若有特號，該邊會扣掉 1 粒正號（特號不算正號）
        hit_banker_main = max(0, hit_banker_total - (1 if extra_in_banker else 0))
        hit_legs_main = max(0, hit_legs_total - (1 if extra_in_legs else 0))

        banker_ball_display = hit_banker_main + (0.5 if extra_in_banker else 0.0)
        leg_ball_display = hit_legs_main + (0.5 if extra_in_legs else 0.0)
        total_hits = banker_ball_display + leg_ball_display

        total_win_bets, total_payout_confirmed, total_pending_win_bets, prize_df = calculate_banker_leg_payout(
            bankers=bankers,
            legs=legs,
            hit_banker_main=hit_banker_main,
            hit_legs_main=hit_legs_main,
            extra_in_banker=bool(extra_in_banker),
            extra_in_legs=bool(extra_in_legs),
            bet_unit=bet_unit,
        )
        actual_prize_level = get_actual_prize_level(prize_df)

        st.session_state["bk_last_calc_signature"] = current_signature
        st.session_state["bk_last_payout_result"] = {
            "result_version": PAYOUT_RESULT_VERSION,
            "extra_in_banker": bool(extra_in_banker),
            "extra_in_legs": bool(extra_in_legs),
            "bankers": bankers,
            "legs": legs,
            "bet_unit": bet_unit,
            "total_bets": total_bets,
            "total_cost": total_cost,
            "banker_ball_display": banker_ball_display,
            "leg_ball_display": leg_ball_display,
            "total_hits": total_hits,
            "actual_prize_level": actual_prize_level,
            "total_win_bets": total_win_bets,
            "total_payout_confirmed": total_payout_confirmed,
            "total_pending_win_bets": total_pending_win_bets,
            "prize_df": prize_df,
        }

    result = st.session_state.get("bk_last_payout_result")
    if result is not None and result.get("result_version") != PAYOUT_RESULT_VERSION:
        st.session_state.pop("bk_last_payout_result", None)
        st.session_state.pop("bk_last_calc_signature", None)
        result = None

    if result is None:
        st.info("請先設定中獎條件，按「計算派彩」後才顯示派彩表。")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    payout_confirmed_str = f"$ {result['total_payout_confirmed']:,}"
    payout_detail_lines = build_payout_detail_lines(result["prize_df"])
    payout_detail_html = "<br>".join(payout_detail_lines) if payout_detail_lines else "沒有中獎獎項明細"

    st.markdown(
        f"""
        <div class="bk-kpi">
            <div class="bk-row"><span class="bk-label">用戶投注條件查詢</span>
                <span class="bk-value">{result['bankers']} 膽 + {result['legs']} 腳，${result['bet_unit']} 注 x {result['total_bets']:,} 注，投注額 $ {result['total_cost']:,}</span></div>
            <div class="bk-row"><span class="bk-label">命中膽 + 配腳總數</span>
                <span class="bk-value">膽 {result['banker_ball_display']:.1f} + 配腳 {result['leg_ball_display']:.1f} = {result['total_hits']:.1f} 球</span></div>
            <div class="bk-row"><span class="bk-label">膽拖派彩會因投注條件不同，即使同樣命中 5 球或 5.5 球，實際中獎注數也可能不同。</span>
                <span class="bk-value"></span></div>
            <div class="bk-row"><span class="bk-label">頭獎、二獎、三獎必須由拆出的單式達成條件，才會計入該獎項派彩。</span>
                <span class="bk-value"></span></div>
            <div class="bk-row"><span class="bk-label">派彩明細</span><span class="bk-value bk-win"></span></div>
            <div class="bk-detail">{payout_detail_html}<br>總派彩 {payout_confirmed_str}</div>
            <div class="bk-row"><span class="bk-label">可計算中獎注數</span><span class="bk-value bk-win">{result['total_win_bets']:,} 注</span></div>
            <div class="bk-row"><span class="bk-label">膽拖投注可計算注數 X 固定派彩金額</span><span class="bk-value bk-win">{payout_confirmed_str}</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="bk-table-wrap">', unsafe_allow_html=True)
    st.dataframe(result["prize_df"], width='stretch', hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)


def main() -> None:
    render_banker_leg_page()


if __name__ == "__main__":
    main()
