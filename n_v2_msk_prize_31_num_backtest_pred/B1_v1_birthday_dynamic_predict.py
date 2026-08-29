from pathlib import Path
import csv
import itertools
import json
import subprocess
import sys
from typing import TypedDict

"""
B1_v1_birthday_dynamic_predict：
研究版下期預測。
以 1-9、10-20、21-31 三組生日號，先用 12 / 6 / 2 期判斷動態配額，
再用 B0_v4_backtest_with_json 的 2 球組合、prize3 人氣、近期權重方向產生分組候選號。
本版只輸出 9 球候選池，不拆成 6 球單式。
以加入 特號分析 N1..N6 + N7 的命中結果，計算每期最高命中球數，並統計總回測命中率。
"""


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
M6_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"
M4_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M4_lotto_prize_summary.csv"
B0_BACKTEST_SCRIPT = CURRENT_DIR / "B0_v4_backtest_with_json.py"
GROUP_WEIGHT_JSON = CURRENT_DIR / "json_data" / "group_weight_best_modes.json"
BET_DATA_DIR = CURRENT_DIR / "bet_data"
NEXTDRAW_PRED_CSV = BET_DATA_DIR / "nextdraw_pred.csv"

'''
比較穩的範圍：最高權重：10
[(12, 2), (6, 3), (2, 5)]
[(12, 3), (6, 4), (2, 5)]
[(12, 1), (6, 3), (2, 6)]
[(14, 3), (7, 4), (3, 5)]
'''

# ---- 分組及動態配額參數
PRINT_GROUP_OPTIONS = [1, 2, 3]  # 分組：1=1-9，2=10-20，3=21-31
# 越近期權重越高, 近期權重只是分析 1，2，3 組那組走勢。不代表近 2 期的球號一定要重復出現。
# 例如近 2 期 ，N1 是由 10 -31 代表 1-9 失勢。不預測3球配額 減至 1 或 0 球預測。
TREND_PERIOD_WEIGHT_LIST = [(14, 3), (7, 4), (3, 5)]  # 分組趨勢期數及權重
TREND_PERIODS = [period for period, _weight in TREND_PERIOD_WEIGHT_LIST]
TREND_PERIOD_WEIGHTS = dict(TREND_PERIOD_WEIGHT_LIST)
TOTAL_PREDICT_NUM_COUNT = 9  # 三組合共候選球數
GROUP_QUOTA_MODE = "dynamic"  # 可選："fixed" 固定3+3+3；"dynamic" 動態2/3/4

# ---- B0_v4_backtest_with_json 權重選號參數
WINDOW_DRAW_COUNT = 18  # 取最近多少期作權重樣本
COMBINATION_TAKE_COUNT = 2  # 每期分組範圍內至少幾個號碼才納入樣本
BIRTHDAY_NUM_MATCH_MODE = ">="  # 可選：">=" 或 "=="
TOP_PRIZE_DRAW_COUNT = 5  # 取 prize3 注數最高多少期作 pair 分析
PAIR_HIT_WEIGHT = 7  # 2 球組合出現次數權重
NUM_HIT_WEIGHT = 1  # 單號出現次數權重
RECENT_NUM_BONUS = [13, 11, 9, 7, 5, 3, 1]  # 最近符合期數的單號額外權重
USE_B0_JSON_BONUS = True  # 可選：True 讀取 B0_v4_backtest_with_json 產生的每組最佳權重
SPECIAL_NUM_WEIGHT = 2  # 特號輔助分，不壓過正號
ZERO_PENALTY_WEIGHT = 2  # 動態配額時，分組 0 球扣分
SAVE_NEXTDRAW_PRED_CSV = True  # 可選：True 將分組預測寫入 bet_data/nextdraw_pred.csv
RUN_B0_BACKTEST_FIRST = True  # 可選：True 執行 B1 前先跑 B0，更新 JSON 權重


BIRTHDAY_GROUPS: dict[int, tuple[int, int]] = {
    1: (1, 9),
    2: (10, 20),
    3: (21, 31),
}


class DrawRow(TypedDict):
    date: str
    nums: list[int]
    selected_nums: list[int]
    special_num: int | None
    prize3_count: float


class GroupPrediction(TypedDict):
    group_option: int
    group_range: str
    quota: int
    strength_score: float
    bonus_mode: str
    bonus_scores: list[int]
    predicted_nums: list[int]
    top_pair_text: str


