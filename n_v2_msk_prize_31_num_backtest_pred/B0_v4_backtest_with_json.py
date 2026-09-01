from pathlib import Path
import csv
import itertools
import json
import random
from typing import TypedDict

"""
B0_v4_backtest_with_json：
以 1-9、10-20、21-31 三組生日號做回測。
每個回測期用之前 WINDOW_DRAW_COUNT 期做窗口，不包含核對期。
每個分組先獨立比較 hot / delay / middle 權重，選出該組最佳模式後寫入 JSON。
正式合併回測時，每組使用自己的最佳權重模式。

以加入 特號分析 N1..N6 + N7 的命中結果，計算每期最高命中球數，並統計總回測命中率。

WINDOW_DRAW_COUNT
COMBINATION_TAKE_COUNT
TOP_PRIZE_DRAW_COUNT
PRIZE_OPTION
RECENT_BONUS_MODES

"""


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
M6_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"
JSON_DATA_DIR = CURRENT_DIR / "json_data"
GROUP_WEIGHT_JSON = JSON_DATA_DIR / "group_weight_best_modes.json"
BET_DATA_DIR = CURRENT_DIR / "bet_data"
BET_RECORDS_CSV = BET_DATA_DIR / "bet_records.csv"
WIN_RESULTS_CSV = BET_DATA_DIR / "win_results.csv"
BACKTEST_WINDOW_CHECK_CSV = BET_DATA_DIR / "backtest_window_check_rows.csv"

# ---- 回測及窗口參數
BACKTEST_DRAW_COUNT = 10  # 回測最近多少期
WINDOW_DRAW_COUNT = 18  # 每個回測期之前，向前取多少期作窗口樣本
# ---- 回測及窗口參數自動比較
AUTO_OPTIMIZE_BACKTEST_WINDOW = True  # 可選：True 自動比較回測期及窗口期列表
BACKTEST_DRAW_COUNT_LIST = [12]  # 自動比較用回測期數
WINDOW_DRAW_COUNT_LIST = [21, 36]  # 自動比較用窗口期數
SHOW_ANALYSIS_ADVICE = True  # 可選：True 顯示本版分析建議；False 不顯示
SAVE_BACKTEST_BET_CSV = True  # 可選：True 將回測預測及命中結果寫入 bet_data
# ----
# ---- 查詢條件參數
PRINT_GROUP_OPTIONS = [1, 2, 3]  # 可選：[1]、[2]、[3]、[1, 2, 3]
COMBINATION_TAKE_COUNT = 2  # 每期開獎號在分組範圍內符合幾個號碼
BIRTHDAY_NUM_MATCH_MODE = ">="  # 可選：">=" 或 "=="
TOP_PRIZE_DRAW_COUNT = 5  # 每個分組取 prize 注數最高多少期作 pair 分析
PRIZE_OPTION = 3  # 可選：1、2、3；顯示 prize1 / prize2 / prize3 注數
SAMPLE_SORT_MODE = "prize"  # 可選："prize" 中獎注數多至少；"date" 日期遠至近

# ---- 2 球組合加權參數
PAIR_HIT_WEIGHT = 7  # 2 球組合本身出現次數權重
NUM_HIT_WEIGHT = 1  # 單號在樣本內出現次數權重
RECENT_BONUS_MODE = "hot"  # 單組 fallback 模式："hot" 最近最高；"delay" 隔期較高；"middle" 中段最高
AUTO_SELECT_GROUP_BEST_MODES = True  # 可選：True 每個分組自動選最佳權重模式並寫入 JSON
SHOW_GROUP_MODE_COMPARE = False  # 可選：True 顯示每個分組 hot / delay / middle 比較
RECENT_BONUS_MODES: dict[str, list[int]] = {
    "hot": [13, 11, 9, 7, 5, 3, 1],
    "delay": [1, 2, 3, 4, 5, 6, 7],
    "middle": [3, 5, 7, 9, 7, 5, 3],
}
CURRENT_RECENT_NUM_BONUS = RECENT_BONUS_MODES[RECENT_BONUS_MODE]
CURRENT_GROUP_RECENT_BONUS: dict[int, list[int]] = {}
MIN_PAIR_HIT_COUNT = 1  # 只顯示出現次數 >= 此值的 2 球組合
MAX_PAIR_DISPLAY_COUNT = 7  # 每組最多顯示多少個 2 球組合
GROUP_PREDICT_NUM_COUNT = 3  # 每個分組產生幾個預測號碼

# ---- 分組預測模式參數
PREDICT_MODE = "mixed"  # 可選："stable" 固定取最高分；"mixed" 權重候選中受控變化
PREDICT_RANDOM_SEED = 20260826  # mixed 模式用固定種子，方便每次回測結果一致
PREDICT_CANDIDATE_POOL_SIZE = 5  # mixed 模式從前多少個候選號中取變化


BIRTHDAY_GROUPS: dict[int, tuple[int, int]] = {
    1: (1, 9),
    2: (10, 20),
    3: (21, 31),
}


class DrawRow(TypedDict):
    date: str
    nums: list[int]
    selected_nums: list[int]
    prize_count: float


class PairScore(TypedDict):
    pair: tuple[int, int]
    pair_hit_count: int
    score: int
    hit_nums: list[int]


class BacktestSummary(TypedDict):
    backtest_rank: int
    target_date: str
    check_date: str
    check_nums_1_31_slots: list[int | None]
    predictions: list[list[int]]
    hit_nums: list[int]
    special_hit_num: int | None
    hit_score: float
    prize_level: str


class GroupModeResult(TypedDict):
    group_option: int
    group_range: str
    mode: str
    bonus_scores: list[int]
    exact_counts: dict[float, int]
    score: float


class OptimizeResult(TypedDict):
    backtest_draw_count: int
    window_draw_count: int
    best_results: dict[int, GroupModeResult]
    exact_counts: dict[float, int]
    score: float
    hit_5_or_above: int
    hit_4_or_above: int
    hit_3_or_above: int
    zero_count: int


