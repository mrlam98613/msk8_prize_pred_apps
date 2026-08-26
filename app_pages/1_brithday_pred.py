from pathlib import Path
import base64
import csv
from collections import defaultdict
from datetime import datetime
import sys

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from css import white_black_style


BALLS_DIR = PROJECT_ROOT / "A_msk_balls_png"
PRIZE_SUMMARY_PATH = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M4_lotto_prize_summary.csv"
M6_HISTORY_PATH = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"
BET_PRIZE_DATA_DIR = PROJECT_ROOT / "n_v1_msk_prize_31_num_backtest_pred" / "bet_prize_data"
BET_RECORDS_CSV = BET_PRIZE_DATA_DIR / "bet_records.csv"
NEXT_BET_CSV = BET_PRIZE_DATA_DIR / "nextBetDraw_record.csv"
WIN_RESULTS_CSV = BET_PRIZE_DATA_DIR / "win_results.csv"


PRIZE_TABLE = {
    6.0: ("頭獎", 10_000_000),
    5.5: ("二獎", 1_100_000),
    5.0: ("三獎", 300_000),
    4.5: ("四獎", 9_600),
    4.0: ("五獎", 640),
    3.5: ("六獎", 320),
    3.0: ("七獎", 40),
}


@st.cache_data(show_spinner=False)
def load_ball_image_base64(num: int) -> str:
    img_path = BALLS_DIR / f"{num}.png"
    if not img_path.exists():
        return ""
    return base64.b64encode(img_path.read_bytes()).decode("utf-8")


def read_dict_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames:
            reader.fieldnames = [name.strip().lstrip("\ufeff") for name in reader.fieldnames]
        return [{(key or "").strip().lstrip("\ufeff"): (value or "").strip() for key, value in row.items()} for row in reader]


def format_date_with_weekday(date_text: str) -> str:
    if not date_text:
        return "-"
    try:
        dt = datetime.strptime(date_text, "%Y-%m-%d")
    except ValueError:
        return date_text
    weekday_map = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    return f"{date_text}  {weekday_map[dt.weekday()]}"


def format_money(value: object) -> str:
    try:
        return f"${int(float(value)):,}"
    except (TypeError, ValueError):
        return "-"


def row_to_bet(row: dict[str, str]) -> dict[str, object] | None:
    nums: list[int] = []
    for idx in range(1, 7):
        value = row.get(f"N{idx}", "")
        try:
            num = int(value)
        except ValueError:
            return None
        if not 1 <= num <= 49:
            return None
        nums.append(num)
    bet_date = row.get("bet_date", "").strip()
    if not bet_date:
        return None
    return {"date": bet_date, "nums": nums}


def load_bets(path: Path) -> list[dict[str, object]]:
    bets: list[dict[str, object]] = []
    for row in read_dict_rows(path):
        bet = row_to_bet(row)
        if bet:
            bets.append(bet)
    return bets


def load_latest_prize_summary() -> dict[str, str]:
    rows = read_dict_rows(PRIZE_SUMMARY_PATH)
    return rows[-1] if rows else {}


def load_lotto_results() -> dict[str, dict[str, object]]:
    results: dict[str, dict[str, object]] = {}
    for row in read_dict_rows(M6_HISTORY_PATH):
        date = row.get("nDdate", "").strip()
        try:
            nums = [int(row.get(f"N{idx}", 0)) for idx in range(1, 7)]
            special = int(row.get("N7", 0))
        except ValueError:
            continue
        if date and all(1 <= num <= 49 for num in nums) and 1 <= special <= 49:
            results[date] = {"nums": set(nums), "special": special}
    return results


def get_prize_result(nums: list[int], draw_result: dict[str, object]) -> tuple[set[int], int | None, float, str, int]:
    draw_nums = draw_result["nums"]
    special = draw_result["special"]
    if not isinstance(draw_nums, set) or not isinstance(special, int):
        return set(), None, 0.0, "0", 0

    win_main_set = set(nums) & draw_nums
    win_special = special if special in nums else None
    win_score = len(win_main_set) + (0.5 if win_special and len(win_main_set) < 6 else 0)
    prize_name = "0"
    payout = 0
    for score, prize_data in PRIZE_TABLE.items():
        if win_score >= score:
            prize_name, payout = prize_data
            break
    return win_main_set, win_special, win_score, prize_name, payout


def render_balls(nums: list[int], label: str = "", highlight: dict[str, object] | None = None) -> None:
    highlight = highlight or {}
    main_hits = highlight.get("main", set())
    special_hit = highlight.get("special")
    parts = []

    for num in nums:
        b64 = load_ball_image_base64(num)
        style = "width:32px;height:32px;object-fit:contain;margin-right:3px;"
        if isinstance(main_hits, set) and num in main_hits:
            style += "border:2.5px solid red;border-radius:50%;box-sizing:border-box;"
        elif num == special_hit:
            style += "border:2.5px solid #0074D9;border-radius:6px;box-sizing:border-box;"

        if b64:
            parts.append(f"<img src='data:image/png;base64,{b64}' style='{style}'/>")
        else:
            span_style = "display:inline-block;margin-right:6px;font-weight:800;"
            if isinstance(main_hits, set) and num in main_hits:
                span_style += "border:2.5px solid red;border-radius:50%;padding:2px;"
            elif num == special_hit:
                span_style += "border:2.5px solid #0074D9;border-radius:6px;padding:2px;"
            parts.append(f"<span style='{span_style}'>{num}</span>")

    label_html = f"<span style='font-weight:800;margin-right:8px;'>{label}</span>" if label else ""
    st.markdown(
        f"<div style='display:flex;align-items:center;justify-content:flex-start;"
        f"flex-wrap:nowrap;overflow-x:auto;margin-bottom:4px;'>{label_html}{''.join(parts)}</div>",
        unsafe_allow_html=True,
    )


