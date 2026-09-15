from pathlib import Path
import csv
import random
import sys
from typing import TypedDict


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
M6_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"
M4_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M4_lotto_prize_summary.csv"

'''
(1,2,3) = 1-31 號，合共 31 球，
(2,3,4) = 10- 40 號，合共 31 球，

A = 1-9 ,B = 10-20 ,C = 21 - 31,D = 32-40. 
prize_score   = 中獎注數權重
recent_score  = 日期近期權重
mixed_score   = prize_score + recent_score
高注熱門號：
近期活躍號：
混合候選號：
'''

# MODE 可選："backtest" 或 "predict"。
MODE = "backtest"
BACKTEST_DRAW_COUNT_LIST = [10]
WINDOW_DRAW_COUNT_LIST = [24]

# DOUBLE_MODE_GROUPS 會在同一窗口期內，分 2 個選組模式獨立分析。
DOUBLE_MODE_GROUPS = ((1, 2, 3), (2, 3, 4))

# DOUBLE_MODE_SORT 可選："date_asc", "date_desc", "prize_asc", "prize_desc" 大至小。
DOUBLE_MODE_SORT = "dete_desc"

# 預測分析每類最多顯示多少個候選球。
ANALYSIS_CANDIDATE_LIMIT = 9

# ANALYSIS_WEIGHT_MODE 可選："prize", "recent", "mixed"。
ANALYSIS_WEIGHT_MODE = "recent"

# mixed 模式下，Pz3 注數與日期近期的混合比例。
PRIZE_WEIGHT_RATIO = 0.6
RECENT_WEIGHT_RATIO = 0.4

# 日期近期分，窗口內越近期越接近 RECENT_WEIGHT_MAX。
RECENT_WEIGHT_MAX = 1.0
RECENT_WEIGHT_MIN = 0.2

# 同號在相鄰開獎期重現時，加到重現權重。
CONSECUTIVE_WEIGHT_BONUS = 2.0

# LOTTO_LIST=True 時，每期將所選組別號碼合併成一個 [] 顯示；False 則按組別分開顯示。
LOTTO_LIST = True

# PRINT_BACKTEST_MODE 可選 "detail" 或 "simple"。
# detail 會打印窗口期明細；simple 只打印每期核對、預測球與命中統計。
PRINT_BACKTEST_MODE = "detail" #"detail" 或 "simple"。

# 每一期在指定範圍內有多少球才算符合條件。
COMBINATION_TAKE_COUNT = 5
BIRTHDAY_NUM_MATCH_MODE = ">="

# 每個 double mode 最少要有多少個合條件開獎期，才產生候選球分析。
MIN_ANALYSIS_DRAW_COUNT = 5
# -------------------------
# PRIZE_OPTION=3 即顯示三獎中獎注數 prize3。
PRIZE_OPTION = 3 # 設定要顯示的獎項，3 即顯示三獎中獎注數。
PRIZE_PRINT_SHOW = True
# -------------------------
RANDOM_GROUP_TAKE_COUNT = 3
RANDOM_SEED = 20260912

# PRINT_RANDOM_RESULT=True 時顯示隨機發球、命中與統計；False 時只顯示核對日期與開獎號。
PRINT_RANDOM_RESULT = False

GROUPS = {
    1: ("1-9", 1, 9),
    2: ("10-20", 10, 20),
    3: ("21-31", 21, 31),
    4: ("32-40", 32, 40),
}


class DrawRow(TypedDict):
    date: str
    nums: list[int]
    special: int | None
    prize_count: float


class CandidateAnalysis(TypedDict):
    prize_hot: list[int]
    recent_hot: list[int]
    mixed_hot: list[int]
    hot: list[int]
    weak: list[int]
    consecutive: list[tuple[int, ...]]
    cold: list[int]
    leak: list[int]


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


def primary_group_ids() -> tuple[int, ...]:
    ''' 取得舊功能或隨機發球使用的主要組別；預設用 double mode 第一組。 '''
    if not DOUBLE_MODE_GROUPS:
        raise ValueError("DOUBLE_MODE_GROUPS 不可為空。")
    return tuple(DOUBLE_MODE_GROUPS[0])


