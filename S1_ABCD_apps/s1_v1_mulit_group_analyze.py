from pathlib import Path
import csv
import importlib.util
from collections import Counter
from itertools import combinations
from typing import Optional, TypedDict

''' 
A,B,C,D, (1-9) , (10-20) , (21-31) , (32-40), (分組查詢)
1-9,   [1,3,5,7,9], [2,4,6,8] = 9 球
10-20, [11,13,15,17,19], [10,12,14,16,18,20] = 11 球
21-31, [21,23,25,27,29,31], [22,24,26,28,30] = 11 球
32-40, [33,35,37,39], [32,34,36,38,40] = 9 球 
重點已改好：
- 近 1 期不納入 ABCD 四類屬性累計
- 四類屬性只用近 2 至 N 期
- 查詢條件 N1..N7，特號 = 1 球
- HFB 高頻膽號 / HFL 高頻腳號改為同組雙開或多開期分析
- 同組雙開或多開期內出現 >= 2 次 = HFB 高頻膽號
- 同組雙開或多開期內出現 1 次 = HFL 高頻腳號
- ANB 缺席球 / HFB 高頻膽號 / HFL 高頻腳號 / OTN 單次球 四類互斥，合計補滿該組全部號碼
- 維度熱門號保持獨立，可與以上四類重複
- 近 1 期比對現在會顯示
absent_number_balls = ANB / 缺席球 
high_frequency_banker = HFB / 高頻膽號 
high_frequency_leg = HFL / 高頻腳號 
once_times_number = OTN / 單次球
維度 = #1,#2 #3 / 

1-9 ＝9 球，10-20 ＝11 球，21- 31 ＝11 球，32-40 ＝9 球。
所以 ABCD 1-40 球分析。
最後顯示 1-40 ，必定分析出 在那屬性分組在。
'''

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
M6_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"
M4_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M4_lotto_prize_summary.csv"
COMBO_TREND_SCRIPT = CURRENT_DIR / "S1_v1_combo_trend_analyze.py"
TREND_PRED_CSV = CURRENT_DIR / "backtest_pred_data" / "trend_pred.csv"
BACKTEST_ABCD_GROUP_RESULTS_CSV = CURRENT_DIR / "backtest_pred_data" / "backtest_ABCD_group_results.csv"
LASTDRAW_HIT_HFB_RESULTS_CSV = CURRENT_DIR / "backtest_pred_data" / "lastDraw_hit_HFB_results.csv"


# MODE 可選："backtest" 或 "predict"。
VERSION = "S1_v1 1-40 mulit_group_analyze"
'''
只有 predict 同步趨勢預測。 backtest mode 獨立。 
BACKTEST_DRAW_COUNT_LIST = [1] 同步 
WINDOW_DRAW_COUNT_LIST = [19] 同步
'''

MODE = "predict" # 
BACKTEST_DRAW_COUNT_LIST = [1]
WINDOW_DRAW_COUNT_LIST = [19]

# SELECT_GROUPS 可選 1,2,3,4；例如 (1,) 只查 1-9，(1,2,3,4) 全組別。
'''
SELECT_GROUPS = (1)           # 只選 1-9
SELECT_GROUPS = (1, 2, 3)      # 自選 1-31
SELECT_GROUPS = (1, 2, 3, 4)   # 全組別 1-40
SELECT_GROUPS = (2, 4)         # 只選 10-20 + 32-40
'''
SELECT_GROUPS = (1,2,3,4) # select group index = 1

# 每一期在指定範圍內有多少球才算符合條件。
COMBINATION_TAKE_COUNT = 4
BIRTHDAY_NUM_MATCH_MODE = ">="

# LOTTO_LIST=True 時，每期將所選組別號碼合併成一個 [] 顯示；False 則按組別分開顯示。
''' backtest,窗口期不包括核對期,預留核對預測
False = 近 10期:2026-08-27,[12,17],[25,31],[*35] /> 4.5 球
Treu = 近 10期:2026-08-27,[12,17,25,31,*35] /> 4.5 球
'''
LOTTO_LIST = False

