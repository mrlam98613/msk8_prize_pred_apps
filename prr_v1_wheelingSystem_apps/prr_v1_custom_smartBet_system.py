import itertools
import random
import re
import unicodedata
from typing import TypedDict

'''
用戶自選智慧 1 or 2 膽拖 12 配腳 ，投注系統

1,[4,5,10,11]
2,[8,9,10,11]
3,[1,3,10,12]
4,[2,9,10,12]
5,[1,4,9,10]
6,[2,3,6,10]
7,[3,5,7,11]
8,[4,7,8,10]
9,[5,6,8,10]
10,[1,6,11,12]
11,[3,8,11,12]
12,[6,7,11,12]
13,[1,2,7,11]
14,[2,4,6,11]
15,[3,5,9,11]
16,[1,2,5,12]
17,[1,2,8,12]
18,[4,5,6,12]
19,[4,7,9,12]
20,[1,2,6,7]
21,[1,3,4,8]
22,[1,3,6,9]
23,[1,5,7,8]
24,[2,3,4,7]
25,[2,5,8,9]
26,[6,7,8,9]

'''

class OptionMenuItem(TypedDict):
    option_no: int
    mode_name: str
    ticket_size: int
    bet_unit: int
    unit_count: int
    drag_take_count: int
    match_if: int
    guarantee: int


class CalculatedOption(OptionMenuItem):
    tickets: list[tuple[int, ...]]
    uncovered_subsets: set[tuple[int, ...]]
    cost: int


# 膽可輸入 1 或 2 個，合共候選固定 12 個。
TOTAL_NUM_COUNT = 12

# 每個 tuple = (合共候選號中命中幾個, 保證至少一注中幾個號)。
GUARANTEE_OPTIONS = [
    (5, 5),
    (4, 4),
    (4, 3),
]

BET_MODES = [
    {
        "mode_name": "6字單式",
        "ticket_size": 6,
        "bet_unit": 10,
        "unit_count": 1,
    },
    {
        "mode_name": "7字複式",
        "ticket_size": 7,
        "bet_unit": 5,
        "unit_count": 7,
    },
]


def parse_number_list(raw_text: str) -> list[int]:
    """解析輸入文字中的所有整數號碼。"""
    cleaned_text = unicodedata.normalize("NFKC", raw_text)
    return sorted(set(int(text) for text in re.findall(r"\d+", cleaned_text)))


def input_numbers(prompt: str, min_count: int, max_count: int) -> list[int]:
    """輸入指定數量範圍的號碼。"""
    while True:
        try:
            raw_text = input(prompt).strip()
            numbers = parse_number_list(raw_text)
            if len(numbers) < min_count or len(numbers) > max_count:
                if min_count == max_count:
                    print(f"錯誤：必須輸入 {min_count} 個不同號碼，目前是 {len(numbers)} 個。\n")
                else:
                    print(f"錯誤：必須輸入 {min_count}-{max_count} 個不同號碼，目前是 {len(numbers)} 個。\n")
                continue
            return numbers
        except ValueError:
            print("錯誤：請輸入整數號碼。\n")


def input_custom_numbers() -> tuple[list[int], list[int]]:
    """輸入 1 或 2 個自選固定號碼，並自動要求補足至合共 12 個號碼。"""
    fixed_nums = input_numbers("請輸入 1 或 2 個自選固定號碼（膽）：", 1, 2)
    drag_num_count = TOTAL_NUM_COUNT - len(fixed_nums)
    while True:
        drag_nums = input_numbers(f"請輸入 {drag_num_count} 個候選補號（拖）：", drag_num_count, drag_num_count)
        overlap = sorted(set(fixed_nums) & set(drag_nums))
        if overlap:
            print(f"錯誤：固定號碼和補號不可重複，重複號碼：{overlap}\n")
            continue
        print()
        print(f"固定號碼：{fixed_nums} = 你選了 {len(fixed_nums)} 個膽")
        print(f"候選補號：{drag_nums} = 你選了 {len(drag_nums)} 個拖")
        print(f"合共號碼：{sorted(fixed_nums + drag_nums)} = {len(fixed_nums + drag_nums)} 個號碼\n")
        return fixed_nums, drag_nums


def input_max_tickets_limit() -> int | None:
    """輸入注數上限。"""
    while True:
        raw_text = input("每個方案最多計算多少注？直接 Enter = 不限制：").strip()
        if not raw_text:
            return None
        try:
            limit = int(raw_text)
        except ValueError:
            print("錯誤：請輸入整數。\n")
            continue
        if limit <= 0:
            print("錯誤：注數上限必須大於 0。\n")
            continue
        return limit


def build_all_custom_tickets(fixed_nums: list[int], drag_nums: list[int], drag_take_count: int) -> list[tuple[int, ...]]:
    """生成所有 膽 + N 拖的投注組合。"""
    tickets: list[tuple[int, ...]] = []
    for drag_part in itertools.combinations(drag_nums, drag_take_count):
        tickets.append(tuple(sorted(fixed_nums + list(drag_part))))
    return tickets


