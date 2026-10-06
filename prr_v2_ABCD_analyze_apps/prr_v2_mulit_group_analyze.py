from pathlib import Path
import csv
from collections import Counter
from itertools import combinations
from typing import Optional, TypedDict

''' 
A,B,C,D, (1-9) , (10-20) , (21-31) , (32-40), (分單雙分佈)
1-9,   [1,3,5,7,9], [2,4,6,8] = 9 球
10-20, [11,13,15,17,19], [10,12,14,16,18,20] = 11 球
21-31, [21,23,25,27,29,31], [22,24,26,28,30] = 11 球
32-40, [33,35,37,39], [32,34,36,38,40] = 9 球 

'''

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
M6_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"
M4_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M4_lotto_prize_summary.csv"


# MODE 可選："backtest" 或 "predict"。
MODE = "backtest"
BACKTEST_DRAW_COUNT_LIST = [1]
WINDOW_DRAW_COUNT_LIST = [18]

# SELECT_GROUPS 可選 1,2,3,4；例如 (1,) 只查 1-9，(1,2,3,4) 全組別。
'''
SELECT_GROUPS = (1,)           # 只選 1-9
SELECT_GROUPS = (1, 2, 3)      # 自選 1-31
SELECT_GROUPS = (1, 2, 3, 4)   # 全組別 1-40
SELECT_GROUPS = (2, 4)         # 只選 10-20 + 32-40
'''
SELECT_GROUPS = (1,2,3,4) # select group index =1

# 每一期在指定範圍內有多少球才算符合條件。
COMBINATION_TAKE_COUNT = 2
BIRTHDAY_NUM_MATCH_MODE = ">="

# LOTTO_LIST=True 時，每期將所選組別號碼合併成一個 [] 顯示；False 則按組別分開顯示。
''' backtest,窗口期不包括核對期,預留核對預測
False = 近 10期:2026-08-27,[12,17],[25,31],[*35] /> 4.5 球
Treu = 近 10期:2026-08-27,[12,17,25,31,*35] /> 4.5 球
'''
LOTTO_LIST = True

# PRINT_BACKTEST_MODE 可選 "detail" 或 "simple"。
# detail 會打印窗口期明細；simple 只打印每期核對、預測球與命中統計。
PRINT_BACKTEST_MODE = "detail" #"detail" 或 "simple"。

# -------------------------
# PRIZE_OPTION=3 即顯示三獎中獎注數 prize3。
PRIZE_OPTION = 3 # 設定要顯示的獎項，3 即顯示三獎中獎注數。
PRIZE_PRINT_SHOW = False

# 是否顯示 A-D 分組內的單雙、R/B/G 分組累計。
PRINT_ODD_EVEN_GROUP_ANALYSIS = False
PRINT_RBG_GROUP_ANALYSIS = False

GROUPS = {
    1: ("1-9", 1, 9), # 9 球
    2: ("10-20", 10, 20), # 11 球
    3: ("21-31", 21, 31), # 11 球 
    4: ("32-40", 32, 40), # 9 球
    # Total 40 球 
}
GROUP_CODES = {
    1: "A",
    2: "B",
    3: "C",
    4: "D",
}

