import math

import pandas as pd
import streamlit as st


PRIZE_RULES = [
    {"score": 6.0, "prize": "頭獎", "x": 6, "y": 0, "unit_10": None, "pending": True},
    {"score": 5.5, "prize": "二獎", "x": 5, "y": 1, "unit_10": None, "pending": True},
    {"score": 5.0, "prize": "三獎", "x": 5, "y": 0, "unit_10": None, "pending": True},
    {"score": 4.5, "prize": "四獎", "x": 4, "y": 1, "unit_10": 9600, "pending": False},
    {"score": 4.0, "prize": "五獎", "x": 4, "y": 0, "unit_10": 640, "pending": False},
    {"score": 3.5, "prize": "六獎", "x": 3, "y": 1, "unit_10": 320, "pending": False},
    {"score": 3.0, "prize": "七獎", "x": 3, "y": 0, "unit_10": 40, "pending": False},
]


def format_score(score: float) -> str:
    return str(int(score)) if float(score).is_integer() else str(score)


def score_to_prize_name(score: float):
    for rule in PRIZE_RULES:
        if float(rule["score"]) == float(score):
            return str(rule["prize"])
    return "未達七獎"


def calculate_bet_summary(bet_num: int, bet_unit: int):
    total_bets = math.comb(bet_num, 6)
    total_cost = total_bets * bet_unit
    return total_bets, total_cost


def calculate_multiple_payout(bet_num: int, hit_main: int, hit_special: int, bet_unit: int = 10):
    if bet_num < 7:
        raise ValueError("複式號碼數量不可少於 7。")
    if not (0 <= hit_main <= 6):
        raise ValueError("中正號數量需介乎 0 至 6。")
    if hit_special not in (0, 1):
        raise ValueError("特別號命中設定只可為 0 或 1。")
    if bet_unit not in (5, 10):
        raise ValueError("每注金額只可為 5 或 10。")

    rows = []
    total_win_bets = 0
    total_payout_confirmed = 0
    total_pending_win_bets = 0

    for rule in PRIZE_RULES:
        x = int(rule["x"])
        y = int(rule["y"])
        if x > hit_main or y > hit_special or (6 - x - y) > (bet_num - hit_main - hit_special):
            count = 0
        else:
            count = (
                math.comb(hit_main, x)
                * math.comb(hit_special, y)
                * math.comb(bet_num - hit_main - hit_special, 6 - x - y)
            )

        total_win_bets += count

        pending = bool(rule["pending"])
        if pending:
            unit_text = "等待馬會公佈"
            payout_text = "待公佈"
            total_pending_win_bets += count
        else:
            base_payout = int(rule["unit_10"])
            unit_payout = base_payout // 2 if bet_unit == 5 else base_payout
            payout = unit_payout * count
            unit_text = f"$ {unit_payout:,}"
            payout_text = f"$ {payout:,}"
            total_payout_confirmed += payout

        rows.append(
            {
                "中獎球數": format_score(float(rule["score"])),
                "獎級": str(rule["prize"]),
                "中獎注數": int(count),
                "每注派彩": unit_text,
                "派彩金額": payout_text,
            }
        )

    return total_win_bets, total_payout_confirmed, total_pending_win_bets, pd.DataFrame(rows)


