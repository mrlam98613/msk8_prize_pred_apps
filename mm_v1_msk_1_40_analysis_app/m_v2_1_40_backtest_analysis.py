from pathlib import Path
from collections import Counter
import csv
import random
import sys
from typing import TypedDict


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
M6_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"
M4_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M4_lotto_prize_summary.csv"


# MODE 可選："backtest" 或 "predict"。
MODE = "backtest"
BACKTEST_DRAW_COUNT_LIST = [6]
WINDOW_DRAW_COUNT_LIST = [7]

# SELECT_GROUPS 可選 1,2,3,4；例如 (1,2,3) 自選前三組，(1,2,3,4) 全組別。
'''
SELECT_GROUPS = (1, 2, 3)      # 自選 1-31
SELECT_GROUPS = (1, 2, 3, 4)   # 全組別 1-40
SELECT_GROUPS = (2, 4)         # 只選 10-20 + 32-40
'''
SELECT_GROUPS = (1,2, 3,4)

# 每一期在指定範圍內有多少球才算符合條件。
COMBINATION_TAKE_COUNT = 2
BIRTHDAY_NUM_MATCH_MODE = ">="
# -------------------------
# PRIZE_OPTION=3 即顯示三獎中獎注數 prize3。
PRIZE_OPTION = 3 # 設定要顯示的獎項，3 即顯示三獎中獎注數。
PRIZE_PRINT_SHOW = False
# -------------------------
RANDOM_GROUP_TAKE_COUNT = 3
RANDOM_SEED = 20260912
HIGH_FREQ_LOOKBACK_LIST = [1, 2, 3, 4, 5]
COLD_EXTRA_DRAW_COUNT = 3
HOT_MIN_COUNT = 2

GROUPS = {
    1: ("A", 1, 9),
    2: ("B", 10, 20),
    3: ("C", 21, 31),
    4: ("D", 32, 40),
}


class DrawRow(TypedDict):
    date: str
    nums: list[int]
    special: int | None
    prize_count: float


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


def to_float(value: object, default: float = 0.0) -> float:
    ''' 安全轉換數值為 float，失敗時回傳 default。 '''
    if not isinstance(value, (int, float, str)):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_m6_row(row: dict[str, str]) -> DrawRow:
    ''' 將 M6 原始 CSV 一行轉成標準 DrawRow。 '''
    special = to_int(row.get("N7"))
    return {
        "date": row.get("nDdate", ""),
        "nums": [to_int(row.get(f"N{index}")) for index in range(1, 7)],
        "special": special if 1 <= special <= 49 else None,
        "prize_count": to_float(row.get(f"prize{PRIZE_OPTION}")),
    }


def read_draws() -> list[DrawRow]:
    ''' 讀取所有有效歷史開獎紀錄。 '''
    return [row for row in [parse_m6_row(raw) for raw in read_csv_rows(M6_CSV)] if row["date"]]


def read_next_draw_date() -> str:
    ''' 從 M4 摘要讀取下一期開獎日期。 '''
    rows = read_csv_rows(M4_CSV)
    return rows[-1].get("next_draw_date", "") if rows else ""


def format_nums(
    nums: list[int],
    special: int | None = None,
    show_special_placeholder: bool = False,
    special_placeholder: str = "_",
) -> str:
    ''' 格式化號碼列表，特號以 *號碼 放在最後。 '''
    parts = [str(num) for num in nums]
    if special is not None:
        parts.append(f"*{special}")
    elif show_special_placeholder:
        parts.append(special_placeholder)
    return "[" + ",".join(parts) + "]"


def format_hit_nums(nums: list[int], special: int | None = None) -> str:
    ''' 格式化命中號碼，不加入特號佔位符。 '''
    return format_nums(nums, special, False)


def format_ball_count(value: float) -> str:
    ''' 格式化球數，整數不顯示小數點。 '''
    return str(int(value)) if value.is_integer() else f"{value:g}"


def prize_text(value: float) -> str:
    ''' 格式化獎項注數，整數不顯示小數點。 '''
    return str(int(value)) if value.is_integer() else f"{value:g}"


