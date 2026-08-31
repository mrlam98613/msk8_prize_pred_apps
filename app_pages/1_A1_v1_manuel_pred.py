from pathlib import Path
import base64
import csv
import math
import sys
from collections import Counter
from typing import TypedDict

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from css import white_black_style
from custom_components.number_picker import number_picker


M6_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"
M4_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M4_lotto_prize_summary.csv"
BALLS_DIR = PROJECT_ROOT / "A_msk_balls_png"
BET_PRIZE_DATA_DIR = PROJECT_ROOT / "n_v1_msk_prize_31_num_backtest_pred" / "bet_prize_data"
ADMIN_BET_CSV = BET_PRIZE_DATA_DIR / "admin_bet.csv"

PERIOD_COUNTS = [14, 7, 2]
SHOW_RECENT_COMBO = False
BIRTHDAY_GROUPS = {
    1: ("1-9", 1, 9),
    2: ("10-20", 10, 20),
    3: ("21-31", 21, 31),
}


class PeriodStats(TypedDict):
    period: int
    rows: list[dict[str, str]]
    buckets: Counter[str]
    num_freq: Counter[int]
    special_freq: Counter[int]


@st.cache_data(show_spinner=False)
def read_m6_rows() -> list[dict[str, str]]:
    if not M6_CSV.exists():
        return []

    with M6_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames:
            reader.fieldnames = [name.strip().lstrip("\ufeff") for name in reader.fieldnames]
        return [
            {(key or "").strip().lstrip("\ufeff"): (value or "").strip() for key, value in row.items()}
            for row in reader
        ]