def birthday_range(group_option: int) -> tuple[int, int]:
    """按分組參數取得生日號查詢範圍。"""

    if group_option not in BIRTHDAY_GROUPS:
        raise ValueError("PRINT_GROUP_OPTIONS 只可選 1、2、3")
    return BIRTHDAY_GROUPS[group_option]


def format_group_options(group_options: list[int]) -> str:
    """格式化分組選項及號碼範圍。"""

    group_ranges = []
    for group_option in group_options:
        start_num, end_num = birthday_range(group_option)
        group_ranges.append(f"{start_num}-{end_num}")
    return f"分組 {group_options} {' + '.join(group_ranges)}"


def validate_params() -> None:
    """檢查主要參數。"""

    if BACKTEST_DRAW_COUNT < 1:
        raise ValueError("BACKTEST_DRAW_COUNT 必須大於 0")
    if WINDOW_DRAW_COUNT < 1:
        raise ValueError("WINDOW_DRAW_COUNT 必須大於 0")
    if COMBINATION_TAKE_COUNT < 1:
        raise ValueError("COMBINATION_TAKE_COUNT 必須大於 0")
    if BIRTHDAY_NUM_MATCH_MODE not in {">=", "=="}:
        raise ValueError('BIRTHDAY_NUM_MATCH_MODE 只可選 ">=" 或 "=="')
    if PRIZE_OPTION not in {1, 2, 3}:
        raise ValueError("PRIZE_OPTION 只可選 1、2、3")
    if SAMPLE_SORT_MODE not in {"prize", "date"}:
        raise ValueError('SAMPLE_SORT_MODE 只可選 "prize" 或 "date"')
    if RECENT_BONUS_MODE not in RECENT_BONUS_MODES:
        raise ValueError('RECENT_BONUS_MODE 只可選 "hot"、"delay" 或 "middle"')
    if PREDICT_MODE not in {"stable", "mixed"}:
        raise ValueError('PREDICT_MODE 只可選 "stable" 或 "mixed"')
    if PREDICT_CANDIDATE_POOL_SIZE < GROUP_PREDICT_NUM_COUNT:
        raise ValueError("PREDICT_CANDIDATE_POOL_SIZE 必須大於或等於 GROUP_PREDICT_NUM_COUNT")
    for group_option in PRINT_GROUP_OPTIONS:
        birthday_range(group_option)


def get_recent_bonus_scores(group_option: int) -> list[int]:
    """取得目前分組使用的近期單號權重。"""

    return CURRENT_GROUP_RECENT_BONUS.get(group_option, CURRENT_RECENT_NUM_BONUS)


def read_m6_rows(csv_path: Path = M6_CSV) -> list[dict[str, str]]:
    """讀入 M6 歷史開獎資料。"""

    if not csv_path.exists():
        raise FileNotFoundError(f"找不到 M6 CSV：{csv_path}")

    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames:
            reader.fieldnames = [name.strip().lstrip("\ufeff") for name in reader.fieldnames]
        return [
            {(key or "").strip().lstrip("\ufeff"): (value or "").strip() for key, value in row.items()}
            for row in reader
        ]


def parse_nums(row: dict[str, str]) -> list[int]:
    """抽取 N1-N6 正號。"""

    nums: list[int] = []
    for idx in range(1, 7):
        try:
            nums.append(int(row.get(f"N{idx}", "0")))
        except ValueError:
            nums.append(0)
    return nums


def parse_special_num(row: dict[str, str]) -> int | None:
    """抽取 N7 特號。"""

    try:
        special_num = int(row.get("N7", "0") or 0)
    except ValueError:
        return None
    return special_num if 1 <= special_num <= 49 else None


def parse_prize_count(row: dict[str, str]) -> float:
    """抽取指定獎項的中獎注數。"""

    try:
        return float(row.get(f"prize{PRIZE_OPTION}", "0") or 0)
    except ValueError:
        return 0.0


def selected_nums(nums: list[int], group_option: int) -> list[int]:
    """只保留指定生日號分組範圍內的開獎號。"""

    start_num, end_num = birthday_range(group_option)
    return sorted(num for num in nums if start_num <= num <= end_num)


def is_matched(count: int) -> bool:
    """判斷符合號碼數量是否達到查詢條件。"""

    if BIRTHDAY_NUM_MATCH_MODE == "==":
        return count == COMBINATION_TAKE_COUNT
    return count >= COMBINATION_TAKE_COUNT


def get_window_rows_for_target(rows: list[dict[str, str]], target_index: int) -> list[dict[str, str]]:
    """取得指定回測目標期之前的窗口期，不包含目標期本身。"""

    window_start = max(0, target_index - WINDOW_DRAW_COUNT)
    return rows[window_start:target_index]


def build_matched_rows(
    rows: list[dict[str, str]],
    group_option: int,
    target_index: int,
) -> list[DrawRow]:
    """從窗口內取出符合分組條件的期數，並按參數排序。"""

    matched_rows: list[DrawRow] = []
    for row in get_window_rows_for_target(rows, target_index):
        nums = parse_nums(row)
        selected = selected_nums(nums, group_option)
        if not is_matched(len(selected)):
            continue
        matched_rows.append(
            {
                "date": row.get("nDdate", ""),
                "nums": nums,
                "selected_nums": selected,
                "prize_count": parse_prize_count(row),
            }
        )
    if SAMPLE_SORT_MODE == "date":
        return sorted(matched_rows, key=lambda item: item["date"])
    return sorted(matched_rows, key=lambda item: (-item["prize_count"], item["date"]))


def build_recent_num_bonus(matched_rows: list[DrawRow], group_option: int) -> dict[int, int]:
    """按最近符合條件期數，給單號額外加權。"""

    bonus_scores: dict[int, int] = {}
    recent_rows = sorted(matched_rows, key=lambda item: item["date"], reverse=True)
    for row, bonus in zip(recent_rows, get_recent_bonus_scores(group_option)):
        for num in row["selected_nums"]:
            bonus_scores[num] = bonus_scores.get(num, 0) + bonus
    return bonus_scores


