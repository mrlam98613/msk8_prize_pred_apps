# -*- coding: utf-8 -*-
"""
A2_num49_interval_multi_BacktestPred_v2.py
多窗口集成 + 
10. 2026-06-30 | 窗口期：[8] | 真實:[1, 1, 1, 1, 2, 3] | 預測:[0, 0, 1, 2, 3, 4] | 命中:3
11. 2026-07-02 | 窗口期：[8] | 真實:[0, 1, 2, 3, 3, 4] | 預測:[0, 0, 1, 2, 3, 4] | 命中:5
12. 2026-07-05 | 窗口期：[8] | 真實:[0, 1, 1, 2, 3, 3] | 預測:[0, 0, 1, 2, 3, 4] | 命中:4
"""
from collections import defaultdict, Counter
import pandas as pd
from pathlib import Path
import os
import random

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


def build_final_pred_intervals(zone_score, fixed_interval_mode="head_tail"):
    """
    根據參數建立 6 個預測區間。

    fixed_interval_mode:
    - "head_tail": 固定 N1=0、N6=4
    - "tail_only": 只固定 N6=4
    - "none": 不固定 N1/N6
    """
    fixed_map = {
        "head_tail": [0, 4],
        "tail_only": [4],
        "none": [],
    }
    if fixed_interval_mode not in fixed_map:
        raise ValueError(f"未知 fixed_interval_mode: {fixed_interval_mode}")

    fixed_intervals = fixed_map[fixed_interval_mode]
    middle_count = 6 - len(fixed_intervals)
    sorted_zones = [z for z, _ in zone_score.most_common()]
    if not sorted_zones:
        sorted_zones = [0, 1, 2, 3, 4]

    active_zones = sorted_zones[:4]
    middle_pred = (active_zones * 6)[:middle_count]
    return sorted([*middle_pred, *fixed_intervals])


def main():
    clear_screen()
    df_all = load_data_func()
    inp_backtest_draw = 50  # 回測期數
    start_draw = len(df_all) - inp_backtest_draw
    window_list = [6]  # 多窗口集成
    included_last_nRn = False # 回測窗口, 不包含當期
    fixed_interval_mode = "none"  # "head_tail" / "tail_only" / "none"
    summary_results = []
    hit_draw_count = 0
    
    # 回測指定期數
    for idx in range(start_draw, len(df_all)):
        y_data = df_all.iloc[idx].values
        y_date = y_data[0]
        y_6_Num = [int(x) for x in y_data[1:7]]
        # y_spc7 = [int(x) for x in y_data[7:8]]
        # 取出N1..N6 的區間編號
        y_true_interval = get_num49_interval_map(y_6_Num)
        # 多窗口集成分數
        zone_score = Counter()
        
        # 取出回測窗口期數的資料，依窗口期數計算馬可夫轉移矩陣，並累加分數
        for get_window_draw in window_list:
            window_df = res_nDate_getPass_nRn_func(
                ndate=y_date,
                window_nRn=get_window_draw,
                included_last_nRn=included_last_nRn #不包含當期，因為要用當期資料來預測下一期
            )
            xlist_arr = get_x_val_list_func(window_df)
            
            if len(xlist_arr) < 2:
                continue
            interval_sequences = []
            for sublist in xlist_arr:
                num49_interval_index = get_num49_interval_map(sublist)
                interval_sequences.append(num49_interval_index)
            if len(interval_sequences) < 2:
                continue
            transition = build_markov_transition(interval_sequences)
            current_seq = interval_sequences[-1]
            score = predict_next_intervals(transition, current_seq, alpha=1.0)
            zone_score.update(score)
            
        # 產生預測區間組合。
        final_pred_sorted = build_final_pred_intervals(
            zone_score,
            fixed_interval_mode=fixed_interval_mode,
        )
        match_seq_count = sum((Counter(y_true_interval) & Counter(final_pred_sorted)).values())
        summary_results.append({
            "date": y_date,
            "window": str(window_list),
            "fixed_mode": fixed_interval_mode,
            "true_interval": y_true_interval,
            "pred_interval": final_pred_sorted,
            "hit": match_seq_count
        })
        
        print(f'窗口期：{window_list} ，目標期真實區間: {y_true_interval} ，預測區間：{final_pred_sorted}， 命中：{match_seq_count}')
        if match_seq_count >= 4:
            hit_draw_count += 1
    # 統計總結-----
    print("\n================ 預測核對總結統計 ================")
    print(f'本次回測窗口期數: {window_list}')
    print(f'固定區間模式: {fixed_interval_mode}')
    if len(summary_results) == 0:
        print("無可統計資料")
    else:
        total_cases = len(summary_results)
        total_hits = sum(x["hit"] for x in summary_results)
        avg_hit = total_hits / total_cases
        hit_dist = Counter(x["hit"] for x in summary_results)
        print(f'總期數: {total_cases}')
        print(f'總命中欄位: {total_hits}')
        print(f'平均命中欄位: {avg_hit:.3f}')
        print(f'命中分佈: {dict(sorted(hit_dist.items()))}')
        for i, row in enumerate(summary_results, 1):
            print(
                f'{i:>2}. {row["date"]} | 窗口期：{row["window"]} | '
                f'真實:{row["true_interval"]} | 預測:{row["pred_interval"]} | 命中:{row["hit"]}'
            )

    print(f'\n 回測:{inp_backtest_draw} 期： 預測區間模式=[0,4][4],{fixed_interval_mode}=[馬可夫隨機]， 命中區間 >=4 => {hit_draw_count} 欄/> ({(hit_draw_count/inp_backtest_draw)*100:.2f}%).\n')
