import pandas as pd 
from pathlib import Path
import os
import res_func_num_convert_RBG_Dict
import res_func_marksix_next_BetDate

"""
找出下期中獎號中的 R,B,G color 顏色球追縱窗口期。
1. 讀取歷史開獎資料，包含日期和號碼。
2. 對每期開獎，從最近的幾期開始，逐步增加窗口期數，直到找到一個窗口期數集合，使得集合內的號碼與下期中獎號的交集至少有5個球。
3. 統計每期使用的窗口期數集合，以及命中球數分布。
4. 輸出結果，分析窗口期數集合對命中球數的影響。
"""


def clear_screen():
    os.system("clear")


# 取得目前檔案所在目錄
current_dir = Path(__file__).resolve().parent

# 讀取歷史開獎資料，包含日期和號碼。
def load_data_func():
    df_ = pd.read_csv(
        current_dir.parent / "A_msk_lottery_data_folder" / "M2_last_upgrade_lotto_data.csv"
    )
    df_all = df_.iloc[:, [0, 1, 2, 3, 4, 5, 6, 7]]  # ndate, N1..N6 + N7
    return df_all

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
    res_df_list = dfs.iloc[:, 1:8].values # 取 N1..N6 + N7 的號碼列，轉成 numpy array，再轉成 list
    return res_df_list


def rank_color_ball_stats_func(ball_stats):
    """將同色候選球依熱門/冷門與窗口先後排序。"""
    # 排序優先序：
    # 1) appear_window_count 越多越前面（多個窗口都出現 = 跨期穩定可靠）
    # 2) 有 hot_count 的球優先於純冷門球
    # 3) hot_count 越高越前面
    # 4) best_hot_window 越小越前面（越早窗口出現視為越熱）
    # 5) 若熱門指標相同，再看 cold_count 與 best_cold_window
    # 6) 最後用球號做穩定排序，確保結果可重現
    ranked_items = sorted(
        ball_stats.items(),
        key=lambda item: (
            -item[1].get("appear_window_count", 0),
            -int(item[1]["hot_count"] > 0),
            -item[1]["hot_count"],
            item[1]["best_hot_window"] if item[1]["best_hot_window"] is not None else 999,
            -item[1]["cold_count"],
            item[1]["best_cold_window"] if item[1]["best_cold_window"] is not None else 999,
            item[0],
        ),
    )

    ranked_all = [ball for ball, _ in ranked_items]
    # 熱門清單：至少出現過一次 >=3 同色條件
    hot_only = [ball for ball, stats in ranked_items if stats["hot_count"] > 0]
    # 冷門清單：沒有熱門紀錄，只有 ==1 同色條件
    cold_only = [ball for ball, stats in ranked_items if stats["hot_count"] == 0 and stats["cold_count"] > 0]
    return ranked_all, hot_only, cold_only


def alloc_quota_by_ratio(total_balls, ratio_map, active_colors):
    """依比例分配球數，回傳每個顏色應取球數。"""
    use_ratio = {c: max(float(ratio_map.get(c, 0)), 0.0) for c in active_colors}
    ratio_sum = sum(use_ratio.values())

    if ratio_sum <= 0:
        equal_ratio = {c: 1.0 for c in active_colors}
        use_ratio = equal_ratio
        ratio_sum = float(len(active_colors))

    raw_quota = {c: (total_balls * use_ratio[c] / ratio_sum) for c in active_colors}
    quota_int = {c: int(raw_quota[c]) for c in active_colors}

    remain = total_balls - sum(quota_int.values())
    if remain > 0:
        # 將餘數優先配給小數點較大的顏色
        frac_sorted = sorted(
            active_colors,
            key=lambda c: (raw_quota[c] - quota_int[c], use_ratio[c]),
            reverse=True,
        )
        for i in range(remain):
            quota_int[frac_sorted[i % len(frac_sorted)]] += 1

    return quota_int


def auto_ratio_from_windows(color_window_summary, active_colors):
    """依各顏色窗口中位數反比計算權重。窗口越小，權重越高。"""
    median_map = {}
    for c in active_colors:
        ws = [w for w in color_window_summary.get(c, []) if w is not None]
        if ws:
            median_map[c] = float(pd.Series(ws).median())
        else:
            median_map[c] = None

    valid_medians = [m for m in median_map.values() if m and m > 0]
    fallback_median = float(pd.Series(valid_medians).median()) if valid_medians else 1.0

    weight_map = {}
    for c in active_colors:
        med = median_map[c] if (median_map[c] and median_map[c] > 0) else fallback_median
        weight_map[c] = 1.0 / med

    return weight_map, median_map