def normalize_select_groups() -> tuple[int, ...]:
    ''' 檢查主要組別型別、組別範圍與最少組數。 '''
    group_ids = primary_group_ids()
    if len(group_ids) < 2:
        raise ValueError("DOUBLE_MODE_GROUPS 第一組最少需要選 2 個組別，例如 (1, 2) 或 (1, 2, 3)。")
    for group_id in group_ids:
        if group_id not in GROUPS:
            raise ValueError(f"DOUBLE_MODE_GROUPS 只可選 1,2,3,4；錯誤值：{group_id}")
    return group_ids


def validate_print_backtest_mode() -> None:
    ''' 檢查 backtest 打印模式，只可使用 detail 或 simple。 '''
    if PRINT_BACKTEST_MODE not in ("detail", "simple"):
        raise ValueError('PRINT_BACKTEST_MODE 只可設定為 "detail" 或 "simple"。')


def validate_double_mode() -> None:
    ''' 檢查 double mode 分組與排序設定。 '''
    if DOUBLE_MODE_SORT not in ("date_asc", "date_desc", "prize_asc", "prize_desc"):
        raise ValueError('DOUBLE_MODE_SORT 只可設定為 "date_asc", "date_desc", "prize_asc", "prize_desc"。')
    for group_ids in DOUBLE_MODE_GROUPS:
        if not isinstance(group_ids, (tuple, list)) or len(group_ids) < 2:
            raise ValueError("DOUBLE_MODE_GROUPS 每組最少需要 2 個組別，例如 (1, 2, 3)。")
        for group_id in group_ids:
            if group_id not in GROUPS:
                raise ValueError(f"DOUBLE_MODE_GROUPS 只可選 1,2,3,4；錯誤值：{group_id}")


def groups_from_ids(group_ids: tuple[int, ...] | list[int]) -> list[tuple[str, int, int]]:
    ''' 依指定 group id 取得組別設定。 '''
    return [GROUPS[group_id] for group_id in group_ids]


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
    ''' 取得合併顯示用的所選組別正號與特號。 '''
    nums: list[int] = []
    special: int | None = None
    for _name, start_num, end_num in selected_groups():
        nums.extend(selected_nums(row, start_num, end_num))
        group_special = selected_special(row, start_num, end_num)
        if group_special is not None:
            special = group_special
    return sorted(set(nums)), special


def lotto_list_nums_and_special_by_groups(row: DrawRow, group_ids: tuple[int, ...]) -> tuple[list[int], int | None]:
    ''' 取得指定選組模式的合併正號與特號。 '''
    nums: list[int] = []
    special: int | None = None
    for _name, start_num, end_num in groups_from_ids(group_ids):
        nums.extend(selected_nums(row, start_num, end_num))
        group_special = selected_special(row, start_num, end_num)
        if group_special is not None:
            special = group_special
    return sorted(set(nums)), special


def double_mode_row_result_text(row: DrawRow, group_ids: tuple[int, ...]) -> str:
    ''' 產生指定選組模式的合條件顯示文字。 '''
    nums, special = lotto_list_nums_and_special_by_groups(row, group_ids)
    ball_count = display_ball_count(len(nums), special)
    return f"{format_nums(nums, special)} /> {format_ball_count(ball_count)} 球"


def sort_double_mode_rows(rows: list[tuple[int, DrawRow]]) -> list[tuple[int, DrawRow]]:
    ''' 依 DOUBLE_MODE_SORT 排序窗口期結果。 '''
    if DOUBLE_MODE_SORT == "date_desc":
        return sorted(rows, key=lambda item: item[1]["date"], reverse=True)
    if DOUBLE_MODE_SORT == "prize_asc":
        return sorted(rows, key=lambda item: item[1]["prize_count"])
    if DOUBLE_MODE_SORT == "prize_desc":
        return sorted(rows, key=lambda item: item[1]["prize_count"], reverse=True)
    return sorted(rows, key=lambda item: item[1]["date"])


