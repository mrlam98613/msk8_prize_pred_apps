from pathlib import Path
import csv
from collections import Counter
from typing import Optional, TypedDict

''' 
查詢 有關特號球計算 0.5 / 1 , 情景1,2。
1, = SELECT_GROUPS = (1, 2, 3, 4)
特別號以 0.5 球計算。
2, = SELECT_GROUPS = (1, 2) 或其他部分組別
特別號以 1 球整數計算。

A,B,C,D, (1-9) , (10-20) , (21-31) , (32-40), (分組查詢)
1-9,   [1,3,5,7,9], [2,4,6,8] = 9 球
10-20, [11,13,15,17,19], [10,12,14,16,18,20] = 11 球
21-31, [21,23,25,27,29,31], [22,24,26,28,30] = 11 球
32-40, [33,35,37,39], [32,34,36,38,40] = 9 球 

總球次位置 = 19 × 7 = 133

A/D 預期位置 = 133 × 9 ÷ 40 = 29.925
B/C 預期位置 = 133 × 11 ÷ 40 = 36.575

'''

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
M6_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"
M4_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M4_lotto_prize_summary.csv"


# -------------------------
# S3 ABCD pattern 基本參數
VERSION = "S3 ABCD 獨立分組 + 3 獎分析 "

MODE = "predict" # backtest / predict mode input
BACKTEST_DRAW_COUNT_LIST = [1]
WINDOW_DRAW_COUNT_LIST = [13] # 最少查詢 7 期
SELECT_GROUPS = 1,2,3,4 # Select 1,2,3,4 
COMBINATION_TAKE_COUNT = 3
COMB_MATCH_MODE = ">="
STRONG_COMBINATION_TAKE_COUNT = 5
# False=原有分組顯示；True=原有合併顯示；"sort"=按每期 ABCD 球數排序顯示
LOTTO_LIST = True # False / True / "sort", 3 種 參數顯示 。
PREDICT = True
PRINT_BACKTEST_MODE = "detail"
PRIZE_OPTION = 3
PRIZE_PRINT_SHOW = True
# 保留 ABCD 屬性分析功能；暫時不顯示分析結果。
PRINT_ABCD_PROPERTY_ANALYSIS = True

# 基本查詢排序："date" 或 "prize3"。
STAND_SORT_MODE = "date"

# 獨立的 3 獎注數排序功能。
prize3_sort_mode = True
prize3_unit_sort = ">="
prize3_unit_count = 50
prize3_max_count = 10


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


def write_csv_rows(path: Path, rows: list[dict[str, object]]) -> None:
    ''' 寫出 CSV；使用 utf-8-sig 方便試算表直接讀中文。 '''
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return

    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


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
    numeric_value = float(value)
    return str(int(numeric_value)) if numeric_value.is_integer() else f"{numeric_value:g}"


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
        group_ids = (SELECT_GROUPS,)
    elif isinstance(SELECT_GROUPS, (tuple, list)):
        group_ids = tuple(SELECT_GROUPS)
    else:
        raise ValueError("SELECT_GROUPS 需要 int/tuple/list，例如 1 或 (1, 2, 3, 4)。")

    if not group_ids:
        raise ValueError("SELECT_GROUPS 最少需要選 1 個組別，例如 1 或 (1, 2, 3, 4)。")
    for group_id in group_ids:
        if group_id not in GROUPS:
            raise ValueError(f"SELECT_GROUPS 只可選 1,2,3,4；錯誤值：{group_id}")
    return group_ids


def validate_print_backtest_mode() -> None:
    ''' 檢查 backtest 打印模式，只可使用 detail 或 simple。 '''
    if PRINT_BACKTEST_MODE not in ("detail", "simple"):
        raise ValueError('PRINT_BACKTEST_MODE 只可設定為 "detail" 或 "simple"。')


def validate_sort_mode() -> None:
    """檢查基本查詢排序功能。"""
    if STAND_SORT_MODE not in ("date", "prize3"):
        raise ValueError('STAND_SORT_MODE 只可設定為 "date" 或 "prize3"。')


def validate_prize3_sort_settings() -> None:
    """檢查獨立 3 獎排序參數。"""
    if not isinstance(prize3_sort_mode, bool):
        raise ValueError("prize3_sort_mode 只可設定為 True 或 False。")
    if prize3_unit_sort not in (">=", "==", "<="):
        raise ValueError('prize3_unit_sort 只可設定為 ">=", "==" 或 "<="。')
    if prize3_unit_count < 0:
        raise ValueError("prize3_unit_count 不可小於 0。")
    if prize3_max_count < 1:
        raise ValueError("prize3_max_count 最少為 1 期。")


