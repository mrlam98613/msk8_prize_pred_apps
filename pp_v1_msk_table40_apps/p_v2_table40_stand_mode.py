from pathlib import Path
import csv
import sys
from collections import Counter
from typing import TypedDict


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from A_msk_marksix_function_app.res_func_num_convert_RBG_Dict import res_call_RBG_123_func

M6_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"
M4_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M4_lotto_prize_summary.csv"


# MODE 可選："backtest" 或 "predict"。
MODE = "backtest"
BACKTEST_DRAW_COUNT_LIST = [1]
WINDOW_DRAW_COUNT_LIST = [30]
# 每一期在指定 table idx_units 內有多少球才算符合條件。
COMBINATION_TAKE_COUNT = 4
BIRTHDAY_NUM_MATCH_MODE = ">="

# SERACH_MODE 可選：
# 1 = lotto_num / rbg / lotto_num_rbg
# 2 = table40，並配合 IDX_DISPLAY_MODE 顯示 idx_tens_units / idx_units / idx_units_dot。
SERACH_MODE = 1

# SERACH_MODE = 1 時使用；可選："lotto_num_rbg", "rbg", "lotto_num"。
SERACH_MODE_1_DISPLAY_RESULT_MODE = "lotto_num"

# SERACH_MODE = 2 時固定使用 table40。
SERACH_MODE_2_DISPLAY_RESULT_MODE = "table40"

# LOTTO_LIST=True 時，每期將所選組別號碼合併成一個 [] 顯示；False 則按組別分開顯示。
LOTTO_LIST = True

'''
 MODE 2 參數查詢 設定
'''
  
# SELECT_IDX_UNITS 用 table40 idx_units 搜尋；0 代表 40,10,20,30。
SELECT_IDX_UNITS = (1,4,7,2,5,8) # 如果查詢 1 個 ＝(2,) 加入 分號。

# IDX_DISPLAY_MODE 可選：
'''
idx_tens_units ＝ 1.3= 13, 0.0=40"
idx_units = 0-9
idx_units_dot = 23= .3, 40= .0
# 球數統計模式由 IDX_DISPLAY_MODE 自動配對：
# idx_tens_units = 1 合條件球數；idx_units = 2 idx_units 不重復球數；idx_units_dot = 3 idx_units_dot 重復球數。
'''
IDX_DISPLAY_MODE = "idx_units_dot"

# 舊 range group 功能保留作 fallback；table40 版本主流程不用它。
SELECT_GROUPS = (1,2,3,0)

# DISPLAY_PAD_EMPTY=True 時，查詢結果固定補齊 N1..N6 + N7 共 7 格，未命中位置用 _。
DISPLAY_PAD_EMPTY = True

# PRINT_BACKTEST_MODE 可選 "detail" 或 "simple"。
# detail 會打印窗口期明細；simple 只打印每期核對、預測球與命中統計。
PRINT_BACKTEST_MODE = "detail" #"detail" 或 "simple"。

# -------------------------
# PRIZE_OPTION=3 即顯示三獎中獎注數 prize3。
PRIZE_OPTION = 3 # 設定要顯示的獎項，3 即顯示三獎中獎注數。
PRIZE_PRINT_SHOW = False
# -------------------------
# RANDOM_GROUP_TAKE_COUNT = 3
# RANDOM_SEED = 20260912

# # PRINT_RANDOM_RESULT=True 時顯示隨機發球、命中與統計；False 時保留功能但暫不打印。
# PRINT_RANDOM_RESULT = True

GROUPS = {
    1: ("1-9", 1, 9),
    2: ("10-20", 10, 20),
    3: ("21-31", 21, 31),
    4: ("32-40", 32, 40),
}

IDX_UNITS_GROUPS = {
    # idx_units = 0-9     idx_tens = 0,1,2,3
    0: ("0", 40,10,20,30),
    #---
    1: ("1", 1,11,21,31),
    2: ("2", 2,12,22,32),
    3: ("3", 3,13,23,33),
    #---
    4: ("4", 4,14,24,34),
    5: ("5", 5,15,25,35),
    6: ("6", 6,16,26,36),
    #---
    7: ("7", 7,17,27,37),
    8: ("8", 8,18,28,38),
    9: ("9", 9,19,29,39),   
}

