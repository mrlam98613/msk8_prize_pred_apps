"""
種子投注策略引擎模組
========================
整合下列邏輯：
1. 上期中獎種子號提取
2. 下期區間位置預測（N1..N6 分布）
3. RBG 三色球與窗口期分析
4. 窗口期最少的兩色候選球選取
5. 種子號與顏色候選去重
6. 按區間預測位置隨機填號
7. 與近 30 期開獎號重覆檢查（≥5 顆就重生，最多重試 40 次）

主要輸出函式：
  - generate_next_bets_with_strategy(): 結合種子與策略產生下期投注
"""

import random
from itertools import combinations

import func2_RBG_collect_5Balls_DrawWindows # 取RBG分析結果的副程式
import res_predict_N1_N6_interval_BackTest # 區間預測副程式


def interval_to_numbers(interval_id):
    """
    將號碼區間 ID 轉換為對應的號碼池。
    
    Args:
        interval_id (int): 區間 ID，0~4 對應 1~49 的五個 10 位區間
                          0=[1-10], 1=[11-20], 2=[21-30], 3=[31-40], 4=[41-49]
    
    Returns:
        list: 該區間內的號碼列表
    """
    zone_map = {
        0: list(range(1, 11)),      # 1-10
        1: list(range(11, 21)),     # 11-20
        2: list(range(21, 31)),     # 21-30
        3: list(range(31, 41)),     # 31-40
        4: list(range(41, 50)),     # 41-49
    }
    return zone_map.get(int(interval_id), [])


def pick_top2_colors_by_window(summary_windows, rbg_collect):
    """
    從 RBG 三種顏色中選出窗口期最少的前兩色。
    
    窗口期越少 = 近期該顏色組合開獎越頻繁 = 強勢色
    
    Args:
        summary_windows (list): [Red窗口期, Blue窗口期, Green窗口期]
        rbg_collect (dict): {1: Red球號列, 2: Blue球號列, 3: Green球號列, 0: 窗口期摘要}
    
    Returns:
        tuple: (top2_color_names, top2_windows, merged_candidates)
               - top2_color_names: ['Blue', 'Red'] 等前兩色名稱
               - top2_windows: 對應的窗口期數
               - merged_candidates: 兩色合併後的候選球號（已排序去重）
    """
    # 色彩名稱對應字典
    color_names = {1: "Red", 2: "Blue", 3: "Green"}
    color_rows = []

    # 將 RBG 三色與其窗口期打包
    for color_idx, window in enumerate(summary_windows, start=1):
        if window is None:
            continue
        balls = rbg_collect.get(color_idx, [])
        color_rows.append((color_idx, int(window), balls))

    # 按窗口期升序排列（窗口期小 = 近期強勢）
    color_rows.sort(key=lambda x: (x[1], x[0]))
    
    # 取前兩色
    top2 = color_rows[:2]

    # 提取前兩色的名稱、窗口期、候選球
    top2_color_names = [color_names[c] for c, _, _ in top2]
    top2_windows = [w for _, w, _ in top2]
    # 合併兩色的候選球號，去重並排序
    merged_candidates = sorted({int(n) for _, _, balls in top2 for n in balls})
    
    return top2_color_names, top2_windows, merged_candidates


def _normalize_interval(pred_interval):
    """
    正規化區間預測結果為長度 6 的列表。
    
    如果預測不足 6 個區間位置，補充預設區間 [0,1,2,3,4,4] 的不足部分。
    
    Args:
        pred_interval (list): 預測的區間位置列表（可能長度 < 6）
    
    Returns:
        list: 長度恰好為 6 的區間位置列表
    """
    # 提取有效的區間值（過濾 None）
    vals = [int(x) for x in pred_interval[:6] if x is not None and isinstance(x, (int, float, str))]
    
    # 若已有 6 個有效值，直接返回
    if len(vals) >= 6:
        return vals[:6]
    
    # 不足則用預設區間填補
    fallback = [0, 1, 2, 3, 4, 4]
    need = 6 - len(vals)
    return vals + fallback[:need]