def prize_print_text(row: DrawRow) -> str:
    ''' 依 PRIZE_PRINT_SHOW 決定是否顯示獎項注數。 '''
    if not PRIZE_PRINT_SHOW:
        return ""
    return f"，{PRIZE_OPTION}獎中獎注數：{prize_text(row['prize_count'])}"


def selected_nums(row: DrawRow, start_num: int, end_num: int) -> list[int]:
    ''' 取出某組範圍內的正號 N1..N6。 '''
    return sorted(num for num in row["nums"] if start_num <= num <= end_num)


def selected_special(row: DrawRow, start_num: int, end_num: int) -> int | None:
    ''' 判斷特號 N7 是否落在指定分組範圍內。 '''
    special = row["special"]
    if special is None:
        return None
    return special if start_num <= special <= end_num else None


def display_ball_count(normal_count: int, special: int | None) -> float:
    ''' 計算顯示球數；正號達 3 球時特號加 0.5。 '''
    if special is not None and normal_count >= 3:
        return normal_count + 0.5
    return float(normal_count)


def normalize_select_groups() -> tuple[int, ...]:
    ''' 檢查 SELECT_GROUPS 型別、組別範圍與最少組數。 '''
    if isinstance(SELECT_GROUPS, int):
        raise ValueError(
            "SELECT_GROUPS 需要 tuple/list，例如 (1, 2) 或 (1, 2, 3, 4)。"
            "你現在寫成 (2)，Python 會當作整數；若只寫單一 tuple 要用 (2,)，"
            "但本程式最少需要選 2 個組別。"
        )
    if not isinstance(SELECT_GROUPS, (tuple, list)):
        raise ValueError("SELECT_GROUPS 需要 tuple/list，例如 (1, 2) 或 (1, 2, 3, 4)。")

    group_ids = tuple(SELECT_GROUPS)
    if len(group_ids) < 2:
        raise ValueError("SELECT_GROUPS 最少需要選 2 個組別，例如 (1, 2)、(1, 2, 3) 或 (1, 2, 3, 4)。")
    for group_id in group_ids:
        if group_id not in GROUPS:
            raise ValueError(f"SELECT_GROUPS 只可選 1,2,3,4；錯誤值：{group_id}")
    return group_ids


def selected_groups() -> list[tuple[str, int, int]]:
    ''' 依 SELECT_GROUPS 取得實際使用的組別設定。 '''
    groups: list[tuple[str, int, int]] = []
    for group_id in normalize_select_groups():
        groups.append(GROUPS[group_id])
    return groups


def row_ball_count(row: DrawRow) -> float:
    ''' 計算某期开奖在所選組別中的總球數。 '''
    normal_count = sum(
        len(selected_nums(row, start_num, end_num))
        for _name, start_num, end_num in selected_groups()
    )
    has_special = any(
        selected_special(row, start_num, end_num) is not None
        for _name, start_num, end_num in selected_groups()
    )
    return display_ball_count(normal_count, row["special"] if has_special else None)


def is_matched(count: int) -> bool:
    ''' 判斷單組正號數量是否符合查詢條件。 '''
    if BIRTHDAY_NUM_MATCH_MODE == "==":
        return count == COMBINATION_TAKE_COUNT
    if BIRTHDAY_NUM_MATCH_MODE == "<=":
        return count <= COMBINATION_TAKE_COUNT
    return count >= COMBINATION_TAKE_COUNT


def group_result_text(row: DrawRow, name: str, start_num: int, end_num: int) -> str:
    ''' 產生單組詳細顯示文字，包含組名與單組球數。 '''
    nums = selected_nums(row, start_num, end_num)
    if not is_matched(len(nums)):
        return f"[{name}] [] /> 0 球"
    special = selected_special(row, start_num, end_num)
    ball_count = display_ball_count(len(nums), special)
    return f"[{name}] {format_nums(nums, special)} /> {format_ball_count(ball_count)} 球"


def group_only_text(row: DrawRow, name: str, start_num: int, end_num: int) -> str:
    ''' 產生單組簡潔顯示文字，只保留 [] 號碼。 '''
    nums = selected_nums(row, start_num, end_num)
    special = selected_special(row, start_num, end_num)
    return format_nums(nums, special)