def validate_lotto_list_mode() -> None:
    """檢查分組顯示模式。"""
    if LOTTO_LIST not in (False, True, "sort"):
        raise ValueError('LOTTO_LIST 只可設定為 False、True 或 "sort"。')


def validate_window_draw_counts() -> None:
    """檢查用戶輸入窗口期最少要 7 期。"""
    for window_count in WINDOW_DRAW_COUNT_LIST:
        if window_count < 7:
            raise ValueError(
                "WINDOW_DRAW_COUNT_LIST 每個窗口期最少查詢 7 期；"
                f"錯誤值：{window_count}"
            )


def selected_groups() -> list[tuple[str, int, int]]:
    ''' 依 SELECT_GROUPS 取得實際使用的組別設定。 '''
    groups: list[tuple[str, int, int]] = []
    for group_id in normalize_select_groups():
        groups.append(GROUPS[group_id])
    return groups


def selected_group_ids() -> tuple[int, ...]:
    ''' 取得目前選中的組別 ID。 '''
    return normalize_select_groups()


def row_ball_count(row: DrawRow) -> float:
    '''計算查詢顯示球數；全 A/B/C/D 特號 0.5 球，部分組別特號 1 球。'''
    normal_count = row_selected_normal_count(row)
    special_count = row_selected_special_count(row)
    if selected_group_ids() == tuple(GROUPS.keys()):
        return normal_count + (0.5 if special_count else 0)
    return float(normal_count + special_count)


def row_selected_normal_count(row: DrawRow) -> int:
    ''' 計算某期开奖在所選組別中的正號 N1..N6 數量。 '''
    return sum(
        len(selected_nums(row, start_num, end_num))
        for _name, start_num, end_num in selected_groups()
    )


def row_selected_special_count(row: DrawRow) -> int:
    ''' 計算某期开奖在所選組別中的特號 N7 數量；查詢時特號當 1 球。 '''
    return sum(
        1
        for _name, start_num, end_num in selected_groups()
        if selected_special(row, start_num, end_num) is not None
    )


def row_selected_ball_count(row: DrawRow) -> int:
    ''' 計算查詢用 N1..N7 總球數；特號當 1 球。 '''
    return row_selected_normal_count(row) + row_selected_special_count(row)


def row_selected_hit_ball_count(row: DrawRow) -> float:
    ''' 計算核對/比對用球數；正號當 1 球，特號當 0.5 球。 '''
    return row_selected_normal_count(row) + (0.5 if row_selected_special_count(row) else 0)


def row_selected_normal_nums(row: DrawRow) -> list[int]:
    ''' 取得某期开奖在所選組別中的正號 N1..N6。 '''
    nums: list[int] = []
    for _name, start_num, end_num in selected_groups():
        nums.extend(selected_nums(row, start_num, end_num))
    return sorted(set(nums))


def is_count_matched(count: int, take_count: int, match_mode: str) -> bool:
    ''' 判斷球數是否符合指定條件。 '''
    if match_mode == "==":
        return count == take_count
    if match_mode == "<=":
        return count <= take_count
    return count >= take_count


def is_matched(count: int) -> bool:
    ''' 判斷球數是否符合基礎查詢條件。 '''
    return is_count_matched(count, COMBINATION_TAKE_COUNT, COMB_MATCH_MODE)


def is_strong_matched(count: int) -> bool:
    ''' 判斷球數是否符合強勢條件。 '''
    return is_count_matched(count, STRONG_COMBINATION_TAKE_COUNT, COMB_MATCH_MODE)


def is_abcd_property_matched(count: int) -> bool:
    ''' ABCD 屬性分析專用：包括特號，條件跟隨主查詢參數。 '''
    return is_count_matched(count, COMBINATION_TAKE_COUNT, COMB_MATCH_MODE)


def abcd_property_row_count(row: DrawRow) -> int:
    ''' 計算 ABCD 屬性分析用的每期合併分組總球數，包括特號。 '''
    return row_selected_ball_count(row)


def is_abcd_property_row_matched(row: DrawRow) -> bool:
    ''' 判斷某期是否符合 ABCD 屬性分析的合併分組總球數條件。 '''
    return is_abcd_property_matched(abcd_property_row_count(row))