def build_weighted_pair_scores(
    matched_rows: list[DrawRow],
    target_nums: list[int],
    group_option: int,
) -> list[PairScore]:
    """建立 2 球組合加權排序。"""

    sample_rows = matched_rows[:TOP_PRIZE_DRAW_COUNT]
    pair_counts: dict[tuple[int, int], int] = {}
    num_counts: dict[int, int] = {}
    recent_bonus = build_recent_num_bonus(matched_rows, group_option)

    for row in sample_rows:
        nums = sorted(set(row["selected_nums"]))
        for num in nums:
            num_counts[num] = num_counts.get(num, 0) + 1
        for pair in itertools.combinations(nums, 2):
            pair_counts[pair] = pair_counts.get(pair, 0) + 1

    target_selected_nums = set(selected_nums(target_nums, group_option))
    pair_scores: list[PairScore] = []
    for pair, pair_hit_count in pair_counts.items():
        if pair_hit_count < MIN_PAIR_HIT_COUNT:
            continue
        score = (
            pair_hit_count * PAIR_HIT_WEIGHT
            + (num_counts.get(pair[0], 0) + num_counts.get(pair[1], 0)) * NUM_HIT_WEIGHT
            + recent_bonus.get(pair[0], 0)
            + recent_bonus.get(pair[1], 0)
        )
        pair_scores.append(
            {
                "pair": pair,
                "pair_hit_count": pair_hit_count,
                "score": score,
                "hit_nums": sorted(set(pair) & target_selected_nums),
            }
        )

    return sorted(
        pair_scores,
        key=lambda item: (
            -item["score"],
            -item["pair_hit_count"],
            item["pair"],
        ),
    )


def build_weighted_num_scores(matched_rows: list[DrawRow], group_option: int) -> list[tuple[int, int]]:
    """建立單號加權排序，用作 3 球預測補號。"""

    sample_rows = matched_rows[:TOP_PRIZE_DRAW_COUNT]
    num_counts: dict[int, int] = {}
    recent_bonus = build_recent_num_bonus(matched_rows, group_option)

    for row in sample_rows:
        for num in sorted(set(row["selected_nums"])):
            num_counts[num] = num_counts.get(num, 0) + 1

    all_nums = set(num_counts) | set(recent_bonus)
    num_scores: list[tuple[int, int]] = []
    for num in all_nums:
        score = num_counts.get(num, 0) * NUM_HIT_WEIGHT + recent_bonus.get(num, 0)
        num_scores.append((num, score))

    return sorted(num_scores, key=lambda item: (-item[1], item[0]))


def build_stable_group_prediction(
    matched_rows: list[DrawRow],
    pair_scores: list[PairScore],
    group_option: int,
) -> list[int]:
    """按 2 球加權組合及單號權重，產生每個分組的 3 球預測。"""

    predicted_nums: list[int] = []
    for item in pair_scores:
        for num in item["pair"]:
            if num not in predicted_nums:
                predicted_nums.append(num)
            if len(predicted_nums) >= GROUP_PREDICT_NUM_COUNT:
                return sorted(predicted_nums)

    for num, _score in build_weighted_num_scores(matched_rows, group_option):
        if num not in predicted_nums:
            predicted_nums.append(num)
        if len(predicted_nums) >= GROUP_PREDICT_NUM_COUNT:
            break

    return sorted(predicted_nums)


def build_mixed_group_prediction(
    matched_rows: list[DrawRow],
    pair_scores: list[PairScore],
    target_index: int,
    group_option: int,
) -> list[int]:
    """用最高分 pair 做核心，再從加權候選號中受控抽取變化號。"""

    if not pair_scores:
        return build_stable_group_prediction(matched_rows, pair_scores, group_option)

    predicted_nums = list(pair_scores[0]["pair"])
    candidate_nums: list[int] = []
    for item in pair_scores[:PREDICT_CANDIDATE_POOL_SIZE]:
        for num in item["pair"]:
            if num not in candidate_nums:
                candidate_nums.append(num)

    for num, _score in build_weighted_num_scores(matched_rows, group_option):
        if num not in candidate_nums:
            candidate_nums.append(num)
        if len(candidate_nums) >= PREDICT_CANDIDATE_POOL_SIZE:
            break

    rng = random.Random(PREDICT_RANDOM_SEED + target_index * 10 + group_option)
    change_pool = [num for num in candidate_nums if num not in predicted_nums]
    rng.shuffle(change_pool)

    for num in change_pool:
        if num not in predicted_nums:
            predicted_nums.append(num)
        if len(predicted_nums) >= GROUP_PREDICT_NUM_COUNT:
            break

    if len(predicted_nums) < GROUP_PREDICT_NUM_COUNT:
        return build_stable_group_prediction(matched_rows, pair_scores, group_option)

    return sorted(predicted_nums[:GROUP_PREDICT_NUM_COUNT])


def build_group_prediction(
    matched_rows: list[DrawRow],
    pair_scores: list[PairScore],
    target_index: int,
    group_option: int,
) -> list[int]:
    """按參數產生分組預測號。"""

    if PREDICT_MODE == "mixed":
        return build_mixed_group_prediction(matched_rows, pair_scores, target_index, group_option)
    return build_stable_group_prediction(matched_rows, pair_scores, group_option)


def format_prize(value: float) -> str:
    """格式化注數，整數不顯示 .0。"""

    return f"{value:g}"


def format_check_num_slots(nums: list[int | None]) -> str:
    """格式化核對號碼固定格數，32-49 顯示為空位。"""

    return ",".join(str(num) if num is not None else "-" for num in nums)


def format_hit_score(hit_score: float) -> str:
    """格式化命中球數，整數不顯示 .0，特號命中顯示 .5。"""

    return f"{hit_score:g}"


def get_hit_score(normal_hit_count: int, has_special_hit: bool) -> float:
    """計算正號命中數；中特號加 0.5 球，6 個正號時仍以 6 球計。"""

    if normal_hit_count >= 6:
        return 6.0
    return normal_hit_count + (0.5 if has_special_hit else 0.0)