# PRINT_BACKTEST_MODE 可選 "detail" 或 "simple"。
# detail 會打印窗口期明細；simple 只打印每期核對、預測球與命中統計。
PRINT_BACKTEST_MODE = "detail" #"detail" 或 "simple"。

# -------------------------
# PRIZE_OPTION=3 即顯示三獎中獎注數 prize3。
PRIZE_OPTION = 3 # 設定要顯示的獎項，3 即顯示三獎中獎注數。
PRIZE_PRINT_SHOW = False

# 是否顯示 A-D 分組冷熱門、R/B/G 分組累計。
PRINT_ODD_EVEN_GROUP_ANALYSIS = False
PRINT_RBG_GROUP_ANALYSIS = False

# 是否顯示 ABCD 四種分析屬性。
PRINT_ABCD_PROPERTY_ANALYSIS = True # True 顯示 ANB/HFB/HFL/OTN 四類屬性。
PRINT_HIGH_FREQ_PAIR_ANALYSIS = True # True 顯示 HFB 高頻膽號與 HFL 高頻腳號。
PRINT_WEAK_NUM_ANALYSIS = True # True 顯示 OTN 單次球。
HIGH_FREQ_MIN_PAIR_COUNT = 2 # HFB 高頻膽號門檻：同組雙開或多開期內出現次數必須達到此數值。

# 是否顯示維度熱門號：近 1 期只作比對；由近 2 期起，每 6 期切一個維度。
PRINT_DIMENSION_HOT_NUM_ANALYSIS = True
DIMENSION_DRAW_COUNT = 6 # 每個維度包含幾期。
DIMENSION_HOT_MIN_COUNT = 2 # 同一維度內單球重開次數必須達到此數值。

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


def read_trend_pred_rows() -> list[dict[str, str]]:
    ''' 讀取組合走趨 predict mode 產生的 trend_pred.csv。 '''
    if not TREND_PRED_CSV.exists():
        return []
    return read_csv_rows(TREND_PRED_CSV)


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


def sync_trend_pred_csv(window_count: int) -> None:
    ''' predict 模式先同步執行組合走趨分析，產生同窗口期 trend_pred.csv。 '''
    if not COMBO_TREND_SCRIPT.exists():
        print(f"未找到組合走趨分析程式：{COMBO_TREND_SCRIPT}")
        return

    spec = importlib.util.spec_from_file_location("s1_combo_trend_predict", COMBO_TREND_SCRIPT)
    if spec is None or spec.loader is None:
        print(f"未能載入組合走趨分析程式：{COMBO_TREND_SCRIPT}")
        return

    combo_trend = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(combo_trend)
    combo_draws = combo_trend.read_draws()
    combo_next_draw_infos = combo_trend.read_next_draw_infos()
    combo_record = combo_trend.build_predict_trend_record(
        combo_draws,
        window_count,
        combo_next_draw_infos,
    )
    combo_trend.write_csv_rows(combo_trend.TREND_PRED_CSV, [combo_record])


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
    ''' 計算查詢顯示球數；N1..N7 以 7 球計，特號當 1 球。 '''
    return float(row_selected_ball_count(row))


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


def is_matched(count: int) -> bool:
    ''' 判斷單組正號數量是否符合查詢條件。 '''
    if BIRTHDAY_NUM_MATCH_MODE == "==":
        return count == COMBINATION_TAKE_COUNT
    if BIRTHDAY_NUM_MATCH_MODE == "<=":
        return count <= COMBINATION_TAKE_COUNT
    return count >= COMBINATION_TAKE_COUNT


def is_abcd_property_matched(count: int) -> bool:
    ''' ABCD 屬性分析專用：條件跟隨主查詢參數。 '''
    return is_matched(count)


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
        rank = target_index - row_index + 1
        result_text = ""
        if is_matched(row_selected_ball_count(row)):
            result_text = f"{row_result_text(row)}{prize_print_text(row)}"
        print(
            f"近 {rank:>2}期：{row['date']}，{result_text}"
        )