def render_page_styles():
    st.markdown(
        """
        <style>
        .mb-wrap{max-width:520px;margin:0 auto;text-align:left;}
        .mb-note{font-size:14px;line-height:1.6;color:#555;margin:0 0 8px 0;}
        .mb-title{font-size:16px;line-height:1.5;color:#222;font-weight:700;margin:0 0 10px 0;}
        .mb-kpi{border:1px solid #e9e9e9;border-radius:12px;padding:10px 12px;background:#fff;margin-bottom:10px;}
        .mb-dashed{max-width:520px;margin:12px auto;border-top:2px dashed #d7d7d7;}
        .mb-row{display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid #f2f2f2;}
        .mb-row:last-child{border-bottom:none;}
        .mb-label{font-size:14px;color:#666;}
        .mb-value{font-size:15px;color:#222;font-weight:700;}
        .mb-win{color:#0f766e;}
        .mb-warn{color:#9a5a00;font-weight:700;}
        .mb-table-wrap{max-width:720px;margin:8px auto 0 auto;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_multiple_bet_page():
    render_page_styles()

    st.markdown('<div class="mb-wrap">', unsafe_allow_html=True)
    st.markdown('<p class="mb-note">第一部份：複式投注查詢（7.. 49 個字）</p>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        bet_num = int(st.number_input("複式投注號碼數（7–49）", min_value=7, max_value=49, value=7, step=1))
    with col2:
        bet_unit = int(
            st.selectbox(
                "每注金額",
                options=[5, 10],
                index=0,
                format_func=lambda x: f"${x} / 注",
            )
        )

    st.button("🔄 更新計算", type="primary", width='stretch')

    total_bets, total_cost = calculate_bet_summary(bet_num=bet_num, bet_unit=bet_unit)

    st.markdown(
        f"""
        <div class="mb-kpi">
            <div class="mb-row"><span class="mb-label">投注注數</span><span class="mb-value">{total_bets:,} 注</span></div>
            <div class="mb-row"><span class="mb-label">每注金額</span><span class="mb-value">$ {bet_unit:,}</span></div>
            <div class="mb-row"><span class="mb-label">投注總金額</span><span class="mb-value">$ {total_cost:,}</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('<div class="mb-dashed"></div>', unsafe_allow_html=True)

    st.markdown('<div class="mb-wrap">', unsafe_allow_html=True)
    st.markdown('<p class="mb-note">第二部份：複式中獎派彩查詢</p>', unsafe_allow_html=True)

    col3, col4 = st.columns(2)
    with col3:
        total_hit = int(st.number_input("中獎球數（3–7）", min_value=3, max_value=7, value=3, step=1))
    with col4:
        include_special = st.checkbox("中獎號是/否包含特號", value=False)

    if include_special and total_hit >= 1:
        hit_main = total_hit - 1
        hit_special = 1
    else:
        hit_main = total_hit
        hit_special = 0

    selected_score = float(hit_main) + (0.5 if hit_special else 0.0)
    selected_prize_name = score_to_prize_name(selected_score)
    score_display = f"{format_score(selected_score)} 球 ｜ {selected_prize_name}"
    st.markdown(
        f"""
        <div class="mb-kpi">
            <div class="mb-row"><span class="mb-label">中獎結果</span><span class="mb-value">{score_display}</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('</div>', unsafe_allow_html=True)

    total_win_bets, total_payout_confirmed, total_pending_win_bets, prize_df = calculate_multiple_payout(
        bet_num=bet_num,
        hit_main=hit_main,
        hit_special=hit_special,
        bet_unit=bet_unit,
    )

    st.markdown('<div class="mb-wrap">', unsafe_allow_html=True)
    st.markdown('<div class="mb-title">複式中獎派彩明細</div>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="mb-kpi">
            <div class="mb-row"><span class="mb-label">中獎注數</span><span class="mb-value mb-win">{total_win_bets:,} 注</span></div>
            <div class="mb-row"><span class="mb-label">可計算派彩金額（4-7獎）</span><span class="mb-value mb-win">$ {total_payout_confirmed:,}</span></div>
            <div class="mb-row"><span class="mb-label">待公佈注數（1-3獎）</span><span class="mb-value mb-warn">{total_pending_win_bets:,} 注</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("註：頭獎、二獎、三獎金額會按馬會公告而定，故顯示為待公佈。")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="mb-table-wrap">', unsafe_allow_html=True)
    st.dataframe(prize_df, width='stretch', hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)


def main() -> None:
    render_multiple_bet_page()


if __name__ == "__main__":
    main()
