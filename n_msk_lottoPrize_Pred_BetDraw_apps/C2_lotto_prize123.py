import pandas as pd 
from pathlib import Path
import res_func_num_convert_RBG_Dict
from collections import Counter
import random

import os

'''
這支程式，找出最近 10 期多寶獎的開獎號碼，並列印出來。
>>> 多寶獎 第 5 期 2026-06-30 開獎號碼: [12, 13, 14, 17, 18, 22, 40]
>>> 多寶獎 第 6 期 2026-07-11 開獎號碼: [2, 5, 7, 11, 41, 43, 46]
>>> 多寶獎 第 7 期 2026-07-09 開獎號碼: [1, 7, 18, 21, 28, 33, 38]
>>> 多寶獎 第 8 期 2026-06-02 開獎號碼: [9, 14, 16, 20, 35, 37, 45]
>>> 多寶獎 第 9 期 2026-07-16 開獎號碼: [18, 21, 26, 27, 30, 32, 44]
>>> 多寶獎 第 10 期 2026-07-07 開獎號碼: [5, 27, 34, 37, 43, 48, 49]

'''


# 取得目前檔案所在目錄
current_dir = Path(__file__).resolve().parent

PRIZE_CSV_DATA = current_dir.parent / "A_msk_lottery_data_folder" / "M5_lotto_prize_123.csv"
LOTTO_DATA = current_dir.parent / "A_msk_lottery_data_folder" / "M2_last_upgrade_lotto_data.csv"
PRIZE_SUMMARY_DATA = current_dir.parent / "A_msk_lottery_data_folder" / "M4_lotto_prize_summary.csv"
SNOWBALL_BET_CSV = current_dir.parent / "msk_new_seed_apps" / "bet_data" / "snowball_bet.csv"

# 多人中獎投注預測參數
BET_COUNT = 3  # 最多產生幾注單式投注組合。
USE_TOP_INTERVAL_PATTERN = 1  # 1-3 使用最高頻的前幾個 1-49 區間 pattern；越大越容易產生組合。
USE_TOP_RBG_PATTERN = 1  # 1-3 使用最高頻的前幾個 RBG pattern；越大越容易產生組合。
ENABLE_FEATURE_RULES = True  # 是否啟用特色條件：生日號、連號、同尾、10/20/30/40。
REQUIRE_HIGH_INTERVAL = True  # 推薦單式是否必須至少包含一個 3/4 高區間號碼，即 30-49。
FORCE_HIGH_INTERVAL_TEMPLATE = True  # 若區間 pattern 太低位，強制改成 [0,0,1,1,2,3或4]。
MAX_ATTEMPTS = 5000  # 隨機嘗試產生組合的最大次數，避免條件太嚴時無限執行。
RANDOM_SEED = 42  # 固定隨機種子；同一份資料會產生相同結果，設為 None 可每次不同。

# 讀取歷史開獎資料，包含日期和號碼。
def load_data_func():
    df_ = pd.read_csv(
        LOTTO_DATA
    )
    df_all = df_.iloc[:, [0, 1, 2, 3, 4, 5, 6, 7]]  # ndate, N1..N6 + N7
    return df_all

def get_RBG_group_list():
    
    num_list = [num for num in range(1, 50)]
    rbg_group = res_func_num_convert_RBG_Dict.res_List_To_rbg_Dict_func(num_list)
    return rbg_group
   
    
    # 回傳指定日期前的窗口期數集合，以及該窗口內的 RBG 色球集合。
def res_nDate_getPass_nRn_func(ndate, window_nRn, included_last_nRn=True):
    df_all = load_data_func()
    df = pd.DataFrame(df_all)
    if included_last_nRn:
        df_data = df.loc[(df["ndate"] <= ndate)]
    else:
        df_data = df.loc[(df["ndate"] < ndate)]
    get_pass_df = df_data.iloc[-window_nRn:, [0, 1, 2, 3, 4, 5, 6, 7]] # ndate, N1..N6 + N7
    return get_pass_df