def get_prize_level(normal_hit_count: int, has_special_hit: bool) -> str:
    """按六合彩正號及特號命中數轉成獎級。"""

    if normal_hit_count >= 6:
        return "1獎"
    if normal_hit_count == 5 and has_special_hit:
        return "2獎"
    if normal_hit_count == 5:
        return "3獎"
    if normal_hit_count == 4 and has_special_hit:
        return "4獎"
    if normal_hit_count == 4:
        return "5獎"
    if normal_hit_count == 3 and has_special_hit:
        return "6獎"
    if normal_hit_count == 3:
        return "7獎"
    return "未中獎"


def format_list_for_csv(nums: list[int]) -> str:
    """將號碼 list 格式化成 CSV 欄位文字。"""

    return "[" + ",".join(str(num) for num in nums) + "]"


def group_csv_field_names() -> list[str]:
    """取得回測 CSV 欄位名稱。"""

    return ["bet_date", "1-9", "10-20", "21-31"]


def predictions_to_group_record(
    bet_date: str,
    predictions: list[list[int]],
    group_options: list[int],
) -> dict[str, str]:
    """將分組預測轉成 bet_records.csv 格式。"""

    group_map = {group_option: nums for group_option, nums in zip(group_options, predictions)}
    return {
        "bet_date": bet_date,
        "1-9": format_list_for_csv(group_map.get(1, [])),
        "10-20": format_list_for_csv(group_map.get(2, [])),
        "21-31": format_list_for_csv(group_map.get(3, [])),
    }


def hits_to_group_record(
    bet_date: str,
    predictions: list[list[int]],
    group_options: list[int],
    check_nums: list[int],
    special_num: int | None,
) -> dict[str, str]:
    """將每組命中號碼轉成 win_results.csv 格式。"""

    record = {
        "bet_date": bet_date,
        "1-9": "[]",
        "10-20": "[]",
        "21-31": "[]",
    }
    for group_option, predicted_nums in zip(group_options, predictions):
        start_num, end_num = birthday_range(group_option)
        group_name = f"{start_num}-{end_num}"
        group_check_nums = set(selected_nums(check_nums, group_option))
        hit_nums = sorted(set(predicted_nums) & group_check_nums)
        if special_num is not None and start_num <= special_num <= end_num and special_num in predicted_nums:
            hit_nums.append(special_num)
            hit_nums = sorted(set(hit_nums))
        record[group_name] = format_list_for_csv(hit_nums)
    return record


def write_group_csv(csv_path: Path, records: list[dict[str, str]]) -> None:
    """重建分組格式 CSV。"""

    BET_DATA_DIR.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=group_csv_field_names())
        writer.writeheader()
        writer.writerows(records)


def backtest_window_check_field_names() -> list[str]:
    """取得多組合窗口回測核對 CSV 欄位名稱。"""

    return ["backtest_draw_count", "window_draw_count", "date", "1-9", "10-20", "21-31", "hit_score"]


def build_backtest_window_check_records(
    backtest_draw_count: int,
    window_draw_count: int,
    summary_rows: list[BacktestSummary],
    group_options: list[int],
) -> list[dict[str, str]]:
    """將單一回測/窗口組合的逐期核對結果轉成 CSV 記錄。"""

    records: list[dict[str, str]] = []
    for item in summary_rows:
        if item["hit_score"] < 3:
            continue
        check_nums = [num for num in item["check_nums_1_31_slots"][:6] if num is not None]
        special_num = item["check_nums_1_31_slots"][6] if len(item["check_nums_1_31_slots"]) > 6 else None
        record = hits_to_group_record(
            item["check_date"],
            item["predictions"],
            group_options,
            check_nums,
            special_num,
        )
        records.append(
            {
                "backtest_draw_count": str(backtest_draw_count),
                "window_draw_count": str(window_draw_count),
                "date": record["bet_date"],
                "1-9": record["1-9"],
                "10-20": record["10-20"],
                "21-31": record["21-31"],
                "hit_score": format_hit_score(item["hit_score"]),
            }
        )
    return records


def save_backtest_window_check_csv(records: list[dict[str, str]]) -> None:
    """重建多組合窗口回測核對 CSV。"""

    BET_DATA_DIR.mkdir(parents=True, exist_ok=True)
    with BACKTEST_WINDOW_CHECK_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=backtest_window_check_field_names())
        writer.writeheader()
        writer.writerows(records)


def save_backtest_group_csv(summary_rows: list[BacktestSummary], group_options: list[int]) -> None:
    """保存 B0 回測預測及核對命中結果。"""

    if not SAVE_BACKTEST_BET_CSV:
        return

    bet_records: list[dict[str, str]] = []
    win_records: list[dict[str, str]] = []
    for item in summary_rows:
        check_nums = [num for num in item["check_nums_1_31_slots"][:6] if num is not None]
        special_num = item["check_nums_1_31_slots"][6] if len(item["check_nums_1_31_slots"]) > 6 else None
        bet_records.append(
            predictions_to_group_record(item["check_date"], item["predictions"], group_options)
        )
        win_records.append(
            hits_to_group_record(
                item["check_date"],
                item["predictions"],
                group_options,
                check_nums,
                special_num,
            )
        )

    write_group_csv(BET_RECORDS_CSV, bet_records)
    write_group_csv(WIN_RESULTS_CSV, win_records)
    print()
    print("====== B0 回測分組 CSV 已重新建立 ======")
    print(f"bet_records.csv：{len(bet_records)} 行")
    print(f"win_results.csv：{len(win_records)} 行")