def group_result_text(row: DrawRow, name: str, start_num: int, end_num: int) -> str:
    ''' 產生單組詳細顯示文字，包含組名與單組球數。 '''
    nums = selected_nums(row, start_num, end_num)
    special = selected_special(row, start_num, end_num)
    ball_count = len(nums) + (1 if special is not None else 0)
    if not is_matched(ball_count):
        return f"[{name}] [] /> 0 球"
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
    if LOTTO_LIST is True:
        return f"{lotto_list_text(row)} /> {format_ball_count(row_ball_count(row))} 球"

    group_text = row_group_text(row)
    return f"{group_text} /> {format_ball_count(row_ball_count(row))} 球"


def row_group_text(row: DrawRow) -> str:
    """產生一期的 ABCD 號碼文字，不附加球數。"""
    if LOTTO_LIST is True:
        return lotto_list_text(row)

    groups = selected_groups()
    if LOTTO_LIST == "sort" and PREDICT:
        groups = sorted(
            groups,
            key=lambda group: (
                -len(selected_nums(row, group[1], group[2]))
                - (1 if selected_special(row, group[1], group[2]) is not None else 0),
                selected_groups().index(group),
            ),
        )
    return "，".join(group_only_text(row, name, start_num, end_num) for name, start_num, end_num in groups)


def query_condition_result_text(row: DrawRow) -> str:
    """在原有查詢明細內套用正號條件與簡化球數顯示。"""
    normal_count = row_selected_normal_count(row)
    if normal_count < COMBINATION_TAKE_COUNT:
        return ""
    if normal_count < STRONG_COMBINATION_TAKE_COUNT:
        return row_result_text(row)
    return f"{row_group_text(row)} /> {format_ball_count(row_ball_count(row))} 球"


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


def format_group_ids(group_ids: tuple[int, ...]) -> str:
    """格式化查詢組別，避免單一組別顯示 Python tuple 尾逗號。"""
    return "(" + ", ".join(str(group_id) for group_id in group_ids) + ")"


def print_query_setting() -> None:
    """打印本次執行的模式與主要查詢參數。"""
    group_ids = normalize_select_groups()
    mode_text = "全組別" if group_ids == tuple(GROUPS.keys()) else "自選組別"
    print(f"======Vol:{VERSION} 開獎紀錄查詢分析 ======")
    print(f"運作模式：{MODE}")
    print(f"查詢模式：{mode_text} {format_group_ids(group_ids)}")
    print(f"回測打印模式：{PRINT_BACKTEST_MODE}")
    print(f"回測期列表：{BACKTEST_DRAW_COUNT_LIST}")
    print(f"窗口期列表：{WINDOW_DRAW_COUNT_LIST}")
    print(
        f"符合條件：基礎 {COMB_MATCH_MODE}{COMBINATION_TAKE_COUNT} 球，"
        f"強勢 {COMB_MATCH_MODE}{STRONG_COMBINATION_TAKE_COUNT} 球"
    )
    print("查詢號碼：N1..N7，N7 特號以 * 顯示")
    display_text = "合併號碼" if LOTTO_LIST is True else "ABCD球數排序" if LOTTO_LIST == "sort" else "分組號碼"
    prize_show_text = f"，Pz{PRIZE_OPTION}" if PRIZE_PRINT_SHOW else ""
    print(f"顯示欄位：開獎日期，{display_text}，N球{prize_show_text}")
    sort_text = "3 獎注數排序優先" if STAND_SORT_MODE == "prize3" else "日期遠近排序"
    print(f"排序功能：{sort_text}")
    print("窗口期最少查詢：7 期")
    print()


def print_draw_rows(
    draws: list[DrawRow],
    window_rows: list[tuple[int, DrawRow]],
    target_index: int,
) -> None:
    """打印窗口期內每一期的組別分布。"""
    for row_index, row in window_rows:
        rank = target_index - row_index + 1
        result_text = f"{query_condition_result_text(row)}{prize_print_text(row)}"
        if not query_condition_result_text(row):
            result_text = prize_print_text(row).lstrip("，")
        main_text = main_group_text(row)
        main_suffix = f"，{main_text}" if main_text else ""
        line_suffix = f"，{result_text}" if result_text else ""
        print(f"近 {rank:>2}期：{row['date']}{main_suffix}{line_suffix}")


def matched_window_count(window_rows: list[tuple[int, DrawRow]]) -> int:
    ''' 統計窗口期內符合查詢條件的期數。 '''
    return sum(1 for _row_index, row in window_rows if is_matched(row_selected_normal_count(row)))


