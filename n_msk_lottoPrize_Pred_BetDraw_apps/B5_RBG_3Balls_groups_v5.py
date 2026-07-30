import pandas as pd 
from pathlib import Path
import res_func_num_convert_RBG_Dict
import res_func_marksix_next_BetDate
from datetime import date
import os
import random
"""
將開獎號改成,R,B,G, 3,2,2 多色排前，少排後。

[R,R,R,B,B,G,G] -> [R,R,R,B,B,G,G]
[B,B,B,R,R,G,G] -> [B,B,B,R,R,G,G]
"""


# 取得目前檔案所在目錄
current_dir = Path(__file__).resolve().parent

# 讀取歷史開獎資料，包含日期和號碼。
def load_data_func():
    df_ = pd.read_csv(
        current_dir.parent / "A_msk_lottery_data_folder" / "M2_last_upgrade_lotto_data.csv"
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
    res_df_list = dfs.iloc[:, 1:7].values # 取 N1..N6 的號碼列，轉成 numpy array，再轉成 list
    return res_df_list

def sort_rbg_groups_by_count(r_balls, b_balls, g_balls, sel_colors=None):
    """按 R/B/G 每色球數由多至少排序，同數量時維持 R、B、G 順序。"""
    if sel_colors is None:
        sel_colors = [1, 2, 3]

    color_groups = [
        (1, "R", list(r_balls)),
        (2, "B", list(b_balls)),
        (3, "G", list(g_balls)),
    ]
    ranked_groups = sorted(
        [group for group in color_groups if group[0] in sel_colors],
        key=lambda group: (-len(group[2]), group[0]),
    )
    ranked_balls = []
    for _, _, balls in ranked_groups:
        ranked_balls.extend(balls)

    return ranked_groups, ranked_balls


def wrap_lotto_num(num):
    """將數字循環回 1..49：49->49、50->1、51->2。"""
    return ((int(num) - 1) % 49) + 1


def to_int_set(nums):
    """將 pandas/numpy 來源的號碼轉成 Python int set，避免印出 np.int64(...)。"""
    return {int(num) for num in nums}


''' -------- Main Function ------------------------------------------------ '''
def main():
    os.system("clear")
    # print('\n' + "=" * 60)
    df_all = load_data_func()
    
    # ---- Setting Parameters ----
    inp_last_matched_draw = 1  # <= 以最後一期為基準，回測前幾期（不包含當期）來找窗口期數集合
    start_draw = len(df_all) - inp_last_matched_draw
    max_window_draw = 9  # 每期最多回測前幾期來找窗口期數集合
    included_last_nRn = True  # 是否包含當期號碼來找窗口期數集合 (True: 包含當期，False: 不包含當期)
    """按 R/B/G 每色球數由多至少排序，同數量時維持 R、B、G 順序。"""
    
    
    # Rnu RBG 1,2,3 集合球追蹤，依窗口期數增加，直到收集到足夠的顏色球為止。
    for idx in range(start_draw, len(df_all)):
        dfs = df_all.iloc[:,0:].values  # 以最後一期為基準
        
        y_date = dfs[idx][0]  # 假設日期欄位名稱為 'date'
        y_num6 = dfs[idx][1:7]  # 假設號碼欄位名稱為 'N1'..'N6'
        y_num7 = dfs[idx][7]    # 假設特別號欄位名稱為 'N7'
       
        print('='*70)
        
        single_num = set()
        double_num = set()
        # -----查詢期數窗口內的 RBG 色球集合-----
        for window in range(max_window_draw, 0, -1):
            """包含當期，回測前 window 期資料 ----- > N1.. N6 , 不包含特號統計"""
            res_df = res_nDate_getPass_nRn_func(ndate=y_date, 
                                                window_nRn=window, 
                                                included_last_nRn=included_last_nRn)
            
            res_xlist_arr = get_x_val_list_func(res_df)
            if len(res_xlist_arr) == 0:
                continue

            # 每增加一個窗口，只處理該窗口新納入的那一期，避免重複累計同一期資料。
            sublist = res_xlist_arr[0]
            # print(f'/> 窗口期數: {window}，回測資料：{sublist}')
            # 找出開獎號 < 10, and >= 40 的號碼。
            
            small_nums = sorted(int(num) for num in sublist if num < 10)
            large_nums = sorted(int(num) for num in sublist if num >= 40)

            if small_nums and large_nums:
                print(f'/> 窗口期數: {window}，{sublist} 有 <10 號碼 {small_nums}，and >=40 號碼 {large_nums}')  
                single_num.update(small_nums)
                double_num.update(large_nums) 
                       
            if small_nums and not large_nums:
                single_num.update(small_nums)
                print(f'/> 窗口期數: {window}，{sublist} --------------------------------------> 只有 <10 號碼 {small_nums}')
            if not small_nums and large_nums:
                double_num.update(large_nums) 
                print(f'/> 窗口期數: {window}, {sublist} --------------------------------------> 只有 >=40 號碼 {large_nums}')
            if not small_nums and not large_nums:
                print(f'/> 窗口期數: {window}, {sublist} --------------------------------------> 沒有 <10 和 >=40 號碼')
        print('='*70)
        print(f'>>> 第 {idx+1} 期 最後一期開獎號碼: {y_date}:{y_num6}') #N1..N6 != N7
            
        print(f'/> 集合： {single_num} <10 號碼集合，{double_num} >=40 號碼集合')
if __name__ == "__main__":
    main()