def print_matched_rows(rows: list[DrawRow], group_option: int, target_date: str, backtest_rank: int) -> None:
    """打印每個回測期的窗口樣本。"""

    start_num, end_num = birthday_range(group_option)
    print(f"/> -- 回測最近第 {backtest_rank} 期: {target_date}， {start_num}-{end_num}開獎號 /> 注數")
    if not rows:
        print("沒有符合條件的期數。")
        return

    for idx, row in enumerate(rows[:TOP_PRIZE_DRAW_COUNT], start=1):
        nums_text = ",".join(str(num) for num in row["selected_nums"])
        print(f"{idx} {row['date']} : {nums_text} /> {format_prize(row['prize_count'])}")


def print_pair_scores(pair_scores: list[PairScore]) -> None:
    """打印加權後的 2 球組合排序。"""

    if not pair_scores:
        print("2球加權組合：沒有符合條件。")
        return

    print(f"2球加權組合，顯示前 {MAX_PAIR_DISPLAY_COUNT} 組：")
    for idx, item in enumerate(pair_scores[:MAX_PAIR_DISPLAY_COUNT], start=1):
        pair = item["pair"]
        hit_text = ",".join(str(num) for num in item["hit_nums"]) if item["hit_nums"] else "-"
        print(
            f"{idx}. [{pair[0]},{pair[1]}] "
            f"/> 分數 {item['score']} / 出次數 {item['pair_hit_count']} "
            f"/ 命中 {hit_text} /> {len(item['hit_nums'])} 球"
        )


def print_group_prediction(predicted_nums: list[int], check_nums: list[int], group_option: int) -> None:
    """打印每個分組的下期 3 球預測及命中結果。"""

    target_selected_nums = set(selected_nums(check_nums, group_option))
    hit_nums = sorted(set(predicted_nums) & target_selected_nums)
    pred_text = ",".join(str(num) for num in predicted_nums) if predicted_nums else "-"
    hit_text = ",".join(str(num) for num in hit_nums) if hit_nums else "-"
    print(f"下期預測號[{pred_text}]，命中 {hit_text} /> {len(hit_nums)} 球")


def print_backtest_summary(summary_rows: list[BacktestSummary]) -> None:
    """打印多期回測預測核對總結。"""

    if not summary_rows:
        return

    print()
    print("====== 多期回測預測核對總結 ======")
    for item in summary_rows:
        prediction_text = "，".join(
            f"[{','.join(str(num) for num in prediction)}]" for prediction in item["predictions"]
        )
        check_nums_text = format_check_num_slots(item["check_nums_1_31_slots"])
        hit_text = ",".join(str(num) for num in item["hit_nums"]) if item["hit_nums"] else "-"
        special_hit_text = (
            f" + 特號[{item['special_hit_num']}]"
            if item["special_hit_num"] is not None
            else ""
        )
        prize_text = f" / 獎級：{item['prize_level']}" if item["prize_level"] != "未中獎" else ""
        print(
            f"近 {item['backtest_rank']}期："
            f"核對期號 [{item['check_date']}: {check_nums_text}] ，"
            f"{prediction_text}，"
            f"命中[{hit_text}]{special_hit_text} /> "
            f"{format_hit_score(item['hit_score'])} 球{prize_text}"
        )


def print_backtest_hit_rate_summary(summary_rows: list[BacktestSummary], title: str = "總回測命中率總計分析") -> None:
    """打印總回測命中率統計。"""

    if not summary_rows:
        return

    total_count = len(summary_rows)
    hit_counts = [item["hit_score"] for item in summary_rows]
    exact_levels = [6, 5.5, 5, 4.5, 4, 3.5, 3, 2.5, 2, 1.5, 1, 0.5, 0]

    print()
    print(f"====== {title} ======")
    print(f"總回測期數：{total_count}")
    print("最高命中球數統計：")
    for level in exact_levels:
        count = sum(1 for hit_count in hit_counts if hit_count == level)
        rate = count / total_count * 100
        level_text = f"{format_hit_score(level)} 球"
        print(f"{level_text:<6} = {count} 期，{rate:.2f}%")


def build_exact_hit_counts(summary_rows: list[BacktestSummary]) -> dict[float, int]:
    """統計每期最高命中球數。"""

    levels = [6, 5.5, 5, 4.5, 4, 3.5, 3, 2.5, 2, 1.5, 1, 0.5, 0]
    counts = {float(level): 0 for level in levels}
    for item in summary_rows:
        hit_count = item["hit_score"]
        counts[hit_count] = counts.get(hit_count, 0) + 1
    return counts


def calc_group_mode_score(exact_counts: dict[float, int]) -> float:
    """計算單分組權重模式分數，先追求 1-2 球穩定命中。"""

    return (
        exact_counts.get(3.5, 0) * 10
        + exact_counts.get(3, 0) * 8
        + exact_counts.get(2.5, 0) * 5
        + exact_counts.get(2, 0) * 4
        + exact_counts.get(1.5, 0) * 2
        + exact_counts.get(1, 0) * 1
        - exact_counts.get(0, 0) * 0.5
    )


def calc_total_model_score(exact_counts: dict[float, int]) -> float:
    """計算三組合併模型分數，重點比較七獎 3 球以上。"""

    return (
        exact_counts.get(6, 0) * 80
        + exact_counts.get(5.5, 0) * 60
        + exact_counts.get(5, 0) * 45
        + exact_counts.get(4.5, 0) * 30
        + exact_counts.get(4, 0) * 20
        + exact_counts.get(3.5, 0) * 12
        + exact_counts.get(3, 0) * 8
        + exact_counts.get(2.5, 0) * 5
        + exact_counts.get(2, 0) * 3
        + exact_counts.get(1.5, 0) * 2
        + exact_counts.get(1, 0)
        + exact_counts.get(0.5, 0) * 0.5
        - exact_counts.get(0, 0) * 2
    )