def strong_matched_window_count(window_rows: list[tuple[int, DrawRow]]) -> int:
    ''' 統計窗口期內符合強勢條件的期數。 '''
    return sum(1 for _row_index, row in window_rows if is_strong_matched(row_selected_normal_count(row)))


def strong_trend_sequence(window_rows: list[tuple[int, DrawRow]]) -> str:
    ''' 將強勢條件走勢轉成 H / - 序列。 '''
    return "".join(
        "H" if is_strong_matched(row_selected_normal_count(row)) else "-"
        for _row_index, row in window_rows
    )


def group_ball_count_sequence(window_rows: list[tuple[int, DrawRow]], group_id: int) -> str:
    """將指定 ABCD 組別的每期球數轉成連續走勢；0 球以 - 顯示。"""
    _name, start_num, end_num = GROUPS[group_id]
    sequence: list[str] = []
    for _row_index, row in window_rows:
        count = len(selected_nums(row, start_num, end_num))
        if selected_special(row, start_num, end_num) is not None:
            count += 1
        sequence.append(str(count) if count else "-")
    return "".join(sequence)


def print_abcd_group_trend_analysis(window_rows: list[tuple[int, DrawRow]]) -> dict[int, int]:
    """打印 ABCD 分組球數走勢，回傳各組總球次數。"""
    window_total = len(window_rows)
    denominator = window_total * 7
    group_totals: dict[int, int] = {}

    print()
    print("----- ABCD 分組球數走勢  查詢期數 x 7球  = 球次數 -----")
    for group_id in selected_group_ids():
        _name, start_num, end_num = GROUPS[group_id]
        total = sum(
            len(selected_nums(row, start_num, end_num))
            + (1 if selected_special(row, start_num, end_num) is not None else 0)
            for _row_index, row in window_rows
        )
        group_totals[group_id] = total
        expected_positions = denominator * (end_num - start_num + 1) / 40
        percent = (total / expected_positions * 100) if expected_positions else 0
        code = GROUP_CODES[group_id]
        print(
            f"{code}組 球數走趨：{group_ball_count_sequence(window_rows, group_id)} "
            f"= {total} 球次 / {expected_positions:g} = {percent:.1f}%"
        )

    return group_totals


def print_main_group_analysis(group_totals: dict[int, int], window_total: int) -> None:
    """打印主力組別統計及排序。"""
    denominator = window_total * 7
    expected_positions = {
        group_id: denominator * (GROUPS[group_id][2] - GROUPS[group_id][1] + 1) / 40
        for group_id in group_totals
    }
    ranked_groups = sorted(
        group_totals,
        key=lambda group_id: (
            -(group_totals[group_id] / expected_positions[group_id]),
            selected_group_ids().index(group_id),
        ),
    )
    ranking_text = " > ".join(
        f"{GROUP_CODES[group_id]}({group_totals[group_id]}球次, "
        f"{(group_totals[group_id] / expected_positions[group_id] * 100) if expected_positions[group_id] else 0:.1f}%)"
        for group_id in ranked_groups
    )
    print()
    print("---- ABCD 主力組別統計分析 ")
    print(f"主力組別排序：{ranking_text}")


def group_ball_count(row: DrawRow, group_id: int) -> int:
    """計算指定 ABCD 組別當期球數；特號按 1 球計。"""
    _name, start_num, end_num = GROUPS[group_id]
    return len(selected_nums(row, start_num, end_num)) + (
        1 if selected_special(row, start_num, end_num) is not None else 0
    )


def print_group_priority_table(
    window_rows: list[tuple[int, DrawRow]],
    target_index: int,
) -> None:
    """以每期主力組和副組列出 ABCD 分組走勢。"""
    print()
    print("----- ABCD 主力組 / 副組分組走勢 -----")
    print("ID   | 日期       | 中獎注 | 球數 | 主力 | 副組")
    # 日期由遠到近排列；ID 仍以最近一期為 01 期。
    for row_index, row in window_rows:
        counts = {
            group_id: group_ball_count(row, group_id)
            for group_id in selected_group_ids()
        }
        ranked_groups = sorted(
            counts,
            key=lambda group_id: (-counts[group_id], selected_group_ids().index(group_id)),
        )
        if not ranked_groups:
            continue
        main_group = ranked_groups[0]
        sub_text = ", ".join(
            f"{GROUP_CODES[group_id]}{counts[group_id]}"
            for group_id in ranked_groups[1:]
            if counts[group_id] > 0
        )
        display_id = target_index - row_index + 1
        print(
            f"{display_id:02d}期 | {row['date']:<10} | "
            f"{prize_text(row['prize_count']):>6} | "
            f"{row_selected_ball_count(row):>4} | "
            f"{GROUP_CODES[main_group]}{counts[main_group]:<2} | {sub_text}"
        )


