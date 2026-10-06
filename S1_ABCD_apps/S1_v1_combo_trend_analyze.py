from pathlib import Path
import csv
from typing import Optional, TypedDict


'''
S1 組合走趨分析：獨立腳本，不依賴其它程式。

用途：
1. 追蹤 ABC / BCD / ABCD 大組合是否連續合條件。
2. 找出連續型態、間斷期、回補訊號。
3. 給出投注提示：單式 / 複式 7 字 / 多組合貼拖 / 聰明組合 12 球。
'''

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
M6_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"


VERSION = "S1_v1 1-40"
MODE = "predict" # "backtest" 不包含核對期；"predict" 包含最後一期已開號。
BACKTEST_DRAW_COUNT_LIST = [1]
WINDOW_DRAW_COUNT_LIST = [13]

# 走勢提示門檻。
RECENT_WINDOW_SHORT = 5
RECENT_WINDOW_LONG = 10
HOT_STREAK_STRONG = 3
RECENT5_STRONG_COUNT = 4
RECENT5_WEAK_COUNT = 2
BREAK_STREAK_STOP = 2

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


class TrendGroupConfig(TypedDict):
    group_ids: tuple[int, ...]
    take_count: int
    match_mode: str
    note: str


TREND_GROUP_SETS: dict[str, TrendGroupConfig] = {
    "ABC": {
        "group_ids": (1, 2, 3),
        "take_count": 4,
        "match_mode": ">=",
        "note": "31 球池，>=4 球追蹤 5 獎型態",
    },
    "BCD": {
        "group_ids": (2, 3, 4),
        "take_count": 4,
        "match_mode": ">=",
        "note": "31 球池，>=4 球追蹤 5 獎型態",
    },
    "ABCD": {
        "group_ids": (1, 2, 3, 4),
        "take_count": 5,
        "match_mode": ">=",
        "note": "40 球池，>=5 球追蹤大池型態",
    },
}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    ''' 讀取 CSV 並清理欄位名稱與文字空白。 '''
    if not path.exists():
        raise FileNotFoundError(f"找不到 CSV：{path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames:
            reader.fieldnames = [name.strip().lstrip("\ufeff") for name in reader.fieldnames]
        return [
            {(key or "").strip().lstrip("\ufeff"): (value or "").strip() for key, value in row.items()}
            for row in reader
        ]


def to_int(value: object, default: int = 0) -> int:
    ''' 安全轉換數值為 int，失敗時回傳 default。 '''
    if not isinstance(value, (int, float, str)):
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def parse_m6_row(row: dict[str, str]) -> DrawRow:
    ''' 將 M6 原始 CSV 一行轉成標準 DrawRow。 '''
    special = to_int(row.get("N7"))
    return {
        "date": row.get("nDdate", ""),
        "nums": [to_int(row.get(f"N{index}")) for index in range(1, 7)],
        "special": special if 1 <= special <= 49 else None,
    }


def read_draws() -> list[DrawRow]:
    ''' 讀取所有有效歷史開獎紀錄。 '''
    return [row for row in [parse_m6_row(raw) for raw in read_csv_rows(M6_CSV)] if row["date"]]


def format_group_ids(group_ids: tuple[int, ...]) -> str:
    ''' 格式化組別 ID。 '''
    return "(" + ", ".join(str(group_id) for group_id in group_ids) + ")"


def format_nums(nums: list[int], special: Optional[int] = None) -> str:
    ''' 格式化號碼列表，特號以 *號碼 放在最後。 '''
    parts = [str(num) for num in nums]
    if special is not None:
        parts.append(f"*{special}")
    return "[" + ",".join(parts) + "]"


def is_matched(count: int, take_count: int, match_mode: str) -> bool:
    ''' 判斷球數是否符合追蹤條件。 '''
    if match_mode == "==":
        return count == take_count
    if match_mode == "<=":
        return count <= take_count
    return count >= take_count


def selected_group_ranges(group_ids: tuple[int, ...]) -> list[tuple[int, int]]:
    ''' 取得選中大組合的號碼範圍。 '''
    return [(GROUPS[group_id][2], GROUPS[group_id][3]) for group_id in group_ids]


def pool_nums(row: DrawRow, group_ids: tuple[int, ...]) -> list[int]:
    ''' 取得某期在大組合池內的正號。 '''
    ranges = selected_group_ranges(group_ids)
    nums = [
        num
        for num in row["nums"]
        if any(start_num <= num <= end_num for start_num, end_num in ranges)
    ]
    return sorted(nums)


def pool_special(row: DrawRow, group_ids: tuple[int, ...]) -> Optional[int]:
    ''' 取得某期在大組合池內的特號。 '''
    special = row["special"]
    if special is None:
        return None
    for start_num, end_num in selected_group_ranges(group_ids):
        if start_num <= special <= end_num:
            return special
    return None


def pool_ball_count(row: DrawRow, group_ids: tuple[int, ...]) -> int:
    ''' 計算大組合池每期開球總數；特號以 1 球計入。 '''
    return len(pool_nums(row, group_ids)) + (1 if pool_special(row, group_ids) is not None else 0)


def pool_desc(group_ids: tuple[int, ...]) -> str:
    ''' 格式化大組合說明。 '''
    codes = "".join(GROUPS[group_id][0] for group_id in group_ids)
    start_num = min(GROUPS[group_id][2] for group_id in group_ids)
    end_num = max(GROUPS[group_id][3] for group_id in group_ids)
    return f"{codes} = {start_num}-{end_num}"


def streak_from_end(values: list[bool], expected: bool) -> int:
    ''' 計算最近連續 True 或 False 期數。 '''
    count = 0
    for value in reversed(values):
        if value != expected:
            break
        count += 1
    return count


def longest_hot_streak(values: list[bool]) -> int:
    ''' 計算最長連續合條件期數。 '''
    longest = 0
    current = 0
    for value in values:
        if value:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def has_recent_rebound(values: list[bool]) -> bool:
    ''' 判斷最近是否出現中斷後回補，例如 -H 或 --H。 '''
    if len(values) < 2 or not values[-1]:
        return False
    return not values[-2] or (len(values) >= 3 and not values[-3])


def trend_score(values: list[bool]) -> float:
    ''' 計算簡單走勢分數。 '''
    hot_streak = streak_from_end(values, True)
    break_streak = streak_from_end(values, False)
    recent5 = sum(values[-RECENT_WINDOW_SHORT:])
    recent10 = sum(values[-RECENT_WINDOW_LONG:])
    return hot_streak * 2 + recent5 + recent10 * 0.5 - break_streak * 2


def trend_level(values: list[bool]) -> str:
    ''' 依近期連續、近 5 期、間斷狀態判斷強弱。 '''
    hot_streak = streak_from_end(values, True)
    break_streak = streak_from_end(values, False)
    recent5 = sum(values[-RECENT_WINDOW_SHORT:])
    if break_streak >= BREAK_STREAK_STOP:
        return "已斷"
    if hot_streak >= HOT_STREAK_STRONG or recent5 >= RECENT5_STRONG_COUNT:
        return "強"
    if recent5 <= RECENT5_WEAK_COUNT:
        return "弱"
    if has_recent_rebound(values):
        return "中，間斷後回補"
    return "中"


def bet_advice(level: str) -> str:
    ''' 依走勢強弱給出投注提示。 '''
    if level == "強":
        return "連續型態組合出現，可投注多組合貼拖，或聰明組合 12 個號碼投注。"
    if level.startswith("中"):
        return "走勢中，可用複式 7-9 字或小組合追蹤。"
    if level == "弱":
        return "走勢偏弱，只投注單式，或等待下一期確認。"
    return "連續型態組合已斷，只投注單式 或複式 7 字。"


def next_draw_bet_advice(name: str, level: str) -> str:
    ''' 依組合池與走勢強弱，產生下期投注走趨建議。 '''
    if name in ("ABC", "BCD"):
        if level == "強":
            return f"{name}：走勢強，可用單/複式，3+3+3 = 9 號以膽拖投注。"
        if level.startswith("中"):
            return f"{name}：走勢中，可小注單/複式，3+3+3 = 9 號以膽拖追蹤。"
        return f"{name}：走勢{level}，只投注單式 或複式 7 字，不建議 9 號膽拖加碼。"

    if level == "強":
        return f"{name}：走勢強，可用 強 12 球- 膽拖，或聰明組合。"
    if level.startswith("中"):
        return f"{name}：走勢中，可用 12 球膽拖小注追蹤，或降低組合注數。"
    return f"{name}：走勢{level}，只投注單式 或複式 7 字，暫不建議 12 球組合。"


def trend_sequence(values: list[bool]) -> str:
    ''' 將走勢轉成 H / - 序列。 '''
    return "".join("H" if value else "-" for value in values)


def print_window_rows(
    window_rows: list[tuple[int, DrawRow]],
    target_index: int,
    group_ids: tuple[int, ...],
    take_count: int,
    match_mode: str,
) -> list[bool]:
    ''' 列印窗口期每期走勢，並回傳合條件序列。 '''
    matches: list[bool] = []
    for row_index, row in window_rows:
        rank = target_index - row_index + 1
        nums = pool_nums(row, group_ids)
        special = pool_special(row, group_ids)
        count = len(nums) + (1 if special is not None else 0)
        matched = is_matched(count, take_count, match_mode)
        matches.append(matched)
        mark = "H" if matched else "-"
        result_text = f"{format_nums(nums, special)} /> {count} 球" if matched else ""
        print(f"近 {rank:>2}期：{row['date']}，{mark}，{result_text}")
    return matches


def print_trend_summary(values: list[bool]) -> None:
    ''' 列印連續走勢統計與系統提示。 '''
    hot_streak = streak_from_end(values, True)
    break_streak = streak_from_end(values, False)
    recent5_count = sum(values[-RECENT_WINDOW_SHORT:])
    recent10_count = sum(values[-RECENT_WINDOW_LONG:])
    longest_streak = longest_hot_streak(values)
    level = trend_level(values)
    print("/> -------------")
    print(f"走勢序列：{trend_sequence(values)}")
    print(f"最近連續合條件：{hot_streak}期")
    print(f"最近連續中斷：{break_streak}期")
    print(f"最近{RECENT_WINDOW_SHORT}期合條件：{recent5_count}/{min(RECENT_WINDOW_SHORT, len(values))}")
    print(f"最近{RECENT_WINDOW_LONG}期合條件：{recent10_count}/{min(RECENT_WINDOW_LONG, len(values))}")
    print(f"最長連續合條件：{longest_streak}期")
    print(f"走勢分數：{trend_score(values):.1f}")
    print(f"走勢判斷：{level}")
    print(f"系統提示：{bet_advice(level)}")


def print_combo_trend_sections(
    window_rows: list[tuple[int, DrawRow]],
    target_index: int,
) -> None:
    ''' 列印各組合池的走趨分析區塊。 '''
    print("追蹤條件：各組合池獨立門檻，特號 N7 以 1 球計入")
    trend_levels: dict[str, str] = {}

    for name, config in TREND_GROUP_SETS.items():
        group_ids = config["group_ids"]
        take_count = config["take_count"]
        match_mode = config["match_mode"]
        note = config["note"]
        print()
        print(f"---------------- {name} {format_group_ids(group_ids)} 連續組合走趨 ----------------")
        print(f"追蹤組合：{pool_desc(group_ids)}")
        print(f"組合條件：每期合併分組總球數 {match_mode} {take_count} 球 (包括特號)")
        print(f"型態說明：{note}")
        values = print_window_rows(window_rows, target_index, group_ids, take_count, match_mode)
        print_trend_summary(values)
        trend_levels[name] = trend_level(values)
    print_next_draw_bet_summary(trend_levels)
    print()


def print_next_draw_bet_summary(trend_levels: dict[str, str]) -> None:
    ''' 列印下期投注走趨總結。 '''
    print()
    print("---------------- 下期投注走趨總結 ----------------")
    for name in TREND_GROUP_SETS:
        level = trend_levels.get(name, "弱")
        print(next_draw_bet_advice(name, level))


def print_combo_trend_window(
    draws: list[DrawRow],
    check_index: int,
    backtest_count: int,
    window_count: int,
    backtest_index: int,
    total_backtest_count: int,
) -> None:
    ''' 列印單一回測期、單一窗口期的組合走趨分析。 '''
    display_backtest_index = total_backtest_count - backtest_index + 1
    window_start_index = max(0, check_index - window_count)
    window_rows = [
        (row_index, row)
        for row_index, row in enumerate(draws[window_start_index:check_index], start=window_start_index)
    ]

    print(
        f"======[回測 {display_backtest_index}] {VERSION} 組合走趨分析，"
        f"回測期= {backtest_count}，窗口期 = {window_count} ======"
    )
    print("backtest：窗口期不包括核對期，預留核對預測")
    print_combo_trend_sections(window_rows, check_index - 1)


def print_predict_window(draws: list[DrawRow], window_count: int) -> None:
    ''' 列印 predict 模式最後窗口期；包含最後一期已開號。 '''
    latest_index = len(draws) - 1
    window_start_index = max(0, latest_index - window_count + 1)
    window_rows = [
        (row_index, row)
        for row_index, row in enumerate(draws[window_start_index:latest_index + 1], start=window_start_index)
    ]

    print(f"====== {VERSION} 組合走趨分析，predict，窗口期 = {window_count} ======")
    print("predict：窗口期包含最後一期已開號，用於預測下一期")
    print_combo_trend_sections(window_rows, latest_index)


def print_query_setting() -> None:
    ''' 打印本次執行的主要參數。 '''
    print(f"======Vol:{VERSION} 組合走趨分析 ======")
    print(f"運作模式：{MODE}")
    if MODE == "backtest":
        print(f"回測期列表：{BACKTEST_DRAW_COUNT_LIST}")
    print(f"窗口期列表：{WINDOW_DRAW_COUNT_LIST}")
    print("符合條件：各組合池獨立門檻，特號 N7 以 1 球計入")
    setting_parts: list[str] = []
    for name, config in TREND_GROUP_SETS.items():
        group_ids = config["group_ids"]
        take_count = config["take_count"]
        match_mode = config["match_mode"]
        setting_parts.append(f"{name}{format_group_ids(group_ids)} {match_mode}{take_count}")
    print("追蹤組合：" + "，".join(setting_parts))
    print()


def main() -> None:
    ''' 主流程。 '''
    draws = read_draws()
    if not draws:
        raise FileNotFoundError(f"找不到或未能讀取 M6：{M6_CSV}")

    print_query_setting()
    latest_index = len(draws) - 1
    if MODE == "backtest":
        for backtest_count in BACKTEST_DRAW_COUNT_LIST:
            first_check_index = max(0, latest_index - backtest_count + 1)
            check_indices = range(first_check_index, latest_index + 1)
            total_backtest_count = len(check_indices)
            for window_count in WINDOW_DRAW_COUNT_LIST:
                for backtest_index, check_index in enumerate(check_indices, start=1):
                    print_combo_trend_window(
                        draws,
                        check_index,
                        backtest_count,
                        window_count,
                        backtest_index,
                        total_backtest_count,
                    )
    elif MODE == "predict":
        for window_count in WINDOW_DRAW_COUNT_LIST:
            print_predict_window(draws, window_count)
    else:
        raise ValueError('MODE 只能是 "backtest" 或 "predict"')


if __name__ == "__main__":
    main()