# 將窗口期數集合，轉成 list array
def get_x_val_list_func(res_df):
    dfs = pd.DataFrame(res_df)
    res_df_list = dfs.iloc[:, 1:8].values # 取 N1..N6 的號碼列，轉成 numpy array，再轉成 list
    return res_df_list

def get_lotto_snowballs_123_prize(getDraw=3):
    """取得歷史多寶獎，最多注數中獎前 3 期。"""
    df_ = pd.read_csv(
        PRIZE_CSV_DATA, dtype={'ndate': str, 'N1': int, 'N2': int, 'N3': int, 'N4': int, 'N5': int, 'N6': int, 'N7': int, 'prize1': float, 'prize2': float, 'prize3': float}
    )
    df_prize = df_.iloc[-getDraw:, [0,1,2,3,4,5,6,7,8,9,10]]  # ndate, N1..N6 + N7 + prize1 + prize2 + prize3
    # df1 = pd.DataFrame(df_prize)
    return df_prize


def to_int_set(nums):
    """將 pandas/numpy 來源的號碼轉成 Python int set，避免印出 np.int64(...)。"""
    return {int(num) for num in nums}


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


def get_next_draw_date():
    """只回傳下期開獎日期，給儲存投注 CSV 使用。"""
    return get_next_draw_info()["bet_date"]


def format_prize_fund(prize_fund):
    """將獎金格式化為 $ 13,000,000。"""
    return f"$ {int(prize_fund):,}"


def save_snowball_bets(bet_list, bet_date):
    """將多人中獎特色投注單式儲存到 snowball_bet.csv。"""
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

    SNOWBALL_BET_CSV.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=["bet_date", "N1", "N2", "N3", "N4", "N5", "N6"]).to_csv(
        SNOWBALL_BET_CSV,
        index=False,
        encoding="utf-8-sig",
    )
    return SNOWBALL_BET_CSV


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
    """將 7 個號碼 pattern 壓成 6 個正選號 pattern。"""
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
    """將 7 個號碼的 R-B-G pattern 壓成 6 個正選號 pattern。"""
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
    """用多人中獎特徵 pattern 產生單式投注組合。"""
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


def print_prize_feature_analysis(df_snowballs_123):
    """分析多人中獎期數的連號、同尾、生日號和特色號碼。"""
    all_nums = []
    special_nums = {10, 20, 30, 40}
    special_counter = Counter()
    birthday_counter = Counter()
    rbg_pattern_counter = Counter()
    interval_pattern_counter = Counter()

    print("\n====== 多人中獎號碼特色分析 ======")
    for idx in range(len(df_snowballs_123)):
        row = df_snowballs_123.iloc[idx]
        x_date = row.iloc[0]
        nums = [int(num) for num in row.iloc[1:8]]
        all_nums.extend(nums)

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

        print(f"\n>>> 第 {idx+1} 期 {x_date} 開獎號碼: {sorted(nums)}")
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
    print("\n====== 多人中獎高頻號碼 ======")
    for num, count in num_frequency.most_common():
        if count >= 2:
            print(f">>> {num} 出現 {count} 次")

    print("\n====== 生日號組高頻號碼 ======")
    for num, count in birthday_counter.most_common():
        if count >= 2:
            print(f">>> {num} 出現 {count} 次")

    print("\n====== 10/20/30/40 特色號碼統計 ======")
    for num in sorted(special_nums):
        print(f">>> {num} 出現 {special_counter[num]} 次")

    # print("\n====== RBG Pattern 統計 ======")
    # print(f"rbg_pattern_counter = {dict(rbg_pattern_counter)}")
    # for pattern, count in rbg_pattern_counter.most_common():
    #     print(f">>> {pattern}: {count} 次")

    # print("\n====== 1-49 區間 Pattern 統計 ======")
    # print(f"interval_pattern_counter = {dict(interval_pattern_counter)}")
    # for pattern, count in interval_pattern_counter.most_common():
    #     print(f">>> {pattern}: {count} 次")

    return rbg_pattern_counter, interval_pattern_counter