def birthday_range(group_option: int) -> tuple[int, int]:
    """按分組取得生日號範圍。"""

    if group_option not in BIRTHDAY_GROUPS:
        raise ValueError("PRINT_GROUP_OPTIONS 只可選 1、2、3")
    return BIRTHDAY_GROUPS[group_option]


def validate_params() -> None:
    """檢查主要參數。"""

    if GROUP_QUOTA_MODE not in {"fixed", "dynamic"}:
        raise ValueError('GROUP_QUOTA_MODE 只可選 "fixed" 或 "dynamic"')
    if BIRTHDAY_NUM_MATCH_MODE not in {">=", "=="}:
        raise ValueError('BIRTHDAY_NUM_MATCH_MODE 只可選 ">=" 或 "=="')
    if TOTAL_PREDICT_NUM_COUNT != 9:
        raise ValueError("本版暫定 TOTAL_PREDICT_NUM_COUNT = 9")
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


def read_csv_rows(csv_path: Path) -> list[dict[str, str]]:
    """讀入一般 CSV。"""

    if not csv_path.exists():
        return []

    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames:
            reader.fieldnames = [name.strip().lstrip("\ufeff") for name in reader.fieldnames]
        return [
            {(key or "").strip().lstrip("\ufeff"): (value or "").strip() for key, value in row.items()}
            for row in reader
        ]


def read_next_draw_date(csv_path: Path = M4_CSV) -> str:
    """從 M4 讀取下期開獎日期。"""

    rows = read_csv_rows(csv_path)
    if not rows:
        return ""
    return rows[-1].get("next_draw_date", "")


def run_b0_backtest_first() -> None:
    """先執行 B0_v4_backtest_with_json.py，確保 JSON 權重是最新。"""

    if not RUN_B0_BACKTEST_FIRST:
        return
    if not B0_BACKTEST_SCRIPT.exists():
        raise FileNotFoundError(f"找不到 B0 回測程式：{B0_BACKTEST_SCRIPT}")

    result = subprocess.run(
        [sys.executable, str(B0_BACKTEST_SCRIPT)],
        cwd=str(CURRENT_DIR),
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        output = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part)
        if output:
            print(output)
        raise RuntimeError(f"B0_v4_backtest_with_json.py 執行失敗：returncode={result.returncode}")


def load_group_json_bonus() -> dict[int, tuple[str, list[int]]]:
    """讀取 B0_v4_backtest_with_json 產生的每組最佳近期權重。"""

    if not USE_B0_JSON_BONUS or not GROUP_WEIGHT_JSON.exists():
        return {}

    try:
        data = json.loads(GROUP_WEIGHT_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}

    group_bonus: dict[int, tuple[str, list[int]]] = {}
    for key, value in data.items():
        if not key.startswith("group_") or not isinstance(value, dict):
            continue
        try:
            group_option = int(key.replace("group_", ""))
        except ValueError:
            continue
        mode = str(value.get("mode", "json"))
        bonus_scores_raw = value.get("bonus_scores", [])
        if not isinstance(bonus_scores_raw, list):
            continue
        try:
            bonus_scores = [int(score) for score in bonus_scores_raw]
        except (TypeError, ValueError):
            continue
        group_bonus[group_option] = (mode, bonus_scores)
    return group_bonus


def get_group_bonus_config(
    group_bonus: dict[int, tuple[str, list[int]]],
    group_option: int,
) -> tuple[str, list[int]]:
    """取得指定分組使用的權重模式及分數。"""

    return group_bonus.get(group_option, ("default", RECENT_NUM_BONUS))


def parse_nums(row: dict[str, str]) -> list[int]:
    """抽取 N1-N6 正號。"""

    nums: list[int] = []
    for idx in range(1, 7):
        try:
            nums.append(int(row.get(f"N{idx}", "0") or 0))
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


def parse_prize3(row: dict[str, str]) -> float:
    """抽取 prize3 中獎注數。"""

    try:
        return float(row.get("prize3", "0") or 0)
    except ValueError:
        return 0.0


def selected_nums(nums: list[int], group_option: int) -> list[int]:
    """只保留指定分組範圍內的正號。"""

    start_num, end_num = birthday_range(group_option)
    return sorted(num for num in nums if start_num <= num <= end_num)


def is_matched(count: int) -> bool:
    """判斷每期分組號碼數量是否符合樣本條件。"""

    if BIRTHDAY_NUM_MATCH_MODE == "==":
        return count == COMBINATION_TAKE_COUNT
    return count >= COMBINATION_TAKE_COUNT