def _recent_30_draw_sets(df_all, anchor_date):
    """
    取出近 30 期的開獎號碼集合（含特別號）。
    
    用於後續重覆檢查。
    
    Args:
        df_all (DataFrame): 全歷史開獎資料
        anchor_date (str): 錨點日期，取該日期含以前的最近 30 期
    
    Returns:
        list: 30 個集合物件，每個集合代表一期的 6 個正號（含特別號）
    """
    # 篩選至錨點日期（含）的所有記錄
    df_hist = df_all[df_all["ndate"].astype(str) <= str(anchor_date)]
    
    # 只取最近 30 期
    df_hist = df_hist.tail(30)
    
    draw_sets = []
    for _, row in df_hist.iterrows():
        # N1~N6 + N7（特別號）合併成集合
        draw_sets.append(set(int(x) for x in row.iloc[1:7].values.tolist() if isinstance(x, (int, float, str))))
    
    return draw_sets


def has_high_overlap_last30(bet_nums, df_all, anchor_date, threshold=5):
    """
    檢查投注號碼與近 30 期開獎號碼的重覆程度。
    
    邏輯：如果投注與任一期的重覆號碼數 >= 門檻值，回傳 True（視為重覆度高）
    
    Args:
        bet_nums (list): 投注的 6 個號碼
        df_all (DataFrame): 全歷史開獎資料
        anchor_date (str): 錨點日期
        threshold (int): 重覆門檻，預設 5 個號碼即判定為過度重覆
    
    Returns:
        bool: True 表示重覆度高（應重新生成），False 表示可接受
    """
    # 投注號碼轉集合
    bet_set = set(int(x) for x in bet_nums if isinstance(x, (int, float, str)))
    
    # 逐期檢查是否與歷史期數的重覆數超過門檻
    for draw_set in _recent_30_draw_sets(df_all, anchor_date):
        # 求交集（重覆的號碼數）
        if len(bet_set & draw_set) >= threshold:
            # 發現重覆數 >= 門檻，立即返回 True
            return True
    
    # 全部檢查完都沒超過門檻
    return False