def group_id_number_pool(group_ids: tuple[int, ...]) -> list[int]:
    ''' 取得指定 double mode 覆蓋的完整球號池。 '''
    nums: set[int] = set()
    for _name, start_num, end_num in groups_from_ids(group_ids):
        nums.update(range(start_num, end_num + 1))
    return sorted(nums)


def row_analysis_numbers(row: DrawRow, group_ids: tuple[int, ...]) -> list[int]:
    ''' 取得指定模式中一期 N1..N7 的分析號碼，特號也納入候選分析。 '''
    nums, special = lotto_list_nums_and_special_by_groups(row, group_ids)
    if special is not None:
        nums = sorted(set(nums + [special]))
    return nums


def top_nums_by_score(scores: dict[int, float], limit: int = ANALYSIS_CANDIDATE_LIMIT) -> list[int]:
    ''' 依分數高低輸出候選球，分數相同時按細號在前。 '''
    return [
        num
        for num, _score in sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]


def normalize_scores(scores: dict[int, float]) -> dict[int, float]:
    ''' 將分數正規化到 0..1，避免不同量級互相壓過。 '''
    if not scores:
        return {}
    max_score = max(scores.values())
    if max_score <= 0:
        return {num: 0.0 for num in scores}
    return {num: score / max_score for num, score in scores.items()}


def recent_weight(row_position: int, total_rows: int) -> float:
    ''' 計算日期近期權重；row_position 越新分數越高。 '''
    if total_rows <= 1:
        return RECENT_WEIGHT_MAX
    ratio = row_position / (total_rows - 1)
    return RECENT_WEIGHT_MIN + (RECENT_WEIGHT_MAX - RECENT_WEIGHT_MIN) * ratio


def mixed_scores(prize_scores: dict[int, float], recent_scores: dict[int, float]) -> dict[int, float]:
    ''' 混合 Pz3 注數分與近期分。 '''
    normalized_prize = normalize_scores(prize_scores)
    normalized_recent = normalize_scores(recent_scores)
    all_nums = set(normalized_prize) | set(normalized_recent)
    return {
        num: normalized_prize.get(num, 0.0) * PRIZE_WEIGHT_RATIO
        + normalized_recent.get(num, 0.0) * RECENT_WEIGHT_RATIO
        for num in all_nums
    }


def consecutive_groups(nums: list[int]) -> list[tuple[int, ...]]:
    ''' 找出同一期內 2 個或以上相鄰球號組合。 '''
    if not nums:
        return []

    groups: list[tuple[int, ...]] = []
    current_group = [nums[0]]
    for num in nums[1:]:
        if num == current_group[-1] + 1:
            current_group.append(num)
        else:
            if len(current_group) >= 2:
                groups.append(tuple(current_group))
            current_group = [num]
    if len(current_group) >= 2:
        groups.append(tuple(current_group))
    return groups


def format_group_nums(groups: list[tuple[int, ...]]) -> str:
    ''' 格式化連號組合。 '''
    if not groups:
        return "[]"
    return "，".join(format_nums(list(group)) for group in groups)


def candidate_count_text(nums: list[int]) -> str:
    ''' 產生候選球總數文字。 '''
    return f" /> {len(nums)} 球"


def flatten_consecutive_group_nums(groups: list[tuple[int, ...]]) -> list[int]:
    ''' 將連號組合攤平成不重複球號。 '''
    nums: set[int] = set()
    for group in groups:
        nums.update(group)
    return sorted(nums)


def top_consecutive_groups_by_score(
    scores: dict[tuple[int, ...], float],
    limit: int = ANALYSIS_CANDIDATE_LIMIT,
) -> list[tuple[int, ...]]:
    ''' 依分數輸出連號組合，分數相同時按長度與細號排序。 '''
    return [
        group
        for group, _score in sorted(scores.items(), key=lambda item: (-item[1], -len(item[0]), item[0]))[:limit]
    ]


