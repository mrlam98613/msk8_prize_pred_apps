import pandas as pd 
from pathlib import Path
import res_func_num_convert_RBG_Dict
from collections import Counter
import random

import os

'''
項目名：3獎高頻中獎分析

分析思路：
1. 從 M6_lotto_history_prize.csv 讀入最近 BACKTEST_DRAW 期開獎及中獎紀錄。
2. 3獎分析只用 prize3 中獎注數排序。
3. 取 prize3 最大前 PRIZE3_TOP_DRAW 期。
4. 3獎 = 命中 5 個正號，所以特色分析只用 N1-N6 正號。
5. N7 特號只作次要參考，使用較低權重。
6. 另設 2獎模組：2獎 = 5 個正號 + 特號，只用 prize2 排序，獨立分析特號。
'''


# 取得目前檔案所在目錄
current_dir = Path(__file__).resolve().parent

PRIZE_CSV_DATA = current_dir.parent / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"
PRIZE_SUMMARY_DATA = current_dir.parent / "A_msk_lottery_data_folder" / "M4_lotto_prize_summary.csv"
PATTERN_BET_CSV = current_dir.parent / "msk_new_seed_apps" / "bet_data" / "pattern_bet.csv"

# 3獎高頻投注預測參數
BET_COUNT = 3  # 最多產生幾注單式投注組合。
USE_TOP_INTERVAL_PATTERN = 1  # 1-3 使用最高頻的前幾個 1-49 區間 pattern；越大越容易產生組合。
USE_TOP_RBG_PATTERN = 1  # 1-3 使用最高頻的前幾個 RBG pattern；越大越容易產生組合。
ENABLE_FEATURE_RULES = True  # 是否啟用特色條件：生日號、連號、同尾、10/20/30/40。
REQUIRE_HIGH_INTERVAL = True  # 推薦單式是否必須至少包含一個 3/4 高區間號碼，即 30-49。
FORCE_HIGH_INTERVAL_TEMPLATE = True  # 若區間 pattern 太低位，強制改成 [0,0,1,1,2,3或4]。
MAX_ATTEMPTS = 5000  # 隨機嘗試產生組合的最大次數，避免條件太嚴時無限執行。
RANDOM_SEED = 42  # 固定隨機種子；同一份資料會產生相同結果，設為 None 可每次不同。

# 3獎高頻分析參數
PRIZE3_TOP_DRAW = 6  # 從最近 BACKTEST_DRAW 期中，取 prize3 最大的前幾期分析。
PRIZE2_TOP_DRAW = 14  # 從最近 BACKTEST_DRAW 期中，取 prize2 最大的前幾期分析特號。
MAIN_NUM_WEIGHT = 1.0  # N1-N6 正號權重。
SPECIAL_NUM_WEIGHT = 0.3  # N7 特號次要權重。

def get_next_draw_info():
    """從 M4_lotto_prize_summary.csv 取得最新一筆下期開獎日期、星期、獎金。"""
    df_summary = pd.read_csv(
        PRIZE_SUMMARY_DATA,
        dtype={
            "next_draw_date": str,
            "week": int,
            "next_draw_prize_fund": float,
        },
    )
    if df_summary.empty:
        raise ValueError(f"找不到下期開獎日期資料：{PRIZE_SUMMARY_DATA}")

    latest = df_summary.iloc[-1]
    return {
        "bet_date": str(latest["next_draw_date"]),
        "week": int(latest["week"]),
        "prize_fund": float(latest["next_draw_prize_fund"]),
    }


def format_prize_fund(prize_fund):
    """將獎金格式化為 $ 13,000,000。"""
    return f"$ {int(prize_fund):,}"


def save_pattern_bets(bet_list, bet_date):
    """將 3獎高頻特色投注單式儲存到 pattern_bet.csv。"""
    rows = []
    for nums in bet_list:
        sorted_nums = sorted(int(num) for num in nums)
        if len(sorted_nums) != 6:
            continue
        rows.append({
            "bet_date": bet_date,
            "N1": sorted_nums[0],
            "N2": sorted_nums[1],
            "N3": sorted_nums[2],
            "N4": sorted_nums[3],
            "N5": sorted_nums[4],
            "N6": sorted_nums[5],
        })

    PATTERN_BET_CSV.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=["bet_date", "N1", "N2", "N3", "N4", "N5", "N6"]).to_csv(
        PATTERN_BET_CSV,
        index=False,
        encoding="utf-8-sig",
    )
    return PATTERN_BET_CSV