def build_bet_with_seed(seed_nums, pred_interval, top2_candidates, seed_base, verbose=False):
    """
    以種子號 + 區間預測 + RBG 候選池組合產生一注投注。
    
    組合邏輯（優先級遞減）：
      1. 若種子數已 >= 6，直接取前 6 個
      2. 逐區間填號：優先從「該區間且在 RBG 候選」抽；不足時退到該區間任何號；
         最後退到全域 1-49 任選
      3. 所有號碼去重
    
    Args:
        seed_nums (list): 中獎種子號碼（如 [35, 44]）
        pred_interval (list): 預測區間位置（6 元素，如 [0,1,2,3,4,4]）
        top2_candidates (list): RBG 前兩色候選球號（如 [2,3,7,8,9,...]）
        seed_base (int): 隨機種子基數（用於固定化隨機結果）
    
    Returns:
        list: 6 個排序後的投注號碼
    """
    # 種子號轉集合
    def _to_int_safe(val):
        if isinstance(val, (int, float, str)):
            return int(val)
        raise TypeError(f"種子號碼型別錯誤: {val} ({type(val)})")
    seed_set = set(_to_int_safe(x) for x in seed_nums)
    
    # 若種子數已 >= 6，直接返回前 6 個
    if len(seed_set) >= 6:
        return sorted(list(seed_set))[:6]

    # 正規化區間（確保長度 6）
    zones = list(_normalize_interval(pred_interval))

    # 扣除種子所在區間：每個種子號對應其區間，從 zones 中移除一個對應槽位
    remaining_zones = zones[:]
    for s in seed_set:
        s_zone = next((z for z in range(5) if s in interval_to_numbers(z)), None)
        if s_zone is not None and s_zone in remaining_zones:
            remaining_zones.remove(s_zone)

    # 計算還需填補的號碼數
    target_count = 6 - len(seed_set)
    used = set(seed_set)  # 記錄已使用號碼（包含種子）
    
    # RBG 候選去掉已用的種子號
    candidate_set = set(_to_int_safe(x) for x in top2_candidates) - seed_set

    # 建立獨立的亂數生成器，避免全域狀態污染
    rng = random.Random(seed_base)
    
    # 依 seed_base 旋轉剩餘區間順序（增加多樣性）
    if remaining_zones:
        offset = seed_base % len(remaining_zones)
        remaining_zones = remaining_zones[offset:] + remaining_zones[:offset]
    zones = remaining_zones

    fill_nums = []
    all_nums = list(range(1, 50))
    zone_names = {0: '1-10', 1: '11-20', 2: '21-30', 3: '31-40', 4: '41-49'}

    # 逐區間填號
    for zone in zones:
        if len(fill_nums) >= target_count:
            break

        # 取該區間的號碼池
        zone_nums = interval_to_numbers(zone)
        
        # 優先池：該區間 AND 在 RBG 候選 AND 未用過
        prefer_pool = [n for n in zone_nums if n in candidate_set and n not in used]
        
        # 次級池：該區間 AND 未用過（不限候選）
        zone_pool = [n for n in zone_nums if n not in used]

        # 按優先級選號，並記錄退回狀況
        if prefer_pool:
            pick = rng.choice(prefer_pool)
        elif zone_pool:
            # RBG 候選在此區間無球，退回區間全域
            if verbose:
                print(f'  [區間提示] zone {zone}({zone_names[zone]}) RBG候選無球，退回區間全域選號')
            pick = rng.choice(zone_pool)
        else:
            # 該區間所有號已用盡，跨區補位
            fallback_pool = [n for n in all_nums if n not in used]
            pick = rng.choice(fallback_pool)
            pick_zone = next((z for z in range(5) if pick in interval_to_numbers(z)), -1)
            if verbose:
                print(f'  [區間提示] zone {zone}({zone_names[zone]}) 球數不足，跨區補位 → 選到 {pick}(zone {pick_zone}:{zone_names.get(pick_zone,"?")})')

        fill_nums.append(pick)
        used.add(pick)

    # 若仍不足 6 個（理論上不應發生），從未用號補齊
    while len(fill_nums) < target_count:
        pool = [n for n in all_nums if n not in used]
        pick = rng.choice(pool)
        fill_nums.append(pick)
        used.add(pick)

    # 返回排序後的完整投注（種子 + 補號）
    return sorted(list(seed_set) + fill_nums)


def generate_bet_with_recheck(seed_nums, 
                              pred_interval, 
                              top2_candidates, 
                              df_all, anchor_date, seed_base,
                              overlap_threshold=5, max_tries=40, verbose=False):
    """
    產生投注並反覆檢查與近 30 期的重覆程度。
    
    若重覆度過高則重新生成，最多重試 max_tries 次。
    
    Args:
        seed_nums (list): 種子號碼
        pred_interval (list): 預測區間
        top2_candidates (list): RBG 候選球
        df_all (DataFrame): 全歷史開獎資料
        anchor_date (str): 錨點日期
        seed_base (int): 隨機種子基數
        overlap_threshold (int): 重覆門檻，預設 5
        max_tries (int): 最大重試次數，預設 40
    
    Returns:
        list: 6 個排序後的投注號碼（通過重覆檢查或達到重試上限）
    """
    # 迴圈重試 max_tries 次
    for k in range(max_tries):
        # 每次用不同的種子基數生成，確保多樣性
        bet = build_bet_with_seed(seed_nums, pred_interval, top2_candidates, seed_base + k)
        
        # 檢查是否重覆度過高
        if not has_high_overlap_last30(bet, df_all, anchor_date, threshold=overlap_threshold):
            # 通過檢查，返回此注
            return bet
    
    # 若重試次數已達上限，最後一次強制用特殊種子產生並返回（第此注顯示區間提示）
    return build_bet_with_seed(seed_nums, pred_interval, top2_candidates, seed_base + 999, verbose=verbose)


