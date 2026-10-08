from __future__ import annotations

import csv
import html
from collections import Counter
from pathlib import Path
from typing import Optional, TypedDict, Union

import streamlit as st

from app_pages.shared_style import apply_new_page_style, page_header, section_title


PROJECT_ROOT = Path(__file__).resolve().parents[1]
M6_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"

BACKTEST_DRAW_COUNT_LIST = [19]
SELECT_GROUPS = (1, 2, 3, 4)
COMBINATION_TAKE_COUNT = 5
BIRTHDAY_NUM_MATCH_MODE = ">="
PRIZE_OPTION = 3
PRIZE_PRINT_SHOW = True
PRINT_ABCD_PROPERTY_ANALYSIS = True
PRINT_HIGH_FREQ_PAIR_ANALYSIS = True
PRINT_WEAK_NUM_ANALYSIS = True
HIGH_FREQ_MIN_PAIR_COUNT = 2
PRINT_DIMENSION_HOT_NUM_ANALYSIS = True
DIMENSION_DRAW_COUNT = 6
DIMENSION_HOT_MIN_COUNT = 2
DEFAULT_BACKTEST_DRAW_COUNT = 19
DEFAULT_SELECT_GROUPS = "1,2,3,4"
DEFAULT_COMBINATION_TAKE_COUNT = 5
DEFAULT_MATCH_MODE = ">="
DEFAULT_PRIZE_OPTION = 3
DEFAULT_PRIZE_PRINT_SHOW = True
PARAM_STATE_KEYS = {
    "prr_v3_backtest_text": str(DEFAULT_BACKTEST_DRAW_COUNT),
    "prr_v3_groups_text": DEFAULT_SELECT_GROUPS,
    "prr_v3_take_count": DEFAULT_COMBINATION_TAKE_COUNT,
    "prr_v3_match_mode": DEFAULT_MATCH_MODE,
    "prr_v3_prize_option": DEFAULT_PRIZE_OPTION,
    "prr_v3_prize_print_show": DEFAULT_PRIZE_PRINT_SHOW,
}

GROUPS = {
    1: ("A", "1-9", 1, 9),
    2: ("B", "10-20", 10, 20),
    3: ("C", "21-31", 21, 31),
    4: ("D", "32-40", 32, 40),
}


class DrawRow(TypedDict):
    date: str
    nums: list[int]
    special: Optional[int]
    prize_count: float


def to_int(value: object, default: int = 0) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def to_float(value: object, default: float = 0.0) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def parse_int_list(raw_text: str) -> list[int]:
    cleaned = (
        raw_text.replace("[", " ")
        .replace("]", " ")
        .replace("(", " ")
        .replace(")", " ")
        .replace("，", ",")
    )
    values: list[int] = []
    for item in cleaned.split(","):
        item = item.strip()
        if item:
            values.append(to_int(item))
    return values


def format_input_numbers(values: Union[list[int], tuple[int, ...]]) -> str:
    return ",".join(str(value) for value in values)


@st.cache_data(show_spinner=False)
def read_draws(prize_option: int) -> list[DrawRow]:
    if not M6_CSV.exists():
        raise FileNotFoundError(f"找不到 CSV：{M6_CSV}")

    rows: list[DrawRow] = []
    with M6_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames:
            reader.fieldnames = [name.strip().lstrip("\ufeff") for name in reader.fieldnames]
        for raw in reader:
            date = (raw.get("nDdate") or "").strip()
            if not date:
                continue
            special = to_int(raw.get("N7"))
            rows.append(
                {
                    "date": date,
                    "nums": [to_int(raw.get(f"N{index}")) for index in range(1, 7)],
                    "special": special if 1 <= special <= 49 else None,
                    "prize_count": to_float(raw.get(f"prize{prize_option}")),
                }
            )
    return rows


def selected_groups() -> list[tuple[str, str, int, int]]:
    return [GROUPS[group_id] for group_id in SELECT_GROUPS]


def selected_group_codes_text() -> str:
    return "(" + ",".join(GROUPS[group_id][0] for group_id in SELECT_GROUPS) + ")"


