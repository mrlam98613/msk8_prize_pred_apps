from pathlib import Path
import csv
import random


from typing import Optional
CURRENT_DIR = Path(__file__).resolve().parent
PRED_17_BALLS_CSV = CURRENT_DIR / "pred_17_balls.csv"

# A. 聰明組合位置配號
# 1. USE_RANDOM_PRED_17_BALLS=False：讀入 pred_17_balls.csv，假設 1-17 號配入 23 注組合。
# 2. USE_RANDOM_PRED_17_BALLS=True：由 NUM_MIN..NUM_MAX 隨機產生 RANDOM_NUM 個預測球。
USE_RANDOM_PRED_17_BALLS = False  # 是否隨機產生 17 個預測球
NUM_MIN = 10
NUM_MAX = 49
RANDOM_NUM = 17

# B. 核對開獎
# 1. USE_RANDOM_LUCKY_NUM=False：手動輸入 LOTTO_NUM，例如 [1,2,3,4] + [7]。
# 2. USE_RANDOM_LUCKY_NUM=True：由 LOTTO_NUM_MIN..LOTTO_NUM_MAX 隨機產生 6 個正號 + 1 個特號。
# 例：[1,2,3,4] + [7] = 4 個正號 + 特號 7；[1,2,3,4] + [0] = 4 個正號，沒有特號。
USE_RANDOM_LUCKY_NUM = False  # 是否隨機產生開獎號碼
LOTTO_NUM_MIN = 10
LOTTO_NUM_MAX = 49
LOTTO_NUM = [1, 2, 3, 4] + [7]

# 投注成本設定。
BET_UNIT = 5
BET_PER_MULTIPLE_7 = 7
MULTIPLE_SET_COUNT = 23

# $5 注固定派彩估算。1-3 獎用測試預設值，正式回測可另行讀 M6 平均派彩。
PRIZE_PAYOUTS = {
    "1": 4_000_000,
    "2": 500_000,
    "3": 40_000,
    "4": 4_800,
    "5": 320,
    "6": 160,
    "7": 20,
}
PRIZE_RULES = [
    ("1", 6, 0),
    ("2", 5, 1),
    ("3", 5, 0),
    ("4", 4, 1),
    ("5", 4, 0),
    ("6", 3, 1),
    ("7", 3, 0),
]


MULTIPLE_INDEX_PATTERNS = [
    (1, 2, 3, 4, 5, 6, 7),
    (1, 2, 3, 8, 9, 10, 11),
    (1, 2, 4, 12, 13, 14, 15),
    (1, 3, 5, 12, 13, 16, 17),
    (1, 4, 6, 8, 9, 16, 17),
    (1, 5, 7, 10, 11, 14, 15),
    (1, 6, 7, 8, 10, 12, 13),
    (2, 3, 6, 10, 11, 16, 17),
    (2, 4, 7, 8, 9, 14, 15),
    (2, 5, 7, 9, 11, 12, 16),
    (2, 5, 6, 13, 14, 15, 17),
    (3, 4, 5, 8, 9, 13, 17),
    (3, 4, 6, 11, 12, 14, 15),
    (3, 7, 9, 10, 13, 15, 16),
    (4, 7, 10, 11, 12, 16, 17),
    (5, 6, 8, 10, 12, 15, 17),
    (5, 6, 9, 11, 13, 14, 16),
    (1, 3, 9, 10, 14, 16, 17),
    (1, 4, 8, 11, 13, 15, 16),
    (2, 3, 7, 8, 12, 14, 17),
    (2, 6, 9, 10, 13, 15, 17),
    (3, 5, 8, 11, 12, 14, 16),
    (4, 6, 7, 9, 10, 12, 13),
]

''' 
23注7字複式號碼組合表：
第 1 注： 01, 02, 03, 04, 05, 06, 07
第 2 注： 01, 02, 03, 08, 09, 10, 11
第 3 注： 01, 02, 04, 12, 13, 14, 15
第 4 注： 01, 03, 05, 12, 13, 16, 17
第 5 注： 01, 04, 06, 08, 09, 16, 17

第 6 注： 01, 05, 07, 10, 11, 14, 15
第 7 注： 01, 06, 07, 08, 10, 12, 13
第 8 注： 02, 03, 06, 10, 11, 16, 17
第 9 注： 02, 04, 07, 08, 09, 14, 15
第 10 注： 02, 05, 07, 09, 11, 12, 16


第 11 注： 02, 05, 06, 13, 14, 15, 17
第 12 注： 03, 04, 05, 08, 09, 13, 17
第 13 注： 03, 04, 06, 11, 12, 14, 15
第 14 注： 03, 07, 09, 10, 13, 15, 16
第 15 注： 04, 07, 10, 11, 12, 16, 17

第 16 注： 05, 06, 08, 10, 12, 15, 17
第 17 注： 05, 06, 09, 11, 13, 14, 16
第 18 注： 01, 03, 09, 10, 14, 16, 17
第 19 注： 01, 04, 08, 11, 13, 15, 16
第 20 注： 02, 03, 07, 08, 12, 14, 17

第 21 注： 02, 06, 09, 10, 13, 15, 17
第 22 注： 03, 05, 08, 11, 12, 14, 16
第 23 注： 04, 06, 07, 09, 10, 12, 13


'''