def get_consecutive_groups(nums):
    """找出連號組，例如 [2, 3]、[28, 29, 30]。"""
    sorted_nums = sorted(set(int(num) for num in nums))
    groups = []
    current_group = []

    for num in sorted_nums:
        if not current_group or num == current_group[-1] + 1:
            current_group.append(num)
        else:
            if len(current_group) >= 2:
                groups.append(current_group)
            current_group = [num]

    if len(current_group) >= 2:
        groups.append(current_group)

    return groups


def get_same_tail_groups(nums):
    """找出同尾組，例如 [7, 17, 27]。"""
    tail_map = {}
    for num in sorted(set(int(num) for num in nums)):
        tail_map.setdefault(num % 10, []).append(num)
    return {tail: group for tail, group in tail_map.items() if len(group) >= 2}


def format_frequency_groups(nums):
    """將號碼按出現次數分組，多次出現排前，單次出現合併在最後。"""
    num_counter = Counter(int(num) for num in nums)
    repeated_groups = [
        [num] * count
        for num, count in sorted(
            num_counter.items(),
            key=lambda item: (-item[1], item[0]),
        )
        if count >= 2
    ]
    single_group = sorted(num for num, count in num_counter.items() if count == 1)
    if single_group:
        repeated_groups.append(single_group)
    return repeated_groups


def get_num49_interval_map(lotto_list):
    """將號碼轉成 1-49 區間：0=1-9, 1=10-19, 2=20-29, 3=30-40, 4=41-49。"""
    interval_map = {
        0: list(range(1, 10)), #1-9
        1: list(range(10, 20)), #10-19
        2: list(range(20, 30)), #20-29
        3: list(range(30, 41)), #30-40
        4: list(range(41, 50)), #41-49
    }
    interval_idx = []
    for num in lotto_list:
        for interval_id, interval_nums in interval_map.items():
            if int(num) in interval_nums:
                interval_idx.append(interval_id)
                break
    return interval_idx


def get_rbg_pattern(nums):
    """回傳 R-B-G 數量 pattern，例如 2-3-2。"""
    rbg_dict = res_func_num_convert_RBG_Dict.res_List_To_rbg_Dict_func(nums)
    return f"{len(rbg_dict.get(0, []))}-{len(rbg_dict.get(1, []))}-{len(rbg_dict.get(2, []))}"


def get_interval_pattern(nums):
    """回傳區間 pattern，例如 0-1-1-2-4。"""
    return "-".join(str(interval_id) for interval_id in sorted(get_num49_interval_map(nums)))


def get_interval_group_dict():
    """回傳 1-49 區間分組。"""
    return {
        0: list(range(1, 10)),
        1: list(range(10, 20)),
        2: list(range(20, 30)),
        3: list(range(30, 41)),
        4: list(range(41, 50)),
    }


def parse_pattern(pattern):
    """將 '0-1-1-2-4' 轉成 [0,1,1,2,4]。"""
    return [int(item) for item in str(pattern).split("-") if item != ""]


def build_six_interval_pattern(interval_pattern, require_high_interval=False):
    """取得 6 個正號使用的區間 pattern；舊 7 號 pattern 會壓成 6 格。"""
    interval_ids = parse_pattern(interval_pattern)
    if len(interval_ids) <= 6:
        six_pattern = interval_ids
    else:
        counts = Counter(interval_ids)
        # 移除出現最多的其中一個區間，讓 pattern 從 7 格變成 6 格。
        remove_interval = counts.most_common(1)[0][0]
        six_pattern = list(interval_ids)
        six_pattern.remove(remove_interval)

    if require_high_interval and FORCE_HIGH_INTERVAL_TEMPLATE and not ({3, 4} & set(six_pattern)):
        six_pattern = [0, 0, 1, 1, 2, random.choice([3, 4])]

    return six_pattern


