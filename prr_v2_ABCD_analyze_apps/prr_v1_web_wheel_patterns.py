import itertools
import random
import unicodedata
from typing import TypedDict

"""
網上 wheeling / 聰明組合樣版庫。

用途：
1. 保存已驗證的網上組合位置樣版。
2. 將用戶候選號碼套入位置組合。
3. 驗證中 N 保 M 是否完全覆蓋。
===== 網上 wheeling 樣版庫 =====
樣版編號 1：FreeEast 聰明組合4：9候選，12注，6字單式，中4保4，12 注，$10 x 12 = $120
樣版編號 2：FreeEast 聰明組合9：10候選，16注，6字單式，中6保5，16 注，$10 x 16 = $160
"""


class WheelPattern(TypedDict):
    code: str
    name: str
    candidate_count: int
    ticket_size: int
    match_if: int
    guarantee: int
    bet_unit: int
    unit_count: int
    patterns: list[tuple[int, ...]]


WHEEL_PATTERNS: dict[str, WheelPattern] = {
    "FREEEAST_9_12_4_6": {
        "code": "FREEEAST_9_12_4_6",
        "name": "FreeEast 聰明組合4：9候選，12注，6字單式，中4保4",
        "candidate_count": 9,
        "ticket_size": 6,
        "match_if": 4,
        "guarantee": 4,
        "bet_unit": 10,
        "unit_count": 1,
        "patterns": [
            (1, 2, 3, 4, 5, 6),
            (1, 2, 3, 7, 8, 9),
            (4, 5, 6, 7, 8, 9),
            (1, 2, 4, 5, 7, 8),
            (1, 3, 4, 6, 7, 9),
            (2, 3, 5, 6, 8, 9),
            (1, 2, 4, 6, 8, 9),
            (1, 3, 5, 6, 7, 8),
            (2, 3, 4, 5, 7, 9),
            (1, 2, 5, 6, 7, 9),
            (1, 3, 4, 5, 8, 9),
            (2, 3, 4, 6, 7, 8),
        ],
    },
    "FREEEAST_10_16_5_6": {
        "code": "FREEEAST_10_16_5_6",
        "name": "FreeEast 聰明組合9：10候選，16注，6字單式，中6保5",
        "candidate_count": 10,
        "ticket_size": 6,
        "match_if": 6,
        "guarantee": 5,
        "bet_unit": 10,
        "unit_count": 1,
        "patterns": [
            (1, 2, 3, 4, 5, 6),
            (1, 2, 3, 7, 8, 9),
            (1, 4, 5, 7, 8, 10),
            (2, 4, 6, 7, 9, 10),
            (3, 5, 6, 8, 9, 10),
            (1, 2, 3, 4, 8, 10),
            (1, 2, 5, 6, 7, 8),
            (1, 3, 4, 5, 7, 9),
            (2, 3, 5, 6, 7, 10),
            (2, 4, 5, 6, 8, 9),
            (1, 2, 5, 6, 9, 10),
            (1, 3, 4, 6, 7, 8),
            (1, 3, 6, 8, 9, 10),
            (2, 3, 4, 5, 7, 9),
            (2, 3, 7, 8, 9, 10),
            (1, 4, 5, 6, 8, 10),
        ],
    },
}


def parse_number_list(raw_text: str) -> list[int]:
    """解析半形/全形逗號、頓號或空格分隔的號碼。"""
    cleaned_text = unicodedata.normalize("NFKC", raw_text)
    for separator in [",", "，", "、", ";", "；"]:
        cleaned_text = cleaned_text.replace(separator, " ")
    return sorted(set(int(text) for text in cleaned_text.split() if text.strip()))


def format_nums(nums: list[int] | tuple[int, ...]) -> str:
    """格式化號碼列表。"""
    return "[" + ",".join(f"{num:02d}" for num in nums) + "]"


def list_patterns() -> None:
    """打印現有 wheeling 樣版。"""
    print("===== 網上 wheeling 樣版庫 =====")
    for index, pattern in enumerate(WHEEL_PATTERNS.values(), start=1):
        ticket_cost = pattern["bet_unit"] * pattern["unit_count"]
        total_cost = len(pattern["patterns"]) * ticket_cost
        print(
            f"樣版編號 {index}：{pattern['name']}，"
            f"{len(pattern['patterns'])} 注，"
            f"${ticket_cost} x {len(pattern['patterns'])} = ${total_cost:,}"
        )


def input_pattern() -> WheelPattern:
    """選擇一個 wheeling 樣版。"""
    patterns = list(WHEEL_PATTERNS.values())
    while True:
        raw_text = input("請選擇樣版編號：").strip()
        try:
            index = int(raw_text)
        except ValueError:
            print("錯誤：請輸入樣版編號。\n")
            continue
        if 1 <= index <= len(patterns):
            return patterns[index - 1]
        print("錯誤：沒有此樣版編號。\n")