def main_group_text(row: DrawRow) -> str:
    """取得單期主力組及球數；同球數依 A/B/C/D 優先。"""
    counts = {
        group_id: group_ball_count(row, group_id)
        for group_id in selected_group_ids()
    }
    if not counts:
        return ""
    main_group = min(
        counts,
        key=lambda group_id: (-counts[group_id], selected_group_ids().index(group_id)),
    )
    return f"{GROUP_CODES[main_group]}{counts[main_group]}"


def print_matched_window_count(window_rows: list[tuple[int, DrawRow]]) -> None:
    ''' 打印窗口期合條件期數統計。 '''
    matched_count = matched_window_count(window_rows)
    strong_matched_count = strong_matched_window_count(window_rows)
    window_total = len(window_rows)
    matched_percent = (matched_count / window_total * 100) if window_total else 0
    strong_matched_percent = (strong_matched_count / window_total * 100) if window_total else 0
    print("---- 查詢條件 統計")
    print(
        f"基礎條件 {COMB_MATCH_MODE} {COMBINATION_TAKE_COUNT} 球，"
        f"查詢 {matched_count} / {window_total} 期統計 = {matched_count}期 "
        f"({matched_percent:.0f} %)"
    )
    print(
        f"強勢條件 {COMB_MATCH_MODE} {STRONG_COMBINATION_TAKE_COUNT} 球，"
        f"查詢 {strong_matched_count} / {window_total} 期統計 = {strong_matched_count}期 "
        f"({strong_matched_percent:.0f} %)"
    )
    print(f"強勢走勢：{strong_trend_sequence(window_rows)}")


def print_window_result_separator() -> None:
    ''' 打印窗口期明細與統計結果之間的分隔線。 '''
    print("/> -----------------------------------------------")


def sorted_hot_cold_nums(counter: Counter[int], nums: list[int]) -> list[tuple[int, int]]:
    """依窗口期出現次數由熱到冷排序；同次數用號碼細至大排序。"""
    return sorted(((num, counter.get(num, 0)) for num in nums), key=lambda item: (-item[1], item[0]))


def format_hot_cold_pairs(
    pairs: list[tuple[int, int]],
    special_counter: Counter[int],
) -> str:
    """格式化號碼出現次數；有特號貢獻時以 * 標記，例如 [8(*2)]。"""
    return "[" + ",".join(
        f"{num}(*{count})" if special_counter.get(num, 0) else f"{num}({count})"
        for num, count in pairs
    ) + "]"


def matched_window_num_counters(window_rows: list[tuple[int, DrawRow]]) -> tuple[Counter[int], Counter[int]]:
    """統計合條件窗口期內 N1..N7 次數；N7 特號併入總數並另外標記。"""
    num_counter: Counter[int] = Counter()
    special_counter: Counter[int] = Counter()
    for _row_index, row in window_rows:
        if not is_matched(row_selected_normal_count(row)):
            continue
        for num in row["nums"]:
            if 1 <= num <= 40:
                num_counter[num] += 1
        special = row["special"]
        if special is not None and 1 <= special <= 40:
            num_counter[special] += 1
            special_counter[special] += 1
    return num_counter, special_counter


def group_window_num_counts(
    window_rows: list[tuple[int, DrawRow]],
    matched_only: bool = False,
) -> dict[int, Counter[int]]:
    """統計窗口期內 ABCD 各組 N1..N7 出現次數。"""
    counters: dict[int, Counter[int]] = {group_id: Counter() for group_id in GROUPS}
    for _row_index, row in window_rows:
        if matched_only and not is_abcd_property_row_matched(row):
            continue
        for group_id, (_name, start_num, end_num) in GROUPS.items():
            for num in selected_nums(row, start_num, end_num):
                counters[group_id][num] += 1
            special = selected_special(row, start_num, end_num)
            if special is not None:
                counters[group_id][special] += 1
    return counters