def get_strategy_context(anchor_date, window_list=None, collect_balls_break=4, draw_same_color=2, included_last_nRn=False):
    """
    取得本期投注的策略上下文（區間預測 + RBG 分析）。
    
    整合呼叫區間預測 + RBG 收集副程式，回傳單一字典。
    
    Args:
        anchor_date (str): 本期開獎日期（以此日期往前取 N 期做預測）
        window_list (list): 區間預測的窗口期列表，預設 [8]
        collect_balls_break (int): RBG 收集時的取球數門檻，預設 4
        draw_same_color (int): 同期同色球數條件，預設 2（==2 球視為熱門）
        included_last_nRn (bool): RBG 收集時是否包含錨點期本身，預設 False
    
    Returns:
        dict: 含以下鍵值：
              {
                'pred_interval': [0,1,2,3,4,4],  # 正規化後的區間預測
                'top2_names': ['Blue', 'Red'],    # 前兩色名稱
                'top2_windows': [12, 23],         # 前兩色窗口期
                'top2_candidates': [2,3,7,8,...] # 前兩色合併候選球
              }
    """
    # 預設窗口期列表
    if window_list is None:
        window_list = [8]

    # ── 呼叫區間預測副程式 ──
    interval_pred = res_predict_N1_N6_interval_BackTest.predict_next_draw_intervals(
        window_list=window_list,
        alpha=1.0,
        anchor_date=str(anchor_date),
    )

    # 安全提取預測結果（可能為 None）
    pred_interval = []
    if interval_pred is not None:
        pred_interval = interval_pred.get("pred_interval", [])

    # ── 呼叫 RBG 收集副程式 ──
    rbg_collect = func2_RBG_collect_5Balls_DrawWindows.main(
        y_date=str(anchor_date),
        collect_balls_break=collect_balls_break,
        draw_same_color=draw_same_color,
        included_last_nRn=included_last_nRn,
    )
    
    # 提取 RBG 窗口期摘要
    summary_windows = rbg_collect.get(0, [])
    
    # ── 選取前兩色 ──
    top2_names, top2_windows, top2_candidates = pick_top2_colors_by_window(summary_windows, rbg_collect)

    # 整裝回傳
    return {
        "pred_interval": _normalize_interval(pred_interval),
        "top2_names": top2_names,
        "top2_windows": top2_windows,
        "top2_candidates": top2_candidates,
        "rbg_collect": rbg_collect,  # 包含三色的完整信息
    }


def _fallback_seed_bets(sorted_matched, last_bet_vals, seed_base):
    """
    當策略資料不足時，以原始種子投注規則做為備用方案。
    
    規則不變：
      - 中 0 球：沿用上一注
      - 中 1 球：1 注（1 種子 + 5 隨機）
      - 中 2 球：2 注（各 1 種子 + 5 隨機）
      - 中 3 球：3 注（每注各帶 1 個種子）
      - 中 4+ 球：最多 3 注（由前 4 個種子混合成二連種子）
    
    Args:
        sorted_matched (list): 中獎種子號
        last_bet_vals (list): 上期投注（無中獎時沿用）
        seed_base (int): 隨機種子基數
    
    Returns:
        list: 下期投注列表（可能 1~3 注）
    """
    n_matched = len(sorted_matched)
    next_bets = []

    # ── 中 0 球 ──
    if n_matched == 0:
        return [last_bet_vals]

    # ── 中 1 球 ──
    if n_matched == 1:
        avail = [n for n in range(1, 50) if n not in sorted_matched]
        rng = random.Random(seed_base)
        lucky = rng.sample(avail, 5)
        return [sorted(sorted_matched + lucky)]

    # ── 中 2 球 ──
    if n_matched == 2:
        for i, seed in enumerate(sorted_matched):
            avail = [n for n in range(1, 50) if n != seed]
            rng = random.Random(seed_base + i)
            lucky = rng.sample(avail, 5)
            next_bets.append(sorted([seed] + lucky))
        return next_bets

    # ── 中 3 球：3 個單種子，各產生一注 ──
    if n_matched == 3:
        for i, seed in enumerate(sorted_matched[:3]):
            avail = [n for n in range(1, 50) if n != seed]
            rng = random.Random(seed_base + i)
            lucky = rng.sample(avail, 5)
            next_bets.append(sorted([seed] + lucky))
        return next_bets

    # ── 中 4+ 球：從前 4 球混合二連種子，最多 3 注 ──
    pairs = list(combinations(sorted_matched[:4], 2))[:3]
    for i, pair in enumerate(pairs):
        seed_pair = list(pair)
        avail = [n for n in range(1, 50) if n not in seed_pair]
        rng = random.Random(seed_base + i)
        lucky = rng.sample(avail, 4)
        next_bets.append(sorted(seed_pair + lucky))
    
    return next_bets


