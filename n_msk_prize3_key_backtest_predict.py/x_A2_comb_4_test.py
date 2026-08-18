import math
import itertools
import pandas as pd
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR
CSV_OUTPUT_DIR = PROJECT_ROOT / "data"

NUM_MIN = 10
NUM_MAX = 20
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
    
