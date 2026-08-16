from pathlib import Path
import csv
import itertools
from typing import TypedDict

'''
M6 分析1-9，  3 位組合回測 
====== 最近 100 期，N1-N6 包含 1-10 號數量 == 3，顯示 prize3 注數 ======
序號 日期 : 1-10開獎號 /> 注數
  1 2025-11-18 : 2,4,10 /> 231.2
  2 2025-12-11 : 1,5,6 /> 358.5
  3 2025-12-25 : 1,2,4 /> 127.5
  4 2026-03-19 : 2,6,8 /> 56.5
  5 2026-04-21 : 2,4,10 /> 126.5
  6 2026-05-02 : 2,3,8 /> 1153.7
  7 2026-05-19 : 1,2,4 /> 185
  8 2026-06-20 : 5,7,10 /> 57.5
  9 2026-07-11 : 2,5,7 /> 65
 10 2026-08-08 : 1,3,7 /> 115.5
 
 ====== 1-10 選 3 組合核對統計，共 120 組 ======
index N1,N2,N3,Sum
  1.  1,2,3, 0
  2.  1,2,4, -----> 2
  3.  1,2,5, 0
  4.  1,2,6, 0

'''

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
M6_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"

RECENT_DRAW_COUNT = 50 # 回測期數
# ---
MIN_BIRTHDAY_NUM_COUNT = 2 # 每注開獎號，符合查詢範圍的號碼數量
BIRTHDAY_NUM_MATCH_MODE = "=="  # 可選：">=" 或 "=="
BIRTHDAY_NUM_MIN = 20 # 查詢範圍最小號碼，例如 1、10、20
BIRTHDAY_NUM_MAX = 31 # 查詢範圍最大號碼，例如 9、19、29
PRIZE_OPTION = 3  # 可選：1、2、3=3獎 中獎注數顯示

# ====
SHOW_PRIZE_COUNT = True  # 可選：True 顯示中獎注數；False 不顯示
# ---------------------
COMBINATION_TAKE_COUNT = 2 # 可選：號碼組合核對統計，取幾個號碼組合
SHOW_COMBINATION_STATS = True  # 可選：True 顯示命中的號碼組合核對統計
# ----


class MatchedDraw(TypedDict):
    date: str
    nums: list[int]
    birthday_num_count: int
    prize_label: str
    prize_count: str


def validate_query_range() -> None:
    if BIRTHDAY_NUM_MIN < 1 or BIRTHDAY_NUM_MAX > 49:
        raise ValueError("查詢號碼範圍必須介乎 1 至 49")
    if BIRTHDAY_NUM_MIN > BIRTHDAY_NUM_MAX:
        raise ValueError("BIRTHDAY_NUM_MIN 不可大於 BIRTHDAY_NUM_MAX")


def read_m6_lotto_history(csv_path: Path = M6_CSV) -> list[dict[str, str]]:
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


def parse_draw_numbers(row: dict[str, str]) -> list[int]:
    nums = []
    for idx in range(1, 7):
        value = row.get(f"N{idx}", "")
        try:
            nums.append(int(value))
        except ValueError:
            nums.append(0)
    return nums


def count_birthday_nums(nums: list[int]) -> int:
    validate_query_range()
    return sum(1 for num in nums if BIRTHDAY_NUM_MIN <= num <= BIRTHDAY_NUM_MAX)


def is_target_draw(nums: list[int], match_mode: str = BIRTHDAY_NUM_MATCH_MODE) -> bool:
    birthday_num_count = count_birthday_nums(nums)
    if match_mode == "==":
        return birthday_num_count == MIN_BIRTHDAY_NUM_COUNT
    return birthday_num_count >= MIN_BIRTHDAY_NUM_COUNT


def get_prize_count(row: dict[str, str], prize_option: int = PRIZE_OPTION) -> tuple[str, str]:
    if prize_option not in {1, 2, 3}:
        raise ValueError("PRIZE_OPTION 只可選 1、2、3")

    prize_label = f"prize{prize_option}"
    return prize_label, row.get(prize_label, "")


def format_prize_count(value: str) -> str:
    try:
        return f"{float(value):g}"
    except ValueError:
        return "0"


def get_selected_nums(nums: list[int]) -> list[int]:
    validate_query_range()
    return [num for num in nums if BIRTHDAY_NUM_MIN <= num <= BIRTHDAY_NUM_MAX]


