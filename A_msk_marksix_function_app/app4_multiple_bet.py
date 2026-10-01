import math


# 組合公式  (nCr)
def calculate_mark6_win(bet_num, hit_main, hit_special, bet_type=10):
    '''
    bet_num = 複式投注號,7,8,9..N (選擇的號碼個數)
    hit_main = 中獎正選號碼數量
    hit_special = 是否中獎特別號碼 (True/False)
    bet_type = 每注金額 (10 或 5)
    '''
    
    n = bet_num
    if n < 7:
        return "號碼數量不足7個"
    
    # 1. 計算總注數 (C(n, 6))
    total_bets = math.comb(n, 6)
    total_cost = total_bets * bet_type
    
    results = {}
    result_msgs = []
    total_payout = 0
    total_count = 0
    sp = 1 if hit_special else 0
    hit_num = hit_main # 中獎正選號碼數量
    
    #  定義獎項對應的中獎條件 (正選號碼數量, 特別號碼數量)
    prizes = {
        1:(6,0),
        2:(5,1),
        3:(5,0),
        4:(4,1),
        5:(4,0),
        6:(3,1),
        7:(3,0)
    }
    ''' 獎項對應的獎金 (以 $10 注為基準) 頭獎、二獎、三獎、四獎、五獎、六獎、七獎 '''
    prizes_money = {
    1: 10_000_000,
    2: 1_000_000,
    3: 100_000,
    4: 9_600,
    5: 640,
    6: 320,
    7: 40
    }
    
    
    ''' 計算中獎注數的邏輯：
    中獎注數 = C(中獎正選號碼數量, x) * C(是否中獎特別號碼數量, y) * C(剩餘未中獎號碼數量, 6-x-y)
    其中 x 和 y 分別是獎項對應的正選號碼數量和特別號碼數量 '''
    for prize,(x,y) in prizes.items():
        # 排除不可能情況
        if x > hit_num or y > sp or (6-x-y) > (bet_num-hit_num-sp):
            count = 0
        else:
            # 計算中獎注數 = C(中獎正選號碼數量, x) * C(是否中獎特別號碼數量, y) * C(剩餘未中獎號碼數量, 6-x-y)
            count = math.comb(hit_num,x) * math.comb(sp,y) * math.comb(bet_num-hit_num-sp, 6-x-y)
            print(f'中 {prize} 獎 : C ({hit_num},{x}) * C ({sp},{y}) * C ({bet_num-hit_num-sp},{6-x-y}) = {count} 注')
        
        # 如果中獎注數大於0，則計算派彩金額並記錄結果
        if count > 0:
            
            # 查詢獎位置對應的獎金
            results[prizes_money[prize]] = count #1..7中獎的注數
            total_count += count # 累計總中獎注數
            
            ''' 計算總派彩金額 = 中獎注數 * 每注獎金'''
            if bet_type == 5:
                # $ 5 注
                half_payout = (prizes_money[prize] // 2) * count # $5 注獎金 $10 元一半
                total_payout += half_payout # 累計總派彩金額
                result_msg = f'/> 中 {prize} 獎, {count} 注 x 每 ${bet_type}注,獎金 $ {(prizes_money[prize] // 2):,} = $ {half_payout:,}'
                
            else:
                # $ 10 注
                full_payout = count * prizes_money[prize]
                total_payout += full_payout
                result_msg = f'/> 中 {prize} 獎, {count} 注 x 每 ${bet_type}注,獎金 $ {(prizes_money[prize]):,} = $ {full_payout:,}'
                
                
            
            result_msgs.append(result_msg)
        
    if not result_msgs:
        if not result_msgs:
            result_msgs.append('/> 不符合中獎條件，注數 0')
        
    return result_msgs, total_count, total_payout, total_bets, total_cost
    
# --投注條件
multiple = 7
bet_type = 10 # $10 注或 $5 注
# --- 模擬中獎情況
matched = 4
has_hit_special = 1 # 0 or 1

# 計算中獎有沒有特號
if has_hit_special:
    total_win_num = matched + 0.5
else:
    total_win_num = matched 
    
payout_results, total_count, total_payout, total_bets, total_cost = calculate_mark6_win(multiple, matched, has_hit_special, bet_type=bet_type)

print('\n=== 香港六合彩複式投注計算機 ===')
print(f'複式投注 {multiple} 號碼，', f'每注金額 = $ {bet_type}')
print(f'總注數: {total_bets} 注，投注金額: $ {total_cost}\n')
print(f'中獎正號數 {matched} 個')
print(f'中特別號碼 {has_hit_special}') 
print(f'中獎 {total_win_num} 球， (正號 + 特別號)\n')
print(f'-> 中獎派彩結果：')
payout = '\n'.join(payout_results)
print(f'派彩計算：\n{payout}')
print(f'/> 中獎注數：{total_count} 注')
print(f'/> 總派彩金額：$ {total_payout:,}\n\n')