def read_pred_17_balls(csv_path: Path = PRED_17_BALLS_CSV) -> list[int]:
    """讀入 pred_17_balls.csv 第一行 17 個候選球。"""
    if not csv_path.exists():
        raise FileNotFoundError(f"找不到 CSV：{csv_path}")

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        row = next(reader, None)

    if row is None:
        raise ValueError(f"CSV 沒有資料：{csv_path}")

    pred_17_balls = [int(row[f"P{index:02d}"]) for index in range(1, 18)]
    if len(set(pred_17_balls)) != 17:
        raise ValueError("pred_17_balls.csv 必須是 17 個不同號碼。")
    return pred_17_balls


def random_pred_balls() -> list[int]:
    """由手動範圍隨機抽出預測球，不使用 random seed。"""
    pool = list(range(NUM_MIN, NUM_MAX + 1))
    if RANDOM_NUM > len(pool):
        raise ValueError("RANDOM_NUM 不能大於可選號碼範圍。")
    return sorted(random.sample(pool, RANDOM_NUM))


def get_pred_17_balls() -> list[int]:
    """取得 17 個候選球：可隨機產生或讀入 CSV。"""
    if USE_RANDOM_PRED_17_BALLS:
        return random_pred_balls()
    return read_pred_17_balls()


def pred_source_text() -> str:
    """取得預測 17 球來源文字。"""
    if USE_RANDOM_PRED_17_BALLS:
        return f"random，選球範圍 {NUM_MIN}-{NUM_MAX}，隨機 {RANDOM_NUM} 球"
    return f"CSV：{PRED_17_BALLS_CSV.name}"


def lotto_source_text() -> str:
    """取得核對開獎來源文字。"""
    if USE_RANDOM_LUCKY_NUM:
        return f"random，開獎範圍 {LOTTO_NUM_MIN}-{LOTTO_NUM_MAX}，6 正號 + 1 特號"
    return f"手動 LOTTO_NUM = {format_list(LOTTO_NUM)}"


def build_multiple_tickets(pred_17_balls: list[int]) -> list[tuple[int, tuple[int, ...], tuple[int, ...]]]:
    """用 23 注聰明組合位置表，套入 17 個候選球。"""
    if len(pred_17_balls) != 17:
        raise ValueError("必須輸入 17 個候選球。")

    tickets: list[tuple[int, tuple[int, ...], tuple[int, ...]]] = []
    for ticket_no, pattern in enumerate(MULTIPLE_INDEX_PATTERNS, start=1):
        ticket = tuple(pred_17_balls[index - 1] for index in pattern)
        tickets.append((ticket_no, pattern, ticket))
    return tickets


def format_tuple(nums: tuple[int, ...]) -> str:
    """格式化 tuple 顯示。"""
    return "[" + ",".join(str(num) for num in nums) + "]"


def format_list(nums: list[int]) -> str:
    """格式化 list 顯示。"""
    return "[" + ",".join(str(num) for num in nums) + "]"


def build_lotto_num(pred_17_balls: list[int]) -> list[int]:
    """取得核對號碼，可手動輸入或由完整號碼範圍獨立隨機抽 6 正號 + 1 特號。"""
    if USE_RANDOM_LUCKY_NUM:
        full_pool = list(range(LOTTO_NUM_MIN, LOTTO_NUM_MAX + 1))
        random_nums = random.sample(full_pool, 7)
        return sorted(random_nums[:6]) + [random_nums[6]]
    return LOTTO_NUM


def split_lotto_num(lotto_num: list[int]) -> tuple[list[int], Optional[int]]:
    """將 lotto_num 拆成正號與特號；最後一個 0 代表沒有特號。"""
    clean_nums = [num for num in lotto_num if num is not None]
    if clean_nums and clean_nums[-1] == 0:
        clean_nums = sorted(clean_nums[:-1])
        special_num = None
    elif len(clean_nums) >= 7:
        special_num = clean_nums[6]
        clean_nums = sorted(clean_nums[:6])
    elif len(clean_nums) >= 4:
        special_num = clean_nums[-1]
        clean_nums = sorted(clean_nums[:-1])
    else:
        clean_nums = sorted(clean_nums)
        special_num = None

    if len(clean_nums) < 3:
        raise ValueError("LOTTO_NUM 最少要有 3 個正號，或用 [1,2,3,4] + [0] 表示無特號。")
    lotto_list = clean_nums
    return lotto_list, special_num


def safe_comb(n: int, r: int) -> int:
    """安全計算組合數。"""
    if r < 0 or r > n:
        return 0
    result = 1
    for value in range(1, r + 1):
        result = result * (n - value + 1) // value
    return result


