from pathlib import Path
import base64
import csv
from collections import defaultdict
from datetime import datetime

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent.parent
BALLS_DIR = PROJECT_ROOT / "A_msk_balls_png"
LOTTO_RESULTS_PATH = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M2_last_upgrade_lotto_data.csv"
PRIZE_SUMMARY_PATH = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M4_lotto_prize_summary.csv"
BET_PRIZE_DATA_DIR = PROJECT_ROOT / "n_msk_lotto_prize123_backtest_pred" / "bet_prize_data"
PRIZE123_BET_CSV = BET_PRIZE_DATA_DIR / "prize123_bet.csv"
PRIZE123_NEXT_DRAW_BET_CSV = BET_PRIZE_DATA_DIR / "prize123_nextDraw_bet.csv"


PRIZE_TABLE = {
    6.0: 10_000_000,
    5.5: 1_100_000,
    5.0: 300_000,
    4.5: 9_600,
    4.0: 640,
    3.5: 320,
    3.0: 40,
}

PRIZE_FEATURE_LABELS = {
    "3": "3獎",
    "2": "2獎",
    "1": "1獎",
}


@st.cache_data(show_spinner=False)
def load_ball_image_base64(num: int):
    img_path = BALLS_DIR / f"{num}.png"
    if not img_path.exists():
        return ""
    return base64.b64encode(img_path.read_bytes()).decode("utf-8")


def format_date_with_weekday(date_text: str):
    if not date_text:
        return "-"
    try:
        dt = datetime.strptime(date_text, "%Y-%m-%d")
    except ValueError:
        return date_text
    weekday_map = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    return f"{date_text}  {weekday_map[dt.weekday()]}"


def format_money(value):
    try:
        return f"${int(float(value)):,}"
    except (TypeError, ValueError):
        return "-"


def render_balls(nums, label: str = "", highlight=None):
    if highlight is None:
        highlight = {}
    if not nums:
        st.write("-")
        return

    parts = []
    for n in nums:
        b64 = load_ball_image_base64(int(n))
        style = "width:32px;height:32px;object-fit:contain;margin-right:3px;"
        if highlight.get("main") and n in highlight["main"]:
            style += "border:2.5px solid red;border-radius:50%;box-sizing:border-box;"
        elif highlight.get("special") and n == highlight["special"]:
            style += "border:2.5px solid #0074D9;border-radius:6px;box-sizing:border-box;"

        if b64:
            parts.append(f"<img src='data:image/png;base64,{b64}' style='{style}'/>")
        else:
            span_style = "display:inline-block;margin-right:6px;font-weight:700;"
            if highlight.get("main") and n in highlight["main"]:
                span_style += "border:2.5px solid red;border-radius:50%;box-sizing:border-box;padding:2px;"
            elif highlight.get("special") and n == highlight["special"]:
                span_style += "border:2.5px solid #0074D9;border-radius:6px;box-sizing:border-box;padding:2px;"
            parts.append(f"<span style='{span_style}'>{n}</span>")

    label_html = f"<span style='font-weight:700;margin-right:8px;'>{label}</span>" if label else ""
    st.markdown(
        f"<div style='display:flex;align-items:center;justify-content:flex-start;"
        f"flex-wrap:nowrap;overflow-x:auto;margin-bottom:4px;'>{label_html}{''.join(parts)}</div>",
        unsafe_allow_html=True,
    )


