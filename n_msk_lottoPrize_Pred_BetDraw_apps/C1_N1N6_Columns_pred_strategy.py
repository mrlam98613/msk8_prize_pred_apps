import pandas as pd 
from pathlib import Path
import res_func_num_convert_RBG_Dict
import B6_RBG_cold_num_v6
import os
import random
import res_predict_N1_N6_interval_BackTest
import res_func_marksix_next_BetDate
import func2_RBG_collect_5Balls_DrawWindows

# 取得目前檔案所在目錄
current_dir = Path(__file__).resolve().parent

# 讀取歷史開獎資料，包含日期和號碼。
def load_data_func():
    df_ = pd.read_csv(
        current_dir.parent / "A_msk_lottery_data_folder" / "M2_last_upgrade_lotto_data.csv"
    )
    df = df_.iloc[:, [0, 1, 2, 3, 4, 5, 6, 7]]  # ndate, N1..N6 + N7
    df_all = pd.DataFrame(df)
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



def to_int_set(nums):
    """將 pandas/numpy 來源的號碼轉成 Python int set，避免印出 np.int64(...)。"""
    return sorted({int(num) for num in nums})

#  下期馬會開獎日期
def JC_next_bet_date():
    next_bet_date, next_week = res_func_marksix_next_BetDate.main()
    return next_bet_date, next_week


def get_num49_interval_map(lotto_list):
    """
    將開獎號碼對應到 1-49 的區間編號
    0: 1-10, 1: 11-20, 2: 21-30, 3: 31-40, 4: 41-49
    回傳每個號碼對應的區間 id 組成的 list
    """
    interval_map = {
        0: list(range(1, 10)), #1-9
        1: list(range(10, 20)), #10-19
        2: list(range(20, 30)), #20-29
        3: list(range(30, 41)), #30-40
        4: list(range(41, 50)), #41-49
    }
    lotto_interval_idx = []
    for num in lotto_list:
        for interval_id, nums in interval_map.items():
            if num in nums:
                lotto_interval_idx.append(interval_id)
                break
    return lotto_interval_idx


def main():

    df_all = load_data_func()
    LAST_DRAW_START = 1  # <= 以最後一期為基準，回測前幾期（不包含當期）來找窗口期數集合
    start_draw = len(df_all) - LAST_DRAW_START
    
    # 取得回測資料
    BACKTEST_WINDOWS = 6 # 回測窗口期。
    included_last_nRn = True # 包含當期
    
   
    # for idx in range(start_draw,len(df_all)):
    #     dfs1 = df_all.iloc[idx, 0:].values  # 以最後一期為基準
    #     y_date = dfs1[0]
    #     y_num6 = dfs1[1:7]  # 假設號碼欄位名稱為 'N1'..'N7'
    #     y_num7 = dfs1[7]
        
    #     for window in range(1, BACKTEST_WINDOWS + 1):
    #         """不包含當期，回測前 window 期資料"""
    #         res_df = res_nDate_getPass_nRn_func(ndate=y_date, window_nRn=window, included_last_nRn=included_last_nRn)
    #         # print(f'/> 窗口期數: {window}，回測資料：\n{res_df}')
    #         res_xlist_arr = get_x_val_list_func(res_df)
    #         if len(res_xlist_arr) == 0:
    #             continue

    #         # 每增加一個窗口，只處理該窗口新納入的那一期，避免重複累計同一期資料。
    #         sublist = res_xlist_arr[0]
    #         # print(f'/> 窗口期數: {window}，回測資料：{sublist}')
            
    #         dictRBG = res_func_num_convert_RBG_Dict.res_List_To_rbg_Dict_func(sublist)
        
    #         r = dictRBG[0]
    #         b = dictRBG[1]
    #         g = dictRBG[2]
    
   

    #         for k,v in dictRBG.items():
    #             if k == 0:
    #                 print(f'R: {v}')
    #             if k == 1:
    #                 print(f'B: {v}')
    #             if k == 2:
    #                 print(f'G: {v}')
            
            
    #         print('='*40)
        
    #         rbg_list = r + g
    #         print(f'{sorted(rbg_list)} /> {len(rbg_list)}')
    #         print('='* 40)
        
    # 找最後一開獎期-日期
    anchor_date = df_all.iloc[-1]["ndate"]
    
    if anchor_date is None:
        anchor_exists = (df_all["ndate"] == anchor_date).any()
        if not anchor_exists:
            print(f"找不到 anchor_date={anchor_date}，無法預測。")
            return None
    
    RBG_Colors_and_Window_summary_dict = func2_RBG_collect_5Balls_DrawWindows.main(
                                            y_date=str(anchor_date),
                                            collect_balls_break=7, 
                                            draw_same_color=2, 
                                            included_last_nRn=True)
    
    ''' 輸出結果：每個顏色的窗口期數，以及依熱門冷門排序的候選球清單。 '''
    for k in [1, 2, 3]: # 1=R, 2=B, 3=G
        v = RBG_Colors_and_Window_summary_dict[k]
        print(f'/> {k} : {sorted(v)}')
    
    # 窗口收集顏色球 windows list = [red,blue,green] 窗口期越少代表越熱門，越遠代表越冷門
    print(f'/> windows colorballs list: [red,blue,green] = {RBG_Colors_and_Window_summary_dict[0]}')
    
    # 下期馬會開獎日期
    next_bet_date, next_week = JC_next_bet_date()
    
    
    
    # ── 呼叫區間預測副程式 ──
    '''
    return {
        "anchor_date": str(anchor_date),
        "next_draw_date": next_draw_date,
        "next_draw_week": next_draw_week,
        "window": window_list,
        "pred_interval": final_pred_sorted,
        "zone_score": dict(zone_score),
    '''
    # '[0,x,x,x,x,4]/[x,x,x,x,x,4],[x,x,x,x,x,x] 依馬可夫隨機預測, 區間模式')
    fixed_interval_mode = "none"  # "head_tail" / "tail_only" / "none"
    window_list = [6]
    interval_pred = res_predict_N1_N6_interval_BackTest.predict_next_draw_intervals(
        window_list=window_list,
        alpha=1.0,
        anchor_date=str(anchor_date),
        fixed_interval_mode = fixed_interval_mode
    )

    # 安全提取預測結果（可能為 None）
    pred_interval = []
    if interval_pred is not None:
        pred_interval = interval_pred.get("pred_interval", [])
        print(f'下期預測開號區間: {pred_interval}')
        
if __name__ == "__main__":
    main()