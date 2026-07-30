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

def get_lotto_snowballs_123_prize(getDraw=3):
    """取得歷史多寶獎，最多注數中獎前 3 期。"""
    df_ = pd.read_csv(
        current_dir.parent / "A_msk_lottery_data_folder" / "M5_lotto_prize_123.csv"
    )
    df_all = df_.iloc[:getDraw, [0,1, 2, 3, 4, 5, 6, 7]]  # ndate, N1..N6 + N7 + prize1 + prize2 + prize3
    return df_all



def get_rbg_sub_group_dict():
    """回傳 R/B/G 的子分組字典。"""
    return {
        1: {
            "R1": [1, 2, 7, 8],
            "R2": [12, 13, 18, 19, 23, 24, 29, 30, 34, 35, 40], # 11
            "R3": [45, 46],
        },
        2: {
            "B1": [3, 4, 9],
            "B2": [10, 14, 15, 20, 25, 26, 31, 36, 37], # 9
            "B3": [41, 42, 47, 48],
        },
        3: {
            "G1": [5, 6],
            "G2": [11,16, 17, 21, 22, 27, 28, 32, 33, 38], # 10
            "G3": [39, 43, 44, 49],
        },
    }


def group_candidates_by_rbg_sub_group(candidate_dict):
    """將 {1:[...], 2:[...], 3:[...]} 候選號分成 R1/R2/R3 等子組。"""
    sub_group_dict = get_rbg_sub_group_dict()
    grouped_dict = {}

    for color_key, sub_groups in sub_group_dict.items():
        candidate_set = set(candidate_dict.get(color_key, []))
        grouped_dict[color_key] = {}
        for group_name, group_nums in sub_groups.items():
            grouped_dict[color_key][group_name] = sorted(candidate_set & set(group_nums))

    return grouped_dict


def to_int_set(nums):
    """將 pandas/numpy 來源的號碼轉成 Python int set，避免印出 np.int64(...)。"""
    return sorted({int(num) for num in nums})

def JC_next_bet_date():
    next_bet_date, next_week = res_func_marksix_next_BetDate.main()
    return next_bet_date, next_week


def normalize_draw_numbers(values):
    """將開獎號碼安全轉成 Python int 清單，避開 NA/object 型別。"""
    normalized = []
    for value in values:
        if pd.isna(value):
            continue
        try:
            normalized.append(int(value))
        except (TypeError, ValueError):
            continue
    return normalized


def main():
    
    os.system("clear")
    
    df_all = load_data_func()
    LAST_DRAW_START = 30  # <= 以最後一期為基準，回測前幾期（不包含當期）來找窗口期數集合
    start_draw = len(df_all) - LAST_DRAW_START
    
    # 取得回測資料
    BACKTEST_DRAW = 7 #最多注數中獎前 3 期。
    
    N1_10_Up_draw = []
    N1_10_Up_draw_set = set()
    
    # get backtest N1 column start 10 number up to N6 column draw
    for idx in range(start_draw,len(df_all)):
        dfs1 = df_all.iloc[idx, 0:].values  # 以最後一期為基準
        x_date = dfs1[0]
        x_num6 = normalize_draw_numbers(dfs1[1:7])  # 假設號碼欄位名稱為 'N1'..'N7'
        x_num7 = normalize_draw_numbers([dfs1[7]])
        x_num7_value = x_num7[0] if x_num7 else None
        
        # print(f'>>> 第 {idx+1} 期 {x_date} 開獎號碼: {to_int_set(x_num6)} + {x_num7_value}') #N1..N6 != N7 --- IGNORE ---
        
        if len(N1_10_Up_draw) == BACKTEST_DRAW:
            break
        
        if not x_num6:
            continue
        
        ''' 找出 第一開球號由 10號- 19 開始，即是沒有 0-9 '''
        N1_num = x_num6[0]
        if N1_num >= 10 and N1_num < 20:
            N1_10_Up_draw.append(to_int_set(x_num6))
            print(f'>>> 第 {idx+1} 期 {x_date} 開獎號碼: {to_int_set(x_num6)} + {x_num7_value}') #N
            for num in x_num6:
                ''' 找出 10 - 39 的開號'''
                if num <= 40:
                    N1_10_Up_draw_set.add(num)
                    
                
            
    
    
    rbg_dict = res_func_num_convert_RBG_Dict.res_List_To_rbg_Dict_func(N1_10_Up_draw_set)
    r = rbg_dict[0]
    b = rbg_dict[1]
    g = rbg_dict[2]
    
    # for idx,lotto in enumerate(N1_10_Up_draw):
    #     print(f'{idx} {lotto}')
        

    for k,v in rbg_dict.items():
        if k == 0:
            print(f'R: {v}')
        if k == 1:
            print(f'B: {v}')
        if k == 2:
            print(f'G: {v}')
            
            
    print('='*40)
    
    rbg_list = r + b+ g
    print(f'{sorted(rbg_list)} /> {len(rbg_list)}')
    print('='* 40)
   
    # ================Matched backtest lotto draw ===========================
    ''' 回測最近 7 期，隨機抽取 6 個號碼，與真實開獎號碼比對，命中 3 個以上就列印出來。'''
    matched_backtest = 5 # backtest matched draw 
    matched_start_draw = len(df_all) - matched_backtest
    matched_ctr = 0
    matched_backtest_total = 0
    pred_draw = 2 # 預測注數
    
    
    # ===== Backtest Loop for each draw from start_draw to the end of df_all =====
    for matched_idx in range(matched_start_draw, len(df_all)):
        matched_backtest_total += 1
        rand_list = []
        
        # --- load df
        dfs1 = df_all.iloc[matched_idx, 0:].values  # 以最後一期為基準
        y_date = dfs1[0]
        y_num7 = normalize_draw_numbers(dfs1[1:8])  # 假設號碼欄位名稱為 'N1'..'N7'
        # y_num7 = dfs1[7]

        
        ''' 10 - 39 號回測 30 期 '''
    
        for n in range(pred_draw):
            
            random.shuffle(rbg_list)
            rand6 = random.sample(rbg_list,6) # pred bet draw 6 number
            rand_list.append(rand6)
            
            #  matched random draw lotto
            matched = set(rand6) & set(y_num7)
            if len(matched) >= 3:
                print(f'{n} = {matched_ctr :>2} {y_date}: {to_int_set(y_num7)} ,{sorted(rand6)} >> {to_int_set(matched)} /> {len(matched)}')
                matched_ctr += 1
        
      
    percents = (matched_ctr / matched_backtest_total * 100) if matched_backtest_total else 0
    print(f'回測期數：{matched_backtest_total}')
    print(f'rbg 10-39 命中期數：{matched_ctr}')
    print(f'命中百分比：{percents:.2f}%')
    print()
    
    
    
    
        
if __name__ == "__main__":
    main()