def selected_group_ids_text() -> str:
    return "(" + ", ".join(str(group_id) for group_id in SELECT_GROUPS) + ")"


def selected_group_ids() -> tuple[int, ...]:
    return tuple(SELECT_GROUPS)


def selected_normal_nums(row: DrawRow) -> list[int]:
    nums: list[int] = []
    for _code, _name, start_num, end_num in selected_groups():
        nums.extend(num for num in row["nums"] if start_num <= num <= end_num)
    return sorted(set(nums))


def group_normal_nums(row: DrawRow, group_id: int) -> list[int]:
    _code, _name, start_num, end_num = GROUPS[group_id]
    return sorted(num for num in row["nums"] if start_num <= num <= end_num)


def selected_special(row: DrawRow) -> Optional[int]:
    special = row["special"]
    if special is None:
        return None
    for _code, _name, start_num, end_num in selected_groups():
        if start_num <= special <= end_num:
            return special
    return None


def group_special(row: DrawRow, group_id: int) -> Optional[int]:
    special = row["special"]
    if special is None:
        return None
    _code, _name, start_num, end_num = GROUPS[group_id]
    return special if start_num <= special <= end_num else None


def display_ball_count(row: DrawRow) -> float:
    return float(selected_ball_count(row))


def selected_ball_count(row: DrawRow) -> int:
    return len(selected_normal_nums(row)) + (1 if selected_special(row) is not None else 0)


def format_ball_count(value: float) -> str:
    return str(int(value)) if value.is_integer() else f"{value:g}"


def format_prize_count(value: float) -> str:
    return str(int(value)) if value.is_integer() else f"{value:g}"


def format_nums(nums: list[int], special: Optional[int] = None) -> str:
    parts = [str(num) for num in nums]
    if special is not None:
        parts.append(f"*{special}")
    return "[" + ",".join(parts) + "]"


def all_check_nums_text(row: DrawRow) -> str:
    parts = [str(num) if 1 <= num <= 40 else "_" for num in sorted(row["nums"])]
    if row["special"] is not None:
        special_text = str(row["special"]) if 1 <= row["special"] <= 40 else "_"
        parts.append(f"*{special_text}")
    return "[" + ",".join(parts) + "]"


def is_matched(count: int) -> bool:
    if BIRTHDAY_NUM_MATCH_MODE == "==":
        return count == COMBINATION_TAKE_COUNT
    if BIRTHDAY_NUM_MATCH_MODE == "<=":
        return count <= COMBINATION_TAKE_COUNT
    return count >= COMBINATION_TAKE_COUNT


def abcd_property_row_count(row: DrawRow) -> int:
    return selected_ball_count(row)


def is_abcd_property_row_matched(row: DrawRow) -> bool:
    return is_matched(abcd_property_row_count(row))


def backtest_rows(draws: list[DrawRow]) -> list[tuple[int, DrawRow]]:
    latest_index = len(draws) - 1
    backtest_count = BACKTEST_DRAW_COUNT_LIST[0]
    start_index = max(0, latest_index - backtest_count + 1)
    return list(enumerate(draws[start_index : latest_index + 1], start=start_index))


def detail_rows(draws: list[DrawRow], period_rows: list[tuple[int, DrawRow]]) -> list[dict[str, object]]:
    latest_index = len(draws) - 1
    records: list[dict[str, object]] = []
    for row_index, row in period_rows:
        rank = latest_index - row_index + 1
        normal_nums = selected_normal_nums(row)
        matched = is_matched(selected_ball_count(row))
        record: dict[str, object] = {
            "近期": f"近{rank}期",
            "日期": row["date"],
            "查詢開獎號": "",
            "總球數": "",
        }
        if PRIZE_PRINT_SHOW:
            record[f"{PRIZE_OPTION}獎注數"] = ""
        if matched:
            record["查詢開獎號"] = format_nums(normal_nums, selected_special(row))
            record["總球數"] = format_ball_count(display_ball_count(row))
            if PRIZE_PRINT_SHOW:
                record[f"{PRIZE_OPTION}獎注數"] = format_prize_count(row["prize_count"])
        records.append(record)
    return records