class DrawRow(TypedDict):
    date: str
    nums: list[int]
    special: int | None
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
    special: int | None = None,
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


def format_hit_nums(nums: list[int], special: int | None = None) -> str:
    ''' 格式化命中號碼，不加入特號佔位符。 '''
    return format_nums(nums, special, False)


def format_ball_count(value: float) -> str:
    ''' 格式化球數，整數不顯示小數點。 '''
    return str(int(value)) if value.is_integer() else f"{value:g}"


def rbg_letter(num: int) -> str:
    ''' 將單一球號轉成 R/B/G。 '''
    rbg_num = res_call_RBG_123_func(num)
    if rbg_num == 1:
        return "R"
    if rbg_num == 2:
        return "B"
    return "G"


def table40_idx_tens_units_code(num: int) -> str:
    ''' 將 1-40 號碼轉成 table40 idx_tens.idx_units 代號；40 固定為 0.0。 '''
    if num == 40:
        return "0.0"
    return f"{num // 10}.{num % 10}"


def table40_idx_units(num: int) -> int:
    ''' 取得 table40 idx_units；10,20,30,40 都是 idx_units 0。 '''
    return num % 10


def table40_idx_units_dot(num: int) -> int:
    ''' 取得 table40 idx_units；idx_units_dot 模式會用 .N 顯示。 '''
    return table40_idx_units(num)


def table40_display_idx_code(num: int) -> str:
    ''' 依 IDX_DISPLAY_MODE 顯示 idx_units、idx_units_dot 或 idx_tens.idx_units。 '''
    if IDX_DISPLAY_MODE == "idx_units":
        return str(table40_idx_units(num))
    if IDX_DISPLAY_MODE == "idx_units_dot":
        return f".{table40_idx_units_dot(num)}"
    return table40_idx_tens_units_code(num)


def rbg_analysis_text(nums: list[int], special: int | None = None) -> str:
    ''' 將查詢結果號碼轉成 RBG 清單與統計。 '''
    display_nums = list(nums)
    if special is not None:
        display_nums.append(special)

    letters = [rbg_letter(num) for num in display_nums]
    red_count = letters.count("R")
    blue_count = letters.count("B")
    green_count = letters.count("G")
    return f" {format_nums_text(letters)} , R{red_count},B{blue_count}, G{green_count},"


def display_result_text(nums: list[int], special: int | None = None) -> str:
    ''' 依目前 SERACH_MODE 生效的顯示模式，顯示號碼、RBG 或 table40。 '''
    lotto_text = format_nums(nums, special)
    rbg_text = rbg_analysis_text(nums, special).strip()
    table40_nums = [table40_idx_tens_units_code(num) for num in nums]
    if special is not None:
        table40_nums.append(f"*{table40_idx_tens_units_code(special)}")
    table40_text = format_nums_text(table40_nums)
    display_mode = active_display_result_mode()
    if display_mode == "rbg":
        return rbg_text
    if display_mode == "table40":
        return table40_text
    if display_mode == "lotto_num":
        return lotto_text
    return f"{lotto_text} {rbg_text}"


def format_nums_text(values: list[str]) -> str:
    ''' 格式化文字列表為 []。 '''
    return "[" + ",".join(values) + "]"


def selected_group_bounds() -> tuple[int, int]:
    ''' 取得目前所選組別覆蓋的最小與最大號碼。 '''
    groups = selected_groups()
    return min(start_num for _name, start_num, _end_num in groups), max(
        end_num for _name, _start_num, end_num in groups
    )


def is_num_in_selected_groups(num: int) -> bool:
    ''' 判斷球號是否落在目前所選組別內。 '''
    return any(start_num <= num <= end_num for _name, start_num, end_num in selected_groups())


