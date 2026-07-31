import pandas as pd
from pathlib import Path
from collections import Counter

import res_func_num_convert_RBG_Dict


"""
項目名：C4 1,2,3獎中獎注數及獎金特色分析

分析思路：
1. 讀入 M6_lotto_history_prize.csv。
2. 最近 BACKTEST_DRAW 期作為 3獎、2獎分析單位，預設 24 期。
3. 3獎分析：依 prize3 中獎注數最多排序，同分再依 prize3_unit 獎金最多排序。
4. 2獎分析：依 prize2 中獎注數最多排序，重點分析特別號 N7。
5. 頭獎分析：由最後一期往前，取最近 HEAD_PRIZE_ZERO_TOP_DRAW 期 prize1 = 0 的資料。
6. 本程式只做分析輸出，不產生投注檔、不修改網站功能。
"""


current_dir = Path(__file__).resolve().parent
PRIZE_CSV_DATA = current_dir.parent / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"

# 手動參數
BACKTEST_DRAW = 24  # 最近 24 期為開獎紀錄單位。
PRIZE3_TOP_DRAW = 7  # 3獎中獎注數最多，取前幾期分析。
PRIZE2_TOP_DRAW = 12  # 2獎中獎注數最多，取前幾期分析特別號。
HEAD_PRIZE_ZERO_TOP_DRAW = 7  # 由最後一期往前，取最近幾期頭獎無人中資料。