def find_recent_100_draws_with_birthday_nums(
    csv_path: Path = M6_CSV,
    match_mode: str = BIRTHDAY_NUM_MATCH_MODE,
    prize_option: int = PRIZE_OPTION,
) -> list[MatchedDraw]:
    rows = read_m6_lotto_history(csv_path)
    recent_rows = rows[-RECENT_DRAW_COUNT:]
    matched_rows: list[MatchedDraw] = []

    for row in recent_rows:
        nums = parse_draw_numbers(row)
        birthday_num_count = count_birthday_nums(nums)
        if is_target_draw(nums, match_mode=match_mode):
            prize_label, prize_count = get_prize_count(row, prize_option=prize_option)
            matched_rows.append(
                {
                    "date": row.get("nDdate", ""),
                    "nums": nums,
                    "birthday_num_count": birthday_num_count,
                    "prize_label": prize_label,
                    "prize_count": prize_count,
                }
            )

    return matched_rows


CombinationStat = tuple[tuple[int, ...], int]


def validate_combination_take_count() -> None:
    validate_query_range()
    available_count = BIRTHDAY_NUM_MAX - BIRTHDAY_NUM_MIN + 1
    if COMBINATION_TAKE_COUNT < 1 or COMBINATION_TAKE_COUNT > available_count:
        raise ValueError(
            f"COMBINATION_TAKE_COUNT 必須介乎 1 至 {available_count}，"
            f"目前是 {COMBINATION_TAKE_COUNT}"
        )


def build_combination_stats(rows: list[MatchedDraw]) -> list[CombinationStat]:
    validate_combination_take_count()
    numbers = range(BIRTHDAY_NUM_MIN, BIRTHDAY_NUM_MAX + 1)
    combinations = itertools.combinations(numbers, COMBINATION_TAKE_COUNT)
    selected_num_sets = [set(get_selected_nums(row["nums"])) for row in rows]

    stats: list[CombinationStat] = []
    for combo in combinations:
        combo_set = set(combo)
        hit_count = sum(1 for num_set in selected_num_sets if combo_set.issubset(num_set))
        stats.append((combo, hit_count))
    return stats


def print_result(rows: list[MatchedDraw]) -> None:
    prize_display = f"顯示 prize{PRIZE_OPTION} 注數" if SHOW_PRIZE_COUNT else "不顯示中獎注數"
    print(
        f"====== 最近 {RECENT_DRAW_COUNT} 期，"
        f"N1-N6 包含 {BIRTHDAY_NUM_MIN}-{BIRTHDAY_NUM_MAX} 號數量 "
        f"{BIRTHDAY_NUM_MATCH_MODE} {MIN_BIRTHDAY_NUM_COUNT}，"
        f"{prize_display} ======"
    )
    suffix = " /> 注數" if SHOW_PRIZE_COUNT else ""
    print(f"序號 日期 : {BIRTHDAY_NUM_MIN}-{BIRTHDAY_NUM_MAX}開獎號{suffix}")

    if not rows:
        print("沒有符合條件的期數。")
        return

    for idx, row in enumerate(rows, start=1):
        birthday_nums_text = ",".join(str(num) for num in get_selected_nums(row["nums"]))
        line = f"{idx:>3} {row['date']} : {birthday_nums_text}"
        if SHOW_PRIZE_COUNT:
            line += f" /> {format_prize_count(row['prize_count'])}"
        print(line)


def print_combination_stats(rows: list[MatchedDraw]) -> None:
    if not SHOW_COMBINATION_STATS:
        return

    validate_combination_take_count()
    total_group = len(
        list(
            itertools.combinations(
                range(BIRTHDAY_NUM_MIN, BIRTHDAY_NUM_MAX + 1),
                COMBINATION_TAKE_COUNT,
            )
        )
    )
    print()
    print(
        f"====== {BIRTHDAY_NUM_MIN}-{BIRTHDAY_NUM_MAX} 選 {COMBINATION_TAKE_COUNT} "
        f"組合核對統計，共 {total_group} 組 ======"
    )
    hit_stats = [
        (idx, combo, hit_count)
        for idx, (combo, hit_count) in enumerate(build_combination_stats(rows), start=1)
        if hit_count > 0
    ]

    if not hit_stats:
        print("沒有命中的組合。")
        return

    for idx, combo, hit_count in hit_stats:
        combo_text = ",".join(str(num) for num in combo)
        print(f"{idx:>4}. {combo_text}, -----> {hit_count}")
        



def main() -> None:
    matched_rows = find_recent_100_draws_with_birthday_nums()
    print_result(matched_rows)
    print_combination_stats(matched_rows)


if __name__ == "__main__":
    main()