def is_num_in_selected_idx_units(num: int) -> bool:
    ''' 判斷球號是否落在目前所選 table idx_units 內。 '''
    return 1 <= num <= 40 and table40_idx_units(num) in selected_idx_units()


def padded_display_slots(row: DrawRow) -> tuple[list[str], list[str], list[str], list[int], int | None]:
    ''' 產生固定 7 格的號碼、RBG、table40 顯示；未落在所選範圍的位置用 _。 '''
    selected_nums_only = sorted(num for num in row["nums"] if is_num_in_selected_idx_units(num))
    missing_normal_count = max(0, 6 - len(selected_nums_only))

    lotto_slots = [str(num) for num in selected_nums_only]
    lotto_slots.extend(["_"] * missing_normal_count)

    rbg_slots = [rbg_letter(num) for num in selected_nums_only]
    rbg_slots.extend(["_"] * missing_normal_count)

    table40_slots = [table40_display_idx_code(num) for num in selected_nums_only]
    table40_slots.extend(["_"] * missing_normal_count)

    selected_special = row["special"] if row["special"] is not None and is_num_in_selected_idx_units(row["special"]) else None
    if selected_special is not None:
        lotto_slots.append(f"*{selected_special}")
        rbg_slots.append(rbg_letter(selected_special))
        table40_slots.append(f"*{table40_display_idx_code(selected_special)}")
    else:
        lotto_slots.append("_")
        rbg_slots.append("_")
        table40_slots.append("_")

    return lotto_slots, rbg_slots, table40_slots, selected_nums_only, selected_special


def display_result_slots_text(lotto_slots: list[str], rbg_slots: list[str], table40_slots: list[str]) -> str:
    ''' 依目前 SERACH_MODE 生效的顯示模式，顯示已補位的號碼、RBG 或 table40。 '''
    lotto_text = format_nums_text(lotto_slots)
    rbg_text = format_nums_text(rbg_slots)
    table40_text = format_nums_text(table40_slots)
    red_count = rbg_slots.count("R")
    blue_count = rbg_slots.count("B")
    green_count = rbg_slots.count("G")
    rbg_summary = f"{rbg_text} , R{red_count},B{blue_count}, G{green_count},"
    display_mode = active_display_result_mode()
    if display_mode == "rbg":
        return rbg_summary
    if display_mode == "table40":
        return table40_text
    if display_mode == "lotto_num":
        return lotto_text
    return f"{lotto_text} {rbg_summary}"


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


def selected_special(row: DrawRow, start_num: int, end_num: int) -> int | None:
    ''' 判斷特號 N7 是否落在指定分組範圍內。 '''
    special = row["special"]
    if special is None:
        return None
    return special if start_num <= special <= end_num else None


def display_ball_count(normal_count: int, special: int | None) -> float:
    ''' 計算顯示球數；正號達 3 球時特號加 0.5。 '''
    if special is not None and normal_count >= 3:
        return normal_count + 0.5
    return float(normal_count)


def normalize_select_groups() -> tuple[int, ...]:
    ''' 檢查 SELECT_GROUPS 型別、組別範圍與最少組數。 '''
    if isinstance(SELECT_GROUPS, int):
        raise ValueError(
            "SELECT_GROUPS 需要 tuple/list，例如 (1, 2) 或 (1, 2, 3, 4)。"
            "你現在寫成 (2)，Python 會當作整數；若只寫單一 tuple 要用 (2,)，"
            "但本程式最少需要選 2 個組別。"
        )
    if not isinstance(SELECT_GROUPS, (tuple, list)):
        raise ValueError("SELECT_GROUPS 需要 tuple/list，例如 (1, 2) 或 (1, 2, 3, 4)。")

    group_ids = tuple(SELECT_GROUPS)
    if len(group_ids) < 2:
        raise ValueError("SELECT_GROUPS 最少需要選 2 個組別，例如 (1, 2)、(1, 2, 3) 或 (1, 2, 3, 4)。")
    for group_id in group_ids:
        if group_id not in GROUPS:
            raise ValueError(f"SELECT_GROUPS 只可選 1,2,3,4；錯誤值：{group_id}")
    return group_ids