def main():
    
    os.system("clear")
    
    # df_all = load_data_func()
    # BEGIN_LAST_DRAW = 1  # <= 以最後一期為基準，回測前幾期（不包含當期）來找窗口期數集合
    # start_draw = len(df_all) - BEGIN_LAST_DRAW
    
    # 取得回測最近 7 期多寶獎的最多人中獎的開獎號碼，並列印出來。
    BACKTEST_DRAW = 7 #最多注數中獎前 7 期。
    # 取出多寶獎最多中獎期數
    df_snowballs_123 = get_lotto_snowballs_123_prize(getDraw=BACKTEST_DRAW)
    
    print('最近 50 期最多注數中獎前 7 期開獎號：')
    
    print(df_snowballs_123)
    
    # ===================== 多人中獎號碼特色分析 及投注預測 =====================
    rbg_pattern_counter, interval_pattern_counter = print_prize_feature_analysis(df_snowballs_123)

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

    print("\n====== 多人中獎投注預測 ======")
    print(f"BET_COUNT = {BET_COUNT}")
    print(f"USE_TOP_INTERVAL_PATTERN = {USE_TOP_INTERVAL_PATTERN}")
    print(f"USE_TOP_RBG_PATTERN = {USE_TOP_RBG_PATTERN}")
    print(f"ENABLE_FEATURE_RULES = {ENABLE_FEATURE_RULES}")
    print(f"REQUIRE_HIGH_INTERVAL = {REQUIRE_HIGH_INTERVAL}")
    print(f"FORCE_HIGH_INTERVAL_TEMPLATE = {FORCE_HIGH_INTERVAL_TEMPLATE}")
    print(f"MAX_ATTEMPTS = {MAX_ATTEMPTS}")
    print(f"原始高頻分析N1-N6區間 pattern: {[p for p, _ in interval_pattern_counter.most_common(USE_TOP_INTERVAL_PATTERN)]}")
    print(f"原始高頻分析 R-B-G pattern: {[p for p, _ in rbg_pattern_counter.most_common(USE_TOP_RBG_PATTERN)]}")
    print(f"單式用 R-B-G pattern: {[build_six_rbg_pattern(p) for p, _ in rbg_pattern_counter.most_common(USE_TOP_RBG_PATTERN)]}")

    next_draw_info = get_next_draw_info()
    print("\n====== 下期獎金及多人中獎特式投注 ======")
    print(f"**{next_draw_info['bet_date']},**")
    print(f"星期 {next_draw_info['week']},")
    print(f"下期獎金 {format_prize_fund(next_draw_info['prize_fund'])}")

    if not bet_list:
        print("未能產生符合條件的單式投注組合，請放寬 pattern 或關閉 ENABLE_FEATURE_RULES。")
    for idx, nums in enumerate(bet_list, 1):
        print(f"推薦單式 {idx}: {next_draw_info['bet_date']} {nums}")

    if bet_list:
        bet_date = next_draw_info["bet_date"]
        output_path = save_snowball_bets(bet_list, bet_date)
        print(f"\n已儲存多人中獎特色投注：{output_path}")
        # print(f"投注日期：{bet_date}")
    
    
    
if __name__ == "__main__":
    main()
    
'''
我今保留 c3.py 功能。新增 C4.py 預測投注分析系統。

1， 如何利用 3獎的分析產生區間位置預測。
2，利用3獎分析產生 區間 [1,2,3,4,5] 5 球預測組合。
3， 第 6 球由 2 獎的特別分析產。
4， 手動參數由用戶決定，下期預測投注注數，最多1-3 注。
5， 1-3 注內包含候選球，由 3獎分析產生組合，RBG, 生日號組合，10-40 0號組合，連號或同尾號組合。
6， 冷號或熱號都必須是最近 14 期內之開獎號，14期內沒有開出為不入選球。


先討論分析，決定模組功能才執行。
'''