def analyze_double_mode_candidates(
    matched_rows: list[tuple[int, DrawRow]],
    group_ids: tuple[int, ...],
) -> CandidateAnalysis:
    ''' 按 Pz3 累計與連續期權重，產生四類下期候選球。 '''
    number_pool = group_id_number_pool(group_ids)
    appear_count = {num: 0 for num in number_pool}
    hot_scores = {num: 0.0 for num in number_pool}
    recent_scores = {num: 0.0 for num in number_pool}
    repeat_scores = {num: 0.0 for num in number_pool}
    consecutive_group_scores: dict[tuple[int, ...], float] = {}

    chronological_rows = sorted(matched_rows, key=lambda item: item[0])
    total_rows = len(chronological_rows)
    previous_index: int | None = None
    previous_nums: set[int] = set()

    for row_position, (row_index, row) in enumerate(chronological_rows):
        nums = row_analysis_numbers(row, group_ids)
        prize_weight = row["prize_count"]
        date_weight = recent_weight(row_position, total_rows)
        for num in nums:
            appear_count[num] = appear_count.get(num, 0) + 1
            hot_scores[num] = hot_scores.get(num, 0.0) + prize_weight
            recent_scores[num] = recent_scores.get(num, 0.0) + date_weight
        for group in consecutive_groups(nums):
            consecutive_group_scores[group] = consecutive_group_scores.get(group, 0.0) + prize_weight

        if previous_index is not None and row_index == previous_index + 1:
            repeated_nums = previous_nums.intersection(nums)
            for num in repeated_nums:
                repeat_scores[num] = repeat_scores.get(num, 0.0) + prize_weight * CONSECUTIVE_WEIGHT_BONUS

        previous_index = row_index
        previous_nums = set(nums)

    appeared_nums = {num for num, count in appear_count.items() if count > 0}
    hot_candidates = {
        num: score
        for num, score in hot_scores.items()
        if appear_count.get(num, 0) >= 2
    }
    recent_candidates = {
        num: score
        for num, score in recent_scores.items()
        if appear_count.get(num, 0) > 0
    }
    mixed_candidates = mixed_scores(hot_candidates, recent_candidates)
    weak_candidates = {
        num: hot_scores.get(num, 0.0)
        for num, count in appear_count.items()
        if count == 1 and repeat_scores.get(num, 0.0) == 0
    }
    cold_candidates = {num: 1.0 for num in number_pool if num not in appeared_nums}

    prize_hot_result = top_nums_by_score(hot_candidates)
    recent_hot_result = top_nums_by_score(recent_candidates)
    mixed_hot_result = top_nums_by_score(mixed_candidates)
    hot_result = {
        "prize": prize_hot_result,
        "recent": recent_hot_result,
        "mixed": mixed_hot_result,
    }.get(ANALYSIS_WEIGHT_MODE, mixed_hot_result)
    weak_result = top_nums_by_score(weak_candidates)
    consecutive_result = top_consecutive_groups_by_score(consecutive_group_scores)
    cold_result = sorted(cold_candidates)[:ANALYSIS_CANDIDATE_LIMIT]
    covered_nums = set(hot_result)
    covered_nums.update(weak_result)
    covered_nums.update(flatten_consecutive_group_nums(consecutive_result))
    covered_nums.update(cold_result)
    leak_result = [num for num in number_pool if num not in covered_nums]

    return {
        "prize_hot": prize_hot_result,
        "recent_hot": recent_hot_result,
        "mixed_hot": mixed_hot_result,
        "hot": hot_result,
        "weak": weak_result,
        "consecutive": consecutive_result,
        "cold": cold_result,
        "leak": leak_result,
    }