def row_result_text(row: DrawRow) -> str:
    ''' 產生一期的所有選中組別顯示文字與總球數。 '''
    group_text = "，".join(
        group_only_text(row, name, start_num, end_num)
        for name, start_num, end_num in selected_groups()
    )
    return f"{group_text} /> {format_ball_count(row_ball_count(row))} 球"


def all_check_nums_text(row: DrawRow) -> str:
    ''' 格式化核對期完整 N1..N6 + N7 開獎號碼。 '''
    return format_nums(sorted(row["nums"]), row["special"])


def selected_draw_nums(row: DrawRow, start_num: int, end_num: int) -> list[int]:
    ''' 取得某分組範圍內的 N1..N7 號碼，特號也作單球分析。 '''
    nums = selected_nums(row, start_num, end_num)
    special = selected_special(row, start_num, end_num)
    if special is not None:
        nums.append(special)
    return sorted(nums)


def group_number_pool(start_num: int, end_num: int) -> list[int]:
    ''' 取得單一分組內全部可分析球號。 '''
    return list(range(start_num, end_num + 1))


def build_group_window_counts(window_rows: list[DrawRow], start_num: int, end_num: int) -> Counter[int]:
    ''' 只統計窗口期內符合條件的開獎期，計算單球出現次數。 '''
    counter: Counter[int] = Counter()
    for row in window_rows:
        normal_nums = selected_nums(row, start_num, end_num)
        if not is_matched(len(normal_nums)):
            continue
        counter.update(selected_draw_nums(row, start_num, end_num))
    return counter


def find_hot_nums(counter: Counter[int]) -> list[int]:
    ''' 熱門號：窗口合條件樣本內出現次數達 HOT_MIN_COUNT 的號碼。 '''
    hot_items = [(num, count) for num, count in counter.items() if count >= HOT_MIN_COUNT]
    return [num for num, _count in sorted(hot_items, key=lambda item: (-item[1], item[0]))]


def find_high_freq_nums(draws: list[DrawRow], check_index: int, start_num: int, end_num: int) -> list[int]:
    ''' 高頻號：核對期有開出，且前 1 至 5 期內曾重複出現的號碼。 '''
    check_nums = set(selected_draw_nums(draws[check_index], start_num, end_num))
    high_freq: set[int] = set()
    for lag in HIGH_FREQ_LOOKBACK_LIST:
        source_index = check_index - lag
        if source_index < 0:
            continue
        source_nums = set(selected_draw_nums(draws[source_index], start_num, end_num))
        high_freq.update(check_nums & source_nums)
    return sorted(high_freq)


def find_cold_nums(draws: list[DrawRow], cold_start_index: int, end_index: int, start_num: int, end_num: int) -> list[int]:
    ''' 冷號：窗口期加前 3 期內完全沒有出現的組內號碼。 '''
    appeared: set[int] = set()
    for row in draws[cold_start_index:end_index]:
        appeared.update(selected_draw_nums(row, start_num, end_num))
    return [num for num in group_number_pool(start_num, end_num) if num not in appeared]


def find_weak_nums(counter: Counter[int], hot_nums: list[int], high_freq_nums: list[int], cold_nums: list[int]) -> list[int]:
    ''' 弱號：窗口合條件樣本內只出現 1 次，且不屬熱門、高頻、冷號。 '''
    excluded = set(hot_nums) | set(high_freq_nums) | set(cold_nums)
    return sorted(num for num, count in counter.items() if count == 1 and num not in excluded)


def format_analysis_nums(nums: list[int]) -> str:
    ''' 格式化分析號碼，只顯示號碼，不顯示組名及出球次數。 '''
    return format_nums(nums)


def append_non_empty_analysis(parts: list[str], nums: list[int]) -> None:
    ''' 分析結果只加入有號碼的分組，空分組不顯示。 '''
    if nums:
        parts.append(format_analysis_nums(nums))


def find_no_group_hit_count(window_rows: list[DrawRow], start_num: int, end_num: int) -> int:
    ''' 統計窗口期內該分組完全沒有開出 N1..N7 的期數。 '''
    return sum(1 for row in window_rows if not selected_draw_nums(row, start_num, end_num))