def property_analysis_rows(
    window_rows: list[tuple[int, DrawRow]],
    target_index: int,
) -> list[tuple[int, DrawRow]]:
    """ABCD 四類屬性分析用資料；近 1 期不納入，只用近 2 至 N 期。"""
    return [
        (row_index, row)
        for row_index, row in window_rows
        if target_index - row_index + 1 >= 2
    ]


def missing_nums_text(window_rows: list[tuple[int, DrawRow]]) -> str:
    """顯示窗口期內 A/B/C/D 各組沒有出現過的號碼。"""
    group_counts = group_window_num_counts(window_rows, matched_only=False)
    parts: list[str] = []
    for group_id in selected_group_ids():
        _name, start_num, end_num = GROUPS[group_id]
        code = GROUP_CODES[group_id]
        missing = [
            num
            for num in range(start_num, end_num + 1)
            if group_counts[group_id][num] == 0
        ]
        parts.append(f"{code}{format_nums(missing)}")
    return "ANB 缺席球 = " + "，".join(parts)


def high_freq_pair_data(window_rows: list[tuple[int, DrawRow]]) -> dict[int, tuple[list[int], list[int]]]:
    """回傳每組的 HFB 高頻膽號與 HFL 高頻腳號；只看同組雙開或多開期。"""
    result: dict[int, tuple[list[int], list[int]]] = {}

    for group_id in selected_group_ids():
        _name, start_num, end_num = GROUPS[group_id]
        multi_open_counter: Counter[int] = Counter()
        for _row_index, row in window_rows:
            nums = selected_nums(row, start_num, end_num)
            special = selected_special(row, start_num, end_num)
            open_nums = sorted(set(nums + ([special] if special is not None else [])))
            if len(open_nums) >= 2:
                multi_open_counter.update(open_nums)

        dan_nums = [
            num
            for num, count in sorted(multi_open_counter.items(), key=lambda item: (-item[1], item[0]))
            if count >= 2
        ]
        partner_nums = sorted(
            [
                num
                for num, count in sorted(multi_open_counter.items(), key=lambda item: (-item[1], item[0]))
                if count == 1 and num not in dan_nums
            ]
        )
        result[group_id] = (dan_nums, partner_nums)

    return result


def high_freq_pair_text(
    pair_data: dict[int, tuple[list[int], list[int]]],
) -> list[str]:
    """格式化 HFB 高頻膽號與 HFL 高頻腳號。"""
    dan_parts: list[str] = []
    partner_parts: list[str] = []
    for group_id in selected_group_ids():
        code = GROUP_CODES[group_id]
        dan_nums, partner_nums = pair_data.get(group_id, ([], []))
        dan_parts.append(f"{code}{format_nums(dan_nums)}")
        partner_parts.append(f"{code}{format_nums(partner_nums)}")
    return [
        "HFB 高頻膽號 = " + "，".join(dan_parts),
        "HFL 高頻腳號 = " + "，".join(partner_parts),
    ]


def weak_nums_text(
    window_rows: list[tuple[int, DrawRow]],
    pair_data: dict[int, tuple[list[int], list[int]]],
) -> list[str]:
    """格式化 OTN 單次球；同組該期只開 1 球時的球號。"""
    group_counts = group_window_num_counts(window_rows, matched_only=False)
    single_open_nums: dict[int, set[int]] = {group_id: set() for group_id in GROUPS}
    for _row_index, row in window_rows:
        for group_id in selected_group_ids():
            nums = group_nums_with_special(row, group_id)
            if len(nums) == 1:
                single_open_nums[group_id].add(nums[0])

    parts: list[str] = []
    for group_id in selected_group_ids():
        _name, start_num, end_num = GROUPS[group_id]
        code = GROUP_CODES[group_id]
        dan_nums, partner_nums = pair_data.get(group_id, ([], []))
        missing_nums = {
            num
            for num in range(start_num, end_num + 1)
            if group_counts[group_id][num] == 0
        }
        assigned_nums = missing_nums | set(dan_nums) | set(partner_nums)
        otn_nums = [
            num
            for num in sorted(single_open_nums[group_id])
            if num not in assigned_nums
        ]
        parts.append(f"{code}{format_nums(otn_nums)}")
    return ["OTN 單次球 = " + "，".join(parts)]