def render_compact_table(rows: list[dict[str, object]], table_class: str = "prr-v3-table") -> None:
    if not rows:
        st.info("沒有資料。")
        return

    def cell_html(value: object) -> str:
        return html.escape(str(value)).replace(",", ",<wbr>")

    headers = list(rows[0].keys())
    header_html = "".join(f"<th>{html.escape(str(header))}</th>" for header in headers)
    body_html = []
    for row in rows:
        cells = "".join(
            f"<td>{cell_html(row.get(header, ''))}</td>"
            for header in headers
        )
        body_html.append(f"<tr>{cells}</tr>")

    st.markdown(
        f"""
        <div class="prr-v3-table-wrap">
            <table class="{table_class}">
                <thead><tr>{header_html}</tr></thead>
                <tbody>{''.join(body_html)}</tbody>
            </table>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_summary(period_rows: list[tuple[int, DrawRow]]) -> None:
    matched_count = sum(1 for _row_index, row in period_rows if is_matched(selected_ball_count(row)))
    total_count = len(period_rows)
    matched_percent = (matched_count / total_count * 100) if total_count else 0

    st.markdown(
        f"結果合條件 {BIRTHDAY_NUM_MATCH_MODE} {COMBINATION_TAKE_COUNT} 球，"
        f"查詢 {matched_count} / {total_count} 期統計 = {matched_count}期 "
        f"({matched_percent:.0f} %)"
    )


def group_window_num_counts(
    period_rows: list[tuple[int, DrawRow]],
    matched_only: bool = False,
) -> dict[int, Counter[int]]:
    counters: dict[int, Counter[int]] = {group_id: Counter() for group_id in GROUPS}
    for _row_index, row in period_rows:
        if matched_only and not is_abcd_property_row_matched(row):
            continue
        for group_id in GROUPS:
            counters[group_id].update(group_normal_nums(row, group_id))
            special = group_special(row, group_id)
            if special is not None:
                counters[group_id][special] += 1
    return counters


def property_source_rows(
    period_rows: list[tuple[int, DrawRow]],
    target_index: int,
) -> list[tuple[int, DrawRow]]:
    return [
        (row_index, row)
        for row_index, row in period_rows
        if target_index - row_index + 1 >= 2
    ]


def missing_nums_text(period_rows: list[tuple[int, DrawRow]]) -> str:
    group_counts = group_window_num_counts(period_rows, matched_only=False)
    parts: list[str] = []
    for group_id in selected_group_ids():
        code, _name, start_num, end_num = GROUPS[group_id]
        missing_nums = [
            num
            for num in range(start_num, end_num + 1)
            if group_counts[group_id][num] == 0
        ]
        parts.append(f"{code}{format_nums(missing_nums)}")
    return "ANB 缺席球 = " + "，".join(parts)


def missing_nums_by_group(period_rows: list[tuple[int, DrawRow]]) -> dict[int, list[int]]:
    group_counts = group_window_num_counts(period_rows, matched_only=False)
    result: dict[int, list[int]] = {}
    for group_id in selected_group_ids():
        _code, _name, start_num, end_num = GROUPS[group_id]
        result[group_id] = [
            num
            for num in range(start_num, end_num + 1)
            if group_counts[group_id][num] == 0
        ]
    return result


def high_freq_pair_data(period_rows: list[tuple[int, DrawRow]]) -> dict[int, tuple[list[int], list[int]]]:
    result: dict[int, tuple[list[int], list[int]]] = {}

    for group_id in selected_group_ids():
        multi_open_counter: Counter[int] = Counter()
        for _row_index, row in period_rows:
            nums = group_normal_nums(row, group_id)
            special = group_special(row, group_id)
            open_nums = sorted(set(nums + ([special] if special is not None else [])))
            if len(open_nums) >= 2:
                multi_open_counter.update(open_nums)

        dan_nums = [
            num
            for num, count in sorted(multi_open_counter.items(), key=lambda item: (-item[1], item[0]))
            if count >= HIGH_FREQ_MIN_PAIR_COUNT
        ]
        partner_nums = sorted(
            [
                num
                for num, count in sorted(multi_open_counter.items(), key=lambda item: (-item[1], item[0]))
                if count == 1 and num not in dan_nums
            ]
        )
        result[group_id] = (dan_nums, partner_nums)

    return result


def high_freq_pair_text(pair_data: dict[int, tuple[list[int], list[int]]]) -> list[str]:
    if not PRINT_HIGH_FREQ_PAIR_ANALYSIS:
        return []

    dan_parts: list[str] = []
    partner_parts: list[str] = []
    for group_id in selected_group_ids():
        code = GROUPS[group_id][0]
        dan_nums, partner_nums = pair_data.get(group_id, ([], []))
        dan_parts.append(f"{code}{format_nums(dan_nums)}")
        partner_parts.append(f"{code}{format_nums(partner_nums)}")
    return [
        "HFB 高頻膽號 = " + "，".join(dan_parts),
        "HFL 高頻腳號 = " + "，".join(partner_parts),
    ]


def weak_nums_text(
    period_rows: list[tuple[int, DrawRow]],
    pair_data: dict[int, tuple[list[int], list[int]]],
) -> list[str]:
    if not PRINT_WEAK_NUM_ANALYSIS:
        return []

    group_counts = group_window_num_counts(period_rows, matched_only=False)
    single_open_nums: dict[int, set[int]] = {group_id: set() for group_id in GROUPS}
    for _row_index, row in period_rows:
        for group_id in selected_group_ids():
            nums = group_nums_with_special(row, group_id)
            if len(nums) == 1:
                single_open_nums[group_id].add(nums[0])

    parts: list[str] = []
    for group_id in selected_group_ids():
        code, _name, start_num, end_num = GROUPS[group_id]
        dan_nums, partner_nums = pair_data.get(group_id, ([], []))
        missing_nums = {
            num
            for num in range(start_num, end_num + 1)
            if group_counts[group_id][num] == 0
        }
        assigned_nums = missing_nums | set(dan_nums) | set(partner_nums)
        otn_nums = [
            num
            for num in sorted(single_open_nums[group_id])
            if num not in assigned_nums
        ]
        parts.append(f"{code}{format_nums(otn_nums)}")
    return ["OTN 單次球 = " + "，".join(parts)]


def weak_nums_by_group(
    period_rows: list[tuple[int, DrawRow]],
    pair_data: dict[int, tuple[list[int], list[int]]],
) -> dict[int, list[int]]:
    group_counts = group_window_num_counts(period_rows, matched_only=False)
    single_open_nums: dict[int, set[int]] = {group_id: set() for group_id in GROUPS}
    for _row_index, row in period_rows:
        for group_id in selected_group_ids():
            nums = group_nums_with_special(row, group_id)
            if len(nums) == 1:
                single_open_nums[group_id].add(nums[0])

    result: dict[int, list[int]] = {}
    for group_id in selected_group_ids():
        _code, _name, start_num, end_num = GROUPS[group_id]
        dan_nums, partner_nums = pair_data.get(group_id, ([], []))
        missing_nums = {
            num
            for num in range(start_num, end_num + 1)
            if group_counts[group_id][num] == 0
        }
        assigned_nums = missing_nums | set(dan_nums) | set(partner_nums)
        result[group_id] = [
            num
            for num in sorted(single_open_nums[group_id])
            if num not in assigned_nums
        ]
    return result


def group_nums_with_special(row: DrawRow, group_id: int) -> list[int]:
    nums = group_normal_nums(row, group_id)
    special = group_special(row, group_id)
    if special is not None:
        nums.append(special)
    return sorted(set(nums))


def dimension_rows(
    period_rows: list[tuple[int, DrawRow]],
    target_index: int,
    dimension_no: int,
) -> list[tuple[int, DrawRow]]:
    rank_start = 2 + (dimension_no - 1) * DIMENSION_DRAW_COUNT
    rank_end = rank_start + DIMENSION_DRAW_COUNT - 1
    return [
        (row_index, row)
        for row_index, row in period_rows
        if rank_start <= target_index - row_index + 1 <= rank_end
    ]


def dimension_hot_nums(
    period_rows: list[tuple[int, DrawRow]],
    target_index: int,
) -> dict[int, dict[int, list[int]]]:
    dimension_count = max(0, (len(period_rows) - 1) // DIMENSION_DRAW_COUNT)
    result: dict[int, dict[int, list[int]]] = {}

    for dimension_no in range(1, dimension_count + 1):
        counters: dict[int, Counter[int]] = {group_id: Counter() for group_id in GROUPS}
        for _row_index, row in dimension_rows(period_rows, target_index, dimension_no):
            for group_id in selected_group_ids():
                nums = group_nums_with_special(row, group_id)
                if len(nums) == 1:
                    counters[group_id][nums[0]] += 1

        result[dimension_no] = {}
        for group_id in selected_group_ids():
            hot_nums = [
                num
                for num, count in sorted(counters[group_id].items(), key=lambda item: (-item[1], item[0]))
                if count >= DIMENSION_HOT_MIN_COUNT
            ]
            result[dimension_no][group_id] = sorted(hot_nums)

    return result


def near_one_dimension_hits(
    near_one_row: DrawRow,
    hot_by_dimension: dict[int, dict[int, list[int]]],
) -> list[str]:
    near_one_nums = {num for num in near_one_row["nums"] if 1 <= num <= 40}
    if near_one_row["special"] is not None and 1 <= near_one_row["special"] <= 40:
        near_one_nums.add(near_one_row["special"])

    hit_parts: list[str] = []
    for dimension_no in sorted(hot_by_dimension):
        dimension_hot_nums_set = {
            num
            for group_hot_nums in hot_by_dimension[dimension_no].values()
            for num in group_hot_nums
        }
        hits = sorted(near_one_nums & dimension_hot_nums_set)
        if hits:
            hit_parts.append(f"#{dimension_no}{format_nums(hits)}")
    return hit_parts


def near_one_high_freq_dan_hits(
    near_one_row: DrawRow,
    pair_data: dict[int, tuple[list[int], list[int]]],
) -> list[int]:
    near_one_nums = {num for num in near_one_row["nums"] if 1 <= num <= 40}
    if near_one_row["special"] is not None and 1 <= near_one_row["special"] <= 40:
        near_one_nums.add(near_one_row["special"])

    dan_nums = {
        num
        for group_id in selected_group_ids()
        for num in pair_data.get(group_id, ([], []))[0]
    }
    return sorted(near_one_nums & dan_nums)


def property_analysis_rows(
    period_rows: list[tuple[int, DrawRow]],
    pair_data: dict[int, tuple[list[int], list[int]]],
) -> list[dict[str, object]]:
    missing_by_group = missing_nums_by_group(period_rows)
    weak_by_group = weak_nums_by_group(period_rows, pair_data)
    row_sources: list[tuple[str, dict[int, list[int]]]] = [
        ("缺席球", missing_by_group),
        ("高頻膽號", {group_id: pair_data.get(group_id, ([], []))[0] for group_id in selected_group_ids()}),
        ("高頻腳號", {group_id: pair_data.get(group_id, ([], []))[1] for group_id in selected_group_ids()}),
        ("單次球", weak_by_group),
    ]

    rows: list[dict[str, object]] = []
    for label, values_by_group in row_sources:
        row: dict[str, object] = {"類別": label}
        for group_id in selected_group_ids():
            code = GROUPS[group_id][0]
            row[code] = format_nums(values_by_group.get(group_id, []))
        rows.append(row)
    return rows


def dimension_hot_rows(
    hot_by_dimension: dict[int, dict[int, list[int]]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for dimension_no in sorted(hot_by_dimension, reverse=True):
        row: dict[str, object] = {"維度": f"#{dimension_no}"}
        for group_id in selected_group_ids():
            code = GROUPS[group_id][0]
            row[code] = format_nums(hot_by_dimension[dimension_no].get(group_id, []))
        rows.append(row)
    return rows


def render_abcd_property_analysis(
    period_rows: list[tuple[int, DrawRow]],
    target_index: int,
) -> dict[int, tuple[list[int], list[int]]]:
    if not PRINT_ABCD_PROPERTY_ANALYSIS:
        return {}

    analysis_rows = property_source_rows(period_rows, target_index)
    pair_data = high_freq_pair_data(analysis_rows)
    section_title("A/B/C/D 選組分析屬性")
    st.markdown(
        f"**{selected_group_ids_text()} A/B/C/D 選組分析屬性**  \n"
        f"ABCD 屬性條件：各組獨立，每期合併分組總球數 "
        f"{BIRTHDAY_NUM_MATCH_MODE} {COMBINATION_TAKE_COUNT} 球 (包括特號)"
    )
    st.markdown("/> -------------")
    render_compact_table(
        property_analysis_rows(analysis_rows, pair_data),
        table_class="prr-v3-table prr-v3-property-table",
    )
    return pair_data


def render_dimension_hot_num_analysis(
    period_rows: list[tuple[int, DrawRow]],
    target_index: int,
    pair_data: Optional[dict[int, tuple[list[int], list[int]]]] = None,
) -> None:
    if not PRINT_DIMENSION_HOT_NUM_ANALYSIS:
        return
    if len(period_rows) < DIMENSION_DRAW_COUNT + 1:
        return

    hot_by_dimension = dimension_hot_nums(period_rows, target_index)
    if not hot_by_dimension:
        return

    section_title("維度熱門號分析 #1/#2/#3")
    st.markdown(
        f"維度規則：近 1 期只作比對；由近 2 期起每 {DIMENSION_DRAW_COUNT} 期一維，"
        f"同組單獨 1 球重開 >= {DIMENSION_HOT_MIN_COUNT} 次"
    )
    render_compact_table(
        dimension_hot_rows(hot_by_dimension),
        table_class="prr-v3-table prr-v3-property-table",
    )

    near_one_row = max(period_rows, key=lambda item: item[0])[1]
    hit_parts = near_one_dimension_hits(near_one_row, hot_by_dimension)
    hit_text = "，".join(hit_parts) if hit_parts else "[]"
    dan_hits = near_one_high_freq_dan_hits(near_one_row, pair_data or {})
    st.markdown(
        f'<div class="prr-v3-property-line">近 1 期比對：{html.escape(near_one_row["date"])}，'
        f'開獎號 {html.escape(all_check_nums_text(near_one_row))}，'
        f'重開提示：維度 {html.escape(hit_text)}，HFB {html.escape(format_nums(dan_hits))}</div>',
        unsafe_allow_html=True,
    )


def reset_param_state() -> None:
    for key, value in PARAM_STATE_KEYS.items():
        st.session_state[key] = value


def init_param_state() -> None:
    for key, value in PARAM_STATE_KEYS.items():
        st.session_state.setdefault(key, value)


def main() -> None:
    global BACKTEST_DRAW_COUNT_LIST
    global BIRTHDAY_NUM_MATCH_MODE
    global COMBINATION_TAKE_COUNT
    global PRIZE_OPTION
    global PRIZE_PRINT_SHOW
    global SELECT_GROUPS

    BACKTEST_DRAW_COUNT_LIST = [DEFAULT_BACKTEST_DRAW_COUNT]
    SELECT_GROUPS = tuple(parse_int_list(DEFAULT_SELECT_GROUPS))
    COMBINATION_TAKE_COUNT = DEFAULT_COMBINATION_TAKE_COUNT
    BIRTHDAY_NUM_MATCH_MODE = DEFAULT_MATCH_MODE
    PRIZE_OPTION = DEFAULT_PRIZE_OPTION
    PRIZE_PRINT_SHOW = DEFAULT_PRIZE_PRINT_SHOW

    init_param_state()
    apply_new_page_style()
    st.markdown(
        """
        <style>
        .prr-v3-table-wrap {
            width: 100%;
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
            border: 1px solid #b8b8b8;
            border-radius: 6px;
            background: #ffffff !important;
            margin: 0.45rem 0 0.85rem;
        }
        .prr-v3-table {
            width: 100%;
            min-width: 100%;
            table-layout: fixed;
            border-collapse: collapse;
            background: #ffffff !important;
            color: #000000 !important;
            font-size: 0.78rem;
        }
        .prr-v3-table th,
        .prr-v3-table td {
            background: #ffffff !important;
            color: #000000 !important;
            border-bottom: 1px solid #dddddd;
            padding: 3px 4px;
            text-align: left;
            white-space: nowrap;
        }
        .prr-v3-table th {
            font-weight: 900;
            background: #f3f5f7 !important;
        }
        .prr-v3-result-table th:nth-child(1),
        .prr-v3-result-table td:nth-child(1) {
            width: 2.9rem;
        }
        .prr-v3-result-table th:nth-child(2),
        .prr-v3-result-table td:nth-child(2) {
            width: 5.4rem;
        }
        .prr-v3-result-table th:nth-child(3),
        .prr-v3-result-table td:nth-child(3) {
            width: 7.2rem;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .prr-v3-result-table th:nth-child(4),
        .prr-v3-result-table td:nth-child(4) {
            width: 2.9rem;
            text-align: center;
        }
        .prr-v3-result-table th:nth-child(5),
        .prr-v3-result-table td:nth-child(5) {
            width: 3.5rem;
            text-align: center;
        }
        .prr-v3-property-table {
            table-layout: fixed;
            font-size: 0.78rem;
        }
        .prr-v3-property-table th,
        .prr-v3-property-table td {
            white-space: normal;
            overflow-wrap: normal;
            word-break: normal;
            overflow: hidden;
            line-height: 1.28;
            padding: 4px 3px;
            vertical-align: top;
        }
        .prr-v3-property-table th:nth-child(1),
        .prr-v3-property-table td:nth-child(1) {
            width: 4.8rem;
            text-align: left;
            font-weight: 900;
        }
        .prr-v3-property-table th:nth-child(2),
        .prr-v3-property-table td:nth-child(2),
        .prr-v3-property-table th:nth-child(5),
        .prr-v3-property-table td:nth-child(5) {
            width: 17%;
        }
        .prr-v3-property-line {
            margin: 0.34rem 0;
            font-size: 1rem;
            line-height: 1.55;
            font-weight: 700;
            color: #111111;
            overflow-wrap: anywhere;
        }
        @media (max-width: 430px) {
            .prr-v3-table {
                font-size: 0.68rem;
            }
            .prr-v3-table th,
            .prr-v3-table td {
                padding: 2px 3px;
            }
            .prr-v3-result-table th:nth-child(3),
            .prr-v3-result-table td:nth-child(3) {
                width: 6.2rem;
            }
            .prr-v3-property-table {
                font-size: 0.66rem;
            }
            .prr-v3-property-table th,
            .prr-v3-property-table td {
                padding: 2px 2px;
            }
            .prr-v3-property-table th:nth-child(1),
            .prr-v3-property-table td:nth-child(1) {
                width: 4.1rem;
            }
            .prr-v3-property-table th:nth-child(2),
            .prr-v3-property-table td:nth-child(2),
            .prr-v3-property-table th:nth-child(5),
            .prr-v3-property-table td:nth-child(5) {
                width: 15%;
            }
            .prr-v3-property-line {
                font-size: 0.94rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    page_header(
        "ABCD 分組 ，開獎紀錄查詢",
        "A(1-9), B(10-20), C(21-31), D(32-40)",
    )

    section_title("參數設定")
    st.session_state["prr_v3_take_count"] = to_int(
        st.session_state.get("prr_v3_take_count"),
        default=DEFAULT_COMBINATION_TAKE_COUNT,
    )
    st.session_state["prr_v3_prize_option"] = to_int(
        st.session_state.get("prr_v3_prize_option"),
        default=DEFAULT_PRIZE_OPTION,
    )
    backtest_text = st.text_input(
        "回測期 (13-30，預設=13期)",
        key="prr_v3_backtest_text",
    )
    groups_text = st.text_input(
        "選擇 ABCD 組 (預設=1,2,3,4)",
        key="prr_v3_groups_text",
    )
    st.number_input(
        "開獎期球數查詢 (預設=4球)",
        min_value=0,
        max_value=7,
        step=1,
        key="prr_v3_take_count",
    )
    match_mode = st.selectbox(
        "合球數條件 (預設=>=)",
        [">=", "=="],
        key="prr_v3_match_mode",
    )
    prize_option = st.number_input(
        "中獎注數 (預設=3獎)",
        min_value=1,
        max_value=10,
        step=1,
        key="prr_v3_prize_option",
    )
    prize_print_show = st.checkbox(
        "顯示中獎注數欄位",
        key="prr_v3_prize_print_show",
    )
    submitted = st.button("執行查詢", key="prr_v3_submit", type="primary")
    st.button("Reset", key="prr_v3_reset", on_click=reset_param_state)

    if not submitted:
        st.info("輸入參數後按「執行查詢」。")
        return

    try:
        parsed_backtest = parse_int_list(backtest_text)
        parsed_groups = parse_int_list(groups_text)
        parsed_take_count = to_int(st.session_state.get("prr_v3_take_count"), default=-1)
        parsed_prize_option = to_int(prize_option, default=-1)
        parsed_match_mode = match_mode.strip()
        if not parsed_backtest or parsed_backtest[0] <= 0:
            raise ValueError("回測期最少需要一個正整數，例如 13。")
        if not 13 <= parsed_backtest[0] <= 30:
            raise ValueError("回測期只可輸入 13 至 30。")
        if not parsed_groups or any(group_id not in GROUPS for group_id in parsed_groups):
            raise ValueError("選擇 ABCD 組只可輸入 1,2,3,4，例如 1,2,3,4。")
        if parsed_take_count < 0:
            raise ValueError("開獎期球數查詢需要整數。")
        if parsed_match_mode not in (">=", "=="):
            raise ValueError('合球數條件只可輸入 ">=" 或 "=="。')
        if parsed_prize_option <= 0:
            raise ValueError("中獎注數需要正整數。")

        BACKTEST_DRAW_COUNT_LIST = [parsed_backtest[0]]
        SELECT_GROUPS = tuple(parsed_groups)
        COMBINATION_TAKE_COUNT = parsed_take_count
        BIRTHDAY_NUM_MATCH_MODE = parsed_match_mode
        PRIZE_OPTION = parsed_prize_option
        PRIZE_PRINT_SHOW = prize_print_show
        draws = read_draws(PRIZE_OPTION)
    except (FileNotFoundError, ValueError) as exc:
        st.error(f"參數或資料錯誤：{exc}")
        return

    if not draws:
        st.warning("沒有可讀取的開獎紀錄。")
        return

    period_rows = backtest_rows(draws)

    st.table(
        {
            "查詢模式": f"全組別 {selected_group_codes_text()}",
            "回測期列表": str(BACKTEST_DRAW_COUNT_LIST),
            "符合條件": f"範圍內號碼數量 {BIRTHDAY_NUM_MATCH_MODE}{COMBINATION_TAKE_COUNT} 球",
            "查詢號碼": "N1..N7，N7 特號以 * 顯示",
            "顯示欄位": (
                f"開獎日期，合併號碼，N球，Pz{PRIZE_OPTION} = {PRIZE_OPTION} 獎"
                if PRIZE_PRINT_SHOW
                else "開獎日期，合併號碼，N球"
            ),
        }
    )

    render_summary(period_rows)

    section_title(f"近 {BACKTEST_DRAW_COUNT_LIST[0]} 期開獎紀錄")
    rows = detail_rows(draws, period_rows)
    render_compact_table(rows, table_class="prr-v3-table prr-v3-result-table")
    latest_index = len(draws) - 1
    pair_data = render_abcd_property_analysis(period_rows, latest_index)
    render_dimension_hot_num_analysis(period_rows, latest_index, pair_data)