def print_double_mode_candidate_analysis(
    matched_rows: list[tuple[int, DrawRow]],
    group_ids: tuple[int, ...],
) -> None:
    ''' 打印指定 double mode 的四類下期候選球分析。 '''
    result = analyze_double_mode_candidates(matched_rows, group_ids)
    print("預測分析：")
    prize_hot_nums = result["prize_hot"]
    recent_hot_nums = result["recent_hot"]
    mixed_hot_nums = result["mixed_hot"]
    hot_nums = result["hot"]
    weak_nums = result["weak"]
    consecutive_groups_result = result["consecutive"]
    consecutive_nums = flatten_consecutive_group_nums(consecutive_groups_result)
    cold_nums = result["cold"]
    leak_nums = result["leak"]
    print(f"高注熱門號：{format_nums(prize_hot_nums)}{candidate_count_text(prize_hot_nums)}")
    print(f"近期活躍號：{format_nums(recent_hot_nums)}{candidate_count_text(recent_hot_nums)}")
    print(f"混合候選號：{format_nums(mixed_hot_nums)}{candidate_count_text(mixed_hot_nums)}")
    print(f"熱門號：{format_nums(hot_nums)}{candidate_count_text(hot_nums)}")
    print(f"弱球號：{format_nums(weak_nums)}{candidate_count_text(weak_nums)}")
    print(f"連續號：{format_group_nums(consecutive_groups_result)}{candidate_count_text(consecutive_nums)}")
    print(f"冷門號：{format_nums(cold_nums)}{candidate_count_text(cold_nums)}")
    print(f"補漏號：{format_nums(leak_nums)}{candidate_count_text(leak_nums)}")


def row_result_text(row: DrawRow) -> str:
    ''' 產生一期的所有選中組別顯示文字與總球數。 '''
    if LOTTO_LIST:
        nums, special = lotto_list_nums_and_special(row)
        ball_count = display_ball_count(len(nums), special)
        if not is_matched(len(nums)):
            return f"[] /> {format_ball_count(ball_count)} 球"
        return f"{format_nums(nums, special)} /> {format_ball_count(ball_count)} 球"

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


def build_random_group_prediction(target_date: str, window_count: int) -> list[int]:
    ''' 按所選組別每組固定隨機發指定球數。 '''
    seed = RANDOM_SEED + int(target_date.replace("-", "")) + window_count
    rng = random.Random(seed)
    predicted: list[int] = []
    for _name, start_num, end_num in selected_groups():
        predicted.extend(sorted(rng.sample(range(start_num, end_num + 1), RANDOM_GROUP_TAKE_COUNT)))
    return sorted(predicted)


def prediction_hit_score(normal_hit_count: int, special_hit: int | None) -> float:
    ''' 計算預測命中球數；特號命中固定加 0.5。 '''
    score = float(normal_hit_count)
    if special_hit is not None:
        score += 0.5
    return score


def random_backtest_result(check_row: DrawRow, window_count: int) -> tuple[str, float]:
    ''' 產生 backtest 核對文字與命中球數。 '''
    predicted = build_random_group_prediction(check_row["date"], window_count)
    predicted_set = set(predicted)
    normal_hits = sorted(num for num in check_row["nums"] if num in predicted_set)
    special_hit = check_row["special"] if check_row["special"] in predicted_set else None
    hit_score = prediction_hit_score(len(normal_hits), special_hit)
    text = (
        f"核對日期：{check_row['date']}: {all_check_nums_text(check_row)}，"
        f"預測球 {format_nums(predicted)}，"
        f"命中: {format_hit_nums(normal_hits, special_hit)} /> {format_ball_count(hit_score)} 球。"
    )
    return text, hit_score


def check_draw_text(check_row: DrawRow) -> str:
    ''' 只顯示核對日期與核對期開獎號。 '''
    return f"核對日期：{check_row['date']}: {all_check_nums_text(check_row)}"


def predict_target_text(next_draw_date: str) -> str:
    ''' 顯示 predict 模式的下期開獎日期。 '''
    return f"下期開獎日期：{next_draw_date or '未知'}"


def random_backtest_text(check_row: DrawRow, window_count: int) -> str:
    ''' 產生 backtest 核對文字，包含預測球與命中球數。 '''
    text, _hit_score = random_backtest_result(check_row, window_count)
    return text


def random_predict_text(next_draw_date: str, window_count: int) -> str:
    ''' 隨機發球功能 '''
    target_date = next_draw_date or "00000000"
    predicted = build_random_group_prediction(target_date, window_count)
    return f"下期開獎日期：{next_draw_date or '未知'}，預測球 {format_nums(predicted)}。"


