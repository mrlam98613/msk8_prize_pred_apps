from pathlib import Path
import csv
import random
from collections import Counter
from collections.abc import Sequence
from typing import Optional, TypedDict, Union


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
M6_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"


# MODE 可選："backtest" 或 "predict"；本版先主力測 backtest。
MODE = "backtest"
BACKTEST_DRAW_COUNT_LIST = [100]
WINDOW_DRAW_COUNT_LIST = [24]

# 查詢號碼範圍。
LOTTO_NUM_MIN = 1
LOTTO_NUM_MAX = 49

# 每期隨機發球數。
RANDOM_PICK_COUNT = 17
RANDOM_SEED = 20260927

# 五組分佈；17 球固定以 4+4+4+3+2 分配。
GROUPS = {
    "A": (1, 9),
    "B": (10, 20),
    "C": (21, 31),
    "D": (32, 40),
    "E": (41, 49),
}
GROUP_TAKE_COUNTS = {
    "A": 4,
    "B": 4,
    "C": 4,
    "D": 3,
    "E": 2,
}

# 窗口期熱號冷號顯示數量。
HOT_COLD_TAKE_COUNT = 8

# 是否打印每期明細。
PRINT_BACKTEST_DETAIL = True

# 是否打印熱號 / 冷號分析。
PRINT_HOT_COLD_RESULT = False


class DrawRow(TypedDict):
    date: str
    nums: list[int]
    special: Optional[int]
    prize_count: float


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    """讀取 CSV 並清理欄位名稱與文字空白。"""
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
    """安全轉換數值為 int。"""
    if not isinstance(value, (int, float, str)):
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def to_float(value: object, default: float = 0.0) -> float:
    """安全轉換數值為 float。"""
    if not isinstance(value, (int, float, str)):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_m6_row(row: dict[str, str]) -> DrawRow:
    """將 M6 原始 CSV 一行轉成標準 DrawRow。"""
    special = to_int(row.get("N7"))
    return {
        "date": row.get("nDdate", ""),
        "nums": [to_int(row.get(f"N{index}")) for index in range(1, 7)],
        "special": special if 1 <= special <= 49 else None,
        "prize_count": to_float(row.get("prize3")),
    }


def read_draws() -> list[DrawRow]:
    """讀取所有有效歷史開獎紀錄。"""
    return [row for row in [parse_m6_row(raw) for raw in read_csv_rows(M6_CSV)] if row["date"]]


def format_nums(nums: Sequence[Union[int, str]]) -> str:
    """格式化號碼列表。"""
    return "[" + ",".join(str(num) for num in nums) + "]"


def format_ball_count(value: float) -> str:
    """格式化球數，整數不顯示小數點。"""
    return str(int(value)) if value.is_integer() else f"{value:g}"


def nums_in_range(nums: list[int]) -> list[int]:
    """只保留設定範圍內的號碼。"""
    return [num for num in nums if LOTTO_NUM_MIN <= num <= LOTTO_NUM_MAX]


def group_nums(group_name: str) -> list[int]:
    """取得分組內、且落在手動 min/max 範圍的號碼。"""
    start, end = GROUPS[group_name]
    return [num for num in range(start, end + 1) if LOTTO_NUM_MIN <= num <= LOTTO_NUM_MAX]


def group_take_counts() -> dict[str, int]:
    """取得 17 球在分組內的固定分配數量。"""
    return dict(GROUP_TAKE_COUNTS)


def random_predict_nums(check_row: DrawRow, draw_index: int) -> list[int]:
    """按分組分佈，隨機產生 17 個不同預測號。"""
    rng = random.Random(f"{RANDOM_SEED}-{check_row['date']}-{draw_index}")
    selected: list[int] = []
    take_counts = group_take_counts()

    for group_name in GROUPS.keys():
        pool = group_nums(group_name)
        take_count = min(take_counts[group_name], len(pool))
        selected.extend(rng.sample(pool, take_count))

    if len(selected) < RANDOM_PICK_COUNT:
        remaining_pool = [num for num in range(LOTTO_NUM_MIN, LOTTO_NUM_MAX + 1) if num not in selected]
        selected.extend(rng.sample(remaining_pool, RANDOM_PICK_COUNT - len(selected)))

    return sorted(selected)


def hit_count(predicted_nums: list[int], check_row: DrawRow) -> float:
    """核對預測號；正號 1 球，特號命中 0.5 球。"""
    predicted_set = set(predicted_nums)
    normal_hits = sum(1 for num in check_row["nums"] if num in predicted_set and LOTTO_NUM_MIN <= num <= LOTTO_NUM_MAX)
    special = check_row["special"]
    special_hit = 0.5 if special is not None and special in predicted_set and LOTTO_NUM_MIN <= special <= LOTTO_NUM_MAX else 0.0
    return normal_hits + special_hit


def hit_nums(predicted_nums: list[int], check_row: DrawRow) -> list[str]:
    """取得命中號碼文字，特號以 * 標示。"""
    predicted_set = set(predicted_nums)
    hits = [str(num) for num in check_row["nums"] if num in predicted_set and LOTTO_NUM_MIN <= num <= LOTTO_NUM_MAX]
    special = check_row["special"]
    if special is not None and special in predicted_set and LOTTO_NUM_MIN <= special <= LOTTO_NUM_MAX:
        hits.append(f"*{special}")
    return hits


