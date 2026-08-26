from pathlib import Path
import csv
from typing import TypedDict

"""
A1_v1_brithday_keys_analysis：
分段期數分析 1-9、10-20、21-31 三組生日號出現率。
加入 N7 特號獨立統計，暫不產生投注預測。
"""


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
M6_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"

# ---- 分析參數
PERIOD_COUNTS = [12, 6, 3]  # 分段期數，例如最近 12、6、3 期
PRINT_GROUP_OPTIONS = [1, 2, 3]  # 可選：[1]、[2]、[3]、[1, 2, 3]
SHOW_NUM_FREQ = True  # 可選：True 顯示每組單號出現次數
SHOW_SPECIAL_FREQ = True  # 可選：True 顯示每組特號出現次數


BIRTHDAY_GROUPS: dict[int, tuple[int, int]] = {
    1: (1, 9),
    2: (10, 20),
    3: (21, 31),
}


class GroupPeriodStats(TypedDict):
    period_count: int
    actual_count: int
    count_4up: int
    count_3: int
    count_2: int
    count_1: int
    count_0: int
    num_freq: dict[int, int]
    special_count: int
    special_freq: dict[int, int]


def birthday_range(group_option: int) -> tuple[int, int]:
    """按分組取得生日號範圍。"""

    if group_option not in BIRTHDAY_GROUPS:
        raise ValueError("PRINT_GROUP_OPTIONS 只可選 1、2、3")
    return BIRTHDAY_GROUPS[group_option]


def validate_params() -> None:
    """檢查主要參數。"""

    if not PERIOD_COUNTS:
        raise ValueError("PERIOD_COUNTS 不可空白")
    for period_count in PERIOD_COUNTS:
        if period_count < 1:
            raise ValueError("PERIOD_COUNTS 內所有期數必須大於 0")
    for group_option in PRINT_GROUP_OPTIONS:
        birthday_range(group_option)


def read_m6_rows(csv_path: Path = M6_CSV) -> list[dict[str, str]]:
    """讀入 M6 歷史開獎資料。"""

    if not csv_path.exists():
        raise FileNotFoundError(f"找不到 M6 CSV：{csv_path}")

    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames:
            reader.fieldnames = [name.strip().lstrip("\ufeff") for name in reader.fieldnames]
        return [
            {(key or "").strip().lstrip("\ufeff"): (value or "").strip() for key, value in row.items()}
            for row in reader
        ]


def parse_nums(row: dict[str, str]) -> list[int]:
    """抽取 N1-N6 正號，不計特號。"""

    nums: list[int] = []
    for idx in range(1, 7):
        try:
            nums.append(int(row.get(f"N{idx}", "0") or 0))
        except ValueError:
            nums.append(0)
    return nums


def parse_special_num(row: dict[str, str]) -> int | None:
    """抽取 N7 特號。"""

    try:
        special_num = int(row.get("N7", "0") or 0)
    except ValueError:
        return None
    return special_num if 1 <= special_num <= 49 else None


def selected_nums(nums: list[int], group_option: int) -> list[int]:
    """只保留指定分組範圍內的正號。"""

    start_num, end_num = birthday_range(group_option)
    return sorted(num for num in nums if start_num <= num <= end_num)


def build_group_period_stats(
    rows: list[dict[str, str]],
    period_count: int,
    group_option: int,
) -> GroupPeriodStats:
    """統計指定期數內，分組號每期出現 0 / 1 / 2 / 3 / 4up 的次數。"""

    recent_rows = rows[-period_count:]
    num_freq = {num: 0 for num in range(*_range_to_stop_tuple(group_option))}
    special_freq = {num: 0 for num in range(*_range_to_stop_tuple(group_option))}
    count_4up = 0
    count_3 = 0
    count_2 = 0
    count_1 = 0
    count_0 = 0
    special_count = 0
    start_num, end_num = birthday_range(group_option)

    for row in recent_rows:
        nums = selected_nums(parse_nums(row), group_option)
        for num in nums:
            num_freq[num] += 1

        special_num = parse_special_num(row)
        if special_num is not None and start_num <= special_num <= end_num:
            special_count += 1
            special_freq[special_num] += 1

        hit_count = len(nums)
        if hit_count >= 4:
            count_4up += 1
        elif hit_count == 3:
            count_3 += 1
        elif hit_count == 2:
            count_2 += 1
        elif hit_count == 1:
            count_1 += 1
        else:
            count_0 += 1

    return {
        "period_count": period_count,
        "actual_count": len(recent_rows),
        "count_4up": count_4up,
        "count_3": count_3,
        "count_2": count_2,
        "count_1": count_1,
        "count_0": count_0,
        "num_freq": num_freq,
        "special_count": special_count,
        "special_freq": special_freq,
    }


def _range_to_stop_tuple(group_option: int) -> tuple[int, int]:
    """將生日號範圍轉成 range 可用的 start / stop。"""

    start_num, end_num = birthday_range(group_option)
    return start_num, end_num + 1


def format_rate(count: int, total_count: int) -> str:
    """格式化期數比例。"""

    if total_count <= 0:
        return "0.00%"
    return f"{count / total_count * 100:.2f}%"


def print_period_stats(stats: GroupPeriodStats) -> None:
    """打印單一分段期數統計。"""

    total_count = stats["actual_count"]
    print(f"{stats['period_count']} 期：")
    print(f"4up = {stats['count_4up']}，{format_rate(stats['count_4up'], total_count)}")
    print(f"3   = {stats['count_3']}，{format_rate(stats['count_3'], total_count)}")
    print(f"2   = {stats['count_2']}，{format_rate(stats['count_2'], total_count)}")
    print(f"1   = {stats['count_1']}，{format_rate(stats['count_1'], total_count)}")
    print(f"0   = {stats['count_0']}，{format_rate(stats['count_0'], total_count)}")
    print(f"特號 = {stats['special_count']}，{format_rate(stats['special_count'], total_count)}")


def print_num_freq(num_freq: dict[int, int]) -> None:
    """打印單號出現次數。"""

    freq_text = "，".join(f"{num}:{count}" for num, count in sorted(num_freq.items()))
    print(f"正號單號出現次數：{freq_text}")


def print_special_freq(special_freq: dict[int, int]) -> None:
    """打印特號出現次數。"""

    freq_text = "，".join(f"{num}:{count}" for num, count in sorted(special_freq.items()))
    print(f"特號單號出現次數：{freq_text}")


def print_group_analysis(rows: list[dict[str, str]], group_option: int) -> None:
    """打印指定分組在多個期數段的分析結果。"""

    start_num, end_num = birthday_range(group_option)
    print()
    print(f"[{start_num}-{end_num}]")
    for period_count in PERIOD_COUNTS:
        stats = build_group_period_stats(rows, period_count, group_option)
        print_period_stats(stats)
        if SHOW_NUM_FREQ:
            print_num_freq(stats["num_freq"])
        if SHOW_SPECIAL_FREQ:
            print_special_freq(stats["special_freq"])
        print()


def main() -> None:
    """主程式入口。"""

    validate_params()
    rows = read_m6_rows()
    print("====== 分段期數，分組號出現率比對 ======")
    print(f"資料總期數：{len(rows)}")
    print(f"分析期數：{PERIOD_COUNTS}")
    for group_option in PRINT_GROUP_OPTIONS:
        print_group_analysis(rows, group_option)


if __name__ == "__main__":
    main()
