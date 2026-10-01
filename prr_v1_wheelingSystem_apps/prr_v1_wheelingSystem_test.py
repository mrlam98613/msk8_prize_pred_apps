import itertools


# ===== 手動參數區 =====
# 8-17 個候選號碼。
CHOSEN_NUMBERS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17]

# 每注幾個號碼；六合彩正碼測試常用 6，7 字複式測試可改 7。
TICKET_SIZE = 6

# 系統先計算以下方案，再由 SELECT_OPTION 選擇打印投注組合明細。
# 例：(5, 5) = 中 5 保 5，(4, 4) = 中 4 保 4，(4, 3) = 中 4 保 3。
GUARANTEE_OPTIONS = [
    (5, 5),
    (4, 4),
    (4, 3),
]
SELECT_OPTION = 3

# 每個方案最多生成多少注；None 表示不限制。
MAX_TICKETS_LIMIT: int | None = None

# 是否使用互動輸入；False 時直接使用以上參數。
USE_INPUT_MODE = False


def get_user_numbers():
    """1. 引導使用者輸入挑選的號碼（嚴格限制 8 ~ 17 個）"""
    while True:
        try:
            print("👉 【參數 1】請輸入您想旋轉的號碼（數量限定 8 ~ 17 個）")
            user_input = input("可以用逗號或空格隔開：")
            cleaned_input = user_input.replace(",", " ")
            numbers = sorted(list(set([int(n) for n in cleaned_input.split() if n.strip()])))
            
            num_count = len(numbers)
            if num_count < 8 or num_count > 17:
                print(f"❌ 錯誤：您選擇了 {num_count} 個號碼。數量必須在 8 到 17 個之間！\n")
                continue
                
            print(f"✅ 輸入成功！您選擇了 {num_count} 個號碼：{numbers}\n")
            return numbers
        except ValueError:
            print("❌ 錯誤：請輸入正確的數字格式（整數）！\n")

def get_guarantee_params(num_count):
    """2. 設定保證中獎條件（如：中 4 保 3）"""
    print("👉 【參數 2】請設定縮水矩陣的保證條件")
    while True:
        try:
            match_if = int(input("・如果開出的 6 個正碼中，中了幾個您的選號？(通常填 4 或 5)：") or 4)
            guarantee = int(input("・您保證至少要中幾個號碼的獎？(通常填 3 或 4)：") or 3)
            
            if guarantee > match_if or match_if > 6:
                print(f"❌ 參數錯誤：『保證中獎數({guarantee})』不能大於『中獎選號數({match_if})』，且不能大於 6。\n")
                continue
            return match_if, guarantee
        except ValueError:
            print("❌ 請輸入整數數字。\n")

def get_max_tickets_limit():
    """3. 設定能接受投注的最多注數"""
    while True:
        try:
            limit = input("👉 【參數 3】請問您最多能接受投注幾多注的組合？(直接斷行/回車代表不限制)：").strip()
            if not limit:
                return float('inf') # 不設限制
            limit_int = int(limit)
            if limit_int <= 0:
                print("❌ 限制注數必須大於 0。\n")
                continue
            return limit_int
        except ValueError:
            print("❌ 請輸入正確的整數注數。\n")

def ticket_covers_subset(ticket: tuple[int, ...], subset: tuple[int, ...], guarantee: int) -> bool:
    """判斷單注是否覆蓋指定中獎子集。"""
    return len(set(ticket) & set(subset)) >= guarantee


def build_cover_sets(all_possible_tickets, all_subsets, guarantee):
    """預先計算每注可覆蓋哪些中獎子集。"""
    cover_sets: list[set[tuple[int, ...]]] = []
    for ticket in all_possible_tickets:
        covered = {subset for subset in all_subsets if ticket_covers_subset(ticket, subset, guarantee)}
        cover_sets.append(covered)
    return cover_sets


def generate_abbreviated_wheel(chosen_numbers, match_if, guarantee, max_limit, ticket_size=6, verbose=True):
    """根據縮水條件與注數上限生成矩陣。"""
    if verbose:
        print("\n⏳ 正在為您優化計算旋轉矩陣，請稍候...")

    all_possible_tickets = list(itertools.combinations(chosen_numbers, ticket_size))
    all_subsets = list(itertools.combinations(chosen_numbers, match_if))
    selected_tickets = []
    uncovered_subsets = set(all_subsets)
    cover_sets = build_cover_sets(all_possible_tickets, all_subsets, guarantee)
    remaining_ticket_indexes = set(range(len(all_possible_tickets)))

    # 使用確定性貪婪演算法覆蓋。
    while uncovered_subsets and remaining_ticket_indexes:
        if len(selected_tickets) >= max_limit:
            if verbose:
                print(f"\n⚠️  提示：生成的注數已達到您設定的上限（{max_limit} 注），程式已停止繼續生成。")
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

        best_ticket = all_possible_tickets[best_index]
        selected_tickets.append(best_ticket)
        remaining_ticket_indexes.remove(best_index)
        uncovered_subsets -= cover_sets[best_index]

    return selected_tickets, uncovered_subsets