def build_six_rbg_pattern(rbg_pattern):
    """取得 6 個正號使用的 R-B-G pattern；舊 7 號 pattern 會壓成 6 格。"""
    counts = parse_pattern(rbg_pattern)
    if sum(counts) <= 6:
        return "-".join(str(count) for count in counts)

    max_idx = max(range(len(counts)), key=lambda idx: counts[idx])
    counts[max_idx] -= 1
    return "-".join(str(count) for count in counts)


def match_rbg_pattern(nums, rbg_pattern):
    """檢查號碼是否符合 R-B-G pattern。"""
    return get_rbg_pattern(nums) == build_six_rbg_pattern(rbg_pattern)


def match_feature_rules(nums):
    """特色條件：生日號偏多，或有連號/同尾/10,20,30,40。"""
    birthday_count = len([num for num in nums if 1 <= num <= 31])
    has_consecutive = bool(get_consecutive_groups(nums))
    has_same_tail = bool(get_same_tail_groups(nums))
    has_special = bool(set(nums) & {10, 20, 30, 40})
    return birthday_count >= 4 or has_consecutive or has_same_tail or has_special


def random_nums_by_interval_pattern(interval_pattern, require_high_interval=False):
    """依區間 pattern 隨機抽出 6 個不重複號碼。"""
    interval_group_dict = get_interval_group_dict()
    selected_nums = []

    for interval_id in build_six_interval_pattern(
        interval_pattern,
        require_high_interval=require_high_interval,
    ):
        candidates = [
            num for num in interval_group_dict[interval_id]
            if num not in selected_nums
        ]
        if not candidates:
            return []
        selected_nums.append(random.choice(candidates))

    return sorted(selected_nums)


def generate_bet_combinations(
    interval_pattern_counter,
    rbg_pattern_counter,
    bet_count=BET_COUNT,
    use_top_interval_pattern=USE_TOP_INTERVAL_PATTERN,
    use_top_rbg_pattern=USE_TOP_RBG_PATTERN,
    enable_feature_rules=ENABLE_FEATURE_RULES,
    require_high_interval=REQUIRE_HIGH_INTERVAL,
    max_attempts=MAX_ATTEMPTS,
):
    """用 3獎高頻特徵 pattern 產生單式投注組合。"""
    interval_patterns = [
        pattern for pattern, _ in interval_pattern_counter.most_common(use_top_interval_pattern)
    ]
    rbg_patterns = [
        pattern for pattern, _ in rbg_pattern_counter.most_common(use_top_rbg_pattern)
    ]
    if not interval_patterns or not rbg_patterns:
        return []

    bet_list = []
    seen_bets = set()
    for _ in range(max_attempts):
        interval_pattern = random.choice(interval_patterns)
        rbg_pattern = random.choice(rbg_patterns)
        nums = random_nums_by_interval_pattern(
            interval_pattern,
            require_high_interval=require_high_interval,
        )
        if len(nums) != 6:
            continue
        if require_high_interval and not ({3, 4} & set(get_num49_interval_map(nums))):
            continue
        if not match_rbg_pattern(nums, rbg_pattern):
            continue
        if enable_feature_rules and not match_feature_rules(nums):
            continue

        bet_key = tuple(nums)
        if bet_key in seen_bets:
            continue
        seen_bets.add(bet_key)
        bet_list.append(nums)
        if len(bet_list) >= bet_count:
            break

    return bet_list


