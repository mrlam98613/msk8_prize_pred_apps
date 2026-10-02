from __future__ import annotations

import csv
import re
from collections import Counter
from pathlib import Path
from typing import TypedDict

import pandas as pd
import streamlit as st

from new_app_pages.shared_style import apply_new_page_style, page_header, section_title


PROJECT_ROOT = Path(__file__).resolve().parents[1]
M6_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"

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


def parse_int_list(raw_text: str) -> list[int]:
    """Parse all integer values from text like [1,2], (1,2), or 1，2."""
    return [int(value) for value in re.findall(r"\d+", raw_text)]


def to_int(value: object, default: int = 0) -> int:
    """Safely convert a value to int."""
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


@st.cache_data(show_spinner=False)
def read_draws() -> list[DrawRow]:
    """Read M6 historical draw rows."""
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
                }
            )
    return rows


def selected_groups(group_ids: list[int]) -> list[tuple[str, str, int, int]]:
    """Return selected A-D group definitions."""
    return [GROUPS[group_id] for group_id in group_ids if group_id in GROUPS]


def selected_normal_nums(row: DrawRow, group_ids: list[int]) -> list[int]:
    """Get N1..N6 nums within selected groups."""
    nums: list[int] = []
    for _code, _name, start_num, end_num in selected_groups(group_ids):
        nums.extend(num for num in row["nums"] if start_num <= num <= end_num)
    return sorted(set(nums))


def selected_special(row: DrawRow, group_ids: list[int]) -> int | None:
    """Return special number if it is within selected groups."""
    special = row["special"]
    if special is None:
        return None
    for _code, _name, start_num, end_num in selected_groups(group_ids):
        if start_num <= special <= end_num:
            return special
    return None


def ball_count(row: DrawRow, group_ids: list[int]) -> float:
    """Count selected normal nums, special counts as 0.5 when normal >= 3."""
    normal_count = len(selected_normal_nums(row, group_ids))
    special = selected_special(row, group_ids)
    if special is not None and normal_count >= 3:
        return normal_count + 0.5
    return float(normal_count)


def format_ball_count(value: float) -> str:
    """Format ball count."""
    return str(int(value)) if value.is_integer() else f"{value:g}"


def format_nums(nums: list[int], special: int | None = None) -> str:
    """Format selected nums and optional special."""
    parts = [str(num) for num in nums]
    if special is not None:
        parts.append(f"*{special}")
    return "[" + ",".join(parts) + "]"


def is_matched(count: int, take_count: int, match_mode: str) -> bool:
    """Check match condition."""
    if match_mode == "==":
        return count == take_count
    if match_mode == "<=":
        return count <= take_count
    return count >= take_count