def build_group_analysis_lines(
    draws: list[DrawRow],
    window_rows: list[DrawRow],
    check_index: int,
    window_start_index: int,
) -> list[str]:
    ''' 建立熱門、高頻、弱號、冷號四類分組分析結果。 '''
    cold_start_index = max(0, window_start_index - COLD_EXTRA_DRAW_COUNT)
    hot_parts: list[str] = []
    high_freq_parts: list[str] = []
    weak_parts: list[str] = []
    cold_parts: list[str] = []
    no_group_hit_parts: list[str] = []

    for name, start_num, end_num in selected_groups():
        counter = build_group_window_counts(window_rows, start_num, end_num)
        hot_nums = find_hot_nums(counter)
        high_freq_nums = find_high_freq_nums(draws, check_index, start_num, end_num)
        cold_nums = find_cold_nums(draws, cold_start_index, check_index, start_num, end_num)
        weak_nums = find_weak_nums(counter, hot_nums, high_freq_nums, cold_nums)
        no_group_hit_count = find_no_group_hit_count(window_rows, start_num, end_num)

        append_non_empty_analysis(hot_parts, hot_nums)
        append_non_empty_analysis(high_freq_parts, high_freq_nums)
        append_non_empty_analysis(weak_parts, weak_nums)
        append_non_empty_analysis(cold_parts, cold_nums)
        if no_group_hit_count:
            no_group_hit_parts.append(f"{name}[{no_group_hit_count}期]")

    return [
        "熱門號全開次數多 ：" + "，".join(hot_parts),
        "高頻頻在隔期出現 ：" + "，".join(high_freq_parts),
        "弱號窗口期 出現  1 次  ：" + "，".join(weak_parts),
        f"窗口期 + {COLD_EXTRA_DRAW_COUNT} 期 都不出現的球號 ：" + "，".join(cold_parts),
        "開獎期內，全組沒有球號 ：" + "，".join(no_group_hit_parts),
    ]


def print_window_analysis(
    draws: list[DrawRow],
    window_rows: list[DrawRow],
    check_index: int,
    window_start_index: int,
) -> None:
    ''' 打印窗口期內合條件開獎號的單球分析結果。 '''
    for line in build_group_analysis_lines(draws, window_rows, check_index, window_start_index):
        print(line)


def build_random_group_prediction(target_date: str, window_count: int) -> list[int]:
    ''' 按所選組別每組固定隨機發指定球數。 '''
    seed = RANDOM_SEED + int(target_date.replace("-", "")) + window_count
    rng = random.Random(seed)
    predicted: list[int] = []
    for _name, start_num, end_num in selected_groups():
        predicted.extend(sorted(rng.sample(range(start_num, end_num + 1), RANDOM_GROUP_TAKE_COUNT)))
    return sorted(predicted)


def random_backtest_text(check_row: DrawRow, window_count: int) -> str:
    ''' 產生 backtest 核對文字，包含預測球與命中球數。 '''
    predicted = build_random_group_prediction(check_row["date"], window_count)
    predicted_set = set(predicted)
    normal_hits = sorted(num for num in check_row["nums"] if num in predicted_set)
    special_hit = check_row["special"] if check_row["special"] in predicted_set else None
    hit_score = display_ball_count(len(normal_hits), special_hit)
    return (
        f"核對日期：{check_row['date']}: {all_check_nums_text(check_row)}，"
        f"預測球 {format_nums(predicted)}，"
        f"命中: {format_hit_nums(normal_hits, special_hit)} /> {format_ball_count(hit_score)} 球。"
    )


def random_predict_text(next_draw_date: str, window_count: int) -> str:
    ''' 隨機發球功能 '''
    target_date = next_draw_date or "00000000"
    predicted = build_random_group_prediction(target_date, window_count)
    return f"下期開獎日期：{next_draw_date or '未知'}，預測球 {format_nums(predicted)}。"