def print_prize3_feature_analysis(df_prize3_top):
    """分析 3獎高頻期數的正號特色，特號只作次要參考。"""
    all_nums = []
    all_7_nums = []
    frequency_weight_counter = Counter()
    weighted_counter = Counter()
    special_ball_counter = Counter()
    special_nums = {10, 20, 30, 40}
    special_counter = Counter()
    birthday_counter = Counter()
    rbg_pattern_counter = Counter()
    interval_pattern_counter = Counter()

    print("\n====== 3獎高頻中獎正號特色分析 ======")
    for idx in range(len(df_prize3_top)):
        row = df_prize3_top.iloc[idx]
        x_date = row["ndate"]
        prize2 = float(row["prize2"])
        prize3 = float(row["prize3"])
        nums = [int(row[f"N{i}"]) for i in range(1, 7)]
        special_ball = int(row["N7"])
        all_nums.extend(nums)
        all_7_nums.extend(nums + [special_ball])
        for num in nums:
            frequency_weight_counter[num] += MAIN_NUM_WEIGHT
            weighted_counter[num] += prize3 * MAIN_NUM_WEIGHT
        frequency_weight_counter[special_ball] += SPECIAL_NUM_WEIGHT
        weighted_counter[special_ball] += prize3 * SPECIAL_NUM_WEIGHT
        special_ball_counter[special_ball] += 1

        consecutive_groups = get_consecutive_groups(nums)
        same_tail_groups = get_same_tail_groups(nums)
        birthday_nums = sorted(num for num in nums if 1 <= num <= 31)
        feature_nums = sorted(set(nums) & special_nums)
        rbg_pattern = get_rbg_pattern(nums)
        interval_pattern = get_interval_pattern(nums)

        birthday_counter.update(birthday_nums)
        special_counter.update(feature_nums)
        rbg_pattern_counter.update([rbg_pattern])
        interval_pattern_counter.update([interval_pattern])

        print(f"\n>>> 第 {idx+1} 期 {x_date} 正號: {sorted(nums)}，特號: {special_ball}")
        print(f"    prize3: {prize3:g}，prize2: {prize2:g}")
        print(f"    RBG pattern: {rbg_pattern}")
        print(f"    區間 pattern: {interval_pattern}")
        if consecutive_groups:
            print(f"    連號: {consecutive_groups}")
        if same_tail_groups:
            print(f"    同尾: {same_tail_groups}")
        print(f"    生日號組(1-31): {birthday_nums} /> {len(birthday_nums)} 球")
        if feature_nums:
            print(f"    10/20/30/40 特色號碼: {feature_nums}")

    num_frequency = Counter(all_nums)
    # print("\n====== 正號高頻號碼 N1-N6 ======")
    # for num, count in num_frequency.most_common():
    #     if count >= 2:
    #         print(f">>> {num} 出現 {count} 次")

    # print("\n====== 號碼出現頻率權重 正號1.0 / 特號0.3 ======")
    # for num, score in frequency_weight_counter.most_common():
    #     if score >= 1:
    #         print(f">>> {num} 頻率權重 {score:.1f}")

    # print("\n====== 3獎權重號碼分數 ======")
    # for num, score in weighted_counter.most_common():
    #     if score > 0:
    #         print(f">>> {num} 權重分數 {score:.1f}")

    # print("\n====== 特號次要參考統計 ======")
    # for num, count in special_ball_counter.most_common():
    #     print(f">>> 特號 {num} 出現 {count} 次")

    special_ball_list = list(special_ball_counter.elements())
    special_rbg_dict = res_func_num_convert_RBG_Dict.res_List_To_rbg_Dict_func(special_ball_list)
    print(f"\n====== 3獎高頻前 {len(df_prize3_top)} 期特號 RBG 分組 ======")
    print(f"R: {format_frequency_groups(special_rbg_dict.get(0, []))} /> {len(set(special_rbg_dict.get(0, [])))} 個不同特號")
    print(f"B: {format_frequency_groups(special_rbg_dict.get(1, []))} /> {len(set(special_rbg_dict.get(1, [])))} 個不同特號")
    print(f"G: {format_frequency_groups(special_rbg_dict.get(2, []))} /> {len(set(special_rbg_dict.get(2, [])))} 個不同特號")

    print("\n====== 生日號組高頻號碼 ======")
    for num, count in birthday_counter.most_common():
        if count >= 2:
            print(f">>> {num} 出現 {count} 次")

    print("\n====== 10/20/30/40 特色號碼統計 ======")
    for num in sorted(special_nums):
        print(f">>> {num} 出現 {special_counter[num]} 次")

    rbg_42_dict = res_func_num_convert_RBG_Dict.res_List_To_rbg_Dict_func(all_7_nums)
    print(f"\n====== 3獎高頻前 {len(df_prize3_top)} 期 42 球 RBG 分組 N1-N6 + 特號 ======")
    r_groups = format_frequency_groups(rbg_42_dict.get(0, []))
    b_groups = format_frequency_groups(rbg_42_dict.get(1, []))
    g_groups = format_frequency_groups(rbg_42_dict.get(2, []))
    print(f"R: {r_groups} /> {len(set(rbg_42_dict.get(0, [])))} 個不同球號")
    print(f"B: {b_groups} /> {len(set(rbg_42_dict.get(1, [])))} 個不同球號")
    print(f"G: {g_groups} /> {len(set(rbg_42_dict.get(2, [])))} 個不同球號")

    # print("\n====== RBG Pattern 統計 N1-N6 不含特號 ======")
    # print(f"rbg_pattern_counter = {dict(rbg_pattern_counter)}")
    # for pattern, count in rbg_pattern_counter.most_common():
    #     print(f">>> {pattern}: {count} 次")

    # print("\n====== 1-49 區間 Pattern 統計 N1-N6 不含特號 ======")
    # print(f"interval_pattern_counter = {dict(interval_pattern_counter)}")
    # for pattern, count in interval_pattern_counter.most_common():
    #     print(f">>> {pattern}: {count} 次")

    return rbg_pattern_counter, interval_pattern_counter