def build_optimize_result(
    backtest_draw_count: int,
    window_draw_count: int,
    best_results: dict[int, GroupModeResult],
    summary_rows: list[BacktestSummary],
) -> OptimizeResult:
    """建立單一參數組合的成績。"""

    exact_counts = build_exact_hit_counts(summary_rows)
    return {
        "backtest_draw_count": backtest_draw_count,
        "window_draw_count": window_draw_count,
        "best_results": best_results,
        "exact_counts": exact_counts,
        "score": calc_total_model_score(exact_counts),
        "hit_5_or_above": sum(count for level, count in exact_counts.items() if level >= 5),
        "hit_4_or_above": sum(count for level, count in exact_counts.items() if level >= 4),
        "hit_3_or_above": sum(count for level, count in exact_counts.items() if level >= 3),
        "zero_count": exact_counts.get(0, 0),
    }


def sort_optimize_results(results: list[OptimizeResult]) -> list[OptimizeResult]:
    """按 3 球以上、5 球以上、4 球以上及分數排序，選出最有用的參數組合。"""

    return sorted(
        results,
        key=lambda item: (
            -item["hit_3_or_above"],
            -item["hit_5_or_above"],
            -item["hit_4_or_above"],
            -item["score"],
            item["zero_count"],
            item["backtest_draw_count"],
            item["window_draw_count"],
        ),
    )


def select_best_recent_bonus_modes(rows: list[dict[str, str]]) -> dict[int, GroupModeResult]:
    """每個生日號分組獨立比較權重模式，選出最佳模式。"""

    global CURRENT_RECENT_NUM_BONUS

    best_results: dict[int, GroupModeResult] = {}
    for group_option in [1, 2, 3]:
        start_num, end_num = birthday_range(group_option)
        if SHOW_GROUP_MODE_COMPARE:
            print()
            print(f"====== 分組 {group_option}：{start_num}-{end_num} 權重模式比較 ======")

        group_results: list[GroupModeResult] = []
        for mode_name, bonus_scores in RECENT_BONUS_MODES.items():
            CURRENT_RECENT_NUM_BONUS = bonus_scores
            summary_rows = print_backtest_window_details(
                rows,
                group_options=[group_option],
                show_window_details=False,
                show_backtest_summary=False,
                show_hit_rate_summary=False,
            )
            exact_counts = build_exact_hit_counts(summary_rows)
            score = calc_group_mode_score(exact_counts)
            result: GroupModeResult = {
                "group_option": group_option,
                "group_range": f"{start_num}-{end_num}",
                "mode": mode_name,
                "bonus_scores": bonus_scores,
                "exact_counts": exact_counts,
                "score": score,
            }
            group_results.append(result)

            if SHOW_GROUP_MODE_COMPARE:
                print(
                    f"{mode_name} {bonus_scores} /> "
                    f"3.5球 {exact_counts.get(3.5, 0)} / "
                    f"3.球 {exact_counts.get(3, 0)} / "
                    f"2.5球 {exact_counts.get(2.5, 0)} / "
                    f"2.球 {exact_counts.get(2, 0)} / "
                    f"1.5球 {exact_counts.get(1.5, 0)} / "
                    f"1 球 {exact_counts.get(1, 0)} / "
                    f"0 球 {exact_counts.get(0, 0)} / "
                    f"分數 {score:g}"
                )

        best_results[group_option] = sorted(
            group_results,
            key=lambda item: (
                -item["score"],
                -item["exact_counts"].get(3, 0),
                -item["exact_counts"].get(2.5, 0),
                -item["exact_counts"].get(2, 0),
                -item["exact_counts"].get(1.5, 0),
                -item["exact_counts"].get(1, 0),
                item["exact_counts"].get(0, 0),
                item["mode"],
            ),
        )[0]

    return best_results


def save_group_weight_best_modes(
    best_results: dict[int, GroupModeResult],
    optimize_results: list[OptimizeResult] | None = None,
) -> None:
    """將每個分組最佳權重模式寫入 JSON。"""

    JSON_DATA_DIR.mkdir(parents=True, exist_ok=True)
    optimize_rows = []
    for result in sort_optimize_results(optimize_results or []):
        optimize_rows.append(
            {
                "backtest_draw_count": result["backtest_draw_count"],
                "window_draw_count": result["window_draw_count"],
                "score": result["score"],
                "hit_5_or_above": result["hit_5_or_above"],
                "hit_4_or_above": result["hit_4_or_above"],
                "hit_3_or_above": result["hit_3_or_above"],
                "zero_count": result["zero_count"],
                "exact_counts": {format_hit_score(level): count for level, count in result["exact_counts"].items()},
            }
        )
    data: dict[str, object] = {
        "__settings__": {
            "backtest_draw_count": BACKTEST_DRAW_COUNT,
            "window_draw_count": WINDOW_DRAW_COUNT,
            "auto_optimize_backtest_window": AUTO_OPTIMIZE_BACKTEST_WINDOW,
            "backtest_draw_count_list": BACKTEST_DRAW_COUNT_LIST,
            "window_draw_count_list": WINDOW_DRAW_COUNT_LIST,
            "print_group_options": PRINT_GROUP_OPTIONS,
            "combination_take_count": COMBINATION_TAKE_COUNT,
            "birthday_num_match_mode": BIRTHDAY_NUM_MATCH_MODE,
            "top_prize_draw_count": TOP_PRIZE_DRAW_COUNT,
            "prize_option": PRIZE_OPTION,
            "sample_sort_mode": SAMPLE_SORT_MODE,
            "pair_hit_weight": PAIR_HIT_WEIGHT,
            "num_hit_weight": NUM_HIT_WEIGHT,
            "group_predict_num_count": GROUP_PREDICT_NUM_COUNT,
            "predict_mode": PREDICT_MODE,
            "predict_candidate_pool_size": PREDICT_CANDIDATE_POOL_SIZE,
            "optimize_results": optimize_rows,
        },
        **{
        f"group_{group_option}": result
        for group_option, result in sorted(best_results.items())
        },
    }
    with GROUP_WEIGHT_JSON.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def print_group_weight_best_modes(best_results: dict[int, GroupModeResult]) -> None:
    """打印每個分組最佳權重模式。"""

    print()
    print("====== 每分組最佳權重模式 ======")
    for group_option, result in sorted(best_results.items()):
        counts = result["exact_counts"]
        print(
            f"[{group_option}] {result['group_range']} /> "
            f"{result['mode']} {result['bonus_scores']} / "
            f"3.5球 {counts.get(3.5, 0)} / "
            f"3球 {counts.get(3, 0)} / "
            f"2.5球 {counts.get(2.5, 0)} / "
            f"2球 {counts.get(2, 0)} / "
            f"1.5球 {counts.get(1.5, 0)} / "
            f"1球 {counts.get(1, 0)} / "
            f"0球 {counts.get(0, 0)} / "
            f"分數 {result['score']:g}"
        )
    print(f"已寫入 JSON：{GROUP_WEIGHT_JSON}")