def print_query_setting() -> None:
    ''' 打印本次執行的模式與主要查詢參數。 '''
    group_ids = normalize_select_groups()
    mode_text = "全組別" if group_ids == tuple(GROUPS.keys()) else "自選組別"
    print("====== m_v2 1-40 回測窗口單球分析 ======")
    print(f"運作模式：{MODE}")
    print(f"查詢模式：{mode_text} {group_ids}")
    print(f"回測期列表：{BACKTEST_DRAW_COUNT_LIST}")
    print(f"窗口期列表：{WINDOW_DRAW_COUNT_LIST}")
    print(f"符合條件：範圍內號碼數量 {BIRTHDAY_NUM_MATCH_MODE}{COMBINATION_TAKE_COUNT} 球")
    print(f"查詢號碼：N1..N7，N7 特號以 * 顯示")
    prize_show_text = f"，prize{PRIZE_OPTION} 中獎注數" if PRIZE_PRINT_SHOW else ""
    print(f"顯示欄位：開獎日期，分組號碼，N球{prize_show_text}")
    print()


def print_draw_rows(
    draws: list[DrawRow],
    window_rows: list[tuple[int, DrawRow]],
    target_index: int,
) -> None:
    ''' 打印窗口期內每一期的組別分布。 '''
    for row_index, row in window_rows:
        rank = target_index - row_index + 1
        print(
            f"近 {rank}期：{row['date']}，{row_result_text(row)}"
            f"{prize_print_text(row)}"
        )


def query_mode_text() -> str:
    ''' 產生標題用的查詢模式文字。 '''
    group_ids = normalize_select_groups()
    if group_ids == tuple(GROUPS.keys()):
        return "全組別"
    return f"自選組別 {group_ids}"


def print_backtest_window(
    draws: list[DrawRow],
    check_index: int,
    backtest_count: int,
    window_count: int,
) -> None:
    ''' 打印單一期 backtest 窗口資料與核對結果。 '''
    check_row = draws[check_index]
    window_start_index = max(0, check_index - window_count)
    window_rows = [
        (row_index, row)
        for row_index, row in enumerate(draws[window_start_index:check_index], start=window_start_index)
    ]
    print(f"====== {query_mode_text()}，回測期= {backtest_count}，N1..N7，窗口期 = {window_count} ======")
    print(f"backtest：窗口期不包括核對期，預留核對預測")
    print_draw_rows(draws, window_rows, check_index - 1)
    print_window_analysis(draws, [row for _row_index, row in window_rows], check_index, window_start_index)
    print()


def print_predict_window(draws: list[DrawRow], window_count: int, next_draw_date: str) -> None:
    ''' 打印 predict 模式最後窗口期資料與下期預測。 '''
    latest_index = len(draws) - 1
    window_start_index = max(0, latest_index - window_count + 1)
    window_rows = [
        (row_index, row)
        for row_index, row in enumerate(draws[window_start_index:latest_index + 1], start=window_start_index)
    ]
    print(f"====== {query_mode_text()}，預測模式，N1..N7，窗口期 = {window_count} ======")
    print(f"predict：只顯示最後窗口期分析及預測，不核對")
    print_draw_rows(draws, window_rows, latest_index)
    print_window_analysis(draws, [row for _row_index, row in window_rows], latest_index, window_start_index)
    print(random_predict_text(next_draw_date, window_count))
    print()


def main() -> None:
    ''' 主流程：驗證參數、讀取資料，並按 MODE 執行。 '''
    try:
        normalize_select_groups()
    except ValueError as exc:
        print(f"參數錯誤：{exc}", file=sys.stderr)
        raise SystemExit(1)

    draws = read_draws()
    if not draws:
        raise FileNotFoundError(f"找不到或未能讀取 M6：{M6_CSV}")

    print_query_setting()
    latest_index = len(draws) - 1

    if MODE == "backtest":
        for backtest_count in BACKTEST_DRAW_COUNT_LIST:
            first_check_index = max(0, latest_index - backtest_count + 1)
            check_indices = range(first_check_index, latest_index + 1)
            for window_count in WINDOW_DRAW_COUNT_LIST:
                for check_index in check_indices:
                    print_backtest_window(draws, check_index, backtest_count, window_count)
    elif MODE == "predict":
        next_draw_date = read_next_draw_date()
        for window_count in WINDOW_DRAW_COUNT_LIST:
            print_predict_window(draws, window_count, next_draw_date)
    else:
        raise ValueError('MODE 只能是 "backtest" 或 "predict"')


if __name__ == "__main__":
    main()