def load_history_prize():
    """讀入 M6 歷史開獎及 1,2,3獎中獎注數/每注獎金資料。"""
    df = pd.read_csv(
        PRIZE_CSV_DATA,
        dtype={
            "nDdate": str,
            "N1": int,
            "N2": int,
            "N3": int,
            "N4": int,
            "N5": int,
            "N6": int,
            "N7": int,
            "prize1": float,
            "prize2": float,
            "prize3": float,
            "prize1_unit": float,
            "prize2_unit": float,
            "prize3_unit": float,
        },
    )
    df = df.rename(columns={"nDdate": "ndate"})
    numeric_cols = [
        "prize1",
        "prize2",
        "prize3",
        "prize1_unit",
        "prize2_unit",
        "prize3_unit",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


def get_recent_draws(df, draw_count):
    """取得最近 draw_count 期資料。"""
    return df.tail(draw_count).reset_index(drop=True)


def get_main_nums(row):
    """取得 N1-N6 正號。"""
    return [int(row[f"N{i}"]) for i in range(1, 7)]


def get_num49_interval_map(nums):
    """將號碼轉成區間：0=1-9, 1=10-19, 2=20-29, 3=30-40, 4=41-49。"""
    interval_map = {
        0: list(range(1, 10)),
        1: list(range(10, 20)),
        2: list(range(20, 30)),
        3: list(range(30, 41)),
        4: list(range(41, 50)),
    }
    interval_idx = []
    for num in nums:
        for interval_id, interval_nums in interval_map.items():
            if int(num) in interval_nums:
                interval_idx.append(interval_id)
                break
    return interval_idx


def get_interval_pattern(nums):
    """回傳區間 pattern，例如 0-1-1-2-4。"""
    return "-".join(str(interval_id) for interval_id in sorted(get_num49_interval_map(nums)))


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


def sort_prize3_top(df_recent):
    """3獎：注數最多優先，同分用每注獎金最多優先。"""
    return df_recent.sort_values(
        by=["prize3", "prize3_unit", "ndate"],
        ascending=[False, False, False],
    ).reset_index(drop=True)


def sort_prize2_top(df_recent):
    """2獎：注數最多優先，同分用每注獎金最多優先。"""
    return df_recent.sort_values(
        by=["prize2", "prize2_unit", "ndate"],
        ascending=[False, False, False],
    ).reset_index(drop=True)


def get_recent_head_prize_zero(df, draw_count):
    """由最後一期往前取最近 draw_count 期頭獎無人中資料，顯示時日期遠排上。"""
    return df[df["prize1"] == 0].tail(draw_count).sort_values(
        by=["ndate"],
        ascending=[True],
    ).reset_index(drop=True)


def print_prize3_table(title, df):
    """列印 3獎分析表，只顯示指定欄位。"""
    cols = ["ndate", "N1", "N2", "N3", "N4", "N5", "N6", "prize3", "prize3_unit"]
    table_df = df[cols].copy()
    table_df.insert(0, "檔位", range(1, len(table_df) + 1))
    print(f"\n====== {title} ======")
    print(table_df.to_string(index=False))


def print_prize2_table(title, df):
    """列印 2獎特號分析表，只顯示 N7 特號及 prize2。"""
    cols = ["ndate", "N7", "prize2"]
    table_df = df[cols].copy()
    table_df.insert(0, "檔位", range(1, len(table_df) + 1))
    print(f"\n====== {title} ======")
    print(table_df.to_string(index=False))


def print_head_prize_zero_table(title, df):
    """列印頭獎無人中分析表，只顯示 N1-N6 正號。"""
    cols = ["ndate", "N1", "N2", "N3", "N4", "N5", "N6", "prize1", "prize2"]
    table_df = df[cols].copy()
    table_df.insert(0, "檔位", range(1, len(table_df) + 1))
    print(f"\n====== {title} ======")
    print(table_df.to_string(index=False))


def print_rbg_groups(title, nums):
    """列印號碼 R/B/G 三色分組。"""
    rbg_dict = res_func_num_convert_RBG_Dict.res_List_To_rbg_Dict_func(nums)
    print(f"\n====== {title} ======")
    print(f"R: {format_frequency_groups(rbg_dict.get(0, []))} /> {len(set(rbg_dict.get(0, [])))} 個不同球號")
    print(f"B: {format_frequency_groups(rbg_dict.get(1, []))} /> {len(set(rbg_dict.get(1, [])))} 個不同球號")
    print(f"G: {format_frequency_groups(rbg_dict.get(2, []))} /> {len(set(rbg_dict.get(2, [])))} 個不同球號")


def print_interval_pattern_counter(title, df):
    """直欄列印 N1-N6 區間 pattern 統計。"""
    interval_pattern_counter = Counter()
    for _, row in df.iterrows():
        interval_pattern_counter.update([get_interval_pattern(get_main_nums(row))])

    print(f"\n====== {title} ======")
    print("區間 pattern 統計:")
    for pattern, count in interval_pattern_counter.most_common():
        print(f"'{pattern}': {count},")


# --------------------------------------- Main function --------------------------------------- #
def main():
    df = load_history_prize()
    df_recent_24 = get_recent_draws(df, BACKTEST_DRAW)

    print("====== C4.py 3獎中獎注數及獎金特色分析 ======")
    print(f"資料來源: {PRIZE_CSV_DATA}")
    print(f"最近 {BACKTEST_DRAW} 期作 3獎分析")

    # 3 獎打印分項
    prize3_top = sort_prize3_top(df_recent_24).head(PRIZE3_TOP_DRAW)
    print_prize3_table(
        f"最近 {BACKTEST_DRAW} 期，中3獎分析排序後最前 {len(prize3_top)} 期",
        prize3_top,
    )
    prize3_main_nums = []
    for _, row in prize3_top.iterrows():
        prize3_main_nums.extend(get_main_nums(row))
    print_rbg_groups(
        f"中3獎前 {len(prize3_top)} 期 X 6 正號 = {len(prize3_main_nums)} 球 RBG 三色分組",
        prize3_main_nums,
    )
    print_interval_pattern_counter(
        f"中3獎前 {len(prize3_top)} 期 N1-N6 區間 pattern 統計",
        prize3_top,
    )

    # 2 獎打印分項
    prize2_top = sort_prize2_top(df_recent_24).head(PRIZE2_TOP_DRAW)
    print_prize2_table(
        f"最近 {BACKTEST_DRAW} 期，中2獎注數最多前 {len(prize2_top)} 期",
        prize2_top,
    )
    prize2_special_nums = [int(row["N7"]) for _, row in prize2_top.iterrows()]
    print_rbg_groups(
        f"中2獎前 {len(prize2_top)} 期 N7 特號 RBG 三色分組",
        prize2_special_nums,
    )
    # 頭獎打印分項
    head_prize_zero_top = get_recent_head_prize_zero(df, HEAD_PRIZE_ZERO_TOP_DRAW)
    print_head_prize_zero_table(
        f"由最後一期往前，頭獎沒有人中最近 {len(head_prize_zero_top)} 期，日期遠排上",
        head_prize_zero_top,
    )
    head_prize_zero_main_nums = []
    for _, row in head_prize_zero_top.iterrows():
        head_prize_zero_main_nums.extend(get_main_nums(row))
    print_rbg_groups(
        f"頭獎無人中最近 {len(head_prize_zero_top)} 期 X 6 正號 = {len(head_prize_zero_main_nums)} 球 RBG 三色分組",
        head_prize_zero_main_nums,
    )
    print_interval_pattern_counter(
        f"頭獎無人中最近 {len(head_prize_zero_top)} 期 N1-N6 區間 pattern 統計",
        head_prize_zero_top,
    )


if __name__ == "__main__":
    main()