def print_backtest_window_details(
    rows: list[dict[str, str]],
    *,
    group_options: list[int] | None = None,
    show_window_details: bool = True,
    show_backtest_summary: bool = True,
    show_hit_rate_summary: bool = True,
) -> list[BacktestSummary]:
    """最近 BACKTEST_DRAW_COUNT 期逐期打印窗口分析及加權 pair 核對。"""

    if len(rows) <= WINDOW_DRAW_COUNT + 1:
        print("回測資料不足。")
        return []

    active_group_options = group_options if group_options is not None else PRINT_GROUP_OPTIONS
    last_backtest_index = len(rows) - 2
    first_target_index = max(WINDOW_DRAW_COUNT, last_backtest_index - BACKTEST_DRAW_COUNT + 1)
    target_indices = list(range(first_target_index, last_backtest_index + 1))
    if show_window_details:
        print(
            f"====== 最近 {len(target_indices)} 期回測，"
            f"每期用前 {WINDOW_DRAW_COUNT} 期窗口，不含核對期 ======"
        )

    total_targets = len(target_indices)
    summary_rows: list[BacktestSummary] = []
    for display_index, target_index in enumerate(target_indices, start=1):
        backtest_rank = total_targets - display_index + 1
        target_row = rows[target_index]
        target_date = target_row.get("nDdate", "")
        check_row = rows[target_index + 1]
        check_date = check_row.get("nDdate", "")
        check_nums = parse_nums(check_row)
        special_num = parse_special_num(check_row)
        summary_predictions: list[list[int]] = []
        summary_hit_nums: set[int] = set()
        summary_predicted_nums: set[int] = set()
        if show_window_details and display_index > 1:
            print()

        for group_display_index, group_option in enumerate(active_group_options):
            if show_window_details and group_display_index:
                print()
            matched_rows = build_matched_rows(rows, group_option, target_index)
            pair_scores = build_weighted_pair_scores(matched_rows, check_nums, group_option)
            predicted_nums = build_group_prediction(matched_rows, pair_scores, target_index, group_option)
            if show_window_details:
                print_matched_rows(matched_rows, group_option, target_date, backtest_rank)
                print()
                print(f"核對期開日期{check_date} ：{','.join(str(num) for num in sorted(check_nums))}")
                if special_num is not None:
                    print(f"特號：{special_num}")
                print()
                print_pair_scores(pair_scores)
                print_group_prediction(predicted_nums, check_nums, group_option)
            summary_predictions.append(predicted_nums)
            summary_predicted_nums.update(predicted_nums)
            summary_hit_nums.update(set(predicted_nums) & set(selected_nums(check_nums, group_option)))

        special_hit_num = special_num if special_num in summary_predicted_nums else None
        hit_score = get_hit_score(len(summary_hit_nums), special_hit_num is not None)
        prize_level = get_prize_level(len(summary_hit_nums), special_hit_num is not None)
        summary_rows.append(
            {
                "backtest_rank": backtest_rank,
                "target_date": target_date,
                "check_date": check_date,
                "check_nums_1_31_slots": [
                    *[num if 1 <= num <= 31 else None for num in sorted(check_nums)],
                    special_num if special_num is not None and 1 <= special_num <= 31 else None,
                ],
                "predictions": summary_predictions,
                "hit_nums": sorted(summary_hit_nums),
                "special_hit_num": special_hit_num,
                "hit_score": hit_score,
                "prize_level": prize_level,
            }
        )

    if show_backtest_summary:
        print_backtest_summary(summary_rows)
    if show_hit_rate_summary:
        print_backtest_hit_rate_summary(summary_rows)
    return summary_rows


def print_analysis_advice() -> None:
    """打印本版回測預測分析建議。"""

    if not SHOW_ANALYSIS_ADVICE:
        return

    print("====== B0_v4 分析建議 ======")
    print("1. 本版以 prize3 中獎注數作人氣組合球分析。")
    print("2. prize3 主要條件是中 5 個正號，所以本版只分析 N1-N6，不分析特號。")
    print("3. 生日號分成 1-9、10-20、21-31 三組，先在每組內找人氣球及 2 球關係。")
    print("4. 每組預測 3-4 球已足夠，目標是突破命中 3 個正號。")
    print("5. 候選範圍由 49 球收窄到 1-31，再可只取三組其中兩組合併作預測。")
    print("6. 本版重點不是線性預測，而是用近期 prize3 人氣集合與 2 球加權作投注參考。")
    print()


def print_optimize_result_table(results: list[OptimizeResult]) -> None:
    """打印多組合回測參數的 3 球以上最高命中獎球數成績。"""

    if not results:
        return

    print()
    print("====== 回測參數多組合 3球以上最高命中獎球數成績 ======")
    print("排名 | 回測期 | 窗口期 | 5球+ | 4球+ | 3球+ | 0球 | 分數 | 6球 | 5.5球 | 5球 | 4.5球 | 4球 | 3.5球 | 3球")
    for rank, result in enumerate(sort_optimize_results(results), start=1):
        counts = result["exact_counts"]
        print(
            f"{rank:>2} | "
            f"{result['backtest_draw_count']:>4} | "
            f"{result['window_draw_count']:>4} | "
            f"{result['hit_5_or_above']:>3} | "
            f"{result['hit_4_or_above']:>3} | "
            f"{result['hit_3_or_above']:>3} | "
            f"{result['zero_count']:>2} | "
            f"{result['score']:>5g} | "
            f"{counts.get(6, 0):>2} | "
            f"{counts.get(5.5, 0):>4} | "
            f"{counts.get(5, 0):>2} | "
            f"{counts.get(4.5, 0):>4} | "
            f"{counts.get(4, 0):>2} | "
            f"{counts.get(3.5, 0):>4} | "
            f"{counts.get(3, 0):>2}"
        )


