import math

'''
https://mark6app.github.io/bankercal

在 Python 中計算六合彩「膽拖」派彩，核心邏輯是使用 組合數公式 (
) 來計算中獎注數。由於膽拖投注固定了部分號碼（膽），剩餘的號碼必須從「拖」中產生。
核心計算公式
假設你買了 
 個「膽」和 
 個「拖」，並從中中了 
 個「膽」和 
 個「拖」：
總注數：
中獎注數 (中 
 個字)：

中特別獎注數：逻辑同上，但需區分「拖」中是否包含特別號碼。

'''
import math

def combinations(n, r):
    if r < 0 or r > n:
        return 0
    return math.comb(n, r)

def calculate_mark6_banker(bet_bankers, bet_legs, hit_banker=1, hit_legs=2, extra_number_banker=0, extra_number_legs=0):
    """
    bankers: 膽號碼 (set)
    legs: 拖號碼 (set)
    drawn_numbers: 6個攪出號碼 (set)
    extra_number: 特別號碼 (int)
    """
    B = bet_bankers
    L = bet_legs
    
    # 1. 計算總注數
    total_bets = combinations(L, 6 - B)
    
    # 2. 統計中獎情況
    # 輸入語意：
    # hit_banker / hit_legs = 命中數量（可包含特別號）
    # extra_number_banker / extra_number_legs = 該區是否命中特別號 (0/1)
    # 轉為「正選命中數」時，若該區有中特別號，需扣 1。
    if extra_number_banker and extra_number_legs:
        raise ValueError('特別號只能在膽或拖其中一邊，不能同時為 1')

    hit_bankers_main = hit_banker - (1 if extra_number_banker else 0)
    hit_legs_main = hit_legs - (1 if extra_number_legs else 0)

    if hit_bankers_main < 0 or hit_legs_main < 0:
        raise ValueError('命中數量與特別號設定不一致：命中數不能小於特別號數')
    
    # 檢查特別號碼在哪
    extra_in_banker = extra_number_banker # 0 or 1 True or False
    extra_in_legs = extra_number_legs # 0 or 1 = True or False
    
    results = {}
    
    # 獎項邏輯函數
    def count_wins(req_normal, req_extra):
        slots_from_legs = 6 - B
        needed_hit_legs = req_normal - hit_bankers_main

        # 拖內可用的「正選號碼」池（不含特別號）
        normal_legs_total = L - (1 if extra_in_legs else 0)
        normal_legs_hit = hit_legs_main
        normal_legs_miss = normal_legs_total - normal_legs_hit

        # 需要由拖補的非正選位數
        needed_miss_legs = slots_from_legs - needed_hit_legs

        if req_extra == 1:
            # 需要中特別號
            if extra_in_banker == 1:
                # 特別號在膽，已固定中出，不需佔用拖位
                return combinations(normal_legs_hit, needed_hit_legs) * combinations(normal_legs_miss, needed_miss_legs)
            if extra_in_legs == 1:
                # 特別號在拖，必須選中它，會佔用 1 個拖位
                return combinations(normal_legs_hit, needed_hit_legs) * combinations(normal_legs_miss, needed_miss_legs - 1)
            return 0

        # req_extra == 0: 不能含特別號
        if extra_in_banker == 1:
            # 特別號在膽且膽是固定入注，故不可能屬於「不含特別號」獎項
            return 0
        # 特別號在拖時，透過 normal_legs_* 自然排除
        return combinations(normal_legs_hit, needed_hit_legs) * combinations(normal_legs_miss, needed_miss_legs)

    # 各獎項計算
    results['頭獎'] = count_wins(6, 0)
    results['二獎'] = count_wins(5, 1)
    results['三獎'] = count_wins(5, 0)
    results['四獎'] = count_wins(4, 1)
    results['五獎'] = count_wins(4, 0)
    results['六獎'] = count_wins(3, 1)
    results['七獎'] = count_wins(3, 0)
    
    # 輸出總注數，中獎項目和注數
    return total_bets, results