def render_next_draw_section() -> None:
    summary = load_latest_prize_summary()
    next_draw_date = summary.get("next_draw_date", "")
    next_prize_fund = summary.get("next_draw_prize_fund", "")

    st.markdown(
        '<div class="birthday-next-title">1. 生日號分組下期投注預測</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div class='birthday-next-date'>下期開獎日期： {format_date_with_weekday(next_draw_date)}</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div class='birthday-next-fund'>下期頭獎預測獎金： "
        f"<span>{format_money(next_prize_fund)}</span></div>",
        unsafe_allow_html=True,
    )
    st.markdown("<hr style='margin:8px 0;border:0;border-top:1px solid #999;'>", unsafe_allow_html=True)

    next_bets = load_bets(NEXT_BET_CSV)
    if not next_bets:
        st.info("目前未找到 nextBetDraw_record.csv 的下期預測投注。")
        return

    st.markdown(
        "<div style='margin-bottom:6px'><span style='font-size:1.1rem;font-weight:700;'>下期投注預測：</span></div>",
        unsafe_allow_html=True,
    )
    for idx, bet in enumerate(next_bets, start=1):
        render_balls(bet["nums"], label=f"{idx}注：")  # type: ignore[arg-type]


def render_history_section() -> None:
    st.markdown("<hr style='margin:14px 0;border:0;border-top:2px solid #888;'>", unsafe_allow_html=True)
    st.markdown(
        '<div style="margin-bottom:2px"><h6 style="font-size:1.35rem;font-weight:bold;'
        'display:inline-block;">2. 生日號預測開獎紀錄統計</h6></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='margin-bottom:6px'><span style='font-size:0.95rem;font-weight:700;'>"
        "⭕ 中正號　▣ 中特號</span></div>",
        unsafe_allow_html=True,
    )

    next_draw_date = load_latest_prize_summary().get("next_draw_date", "")
    bets = [bet for bet in load_bets(BET_RECORDS_CSV) if bet["date"] != next_draw_date]
    if not bets:
        st.info("目前未找到 bet_records.csv 的過去投注紀錄。")
        return

    lotto_results = load_lotto_results()
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for bet in bets:
        grouped[str(bet["date"])].append(bet)

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
            nums = bet["nums"]
            if not isinstance(nums, list):
                continue

            if date in lotto_results:
                win_main_set, win_special, win_score, prize_name, payout = get_prize_result(nums, lotto_results[date])
                if payout > 0:
                    win_count += 1
                    total_win += payout
                highlight: dict[str, object] = {"main": win_main_set}
                if win_special:
                    highlight["special"] = win_special
                render_balls(nums, label=f"{idx}注：", highlight=highlight)
                st.markdown(
                    f"<div style='margin:0 0 5px 40px'><span style='font-weight:700;'>"
                    f"中 = {win_score:g} 球 | 獎項：{prize_name} | 派彩：{format_money(payout)}</span></div>",
                    unsafe_allow_html=True,
                )
            else:
                render_balls(nums, label=f"{idx}注：")
                st.markdown(
                    "<div style='margin:0 0 5px 40px'><span style='font-weight:700;'>未開獎</span></div>",
                    unsafe_allow_html=True,
                )
        st.markdown("<hr style='margin:6px 0;border:0;border-top:1px solid #e0e0e0;'>", unsafe_allow_html=True)

    st.markdown("---")
    st.write(f"投注注數：{len(bets)} 注 * 每注 $10")
    st.write(f"投注總金額：{format_money(total_bet)}")
    st.write(f"中獎注數：{win_count} 注，派彩總金額 = {format_money(total_win)}")
    st.write(f"損益金額 = {format_money(total_win - total_bet)}")


def render_home_page() -> None:
    st.markdown(white_black_style, unsafe_allow_html=True)
    st.markdown(
        """
        <style>
        .stMarkdown p, .stMarkdown h6 {
            margin-bottom: 4px !important;
            margin-top: 4px !important;
        }
        .birthday-next-title {
            margin: 8px 0 12px 0 !important;
            color: #0B5CAD !important;
            font-size: 1.35rem !important;
            font-weight: 800 !important;
            line-height: 1.3 !important;
        }
        .birthday-next-date,
        .birthday-next-fund {
            margin-bottom: 6px !important;
            color: #0B5CAD !important;
            font-size: 1.08rem !important;
            font-weight: 800 !important;
            line-height: 1.35 !important;
        }
        .birthday-next-fund {
            margin-bottom: 10px !important;
        }
        .birthday-next-fund span {
            color: #D10000 !important;
            font-weight: 900 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    render_next_draw_section()
    render_history_section()


def main() -> None:
    render_home_page()


if __name__ == "__main__":
    main()
