from pathlib import Path
import csv
import itertools
import random
from typing import TypedDict

"""
A0_v3：
以 1-9、10-20、21-31 三組生日號做回測。
每個回測期用之前 WINDOW_DRAW_COUNT 期做窗口，不包含核對期。
從窗口內符合條件的期數取 prize 注數最高前 N 期，建立 2 球組合加權排序。
"""


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
M6_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"

# ---- 回測及窗口參數
BACKTEST_DRAW_COUNT = 100  # 回測最近多少期
WINDOW_DRAW_COUNT = 24  # 每個回測期之前，向前取多少期作窗口樣本
SHOW_ANALYSIS_ADVICE = False  # 可選：True 顯示本版分析建議；False 不顯示

# ---- 查詢條件參數
PRINT_GROUP_OPTIONS = [1,2]  # 可選：[1]、[2]、[3]、[1, 2, 3]
COMBINATION_TAKE_COUNT = 2  # 每期開獎號在分組範圍內符合幾個號碼
BIRTHDAY_NUM_MATCH_MODE = ">="  # 可選：">=" 或 "=="
TOP_PRIZE_DRAW_COUNT = 5  # 每個分組取 prize 注數最高多少期作 pair 分析
PRIZE_OPTION = 3  # 可選：1、2、3；顯示 prize1 / prize2 / prize3 注數
SAMPLE_SORT_MODE = "date"  # 可選："prize" 中獎注數多至少；"date" 日期遠至近

# ---- 2 球組合加權參數
PAIR_HIT_WEIGHT = 7  # 2 球組合本身出現次數權重
NUM_HIT_WEIGHT = 1  # 單號在樣本內出現次數權重
RECENT_BONUS_MODE = "delay"  # 可選："hot" 最近最高；"delay" 隔期較高；"middle" 中段最高
COMPARE_RECENT_BONUS_MODES = True  # 可選：True 一次比較 hot / delay / middle 總計結果
RECENT_BONUS_MODES: dict[str, list[int]] = {
    "hot": [13, 11, 9, 7, 5, 3, 1],
    "delay": [1, 2, 3, 4, 5, 6, 7],
    "middle": [3, 5, 7, 9, 7, 5, 3],
}
CURRENT_RECENT_NUM_BONUS = RECENT_BONUS_MODES[RECENT_BONUS_MODE]
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


def birthday_range(group_option: int) -> tuple[int, int]:
    """按分組參數取得生日號查詢範圍。"""

    if group_option not in BIRTHDAY_GROUPS:
        raise ValueError("PRINT_GROUP_OPTIONS 只可選 1、2、3")
    return BIRTHDAY_GROUPS[group_option]


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


def build_recent_num_bonus(matched_rows: list[DrawRow]) -> dict[int, int]:
    """按最近符合條件期數，給單號額外加權。"""

    bonus_scores: dict[int, int] = {}
    recent_rows = sorted(matched_rows, key=lambda item: item["date"], reverse=True)
    for row, bonus in zip(recent_rows, CURRENT_RECENT_NUM_BONUS):
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
    recent_bonus = build_recent_num_bonus(matched_rows)

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


def build_weighted_num_scores(matched_rows: list[DrawRow]) -> list[tuple[int, int]]:
    """建立單號加權排序，用作 3 球預測補號。"""

    sample_rows = matched_rows[:TOP_PRIZE_DRAW_COUNT]
    num_counts: dict[int, int] = {}
    recent_bonus = build_recent_num_bonus(matched_rows)

    for row in sample_rows:
        for num in sorted(set(row["selected_nums"])):
            num_counts[num] = num_counts.get(num, 0) + 1

    all_nums = set(num_counts) | set(recent_bonus)
    num_scores: list[tuple[int, int]] = []
    for num in all_nums:
        score = num_counts.get(num, 0) * NUM_HIT_WEIGHT + recent_bonus.get(num, 0)
        num_scores.append((num, score))

    return sorted(num_scores, key=lambda item: (-item[1], item[0]))


def build_stable_group_prediction(matched_rows: list[DrawRow], pair_scores: list[PairScore]) -> list[int]:
    """按 2 球加權組合及單號權重，產生每個分組的 3 球預測。"""

    predicted_nums: list[int] = []
    for item in pair_scores:
        for num in item["pair"]:
            if num not in predicted_nums:
                predicted_nums.append(num)
            if len(predicted_nums) >= GROUP_PREDICT_NUM_COUNT:
                return sorted(predicted_nums)

    for num, _score in build_weighted_num_scores(matched_rows):
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
        return build_stable_group_prediction(matched_rows, pair_scores)

    predicted_nums = list(pair_scores[0]["pair"])
    candidate_nums: list[int] = []
    for item in pair_scores[:PREDICT_CANDIDATE_POOL_SIZE]:
        for num in item["pair"]:
            if num not in candidate_nums:
                candidate_nums.append(num)

    for num, _score in build_weighted_num_scores(matched_rows):
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
        return build_stable_group_prediction(matched_rows, pair_scores)

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
    return build_stable_group_prediction(matched_rows, pair_scores)