def build_window_rows(rows: list[dict[str, str]], group_option: int) -> list[DrawRow]:
    """取最近 WINDOW_DRAW_COUNT 期，建立符合條件的分組樣本。"""

    window_rows: list[DrawRow] = []
    for row in rows[-WINDOW_DRAW_COUNT:]:
        nums = parse_nums(row)
        selected = selected_nums(nums, group_option)
        if not is_matched(len(selected)):
            continue
        window_rows.append(
            {
                "date": row.get("nDdate", ""),
                "nums": nums,
                "selected_nums": selected,
                "special_num": parse_special_num(row),
                "prize3_count": parse_prize3(row),
            }
        )
    return sorted(window_rows, key=lambda item: (-item["prize3_count"], item["date"]))


def build_group_strength(rows: list[dict[str, str]], group_option: int) -> float:
    """用 12 / 6 / 2 期趨勢計算分組強弱，供配額排序。"""

    score = 0.0
    for period_count in TREND_PERIODS:
        period_rows = rows[-period_count:]
        weight = TREND_PERIOD_WEIGHTS.get(period_count, 1)
        for row in period_rows:
            hit_count = len(selected_nums(parse_nums(row), group_option))
            if hit_count == 0:
                score -= ZERO_PENALTY_WEIGHT * weight
            else:
                score += hit_count * weight
    return score


def allocate_group_quotas(group_scores: dict[int, float]) -> dict[int, int]:
    """分配每組預測球數。"""

    quotas = {group_option: 3 for group_option in PRINT_GROUP_OPTIONS}
    if GROUP_QUOTA_MODE == "fixed":
        return quotas

    sorted_groups = sorted(PRINT_GROUP_OPTIONS, key=lambda group: (-group_scores[group], group))
    quotas[sorted_groups[0]] = 4
    quotas[sorted_groups[1]] = 3
    quotas[sorted_groups[2]] = 2
    return quotas


def build_recent_bonus(matched_rows: list[DrawRow], bonus_scores: list[int]) -> dict[int, int]:
    """按最近符合條件期數，給單號額外加分。"""

    bonus_result: dict[int, int] = {}
    recent_rows = sorted(matched_rows, key=lambda item: item["date"], reverse=True)
    for row, bonus in zip(recent_rows, bonus_scores):
        for num in row["selected_nums"]:
            bonus_result[num] = bonus_result.get(num, 0) + bonus
    return bonus_result


def build_num_scores(
    matched_rows: list[DrawRow],
    group_option: int,
    bonus_scores: list[int],
) -> dict[int, float]:
    """用 pair、單號、prize3 人氣及特號輔助分建立號碼分數。"""

    start_num, end_num = birthday_range(group_option)
    scores = {num: 0.0 for num in range(start_num, end_num + 1)}
    sample_rows = matched_rows[:TOP_PRIZE_DRAW_COUNT]
    recent_bonus = build_recent_bonus(matched_rows, bonus_scores)

    for num, bonus in recent_bonus.items():
        scores[num] += bonus

    for row in sample_rows:
        nums = sorted(set(row["selected_nums"]))
        prize_bonus = max(1.0, row["prize3_count"] / 100)
        for num in nums:
            scores[num] += NUM_HIT_WEIGHT + prize_bonus

        for pair in itertools.combinations(nums, 2):
            pair_score = PAIR_HIT_WEIGHT + prize_bonus
            scores[pair[0]] += pair_score / 2
            scores[pair[1]] += pair_score / 2

        special_num = row["special_num"]
        if special_num is not None and start_num <= special_num <= end_num:
            scores[special_num] += SPECIAL_NUM_WEIGHT

    return scores


def build_top_pair_text(matched_rows: list[DrawRow]) -> str:
    """顯示分組內最高出現次數的 2 球組合。"""

    pair_counts: dict[tuple[int, int], int] = {}
    for row in matched_rows[:TOP_PRIZE_DRAW_COUNT]:
        for pair in itertools.combinations(sorted(set(row["selected_nums"])), 2):
            pair_counts[pair] = pair_counts.get(pair, 0) + 1
    if not pair_counts:
        return "-"

    top_pairs = sorted(pair_counts.items(), key=lambda item: (-item[1], item[0]))[:3]
    return "，".join(f"[{pair[0]},{pair[1]}]x{count}" for pair, count in top_pairs)