def generate_next_bets_with_strategy(sorted_matched, last_bet_vals, anchor_date, df_all, seed_base,
                                   collect_balls_break=4, draw_same_color=2):
    """
    主策略引擎：根據上期中獎種子號，結合區間預測與 RBG 分析，生成下期投注。
    
    優先流程：
      1. 若中 0 球，回傳上一注
      2. 取本期策略上下文（區間 + RBG）
      3. 若策略資料不足，回退到備用規則（純種子隨機）
      4. 按種子數決定投注組數：
         - 中 1 球：1 組（1 種子 + 策略補號）
         - 中 2 球：2 組（各 1 種子 + 策略補號）
         - 中 3 球：3 組（各 1 種子 + 策略補號）
         - 中 4+ 球：最多 3 組（由前 4 個種子混合二連種子 + 策略補號）
      5. 每注進行近 30 期重覆檢查，若過高則重試（最多 40 次）
    
    Args:
        sorted_matched (list): 上期中獎的種子號碼（已排序）
        last_bet_vals (list): 上期投注（無中獎時沿用）
        anchor_date (str): 本期開獎日期
        df_all (DataFrame): 全歷史開獎資料
        seed_base (int): 隨機種子基數
        collect_balls_break (int): RBG 收集球數門檻，預設 4
        draw_same_color (int): 同期同色球數條件，預設 2
    
    Returns:
        list: 下期投注列表（每注一個 6 元素列表）
    """
    # ── 中 0 球：沿用上一注，直到命中才產生種子號 ──
    if len(sorted_matched) == 0:
        return [last_bet_vals]

    # ── 取策略上下文（有種子號時才需要）──
    ctx = get_strategy_context(anchor_date, collect_balls_break=collect_balls_break, draw_same_color=draw_same_color)
    pred_interval = ctx.get("pred_interval", [])
    top2_candidates = ctx.get("top2_candidates", [])

    # ── 策略資料不足 => 回退到備用規則 ──
    if len(pred_interval) < 6 or len(top2_candidates) == 0:
        return _fallback_seed_bets(sorted_matched, last_bet_vals, seed_base)

    # ── 根據種子數決定投注組數 ──
    seed_groups = []
    
    if len(sorted_matched) == 1:
        # 中 1 球：1 組
        seed_groups = [[sorted_matched[0]]]
    elif len(sorted_matched) == 2:
        # 中 2 球：2 組（各 1 種子）
        seed_groups = [[sorted_matched[0]], [sorted_matched[1]]]
    elif len(sorted_matched) == 3:
        # 中 3 球：3 組，各 1 種子
        seed_groups = [[seed] for seed in sorted_matched[:3]]
    else:
        # 中 4+ 球：由前 4 球混合二連種子，最多 3 組
        seed_groups = [list(p) for p in combinations(sorted_matched[:4], 2)][:3]

    # ── 逐組生成投注（含重覆檢查）──
    bets = []
    for i, seeds in enumerate(seed_groups):
        # 以不同的 seed_base 產生不同投注，確保多樣性
        bet = generate_bet_with_recheck(
            seed_nums=seeds,
            pred_interval=pred_interval,
            top2_candidates=top2_candidates,
            df_all=df_all,
            anchor_date=anchor_date,
            seed_base=seed_base + i,
            overlap_threshold=5,        # 與近 30 期重覆 >=5 個就重新生成
            max_tries=40,               # 最多重試 40 次
            verbose=True,
        )
        bets.append(sorted(bet))

    return bets
