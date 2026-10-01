import itertools

number = [2,5,6,7,8,9]
RC = 2
combinations = list(itertools.combinations(number, RC))

print(f"查詢 {len(number)} 個數字, 每組 {RC} 個, 總其有：{len(combinations)} 組\n")


print("詳細組合列表：")
for idx, comb in enumerate(combinations):
    print(f"/> {idx:>2}, {comb}")
    
    
'''
查詢 6 個數字, 每組 3 個, 總其有：20 組
查詢 5 個數字, 每組 3 個, 總其有：10 組
查詢 9 個數字, 每組 3 個, 總其有：84 組
'''
