from __future__ import annotations

import csv
import html
from pathlib import Path
from typing import TypedDict

import streamlit as st

from app_pages.shared_style import apply_new_page_style, page_header, section_title


PROJECT_ROOT = Path(__file__).resolve().parents[1]
M6_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"

BACKTEST_DRAW_COUNT_LIST = [13]
SELECT_GROUPS = (1, 2, 3, 4)
COMBINATION_TAKE_COUNT = 4
BIRTHDAY_NUM_MATCH_MODE = ">="
PRIZE_OPTION = 3
PRIZE_PRINT_SHOW = True
DEFAULT_BACKTEST_DRAW_COUNT = 13
DEFAULT_SELECT_GROUPS = "1,2,3,4"
DEFAULT_COMBINATION_TAKE_COUNT = 4
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
    special: int | None
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


def format_input_numbers(values: list[int] | tuple[int, ...]) -> str:
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


def selected_normal_nums(row: DrawRow) -> list[int]:
    nums: list[int] = []
    for _code, _name, start_num, end_num in selected_groups():
        nums.extend(num for num in row["nums"] if start_num <= num <= end_num)
    return sorted(set(nums))


def selected_special(row: DrawRow) -> int | None:
    special = row["special"]
    if special is None:
        return None
    for _code, _name, start_num, end_num in selected_groups():
        if start_num <= special <= end_num:
            return special
    return None


def display_ball_count(row: DrawRow) -> float:
    normal_count = len(selected_normal_nums(row))
    special = selected_special(row)
    if special is not None and normal_count >= 3:
        return normal_count + 0.5
    return float(normal_count)


def format_ball_count(value: float) -> str:
    return str(int(value)) if value.is_integer() else f"{value:g}"


def format_prize_count(value: float) -> str:
    return str(int(value)) if value.is_integer() else f"{value:g}"


def format_nums(nums: list[int], special: int | None = None) -> str:
    parts = [str(num) for num in nums]
    if special is not None:
        parts.append(f"*{special}")
    return "[" + ",".join(parts) + "]"


def is_matched(count: int) -> bool:
    if BIRTHDAY_NUM_MATCH_MODE == "==":
        return count == COMBINATION_TAKE_COUNT
    if BIRTHDAY_NUM_MATCH_MODE == "<=":
        return count <= COMBINATION_TAKE_COUNT
    return count >= COMBINATION_TAKE_COUNT


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
        matched = is_matched(len(normal_nums))
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

    headers = list(rows[0].keys())
    header_html = "".join(f"<th>{html.escape(str(header))}</th>" for header in headers)
    body_html = []
    for row in rows:
        cells = "".join(
            f"<td>{html.escape(str(row.get(header, '')))}</td>"
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
    matched_count = sum(1 for _row_index, row in period_rows if is_matched(len(selected_normal_nums(row))))
    total_count = len(period_rows)
    matched_percent = (matched_count / total_count * 100) if total_count else 0

    st.markdown(
        f"結果合條件 {BIRTHDAY_NUM_MATCH_MODE} {COMBINATION_TAKE_COUNT} 球，"
        f"查詢 {matched_count} / {total_count} 期統計 = {matched_count}期 "
        f"({matched_percent:.0f} %)"
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
            width: max-content;
            min-width: 100%;
            border-collapse: collapse;
            background: #ffffff !important;
            color: #000000 !important;
            font-size: 0.84rem;
        }
        .prr-v3-table th,
        .prr-v3-table td {
            background: #ffffff !important;
            color: #000000 !important;
            border-bottom: 1px solid #dddddd;
            padding: 4px 5px;
            text-align: left;
            white-space: nowrap;
        }
        .prr-v3-table th {
            font-weight: 900;
            background: #f3f5f7 !important;
        }
        .prr-v3-result-table th:nth-child(1),
        .prr-v3-result-table td:nth-child(1) {
            width: 3.1rem;
        }
        .prr-v3-result-table th:nth-child(2),
        .prr-v3-result-table td:nth-child(2) {
            width: 5.8rem;
        }
        .prr-v3-result-table th:nth-child(3),
        .prr-v3-result-table td:nth-child(3) {
            max-width: 8.8rem;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .prr-v3-result-table th:nth-child(4),
        .prr-v3-result-table td:nth-child(4) {
            width: 3.4rem;
            text-align: center;
        }
        .prr-v3-result-table th:nth-child(5),
        .prr-v3-result-table td:nth-child(5) {
            width: 4.2rem;
            text-align: center;
        }
        @media (max-width: 430px) {
            .prr-v3-table {
                font-size: 0.74rem;
            }
            .prr-v3-table th,
            .prr-v3-table td {
                padding: 3px 4px;
            }
            .prr-v3-result-table th:nth-child(3),
            .prr-v3-result-table td:nth-child(3) {
                max-width: 7.5rem;
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
    submitted = st.button("執行查詢", key="prr_v3_submit", type="primary", use_container_width=True)
    st.button("Reset", key="prr_v3_reset", use_container_width=True, on_click=reset_param_state)

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