# 
class DrawRow(TypedDict):
    date: str
    nums: list[int]
    special: Optional[int]
    prize_count: float


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    ''' 讀取 CSV 並清理欄位名稱與文字空白。 '''
    if not path.exists():
        raise FileNotFoundError(f"找不到 CSV：{path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames:
            reader.fieldnames = [name.strip().lstrip("\ufeff") for name in reader.fieldnames]
        return [
            {(key or "").strip().lstrip("\ufeff"): (value or "").strip() for key, value in row.items()}
            for row in reader
        ]


def to_int(value: object, default: int = 0) -> int:
    ''' 安全轉換數值為 int，失敗時回傳 default。 '''
    if not isinstance(value, (int, float, str)):
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def to_float(value: object, default: float = 0.0) -> float:
    ''' 安全轉換數值為 float，失敗時回傳 default。 '''
    if not isinstance(value, (int, float, str)):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_m6_row(row: dict[str, str]) -> DrawRow:
    ''' 將 M6 原始 CSV 一行轉成標準 DrawRow。 '''
    special = to_int(row.get("N7"))
    return {
        "date": row.get("nDdate", ""),
        "nums": [to_int(row.get(f"N{index}")) for index in range(1, 7)],
        "special": special if 1 <= special <= 49 else None,
        "prize_count": to_float(row.get(f"prize{PRIZE_OPTION}")),
    }


def read_draws() -> list[DrawRow]:
    ''' 讀取所有有效歷史開獎紀錄。 '''
    return [row for row in [parse_m6_row(raw) for raw in read_csv_rows(M6_CSV)] if row["date"]]


def read_next_draw_date() -> str:
    ''' 從 M4 摘要讀取下一期開獎日期。 '''
    rows = read_csv_rows(M4_CSV)
    return rows[-1].get("next_draw_date", "") if rows else ""


def format_nums(
    nums: list[int],
    special: Optional[int] = None,
    show_special_placeholder: bool = False,
    special_placeholder: str = "_",
) -> str:
    ''' 格式化號碼列表，特號以 *號碼 放在最後。 '''
    parts = [str(num) for num in nums]
    if special is not None:
        parts.append(f"*{special}")
    elif show_special_placeholder:
        parts.append(special_placeholder)
    return "[" + ",".join(parts) + "]"


def format_hit_nums(nums: list[int], special: Optional[int] = None) -> str:
    ''' 格式化命中號碼，不加入特號佔位符。 '''
    return format_nums(nums, special, False)


def format_ball_count(value: float) -> str:
    ''' 格式化球數，整數不顯示小數點。 '''
    return str(int(value)) if value.is_integer() else f"{value:g}"


def prize_text(value: float) -> str:
    ''' 格式化獎項注數，整數不顯示小數點。 '''
    return str(int(value)) if value.is_integer() else f"{value:g}"


def prize_print_text(row: DrawRow) -> str:
    ''' 依 PRIZE_PRINT_SHOW 決定是否顯示獎項注數。 '''
    if not PRIZE_PRINT_SHOW:
        return ""
    return f"，Pz{PRIZE_OPTION}: {prize_text(row['prize_count'])}"


def selected_nums(row: DrawRow, start_num: int, end_num: int) -> list[int]:
    ''' 取出某組範圍內的正號 N1..N6。 '''
    return sorted(num for num in row["nums"] if start_num <= num <= end_num)


def selected_special(row: DrawRow, start_num: int, end_num: int) -> Optional[int]:
    ''' 判斷特號 N7 是否落在指定分組範圍內。 '''
    special = row["special"]
    if special is None:
        return None
    return special if start_num <= special <= end_num else None


def display_ball_count(normal_count: int, special: Optional[int]) -> float:
    ''' 計算顯示球數；正號達 3 球時特號加 0.5。 '''
    if special is not None and normal_count >= 3:
        return normal_count + 0.5
    return float(normal_count)


def normalize_select_groups() -> tuple[int, ...]:
    ''' 檢查 SELECT_GROUPS 型別與組別範圍；可單選一組。 '''
    if isinstance(SELECT_GROUPS, int):
        raise ValueError(
            "SELECT_GROUPS 需要 tuple/list，例如 (1,) 或 (1, 2, 3, 4)。"
            "你現在寫成 (1)，Python 會當作整數；若只寫單一組要用 (1,)。"
        )
    if not isinstance(SELECT_GROUPS, (tuple, list)):
        raise ValueError("SELECT_GROUPS 需要 tuple/list，例如 (1,) 或 (1, 2, 3, 4)。")

    group_ids = tuple(SELECT_GROUPS)
    if not group_ids:
        raise ValueError("SELECT_GROUPS 最少需要選 1 個組別，例如 (1,) 或 (1, 2, 3, 4)。")
    for group_id in group_ids:
        if group_id not in GROUPS:
            raise ValueError(f"SELECT_GROUPS 只可選 1,2,3,4；錯誤值：{group_id}")
    return group_ids


def validate_print_backtest_mode() -> None:
    ''' 檢查 backtest 打印模式，只可使用 detail 或 simple。 '''
    if PRINT_BACKTEST_MODE not in ("detail", "simple"):
        raise ValueError('PRINT_BACKTEST_MODE 只可設定為 "detail" 或 "simple"。')


def selected_groups() -> list[tuple[str, int, int]]:
    ''' 依 SELECT_GROUPS 取得實際使用的組別設定。 '''
    groups: list[tuple[str, int, int]] = []
    for group_id in normalize_select_groups():
        groups.append(GROUPS[group_id])
    return groups


def row_ball_count(row: DrawRow) -> float:
    ''' 計算某期开奖在所選組別中的總球數。 '''
    normal_count = sum(
        len(selected_nums(row, start_num, end_num))
        for _name, start_num, end_num in selected_groups()
    )
    has_special = any(
        selected_special(row, start_num, end_num) is not None
        for _name, start_num, end_num in selected_groups()
    )
    return display_ball_count(normal_count, row["special"] if has_special else None)


def row_selected_normal_count(row: DrawRow) -> int:
    ''' 計算某期开奖在所選組別中的正號 N1..N6 數量。 '''
    return sum(
        len(selected_nums(row, start_num, end_num))
        for _name, start_num, end_num in selected_groups()
    )


def row_selected_normal_nums(row: DrawRow) -> list[int]:
    ''' 取得某期开奖在所選組別中的正號 N1..N6。 '''
    nums: list[int] = []
    for _name, start_num, end_num in selected_groups():
        nums.extend(selected_nums(row, start_num, end_num))
    return sorted(set(nums))


def is_matched(count: int) -> bool:
    ''' 判斷單組正號數量是否符合查詢條件。 '''
    if BIRTHDAY_NUM_MATCH_MODE == "==":
        return count == COMBINATION_TAKE_COUNT
    if BIRTHDAY_NUM_MATCH_MODE == "<=":
        return count <= COMBINATION_TAKE_COUNT
    return count >= COMBINATION_TAKE_COUNT


def group_result_text(row: DrawRow, name: str, start_num: int, end_num: int) -> str:
    ''' 產生單組詳細顯示文字，包含組名與單組球數。 '''
    nums = selected_nums(row, start_num, end_num)
    if not is_matched(len(nums)):
        return f"[{name}] [] /> 0 球"
    special = selected_special(row, start_num, end_num)
    ball_count = display_ball_count(len(nums), special)
    return f"[{name}] {format_nums(nums, special)} /> {format_ball_count(ball_count)} 球"


def group_only_text(row: DrawRow, name: str, start_num: int, end_num: int) -> str:
    ''' 產生單組簡潔顯示文字，只保留 [] 號碼。 '''
    nums = selected_nums(row, start_num, end_num)
    special = selected_special(row, start_num, end_num)
    return format_nums(nums, special)


def lotto_list_text(row: DrawRow) -> str:
    ''' 將所選組別內的正號合併成一個 []，特號不在所選組別時用 _ 佔位。 '''
    nums: list[int] = []
    special: Optional[int] = None
    for _name, start_num, end_num in selected_groups():
        nums.extend(selected_nums(row, start_num, end_num))
        group_special = selected_special(row, start_num, end_num)
        if group_special is not None:
            special = group_special
    return format_nums(sorted(set(nums)), special)


def row_result_text(row: DrawRow) -> str:
    ''' 產生一期的所有選中組別顯示文字與總球數。 '''
    if LOTTO_LIST:
        return f"{lotto_list_text(row)} /> {format_ball_count(row_ball_count(row))} 球"

    group_text = "，".join(
        group_only_text(row, name, start_num, end_num)
        for name, start_num, end_num in selected_groups()
    )
    return f"{group_text} /> {format_ball_count(row_ball_count(row))} 球"


def all_check_nums_text(row: DrawRow) -> str:
    ''' 格式化核對期 N1..N7；只顯示 1-40，41-49 用底線代替。 '''
    parts = [str(num) if 1 <= num <= 40 else "_" for num in sorted(row["nums"])]
    if row["special"] is not None:
        special_text = str(row["special"]) if 1 <= row["special"] <= 40 else "_"
        parts.append(f"*{special_text}")
    return "[" + ",".join(parts) + "]"


def query_mode_text() -> str:
    """產生標題用的查詢模式文字。"""
    group_ids = normalize_select_groups()
    if group_ids == tuple(GROUPS.keys()):
        return "全組別"
    return "自選組別"


def print_query_setting() -> None:
    """打印本次執行的模式與主要查詢參數。"""
    group_ids = normalize_select_groups()
    mode_text = "全組別" if group_ids == tuple(GROUPS.keys()) else "自選組別"
    print("====== p_v1 1-40 開獎紀錄基查 ======")
    print(f"運作模式：{MODE}")
    print(f"查詢模式：{mode_text} {group_ids}")
    print(f"回測打印模式：{PRINT_BACKTEST_MODE}")
    print(f"回測期列表：{BACKTEST_DRAW_COUNT_LIST}")
    print(f"窗口期列表：{WINDOW_DRAW_COUNT_LIST}")
    print(f"符合條件：範圍內號碼數量 {BIRTHDAY_NUM_MATCH_MODE}{COMBINATION_TAKE_COUNT} 球")
    print("查詢號碼：N1..N7，N7 特號以 * 顯示")
    display_text = "合併號碼" if LOTTO_LIST else "分組號碼"
    prize_show_text = f"，Pz{PRIZE_OPTION}" if PRIZE_PRINT_SHOW else ""
    print(f"顯示欄位：開獎日期，{display_text}，N球{prize_show_text}")
    print()


def print_draw_rows(
    draws: list[DrawRow],
    window_rows: list[tuple[int, DrawRow]],
    target_index: int,
) -> None:
    """打印窗口期內每一期的組別分布。"""
    for row_index, row in window_rows:
        if not is_matched(row_selected_normal_count(row)):
            continue
        rank = target_index - row_index + 1
        print(
            f"近 {rank}期：{row['date']}，{row_result_text(row)}"
            f"{prize_print_text(row)}"
        )


def matched_window_count(window_rows: list[tuple[int, DrawRow]]) -> int:
    ''' 統計窗口期內符合查詢條件的期數。 '''
    return sum(1 for _row_index, row in window_rows if is_matched(row_selected_normal_count(row)))


def print_matched_window_count(window_rows: list[tuple[int, DrawRow]]) -> None:
    ''' 打印窗口期合條件期數統計。 '''
    matched_count = matched_window_count(window_rows)
    window_total = len(window_rows)
    matched_percent = (matched_count / window_total * 100) if window_total else 0
    print(
        f"結果合條件 {BIRTHDAY_NUM_MATCH_MODE} {COMBINATION_TAKE_COUNT} 球，"
        f"查詢 {matched_count} / {window_total} 期統計 = {matched_count}期 "
        f"({matched_percent:.0f} %)"
    )


def sorted_hot_cold_nums(counter: Counter[int], nums: list[int]) -> list[tuple[int, int]]:
    """依窗口期出現次數由熱到冷排序；同次數用號碼細至大排序。"""
    return sorted(((num, counter.get(num, 0)) for num in nums), key=lambda item: (-item[1], item[0]))


def format_hot_cold_pairs(pairs: list[tuple[int, int]]) -> str:
    """格式化號碼出現次數，例如 [9(10),5(8)]。"""
    return "[" + ",".join(f"{num}({count})" for num, count in pairs) + "]"


def print_group_odd_even_hot_cold(window_rows: list[tuple[int, DrawRow]]) -> None:
    """按 A/B/C/D 分組，統計窗口期正號 N1..N6 的單雙冷熱門排列。"""
    if not PRINT_ODD_EVEN_GROUP_ANALYSIS:
        return

    num_counter: Counter[int] = Counter()
    for _row_index, row in window_rows:
        for num in row["nums"]:
            if 1 <= num <= 40:
                num_counter[num] += 1

    print("----- A-D 分組單雙冷熱門累計 -----")
    for group_id in normalize_select_groups():
        name, start_num, end_num = GROUPS[group_id]
        group_code = GROUP_CODES[group_id]
        odd_nums = [num for num in range(start_num, end_num + 1) if num % 2 == 1]
        even_nums = [num for num in range(start_num, end_num + 1) if num % 2 == 0]
        odd_text = format_hot_cold_pairs(sorted_hot_cold_nums(num_counter, odd_nums))
        even_text = format_hot_cold_pairs(sorted_hot_cold_nums(num_counter, even_nums))
        print(f"{group_code}組 {name}：{odd_text}，{even_text}")


def rbg_color_id(num: int) -> int:
    """依六合彩 R/B/G 公式回傳 1=R、2=B、3=G。"""
    adjusted_num = num - 1
    return (((adjusted_num // 10) + adjusted_num) % 6 // 2) + 1


def print_group_rbg_hot_cold(window_rows: list[tuple[int, DrawRow]]) -> None:
    """按 A/B/C/D 分組，統計窗口期正號 N1..N6 的 R/B/G 顏色冷熱門排列。"""
    if not PRINT_RBG_GROUP_ANALYSIS:
        return

    num_counter: Counter[int] = Counter()
    for _row_index, row in window_rows:
        for num in row["nums"]:
            if 1 <= num <= 40:
                num_counter[num] += 1

    color_labels = {
        1: "R",
        2: "B",
        3: "G",
    }
    print("----- A-D 分組 R/B/G 顏色冷熱門累計 -----")
    for group_id in normalize_select_groups():
        name, start_num, end_num = GROUPS[group_id]
        group_code = GROUP_CODES[group_id]
        color_parts: list[str] = []
        for color_id in (1, 2, 3):
            color_nums = [
                num
                for num in range(start_num, end_num + 1)
                if rbg_color_id(num) == color_id
            ]
            color_text = format_hot_cold_pairs(sorted_hot_cold_nums(num_counter, color_nums))
            color_parts.append(f"{color_labels[color_id]}{color_text}")
        print(f"{group_code}組-RBG {name}：" + "，".join(color_parts))


def fortune_candidate_pool(window_rows: list[tuple[int, DrawRow]]) -> tuple[list[int], list[tuple[int, int, int]]]:
    ''' 分析 fortune_keys，先用單號高頻取 6 球，再產生 C(6,3) 組合。 '''
    matched_nums_list = [
        row_selected_normal_nums(row)
        for _row_index, row in window_rows
        if is_matched(row_selected_normal_count(row))
    ]

    num_counter: Counter[int] = Counter()
    for nums in matched_nums_list:
        num_counter.update(nums)

    if not num_counter:
        return [], []

    candidate_nums = [
        num
        for num, _count in sorted(num_counter.items(), key=lambda item: (-item[1], item[0]))
    ][:6]

    selected_all_nums = sorted(
        {
            num
            for _name, start_num, end_num in selected_groups()
            for num in range(start_num, end_num + 1)
        }
    )
    for num in selected_all_nums:
        if len(candidate_nums) == 6:
            break
        if num not in candidate_nums:
            candidate_nums.append(num)

    candidate_nums = sorted(candidate_nums[:6])
    candidate_combs = list(combinations(candidate_nums, 3))
    return candidate_nums, candidate_combs


def fortune_comb_hits(candidate_combs: list[tuple[int, int, int]], check_row: DrawRow) -> list[tuple[int, int, int]]:
    ''' 用核對期正號 N1..N6 檢查 C(6,3) 組合是否全中。 '''
    check_nums = set(row_selected_normal_nums(check_row))
    return [comb for comb in candidate_combs if set(comb).issubset(check_nums)]


def fortune_check_text(candidate_combs: list[tuple[int, int, int]], check_row: DrawRow) -> str:
    ''' 產生 fortune_keys C(6,3) 核對文字。 '''
    hit_combs = fortune_comb_hits(candidate_combs, check_row)
    hit_text = "，".join(format_nums(list(comb)) for comb in hit_combs) if hit_combs else "[]"
    return f"c(6,3) 核對：命中：{hit_text} /> {len(hit_combs)} 組"


def print_fortune_keys_analysis(window_rows: list[tuple[int, DrawRow]]) -> list[tuple[int, int, int]]:
    ''' 打印 fortune_keys 單號高頻與 C(6,3) 預測組合，並回傳 20 組候選。 '''
    matched_count = sum(1 for _row_index, row in window_rows if is_matched(row_selected_normal_count(row)))
    candidate_nums, candidate_combs = fortune_candidate_pool(window_rows)

    print("----- fortune_keys 分析 -----")
    print(f"fortune_keys 合條件期數：{matched_count}")
    if not candidate_nums:
        print("單號高頻球：[]")
        print("候選 6 球：[]")
        print("C(6,3) 預測組合：[]")
        return []

    single_counter: Counter[int] = Counter()
    for _row_index, row in window_rows:
        if is_matched(row_selected_normal_count(row)):
            single_counter.update(row_selected_normal_nums(row))
    single_text = "，".join(
        f"{num}({count})"
        for num, count in sorted(single_counter.items(), key=lambda item: (-item[1], item[0]))
    )
    comb_text = "，".join(format_nums(list(comb)) for comb in candidate_combs)
    print(f"單號高頻球：{single_text}")
    print(f"候選 6 球：{format_nums(candidate_nums)}")
    print(f"C(6,3) 預測組合：{comb_text}")
    return candidate_combs


def print_backtest_window(
    draws: list[DrawRow],
    check_index: int,
    backtest_count: int,
    window_count: int,
    backtest_index: int,
    total_backtest_count: int,
) -> None:
    """打印單一期 backtest 窗口資料與核對日期。"""
    check_row = draws[check_index]
    display_backtest_index = total_backtest_count - backtest_index + 1
    window_start_index = max(0, check_index - window_count)
    window_rows = [
        (row_index, row)
        for row_index, row in enumerate(draws[window_start_index:check_index], start=window_start_index)
    ]

    if PRINT_BACKTEST_MODE == "simple":
        print(f"核對日期 ： {check_row['date']}: {all_check_nums_text(check_row)}")
        return

    print(
        f"======[回測 {display_backtest_index}] "
        f"{query_mode_text()}，參數，回測期= {backtest_count}，N1..N7，窗口期 = {window_count} ======"
    )
    print("backtest：窗口期不包括核對期，預留核對預測")
    print_draw_rows(draws, window_rows, check_index - 1)
    print_matched_window_count(window_rows)
    print_group_odd_even_hot_cold(window_rows)
    print_group_rbg_hot_cold(window_rows)
    print()


def print_predict_window(draws: list[DrawRow], window_count: int, next_draw_date: str) -> None:
    """打印 predict 模式最後窗口期資料。"""
    latest_index = len(draws) - 1
    window_start_index = max(0, latest_index - window_count + 1)
    window_rows = [
        (row_index, row)
        for row_index, row in enumerate(draws[window_start_index:latest_index + 1], start=window_start_index)
    ]
    print(f"====== {query_mode_text()}，預測模式，N1..N7，窗口期 = {window_count} ======")
    print("predict：只顯示最後窗口期分析，不輸出預測球")
    print_draw_rows(draws, window_rows, latest_index)
    print_matched_window_count(window_rows)
    print_group_odd_even_hot_cold(window_rows)
    print_group_rbg_hot_cold(window_rows)
    print(f"下期開獎日期：{next_draw_date or '未知'}")
    print()


def main() -> None:
    """主流程：驗證參數、讀取資料，並按 MODE 執行。"""
    try:
        normalize_select_groups()
        validate_print_backtest_mode()
    except ValueError as exc:
        raise SystemExit(f"參數錯誤：{exc}") from exc

    draws = read_draws()
    if not draws:
        raise FileNotFoundError(f"找不到或未能讀取 M6：{M6_CSV}")

    print_query_setting()

    if MODE == "backtest":
        latest_index = len(draws) - 1
        for backtest_count in BACKTEST_DRAW_COUNT_LIST:
            first_check_index = max(0, latest_index - backtest_count + 1)
            check_indices = range(first_check_index, latest_index + 1)
            for window_count in WINDOW_DRAW_COUNT_LIST:
                total_backtest_count = len(check_indices)
                for backtest_index, check_index in enumerate(check_indices, start=1):
                    print_backtest_window(
                        draws,
                        check_index,
                        backtest_count,
                        window_count,
                        backtest_index,
                        total_backtest_count,
                    )
    elif MODE == "predict":
        next_draw_date = read_next_draw_date()
        for window_count in WINDOW_DRAW_COUNT_LIST:
            print_predict_window(draws, window_count, next_draw_date)
    else:
        raise ValueError('MODE 只能是 "backtest" 或 "predict"')


if __name__ == "__main__":
    main()