def print_query_setting() -> None:
    ''' 打印本次執行的模式與主要查詢參數。 '''
    print("====== m_v1 1-40 開獎紀錄基查 ======")
    print(f"運作模式：{MODE}")
    print(f"Double mode：{DOUBLE_MODE_GROUPS}")
    print(f"Double mode 排序：{DOUBLE_MODE_SORT}")
    print(f"分析權重模式：{ANALYSIS_WEIGHT_MODE}")
    print(f"混合權重：Pz3={PRIZE_WEIGHT_RATIO:g}，近期={RECENT_WEIGHT_RATIO:g}")
    print(f"回測打印模式：{PRINT_BACKTEST_MODE}")
    print(f"隨機發球顯示：{PRINT_RANDOM_RESULT}")
    print(f"回測期列表：{BACKTEST_DRAW_COUNT_LIST}")
    print(f"窗口期列表：{WINDOW_DRAW_COUNT_LIST}")
    print(f"符合條件：範圍內號碼數量 {BIRTHDAY_NUM_MATCH_MODE}{COMBINATION_TAKE_COUNT} 球")
    print(f"最少合分析期數：{MIN_ANALYSIS_DRAW_COUNT}")
    print(f"查詢號碼：N1..N7，N7 特號以 * 顯示")
    display_text = "合併號碼" if LOTTO_LIST else "分組號碼"
    prize_show_text = f"，Pz{PRIZE_OPTION}" if PRIZE_PRINT_SHOW else ""
    print(f"顯示欄位：開獎日期，{display_text}，N球{prize_show_text}")
    print()


def print_draw_rows(
    draws: list[DrawRow],
    window_rows: list[tuple[int, DrawRow]],
    target_index: int,
) -> None:
    ''' 打印窗口期內每一期的組別分布。 '''
    rank_width = len(str(len(window_rows)))
    for row_index, row in window_rows:
        rank = target_index - row_index + 1
        print(
            f"近 {rank:>{rank_width}}期：{row['date']}，{row_result_text(row)}"
            f"{prize_print_text(row)}"
        )


def print_double_mode_draw_rows(
    window_rows: list[tuple[int, DrawRow]],
    target_index: int,
    footer_text: str,
) -> None:
    ''' 分 2 個選組模式，只打印合條件的窗口期明細。 '''
    rank_width = len(str(len(window_rows)))
    for mode_index, group_ids in enumerate(DOUBLE_MODE_GROUPS, start=1):
        if mode_index > 1:
            print("-----")
        print(f"{mode_index}，{tuple(group_ids)}")

        matched_rows: list[tuple[int, DrawRow]] = []
        for row_index, row in window_rows:
            nums, _special = lotto_list_nums_and_special_by_groups(row, tuple(group_ids))
            if is_matched(len(nums)):
                matched_rows.append((row_index, row))

        for row_index, row in sort_double_mode_rows(matched_rows):
            rank = target_index - row_index + 1
            print(
                f"近 {rank:>{rank_width}}期：{row['date']}，{double_mode_row_result_text(row, tuple(group_ids))}"
                f"{prize_print_text(row)}"
            )
        if len(matched_rows) >= MIN_ANALYSIS_DRAW_COUNT:
            print_double_mode_candidate_analysis(matched_rows, tuple(group_ids))
        else:
            print(
                f"合分析期數不足：{len(matched_rows)} / {MIN_ANALYSIS_DRAW_COUNT}，"
                f"暫不產生預測分析。"
            )
        print(footer_text)


def query_mode_text() -> str:
    ''' 產生標題用的查詢模式文字。 '''
    group_ids = normalize_select_groups()
    if group_ids == tuple(GROUPS.keys()):
        return "全組別"
    return f"自選組別 {group_ids}"


