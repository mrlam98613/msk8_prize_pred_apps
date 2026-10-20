import itertools
import random
import unicodedata
from typing import Optional, TypedDict, Union
'''
===== 方案摘要 =====
1. 6字單式，中5保5 = 726 組，$10 x 726 = $7,260，完全覆蓋
2. 6字單式，中4保4 = 145 組，$10 x 145 = $1,450，完全覆蓋
3. 6字單式，中4保3 = 17 組，$10 x 17 = $170，完全覆蓋
4. 7字複式，中5保5 = 254 組，$35 x 254 = $8,890，完全覆蓋
5. 7字複式，中4保4 = 63 組，$35 x 63 = $2,205，完全覆蓋
6. 7字複式，中4保3 = 10 組，$35 x 10 = $350，完全覆蓋
'''


class BetMode(TypedDict):
    name: str
    ticket_size: int
    bet_unit: int
    unit_count: int


class OptionMenuItem(TypedDict):
    option_no: int
    mode_key: str
    mode_name: str
    ticket_size: int
    bet_unit: int
    unit_count: int
    match_if: int
    guarantee: int


class CalculatedOption(OptionMenuItem):
    tickets: list[tuple[int, ...]]
    uncovered_subsets: set[tuple[int, ...]]
    cost: int


# ===== 預設方案 =====
# 每個 tuple = (中幾個候選號, 保證至少一注中幾個號)。
GUARANTEE_OPTIONS = [
    (5, 5),
    (4, 4),
    (4, 3),
]


BET_MODES: dict[str, BetMode] = {
    "6": {
        "name": "6字單式",
        "ticket_size": 6,
        "bet_unit": 10,
        "unit_count": 1,
    },
    "7": {
        "name": "7字複式",
        "ticket_size": 7,
        "bet_unit": 5,
        "unit_count": 7,
    },
}


# 候選球池允許的號碼數量範圍。
MIN_CANDIDATE_COUNT = 8
MAX_CANDIDATE_COUNT = 25


def parse_number_list(raw_text: str) -> list[int]:
    """解析半形/全形逗號、頓號或空格分隔的號碼。"""
    cleaned_text = unicodedata.normalize("NFKC", raw_text)
    for separator in [",", "，", "、", ";", "；"]:
        cleaned_text = cleaned_text.replace(separator, " ")
    return sorted(set(int(text) for text in cleaned_text.split() if text.strip()))


def input_candidate_numbers() -> list[int]:
    """輸入指定數量範圍內的候選號碼。"""
    while True:
        try:
            raw_text = input(
                f"請輸入候選號碼 {MIN_CANDIDATE_COUNT}-{MAX_CANDIDATE_COUNT} 個（逗號或空格分隔）："
            ).strip()
            numbers = parse_number_list(raw_text)
            if len(numbers) < MIN_CANDIDATE_COUNT or len(numbers) > MAX_CANDIDATE_COUNT:
                print(
                    f"錯誤：候選號碼數量必須是 {MIN_CANDIDATE_COUNT}-{MAX_CANDIDATE_COUNT} 個，"
                    f"目前是 {len(numbers)} 個。\n"
                )
                continue
            print(f"候選號碼：{numbers} = 你選了 {len(numbers)} 個號碼\n")
            return numbers
        except ValueError:
            print("錯誤：請輸入整數號碼。\n")


def input_max_tickets_limit() -> Optional[int]:
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
        ticket_set = set(ticket)
        outside_nums = [num for num in chosen_numbers if num not in ticket_set]
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


def generate_abbreviated_wheel(
    chosen_numbers: list[int],
    match_if: int,
    guarantee: int,
    max_limit: Optional[int],
    ticket_size: int,
) -> tuple[list[tuple[int, ...]], set[tuple[int, ...]]]:
    """用確定性貪婪法生成 wheeling 組合。"""
    all_possible_tickets = list(itertools.combinations(chosen_numbers, ticket_size))
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


def validate_option(mode_key: str, match_if: int, guarantee: int) -> bool:
    """檢查方案是否適用於投注模式。"""
    ticket_size = BET_MODES[mode_key]["ticket_size"]
    return guarantee <= match_if <= ticket_size


def calculate_option_results(chosen_numbers: list[int], max_limit: Optional[int]) -> list[CalculatedOption]:
    """計算 6 字單式與 7 字複式的方案摘要。"""
    results: list[CalculatedOption] = []
    option_no = 1
    for mode_key, mode in BET_MODES.items():
        ticket_size = int(mode["ticket_size"])
        bet_unit = int(mode["bet_unit"])
        unit_count = int(mode["unit_count"])
        for match_if, guarantee in GUARANTEE_OPTIONS:
            if not validate_option(mode_key, match_if, guarantee):
                continue

            tickets, uncovered_subsets = generate_abbreviated_wheel(
                chosen_numbers=chosen_numbers,
                match_if=match_if,
                guarantee=guarantee,
                max_limit=max_limit,
                ticket_size=ticket_size,
            )
            cost = len(tickets) * bet_unit * unit_count
            results.append(
                {
                    "option_no": option_no,
                    "mode_key": mode_key,
                    "mode_name": mode["name"],
                    "ticket_size": ticket_size,
                    "bet_unit": bet_unit,
                    "unit_count": unit_count,
                    "match_if": match_if,
                    "guarantee": guarantee,
                    "tickets": tickets,
                    "uncovered_subsets": uncovered_subsets,
                    "cost": cost,
                }
            )
            option_no += 1
    return results


