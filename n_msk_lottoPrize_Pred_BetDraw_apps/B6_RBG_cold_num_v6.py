import pandas as pd 
from pathlib import Path
import res_func_num_convert_RBG_Dict
import os

'''
14期不出現：死號，排除
9期不出現但不是14期死號：冷門配腳
7期不出現但不是9期冷號：副配腳

最後 1-49 RBG篩選 死號 > 冷門配腳 > 副配腳 > 熱門候選號
        
'''

# 取得目前檔案所在目錄
current_dir = Path(__file__).resolve().parent

# 讀取歷史開獎資料，包含日期和號碼。
def load_data_func():
    df_ = pd.read_csv(
        current_dir.parent / "A_msk_lottery_data_folder" / "M2_last_upgrade_lotto_data.csv"
    )
    df_all = df_.iloc[:, [0, 1, 2, 3, 4, 5, 6, 7]]  # ndate, N1..N6 + N7
    return df_all


def gen_RBG_1To49_group_list():
    ''' 自生產生 1-49 號球的 RBG 分組字典，key 是顏色索引（0=R, 1=B, 2=G），value 是該顏色的號碼列表。'''
    num_list = [num for num in range(1, 50)]
    rbg_123_group = res_func_num_convert_RBG_Dict.res_List_To_rbg_Dict_func(num_list)
    return rbg_123_group
   
    
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


def get_rbg_sub_group_dict():
    """自定 RBG 分組 組合，回傳 R/B/G 的子分組字典。
    自定原則，是以 <10 and >40 分組，中間選號 11..38, 盡量平均分組，避免某些 R/B/G 顏色分組過多或過少。
    """
    return {
        1: {
            "R1": [1, 2, 7, 8],
            "R2": [12, 13, 18, 19, 23, 24, 29, 30, 34, 35],
            "R3": [40, 45, 46],
        },
        2: {
            "B1": [3, 4, 9, 10],
            "B2": [14, 15, 20, 25, 26, 31, 36, 37],
            "B3": [41, 42, 47, 48],
        },
        3: {
            "G1": [5, 6, 11],
            "G2": [16, 17, 21, 22, 27, 28, 32, 33, 38],
            "G3": [39, 43, 44, 49],
        },
    }


def group_candidates_by_rbg_sub_group(candidate_dict):
    """將 分組設定 RBG  {1:[...], 2:[...], 3:[...]} 
    候選號分成 R1/R2/R3 等子組。
    >>> R1: [1, 7, 8] /> 3 球
    >>> R2: [12, 19, 29, 30, 34, 35] /> 6 球
    >>> R3: [40, 45, 46] /> 3 球
    >>> B1: [3, 4, 9, 10] /> 4 球
    >>> B2: [14, 15, 20, 26, 36, 37] /> 6 球
    >>> B3: [41, 42, 47] /> 3 球
    >>> G1: [5, 6, 11] /> 3 球
    >>> G2: [16, 17, 21, 27, 28, 32, 33] /> 7 球
    >>> G3: [39, 43, 44] /> 3 球
    """
    sub_group_dict = get_rbg_sub_group_dict()
    grouped_dict = {}

    for color_key, sub_groups in sub_group_dict.items():
        candidate_set = set(candidate_dict.get(color_key, []))
        grouped_dict[color_key] = {}
        for group_name, group_nums in sub_groups.items():
            grouped_dict[color_key][group_name] = sorted(candidate_set & set(group_nums))

    return grouped_dict