def input_candidate_numbers(candidate_count: int) -> list[int]:
    """輸入指定數量的候選號碼。"""
    while True:
        try:
            raw_text = input(f"請輸入 {candidate_count} 個候選號碼：").strip()
            numbers = parse_number_list(raw_text)
        except ValueError:
            print("錯誤：請輸入整數號碼。\n")
            continue
        if len(numbers) != candidate_count:
            print(f"錯誤：必須輸入 {candidate_count} 個不同號碼，目前是 {len(numbers)} 個。\n")
            continue
        return numbers


def apply_patterns(candidate_numbers: list[int], patterns: list[tuple[int, ...]]) -> list[tuple[int, ...]]:
    """將位置組合套入實際候選號碼。"""
    tickets: list[tuple[int, ...]] = []
    for pattern in patterns:
        tickets.append(tuple(candidate_numbers[index - 1] for index in pattern))
    return tickets


def validate_cover(pattern: WheelPattern) -> tuple[bool, list[tuple[int, ...]]]:
    """驗證樣版是否符合中 N 保 M。"""
    candidate_positions = list(range(1, pattern["candidate_count"] + 1))
    all_match_subsets = list(itertools.combinations(candidate_positions, pattern["match_if"]))
    uncovered: list[tuple[int, ...]] = []

    for match_subset in all_match_subsets:
        match_set = set(match_subset)
        best_hit = max(len(match_set & set(ticket)) for ticket in pattern["patterns"])
        if best_hit < pattern["guarantee"]:
            uncovered.append(match_subset)

    return len(uncovered) == 0, uncovered


def print_pattern_detail(pattern: WheelPattern, candidate_numbers: list[int]) -> None:
    """打印樣版位置與實際投注組合。"""
    tickets = apply_patterns(candidate_numbers, pattern["patterns"])
    is_covered, uncovered = validate_cover(pattern)
    ticket_cost = pattern["bet_unit"] * pattern["unit_count"]
    total_cost = len(tickets) * ticket_cost
    status = "完全覆蓋" if is_covered else f"未覆蓋 {len(uncovered)} 組"

    print(f"\n===== {pattern['name']} =====")
    print(f"候選號碼：{format_nums(candidate_numbers)}")
    print(f"投注組數：{len(tickets)}")
    print(f"總成本：${ticket_cost} x {len(tickets)} = ${total_cost:,}")
    print(f"驗證：中{pattern['match_if']}保{pattern['guarantee']}，{status}")
    if uncovered:
        print(f"未覆蓋位置：{uncovered[:20]}")
    print("-" * 52)
    for index, (position_pattern, ticket) in enumerate(zip(pattern["patterns"], tickets), start=1):
        print(f"第 {index:02d} 注：位置 {format_nums(position_pattern)} -> {format_nums(ticket)}")
    print("-" * 52)


def find_winning_tickets(tickets: list[tuple[int, ...]], draw_nums: tuple[int, ...], guarantee: int) -> list[tuple[int, tuple[int, ...], tuple[int, ...]]]:
    """找出命中指定保證球數的投注注單。"""
    draw_set = set(draw_nums)
    winning_tickets: list[tuple[int, tuple[int, ...], tuple[int, ...]]] = []
    for index, ticket in enumerate(tickets, start=1):
        hits = tuple(num for num in ticket if num in draw_set)
        if len(hits) >= guarantee:
            winning_tickets.append((index, ticket, hits))
    return winning_tickets


def print_random_cover_test(pattern: WheelPattern, candidate_numbers: list[int], test_count: int = 3) -> None:
    """用候選球隨機抽出開出球，核對是否有注單命中保證條件。"""
    tickets = apply_patterns(candidate_numbers, pattern["patterns"])
    print(f"\n-- 隨機核對驗證：每次隨機開出 {pattern['match_if']} 球，保中 {pattern['guarantee']} 球")
    for test_index in range(1, test_count + 1):
        draw_nums = tuple(sorted(random.sample(candidate_numbers, pattern["match_if"])))
        winning_tickets = find_winning_tickets(tickets, draw_nums, pattern["guarantee"])
        print(f"第 {test_index} 組隨機開出 {pattern['match_if']} 球：{format_nums(draw_nums)}")
        if not winning_tickets:
            print("沒有注單命中保證條件")
            continue
        for ticket_index, ticket, hits in winning_tickets:
            print(f"第 {ticket_index:02d} 注：{format_nums(ticket)}，中 {format_nums(hits)}")


def main() -> None:
    """互動式查詢網上 wheeling 樣版。"""
    list_patterns()
    pattern = input_pattern()
    candidate_numbers = input_candidate_numbers(pattern["candidate_count"])
    print_pattern_detail(pattern, candidate_numbers)
    print_random_cover_test(pattern, candidate_numbers)


if __name__ == "__main__":
    main()