def read_csv_rows(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.exists():
        return []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames:
            reader.fieldnames = [name.strip().lstrip("\ufeff") for name in reader.fieldnames]
        return [
            {(key or "").strip().lstrip("\ufeff"): (value or "").strip() for key, value in row.items()}
            for row in reader
        ]


@st.cache_data(show_spinner=False)
def load_ball_image_base64(num: int) -> str:
    img_path = BALLS_DIR / f"{int(num)}.png"
    if not img_path.exists():
        return ""
    return base64.b64encode(img_path.read_bytes()).decode("utf-8")


def parse_nums(row: dict[str, str]) -> list[int]:
    nums: list[int] = []
    for idx in range(1, 7):
        try:
            nums.append(int(row.get(f"N{idx}", "0") or 0))
        except ValueError:
            continue
    return nums


def parse_special(row: dict[str, str]) -> int | None:
    try:
        num = int(row.get("N7", "0") or 0)
    except ValueError:
        return None
    return num if 1 <= num <= 49 else None


def group_nums(nums: list[int], start_num: int, end_num: int) -> list[int]:
    return sorted(num for num in nums if start_num <= num <= end_num)


def period_stats(rows: list[dict[str, str]], period_count: int, start_num: int, end_num: int) -> PeriodStats:
    recent_rows = rows[-period_count:]
    buckets = Counter()
    num_freq = Counter()
    special_freq = Counter()

    for row in recent_rows:
        nums = group_nums(parse_nums(row), start_num, end_num)
        hit_count = len(nums)
        bucket = "4+" if hit_count >= 4 else str(hit_count)
        buckets[bucket] += 1
        num_freq.update(nums)

        special = parse_special(row)
        if special is not None and start_num <= special <= end_num:
            special_freq.update([special])

    return {
        "period": period_count,
        "rows": recent_rows,
        "buckets": buckets,
        "num_freq": num_freq,
        "special_freq": special_freq,
    }


def parse_period_counts(period_text: str) -> list[int]:
    period_counts: list[int] = []
    for part in period_text.replace("，", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            period_count = int(part)
        except ValueError:
            continue
        if period_count > 0 and period_count not in period_counts:
            period_counts.append(period_count)
    return period_counts or PERIOD_COUNTS


def build_period_weights(period_counts: list[int]) -> dict[int, int]:
    ordered_periods = sorted(period_counts, reverse=True)
    return {period_count: idx + 1 for idx, period_count in enumerate(ordered_periods)}


def build_attention_scores(
    rows: list[dict[str, str]],
    start_num: int,
    end_num: int,
    period_counts: list[int],
) -> dict[int, int]:
    scores = {num: 0 for num in range(start_num, end_num + 1)}
    period_weights = build_period_weights(period_counts)
    for period_count in period_counts:
        weight = period_weights[period_count]
        for row in rows[-period_count:]:
            for num in group_nums(parse_nums(row), start_num, end_num):
                scores[num] += weight
            special = parse_special(row)
            if special is not None and start_num <= special <= end_num:
                scores[special] += max(1, weight // 2)
    return scores


def build_special_attention(
    rows: list[dict[str, str]],
    start_num: int,
    end_num: int,
    period_counts: list[int],
) -> dict[int, int]:
    scores = {num: 0 for num in range(start_num, end_num + 1)}
    period_weights = build_period_weights(period_counts)
    for period_count in period_counts:
        weight = period_weights[period_count]
        for row in rows[-period_count:]:
            special = parse_special(row)
            if special is not None and start_num <= special <= end_num:
                scores[special] += weight
    return scores


def build_cold_gaps(rows: list[dict[str, str]], start_num: int, end_num: int) -> dict[int, int]:
    gaps = {num: len(rows) for num in range(start_num, end_num + 1)}
    for num in range(start_num, end_num + 1):
        for gap, row in enumerate(reversed(rows), start=0):
            if num in parse_nums(row):
                gaps[num] = gap
                break
    return gaps


def build_cold_nums(
    rows: list[dict[str, str]],
    start_num: int,
    end_num: int,
    period_counts: list[int],
    limit: int = 3,
) -> list[int]:
    """正號多期未出，且特號在分析期內沒有出現，才列為冷門號。"""

    cold_gaps = build_cold_gaps(rows, start_num, end_num)
    special_scores = build_special_attention(rows, start_num, end_num, period_counts)
    candidates = [num for num in cold_gaps if special_scores.get(num, 0) == 0]
    return sorted(candidates, key=lambda num: (-cold_gaps[num], num))[:limit]


def build_watch_nums(
    rows: list[dict[str, str]],
    start_num: int,
    end_num: int,
    period_counts: list[int],
    base_limit: int = 5,
) -> list[int]:
    scores = build_attention_scores(rows, start_num, end_num, period_counts)
    special_scores = build_special_attention(rows, start_num, end_num, period_counts)
    cold_gaps = build_cold_gaps(rows, start_num, end_num)
    watch_nums = sorted(scores, key=lambda num: (-scores[num], -cold_gaps[num], num))[:base_limit]

    ordered_periods = sorted(period_counts, reverse=True) if period_counts else PERIOD_COUNTS
    cold_threshold = ordered_periods[1] if len(ordered_periods) >= 2 else ordered_periods[0]
    special_cold_nums = [
        num
        for num in range(start_num, end_num + 1)
        if cold_gaps.get(num, 0) >= cold_threshold and special_scores.get(num, 0) > 0
    ]
    for num in sorted(special_cold_nums, key=lambda value: (-cold_gaps[value], -special_scores[value], value)):
        if num not in watch_nums:
            watch_nums.append(num)
    return watch_nums


def trend_label(stats_by_period: dict[int, PeriodStats], period_counts: list[int]) -> str:
    def avg_hits(stats: PeriodStats) -> float:
        buckets = stats["buckets"]
        total = int(stats["period"])
        score = buckets["1"] + buckets["2"] * 2 + buckets["3"] * 3 + buckets["4+"] * 4
        return score / total if total else 0

    ordered_periods = sorted(period_counts, reverse=True)
    averages = [avg_hits(stats_by_period[period_count]) for period_count in ordered_periods]
    if len(averages) < 2:
        return "穩定"

    if all(next_avg >= current_avg for current_avg, next_avg in zip(averages, averages[1:])) and averages[-1] > averages[0]:
        return "升溫"
    if all(next_avg <= current_avg for current_avg, next_avg in zip(averages, averages[1:])) and averages[-1] < averages[0]:
        return "回落"
    return "穩定"


def mini_bar(value: int, max_value: int, width: int = 8) -> str:
    filled = 0 if max_value <= 0 else round(value / max_value * width)
    blocks = []
    for idx in range(width):
        color = "#2563eb" if idx < filled else "#cbd5e1"
        blocks.append(
            f'<span style="display:inline-block;width:9px;height:12px;'
            f'background-color:{color};border-radius:2px;margin-right:2px;'
            f'vertical-align:-1px;"></span>'
        )
    return "".join(blocks)


def render_styles() -> None:
    st.markdown(white_black_style, unsafe_allow_html=True)
    st.markdown(
        """
        <style>
        .a1-card{border:1px solid #e5e7eb;border-radius:8px;padding:10px 12px;margin:8px 0;background:#fff;}
        .a1-title{font-size:17px;font-weight:800;color:#111827;margin-bottom:4px;}
        .a1-line{font-size:14px;line-height:1.7;color:#1f2937;white-space:nowrap;overflow-x:auto;}
        .a1-bet-line{font-size:16px;line-height:1.8;color:#111827;font-weight:800;white-space:nowrap;overflow-x:auto;}
        .a1-ball-row{display:flex;align-items:center;gap:4px;flex-wrap:wrap;margin:4px 0 8px 0;}
        .a1-ball-row img{width:34px;height:34px;object-fit:contain;}
        .a1-plus{font-size:20px;font-weight:900;margin:0 5px;color:#111827;}
        .a1-muted{font-size:12px;line-height:1.55;color:#6b7280;margin-bottom:6px;}
        .a1-save-status{font-size:13px;line-height:1.6;color:#6b7280;margin:4px 0 6px 0;}
        .a1-tag{display:inline-block;min-width:42px;font-weight:800;color:#0f766e;}
        .a1-hot{color:#b91c1c;font-weight:800;}
        .a1-cold{color:#1d4ed8;font-weight:800;}
        .a1-special{color:#7c3aed;font-weight:800;}
        .a1-bar-active{color:#2563eb;font-weight:900;}
        .a1-bar-muted{color:#cbd5e1;font-weight:900;}
        [data-testid="stTextInput"] [data-baseweb="input"] > div {
            border: 1.5px solid #9ca3af !important;
            border-radius: 8px !important;
            background-color: #ffffff !important;
            box-shadow: none !important;
        }
        [data-testid="stTextInput"] [data-baseweb="input"] > div:focus-within {
            border-color: #2563eb !important;
            box-shadow: 0 0 0 1px #2563eb !important;
        }
        [data-testid="stButton"] button[kind="primary"]:disabled,
        [data-testid="stButton"] button[kind="primary"][disabled] {
            background-color: #f3f4f6 !important;
            color: #9ca3af !important;
            border-color: #d1d5db !important;
            opacity: 1 !important;
        }
        [data-testid="stButton"] button[kind="primary"]:disabled *,
        [data-testid="stButton"] button[kind="primary"][disabled] * {
            color: #9ca3af !important;
            -webkit-text-fill-color: #9ca3af !important;
        }
        @media (max-width:430px){
            .a1-card{padding:9px 10px;}
            .a1-title{font-size:16px;}
            .a1-line{font-size:13px;}
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_group_card(
    group_name: str,
    start_num: int,
    end_num: int,
    rows: list[dict[str, str]],
    period_counts: list[int],
) -> None:
    stats_by_period = {
        period_count: period_stats(rows, period_count, start_num, end_num)
        for period_count in period_counts
    }
    trend = trend_label(stats_by_period, period_counts)
    scores = build_attention_scores(rows, start_num, end_num, period_counts)
    special_scores = build_special_attention(rows, start_num, end_num, period_counts)
    cold_gaps = build_cold_gaps(rows, start_num, end_num)
    hot_nums = sorted(scores, key=lambda num: (-scores[num], num))[:3]
    special_nums = [num for num in sorted(special_scores, key=lambda num: (-special_scores[num], num)) if special_scores[num] > 0][:3]
    cold_nums = build_cold_nums(rows, start_num, end_num, period_counts)
    watch_nums = build_watch_nums(rows, start_num, end_num, period_counts)

    st.markdown('<div class="a1-card">', unsafe_allow_html=True)
    st.markdown(f'<div class="a1-title">[{group_name}] 趨勢：{trend}</div>', unsafe_allow_html=True)
    for period_count in period_counts:
        stats = stats_by_period[period_count]
        buckets = stats["buckets"]
        strong_count = buckets["3"] + buckets["4+"]
        bar = mini_bar(strong_count, period_count)
        st.markdown(
            f'<div class="a1-line"><span class="a1-tag">{period_count}期</span>{bar} '
            f'4+:{buckets["4+"]}｜3:{buckets["3"]}｜2:{buckets["2"]}｜1:{buckets["1"]}｜0:{buckets["0"]}</div>',
            unsafe_allow_html=True,
        )

    hot_text = "，".join(f"{num}({scores[num]})" for num in hot_nums)
    special_text = "，".join(f"{num}(特{special_scores[num]})" for num in special_nums) if special_nums else "-"
    cold_text_parts = []
    for num in cold_nums:
        special_count = special_scores[num]
        if special_count > 0:
            cold_text_parts.append(f"{num}({cold_gaps[num]}期未出｜特號{special_count}次)")
        else:
            cold_text_parts.append(f"{num}({cold_gaps[num]}期未出)")
    cold_text = "，".join(cold_text_parts)
    watch_text = "，".join(f"{num}[特]" if special_scores[num] > 0 else str(num) for num in watch_nums)
    st.markdown(f'<div class="a1-line">熱號：<span class="a1-hot">{hot_text}</span></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="a1-line">特號注意：<span class="a1-special">{special_text}</span></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="a1-line">正號冷號：<span class="a1-cold">{cold_text}</span></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="a1-line">注視號：{watch_text}</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def build_dim_numbers_for_groups(
    rows: list[dict[str, str]],
    group_options: list[int],
    period_counts: list[int],
) -> list[int]:
    dim_numbers: set[int] = set()
    for group_option in group_options:
        _group_name, start_num, end_num = BIRTHDAY_GROUPS[int(group_option)]
        cold_nums = build_cold_nums(rows, start_num, end_num, period_counts)
        dim_numbers.update(cold_nums)
    return sorted(dim_numbers)


def build_watch_numbers_for_groups(
    rows: list[dict[str, str]],
    group_options: list[int],
    period_counts: list[int],
) -> dict[str, list[int]]:
    """集合已選分組的注視號，供手動投注鍵盤上方參考。"""

    watch_map: dict[str, list[int]] = {}
    for group_option in group_options:
        group_name, start_num, end_num = BIRTHDAY_GROUPS[int(group_option)]
        watch_nums = build_watch_nums(rows, start_num, end_num, period_counts)
        watch_map[group_name] = watch_nums
    return watch_map


def build_special_cold_numbers_for_groups(
    rows: list[dict[str, str]],
    group_options: list[int],
    period_counts: list[int],
) -> list[int]:
    special_cold_nums: set[int] = set()
    ordered_periods = sorted(period_counts, reverse=True) if period_counts else PERIOD_COUNTS
    cold_threshold = ordered_periods[1] if len(ordered_periods) >= 2 else ordered_periods[0]
    for group_option in group_options:
        _group_name, start_num, end_num = BIRTHDAY_GROUPS[int(group_option)]
        special_scores = build_special_attention(rows, start_num, end_num, period_counts)
        cold_gaps = build_cold_gaps(rows, start_num, end_num)
        for num in range(start_num, end_num + 1):
            if cold_gaps.get(num, 0) >= cold_threshold and special_scores.get(num, 0) > 0:
                special_cold_nums.add(num)
    return sorted(special_cold_nums)


def render_watch_numbers_hint(watch_map: dict[str, list[int]], extra_watch_nums: list[int] | None = None) -> None:
    """在數字鍵盤上方顯示注視號集合。"""

    if not watch_map:
        return

    extra_watch_nums = extra_watch_nums or []
    group_parts = [
        f"{group_name}:{format_nums(nums)}"
        for group_name, nums in watch_map.items()
        if nums
    ]
    all_watch_nums = sorted({num for nums in watch_map.values() for num in nums} | set(extra_watch_nums))
    if not group_parts or not all_watch_nums:
        return

    st.markdown(
        f'<div class="a1-line">1-31 預測注視號：{format_nums(all_watch_nums)} '
        f'/> {len(all_watch_nums)} 球</div>'
        f'<div class="a1-muted">分組注視球：</div>'
        f'<div class="a1-muted">{" ｜ ".join(group_parts)}</div>',
        unsafe_allow_html=True,
    )


def render_dim_numbers_hint(dim_numbers: list[int]) -> None:
    if not dim_numbers:
        return
    st.caption(f"灰色號碼 = 目前分析冷門球號：{', '.join(str(num) for num in dim_numbers)}，仍可選取。")


def load_next_draw_date() -> str:
    rows = read_csv_rows(M4_CSV)
    if not rows:
        return ""
    return rows[-1].get("next_draw_date", "").strip()


def init_admin_bet_state() -> None:
    st.session_state.setdefault("admin_standard_nums", [])
    st.session_state.setdefault("admin_banker_nums", [])
    st.session_state.setdefault("admin_leg_nums", [])
    st.session_state.setdefault("admin_standard_reset_token", 0)
    st.session_state.setdefault("admin_banker_reset_token", 0)
    st.session_state.setdefault("admin_leg_reset_token", 0)
    st.session_state.setdefault("admin_pick_mode", "膽")
    st.session_state.setdefault("admin_saved_notice", "")


def reset_admin_bet_state() -> None:
    st.session_state["admin_standard_nums"] = []
    st.session_state["admin_banker_nums"] = []
    st.session_state["admin_leg_nums"] = []
    st.session_state["admin_standard_reset_token"] += 1
    st.session_state["admin_banker_reset_token"] += 1
    st.session_state["admin_leg_reset_token"] += 1
    st.session_state["admin_saved_notice"] = ""


def write_admin_bet_record(record: dict[str, str]) -> None:
    BET_PRIZE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = ["bet_date", "bet_type", "bet_unit", "total_bets", "total_cost", "numbers", "bankers", "legs"]
    records = read_csv_rows(ADMIN_BET_CSV)
    records.append(record)
    write_admin_bet_records(records)


def write_admin_bet_records(records: list[dict[str, str]]) -> None:
    BET_PRIZE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = ["bet_date", "bet_type", "bet_unit", "total_bets", "total_cost", "numbers", "bankers", "legs"]
    with ADMIN_BET_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def format_nums(nums: list[int]) -> str:
    return "[" + ",".join(str(num) for num in nums) + "]"


def parse_num_list(text: str) -> list[int]:
    nums: list[int] = []
    for part in text.strip().strip("[]").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            nums.append(int(part))
        except ValueError:
            continue
    return nums


def build_ball_image_html(nums: list[int]) -> str:
    parts: list[str] = []
    for num in nums:
        b64 = load_ball_image_base64(num)
        if b64:
            parts.append(f"<img src='data:image/png;base64,{b64}' alt='{num}'/>")
        else:
            parts.append(f"<span style='font-size:16px;font-weight:900;margin-right:4px;'>{num}</span>")
    return "".join(parts)


def render_ball_box(label: str, nums: list[int], bankers: list[int] | None = None, legs: list[int] | None = None) -> None:
    if bankers is not None or legs is not None:
        body = (
            build_ball_image_html(bankers or [])
            + '<span class="a1-plus">+</span>'
            + build_ball_image_html(legs or [])
        )
    else:
        body = build_ball_image_html(nums)
    st.markdown(
        f'<div class="a1-bet-line">{label}</div><div class="a1-ball-row">{body}</div>',
        unsafe_allow_html=True,
    )


def build_admin_record(
    bet_date: str,
    bet_type: str,
    bet_unit: int,
    nums: list[int],
    bankers: list[int] | None = None,
    legs: list[int] | None = None,
) -> dict[str, str]:
    bankers = bankers or []
    legs = legs or []
    if bet_type == "單式":
        total_bets = 1
    elif bet_type == "複式":
        total_bets = math.comb(len(nums), 6) if len(nums) >= 7 else 0
    else:
        total_bets = math.comb(len(legs), 6 - len(bankers)) if 1 <= len(bankers) <= 5 and len(legs) >= 7 - len(bankers) else 0

    return {
        "bet_date": bet_date,
        "bet_type": bet_type,
        "bet_unit": str(bet_unit),
        "total_bets": str(total_bets),
        "total_cost": str(total_bets * bet_unit),
        "numbers": format_nums(nums),
        "bankers": format_nums(bankers) if bankers else "",
        "legs": format_nums(legs) if legs else "",
    }


def render_admin_record_line(record: dict[str, str]) -> str:
    bet_date = record.get("bet_date", "")
    bet_type = record.get("bet_type", "")
    if bet_type == "膽拖":
        body = f"{record.get('bankers', '[]')} + {record.get('legs', '[]')}"
    else:
        body = record.get("numbers", "[]")
    return f"{bet_date} {bet_type} {body}"


def format_record_money(value: str) -> str:
    try:
        return f"${int(float(value)):,}"
    except (TypeError, ValueError):
        return "$0"


def render_admin_record_html(record: dict[str, str]) -> str:
    bet_date = record.get("bet_date", "")
    bet_type = record.get("bet_type", "")
    bet_unit = record.get("bet_unit", "5")
    total_bets = record.get("total_bets", "0")
    total_cost = record.get("total_cost", "0")
    if bet_type == "膽拖":
        bankers = parse_num_list(record.get("bankers", ""))
        legs = parse_num_list(record.get("legs", ""))
        title = (
            f"{bet_date} {bet_type}，{len(bankers)}膽 + {len(legs)}腳，"
            f"${bet_unit} X {total_bets} 注 = {format_record_money(total_cost)}"
        )
        body = (
            build_ball_image_html(bankers)
            + '<span class="a1-plus">+</span>'
            + build_ball_image_html(legs)
        )
    elif bet_type == "複式":
        title = f"{bet_date} {bet_type}，${bet_unit} X {total_bets} 注 = {format_record_money(total_cost)}"
        body = build_ball_image_html(parse_num_list(record.get("numbers", "")))
    else:
        title = f"{bet_date} {bet_type}，投注 ${bet_unit}"
        body = build_ball_image_html(parse_num_list(record.get("numbers", "")))
    return (
        f'<div class="a1-bet-line">{title}</div>'
        f'<div class="a1-ball-row">{body}</div>'
    )


def render_admin_bet_records() -> None:
    records = read_csv_rows(ADMIN_BET_CSV)
    if not records:
        st.info("未有 admin_bet.csv 趨勢投注紀錄。")
        return

    st.markdown("#### 已存管理員趨勢投注紀錄")
    for record in records[-12:][::-1]:
        st.markdown(render_admin_record_html(record), unsafe_allow_html=True)


def render_admin_bet_manager() -> None:
    records = read_csv_rows(ADMIN_BET_CSV)
    if not records:
        return

    st.markdown("#### 總投注存檔")
    st.caption("可逐筆刪除，或勾選多筆後刪除。全選刪除會清空本地 admin_bet.csv 紀錄。")

    selected_indexes: list[int] = []
    for idx, record in enumerate(records):
        if record.get("bet_type") == "膽拖":
            bet_nums = f"{record.get('bankers', '[]')} + {record.get('legs', '[]')}"
        else:
            bet_nums = record.get("numbers", "[]")

        cols = st.columns([0.13, 0.67, 0.2])
        checked = cols[0].checkbox("刪除", key=f"admin_bet_delete_pick_{idx}", label_visibility="collapsed")
        if checked:
            selected_indexes.append(idx)
        cols[1].markdown(
            f"**{idx + 1}. {record.get('bet_date', '')} {record.get('bet_type', '')}**  \n"
            f"{bet_nums}  \n"
            f"${record.get('bet_unit', '')} X {record.get('total_bets', '')} 注 = "
            f"{format_record_money(record.get('total_cost', '0'))}"
        )
        if cols[2].button("刪除", key=f"admin_bet_delete_one_{idx}", width="stretch"):
            remaining_records = [item for row_idx, item in enumerate(records) if row_idx != idx]
            write_admin_bet_records(remaining_records)
            st.success(f"已刪除第 {idx + 1} 筆投注紀錄。")
            st.rerun()

    cols = st.columns(2)
    if cols[0].button("刪除已選", type="secondary", width="stretch", disabled=not selected_indexes):
        remaining_records = [record for idx, record in enumerate(records) if idx not in set(selected_indexes)]
        write_admin_bet_records(remaining_records)
        st.success(f"已刪除 {len(selected_indexes)} 筆投注紀錄。")
        st.rerun()

    if cols[1].button("全選刪除", type="secondary", width="stretch"):
        write_admin_bet_records([])
        st.success("已清空全部投注紀錄。")
        st.rerun()


def render_admin_manual_bet(dim_numbers: list[int], watch_map: dict[str, list[int]]) -> None:
    init_admin_bet_state()
    st.markdown("### 手動輸入下期預測投注")
    bet_date = st.text_input("投注日期", value=load_next_draw_date() or "", key="admin_bet_date")
    bet_type = st.radio(
        "投注格式",
        ["單式", "複式", "膽拖"],
        horizontal=True,
        key="admin_bet_type",
        on_change=reset_admin_bet_state,
    )

    bet_unit = int(st.selectbox("每注金額", [5, 10], index=0, format_func=lambda value: f"${value}", key="admin_bet_unit"))
    saved_notice = st.session_state.get("admin_saved_notice", "")
    can_save = False
    record: dict[str, str] | None = None

    if bet_type in {"單式", "複式"}:
        max_select = 6 if bet_type == "單式" else int(st.selectbox("複式球數", list(range(7, 16)), key="admin_multiple_size"))
        nums = sorted(int(num) for num in st.session_state["admin_standard_nums"])[:max_select]
        render_ball_box("球圖框", nums)
        render_dim_numbers_hint(dim_numbers)
        render_watch_numbers_hint(watch_map, st.session_state.get("admin_extra_watch_nums", []))
        st.caption("輸入按鈕 1-31")
        selected = number_picker(
            selected=nums,
            max_select=max_select,
            max_number=31,
            dim_numbers=dim_numbers,
            reset_token=st.session_state["admin_standard_reset_token"],
            key=f"admin_standard_picker_{bet_type}_{max_select}_{st.session_state['admin_standard_reset_token']}",
        )
        nums = sorted(int(num) for num in selected)
        if nums != st.session_state["admin_standard_nums"]:
            st.session_state["admin_standard_nums"] = nums
            st.session_state["admin_saved_notice"] = ""
            st.rerun()
        can_save = bool(bet_date) and len(nums) == max_select
        record = build_admin_record(bet_date, bet_type, bet_unit, nums)
    else:
        banker_count = int(st.selectbox("膽數", list(range(1, 6)), key="admin_banker_count", on_change=reset_admin_bet_state))
        min_leg_count = 7 - banker_count
        leg_count = int(st.selectbox("配腳數", list(range(min_leg_count, 50 - banker_count)), key="admin_leg_count", on_change=reset_admin_bet_state))
        bankers = sorted(int(num) for num in st.session_state["admin_banker_nums"])[:banker_count]
        legs = sorted(int(num) for num in st.session_state["admin_leg_nums"] if int(num) not in bankers)[:leg_count]
        render_ball_box("球圖框", [], bankers=bankers, legs=legs)
        render_dim_numbers_hint(dim_numbers)
        render_watch_numbers_hint(watch_map, st.session_state.get("admin_extra_watch_nums", []))
        st.caption("輸入按鈕 1-31")
        pick_mode = st.radio("選號模式", ["膽", "配腳"], horizontal=True, key="admin_pick_mode")

        if pick_mode == "膽":
            selected = number_picker(
                selected=bankers,
                max_select=banker_count,
                max_number=31,
                dim_numbers=dim_numbers,
                reset_token=st.session_state["admin_banker_reset_token"],
                key=f"admin_banker_picker_{banker_count}_{st.session_state['admin_banker_reset_token']}",
            )
            new_bankers = sorted(int(num) for num in selected)
            if new_bankers != bankers:
                st.session_state["admin_banker_nums"] = new_bankers
                st.session_state["admin_leg_nums"] = [num for num in legs if num not in new_bankers]
                st.session_state["admin_saved_notice"] = ""
                st.rerun()
        else:
            selected = number_picker(
                selected=legs,
                max_select=leg_count,
                max_number=31,
                dim_numbers=dim_numbers,
                disabled_numbers=bankers,
                reset_token=st.session_state["admin_leg_reset_token"],
                key=f"admin_leg_picker_{leg_count}_{st.session_state['admin_leg_reset_token']}",
            )
            new_legs = sorted(int(num) for num in selected if int(num) not in bankers)
            if new_legs != legs:
                st.session_state["admin_leg_nums"] = new_legs
                st.session_state["admin_saved_notice"] = ""
                st.rerun()

        can_save = bool(bet_date) and len(bankers) == banker_count and len(legs) == leg_count
        record = build_admin_record(bet_date, bet_type, bet_unit, sorted(bankers + legs), bankers, legs)

    if can_save:
        st.markdown('<div class="a1-save-status">已選夠號碼，可以存檔。</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="a1-save-status">未選夠號碼，存檔按鈕暫時灰色停用。</div>', unsafe_allow_html=True)

    cols = st.columns(2)
    if cols[0].button("清除選號", type="secondary", width="stretch"):
        reset_admin_bet_state()
        st.rerun()
    if cols[1].button("存檔", type="primary", width="stretch", disabled=not can_save):
        assert record is not None
        write_admin_bet_record(record)
        st.session_state["admin_saved_notice"] = f"已存檔：{render_admin_record_line(record)}"
        st.rerun()

    if saved_notice:
        st.success(saved_notice)
    render_admin_bet_records()
    render_admin_bet_manager()


def render_recent_combo(rows: list[dict[str, str]]) -> None:
    st.markdown("### 最近 12 期組合")
    st.markdown('<div class="a1-muted">格式：[1-9, 10-20, 21-31]，只計 N1-N6 正號。</div>', unsafe_allow_html=True)
    for row in reversed(rows[-12:]):
        nums = parse_nums(row)
        counts = [
            len(group_nums(nums, 1, 9)),
            len(group_nums(nums, 10, 20)),
            len(group_nums(nums, 21, 31)),
        ]
        date_text = row.get("nDdate", "-")
        nums_text = ", ".join(str(num) for num in nums)
        st.markdown(
            f'<div class="a1-line">{date_text}　[{counts[0]}, {counts[1]}, {counts[2]}]　{nums_text}</div>',
            unsafe_allow_html=True,
        )


def main() -> None:
    render_styles()
    rows = read_m6_rows()
    st.subheader("A1_v1 生日號趨勢圖")
    st.caption("手機簡約版：最近 14 / 7 / 2 期分組趨勢、熱冷號及注視力。")

    if not rows:
        st.error(f"找不到或未能讀取 M6：{M6_CSV}")
        return

    latest_date = rows[-1].get("nDdate", "-")
    st.markdown(f'<div class="a1-muted">資料期數：{len(rows)}｜最新開獎期日期：{latest_date}</div>', unsafe_allow_html=True)

    period_text = st.text_input(
        "請輸入分析遠近期數設定為[14,7,2]",
        value=",".join(str(num) for num in PERIOD_COUNTS),
        help="例如：14,7,2",
    )
    period_counts = parse_period_counts(period_text)
    group_options = st.multiselect(
        "分析分組",
        options=list(BIRTHDAY_GROUPS.keys()),
        default=list(BIRTHDAY_GROUPS.keys()),
        format_func=lambda key: BIRTHDAY_GROUPS[int(key)][0],
    )
    if not group_options:
        st.warning("請最少選擇一個分析分組。")
        return

    st.markdown(
        f'<div class="a1-muted">目前參數：期數 {period_counts}｜分組 {list(group_options)}</div>',
        unsafe_allow_html=True,
    )

    for group_option in group_options:
        group_name, start_num, end_num = BIRTHDAY_GROUPS[int(group_option)]
        render_group_card(group_name, start_num, end_num, rows, period_counts)

    dim_numbers = build_dim_numbers_for_groups(
        rows,
        [int(group_option) for group_option in group_options],
        period_counts,
    )
    watch_map = build_watch_numbers_for_groups(
        rows,
        [int(group_option) for group_option in group_options],
        period_counts,
    )
    st.session_state["admin_extra_watch_nums"] = build_special_cold_numbers_for_groups(
        rows,
        [int(group_option) for group_option in group_options],
        period_counts,
    )
    render_admin_manual_bet(dim_numbers, watch_map)

    if SHOW_RECENT_COMBO:
        render_recent_combo(rows)


if __name__ == "__main__":
    main()