''' -------- Main Function ------------------------------------------------ '''
def main():
    os.system("clear")
    # print('\n' + "=" * 60)
    df_all = load_data_func()
    
    # ---- Setting Parameters ----
    inp_last_matched_draw = 1  # <= 以最後一期為基準，回測前幾期（不包含當期）來找窗口期數集合
    start_draw = len(df_all) - inp_last_matched_draw
    max_window_draw =[7,9,14] # 每期最多回測前幾期來找窗口期數集合
    included_last_nRn = True  # 是否包含當期號碼來找窗口期數集合 (True: 包含當期，False: 不包含當期)
    """按 R/B/G 每色球數由多至少排序，同數量時維持 R、B、G 順序。"""
    
    # Rnu RBG 1,2,3 集合球追蹤，依窗口期數增加，直到收集到足夠的顏色球為止。
    for idx in range(start_draw, len(df_all)):
        dfs = df_all.iloc[:,0:].values  # 以最後一期為基準
        
        y_date = dfs[idx][0]  # 假設日期欄位名稱為 'date'
        y_num7 = dfs[idx][1:8]  # 下一期的 N1..N6 + N7 號碼列
        
        print('-'*30)
        print(f'>>> 第 {idx} 期 {y_date} 開獎號碼: {y_num7}')
        ''' 分析 回測 7,9,14 窗口期數內沒有出現過的 RBG 色球，是否有冷門色球趨勢。'''
        missing_by_window = {}
        for max_window in max_window_draw:
            r_color_balls = []  # 用來收集窗口期數內的 RBG 色球集合
            b_color_balls = []
            g_color_balls = []
            # print(f'>>> 第 {idx+1} 期 {y_date} 開獎號碼: {y_num7}，回測窗口期數: {max_window}')
            # -----查詢期數窗口內的 RBG 色球集合-----
            for window in range(1, max_window +1):
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
                r = dictRBG.get(0, [])
                b = dictRBG.get(1, [])
                g = dictRBG.get(2, [])

                r_color_balls.extend(to_int_set(r))
                b_color_balls.extend(to_int_set(b))
                g_color_balls.extend(to_int_set(g))
                
                
            # print('-' * 50)
            # 將窗口期數內的 RBG 色球集合轉成 set，方便後續找出沒有出現過的色球
            r_set = set(r_color_balls)
            b_set = set(b_color_balls)
            g_set = set(g_color_balls)
        
            # 自行產生 RBG 1-49 球 red, blue, green 分組 
            rbg_123_dict = gen_RBG_1To49_group_list()
            
            red_all_balls = rbg_123_dict.get(0, [])  # 所有紅色球的集合
            blue_all_balls = rbg_123_dict.get(1, [])  # 所有藍色球的集合
            green_all_balls = rbg_123_dict.get(2, [])  # 所有綠色球的集合
            red_all_balls = to_int_set(red_all_balls)
            blue_all_balls = to_int_set(blue_all_balls)
            green_all_balls = to_int_set(green_all_balls)
        
        
    
            # 找出沒有出現過的RBG 分色球
            missing_red_balls = sorted(red_all_balls - r_set)
            missing_blue_balls = sorted(blue_all_balls - b_set)
            missing_green_balls = sorted(green_all_balls - g_set)
            
            # 記錄回測窗口期數內沒有出現過的 RBG 色球集合，供後續分析冷門色球趨勢使用
            missing_by_window[max_window] = {
                "R": set(missing_red_balls),
                "B": set(missing_blue_balls),
                "G": set(missing_green_balls),
            }
            
            # print(f'=== 回測 {max_window} 期 沒有出現過的 RBG球=== ')
            # print(f'>>> 沒有出現過的-紅色球: {sorted(missing_red_balls)} /> {len(missing_red_balls)} 球')
            # print(f'>>> 沒有出現過的-藍色球: {sorted(missing_blue_balls)} /> {len(missing_blue_balls)} 球')
            # print(f'>>> 沒有出現過的-綠色球: {sorted(missing_green_balls)} /> {len(missing_green_balls)} 球\n')

        print('>>>>>>>> === 7,9,14 期,回測分析, RBG 冷門號分類 ===')
        all_balls_by_color = {
            "R": red_all_balls,
            "B": blue_all_balls,
            "G": green_all_balls,
        }
        dead_balls_dict = {}
        cold_candidates_dict = {}
        hot_candidates_dict = {}
        color_key_map = {"R": 1, "B": 2, "G": 3}
        for color in ["R", "B", "G"]:
            color_key = color_key_map[color]
            dead_14 = missing_by_window[14][color]
            cold_leg = missing_by_window[9][color] - dead_14
            sub_leg = missing_by_window[7][color] - missing_by_window[9][color]
            cold_candidates_set = cold_leg | sub_leg
            hot_candidates = all_balls_by_color[color] - dead_14 - cold_candidates_set

            dead_balls_dict[color_key] = sorted(dead_14)
            cold_candidates_dict[color_key] = sorted(cold_candidates_set)
            hot_candidates_dict[color_key] = sorted(hot_candidates)

            # print(f'{color} 14期死號，不提供候選: {sorted(dead_14)} /> {len(dead_14)} 球')
            # print(f'{color} 冷門配腳，9期未出但排除14期死號: {sorted(cold_leg)} /> {len(cold_leg)} 球')
            # print(f'{color} 副配腳，7期未出但排除9期未出: {sorted(sub_leg)} /> {len(sub_leg)} 球')
            # print(f'{color} 14期死球號: {dead_balls_dict[color_key]} /> {len(dead_balls_dict[color_key])} 球')
            # print(f'{color} 次冷候選號: {cold_candidates_dict[color_key]} /> {len(cold_candidates_dict[color_key])} 球')
            # print(f'{color} 熱門候選號: {hot_candidates_dict[color_key]} /> {len(hot_candidates_dict[color_key])} 球\n')

        '''
        14期不出現：死號，排除
        9期不出現但不是14期死號：冷門配腳
        7期不出現但不是9期冷號：副配腳
        
        最後 1-49 RBG篩選 死號 > 冷門配腳 > 副配腳 > 熱門候選號
        
        '''
        print(f'>>> RBG 14期死球號 Dict: {dead_balls_dict}')
        for k,v in dead_balls_dict.items():
            color = [color for color, key in color_key_map.items() if key == k][0]
            # if color == 'B':
            print(f'>>> 回測 RBG 14期死球號 - {color} 色球: {v} /> {len(v)} 球')
        print()
        
        print('已排除 14 期死球號,回測7,9 期,次冷候選號分析：')
        for k,v in cold_candidates_dict.items():
            color = [color for color, key in color_key_map.items() if key == k][0]
            # if color == 'B':
            print(f'>>> 回測次冷門候選號 - {color} 色球: {v} /> {len(v)} 球')

        print()
        
        print('已排除 14 期死球號, 篩選 7,9 期次冷號後，剩餘熱門候選號分析：')
        hot_candidates_grouped_dict = group_candidates_by_rbg_sub_group(hot_candidates_dict)
        print('熱門候選號 RBG 子分組：')
        for color_key in [1, 2, 3]:
            for group_name, nums in hot_candidates_grouped_dict[color_key].items():
                print(f'>>> {group_name}: {nums} /> {len(nums)} 球')
        print('=' * 60)
    
    return dead_balls_dict, cold_candidates_dict, hot_candidates_dict
    
if __name__ == "__main__":
    main()

'''
Red = R1:[1,2,7,8], R2:[12,13,18,19,23,24,29,30,34,35],R3:[40,45,46]
Blue = B1:[3,4,9,10], B2:[14,15,20,25,26,31,36,37], B3:[41,42,47,48]
Green = G1:[5,6,11], G2:[16,17,21,22,27,28,32,33,38] ,G3:[39,43,44,49]
'''
