# -*- coding: utf-8 -*-
"""
/> 3321 2026-04-18 真實開獎號碼: [17, 20, 27, 32, 39, 46] + 34
/> 下一期預測(anchor=2026-04-18) => 日期:2026-04-21 星期:None 窗口:[8] 預測區間:[0, 1, 2, 3, 4, 4]
/> 預測下期N1..N6區間號: [0, 1, 2, 3, 4, 4]
/> 對應下一期日期: 2026-04-21
/> RBG 顏色集合球需要期數 :[23, 12, 29]
    Red Balls 集合球: [12, 46, 18, 19, 45, 2, 40, 23, 13, 29, 8, 7]
    Blue Balls 集合球: [9, 14, 42, 26, 20, 15, 3, 37, 47, 41, 48, 25]
    Green Balls 集合球: [33, 49, 5, 6, 28, 11, 16, 39, 22, 38, 17, 32]
/> 最少 2 色(期數最小): ['Blue', 'Red'] / windows=[12, 23]
/> 兩色合併預測候選球號: [2, 3, 7, 8, 9, 12, 13, 14, 15, 18, 19, 20, 23, 25, 26, 29, 37, 40, 41, 42, 45, 46, 47, 48] /> 共 24 顆球。
/> 下一期真實區間(2026-04-21): [0, 0, 0, 1, 2, 4]，區間命中: 4
/> 下期投注單式(2026-04-21): [7, 13, 25, 40, 41, 42]
/> 下期開獎號碼(2026-04-21): [2, 4, 10, 11, 26, 44] + 40
/> 單式命中: [] special_hit=1 score=0.0 prize=0 ✅

"""
from collections import defaultdict, Counter
import pandas as pd
from pathlib import Path
import os
import random
import res_func_num_convert_RBG_Dict
import res_func_marksix_next_BetDate

def clear_screen():
    """清除終端機畫面"""
    os.system("clear")

current_dir = Path(__file__).resolve().parent

def load_data_func():
    """
    讀取歷史開獎資料，回傳 DataFrame，欄位為 ndate, N1..N6, N7
    """
    df_ = pd.read_csv(
        current_dir.parent / "A_msk_lottery_data_folder" / "M2_last_upgrade_lotto_data.csv"
    )
    df_all = df_.iloc[:, [0, 1, 2, 3, 4, 5, 6, 7]]  # ndate, N1..N6 + N7
    return df_all

def res_nDate_getPass_nRn_func(ndate, window_nRn, included_last_nRn=True):
    """
    根據 ndate 和窗口期數，取得對應的開獎資料
    ndate: 目標期日期
    window_nRn: 視窗期數
    included_last_nRn: 是否包含目標期本身
    """
    df_all = load_data_func()
    df = pd.DataFrame(df_all)
    if included_last_nRn:
        df_data = df.loc[(df["ndate"] <= ndate)]
    else:
        df_data = df.loc[(df["ndate"] < ndate)]
    get_window_df = df_data.iloc[-window_nRn:, [0, 1, 2, 3, 4, 5, 6, 7]]
    return get_window_df

def get_x_val_list_func(window_df):
    """
    從 DataFrame 中提取號碼列表，回傳 N1..N6 的 numpy array
    """
    dfs = pd.DataFrame(window_df)
    df_list_arr = dfs.iloc[:, 1:7].values
    return df_list_arr

def get_num49_interval_map(lotto_list):
    """
    將開獎號碼對應到 1-49 的區間編號
    0: 1-10, 1: 11-20, 2: 21-30, 3: 31-40, 4: 41-49
    回傳每個號碼對應的區間 id 組成的 list
    """
    interval_map = {
        0: list(range(1, 11)), #1-10
        1: list(range(11, 21)), #11-20
        2: list(range(21, 31)), #21-30
        3: list(range(31, 41)), #31-40
        4: list(range(41, 50)), #41-49
    }
    lotto_interval_idx = []
    for num in lotto_list:
        for interval_id, nums in interval_map.items():
            if num in nums:
                lotto_interval_idx.append(interval_id)
                break
    return lotto_interval_idx

def build_markov_transition(interval_sequences):
    """
    建立馬可夫轉移矩陣
    interval_sequences: list of list，每期的區間序列
    回傳: 轉移次數 dict
    """
    transition = defaultdict(lambda: defaultdict(int))
    for i in range(len(interval_sequences) - 1):
        current_seq = interval_sequences[i]
        next_seq    = interval_sequences[i + 1]
        for cur_zone in set(current_seq):
            for nxt_zone in set(next_seq):
                transition[cur_zone][nxt_zone] += 1
    return transition