def prize_counts_for_ticket(ticket: tuple[int, ...], lotto_list: list[int], special_num: Optional[int]) -> tuple[str, int]:
    """計算一組 7 字複式拆 7 注後，1-7 獎中獎注數及派彩。"""
    normal_hit = sum(1 for num in ticket if num in set(lotto_list))
    special_hit = 1 if special_num is not None and special_num in ticket else 0
    miss_count = len(ticket) - normal_hit - special_hit
    prize_parts: list[str] = []
    total_amount = 0

    for prize, req_normal, req_special in PRIZE_RULES:
        req_miss = 6 - req_normal - req_special
        if req_normal > normal_hit or req_special > special_hit or req_miss > miss_count:
            continue

        unit = safe_comb(normal_hit, req_normal) * safe_comb(special_hit, req_special) * safe_comb(miss_count, req_miss)
        if unit <= 0:
            continue
        prize_parts.append(f"{prize}獎={unit}注")
        total_amount += unit * PRIZE_PAYOUTS[prize]

    if prize_parts:
        return "，".join(prize_parts), total_amount
    return "沒有中獎", 0


def pred_hit_summary(pred_17_balls: list[int], lotto_list: list[int], special_num: Optional[int]) -> tuple[list[int], list[int], float]:
    """計算預測 17 球整體命中核對開獎號的球數。"""
    pred_set = set(pred_17_balls)
    normal_hits = [num for num in lotto_list if num in pred_set]
    special_hits = [special_num] if special_num is not None and special_num in pred_set else []
    hit_score = len(normal_hits) + (0.5 if special_hits else 0.0)
    return normal_hits, special_hits, hit_score


def print_pred_hit_summary(pred_17_balls: list[int], lotto_list: list[int], special_num: Optional[int]) -> None:
    """打印 C 部份：預測 17 球整體命中核對開獎號。"""
    pred_normal_hits, pred_special_hits, pred_hit_score = pred_hit_summary(pred_17_balls, lotto_list, special_num)
    print("C. 預測球包含核對開獎號")
    print(
        f"17球核對：命中 {format_list(pred_normal_hits)} + {format_list(pred_special_hits)} "
        f"= {pred_hit_score:g} 球"
    )


def print_multiple_tickets(pred_17_balls: list[int]) -> None:
    """打印 17 球套入 23 注聰明組合後的投注表。"""
    print("====== 17球套入23注聰明組合 ======")
    print("A. 聰明組合位置配號")
    print(f"預測17球來源：{pred_source_text()}")
    print(f"預測17球：{format_tuple(tuple(pred_17_balls))}")
    print()

    lotto_num = build_lotto_num(pred_17_balls)
    lotto_list, special_num = split_lotto_num(lotto_num)
    total_amount = 0
    hit_ticket_count = 0

    special_text = f"*{special_num}" if special_num is not None else "_"
    print("B. 核對開獎")
    print(f"核對來源：{lotto_source_text()}")
    print(f"核對7球：{format_list(lotto_num)}")
    print(f"核對正號：{format_list(lotto_list)}，特號：{special_text}")
    print()

    print_pred_hit_summary(pred_17_balls, lotto_list, special_num)
    print()

    print("----- 23 注核對明細 -----")
    print()

    for ticket_no, pattern, ticket in build_multiple_tickets(pred_17_balls):
        hits = [num for num in ticket if num in set(lotto_list)]
        special_hit = special_num is not None and special_num in ticket
        special_hits = [special_num] if special_hit and special_num is not None else []
        hit_count = len(hits)
        hit_score = hit_count + (0.5 if special_hit else 0)
        prize_text, amount = prize_counts_for_ticket(ticket, lotto_list, special_num)
        total_amount += amount
        if amount > 0:
            hit_ticket_count += 1

        line = (
            f"第 {ticket_no:2d} 注：位置 {format_tuple(pattern)} -> {format_tuple(ticket)}，"
            f"命中 {format_list(hits)} + {format_list(special_hits)} /> {hit_score:g} 球"
        )
        if hit_score >= 3:
            line += f" ==> {prize_text}，派彩 ${amount:,}"
        print(line)

    print()
    print("------------------------------")
    print_pred_hit_summary(pred_17_balls, lotto_list, special_num)
    print("----- 核對總結 -----")
    total_cost = BET_UNIT * BET_PER_MULTIPLE_7 * MULTIPLE_SET_COUNT
    profit = total_amount - total_cost
    profit_sign = "+" if profit > 0 else ""
    print(
        f"複式 {BET_UNIT}元注 x {BET_PER_MULTIPLE_7} 注 = {BET_UNIT * BET_PER_MULTIPLE_7} 元 "
        f"x {MULTIPLE_SET_COUNT}注"
    )
    print(f"總投注 = {total_cost:,} 元")
    print(f"中獎複式：{hit_ticket_count} 組")
    print(f"總派彩：${total_amount:,}")
    print(f"損益 = {profit_sign}{profit:,} 元")


def main() -> None:
    """主流程。"""
    pred_17_balls = get_pred_17_balls()
    print_multiple_tickets(pred_17_balls)


if __name__ == "__main__":
    main()