def format_prize(value: float) -> str:
    """格式化注數，整數不顯示 .0。"""

    return f"{value:g}"


def format_check_num_slots(nums: list[int | None]) -> str:
    """格式化核對號碼固定 6 格，32-49 顯示為空位。"""

    return ",".join(str(num) if num is not None else "-" for num in nums)


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
        print(
            f"近 {item['backtest_rank']}期："
            f"核對期號 [{item['check_date']}: {check_nums_text}] ，"
            f"{prediction_text}，"
            f"命中[{hit_text}] /> {len(item['hit_nums'])} 球"
        )


def print_backtest_hit_rate_summary(summary_rows: list[BacktestSummary], title: str = "總回測命中率總計分析") -> None:
    """打印總回測命中率統計。"""

    if not summary_rows:
        return

    total_count = len(summary_rows)
    hit_counts = [len(item["hit_nums"]) for item in summary_rows]
    exact_levels = [6, 5, 4, 3, 2, 1, 0]

    print()
    print(f"====== {title} ======")
    print(f"總回測期數：{total_count}")
    print("最高命中球數統計：")
    for level in exact_levels:
        count = sum(1 for hit_count in hit_counts if hit_count == level)
        rate = count / total_count * 100
        print(f"{level} 球 = {count} 期，{rate:.2f}%")


def print_backtest_window_details(
    rows: list[dict[str, str]],
    *,
    show_window_details: bool = True,
    show_backtest_summary: bool = True,
    show_hit_rate_summary: bool = True,
) -> list[BacktestSummary]:
    """最近 BACKTEST_DRAW_COUNT 期逐期打印窗口分析及加權 pair 核對。"""

    if len(rows) <= WINDOW_DRAW_COUNT + 1:
        print("回測資料不足。")
        return []

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
        summary_predictions: list[list[int]] = []
        summary_hit_nums: set[int] = set()
        if show_window_details and display_index > 1:
            print()

        for group_display_index, group_option in enumerate(PRINT_GROUP_OPTIONS):
            if show_window_details and group_display_index:
                print()
            matched_rows = build_matched_rows(rows, group_option, target_index)
            pair_scores = build_weighted_pair_scores(matched_rows, check_nums, group_option)
            predicted_nums = build_group_prediction(matched_rows, pair_scores, target_index, group_option)
            if show_window_details:
                print_matched_rows(matched_rows, group_option, target_date, backtest_rank)
                print()
                print(f"核對期開日期{check_date} ：{','.join(str(num) for num in sorted(check_nums))}")
                print()
                print_pair_scores(pair_scores)
                print_group_prediction(predicted_nums, check_nums, group_option)
            summary_predictions.append(predicted_nums)
            summary_hit_nums.update(set(predicted_nums) & set(selected_nums(check_nums, group_option)))

        summary_rows.append(
            {
                "backtest_rank": backtest_rank,
                "target_date": target_date,
                "check_date": check_date,
                "check_nums_1_31_slots": [num if 1 <= num <= 31 else None for num in sorted(check_nums)],
                "predictions": summary_predictions,
                "hit_nums": sorted(summary_hit_nums),
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

    print("====== A0_v3 分析建議 ======")
    print("1. 本版以 prize3 中獎注數作人氣組合球分析。")
    print("2. prize3 主要條件是中 5 個正號，所以本版只分析 N1-N6，不分析特號。")
    print("3. 生日號分成 1-9、10-20、21-31 三組，先在每組內找人氣球及 2 球關係。")
    print("4. 每組預測 3-4 球已足夠，目標是突破命中 3 個正號。")
    print("5. 候選範圍由 49 球收窄到 1-31，再可只取三組其中兩組合併作預測。")
    print("6. 本版重點不是線性預測，而是用近期 prize3 人氣集合與 2 球加權作投注參考。")
    print()


def main() -> None:
    """主程式入口。"""

    global CURRENT_RECENT_NUM_BONUS

    validate_params()
    rows = read_m6_rows()
    print_analysis_advice()
    if not COMPARE_RECENT_BONUS_MODES:
        CURRENT_RECENT_NUM_BONUS = RECENT_BONUS_MODES[RECENT_BONUS_MODE]
        print_backtest_window_details(rows)
        return

    print("====== 近期權重模式總計比較 ======")
    print(f"回測期數：{BACKTEST_DRAW_COUNT}，窗口期數：{WINDOW_DRAW_COUNT}")
    print(f"分組：{PRINT_GROUP_OPTIONS}，每組預測 {GROUP_PREDICT_NUM_COUNT} 球")
    for mode_name, bonus_scores in RECENT_BONUS_MODES.items():
        CURRENT_RECENT_NUM_BONUS = bonus_scores
        summary_rows = print_backtest_window_details(
            rows,
            show_window_details=False,
            show_backtest_summary=False,
            show_hit_rate_summary=False,
        )
        print_backtest_hit_rate_summary(
            summary_rows,
            title=f"{mode_name} 權重 {bonus_scores} 回測命中率",
        )


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