def read_dict_rows(path: Path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames:
            reader.fieldnames = [name.strip().lstrip("\ufeff") for name in reader.fieldnames]
        return [{(k or "").strip().lstrip("\ufeff"): (v or "").strip() for k, v in row.items()} for row in reader]


def row_to_bet(row):
    nums = []
    for i in range(1, 7):
        val = row.get(f"N{i}", "")
        if str(val).isdigit():
            nums.append(int(val))
    if len(nums) != 6 or not all(1 <= n <= 49 for n in nums):
        return None
    prize = str(row.get("prize", "")).strip()
    return {
        "date": str(row.get("bet_date", "")).strip(),
        "nums": nums,
        "prize": prize,
    }


def load_bets(path: Path):
    bets = []
    for row in read_dict_rows(path):
        bet = row_to_bet(row)
        if bet and bet["date"]:
            bets.append(bet)
    return bets


def load_latest_prize_summary():
    rows = read_dict_rows(PRIZE_SUMMARY_PATH)
    if not rows:
        return {}
    return rows[-1]


def load_lotto_results():
    results = {}
    for row in read_dict_rows(LOTTO_RESULTS_PATH):
        date = row.get("ndate", "").strip()
        try:
            nums = [int(row.get(f"N{i}", 0)) for i in range(1, 7)]
            special = int(row.get("N7", 0))
        except ValueError:
            continue
        if date and all(1 <= n <= 49 for n in nums) and 1 <= special <= 49:
            results[date] = {"nums": set(nums), "special": special}
    return results


def get_prize_result(nums, draw_result):
    win_main_set = set(nums) & draw_result["nums"]
    win_special = draw_result["special"] if draw_result["special"] in nums else None
    win_score = len(win_main_set) + (0.5 if win_special else 0)
    prize_name = "0"
    payout = 0
    for score in sorted(PRIZE_TABLE.keys(), reverse=True):
        if win_score >= score:
            payout = PRIZE_TABLE[score]
            prize_name = {
                6.0: "頭獎",
                5.5: "二獎",
                5.0: "三獎",
                4.5: "四獎",
                4.0: "五獎",
                3.5: "六獎",
                3.0: "七獎",
            }[score]
            break
    return win_main_set, win_special, win_score, prize_name, payout


def render_next_draw_section():
    summary = load_latest_prize_summary()
    next_draw_date = summary.get("next_draw_date", "")
    next_prize_fund = summary.get("next_draw_prize_fund", "")

    st.markdown(
        '<div style="margin-bottom:12px;margin-top:8px;"><h6 style="font-size:1.35rem;'
        'font-weight:bold;display:inline-block;">1. 下期 1,2,3 獎特式投注預測</h6></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div style='margin-bottom:6px'><span style='font-size:1.08rem;font-weight:700;'>"
        f"下期開獎日期： {format_date_with_weekday(next_draw_date)}</span></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div style='margin-bottom:10px'><span style='font-size:1.08rem;font-weight:700;'>"
        f"下期頭獎預測獎金： {format_money(next_prize_fund)}</span></div>",
        unsafe_allow_html=True,
    )
    st.markdown("<hr style='margin:8px 0;border:0;border-top:1px solid #999;'>", unsafe_allow_html=True)
    st.markdown(
        "<div style='margin-bottom:6px'><span style='font-size:1.1rem;font-weight:700;'>下期投注預測：</span></div>",
        unsafe_allow_html=True,
    )

    next_bets = load_bets(PRIZE123_NEXT_DRAW_BET_CSV)
    if not next_bets:
        st.info("目前未找到 prize123_nextDraw_bet.csv 的下期預測投注。")
        return

    for idx, bet in enumerate(next_bets, start=1):
        feature_label = PRIZE_FEATURE_LABELS.get(bet["prize"], f"{bet['prize']}獎")
        render_balls(
            bet["nums"],
            label=f"{idx}注：",
        )
        st.markdown(
            f"<div style='margin:0 0 6px 40px'><span style='font-weight:700;'>預測特式：{feature_label}</span></div>",
            unsafe_allow_html=True,
        )


def render_history_section():
    st.markdown("<hr style='margin:14px 0;border:0;border-top:2px solid #888;'>", unsafe_allow_html=True)
    st.markdown(
        '<div style="margin-bottom:2px"><h6 style="font-size:1.35rem;font-weight:bold;'
        'display:inline-block;">2. 特式預測開獎紀錄統計</h6></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='margin-bottom:4px'><span style='font-size:0.95rem;font-weight:700;'>"
        "bet_prize_data / prize123_bet.csv</span></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='margin-bottom:6px'><span style='font-size:0.95rem;font-weight:700;'>"
        "⭕ 中正號　🔲 中特號</span></div>",
        unsafe_allow_html=True,
    )

    summary = load_latest_prize_summary()
    next_draw_date = summary.get("next_draw_date", "")
    bets = [bet for bet in load_bets(PRIZE123_BET_CSV) if bet["date"] != next_draw_date]
    if not bets:
        st.info("目前未找到 prize123_bet.csv 的過去投注紀錄。")
        return

    lotto_results = load_lotto_results()
    grouped = defaultdict(list)
    for bet in bets:
        grouped[bet["date"]].append(bet)

    total_bet = 0
    total_win = 0
    win_count = 0
    bet_amount = 10

    for date in sorted(grouped.keys(), reverse=True):
        st.markdown(
            f"<div style='margin:8px 0 4px'><span style='font-weight:800;'>"
            f"投注日期： {format_date_with_weekday(date)}</span></div>",
            unsafe_allow_html=True,
        )
        for idx, bet in enumerate(grouped[date], start=1):
            total_bet += bet_amount
            feature_label = PRIZE_FEATURE_LABELS.get(bet["prize"], f"{bet['prize']}獎")
            nums = bet["nums"]
            if date in lotto_results:
                win_main_set, win_special, win_score, prize_name, payout = get_prize_result(nums, lotto_results[date])
                if payout > 0:
                    win_count += 1
                    total_win += payout
                highlight = {"main": win_main_set}
                if win_special:
                    highlight["special"] = win_special
                render_balls(nums, label=f"{idx}注：", highlight=highlight)
                st.markdown(
                    f"<div style='margin:0 0 5px 40px'><span style='font-weight:700;'>"
                    f"預測特式：{feature_label} | 中 = {win_score:g} 球 | 獎項：{prize_name} | 派彩：{format_money(payout)}</span></div>",
                    unsafe_allow_html=True,
                )
            else:
                render_balls(nums, label=f"{idx}注：")
                st.markdown(
                    f"<div style='margin:0 0 5px 40px'><span style='font-weight:700;'>"
                    f"預測特式：{feature_label} | 未開獎</span></div>",
                    unsafe_allow_html=True,
                )
        st.markdown("<hr style='margin:6px 0;border:0;border-top:1px solid #e0e0e0;'>", unsafe_allow_html=True)

    st.markdown("---")
    st.write(f"投注注數：{len(bets)} 注 * 每注 $10")
    st.write(f"投注總金額：{format_money(total_bet)}")
    st.write(f"中獎注數：{win_count} 注，派彩總金額 = {format_money(total_win)}")
    st.write(f"損益金額 = {format_money(total_win - total_bet)}")


def render_home_page():
    st.markdown(
        """
        <style>
        .stMarkdown p, .stMarkdown h6 {
            margin-bottom: 4px !important;
            margin-top: 4px !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    render_next_draw_section()
    render_history_section()


def main():
    render_home_page()


if __name__ == "__main__":
    main()