if __name__ == "__main__":
    main()

'''
================ 預測核對總結統計 ================
總期數: 12
總命中欄位: 37
平均命中欄位: 3.083
命中分佈: {1: 1, 2: 3, 3: 4, 4: 2, 5: 2}
1. 2026-02-26 | 窗口期：8 | 真實:[0, 1, 1, 1, 3, 4] | 預測:[0, 0, 1, 1, 3, 4] | 命中:5
2. 2026-02-28 | 窗口期：8 | 真實:[0, 1, 3, 3, 4, 4] | 預測:[0, 0, 3, 3, 4, 4] | 命中:5
3. 2026-03-03 | 窗口期：8 | 真實:[0, 1, 1, 3, 3, 4] | 預測:[0, 0, 0, 1, 2, 4] | 命中:3
4. 2026-03-05 | 窗口期：8 | 真實:[0, 1, 2, 3, 4, 4] | 預測:[0, 0, 0, 2, 3, 4] | 命中:4
5. 2026-03-07 | 窗口期：8 | 真實:[1, 1, 1, 2, 2, 3] | 預測:[0, 0, 0, 3, 4, 4] | 命中:1
6. 2026-03-10 | 窗口期：8 | 真實:[0, 1, 2, 3, 3, 3] | 預測:[0, 0, 1, 3, 3, 4] | 命中:4
7. 2026-03-12 | 窗口期：8 | 真實:[0, 1, 1, 1, 2, 2] | 預測:[0, 0, 0, 1, 4, 4] | 命中:2
8. 2026-03-17 | 窗口期：8 | 真實:[1, 1, 2, 2, 4, 4] | 預測:[0, 2, 3, 3, 3, 4] | 命中:2
9. 2026-03-19 | 窗口期：8 | 真實:[0, 0, 0, 3, 4, 4] | 預測:[0, 1, 2, 2, 4, 4] | 命中:3
10. 2026-03-21 | 窗口期：8 | 真實:[0, 0, 1, 1, 2, 4] | 預測:[0, 2, 2, 3, 4, 4] | 命中:3
11. 2026-03-24 | 窗口期：8 | 真實:[0, 0, 2, 2, 4, 4] | 預測:[0, 0, 1, 1, 3, 4] | 命中:3
12. 2026-03-26 | 窗口期：8 | 真實:[1, 1, 2, 2, 2, 3] | 預測:[0, 0, 0, 1, 1, 4] | 命中:2

窗口期：[6, 8, 12] ，目標期真實區間: [0, 1, 1, 1, 3, 4] ，預測區間：[0, 0, 1, 2, 3, 4]， 命中：4
窗口期：[6, 8, 12] ，目標期真實區間: [0, 1, 3, 3, 4, 4] ，預測區間：[0, 0, 1, 2, 3, 4]， 命中：4
窗口期：[6, 8, 12] ，目標期真實區間: [0, 1, 1, 3, 3, 4] ，預測區間：[0, 0, 1, 3, 4, 4]， 命中：4
窗口期：[6, 8, 12] ，目標期真實區間: [0, 1, 2, 3, 4, 4] ，預測區間：[0, 0, 1, 3, 4, 4]， 命中：5
窗口期：[6, 8, 12] ，目標期真實區間: [1, 1, 1, 2, 2, 3] ，預測區間：[0, 0, 1, 3, 4, 4]， 命中：2
窗口期：[6, 8, 12] ，目標期真實區間: [0, 1, 2, 3, 3, 3] ，預測區間：[0, 0, 1, 3, 4, 4]， 命中：3
窗口期：[6, 8, 12] ，目標期真實區間: [0, 1, 1, 1, 2, 2] ，預測區間：[0, 0, 1, 2, 3, 4]， 命中：3
窗口期：[6, 8, 12] ，目標期真實區間: [1, 1, 2, 2, 4, 4] ，預測區間：[0, 0, 1, 2, 3, 4]， 命中：3
窗口期：[6, 8, 12] ，目標期真實區間: [0, 0, 0, 3, 4, 4] ，預測區間：[0, 0, 1, 2, 3, 4]， 命中：4
窗口期：[6, 8, 12] ，目標期真實區間: [0, 0, 1, 1, 2, 4] ，預測區間：[0, 0, 1, 2, 3, 4]， 命中：5
窗口期：[6, 8, 12] ，目標期真實區間: [0, 0, 2, 2, 4, 4] ，預測區間：[0, 0, 1, 2, 4, 4]， 命中：5
窗口期：[6, 8, 12] ，目標期真實區間: [1, 1, 2, 2, 2, 3] ，預測區間：[0, 0, 1, 2, 4, 4]， 命中：2

1. 2026-02-26 | 窗口期：[8] | 真實:[0, 1, 1, 1, 3, 4] | 預測:[0, 0, 1, 2, 3, 4] | 命中:4
2. 2026-02-28 | 窗口期：[8] | 真實:[0, 1, 3, 3, 4, 4] | 預測:[0, 0, 1, 2, 3, 4] | 命中:4
3. 2026-03-03 | 窗口期：[8] | 真實:[0, 1, 1, 3, 3, 4] | 預測:[0, 0, 1, 3, 4, 4] | 命中:4
4. 2026-03-05 | 窗口期：[8] | 真實:[0, 1, 2, 3, 4, 4] | 預測:[0, 0, 1, 3, 4, 4] | 命中:5
5. 2026-03-07 | 窗口期：[8] | 真實:[1, 1, 1, 2, 2, 3] | 預測:[0, 0, 1, 3, 4, 4] | 命中:2
6. 2026-03-10 | 窗口期：[8] | 真實:[0, 1, 2, 3, 3, 3] | 預測:[0, 0, 1, 3, 4, 4] | 命中:3
7. 2026-03-12 | 窗口期：[8] | 真實:[0, 1, 1, 1, 2, 2] | 預測:[0, 0, 1, 2, 3, 4] | 命中:3
8. 2026-03-17 | 窗口期：[8] | 真實:[1, 1, 2, 2, 4, 4] | 預測:[0, 0, 1, 2, 3, 4] | 命中:3
9. 2026-03-19 | 窗口期：[8] | 真實:[0, 0, 0, 3, 4, 4] | 預測:[0, 0, 1, 2, 3, 4] | 命中:4
10. 2026-03-21 | 窗口期：[8] | 真實:[0, 0, 1, 1, 2, 4] | 預測:[0, 0, 1, 2, 3, 4] | 命中:5
11. 2026-03-24 | 窗口期：[8] | 真實:[0, 0, 2, 2, 4, 4] | 預測:[0, 0, 1, 2, 3, 4] | 命中:4
12. 2026-03-26 | 窗口期：[8] | 真實:[1, 1, 2, 2, 2, 3] | 預測:[0, 0, 1, 2, 4, 4] | 命中:2

A1_v2.py 總結統計：
================ 預測核對總結統計 ================
總期數: 12
本次回測窗口期數: 8
總命中欄位: 37
平均命中欄位: 3.083
命中分佈: {1: 1, 2: 3, 3: 4, 4: 2, 5: 2}


A2_v2.py 總結統計：
================ 預測核對總結統計 ================
本次回測窗口期數: [8]
總期數: 12
總命中欄位: 43
平均命中欄位: 3.583
命中分佈: {2: 2, 3: 3, 4: 5, 5: 2}
'''