def validate_print_backtest_mode() -> None:
    ''' 檢查 backtest 打印模式，只可使用 detail 或 simple。 '''
    if PRINT_BACKTEST_MODE not in ("detail", "simple"):
        raise ValueError('PRINT_BACKTEST_MODE 只可設定為 "detail" 或 "simple"。')


def active_display_result_mode() -> str:
    ''' 按 SERACH_MODE 取得真正生效的查詢結果顯示模式。 '''
    if SERACH_MODE == 1:
        return SERACH_MODE_1_DISPLAY_RESULT_MODE
    if SERACH_MODE == 2:
        return SERACH_MODE_2_DISPLAY_RESULT_MODE
    raise ValueError("SERACH_MODE 只可設定為 1 或 2。")


def validate_serach_mode() -> None:
    ''' 檢查 SERACH_MODE 與對應顯示模式設定。 '''
    if SERACH_MODE not in (1, 2):
        raise ValueError("SERACH_MODE 只可設定為 1 或 2。")
    if SERACH_MODE_1_DISPLAY_RESULT_MODE not in ("lotto_num_rbg", "rbg", "lotto_num"):
        raise ValueError('SERACH_MODE_1_DISPLAY_RESULT_MODE 只可設定為 "lotto_num_rbg", "rbg", "lotto_num"。')
    if SERACH_MODE_2_DISPLAY_RESULT_MODE != "table40":
        raise ValueError('SERACH_MODE_2_DISPLAY_RESULT_MODE 固定為 "table40"。')


def validate_table_settings() -> None:
    ''' 檢查 table40 idx_units 查詢參數。 '''
    if IDX_DISPLAY_MODE not in ("idx_tens_units", "idx_units", "idx_units_dot"):
        raise ValueError('IDX_DISPLAY_MODE 只可設定為 "idx_tens_units", "idx_units" 或 "idx_units_dot"。')
    if isinstance(SELECT_IDX_UNITS, int):
        raise ValueError("SELECT_IDX_UNITS 需要 tuple/list，例如 (1, 2, 3) 或 (1,2,3,4,5,6,7,8,9,0)。")
    if not isinstance(SELECT_IDX_UNITS, (tuple, list)):
        raise ValueError("SELECT_IDX_UNITS 需要 tuple/list。")
    for idx_unit in SELECT_IDX_UNITS:
        if idx_unit not in IDX_UNITS_GROUPS:
            raise ValueError(f"SELECT_IDX_UNITS 只可選 0..9；錯誤值：{idx_unit}")


def selected_idx_units() -> tuple[int, ...]:
    ''' 取得目前選用的 table idx_units。 '''
    return tuple(SELECT_IDX_UNITS)


def ball_count_mode() -> int:
    ''' 依 SERACH_MODE / IDX_DISPLAY_MODE 自動取得球數統計模式。 '''
    if active_display_result_mode() != "table40":
        return 1
    if IDX_DISPLAY_MODE == "idx_units":
        return 2
    if IDX_DISPLAY_MODE == "idx_units_dot":
        return 3
    return 1


def selected_groups() -> list[tuple[str, int, int]]:
    ''' 依 SELECT_GROUPS 取得實際使用的組別設定。 '''
    groups: list[tuple[str, int, int]] = []
    for group_id in normalize_select_groups():
        groups.append(GROUPS[group_id])
    return groups


def row_ball_count(row: DrawRow) -> float:
    ''' 計算某期开奖在所選 table idx_units 中的總球數。 '''
    normal_count = sum(1 for num in row["nums"] if is_num_in_selected_idx_units(num))
    special = row["special"] if row["special"] is not None and is_num_in_selected_idx_units(row["special"]) else None
    return display_ball_count(normal_count, special)


def row_table_normal_count(row: DrawRow) -> int:
    ''' 計算某期开奖正號 N1..N6 命中所選 table idx_units 的數量。 '''
    return sum(1 for num in row["nums"] if is_num_in_selected_idx_units(num))