def matched_window_count(window_rows: list[tuple[int, DrawRow]]) -> int:
    ''' 統計窗口期內符合查詢條件的期數。 '''
    return sum(1 for _row_index, row in window_rows if is_matched(row_selected_ball_count(row)))


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
        if not is_matched(row_selected_ball_count(row)):
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
            if count >= HIGH_FREQ_MIN_PAIR_COUNT
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
    if not PRINT_HIGH_FREQ_PAIR_ANALYSIS:
        return []

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
    if not PRINT_WEAK_NUM_ANALYSIS:
        return []

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
    if not PRINT_ABCD_PROPERTY_ANALYSIS:
        return {}

    analysis_rows = property_analysis_rows(window_rows, target_index)
    pair_data = high_freq_pair_data(analysis_rows)
    print()
    print(
        f"---------------- {format_group_ids(selected_group_ids())} "
        "A/B/C/D 選組分析屬性 ----------------"
    )
    print(
        f"ABCD 屬性條件：各組獨立，每期合併分組總球數  "
        f"{BIRTHDAY_NUM_MATCH_MODE} {COMBINATION_TAKE_COUNT} 球 (包括特號)"
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


def dimension_rows(
    window_rows: list[tuple[int, DrawRow]],
    target_index: int,
    dimension_no: int,
) -> list[tuple[int, DrawRow]]:
    """取得指定維度資料；#1=近2-7期，#2=近8-13期。"""
    rank_start = 2 + (dimension_no - 1) * DIMENSION_DRAW_COUNT
    rank_end = rank_start + DIMENSION_DRAW_COUNT - 1
    return [
        (row_index, row)
        for row_index, row in window_rows
        if rank_start <= target_index - row_index + 1 <= rank_end
    ]


def dimension_hot_nums(
    window_rows: list[tuple[int, DrawRow]],
    target_index: int,
) -> dict[int, dict[int, list[int]]]:
    """統計各維度內，各組單獨 1 球重開達到門檻的熱門號。"""
    dimension_count = max(0, (len(window_rows) - 1) // DIMENSION_DRAW_COUNT)
    result: dict[int, dict[int, list[int]]] = {}

    for dimension_no in range(1, dimension_count + 1):
        counters: dict[int, Counter[int]] = {group_id: Counter() for group_id in GROUPS}
        for _row_index, row in dimension_rows(window_rows, target_index, dimension_no):
            for group_id in selected_group_ids():
                nums = group_nums_with_special(row, group_id)
                if len(nums) == 1:
                    counters[group_id][nums[0]] += 1

        result[dimension_no] = {}
        for group_id in selected_group_ids():
            hot_nums = [
                num
                for num, count in sorted(counters[group_id].items(), key=lambda item: (-item[1], item[0]))
                if count >= DIMENSION_HOT_MIN_COUNT
            ]
            result[dimension_no][group_id] = sorted(hot_nums)

    return result


def near_one_dimension_hits(
    near_one_row: DrawRow,
    hot_by_dimension: dict[int, dict[int, list[int]]],
) -> list[str]:
    """用近 1 期開獎號比對維度熱門號。"""
    near_one_nums = {
        num
        for num in near_one_row["nums"]
        if 1 <= num <= 40
    }
    if near_one_row["special"] is not None and 1 <= near_one_row["special"] <= 40:
        near_one_nums.add(near_one_row["special"])

    hit_parts: list[str] = []
    for dimension_no in sorted(hot_by_dimension):
        dimension_hot_nums_set = {
            num
            for group_hot_nums in hot_by_dimension[dimension_no].values()
            for num in group_hot_nums
        }
        hits = sorted(near_one_nums & dimension_hot_nums_set)
        if hits:
            hit_parts.append(f"#{dimension_no}{format_nums(hits)}")
    return hit_parts


def near_one_high_freq_dan_hits(
    near_one_row: DrawRow,
    pair_data: dict[int, tuple[list[int], list[int]]],
) -> list[int]:
    """用近 1 期開獎號比對高頻膽號。"""
    near_one_nums = {
        num
        for num in near_one_row["nums"]
        if 1 <= num <= 40
    }
    if near_one_row["special"] is not None and 1 <= near_one_row["special"] <= 40:
        near_one_nums.add(near_one_row["special"])

    dan_nums = {
        num
        for group_id in selected_group_ids()
        for num in pair_data.get(group_id, ([], []))[0]
    }
    return sorted(near_one_nums & dan_nums)


def print_dimension_hot_num_analysis(
    window_rows: list[tuple[int, DrawRow]],
    target_index: int,
    pair_data: Optional[dict[int, tuple[list[int], list[int]]]] = None,
) -> None:
    """打印維度熱門號分析；近 1 期只用來比對，不納入維度統計。"""
    if not PRINT_DIMENSION_HOT_NUM_ANALYSIS:
        return
    if len(window_rows) < DIMENSION_DRAW_COUNT + 1:
        return

    hot_by_dimension = dimension_hot_nums(window_rows, target_index)
    if not hot_by_dimension:
        return

    print()
    print("----- 維度熱門號分析 #1/#2/#3 -----")
    print(
        f"維度規則：近 1 期只作比對；由近 2 期起每 {DIMENSION_DRAW_COUNT} 期一維，"
        f"同組單獨 1 球重開 >= {DIMENSION_HOT_MIN_COUNT} 次"
    )
    for dimension_no in sorted(hot_by_dimension, reverse=True):
        parts: list[str] = []
        for group_id in selected_group_ids():
            code = GROUP_CODES[group_id]
            parts.append(f"{code}{format_nums(hot_by_dimension[dimension_no].get(group_id, []))}")
        print(f"#{dimension_no} 維{dimension_no}：" + "，".join(parts))

    near_one_row = max(window_rows, key=lambda item: item[0])[1]
    hit_parts = near_one_dimension_hits(near_one_row, hot_by_dimension)
    dimension_hit_text = "，".join(hit_parts) if hit_parts else "[]"
    hfb_nums = merged_hfb_nums(pair_data or {})
    dan_hits, dan_special = hfb_check_nums(near_one_row, hfb_nums)
    dan_hit_count = hfb_hit_score(dan_hits, dan_special)
    near_one_hit_count = row_selected_hit_ball_count(near_one_row)
    print(
        f"近 1 期比對：{near_one_row['date']}，開獎號 {all_check_nums_text(near_one_row)}，"
        f"/> {format_ball_count(near_one_hit_count)} 球，"
        f"重開提示：維度 {dimension_hit_text}，"
        f"HFB {format_nums(dan_hits, dan_special)} /> {format_ball_count(dan_hit_count)} 球"
    )


def merged_hfb_nums(pair_data: dict[int, tuple[list[int], list[int]]]) -> list[int]:
    """合併所選組別的 HFB 高頻膽號。"""
    nums = {
        num
        for group_id in selected_group_ids()
        for num in pair_data.get(group_id, ([], []))[0]
    }
    return sorted(nums)


def merged_hfl_nums(pair_data: dict[int, tuple[list[int], list[int]]]) -> list[int]:
    """合併所選組別的 HFL 高頻配腳號。"""
    nums = {
        num
        for group_id in selected_group_ids()
        for num in pair_data.get(group_id, ([], []))[1]
    }
    return sorted(nums)


def hfb_check_nums(check_row: DrawRow, hfb_nums: list[int]) -> tuple[list[int], Optional[int]]:
    """用核對期 N1..N7 比對 HFB；特號命中時以 * 顯示。"""
    hfb_set = set(hfb_nums)
    normal_hits = sorted(num for num in row_selected_normal_nums(check_row) if num in hfb_set)
    special = next(
        (
            selected_special(check_row, start_num, end_num)
            for _name, start_num, end_num in selected_groups()
            if selected_special(check_row, start_num, end_num) is not None
        ),
        None,
    )
    special_hit = special if special is not None and special in hfb_set else None
    return normal_hits, special_hit


def hfb_hit_score(hit_nums: list[int], hit_special: Optional[int]) -> float:
    """HFB 對獎命中球數；特號以 0.5 球計。"""
    return len(hit_nums) + (0.5 if hit_special is not None else 0)


def hfb_near_one_score(pair_data: dict[int, tuple[list[int], list[int]]], near_one_row: DrawRow) -> float:
    """窗口近 1 期與 HFB 的重開命中球數；特號以 0.5 球計。"""
    hfb_nums = merged_hfb_nums(pair_data)
    hit_nums, hit_special = hfb_check_nums(near_one_row, hfb_nums)
    return hfb_hit_score(hit_nums, hit_special)


def print_backtest_hfb_check(pair_data: dict[int, tuple[list[int], list[int]]], check_row: DrawRow) -> float:
    """打印 backtest 每一期最後的 HFB 高頻膽號 / HFL 高頻配腳號核對。"""
    hfb_nums = merged_hfb_nums(pair_data)
    hfl_nums = merged_hfl_nums(pair_data)
    hfb_hit_nums, hfb_hit_special = hfb_check_nums(check_row, hfb_nums)
    hfb_hit_count = hfb_hit_score(hfb_hit_nums, hfb_hit_special)
    hfl_hit_nums, hfl_hit_special = hfb_check_nums(check_row, hfl_nums)
    hfl_hit_count = hfb_hit_score(hfl_hit_nums, hfl_hit_special)
    check_count = row_selected_ball_count(check_row)
    print()
    print("---- HFB 高頻膽號 / HFL 高頻配腳號核對 -----")
    print(f"HFB 高頻膽號 = {format_nums(hfb_nums)} /> {len(hfb_nums)} 球")
    print()
    print(f"HFL 高頻配腳號 = {format_nums(hfl_nums)} /> {len(hfl_nums)} 球")
    print(
        f"核對期 {check_row['date']}，{lotto_list_text(check_row)} /> {check_count} 球，"
        f"HFB 命中：{format_nums(hfb_hit_nums, hfb_hit_special)} /> {format_ball_count(hfb_hit_count)} 球，"
        f"HFL 命中：{format_nums(hfl_hit_nums, hfl_hit_special)} /> {format_ball_count(hfl_hit_count)} 球"
    )
    return hfb_hit_count


def backtest_hfb_result_record(
    pair_data: dict[int, tuple[list[int], list[int]]],
    check_row: DrawRow,
) -> dict[str, object]:
    """建立 backtest HFB 核對結果 CSV record。"""
    hfb_nums = merged_hfb_nums(pair_data)
    hit_nums, hit_special = hfb_check_nums(check_row, hfb_nums)
    hit_count = hfb_hit_score(hit_nums, hit_special)
    return {
        "date": check_row["date"],
        "(ABCD 1-40)": all_check_nums_text(check_row),
        "條件球數": row_selected_ball_count(check_row),
        "高頻膽號候選池數量": len(hfb_nums),
        "命中號": format_nums(hit_nums, hit_special),
        "命中球數": format_ball_count(hit_count),
    }


def lastdraw_hit_hfb_result_record(
    pair_data: dict[int, tuple[list[int], list[int]]],
    near_one_row: DrawRow,
) -> dict[str, object]:
    """建立近 1 期比對 HFB 回測結果 CSV record。"""
    hfb_nums = merged_hfb_nums(pair_data)
    hit_nums, hit_special = hfb_check_nums(near_one_row, hfb_nums)
    hit_count = hfb_hit_score(hit_nums, hit_special)
    return {
        "lastDraw_data": near_one_row["date"],
        "(ABCD 1-40)": all_check_nums_text(near_one_row),
        "條件球數": format_ball_count(row_selected_hit_ball_count(near_one_row)),
        "高頻膽號候選池數量": len(hfb_nums),
        "命中號": format_nums(hit_nums, hit_special),
        "命中球數": format_ball_count(hit_count),
    }


def print_trend_pred_analysis() -> None:
    """打印組合走趨 predict mode 的下期系統預測。"""
    print()
    print("---- 下期 系統預測 mode 走趨分析  -----")
    rows = read_trend_pred_rows()
    if not rows:
        print(f"未讀取到 trend_pred.csv：{TREND_PRED_CSV}")
        return

    for row in rows:
        next_draw_date = row.get("nextDraw date", "")
        pred_mode = row.get("pred_mode", "")
        trend_text = row.get("走趨分析", "")
        score = row.get("走勢分數", "")
        level = row.get("走勢判斷", "")
        print(
            f"下期日期：{next_draw_date or '未知'}，"
            f"pred_mode：{pred_mode or '未知'}，"
            f"{trend_text or '未有走趨分析'}，"
            f"走勢分數：{score or '0'}，"
            f"走勢判斷：{level or '未知'}"
        )


def print_group_odd_even_hot_cold(window_rows: list[tuple[int, DrawRow]]) -> None:
    """按 A/B/C/D 分組，統計窗口期 N1..N7 的冷熱門排列。"""
    if not PRINT_ODD_EVEN_GROUP_ANALYSIS:
        return

    num_counter, special_counter = matched_window_num_counters(window_rows)

    print()
    print("----- A-D 分組 冷熱門累計 -----")
    for group_id in normalize_select_groups():
        name, start_num, end_num = GROUPS[group_id]
        group_code = GROUP_CODES[group_id]
        group_nums = list(range(start_num, end_num + 1))
        group_text = format_hot_cold_pairs(
            sorted_hot_cold_nums(num_counter, group_nums),
            special_counter,
        )
        print(f"{group_code}組 {name:<5}：{group_text}")


def rbg_color_id(num: int) -> int:
    """依六合彩 R/B/G 公式回傳 1=R、2=B、3=G。"""
    adjusted_num = num - 1
    return (((adjusted_num // 10) + adjusted_num) % 6 // 2) + 1


def print_group_rbg_hot_cold(window_rows: list[tuple[int, DrawRow]]) -> None:
    """按 A/B/C/D 分組，統計窗口期正號 N1..N6 的 R/B/G 顏色冷熱門排列。"""
    if not PRINT_RBG_GROUP_ANALYSIS:
        return

    num_counter, special_counter = matched_window_num_counters(window_rows)

    color_labels = {
        1: "R",
        2: "B",
        3: "G",
    }
    print()
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
            color_text = format_hot_cold_pairs(
                sorted_hot_cold_nums(num_counter, color_nums),
                special_counter,
            )
            color_parts.append(f"{color_labels[color_id]}{color_text}")
        print(f"{group_code}組-RBG {name:<5}：" + "，".join(color_parts))


def fortune_candidate_pool(window_rows: list[tuple[int, DrawRow]]) -> tuple[list[int], list[tuple[int, int, int]]]:
    ''' 分析 fortune_keys，先用單號高頻取 6 球，再產生 C(6,3) 組合。 '''
    matched_nums_list = [
        row_selected_normal_nums(row)
        for _row_index, row in window_rows
        if is_matched(row_selected_ball_count(row))
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
    matched_count = sum(1 for _row_index, row in window_rows if is_matched(row_selected_ball_count(row)))
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
        if is_matched(row_selected_ball_count(row)):
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
) -> tuple[float, float, dict[str, object], dict[str, object]]:
    """打印單一期 backtest 窗口資料與核對日期。"""
    check_row = draws[check_index]
    display_backtest_index = total_backtest_count - backtest_index + 1
    window_start_index = max(0, check_index - window_count)
    window_rows = [
        (row_index, row)
        for row_index, row in enumerate(draws[window_start_index:check_index], start=window_start_index)
    ]
    pair_data_for_stats = high_freq_pair_data(property_analysis_rows(window_rows, check_index - 1))
    near_one_row = max(window_rows, key=lambda item: item[0])[1] if window_rows else check_row
    near_one_hfb_score = hfb_near_one_score(pair_data_for_stats, near_one_row)
    check_hfb_score = hfb_hit_score(*hfb_check_nums(check_row, merged_hfb_nums(pair_data_for_stats)))
    result_record = backtest_hfb_result_record(pair_data_for_stats, check_row)
    lastdraw_result_record = lastdraw_hit_hfb_result_record(pair_data_for_stats, near_one_row)

    if PRINT_BACKTEST_MODE == "simple":
        print(f"核對日期 ： {check_row['date']}: {all_check_nums_text(check_row)}")
        return check_hfb_score, near_one_hfb_score, result_record, lastdraw_result_record

    print(
        f"======[回測 {display_backtest_index}] "
        f"{query_mode_text()}，參數，回測期= {backtest_count}，N1..N7，窗口期 = {window_count} ======"
    )
    print("backtest：窗口期不包括核對期，預留核對預測")
    print_draw_rows(draws, window_rows, check_index - 1)
    print_window_result_separator()
    print_matched_window_count(window_rows)
    pair_data = print_abcd_property_analysis(window_rows, check_index - 1)
    print_dimension_hot_num_analysis(window_rows, check_index - 1, pair_data)
    check_hfb_score = print_backtest_hfb_check(pair_data, check_row)
    print_group_odd_even_hot_cold(window_rows)
    print_group_rbg_hot_cold(window_rows)
    print()
    return check_hfb_score, near_one_hfb_score, result_record, lastdraw_result_record


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
    print_window_result_separator()
    print_matched_window_count(window_rows)
    pair_data = print_abcd_property_analysis(window_rows, latest_index)
    print_dimension_hot_num_analysis(window_rows, latest_index, pair_data)
    print_trend_pred_analysis()
    print_group_odd_even_hot_cold(window_rows)
    print_group_rbg_hot_cold(window_rows)
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


def print_hfb_hit_stat_table(title: str, counter: Counter[float], total_count: int) -> None:
    """打印 HFB 命中球數分布統計。"""
    print()
    print(title)
    print("命中球數 | 期數")
    print("-----+----------")
    for level in hfb_stat_levels():
        count = counter.get(level, 0)
        percent = (count / total_count * 100) if total_count else 0
        print(f"{format_stat_score(level):<5}| {count}期 ({percent:.1f}%)")


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
                check_hfb_counter: Counter[float] = Counter()
                near_one_hfb_counter: Counter[float] = Counter()
                backtest_result_records: list[dict[str, object]] = []
                lastdraw_result_records: list[dict[str, object]] = []
                for backtest_index, check_index in enumerate(check_indices, start=1):
                    check_hfb_score, near_one_hfb_score, result_record, lastdraw_result_record = print_backtest_window(
                        draws,
                        check_index,
                        backtest_count,
                        window_count,
                        backtest_index,
                        total_backtest_count,
                    )
                    check_hfb_counter[check_hfb_score] += 1
                    near_one_hfb_counter[near_one_hfb_score] += 1
                    backtest_result_records.append(result_record)
                    lastdraw_result_records.append(lastdraw_result_record)
                print_hfb_hit_stat_table(
                    f"----- 回測期 {backtest_count}，全部高頻膽號合併，命中核對期，窗口期={window_count} -----",
                    check_hfb_counter,
                    total_backtest_count,
                )
                print_hfb_hit_stat_table(
                    f"----- 回測期 {backtest_count}，近 1 期比對，HFB 高頻膽號重開提示，窗口期={window_count} -----",
                    near_one_hfb_counter,
                    total_backtest_count,
                )
                write_csv_rows(BACKTEST_ABCD_GROUP_RESULTS_CSV, backtest_result_records)
                write_csv_rows(LASTDRAW_HIT_HFB_RESULTS_CSV, lastdraw_result_records)
    elif MODE == "predict":
        next_draw_date = read_next_draw_date()
        for window_count in WINDOW_DRAW_COUNT_LIST:
            sync_trend_pred_csv(window_count)
            print_predict_window(draws, window_count, next_draw_date)
    else:
        raise ValueError('MODE 只能是 "backtest" 或 "predict"')


if __name__ == "__main__":
    main()