def validate_params(chosen_numbers, guarantee_options, selected_option, max_limit, ticket_size):
    """檢查手動參數是否可用。"""
    numbers = sorted(set(chosen_numbers))
    if len(numbers) < 8 or len(numbers) > 17:
        raise ValueError(f"CHOSEN_NUMBERS 必須是 8-17 個不同號碼，目前是 {len(numbers)} 個。")
    if selected_option < 1 or selected_option > len(guarantee_options):
        raise ValueError("SELECT_OPTION 必須在 GUARANTEE_OPTIONS 範圍內。")
    for match_if, guarantee in guarantee_options:
        if guarantee > match_if:
            raise ValueError("GUARANTEE 不能大於 MATCH_IF。")
        if match_if > ticket_size:
            raise ValueError("MATCH_IF 不能大於 TICKET_SIZE。")
    if ticket_size > len(numbers):
        raise ValueError("TICKET_SIZE 不能大於候選號碼數量。")
    if max_limit is not None and max_limit <= 0:
        raise ValueError("MAX_TICKETS_LIMIT 必須大於 0，或設為 None。")
    return numbers


def print_query_setting(chosen_numbers, guarantee_options, selected_option, max_limit, ticket_size):
    """打印本次 wheeling 設定。"""
    max_text = "不限制" if max_limit == float("inf") else f"{max_limit} 注"
    print("----- wheeling system 參數 -----")
    print(f"候選號碼：{chosen_numbers}")
    print(f"候選數量：{len(chosen_numbers)}")
    print(f"每注號碼數：{ticket_size}")
    print(f"方案選項：{', '.join(f'{idx}.中{match_if}保{guarantee}' for idx, (match_if, guarantee) in enumerate(guarantee_options, 1))}")
    print(f"明細方案：第 {selected_option} 項")
    print(f"注數上限：{max_text}")


def analyze_options(chosen_numbers, guarantee_options, max_limit, ticket_size):
    """計算各保證條件需要多少注。"""
    results = []
    for match_if, guarantee in guarantee_options:
        tickets, uncovered_subsets = generate_abbreviated_wheel(
            chosen_numbers,
            match_if,
            guarantee,
            max_limit,
            ticket_size,
            verbose=False,
        )
        results.append(
            {
                "match_if": match_if,
                "guarantee": guarantee,
                "tickets": tickets,
                "uncovered_subsets": uncovered_subsets,
            }
        )
    return results


def print_option_summary(option_results):
    """打印方案注數摘要。"""
    print("\n----- 保證條件方案摘要 -----")
    for idx, result in enumerate(option_results, 1):
        status = "完全覆蓋" if not result["uncovered_subsets"] else f"未覆蓋 {len(result['uncovered_subsets'])} 組"
        print(
            f"{idx}. 中{result['match_if']}，保{result['guarantee']} "
            f"= {len(result['tickets'])} 注，{status}"
        )


def print_ticket_details(tickets):
    """打印投注組合注明細。"""
    print("-" * 45)
    for idx, ticket in enumerate(tickets, 1):
        formatted_ticket = ", ".join(f"{num:02d}" for num in ticket)
        print(f"第 {idx:02d} 注 -> [ {formatted_ticket} ]")
    print("-" * 45)

# === 主程式 ===
def main():
    print("=========================================")
    print("   樂透旋轉矩陣生成器 (精準預算控制版)   ")
    print("=========================================\n")
    
    if USE_INPUT_MODE:
        # 參數 1：選號 (8-17個)
        my_numbers = get_user_numbers()
        # 參數 2：中 X 保 Y (例如中 4 保 3)
        match_if, guarantee = get_guarantee_params(len(my_numbers))
        # 參數 3：注數上限控制
        max_limit = get_max_tickets_limit()
        ticket_size = TICKET_SIZE
        guarantee_options = [(match_if, guarantee)]
        selected_option = 1
    else:
        my_numbers = validate_params(
            CHOSEN_NUMBERS,
            GUARANTEE_OPTIONS,
            SELECT_OPTION,
            MAX_TICKETS_LIMIT,
            TICKET_SIZE,
        )
        guarantee_options = GUARANTEE_OPTIONS
        selected_option = SELECT_OPTION
        max_limit = float("inf") if MAX_TICKETS_LIMIT is None else MAX_TICKETS_LIMIT
        ticket_size = TICKET_SIZE

    print_query_setting(my_numbers, guarantee_options, selected_option, max_limit, ticket_size)

    option_results = analyze_options(my_numbers, guarantee_options, max_limit, ticket_size)
    print_option_summary(option_results)

    selected_result = option_results[selected_option - 1]
    tickets = selected_result["tickets"]
    uncovered_subsets = selected_result["uncovered_subsets"]
    match_if = selected_result["match_if"]
    guarantee = selected_result["guarantee"]

    print(f"\n----- 第 {selected_option} 項投注組合明細：中 {match_if} 保 {guarantee} -----")
    print(f"最終總共：【 {len(tickets)} 】注")
    if uncovered_subsets:
        print(f"⚠️ 未完全覆蓋：尚有 {len(uncovered_subsets)} 組『中 {match_if}』情況未達保 {guarantee}。")
    else:
        print(f"✅ 已完全覆蓋：所有『中 {match_if}』情況都至少保 {guarantee}。")
    print_ticket_details(tickets)

if __name__ == "__main__":
    main()