def row_selected_display_nums(row: DrawRow) -> tuple[list[int], int | None]:
    ''' 取得正號與特號中命中所選 table idx_units 的號碼。 '''
    nums = sorted(num for num in row["nums"] if is_num_in_selected_idx_units(num))
    special = row["special"] if row["special"] is not None and is_num_in_selected_idx_units(row["special"]) else None
    return nums, special


def row_unique_idx_units_summary(row: DrawRow) -> tuple[str, int]:
    ''' 統計只出現 1 次的 table idx_units；正號與特號一併計算。 '''
    nums, special = row_selected_display_nums(row)
    idx_units = [table40_idx_units(num) for num in nums]
    if special is not None:
        idx_units.append(table40_idx_units(special))

    idx_unit_counts = Counter(idx_units)
    unique_idx_units = [idx_unit for idx_unit, count in sorted(idx_unit_counts.items()) if count == 1]
    if not unique_idx_units:
        return "", 0
    return format_nums_text([str(idx_unit) for idx_unit in unique_idx_units]), len(unique_idx_units)


def row_idx_units_repeat_summary(row: DrawRow) -> tuple[str, int]:
    ''' 統計重複 idx_units_dot 明細；同一 idx_units_dot 出現 N 次時計為 N-1 個重複球。 '''
    nums, special = row_selected_display_nums(row)
    idx_units_dots_ = [table40_idx_units_dot(num) for num in nums]
    if special is not None:
        idx_units_dots_.append(table40_idx_units_dot(special))

    repeat_counts = {
        idx_units_dot: count - 1
        for idx_units_dot, count in sorted(Counter(idx_units_dots_).items())
        if count >= 2
    }
    if not repeat_counts:
        return "", 0

    repeat_text = ",".join(f"[.{idx_units_dot}]={count}" for idx_units_dot, count in repeat_counts.items())
    return repeat_text, sum(repeat_counts.values())


def row_display_ball_count_text(row: DrawRow) -> str:
    ''' 依 IDX_DISPLAY_MODE 自動配對球數統計文字。 '''
    mode = ball_count_mode()
    if mode == 2:
        unique_text, unique_count = row_unique_idx_units_summary(row)
        detail_text = f" {unique_text}" if unique_text else ""
        return f"idx_units 不重復{detail_text} /> {unique_count} 球"
    if mode == 3:
        repeat_text, repeat_count = row_idx_units_repeat_summary(row)
        detail_text = f" {repeat_text}" if repeat_text else ""
        return f"idx_units 重復{detail_text} /> {repeat_count} 球"
    return f"/> {format_ball_count(row_ball_count(row))} 球"


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
    special: int | None = None
    for _name, start_num, end_num in selected_groups():
        nums.extend(selected_nums(row, start_num, end_num))
        group_special = selected_special(row, start_num, end_num)
        if group_special is not None:
            special = group_special
    return format_nums(sorted(set(nums)), special)


def lotto_list_nums_and_special(row: DrawRow) -> tuple[list[int], int | None]:
    ''' 取得所選 table idx_units 內的合併正號與特號。 '''
    nums = sorted(num for num in row["nums"] if is_num_in_selected_idx_units(num))
    special = row["special"] if row["special"] is not None and is_num_in_selected_idx_units(row["special"]) else None
    return nums, special


def row_result_text(row: DrawRow) -> str:
    ''' 產生一期的所有選中組別顯示文字與總球數。 '''
    if LOTTO_LIST:
        if DISPLAY_PAD_EMPTY:
            lotto_slots, rbg_slots, table40_slots, _nums, _special = padded_display_slots(row)
            return (
                f"{display_result_slots_text(lotto_slots, rbg_slots, table40_slots)}"
                f" {row_display_ball_count_text(row)}"
            )

        nums, special = lotto_list_nums_and_special(row)
        return (
            f"{display_result_text(nums, special)}"
            f" {row_display_ball_count_text(row)}"
        )

    group_text = "，".join(
        (
            f"{display_result_text(selected_nums(row, start_num, end_num), selected_special(row, start_num, end_num))}"
        )
        for name, start_num, end_num in selected_groups()
    )
    return f"{group_text} {row_display_ball_count_text(row)}"