def build_option_menu() -> list[OptionMenuItem]:
    """建立未計算前的方案選單。"""
    options: list[OptionMenuItem] = []
    option_no = 1
    for mode_key, mode in BET_MODES.items():
        for match_if, guarantee in GUARANTEE_OPTIONS:
            if not validate_option(mode_key, match_if, guarantee):
                continue
            options.append(
                {
                    "option_no": option_no,
                    "mode_key": mode_key,
                    "mode_name": mode["name"],
                    "ticket_size": mode["ticket_size"],
                    "bet_unit": mode["bet_unit"],
                    "unit_count": mode["unit_count"],
                    "match_if": match_if,
                    "guarantee": guarantee,
                }
            )
            option_no += 1
    return options


def print_option_summary(option_results: list[CalculatedOption]) -> None:
    """打印所有方案注數和成本摘要。"""
    print("\n===== 方案摘要 =====")
    for result in option_results:
        unit_cost = result["bet_unit"] * result["unit_count"]
        uncovered_count = len(result["uncovered_subsets"])
        status = "完全覆蓋" if uncovered_count == 0 else f"未覆蓋 {uncovered_count} 組"
        print(
            f"{result['option_no']}. {result['mode_name']}，"
            f"中{result['match_if']}保{result['guarantee']} = "
            f"{len(result['tickets'])} 組，"
            f"${unit_cost} x {len(result['tickets'])} = ${result['cost']:,}，"
            f"{status}"
        )


def input_selected_option(option_results: list[CalculatedOption]) -> CalculatedOption:
    """讓用戶選擇要計算和打印明細的方案。"""
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


def calculate_selected_option(
    chosen_numbers: list[int],
    selected_option: OptionMenuItem,
    max_limit: Optional[int],
) -> CalculatedOption:
    """只計算用戶選中的方案。"""
    tickets, uncovered_subsets = generate_abbreviated_wheel(
        chosen_numbers=chosen_numbers,
        match_if=selected_option["match_if"],
        guarantee=selected_option["guarantee"],
        max_limit=max_limit,
        ticket_size=selected_option["ticket_size"],
    )
    cost = len(tickets) * selected_option["bet_unit"] * selected_option["unit_count"]
    return {
        **selected_option,
        "tickets": tickets,
        "uncovered_subsets": uncovered_subsets,
        "cost": cost,
    }


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
    if isinstance(uncovered_subsets, set) and uncovered_subsets:
        print(f"狀態：未完全覆蓋，尚有 {len(uncovered_subsets)} 組未覆蓋")
    else:
        print("狀態：完全覆蓋")
    print("-" * 52)
    for index, ticket in enumerate(tickets, 1):
        formatted_ticket = ", ".join(f"{num:02d}" for num in ticket)
        print(f"第 {index:03d} 組 -> [ {formatted_ticket} ]")
    print("-" * 52)


def format_nums(nums: Union[list[int], tuple[int, ...]]) -> str:
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
    chosen_numbers: list[int],
    result: CalculatedOption,
    test_count: int = 3,
) -> None:
    """用候選號隨機開出 match_if 球，核對是否保中 guarantee 球。"""
    tickets = result["tickets"]
    match_if = result["match_if"]
    guarantee = result["guarantee"]
    print(f"\n-- 隨機核對驗證：每次隨機開出 {match_if} 球，保中 {guarantee} 球")
    for test_index in range(1, test_count + 1):
        draw_nums = tuple(sorted(random.sample(chosen_numbers, match_if)))
        winning_tickets = find_winning_tickets(tickets, draw_nums, guarantee)
        if not winning_tickets:
            continue
        for ticket_index, ticket, hits in winning_tickets:
            print(f"第 {ticket_index:03d} 組：{format_nums(ticket)}，中 {format_nums(hits)}")


def main() -> None:
    """主流程：先查詢，再選項，最後顯示投注組合明細。"""
    print("=========================================")
    print("   Smart Bet Wheeling System")
    print("=========================================\n")

    chosen_numbers = input_candidate_numbers()
    max_limit = input_max_tickets_limit()
    print("正在計算 1-6 方案注數和成本，請稍候...")
    option_results = calculate_option_results(chosen_numbers, max_limit)
    print_option_summary(option_results)
    selected_result = input_selected_option(option_results)
    print_ticket_details(selected_result)
    print_random_cover_test(chosen_numbers, selected_result)


if __name__ == "__main__":
    main()