def ticket_covers_subset(ticket: tuple[int, ...], subset: tuple[int, ...], guarantee: int) -> bool:
    """判斷單注是否覆蓋指定中獎子集。"""
    return len(set(ticket) & set(subset)) >= guarantee


def build_cover_sets(
    all_possible_tickets: list[tuple[int, ...]],
    all_subsets: list[tuple[int, ...]],
    guarantee: int,
) -> list[set[tuple[int, ...]]]:
    """預先計算每注可覆蓋哪些中獎子集。"""
    if not all_subsets:
        return [set() for _ in all_possible_tickets]

    match_if = len(all_subsets[0])
    chosen_numbers = sorted(set(num for subset in all_subsets for num in subset))
    all_subset_set = set(all_subsets)
    cover_sets: list[set[tuple[int, ...]]] = []

    for ticket in all_possible_tickets:
        covered: set[tuple[int, ...]] = set()
        for guaranteed_part in itertools.combinations(ticket, guarantee):
            remaining_count = match_if - guarantee
            if remaining_count == 0:
                subset = tuple(sorted(guaranteed_part))
                if subset in all_subset_set:
                    covered.add(subset)
                continue
            possible_rest = [num for num in chosen_numbers if num not in set(guaranteed_part)]
            for rest in itertools.combinations(possible_rest, remaining_count):
                subset = tuple(sorted(guaranteed_part + rest))
                if subset in all_subset_set:
                    covered.add(subset)
        cover_sets.append(covered)
    return cover_sets


def generate_custom_wheel(
    fixed_nums: list[int],
    drag_nums: list[int],
    match_if: int,
    guarantee: int,
    max_limit: int | None,
    drag_take_count: int,
) -> tuple[list[tuple[int, ...]], set[tuple[int, ...]]]:
    """用 膽 + N 拖的可用注單，生成符合保證條件的組合。"""
    chosen_numbers = sorted(fixed_nums + drag_nums)
    all_possible_tickets = build_all_custom_tickets(fixed_nums, drag_nums, drag_take_count)
    all_subsets = list(itertools.combinations(chosen_numbers, match_if))
    uncovered_subsets = set(all_subsets)
    selected_tickets: list[tuple[int, ...]] = []
    cover_sets = build_cover_sets(all_possible_tickets, all_subsets, guarantee)
    remaining_ticket_indexes = set(range(len(all_possible_tickets)))
    limit = float("inf") if max_limit is None else max_limit

    while uncovered_subsets and remaining_ticket_indexes:
        if len(selected_tickets) >= limit:
            break

        best_index = None
        max_covered = -1
        for ticket_index in remaining_ticket_indexes:
            covered_count = len(cover_sets[ticket_index] & uncovered_subsets)
            if covered_count > max_covered:
                max_covered = covered_count
                best_index = ticket_index

        if best_index is None or max_covered <= 0:
            break

        selected_tickets.append(all_possible_tickets[best_index])
        remaining_ticket_indexes.remove(best_index)
        uncovered_subsets -= cover_sets[best_index]

    return selected_tickets, uncovered_subsets


def calculate_option_results(fixed_nums: list[int], drag_nums: list[int], max_limit: int | None) -> list[CalculatedOption]:
    """計算 6 字單式與 7 字複式的保證方案摘要。"""
    results: list[CalculatedOption] = []
    option_no = 1
    fixed_count = len(fixed_nums)
    for mode in BET_MODES:
        ticket_size = int(mode["ticket_size"])
        drag_take_count = ticket_size - fixed_count
        if drag_take_count < 0 or drag_take_count > len(drag_nums):
            continue

        for match_if, guarantee in GUARANTEE_OPTIONS:
            tickets, uncovered_subsets = generate_custom_wheel(
                fixed_nums=fixed_nums,
                drag_nums=drag_nums,
                match_if=match_if,
                guarantee=guarantee,
                max_limit=max_limit,
                drag_take_count=drag_take_count,
            )
            bet_unit = int(mode["bet_unit"])
            unit_count = int(mode["unit_count"])
            cost = len(tickets) * bet_unit * unit_count
            results.append(
                {
                    "option_no": option_no,
                    "mode_name": f"{fixed_count}膽+{drag_take_count}拖 {mode['mode_name']}",
                    "ticket_size": ticket_size,
                    "bet_unit": bet_unit,
                    "unit_count": unit_count,
                    "drag_take_count": drag_take_count,
                    "match_if": match_if,
                    "guarantee": guarantee,
                    "tickets": tickets,
                    "uncovered_subsets": uncovered_subsets,
                    "cost": cost,
                }
            )
            option_no += 1
    return results


def print_option_summary(option_results: list[CalculatedOption]) -> None:
    """打印所有方案注數和成本摘要。"""
    print("\n===== 方案摘要 =====")
    has_uncovered = False
    for result in option_results:
        unit_cost = result["bet_unit"] * result["unit_count"]
        uncovered_count = len(result["uncovered_subsets"])
        has_uncovered = has_uncovered or uncovered_count > 0
        status = "完全覆蓋" if uncovered_count == 0 else f"未覆蓋 {uncovered_count} 組"
        print(
            f"{result['option_no']}. {result['mode_name']}，"
            f"中{result['match_if']}保{result['guarantee']} = "
            f"{len(result['tickets'])} 組，"
            f"${unit_cost} x {len(result['tickets'])} = ${result['cost']:,}，"
            f"{status}"
        )
    if has_uncovered:
        print("註解：未覆蓋，因為系統只計算配腳的組合公式")