def print_prize2_special_analysis(df_prize2_top):
    """分析 2獎高頻期數的特號特色；2獎 = 5 個正號 + 特號。"""
    special_balls = []
    special_counter = Counter()
    rbg_counter = Counter()
    interval_counter = Counter()

    print("\n====== 2獎高頻中獎特號分析 ======")
    print(f"2獎 = 5 個正號 + 特號；以下取 prize2 最大前 {len(df_prize2_top)} 期")

    for idx in range(len(df_prize2_top)):
        row = df_prize2_top.iloc[idx]
        x_date = row["ndate"]
        prize2 = float(row["prize2"])
        prize3 = float(row["prize3"])
        special_ball = int(row["N7"])
        special_balls.append(special_ball)

        rbg_id = res_func_num_convert_RBG_Dict.res_call_RBG_123_func(special_ball)
        interval_id = get_num49_interval_map([special_ball])[0]
        special_counter.update([special_ball])
        rbg_counter.update([rbg_id])
        interval_counter.update([interval_id])

        # print(
        #     f">>> 第 {idx+1} 期 {x_date} "
        #     f"特號: {special_ball}，prize2: {prize2:g}，prize3: {prize3:g}，"
        #     f"RBG: {rbg_id}，區間: {interval_id}"
        # )

    rbg_dict = res_func_num_convert_RBG_Dict.res_List_To_rbg_Dict_func(special_balls)
    print(f"\n====== 2獎高頻前 {PRIZE2_TOP_DRAW} 期特號 RBG 分組 ======")
    print(f"R: {format_frequency_groups(rbg_dict.get(0, []))} /> {len(set(rbg_dict.get(0, [])))} 個不同特號")
    print(f"B: {format_frequency_groups(rbg_dict.get(1, []))} /> {len(set(rbg_dict.get(1, [])))} 個不同特號")
    print(f"G: {format_frequency_groups(rbg_dict.get(2, []))} /> {len(set(rbg_dict.get(2, [])))} 個不同特號")

    # print("\n====== 2獎高頻特號出現統計 ======")
    # for num, count in special_counter.most_common():
    #     print(f">>> 特號 {num} 出現 {count} 次")

    # print("\n====== 2獎高頻特號 RBG 統計 ======")
    # print(f"R-B-G: {rbg_counter.get(1, 0)}-{rbg_counter.get(2, 0)}-{rbg_counter.get(3, 0)}")

    # print("\n====== 2獎高頻特號 1-49 區間統計 ======")
    # for interval_id in range(5):
    #     print(f">>> 區間 {interval_id}: {interval_counter.get(interval_id, 0)} 次")