def predict_next_intervals(transition, current_seq, alpha=1.0):
    """
    根據當期區間序列，預測下期最可能的區間（加 Laplace smoothing）
    transition: 轉移次數 dict
    current_seq: 當期區間序列
    alpha: smoothing 參數，預設 1.0
    回傳: {區間: 分數}
    """
    score = defaultdict(float)
    zones = [0, 1, 2, 3, 4]
    for cur_zone in set(current_seq):
        row = transition.get(cur_zone, {})
        total = sum(row.values()) + alpha * len(zones)
        for nxt_zone in zones:
            cnt = row.get(nxt_zone, 0)
            prob = (cnt + alpha) / total
            score[nxt_zone] += prob
    return score  # 回傳所有分數，不排序


def get_next_draw_info_by_anchor(df_all, anchor_date):
    """
    由指定 anchor_date 找出資料表中的下一期日期。
    回傳: (next_draw_date, next_draw_week)；若沒有下一期則回傳 (None, None)
    """
    df = pd.DataFrame(df_all).reset_index(drop=True)
    idx_list = df.index[df["ndate"] == anchor_date].tolist()
    if not idx_list:
        return None, None
    idx = idx_list[-1]
    if idx + 1 >= len(df):
        return None, None
    next_row = df.iloc[idx + 1]
    next_draw_date = str(next_row["ndate"])
    next_draw_week = None
    return next_draw_date, next_draw_week


def predict_next_draw_intervals(window_list=None, alpha=1.0, anchor_date=None):
    if window_list is None:
        window_list = [8]

    df_all = load_data_func()
    if df_all.empty:
        print("資料為空，無法預測。")
        return None

    # 無指定 anchor_date 時，使用最後一期已知開獎日
    if anchor_date is None:
        anchor_date = df_all.iloc[-1]["ndate"]

    anchor_exists = (df_all["ndate"] == anchor_date).any()
    if not anchor_exists:
        print(f"找不到 anchor_date={anchor_date}，無法預測。")
        return None

    zone_score = Counter()

    for get_window_draw in window_list:
        window_df = res_nDate_getPass_nRn_func(
            ndate=anchor_date,
            window_nRn=get_window_draw,
            included_last_nRn=True #包含當期，因為要用當期資料來預測下一期
        )

        xlist_arr = get_x_val_list_func(window_df)
        if len(xlist_arr) < 2:
            continue

        interval_sequences = []
        for sublist in xlist_arr:
            interval_sequences.append(get_num49_interval_map(sublist))

        if len(interval_sequences) < 2:
            continue

        transition = build_markov_transition(interval_sequences)
        current_seq = interval_sequences[-1]
        score = predict_next_intervals(transition, current_seq, alpha=alpha)
        zone_score.update(score)

    if not zone_score:
        print("分數為空，請增加 window 或確認資料筆數。")
        return None

    fixed_head, fixed_tail = 0, 4
    sorted_zones = [z for z, _ in zone_score.most_common()]
    middle_pred = (sorted_zones * 4)[:4] if len(sorted_zones) < 4 else sorted_zones[:4]
    final_pred_sorted = sorted([fixed_head, *middle_pred, fixed_tail])

    # 若為回測內 anchor_date，優先使用資料表中的下一期；否則使用馬會摘要表下一期
    next_draw_date, next_draw_week = get_next_draw_info_by_anchor(df_all, anchor_date)
    if next_draw_date is None:
        next_draw_date, next_draw_week = res_func_marksix_next_BetDate.get_JC_next_Date()

    print(
        f"/> 下一期預測(anchor={anchor_date}) => 日期:{next_draw_date} 星期:{next_draw_week} "
        f"窗口:{window_list} 預測區間:{final_pred_sorted}"
    )

    return {
        "anchor_date": str(anchor_date),
        "next_draw_date": next_draw_date,
        "next_draw_week": next_draw_week,
        "window": window_list,
        "pred_interval": final_pred_sorted,
        "zone_score": dict(zone_score),
    }
    
    
def main():
    '''
    主程式入口 N1..N6 區間預測, 最終輸出結果：
    /> 下一期預測(anchor=2026-06-14) => 日期:2026-06-18 星期:4 窗口:[8] 預測區間:[0, 0, 1, 2, 3, 4]
    
    '''
    
    clear_screen()
    predict_next_draw_intervals(window_list=[8], alpha=1.0)
    return

if __name__ == "__main__":
    main()