def input_selected_option(option_results: list[CalculatedOption]) -> CalculatedOption:
    """讓用戶選擇要顯示明細的方案。"""
    valid_options = {result["option_no"]: result for result in option_results}
    while True:
        raw_text = input("\n請選擇要顯示明細的方案編號：").strip()
        try:
            option_no = int(raw_text)
        except ValueError:
            print("錯誤：請輸入方案編號。")
            continue
        if option_no not in valid_options:
            print("錯誤：沒有此方案編號。")
            continue
        return valid_options[option_no]


def print_ticket_details(result: CalculatedOption) -> None:
    """打印投注組合明細。"""
    tickets = result["tickets"]
    uncovered_subsets = result["uncovered_subsets"]
    print(
        f"\n===== 方案 {result['option_no']} 明細：{result['mode_name']}，"
        f"中{result['match_if']}保{result['guarantee']} ====="
    )
    print(f"投注組數：{len(tickets)}")
    print(f"總成本：${result['cost']:,}")
    if uncovered_subsets:
        print(f"狀態：未完全覆蓋，尚有 {len(uncovered_subsets)} 組未覆蓋")
    else:
        print("狀態：完全覆蓋")
    print("-" * 52)
    for index, ticket in enumerate(tickets, 1):
        formatted_ticket = ", ".join(f"{num:02d}" for num in ticket)
        print(f"第 {index:03d} 組 -> [ {formatted_ticket} ]")
    print("-" * 52)


def format_nums(nums: list[int] | tuple[int, ...]) -> str:
    """格式化號碼列表。"""
    return "[" + ",".join(f"{num:02d}" for num in nums) + "]"


def find_winning_tickets(
    tickets: list[tuple[int, ...]],
    draw_nums: tuple[int, ...],
    guarantee: int,
) -> list[tuple[int, tuple[int, ...], tuple[int, ...]]]:
    """找出命中指定保證球數的投注組合。"""
    draw_set = set(draw_nums)
    winning_tickets: list[tuple[int, tuple[int, ...], tuple[int, ...]]] = []
    for index, ticket in enumerate(tickets, start=1):
        hits = tuple(num for num in ticket if num in draw_set)
        if len(hits) >= guarantee:
            winning_tickets.append((index, ticket, hits))
    return winning_tickets


def print_random_cover_test(
    fixed_nums: list[int],
    drag_nums: list[int],
    result: CalculatedOption,
    test_count: int = 3,
) -> None:
    """用 1/2 膽 + 拖腳隨機核對，顯示膽與配腳命中分佈。"""
    tickets = result["tickets"]
    match_if = result["match_if"]
    guarantee = result["guarantee"]
    chosen_numbers = sorted(fixed_nums + drag_nums)
    fixed_set = set(fixed_nums)
    drag_set = set(drag_nums)

    print(f"\n-- 隨機核對驗證：每次隨機開出 {match_if} 球，保中 {guarantee} 球")
    print("核對說明：顯示 中膽 + 中拖，例如 中2膽 + 中2拖 = 合共4球")
    for test_index in range(1, test_count + 1):
        if test_index > 1:
            print("-" * 52)
        draw_nums = tuple(sorted(random.sample(chosen_numbers, match_if)))
        fixed_hits = tuple(num for num in draw_nums if num in fixed_set)
        drag_hits = tuple(num for num in draw_nums if num in drag_set)
        winning_tickets = find_winning_tickets(tickets, draw_nums, guarantee)
        print(
            f"第 {test_index} 組隨機開出 {match_if} 球：{format_nums(draw_nums)}，"
            f"中{len(fixed_hits)}膽 {format_nums(fixed_hits)} + "
            f"中{len(drag_hits)}拖 {format_nums(drag_hits)}"
        )
        if not winning_tickets:
            print("沒有注單命中保證條件")
            continue
        for ticket_index, ticket, hits in winning_tickets:
            print(f"第 {ticket_index:03d} 組：{format_nums(ticket)}，中 {format_nums(hits)}")


def main() -> None:
    """主流程：輸入 1/2 膽並補足 12 個號碼，查詢方案，再選項顯示明細。"""
    print("=========================================")
    print("   Custom Smart Bet System：1/2膽 + 補足12球")
    print("=========================================\n")

    fixed_nums, drag_nums = input_custom_numbers()
    max_limit = input_max_tickets_limit()
    print("正在計算方案注數和成本，請稍候...")
    option_results = calculate_option_results(fixed_nums, drag_nums, max_limit)
    print_option_summary(option_results)
    selected_result = input_selected_option(option_results)
    print_ticket_details(selected_result)
    print_random_cover_test(fixed_nums, drag_nums, selected_result)


if __name__ == "__main__":
    main()