def rbg_color_id(num: int) -> int:
    """Return 1=R, 2=B, 3=G."""
    adjusted_num = num - 1
    return (((adjusted_num // 10) + adjusted_num) % 6 // 2) + 1


def hot_cold_pairs(counter: Counter[int], nums: list[int]) -> str:
    """Format nums sorted by frequency hot to cold."""
    pairs = sorted(((num, counter.get(num, 0)) for num in nums), key=lambda item: (-item[1], item[0]))
    return "[" + ",".join(f"{num}({count})" for num, count in pairs) + "]"


def build_window_rows(
    draws: list[DrawRow],
    mode: str,
    backtest_count: int,
    window_count: int,
) -> tuple[list[tuple[int, DrawRow]], int | None]:
    """Build the first trial window for backtest or predict."""
    latest_index = len(draws) - 1
    if mode == "predict":
        window_start = max(0, latest_index - window_count + 1)
        return list(enumerate(draws[window_start : latest_index + 1], start=window_start)), None

    check_index = max(0, latest_index - backtest_count + 1)
    window_start = max(0, check_index - window_count)
    return list(enumerate(draws[window_start:check_index], start=window_start)), check_index


def window_detail_df(
    draws: list[DrawRow],
    window_rows: list[tuple[int, DrawRow]],
    target_index: int,
    group_ids: list[int],
    take_count: int,
    match_mode: str,
) -> pd.DataFrame:
    """Build matched window detail dataframe."""
    records: list[dict[str, object]] = []
    for row_index, row in window_rows:
        normal_nums = selected_normal_nums(row, group_ids)
        if not is_matched(len(normal_nums), take_count, match_mode):
            continue
        special = selected_special(row, group_ids)
        records.append(
            {
                "近 N期": target_index - row_index + 1,
                "日期": row["date"],
                "號碼": format_nums(normal_nums, special),
                "N球": format_ball_count(ball_count(row, group_ids)),
            }
        )
    return pd.DataFrame(records, columns=["近 N期", "日期", "號碼", "N球"])


def group_hot_cold_df(window_rows: list[tuple[int, DrawRow]], group_ids: list[int]) -> pd.DataFrame:
    """Build A-D odd/even hot-cold dataframe."""
    counter: Counter[int] = Counter()
    for _row_index, row in window_rows:
        counter.update(num for num in row["nums"] if 1 <= num <= 40)

    records: list[dict[str, str]] = []
    for group_id in group_ids:
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
    return pd.DataFrame(records)


def group_rbg_df(window_rows: list[tuple[int, DrawRow]], group_ids: list[int]) -> pd.DataFrame:
    """Build A-D R/B/G hot-cold dataframe."""
    counter: Counter[int] = Counter()
    for _row_index, row in window_rows:
        counter.update(num for num in row["nums"] if 1 <= num <= 40)

    records: list[dict[str, str]] = []
    labels = {1: "R", 2: "B", 3: "G"}
    for group_id in group_ids:
        code, name, start_num, end_num = GROUPS[group_id]
        record = {"組別": f"{code}組-RBG {name}"}
        for color_id, label in labels.items():
            nums = [num for num in range(start_num, end_num + 1) if rbg_color_id(num) == color_id]
            record[label] = hot_cold_pairs(counter, nums)
        records.append(record)
    return pd.DataFrame(records)


def main() -> None:
    """Render Streamlit page."""
    apply_new_page_style()
    page_header(
        "1-40 多組條件分析",
        "以 A/B/C/D 四組查詢窗口期合條件開獎期，並顯示單雙與 R/B/G 冷熱門累計。",
    )

    with st.form("multi_group_params"):
        section_title("參數設定")
        mode = st.text_input("1. MODE", value="backtest")
        backtest_text = st.text_input("2. BACKTEST_DRAW_COUNT_LIST", value="[1]")
        window_text = st.text_input("3. WINDOW_DRAW_COUNT_LIST", value="[24]")
        groups_text = st.text_input("4. SELECT_GROUPS", value="(1,2,3,4)")
        take_count = st.text_input("5. COMBINATION_TAKE_COUNT", value="5")
        match_mode = st.text_input("6. MATCH_MODE", value=">=")
        submitted = st.form_submit_button("執行查詢")

    if not submitted:
        st.info("輸入參數後按「執行查詢」。")
        return

    try:
        draws = read_draws()
        backtest_count = parse_int_list(backtest_text)[0]
        window_count = parse_int_list(window_text)[0]
        group_ids = parse_int_list(groups_text)
        take_count_int = int(take_count)
    except (ValueError, IndexError, FileNotFoundError) as exc:
        st.error(f"參數或資料錯誤：{exc}")
        return

    mode = mode.strip()
    match_mode = match_mode.strip()
    if mode not in ("backtest", "predict"):
        st.error('MODE 只可輸入 "backtest" 或 "predict"。')
        return
    if match_mode not in (">=", "==", "<="):
        st.error('MATCH_MODE 只可輸入 ">="、"==" 或 "<="。')
        return
    if not group_ids or any(group_id not in GROUPS for group_id in group_ids):
        st.error("SELECT_GROUPS 只可輸入 1,2,3,4，例如 (1,2,3,4)。")
        return

    window_rows, check_index = build_window_rows(draws, mode, backtest_count, window_count)
    target_index = check_index - 1 if check_index is not None else len(draws) - 1
    detail_df = window_detail_df(draws, window_rows, target_index, group_ids, take_count_int, match_mode)
    window_total = len(window_rows)
    matched_count = len(detail_df)
    matched_percent = (matched_count / window_total * 100) if window_total else 0

    section_title("查詢摘要")
    cols = st.columns(5)
    cols[0].metric("模式", mode)
    cols[1].metric("窗口期", window_count)
    cols[2].metric("查詢", f"{matched_count}/{window_total}")
    cols[3].metric("百分比", f"{matched_percent:.0f}%")
    cols[4].metric("條件", f"{match_mode}{take_count_int} 球")

    if check_index is not None:
        st.caption(f"backtest 核對日期：{draws[check_index]['date']}，窗口期不包含核對期。")
    else:
        st.caption("predict 窗口期包含最新一期開獎期。")

    section_title("合條件開獎期")
    st.caption(
        f"結果合條件 {match_mode} {take_count_int} 球，"
        f"查詢 {matched_count} / {window_total} 期統計 = {matched_count}期 "
        f"({matched_percent:.0f} %)"
    )
    st.dataframe(
        detail_df,
        hide_index=True,
        width="stretch",
        column_config={
            "近 N期": st.column_config.NumberColumn("近 N期", width="small", format="%d"),
            "日期": st.column_config.TextColumn("日期", width="medium"),
            "號碼": st.column_config.TextColumn("號碼", width="large"),
            "N球": st.column_config.TextColumn("N球", width="small"),
        },
    )

    section_title("A-D 分組單雙冷熱門累計")
    st.dataframe(
        group_hot_cold_df(window_rows, group_ids),
        hide_index=True,
        width="stretch",
        column_config={
            "組別": st.column_config.TextColumn("組別", width="small"),
            "單數": st.column_config.TextColumn("單數", width="large"),
            "雙數": st.column_config.TextColumn("雙數", width="large"),
        },
    )

    section_title("A-D 分組 R/B/G 顏色冷熱門累計")
    st.dataframe(
        group_rbg_df(window_rows, group_ids),
        hide_index=True,
        width="stretch",
        column_config={
            "組別": st.column_config.TextColumn("組別", width="medium"),
            "R": st.column_config.TextColumn("R", width="large"),
            "B": st.column_config.TextColumn("B", width="large"),
            "G": st.column_config.TextColumn("G", width="large"),
        },
    )