def get_lotto_history_prize(getDraw=3):
    """取得最近 N 期歷史開獎及 1,2,3 獎中獎紀錄。"""
    df_ = pd.read_csv(
        PRIZE_CSV_DATA,
        dtype={'nDdate': str, 'N1': int, 'N2': int, 'N3': int, 'N4': int, 'N5': int, 'N6': int, 'N7': int, 'prize1': float, 'prize2': float, 'prize3': float}
    )
    df_ = df_.rename(columns={"nDdate": "ndate"})
    df_prize = df_.iloc[-getDraw:, [0,1,2,3,4,5,6,7,8,9,10]]  # ndate, N1..N6 + N7 + prize1 + prize2 + prize3
    # df1 = pd.DataFrame(df_prize)
    return df_prize


def sort_by_prize3(df_history_prize):
    """3獎分析專用：只依 prize3 最大排序，同分時日期新至舊。"""
    df_sorted = df_history_prize.copy()
    df_sorted["prize3"] = pd.to_numeric(df_sorted["prize3"], errors="coerce").fillna(0)
    return df_sorted.sort_values(
        by=["prize3", "ndate"],
        ascending=[False, False],
    ).reset_index(drop=True)


def sort_by_prize2(df_history_prize):
    """2獎分析專用：只依 prize2 最大排序，同分時日期新至舊。"""
    df_sorted = df_history_prize.copy()
    df_sorted["prize2"] = pd.to_numeric(df_sorted["prize2"], errors="coerce").fillna(0)
    return df_sorted.sort_values(
        by=["prize2", "ndate"],
        ascending=[False, False],
    ).reset_index(drop=True)


def main():
    
    os.system("clear")
    
    
    print("====== 3獎高頻中獎分析 ======")

    # 取得最近 N 期開獎號碼及 1,2,3 獎中獎資料。
    BACKTEST_DRAW = 14 # 最近 14 期。
    df_history_prize = get_lotto_history_prize(getDraw=BACKTEST_DRAW)
    
    
    print(f'最近 {BACKTEST_DRAW} 期開獎號及 1,2,3獎中獎紀錄')
    
    print(df_history_prize)

    df_history_prize_sorted = sort_by_prize3(df_history_prize)
    print(f'\n最近 {BACKTEST_DRAW} 期 3獎 prize3 獨立排序')
    print(df_history_prize_sorted)

    df_prize3_top = df_history_prize_sorted.head(PRIZE3_TOP_DRAW)
    print(f'\n最近 {BACKTEST_DRAW} 期中，3獎 prize3 最大前 {PRIZE3_TOP_DRAW} 期')
    print(df_prize3_top)

    df_prize2_sorted = sort_by_prize2(df_history_prize)
    df_prize2_top = df_prize2_sorted.head(PRIZE2_TOP_DRAW)
    print(f'\n最近 {BACKTEST_DRAW} 期中，2獎 prize2 最大前 {PRIZE2_TOP_DRAW} 期')
    print(df_prize2_top)

    # ===================== 2獎高頻特號分析 =====================
    print_prize2_special_analysis(df_prize2_top)
    
    # ===================== 3獎高頻正號特色分析 =====================
    rbg_pattern_counter, interval_pattern_counter = print_prize3_feature_analysis(df_prize3_top)

    if RANDOM_SEED is not None:
        random.seed(RANDOM_SEED)

    bet_list = generate_bet_combinations(
        interval_pattern_counter=interval_pattern_counter,
        rbg_pattern_counter=rbg_pattern_counter,
        bet_count=BET_COUNT,
        use_top_interval_pattern=USE_TOP_INTERVAL_PATTERN,
        use_top_rbg_pattern=USE_TOP_RBG_PATTERN,
        enable_feature_rules=ENABLE_FEATURE_RULES,
        require_high_interval=REQUIRE_HIGH_INTERVAL,
        max_attempts=MAX_ATTEMPTS,
    )
    if len(bet_list) < BET_COUNT:
        bet_list = generate_bet_combinations(
            interval_pattern_counter=interval_pattern_counter,
            rbg_pattern_counter=rbg_pattern_counter,
            bet_count=BET_COUNT,
            use_top_interval_pattern=3,
            use_top_rbg_pattern=3,
            enable_feature_rules=ENABLE_FEATURE_RULES,
            require_high_interval=REQUIRE_HIGH_INTERVAL,
            max_attempts=MAX_ATTEMPTS,
        )

    
    
    
    
if __name__ == "__main__":
    main()