def all_check_nums_text(row: DrawRow) -> str:
    ''' 格式化核對期 N1..N7；只顯示 1-40，41-49 用底線代替。 '''
    parts = [str(num) if 1 <= num <= 40 else "_" for num in sorted(row["nums"])]
    if row["special"] is not None:
        special_text = str(row["special"]) if 1 <= row["special"] <= 40 else "_"
        parts.append(f"*{special_text}")
    return "[" + ",".join(parts) + "]"


def query_mode_text() -> str:
    """產生標題用的查詢模式文字。"""
    display_mode = active_display_result_mode()
    if display_mode == "table40":
        return f"Table idx_units，顯示={display_mode}/{IDX_DISPLAY_MODE}"
    return f"Table idx_units，顯示={display_mode}"


def print_query_setting() -> None:
    """打印本次執行的模式與主要查詢參數。"""
    print("====== p_v2 table40 stand mode 查詢分析 ======")
    print()
    print("基本查詢 參數")
    print('運作模式可選："backtest" / "predict"')
    print(f"運作模式：{MODE}")
    print(f"SERACH_MODE = {SERACH_MODE}")
    print(f"BACKTEST_DRAW_COUNT_LIST = {BACKTEST_DRAW_COUNT_LIST}")
    print(f"WINDOW_DRAW_COUNT_LIST = {WINDOW_DRAW_COUNT_LIST}")
    print(f"COMBINATION_TAKE_COUNT = {COMBINATION_TAKE_COUNT}")
    print(f'BIRTHDAY_NUM_MATCH_MODE = "{BIRTHDAY_NUM_MATCH_MODE}"')
    print(f"回測打印模式：{PRINT_BACKTEST_MODE}")
    print()
    if SERACH_MODE == 1:
        print("------------------- SERACH_MODE 1")
        print('查詢結果顯示模式可選："lotto_num_rbg", "rbg", "lotto_num"')
        print(f"查詢模式 1 = {SERACH_MODE_1_DISPLAY_RESULT_MODE}")
        print(f"查詢結果補位：{DISPLAY_PAD_EMPTY}")
    elif SERACH_MODE == 2:
        print("------------------- SERACH_MODE 2")
        print(f"查詢模式條件：Table 40 {selected_idx_units()}")
        print(f"查詢模式 2 = {SERACH_MODE_2_DISPLAY_RESULT_MODE}")
        print('Table 顯示模式可選："idx_tens_units", "idx_units", "idx_units_dot"')
        print(f"Table 顯示模式：{IDX_DISPLAY_MODE}")
        print(f"符合條件：所選 Table idx_units 正號數量 {BIRTHDAY_NUM_MATCH_MODE}{COMBINATION_TAKE_COUNT} 球")
        print(f"查詢結果補位：{DISPLAY_PAD_EMPTY}")
    print()
    print("------------- 基本條件顯示")
    print(f"實際生效顯示：{active_display_result_mode()}")
    print(f"球數統計模式：{ball_count_mode()} 自動配對")
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
    rank_width = len(str(len(window_rows)))
    for row_index, row in window_rows:
        if not is_matched(row_table_normal_count(row)):
            continue
        rank = target_index - row_index + 1
        print(
            f"近 {rank:>{rank_width}}期：{row['date']}，{row_result_text(row)}"
            f"{prize_print_text(row)}"
        )


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
    print(f"核對日期 ： {check_row['date']}: {all_check_nums_text(check_row)}")
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
    print(f"下期開獎日期：{next_draw_date or '未知'}")
    print()


def main() -> None:
    """主流程：驗證參數、讀取資料，並按 MODE 執行。"""
    try:
        validate_table_settings()
        validate_print_backtest_mode()
        validate_serach_mode()
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