def build_group_prediction(
    rows: list[dict[str, str]],
    group_option: int,
    quota: int,
    strength_score: float,
    group_bonus: dict[int, tuple[str, list[int]]],
) -> GroupPrediction:
    """產生單一分組預測。"""

    start_num, end_num = birthday_range(group_option)
    matched_rows = build_window_rows(rows, group_option)
    bonus_mode, bonus_scores = get_group_bonus_config(group_bonus, group_option)
    num_scores = build_num_scores(matched_rows, group_option, bonus_scores)
    ranked_nums = sorted(num_scores.items(), key=lambda item: (-item[1], item[0]))
    predicted_nums = sorted(num for num, _score in ranked_nums[:quota])
    return {
        "group_option": group_option,
        "group_range": f"{start_num}-{end_num}",
        "quota": quota,
        "strength_score": strength_score,
        "bonus_mode": bonus_mode,
        "bonus_scores": bonus_scores,
        "predicted_nums": predicted_nums,
        "top_pair_text": build_top_pair_text(matched_rows),
    }


def print_prediction(bet_date: str, group_predictions: list[GroupPrediction]) -> None:
    """打印下期分組預測。"""

    candidate_pool = sorted(
        {num for group in group_predictions for num in group["predicted_nums"]}
    )
    group_map = {group["group_option"]: group["predicted_nums"] for group in group_predictions}

    print("====== B1_v1 生日號動態分組預測 ======")

    for group in group_predictions:
        nums_text = ",".join(str(num) for num in group["predicted_nums"])
        print(
            f"[{group['group_option']}] {group['group_range']}:"
            f"{nums_text} /> {group['quota']} 球，"
            f"熱門pair {group['top_pair_text']}"
        )

    print()
    print(f"9球候選池：{','.join(str(num) for num in candidate_pool)}")
    print(
        f"下期開獎日期：{bet_date}，預測 "
        f"{format_list_for_csv(group_map.get(1, []))},"
        f"{format_list_for_csv(group_map.get(2, []))},"
        f"{format_list_for_csv(group_map.get(3, []))}"
    )

    banker_3 = group_map.get(2, [])
    legs_3 = sorted(num for num in candidate_pool if num not in banker_3)
    banker_4 = group_map.get(3, [])
    legs_4 = sorted(num for num in candidate_pool if num not in banker_4)
    print("膽拖組合：")
    print(f"1，3膽 {format_list_for_csv(banker_3)} + {format_list_for_csv(legs_3)} 腳，$5 x 20 注，$100")
    print(f"2，4膽 {format_list_for_csv(banker_4)} + {format_list_for_csv(legs_4)} 腳，$5 x 10 注，$50")


def format_list_for_csv(nums: list[int]) -> str:
    """將號碼 list 格式化成 CSV 欄位文字。"""

    return "[" + ",".join(str(num) for num in nums) + "]"


def save_nextdraw_pred_csv(bet_date: str, group_predictions: list[GroupPrediction]) -> None:
    """將下期分組預測寫入 bet_data/nextdraw_pred.csv，只保留最新一行。"""

    if not SAVE_NEXTDRAW_PRED_CSV:
        return

    group_map = {group["group_option"]: group["predicted_nums"] for group in group_predictions}
    record = {
        "bet_date": bet_date,
        "1-9": format_list_for_csv(group_map.get(1, [])),
        "10-20": format_list_for_csv(group_map.get(2, [])),
        "21-31": format_list_for_csv(group_map.get(3, [])),
    }

    BET_DATA_DIR.mkdir(parents=True, exist_ok=True)
    with NEXTDRAW_PRED_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["bet_date", "1-9", "10-20", "21-31"])
        writer.writeheader()
        writer.writerow(record)


def main() -> None:
    """主程式入口。"""

    validate_params()
    run_b0_backtest_first()
    rows = read_m6_rows()
    group_bonus = load_group_json_bonus()
    group_scores = {
        group_option: build_group_strength(rows, group_option)
        for group_option in PRINT_GROUP_OPTIONS
    }
    quotas = allocate_group_quotas(group_scores)
    group_predictions = [
        build_group_prediction(
            rows,
            group_option,
            quotas[group_option],
            group_scores[group_option],
            group_bonus,
        )
        for group_option in PRINT_GROUP_OPTIONS
    ]
    bet_date = read_next_draw_date()
    print_prediction(bet_date, group_predictions)
    save_nextdraw_pred_csv(bet_date, group_predictions)


if __name__ == "__main__":
    main()