'''
中獎結果：中 2 膽＝2 球，配腳 3 ＝ 2.5 球
總命中 4.5 球數
四獎: 4,800 x 1 注 = $ 4,800
五獎: 320 x 2 注 = $ 640
六獎: 160 x 4 注 = $ 640
七獎: 20 x 2 注 = $ 40
總派彩 $ 6,120
---
中獎結果：中 1 膽＝1 球，配腳 4 ＝ 3.5 球
總命中 4.5 球數
五獎: 320 x 1 注 = $ 320
六獎: 160 x 3 注 = $ 480
七獎: 20 x 3 注 = $ 60
總派彩 $ 860
以上 2 個條件都是 中 4.5 球，因中膽數不同，所以不同獎金。
'''


# ----Sart 膽拖投注條件設定與計算示例----
# 範例：2膽拖8腳，中2膽5拖，特別號碼在拖中且選中
# 膽拖投基查輸入 
banker = 3 #投注膽數量 1,2,3,4,5 膽
legs = 6 #投注配腳數量 1膽-6 leg-48 leg，2-5-47，3-4-46，4-3-45，5-2-44
bet_unit = 5 # 每注金額
# ----

# 膽拖中基條本輸入
# 注意：matched_* 為「命中數（可含特號）」。若 *_hit_special=1，表示該區命中中有 1 個是特別號。
matched_banker = 3 # 命中膽數量（含特號）
banker_hit_special = 1 # 0 or 1 # 膽中包含特別號
matched_legs = 4 # 命中配腳數量（含特號）
leg_hit_special = 0 # 0 or 1 # 配腳中包含特別號

# Call 總注數，派彩結果
total_draw, prize_result = calculate_mark6_banker(bet_bankers=banker, #投注膽
                                                  bet_legs=legs, #投注配腳
                                                  hit_banker=matched_banker, #命中膽數量
                                                  hit_legs=matched_legs, #命中配腳數量
                                                  extra_number_banker=banker_hit_special, #膽中包含特別號
                                                  extra_number_legs=leg_hit_special) #配腳中包含特別號

# 計算投注金額 = 總注數 x 每注金額
bet_amounts = total_draw * bet_unit

print('\n--- 六合彩膽拖投注計算 ---\n')
print(f'投注 {banker} 膽 + {legs} 配腳，總注數：{total_draw} X 每注 ${bet_unit} 注，總金額: {bet_amounts} 元\n')

prize_money = {
    '頭獎': None,
    '二獎': None,
    '三獎': None,
    '四獎': 9_600,
    '五獎': 640,
    '六獎': 320,
    '七獎': 40,
}

banker_ball = matched_banker - (0.5 if banker_hit_special else 0)
legs_ball = matched_legs - (0.5 if leg_hit_special else 0)
total_ball = banker_ball + legs_ball

print(f'中獎結果：中 {matched_banker} 膽＝{banker_ball:g} 球，配腳 {matched_legs} ＝ {legs_ball:g} 球')
print(f'膽 + 配腳 總命中 {total_ball:g} 球數')
print('- 1 獎，必須要膽號全中正號。')
print('- 2，3 獎，取決膽號命中數量及配腳組合，不因命中總球數直接固定派彩。')
print('- 膽拖投注會因投注膽號及配腳命中條件，計算中獎注數及獎金。\n')

total_payout = 0
for prize in ['頭獎', '二獎', '三獎', '四獎', '五獎', '六獎', '七獎']:
    count = prize_result.get(prize, 0)
    if count <= 0:
        continue
    unit_payout = prize_money[prize]
    if unit_payout is None:
        print(f'{prize}: 獎金等馬會公佈 x {count} 注（獎金等馬會公佈）')
        continue
    if bet_unit == 5:
        unit_payout //= 2
    payout = unit_payout * count
    total_payout += payout
    print(f'{prize}: {unit_payout:,} x {count} 注 = $ {payout:,}')

print(f'總派彩 $ {total_payout:,}')

print('--- End of Calculation ---\n')
