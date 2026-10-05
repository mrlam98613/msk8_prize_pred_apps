from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
from typing import Any, TypedDict

import streamlit as st

from new_app_pages.shared_style import apply_new_page_style, page_header, section_title


PROJECT_ROOT = Path(__file__).resolve().parents[1]
M6_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"

BACKTEST_DRAW_COUNT_LIST = [30]
SELECT_GROUPS = (1, 2, 3, 4)
COMBINATION_TAKE_COUNT = 5
BIRTHDAY_NUM_MATCH_MODE = ">="
PRIZE_OPTION = 3
PRIZE_PRINT_SHOW = False

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
            "近 N期": rank,
            "日期": row["date"],
            "號碼": "",
            "N球": "",
        }
        if PRIZE_PRINT_SHOW:
            record[f"Pz{PRIZE_OPTION}"] = ""
        if matched:
            record["號碼"] = format_nums(normal_nums, selected_special(row))
            record["N球"] = format_ball_count(display_ball_count(row))
            if PRIZE_PRINT_SHOW:
                record[f"Pz{PRIZE_OPTION}"] = format_prize_count(row["prize_count"])
        records.append(record)
    return records


def hot_cold_pairs(counter: Counter[int], nums: list[int]) -> str:
    pairs = sorted(((num, counter.get(num, 0)) for num in nums), key=lambda item: (-item[1], item[0]))
    return "[" + ",".join(f"{num}({count})" for num, count in pairs) + "]"


def group_hot_cold_rows(period_rows: list[tuple[int, DrawRow]]) -> list[dict[str, str]]:
    counter: Counter[int] = Counter()
    for _row_index, row in period_rows:
        counter.update(num for num in row["nums"] if 1 <= num <= 40)

    records: list[dict[str, str]] = []
    for group_id in SELECT_GROUPS:
        code, name, start_num, end_num = GROUPS[group_id]
        odd_nums = [num for num in range(start_num, end_num + 1) if num % 2 == 1]
        even_nums = [num for num in range(start_num, end_num + 1) if num % 2 == 0]
        records.append(
            {
                "組別": f"{code}組 {name}",
                "單數": hot_cold_pairs(counter, odd_nums),
                "雙數": hot_cold_pairs(counter, even_nums),
            }
        )
    return records


def render_summary(period_rows: list[tuple[int, DrawRow]]) -> None:
    matched_count = sum(1 for _row_index, row in period_rows if is_matched(len(selected_normal_nums(row))))
    total_count = len(period_rows)
    matched_percent = (matched_count / total_count * 100) if total_count else 0

    st.markdown(
        f"結果合條件 {BIRTHDAY_NUM_MATCH_MODE} {COMBINATION_TAKE_COUNT} 球，"
        f"查詢 {matched_count} / {total_count} 期統計 = {matched_count}期 "
        f"({matched_percent:.0f} %)"
    )


def main() -> None:
    global BACKTEST_DRAW_COUNT_LIST
    global BIRTHDAY_NUM_MATCH_MODE
    global COMBINATION_TAKE_COUNT
    global PRIZE_OPTION
    global PRIZE_PRINT_SHOW
    global SELECT_GROUPS

    apply_new_page_style()
    page_header(
        "prr_v3 , 1-40 ABCD 分組，開獎紀錄查詢",
        "A(1-9), B(10-20), C(21-31), D(32-40)",
    )

    section_title("參數設定")
    with st.form("prr_v3_multi_group_params"):
        backtest_text = st.text_input("回測期", value=format_input_numbers(BACKTEST_DRAW_COUNT_LIST))
        groups_text = st.text_input(
            "SELECT_GROUPS",
            value=format_input_numbers(SELECT_GROUPS),
            help="輸入組別數字：1=A(1-9)，2=B(10-20)，3=C(21-31)，4=D(32-40)。例如：1,2,3,4 或 2，3，4。",
        )
        take_count = st.text_input("COMBINATION_TAKE_COUNT", value=str(COMBINATION_TAKE_COUNT))
        match_mode = st.text_input("BIRTHDAY_NUM_MATCH_MODE", value=BIRTHDAY_NUM_MATCH_MODE)
        prize_option = st.text_input("PRIZE_OPTION", value=str(PRIZE_OPTION))
        prize_print_show = st.checkbox("PRIZE_PRINT_SHOW", value=PRIZE_PRINT_SHOW)
        st.caption("SELECT_GROUPS 數字提示：1=A(1-9)，2=B(10-20)，3=C(21-31)，4=D(32-40)")
        submitted = st.form_submit_button("執行查詢")

    if not submitted:
        st.info("輸入參數後按「執行查詢」。")
        return

    try:
        parsed_backtest = parse_int_list(backtest_text)
        parsed_groups = parse_int_list(groups_text)
        parsed_take_count = to_int(take_count, default=-1)
        parsed_prize_option = to_int(prize_option, default=-1)
        parsed_match_mode = match_mode.strip()
        if not parsed_backtest or parsed_backtest[0] <= 0:
            raise ValueError("BACKTEST_DRAW_COUNT_LIST 最少需要一個正整數，例如 [30]。")
        if not parsed_groups or any(group_id not in GROUPS for group_id in parsed_groups):
            raise ValueError("SELECT_GROUPS 只可輸入 1,2,3,4，例如 (1,2,3,4)。")
        if parsed_take_count < 0:
            raise ValueError("COMBINATION_TAKE_COUNT 需要整數。")
        if parsed_match_mode not in (">=", "==", "<="):
            raise ValueError('BIRTHDAY_NUM_MATCH_MODE 只可輸入 ">="、"==" 或 "<="。')
        if parsed_prize_option <= 0:
            raise ValueError("PRIZE_OPTION 需要正整數。")

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
        },
        border="horizontal",
        width="content",
    )

    render_summary(period_rows)

    section_title("近 30 期開獎紀錄")
    rows = detail_rows(draws, period_rows)
    column_config: Any = {
        "近 N期": st.column_config.NumberColumn("近 N期", width="small", format="%d"),
        "日期": st.column_config.TextColumn("日期", width="medium"),
        "號碼": st.column_config.TextColumn("號碼", width="large"),
        "N球": st.column_config.TextColumn("N球", width="small"),
    }
    if PRIZE_PRINT_SHOW:
        column_config[f"Pz{PRIZE_OPTION}"] = st.column_config.TextColumn(f"Pz{PRIZE_OPTION}", width="small")

    st.dataframe(
        rows,
        hide_index=True,
        width="stretch",
        column_config=column_config,
    )

    section_title("A-D 分組單雙冷熱門累計")
    st.dataframe(
        group_hot_cold_rows(period_rows),
        hide_index=True,
        width="stretch",
        column_config={
            "組別": st.column_config.TextColumn("組別", width="small"),
            "單數": st.column_config.TextColumn("單數", width="large"),
            "雙數": st.column_config.TextColumn("雙數", width="large"),
        },
    )