def print_backtest_window(
    draws: list[DrawRow],
    check_index: int,
    backtest_count: int,
    window_count: int,
    backtest_index: int,
    total_backtest_count: int,
) -> float:
    ''' 打印單一期 backtest 窗口資料與核對結果。 '''
    check_row = draws[check_index]
    display_backtest_index = total_backtest_count - backtest_index + 1
    window_start_index = max(0, check_index - window_count)
    window_rows = [
        (row_index, row)
        for row_index, row in enumerate(draws[window_start_index:check_index], start=window_start_index)
    ]
    backtest_text, hit_score = random_backtest_result(check_row, window_count)
    if PRINT_BACKTEST_MODE == "simple":
        if PRINT_RANDOM_RESULT:
            print(backtest_text)
        else:
            print(check_draw_text(check_row))
        return hit_score

    print(
        f"======[回測 {display_backtest_index}] "
        f"{query_mode_text()}，參數，回測期= {backtest_count}，N1..N7，窗口期 = {window_count} ======"
    )
    print(f"backtest：窗口期不包括核對期，預留核對預測")
    print_double_mode_draw_rows(window_rows, check_index - 1, check_draw_text(check_row))
    if PRINT_RANDOM_RESULT:
        print(backtest_text)
    print()
    return hit_score


def print_predict_window(draws: list[DrawRow], window_count: int, next_draw_date: str) -> None:
    ''' 打印 predict 模式最後窗口期資料與下期預測。 '''
    latest_index = len(draws) - 1
    window_start_index = max(0, latest_index - window_count + 1)
    window_rows = [
        (row_index, row)
        for row_index, row in enumerate(draws[window_start_index:latest_index + 1], start=window_start_index)
    ]
    print(f"====== Double mode，預測模式，N1..N7，窗口期 = {window_count} ======")
    print(f"predict：窗口期包括最後一期開獎號，預測下期未知開獎")
    print_double_mode_draw_rows(window_rows, latest_index, predict_target_text(next_draw_date))
    if PRINT_RANDOM_RESULT:
        print(random_predict_text(next_draw_date, window_count))
    print()


def print_hit_score_summary(backtest_count: int, window_count: int, hit_scores: list[float]) -> None:
    ''' 按命中球數統計回測期數。 '''
    if not hit_scores:
        return

    max_score = max(6.0, max(hit_scores))
    score_steps = [score / 2 for score in range(int(max_score * 2), -1, -1)]
    score_counts = {score: 0 for score in score_steps}
    for score in hit_scores:
        score_counts[score] = score_counts.get(score, 0) + 1

    print()
    print(f"=== 回測期 = {backtest_count} 期，窗口期 = {window_count}，預測球命中統計：===")
    for score in score_steps:
        if score == 2.5:
            print("------")
        print(f"{format_ball_count(score):>3} = {score_counts.get(score, 0)} 期")
    print()


def main() -> None:
    ''' 主流程：驗證參數、讀取資料，並按 MODE 執行。 '''
    try:
        normalize_select_groups()
        validate_print_backtest_mode()
        validate_double_mode()
    except ValueError as exc:
        print(f"參數錯誤：{exc}", file=sys.stderr)
        raise SystemExit(1)

    draws = read_draws()
    if not draws:
        raise FileNotFoundError(f"找不到或未能讀取 M6：{M6_CSV}")

    print_query_setting()
    latest_index = len(draws) - 1

    if MODE == "backtest":
        for backtest_count in BACKTEST_DRAW_COUNT_LIST:
            first_check_index = max(0, latest_index - backtest_count + 1)
            check_indices = range(first_check_index, latest_index + 1)
            for window_count in WINDOW_DRAW_COUNT_LIST:
                total_backtest_count = len(check_indices)
                hit_scores: list[float] = []
                for backtest_index, check_index in enumerate(check_indices, start=1):
                    hit_scores.append(print_backtest_window(
                        draws,
                        check_index,
                        backtest_count,
                        window_count,
                        backtest_index,
                        total_backtest_count,
                    ))
                if PRINT_RANDOM_RESULT:
                    print_hit_score_summary(backtest_count, window_count, hit_scores)
    elif MODE == "predict":
        next_draw_date = read_next_draw_date()
        for window_count in WINDOW_DRAW_COUNT_LIST:
            print_predict_window(draws, window_count, next_draw_date)
    else:
        raise ValueError('MODE 只能是 "backtest" 或 "predict"')


if __name__ == "__main__":
    main()