def pick_balls_by_quota(
    per_color_balls,
    quota_map,
    total_balls,
    fill_with_other_colors_if_short=True,
):
    """依顏色配額產生最終選號；可選擇不足時是否由其他顏色補滿。"""
    selected = []
    used = set()
    color_order = [1, 2, 3]

    # 先按配額取各顏色球
    for color in color_order:
        balls = per_color_balls.get(color, [])
        need = int(quota_map.get(color, 0))
        taken = 0
        for n in balls:
            if n not in used:
                selected.append(n)
                used.add(n)
                taken += 1
                if taken >= need:
                    break

    # 不足時依設定決定是否補滿
    if fill_with_other_colors_if_short and len(selected) < total_balls:
        for color in color_order:
            for n in per_color_balls.get(color, []):
                if n not in used:
                    selected.append(n)
                    used.add(n)
                    if len(selected) >= total_balls:
                        break
            if len(selected) >= total_balls:
                break

    return selected[:total_balls]

''' -------- Main Function -------- '''
def main(y_date='2026-04-21', collect_balls_break=5, draw_same_color=2, included_last_nRn=False):
    # clear_screen()
    # print('\n' + "=" * 60)
    df_all = load_data_func()
    
    # ---- Setting Parameters ----
    inp_last_matched_draw = 1  # <= 以最後一期為基準，回測前幾期（不包含當期）來找窗口期數集合
    start_draw = len(df_all) - inp_last_matched_draw
    max_window_draw = 30  # 測試最大窗口期數，合條件就 break
    collect_balls_break = int(collect_balls_break)  # 收集球數，至少要收集多少顏色球才停止增加窗口期數
    
    ''' 
    如果該期有 3 球相同顏色就執行收集 [R,R,B,B,G,G + RBG], 該期有一顏色球 >=3 球才取樣本。
    '''
    draw_same_color = int(draw_same_color)  # 同一期開號內 ==N 球同色，才收集該期的顏色球號
    
    
    # 可改成單一數字 (1/2/3) 或清單 ([1,2,3])。
    sel_color = [1, 2, 3]
    color_names = {1: "Red", 2: "Blue", 3: "Green"}
    if isinstance(sel_color, int):
        sel_colors = [sel_color]
    else:
        sel_colors = [c for c in sel_color if c in color_names]

    summary_windows_list = []  # 紀錄每次回測期，所需的窗口期數集合
    RBG_color_balls_collect = []  # 紀錄每次回測期，單一顏色球集合
    # 回傳資料格式：
    # 0 -> [R_window, B_window, G_window]
    # 1/2/3 -> 各色排序後候選球（熱門優先）
    # hot/cold -> 各色熱門與冷門候選球清單
    # stats -> 每顆球的熱冷統計明細（供外部策略二次利用）
    RBG_Colors_and_Window_summary_dict = {
        0: [],
        1: [],
        2: [],
        3: [],
        "hot": {1: [], 2: [], 3: []},
        "cold": {1: [], 2: [], 3: []},
        "stats": {1: {}, 2: {}, 3: {}},
    }  # 傳出，window、RBG 3 色集合球、熱門冷門排序。
    # -----------
    
    
    # Rnu RBG 1,2,3 集合球追蹤，依窗口期數增加，直到收集到足夠的顏色球為止。
    for sel_color in sel_colors:
        
        used_window = None
        colorBalls_set = set()  # 保留最終不重複候選球
        ball_stats = {}

        for window in range(1, max_window_draw + 1):
            """不包含當期，回測前 window 期資料"""
            res_df = res_nDate_getPass_nRn_func(ndate=y_date, window_nRn=window, included_last_nRn=included_last_nRn)
            # print(f'/> 窗口期數: {window}，回測資料：\n{res_df}')
            res_xlist_arr = get_x_val_list_func(res_df)
            if len(res_xlist_arr) == 0:
                continue

            # 每增加一個窗口，只處理該窗口新納入的那一期，避免重複累計同一期資料。
            sublist = res_xlist_arr[0]
            # print(f'/> 窗口期數: {window}，回測資料：{sublist}')
            
            dictRBG = res_func_num_convert_RBG_Dict.res_List_To_rbg_Dict_func(sublist)

            color_idx = sel_color - 1 # 因為 R=1, B=2, G=3，但 list 索引是 0,1,2
            max_list = [int(x) for x in dictRBG[color_idx]]

            # 熱門判定：同一期同色球數 == draw_same_color（預設 3）
            ''' 重要修改每期只取 == 1, == 2 球'''
            if len(max_list) == draw_same_color:
                for ball in max_list:
                    stats = ball_stats.setdefault(
                        ball,
                        {
                            "hot_count": 0,
                            "cold_count": 0,
                            "best_hot_window": None,
                            "best_cold_window": None,
                            "appear_window_count": 0,  # 出現幾個不同窗口期
                        },
                    )
                    stats["hot_count"] += 1
                    stats["appear_window_count"] += 1  # 每個窗口只計一次
                    if stats["best_hot_window"] is None or window < stats["best_hot_window"]:
                        stats["best_hot_window"] = window
                    colorBalls_set.add(ball)

            # 冷門判定：同一期該色剛好只有 1 顆球
            elif len(max_list) == 1:
                ball = max_list[0]
                stats = ball_stats.setdefault(
                    ball,
                    {
                        "hot_count": 0,
                        "cold_count": 0,
                        "best_hot_window": None,
                        "best_cold_window": None,
                        "appear_window_count": 0,  # 出現幾個不同窗口期
                    },
                )
                stats["cold_count"] += 1
                stats["appear_window_count"] += 1  # 每個窗口只計一次
                if stats["best_cold_window"] is None or window < stats["best_cold_window"]:
                    stats["best_cold_window"] = window
                colorBalls_set.add(ball)

            
            # 如果收集到足夠的顏色球，則停止增加窗口期數
            if len(colorBalls_set) >= collect_balls_break:
                used_window = window
                break

        # 修正問題1：無論是否達標，均 append 已收集球（保持索引對齊）
        # 依熱冷統計產生排序：colorBalls_list = 熱門優先的完整候選池
        colorBalls_list, hot_balls, cold_balls = rank_color_ball_stats_func(ball_stats)
        RBG_color_balls_collect.append(colorBalls_list) # 單一色集合球列
        
        
        # print(f'/> RBG:{sel_color}: {colorBalls_list}')
        # 傳出此單一色集合球，窗口期數。
        summary_windows_list.append(used_window)
        
        RBG_Colors_and_Window_summary_dict[sel_color] = colorBalls_list
        RBG_Colors_and_Window_summary_dict["hot"][sel_color] = hot_balls
        RBG_Colors_and_Window_summary_dict["cold"][sel_color] = cold_balls
        RBG_Colors_and_Window_summary_dict["stats"][sel_color] = ball_stats

   
    
    RBG_Colors_and_Window_summary_dict[0] = summary_windows_list
    # print(f'/> 窗口期數集合: {summary_windows_list}')
    # ''' 輸出結果：每個顏色的窗口期數，以及依熱門冷門排序的候選球清單。 '''
    # for k in [1, 2, 3, "hot", "cold"]:
    #     v = RBG_Colors_and_Window_summary_dict[k]
    #     print(f'/> {k} : {v}')
        
    # 回傳 窗口期數集合，以及 RBG 3 色集合球。
    ''' 程式重點 '''
    # print(f'收集到 RBG >=5 球，的窗口期數 R,B,G : {summary_windows_list} / 期:')
    return RBG_Colors_and_Window_summary_dict
    # 窗口期數集合: [12, 17, 3] 12=red 17=blue 3=green
    # 12 期才收集到 5 顆紅球，
    # 17 期才收集到 5 顆藍球，
    # 3 期就收集到 5 顆綠球。
if __name__ == "__main__":
    main()

'''
每粒球在 stats 內有 5 個欄位：

hot_count
代表這粒球在多少個窗口中，符合同色 3 球條件（你設定的熱門條件）。

cold_count
代表這粒球在多少個窗口中，符合同色 1 球條件（你設定的冷門條件）。

best_hot_window
這粒球最早在哪個窗口被判為 hot。數字越細，代表越早出現熱門訊號。

best_cold_window
這粒球最早在哪個窗口被判為 cold。

appear_window_count
這粒球總共出現在多少個不同窗口（穩定度指標）。越高通常表示跨期更穩定。

實際用途：

在 func2 本身：用來排序球（不只 hot/cold，還看穩定度與最早窗口）
位置：func2_RBG_collect_5Balls_DrawWindows.py:50
在 func3：直接拿 stats 做分數加權
位置：func3_multi_func_pred_BackTest_V1.py:226
一句話總結：
hot/cold 係分類；stats 係可量化特徵，俾後續策略做更細緻的加權與排序。
'''