def window_frequency(window_rows: list[DrawRow]) -> Counter[int]:
    """統計窗口期內指定範圍正號出現次數。"""
    counter: Counter[int] = Counter({num: 0 for num in range(LOTTO_NUM_MIN, LOTTO_NUM_MAX + 1)})
    for row in window_rows:
        counter.update(nums_in_range(row["nums"]))
    return counter


def hot_cold_nums(window_rows: list[DrawRow]) -> tuple[list[int], list[int]]:
    """以窗口期正號頻率取得熱號與冷號。"""
    freq = window_frequency(window_rows)
    ranked_hot = sorted(freq.items(), key=lambda item: (-item[1], item[0]))
    ranked_cold = sorted(freq.items(), key=lambda item: (item[1], item[0]))
    hot_nums = [num for num, _count in ranked_hot[:HOT_COLD_TAKE_COUNT]]
    cold_nums = [num for num, _count in ranked_cold[:HOT_COLD_TAKE_COUNT]]
    return hot_nums, cold_nums


def format_group_ranges() -> str:
    """格式化分組範圍顯示。"""
    return "，".join(f"{name}={start}-{end}" for name, (start, end) in GROUPS.items())


def format_group_take_counts() -> str:
    """格式化各組發球數顯示。"""
    return "，".join(f"{name}={GROUP_TAKE_COUNTS[name]}球" for name in GROUPS.keys())


def print_query_setting() -> None:
    """打印本次測試設定。"""
    print(f"====== pr_v1 {LOTTO_NUM_MIN}-{LOTTO_NUM_MAX} 隨機多球回測 ======")
    print(f"運作模式：{MODE}")
    print(f"回測期列表：{BACKTEST_DRAW_COUNT_LIST}")
    print(f"窗口期列表：{WINDOW_DRAW_COUNT_LIST}")
    print(f"查詢號碼：{LOTTO_NUM_MIN}-{LOTTO_NUM_MAX}")
    print(f"每期隨機發球：{RANDOM_PICK_COUNT} 個不同號")
    print(f"分組：{format_group_ranges()}")
    print(f"分組發球：{format_group_take_counts()}")
    print("核對：正號=1球，特號=0.5球")
    print()


def print_hit_summary(hit_stats: Counter[float], total_count: int) -> None:
    """打印命中球數統計。"""
    print("----- 預測17球，核對命中球數統計 -----")
    for bucket in sorted(hit_stats.keys(), reverse=True):
        count = hit_stats[bucket]
        print(f"{format_ball_count(bucket):>3} 球 = {count} 期")
    avg_hit = sum(bucket * count for bucket, count in hit_stats.items()) / total_count if total_count else 0.0
    print(f"平均命中：{avg_hit:.2f} 球")


def run_backtest(draws: list[DrawRow]) -> None:
    """執行回測：每一期用前窗口期分析，隨機發 17 球核對該期。"""
    latest_index = len(draws) - 1
    for backtest_count in BACKTEST_DRAW_COUNT_LIST:
        for window_count in WINDOW_DRAW_COUNT_LIST:
            first_check_index = max(window_count, latest_index - backtest_count + 1)
            check_indices = list(range(first_check_index, latest_index + 1))
            hit_stats: Counter[float] = Counter()
            detail_rows: list[str] = []

            print(f"====== 回測期={backtest_count}，窗口期={window_count} ======")
            if PRINT_HOT_COLD_RESULT:
                latest_window_rows = draws[max(0, latest_index - window_count):latest_index]
                hot_nums, cold_nums = hot_cold_nums(latest_window_rows)
                print(f"最後窗口期熱號：{format_nums(hot_nums)}")
                print(f"最後窗口期冷號：{format_nums(cold_nums)}")

            for draw_order, check_index in enumerate(check_indices, start=1):
                check_row = draws[check_index]
                window_rows = draws[max(0, check_index - window_count):check_index]
                predicted_nums = random_predict_nums(check_row, draw_order - 1)
                hits = hit_count(predicted_nums, check_row)
                hit_stats[hits] += 1

                if PRINT_BACKTEST_DETAIL:
                    detail_text = (
                        f"{draw_order} /> 核對日期：{check_row['date']}，"
                        f"預測球 {format_nums(predicted_nums)}，"
                        f"命中 {format_nums(hit_nums(predicted_nums, check_row))} /> {format_ball_count(hits)} 球"
                    )
                    if PRINT_HOT_COLD_RESULT:
                        hot, cold = hot_cold_nums(window_rows)
                        detail_text += f"，熱號 {format_nums(hot)}，冷號 {format_nums(cold)}"
                    detail_rows.append(detail_text)

            if PRINT_BACKTEST_DETAIL:
                print()
                print("----- 回測逐期明細 -----")
                for detail in detail_rows:
                    print(detail)

            print()
            print_hit_summary(hit_stats, len(check_indices))
            print()


def main() -> None:
    """主流程。"""
    draws = read_draws()
    if not draws:
        raise FileNotFoundError(f"找不到或未能讀取 M6：{M6_CSV}")

    print_query_setting()
    if MODE == "backtest":
        run_backtest(draws)
    else:
        raise ValueError('MODE 目前只支援 "backtest"')


if __name__ == "__main__":
    main()