def print_abcd_property_analysis(
    window_rows: list[tuple[int, DrawRow]],
    target_index: int,
) -> dict[int, tuple[list[int], list[int]]]:
    """打印 ANB/HFB/HFL/OTN 四類分析屬性。"""
    analysis_rows = property_analysis_rows(window_rows, target_index)
    pair_data = high_freq_pair_data(analysis_rows)
    print()
    print(
        f"---------------- {format_group_ids(selected_group_ids())} "
        "A/B/C/D 選組分析屬性 ----------------"
    )
    print(
        f"ABCD 屬性條件：各組獨立，每期合併分組總球數  "
        f"{COMB_MATCH_MODE} {COMBINATION_TAKE_COUNT} 球 (包括特號)"
    )
    print("/> -------------")
    print(missing_nums_text(analysis_rows))
    for line in high_freq_pair_text(pair_data):
        print(line)
    for line in weak_nums_text(analysis_rows, pair_data):
        print(line)
    return pair_data


def group_nums_with_special(row: DrawRow, group_id: int) -> list[int]:
    """取得某組正號與特號；特號同一球號只保留一次。"""
    _name, start_num, end_num = GROUPS[group_id]
    nums = selected_nums(row, start_num, end_num)
    special = selected_special(row, start_num, end_num)
    if special is not None:
        nums.append(special)
    return sorted(set(nums))


def print_backtest_window(
    draws: list[DrawRow],
    check_index: int,
    backtest_count: int,
    window_count: int,
    backtest_index: int,
    total_backtest_count: int,
) -> None:
    """只打印基礎回測窗口、統計、3 獎排序與 ABCD 屬性分析。"""
    display_backtest_index = total_backtest_count - backtest_index + 1
    window_start_index = max(0, check_index - window_count)
    window_rows = [
        (row_index, row)
        for row_index, row in enumerate(draws[window_start_index:check_index], start=window_start_index)
    ]

    print(
        f"======[回測 {display_backtest_index}] "
        f"{query_mode_text()}，參數，回測期= {backtest_count}，N1..N7，窗口期 = {window_count}======"
    )
    print("backtest：窗口期不包括核對期，預留核對預測")

    if STAND_SORT_MODE == "prize3":
        abcd_analysis_rows = print_prize3_sorted_rows(window_rows)
        abcd_target_index = max((row_index for row_index, _row in abcd_analysis_rows), default=check_index - 1) + 1
    else:
        print_draw_rows(draws, window_rows, check_index - 1)
        abcd_analysis_rows = window_rows
        abcd_target_index = check_index - 1

    if STAND_SORT_MODE == "date":
        print_prize3_sorted_rows(window_rows)

    print_window_result_separator()
    group_totals = print_abcd_group_trend_analysis(window_rows)
    print_matched_window_count(abcd_analysis_rows)
    print_group_priority_table(window_rows, check_index - 1)
    print_main_group_analysis(group_totals, len(window_rows))
    if PRINT_ABCD_PROPERTY_ANALYSIS:
        print_abcd_property_analysis(abcd_analysis_rows, abcd_target_index)
    print()


def prize3_sorted_window_rows(
    window_rows: list[tuple[int, DrawRow]],
) -> list[tuple[int, DrawRow]]:
    """回傳整個窗口期按 3 獎注數由多至少排序後的資料。"""
    return sorted(window_rows, key=prize3_sort_value, reverse=True)


def prize3_top_abcd_rows(
    sorted_rows: list[tuple[int, DrawRow]],
) -> list[tuple[int, DrawRow]]:
    """取 3 獎排序結果作 ABCD 分析。"""
    return sorted_rows


def print_prize3_sorted_rows(
    window_rows: list[tuple[int, DrawRow]],
) -> list[tuple[int, DrawRow]]:
    """按門檻篩選 3 獎注數，再由多至少顯示前 N 期。"""
    available_count = len(window_rows)
    if not prize3_sort_mode:
        return window_rows

    filtered_rows = [
        item
        for item in window_rows
        if is_count_matched(
            int(to_float(item[1].get("prize_count"))),
            prize3_unit_count,
            prize3_unit_sort,
        )
    ]
    display_rows = prize3_sorted_window_rows(filtered_rows)[:prize3_max_count]

    print("----- 3 獎中獎注數排序分析 -----")
    print(
        f"窗口期 {available_count} 期，Pz{PRIZE_OPTION} "
        f"{prize3_unit_sort} {prize3_unit_count} 注，"
        f"按注數由多至少，最多 {prize3_max_count} 期。"
    )
    if not display_rows:
        print("沒有符合 3 獎注數條件的期數。")
        print()
        return []

    for rank, (_row_index, row) in enumerate(display_rows, start=1):
        prize3_value = to_float(row.get("prize_count"))
        result_text = query_condition_result_text(row)
        prize_suffix = f"Pz{PRIZE_OPTION}: {prize_text(prize3_value)}" if PRIZE_PRINT_SHOW else ""
        detail_text = f"{result_text}，{prize_suffix}" if result_text and prize_suffix else result_text or prize_suffix
        main_text = main_group_text(row)
        print(
            f"排序 {rank:>2}：{row['date']}，{main_text}，{detail_text}"
        )
    print()
    return display_rows