def run_optimized_backtest(rows: list[dict[str, str]]) -> OptimizeResult:
    """比較多組回測期及窗口期，回傳最佳組合。"""

    global BACKTEST_DRAW_COUNT, WINDOW_DRAW_COUNT, CURRENT_GROUP_RECENT_BONUS

    original_backtest_draw_count = BACKTEST_DRAW_COUNT
    original_window_draw_count = WINDOW_DRAW_COUNT
    optimize_results: list[OptimizeResult] = []
    window_check_records: list[dict[str, str]] = []

    for backtest_draw_count in BACKTEST_DRAW_COUNT_LIST:
        for window_draw_count in WINDOW_DRAW_COUNT_LIST:
            BACKTEST_DRAW_COUNT = backtest_draw_count
            WINDOW_DRAW_COUNT = window_draw_count
            best_results = select_best_recent_bonus_modes(rows)
            CURRENT_GROUP_RECENT_BONUS = {
                group_option: result["bonus_scores"]
                for group_option, result in best_results.items()
            }
            summary_rows = print_backtest_window_details(
                rows,
                group_options=PRINT_GROUP_OPTIONS,
                show_window_details=False,
                show_backtest_summary=False,
                show_hit_rate_summary=False,
            )
            window_check_records.extend(
                build_backtest_window_check_records(
                    backtest_draw_count,
                    window_draw_count,
                    summary_rows,
                    PRINT_GROUP_OPTIONS,
                )
            )
            optimize_results.append(
                build_optimize_result(backtest_draw_count, window_draw_count, best_results, summary_rows)
            )

    save_backtest_window_check_csv(window_check_records)
    print_optimize_result_table(optimize_results)
    best_result = sort_optimize_results(optimize_results)[0]

    BACKTEST_DRAW_COUNT = best_result["backtest_draw_count"]
    WINDOW_DRAW_COUNT = best_result["window_draw_count"]
    CURRENT_GROUP_RECENT_BONUS = {
        group_option: result["bonus_scores"]
        for group_option, result in best_result["best_results"].items()
    }
    save_group_weight_best_modes(best_result["best_results"], optimize_results)

    print()
    print(
        f"最佳組合：回測期 {BACKTEST_DRAW_COUNT}，窗口期 {WINDOW_DRAW_COUNT}，"
        f"5球以上 {best_result['hit_5_or_above']} 期，"
        f"4球以上 {best_result['hit_4_or_above']} 期，"
        f"3球以上 {best_result['hit_3_or_above']} 期，"
        f"分數 {best_result['score']:g}"
    )

    if not AUTO_OPTIMIZE_BACKTEST_WINDOW:
        BACKTEST_DRAW_COUNT = original_backtest_draw_count
        WINDOW_DRAW_COUNT = original_window_draw_count

    return best_result


def main() -> None:
    """主程式入口。"""

    global CURRENT_RECENT_NUM_BONUS, CURRENT_GROUP_RECENT_BONUS

    validate_params()
    rows = read_m6_rows()
    print_analysis_advice()

    if not AUTO_SELECT_GROUP_BEST_MODES:
        CURRENT_RECENT_NUM_BONUS = RECENT_BONUS_MODES[RECENT_BONUS_MODE]
        CURRENT_GROUP_RECENT_BONUS = {}
        print_backtest_window_details(rows)
        return

    if AUTO_OPTIMIZE_BACKTEST_WINDOW:
        best_optimize_result = run_optimized_backtest(rows)
        best_results = best_optimize_result["best_results"]
    else:
        best_results = select_best_recent_bonus_modes(rows)
        save_group_weight_best_modes(best_results)

    if SHOW_GROUP_MODE_COMPARE:
        print("====== V4 每分組獨立最佳權重分析 ======")
        print(f"回測期數：{BACKTEST_DRAW_COUNT}，窗口期數：{WINDOW_DRAW_COUNT}")
        print(f"正式合併分組：{PRINT_GROUP_OPTIONS}，每組預測 {GROUP_PREDICT_NUM_COUNT} 球")

    if SHOW_GROUP_MODE_COMPARE:
        print_group_weight_best_modes(best_results)

    CURRENT_GROUP_RECENT_BONUS = {
        group_option: result["bonus_scores"]
        for group_option, result in best_results.items()
    }
    print()
    print("====== 使用每分組最佳權重，正式合併回測 ======")
    summary_rows = print_backtest_window_details(
        rows,
        group_options=PRINT_GROUP_OPTIONS,
        show_window_details=False,
        show_backtest_summary=True,
        show_hit_rate_summary=False,
    )
    print_backtest_hit_rate_summary(
        summary_rows,
        title=f"每分組最佳權重合併回測命中率：{format_group_options(PRINT_GROUP_OPTIONS)}",
    )
    save_backtest_group_csv(summary_rows, PRINT_GROUP_OPTIONS)


if __name__ == "__main__":
    main()
    
   
'''

產生組合 1 to 9 取 2 個數字的所有組合: 36
產生組合 10 to 20 取 2 個數字的所有組合: 55
產生組合 21 to 31 取 2 個數字的所有組合: 55

產生組合 1 to 9 取 3 個數字的所有組合: 84
產生組合 10 to 20 取 3 個數字的所有組合: 165
產生組合 21 to 31 取 3 個數字的所有組合: 165

1-9 選 2  = 9C2  = 36
1-9 選 3  = 9C3  = 84

10-20 選 2 = 11C2 = 55
10-20 選 3 = 11C3 = 165

21-31 選 2 = 11C2 = 55
21-31 選 3 = 11C3 = 165

'''
