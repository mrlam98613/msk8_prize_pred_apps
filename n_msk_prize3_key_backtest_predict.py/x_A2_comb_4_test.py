import math
import itertools
import pandas as pd
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR
CSV_OUTPUT_DIR = PROJECT_ROOT / "data"

NUM_MIN = 21
NUM_MAX = 31
TAKE_COUNT = 3

CSV_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

total_group = math.comb(NUM_MAX - NUM_MIN + 1, TAKE_COUNT)
print(f"產生組合 {NUM_MIN} to {NUM_MAX} 取 {TAKE_COUNT} 個數字的所有組合: {total_group}")
print('\n')
numbers = list(range(NUM_MIN, NUM_MAX + 1))
combinations = list(itertools.combinations(numbers, TAKE_COUNT))


# comb_list = []
# for combo in combinations:
#     comb_list.append(combo)
    # print(combo, end=' ')
    
# dfs = pd.DataFrame(comb_list, columns=[f"Num{i}" for i in range(1, TAKE_COUNT + 1)])
# dfs.to_csv(CSV_OUTPUT_DIR / "comb_1_to_9_take_3.csv", index=False)
    
'''
產生組合 1 to 9 取 2 個數字的所有組合: 36
產生組合 1 to 9 取 3 個數字的所有組合: 84
產生組合 10 to 20 取 2 個數字的所有組合: 55
產生組合 10 to 20 取 3 個數字的所有組合: 165
產生組合 21 to 31 取 2 個數字的所有組合: 55
產生組合 21 to 31 取 3 個數字的所有組合: 165

1-9 選 2  = 9C2  = 36
1-9 選 3  = 9C3  = 84

10-20 選 2 = 11C2 = 55
10-20 選 3 = 11C3 = 165

21-31 選 2 = 11C2 = 55
21-31 選 3 = 11C3 = 165

'''