def prize3_sort_value(item: tuple[int, DrawRow]) -> float:
    """回傳 3 獎排序值。"""
    return to_float(item[1].get("prize_count"))


def print_predict_window(draws: list[DrawRow], window_count: int, next_draw_date: str) -> None:
    """只打印最新窗口、統計、3 獎排序與 ABCD 屬性分析。"""
    latest_index = len(draws) - 1
    window_start_index = max(0, latest_index - window_count + 1)
    window_rows = [
        (row_index, row)
        for row_index, row in enumerate(draws[window_start_index:latest_index + 1], start=window_start_index)
    ]
    print(f"====== {query_mode_text()}，預測模式，N1..N7，窗口期 = {window_count}======")
    print("predict：只顯示最後窗口期基礎分析")

    if STAND_SORT_MODE == "prize3":
        abcd_analysis_rows = print_prize3_sorted_rows(window_rows)
        abcd_target_index = max((row_index for row_index, _row in abcd_analysis_rows), default=latest_index) + 1
    else:
        print_draw_rows(draws, window_rows, latest_index)
        abcd_analysis_rows = window_rows
        abcd_target_index = latest_index

    if STAND_SORT_MODE == "date":
        print_prize3_sorted_rows(window_rows)

    print_window_result_separator()
    group_totals = print_abcd_group_trend_analysis(window_rows)
    print_matched_window_count(abcd_analysis_rows)
    print_group_priority_table(window_rows, latest_index)
    print_main_group_analysis(group_totals, len(window_rows))
    if PRINT_ABCD_PROPERTY_ANALYSIS:
        print_abcd_property_analysis(abcd_analysis_rows, abcd_target_index)
    print()
    print("------ 下期開獎日期 ------------------")
    print(f"下期開獎日期：{next_draw_date or '未知'}")
    print()


def hfb_stat_levels() -> list[float]:
    """HFB 命中統計顯示級距。"""
    return [value / 2 for value in range(12, 5, -1)]


def format_stat_score(value: float) -> str:
    """格式化統計球數，整數不顯示 .0。"""
    return str(int(value)) if value.is_integer() else f"{value:g}"


def format_pool_average(value: float) -> str:
    """格式化候選球池平均球數。"""
    return str(int(value)) if value.is_integer() else f"{value:.1f}"


def object_to_int(value: object) -> int:
    """將 CSV record 的 object 欄位安全轉成 int，避免型別檢查誤判。"""
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        return int(value)
    return 0


def print_hfb_hit_stat_table(
    title: str,
    counter: Counter[float],
    total_count: int,
    candidate_pool_sizes: Optional[list[int]] = None,
) -> None:
    """打印命中球數簡化分布統計。"""
    print()
    print(title)
    if candidate_pool_sizes is not None:
        average_pool_size = sum(candidate_pool_sizes) / len(candidate_pool_sizes) if candidate_pool_sizes else 0.0
        pool_text = "[" + ",".join(str(size) for size in candidate_pool_sizes) + "]"
        print(f"各回測期候選球池 {pool_text}，平均期 {format_pool_average(average_pool_size)}球")

    summary_parts = [
        f"{format_stat_score(score)}({count})"
        for score, count in sorted(counter.items(), key=lambda item: (-item[0], item[1]))
        if count > 0 and score >= 3
    ]
    summary_text = "，".join(summary_parts) if summary_parts else "沒有 >=3 球命中"
    print(f"各期命中球數總結：{summary_text}")


def main() -> None:
    """主流程：驗證參數、讀取資料，並按 MODE 執行。"""
    try:
        normalize_select_groups()
        validate_print_backtest_mode()
        validate_sort_mode()
        validate_prize3_sort_settings()
        validate_lotto_list_mode()
        validate_window_draw_counts()
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
            total_backtest_count = len(check_indices)
            for window_count in WINDOW_DRAW_COUNT_LIST:
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
