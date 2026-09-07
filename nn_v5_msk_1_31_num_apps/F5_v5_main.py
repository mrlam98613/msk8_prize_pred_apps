from pathlib import Path
import csv
import itertools
import json
from typing import TypedDict

from f5_v5_settings import (
    ACTIVE_GROUP_KEY,
    BIRTHDAY_NUM_MAX,
    BIRTHDAY_NUM_MIN,
    COLD_REBOUND_JSON_NAME,
)


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
M6_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"
M4_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M4_lotto_prize_summary.csv"
JSON_PATH = CURRENT_DIR / "json_data" / "F5_v5_best_params.json"
COLD_REBOUND_JSON_PATH = CURRENT_DIR / "json_data" / COLD_REBOUND_JSON_NAME

# F5_v5 自動比較的簡化參數。
BACKTEST_DRAW_COUNT_LIST = [24] # 回測期 
WINDOW_DRAW_COUNT_LIST = [24] # 窗口期 
AFTER_NONE_HIT_RATE_THRESHOLD_LIST = [0.50, 0.60, 0.65]
PREDICT_PAIR_COUNT = 2 #
RECENT_DRAW_COUNT = 5
COLD_WARN_GAP = 12 #預設初步 冷號未開期 。
DEEP_COLD_WARN_GAP = 18 # 預設 深度冷號期。
DETAIL_DISPLAY_MODE = "simple"  # "detail" 顯示完整分析；"simple" 顯示簡單核對。

# 固定策略參數：寫入 JSON，供下一期預測讀取。
COMBINATION_TAKE_COUNT = 2
MAX_PREVIOUS_DRAW_OVERLAP = 1
PAIR_HIT_WEIGHT = 10.0
RECENCY_PAIR_WEIGHT = 3.0
COLD_NUM_WEIGHT = 1.5


class DrawRow(TypedDict):
    date: str
    nums: list[int]
    special: int | None


class BacktestRow(TypedDict):
    backtest_date: str
    backtest_draw_display: str
    backtest_1_31_count: int
    check_date: str
    check_draw_display: str
    check_1_31_count: int
    predictions: list[tuple[int, int]]
    candidate_nums: list[int]
    hit_nums: list[int]
    hit_count: int
    prediction_mode: str
    actual_1_9_count: int
    actual_1_9_nums: list[int]
    window_cold_nums: list[int]
    deep_cold_nums: list[int]
    window_categories: dict[str, int]
    recent_rows: list[dict[str, object]]
    predicted_cold_nums: list[int]
    cold_hit_nums: list[int]
    allocation_correct: bool


def to_float(value: object, default: float = 0.0) -> float:
    if not isinstance(value, (int, float, str)):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def to_int(value: object, default: int = 0) -> int:
    if not isinstance(value, (int, float, str)):
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"找不到 CSV：{path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [{(key or "").strip(): (value or "").strip() for key, value in row.items()} for row in reader]


def read_draws() -> list[DrawRow]:
    draws: list[DrawRow] = []
    for row in read_csv_rows(M6_CSV):
        date = row.get("nDdate", "")
        if date:
            special = to_int(row.get("N7"))
            draws.append({
                "date": date,
                "nums": [to_int(row.get(f"N{index}")) for index in range(1, 7)],
                "special": special if 1 <= special <= 49 else None,
            })
    return draws


def load_cold_rebound_best() -> dict[str, object]:
    if not COLD_REBOUND_JSON_PATH.exists():
        return {}
    try:
        data = json.loads(COLD_REBOUND_JSON_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    group = data.get("analysis_group", {})
    if not isinstance(group, dict) or group.get("key") != ACTIVE_GROUP_KEY:
        return {}
    best = data.get("best", {})
    return best if isinstance(best, dict) else {}


def read_next_draw_date() -> str:
    rows = read_csv_rows(M4_CSV)
    return rows[-1].get("next_draw_date", "") if rows else ""


def all_draw_nums(row: DrawRow) -> set[int]:
    nums = {num for num in row["nums"] if 1 <= num <= 49}
    if row["special"] is not None:
        nums.add(row["special"])
    return nums


def birthday_nums(row: DrawRow) -> set[int]:
    return {num for num in all_draw_nums(row) if BIRTHDAY_NUM_MIN <= num <= BIRTHDAY_NUM_MAX}


def format_nums(nums: list[int]) -> str:
    return "[" + ",".join(str(num) for num in nums) + "]"


def format_1_31_draw(row: DrawRow) -> str:
    normal_nums = [str(num) if 1 <= num <= 31 else "_" for num in row["nums"]]
    special = row["special"]
    special_text = f"*{special}" if special is not None and 1 <= special <= 31 else "_"
    return "[" + ",".join(normal_nums + [special_text]) + "]"


def count_1_31_draw(row: DrawRow) -> int:
    normal_count = sum(1 for num in row["nums"] if 1 <= num <= 31)
    special_count = 1 if row["special"] is not None and 1 <= row["special"] <= 31 else 0
    return normal_count + special_count


def format_pairs(pairs: list[tuple[int, int]]) -> str:
    return ", ".join(f"({left},{right})" for left, right in pairs) or "-"


def count_categories(rows: list[DrawRow]) -> dict[str, int]:
    counts = {"none": 0, "single": 0, "multi": 0}
    for row in rows:
        count = len(birthday_nums(row))
        counts["none" if count == 0 else "single" if count == 1 else "multi"] += 1
    return counts


def cold_numbers(rows: list[DrawRow], gap: int) -> set[int]:
    appeared = {num for row in rows[-gap:] for num in birthday_nums(row)}
    return set(range(BIRTHDAY_NUM_MIN, BIRTHDAY_NUM_MAX + 1)) - appeared


def pair_scores(rows: list[DrawRow]) -> dict[tuple[int, int], float]:
    scores = {pair: 0.0 for pair in itertools.combinations(range(BIRTHDAY_NUM_MIN, BIRTHDAY_NUM_MAX + 1), 2)}
    total = len(rows)
    cold = cold_numbers(rows, COLD_WARN_GAP)
    for index, row in enumerate(rows):
        nums = sorted(birthday_nums(row))
        recency = (index + 1) / total if total else 0.0
        for pair in itertools.combinations(nums, 2):
            scores[pair] += PAIR_HIT_WEIGHT + RECENCY_PAIR_WEIGHT * recency
    for pair in scores:
        scores[pair] += COLD_NUM_WEIGHT * sum(num in cold for num in pair)
    return scores


def after_none_rate(draws: list[DrawRow], check_index: int, window_count: int) -> float:
    history = draws[max(0, check_index - window_count - 1):check_index]
    none_count = 0
    returned_count = 0
    for previous, following in zip(history, history[1:]):
        if not birthday_nums(previous):
            none_count += 1
            returned_count += bool(birthday_nums(following))
    return returned_count / none_count if none_count else 0.0


def should_predict_1_9(
    draws: list[DrawRow],
    check_index: int,
    window_count: int,
    after_none_threshold: float,
) -> bool:
    previous_nums = birthday_nums(draws[check_index - 1])
    if previous_nums:
        return True
    return after_none_rate(draws, check_index, window_count) >= after_none_threshold


def select_pairs(window_rows: list[DrawRow]) -> list[tuple[int, int]]:
    previous_nums = birthday_nums(window_rows[-1]) if window_rows else set()
    ranked = sorted(pair_scores(window_rows).items(), key=lambda item: (-item[1], item[0]))
    selected: list[tuple[int, int]] = []
    for pair, _ in ranked:
        if len(set(pair) & previous_nums) > MAX_PREVIOUS_DRAW_OVERLAP:
            continue
        selected.append(pair)
        if len(selected) == PREDICT_PAIR_COUNT:
            break
    return selected


def run_backtest_once(
    draws: list[DrawRow],
    backtest_count: int,
    window_count: int,
    after_none_threshold: float,
) -> list[BacktestRow]:
    if backtest_count <= 0 or len(draws) < backtest_count + window_count:
        return []
    first_check_index = len(draws) - backtest_count
    results: list[BacktestRow] = []
    for check_index in range(first_check_index, len(draws)):
        window_rows = draws[check_index - window_count:check_index]
        prediction_mode = "發球" if should_predict_1_9(
            draws, check_index, window_count, after_none_threshold
        ) else "不發球"
        pairs = select_pairs(window_rows) if prediction_mode == "發球" else []
        candidates = sorted({num for pair in pairs for num in pair})
        backtest_row = window_rows[-1]
        check_row = draws[check_index]
        actual_nums = birthday_nums(check_row)
        window_cold_nums = cold_numbers(window_rows, COLD_WARN_GAP)
        deep_cold_nums = cold_numbers(draws[:check_index], DEEP_COLD_WARN_GAP)
        recent_rows = [
            {
                "date": row["date"],
                "nums": sorted(birthday_nums(row)),
                "count": len(birthday_nums(row)),
            }
            for row in window_rows[-RECENT_DRAW_COUNT:]
        ]
        predicted_cold_nums = sorted(set(candidates) & window_cold_nums)
        hits = sorted(set(candidates) & actual_nums)
        cold_hit_nums = sorted(set(predicted_cold_nums) & actual_nums)
        allocation_correct = bool(actual_nums) if prediction_mode == "發球" else not actual_nums
        results.append({
            "backtest_date": backtest_row["date"],
            "backtest_draw_display": format_1_31_draw(backtest_row),
            "backtest_1_31_count": count_1_31_draw(backtest_row),
            "check_date": check_row["date"],
            "check_draw_display": format_1_31_draw(check_row),
            "check_1_31_count": count_1_31_draw(check_row),
            "predictions": pairs,
            "candidate_nums": candidates,
            "hit_nums": hits,
            "hit_count": len(hits),
            "prediction_mode": prediction_mode,
            "actual_1_9_count": len(actual_nums),
            "actual_1_9_nums": sorted(actual_nums),
            "window_cold_nums": sorted(window_cold_nums),
            "deep_cold_nums": sorted(deep_cold_nums),
            "window_categories": count_categories(window_rows),
            "recent_rows": recent_rows,
            "predicted_cold_nums": predicted_cold_nums,
            "cold_hit_nums": cold_hit_nums,
            "allocation_correct": allocation_correct,
        })
    return results


def summarize(
    backtest_count: int,
    window_count: int,
    after_none_threshold: float,
    rows: list[BacktestRow],
) -> dict[str, object]:
    counts = {level: sum(row["hit_count"] == level for row in rows) for level in range(5)}
    total_count = len(rows)
    actual_none_count = sum(row["actual_1_9_count"] == 0 for row in rows)
    actual_has_num_count = sum(row["actual_1_9_count"] > 0 for row in rows)
    hit_1_plus_count = sum(
        row["prediction_mode"] == "發球" and row["actual_1_9_count"] > 0 and row["hit_count"] >= 1
        for row in rows
    )
    hit_2_plus_count = sum(
        row["prediction_mode"] == "發球" and row["actual_1_9_count"] > 0 and row["hit_count"] >= 2
        for row in rows
    )
    hit_3_plus_count = sum(
        row["prediction_mode"] == "發球" and row["actual_1_9_count"] > 0 and row["hit_count"] >= 3
        for row in rows
    )
    correct_no_prediction_count = sum(
        row["prediction_mode"] == "不發球" and row["allocation_correct"] for row in rows
    )
    missed_no_prediction_count = sum(
        row["prediction_mode"] == "不發球" and not row["allocation_correct"] for row in rows
    )
    incorrect_prediction_count = sum(
        row["prediction_mode"] == "發球" and not row["allocation_correct"] for row in rows
    )
    return {
        "backtest_draw_count": backtest_count,
        "window_draw_count": window_count,
        "after_none_threshold": after_none_threshold,
        "total_count": total_count,
        "actual_none_count": actual_none_count,
        "actual_has_num_count": actual_has_num_count,
        "hit_4_count": counts[4],
        "hit_3_count": counts[3],
        "hit_2_count": counts[2],
        "hit_1_count": counts[1],
        "hit_0_count": counts[0],
        "hit_4_rate": counts[4] / total_count if total_count else 0.0,
        "hit_3_rate": counts[3] / total_count if total_count else 0.0,
        "hit_2_rate": counts[2] / total_count if total_count else 0.0,
        "hit_1_rate": counts[1] / total_count if total_count else 0.0,
        "hit_1_plus_count": hit_1_plus_count,
        "hit_2_plus_count": hit_2_plus_count,
        "hit_3_plus_count": hit_3_plus_count,
        "hit_1_plus_effective_rate": hit_1_plus_count / actual_has_num_count if actual_has_num_count else 0.0,
        "hit_2_plus_effective_rate": hit_2_plus_count / actual_has_num_count if actual_has_num_count else 0.0,
        "hit_3_plus_effective_rate": hit_3_plus_count / actual_has_num_count if actual_has_num_count else 0.0,
        "correct_no_prediction_count": correct_no_prediction_count,
        "missed_no_prediction_count": missed_no_prediction_count,
        "incorrect_prediction_count": incorrect_prediction_count,
        "no_prediction_hit_rate": correct_no_prediction_count / actual_none_count if actual_none_count else 0.0,
        "allocation_correct_rate": sum(row["allocation_correct"] for row in rows) / total_count if total_count else 0.0,
        "score": counts[4] * 20 + counts[3] * 8 + counts[2] * 3 + counts[1]
        + correct_no_prediction_count * 3
        - missed_no_prediction_count * 3
        - incorrect_prediction_count * 2,
    }


def sort_summaries(items: list[dict[str, object]]) -> list[dict[str, object]]:
    return sorted(items, key=lambda item: (
        -to_float(item.get("hit_3_plus_effective_rate")),
        -to_float(item.get("hit_2_plus_effective_rate")),
        -to_float(item.get("hit_1_plus_effective_rate")),
        -to_float(item.get("no_prediction_hit_rate")),
        -to_float(item.get("allocation_correct_rate")),
        -to_int(item.get("score")) / max(to_int(item.get("total_count")), 1),
        to_int(item.get("window_draw_count")),
        to_float(item.get("after_none_threshold")),
        to_int(item.get("backtest_draw_count")),
    ))


def run_parameter_search(
    draws: list[DrawRow],
) -> tuple[dict[str, object], list[dict[str, object]], list[BacktestRow], dict[str, list[BacktestRow]]]:
    summaries: list[dict[str, object]] = []
    detail_by_key: dict[tuple[int, int, float], list[BacktestRow]] = {}
    for backtest_count in BACKTEST_DRAW_COUNT_LIST:
        for window_count in WINDOW_DRAW_COUNT_LIST:
            for threshold in AFTER_NONE_HIT_RATE_THRESHOLD_LIST:
                rows = run_backtest_once(draws, backtest_count, window_count, threshold)
                detail_by_key[(backtest_count, window_count, threshold)] = rows
                summaries.append(summarize(backtest_count, window_count, threshold, rows))
    ranking = sort_summaries(summaries)
    best = ranking[0]
    best_key = (
        to_int(best["backtest_draw_count"]),
        to_int(best["window_draw_count"]),
        to_float(best["after_none_threshold"]),
    )
    all_details = {
        f"backtest_{backtest}_window_{window}_threshold_{threshold:.0%}": rows
        for (backtest, window, threshold), rows in detail_by_key.items()
    }
    return best, ranking, detail_by_key[best_key], all_details


def fixed_weights() -> dict[str, object]:
    return {
        "pair_hit_weight": PAIR_HIT_WEIGHT,
        "recency_pair_weight": RECENCY_PAIR_WEIGHT,
        "cold_num_weight": COLD_NUM_WEIGHT,
        "max_previous_draw_overlap": MAX_PREVIOUS_DRAW_OVERLAP,
        "predict_pair_count": PREDICT_PAIR_COUNT,
        "recent_draw_count": RECENT_DRAW_COUNT,
        "cold_warn_gap": COLD_WARN_GAP,
        "deep_cold_warn_gap": DEEP_COLD_WARN_GAP,
        "after_none_hit_rate_threshold_list": AFTER_NONE_HIT_RATE_THRESHOLD_LIST,
    }


def save_json(
    best: dict[str, object],
    ranking: list[dict[str, object]],
    rows: list[BacktestRow],
    all_details: dict[str, list[BacktestRow]],
    next_pairs: list[tuple[int, int]],
) -> None:
    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "model": "F5_v5_upgrade",
        "best": best,
        "ranking": ranking,
        "weights": fixed_weights(),
        "backtest_rows": rows,
        "parameter_backtest_details": all_details,
        "next_prediction": {
            "bet_date": read_next_draw_date(),
            "pairs": [list(pair) for pair in next_pairs],
            "candidate_nums": sorted({num for pair in next_pairs for num in pair}),
        },
    }
    JSON_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def print_ranking(ranking: list[dict[str, object]]) -> None:
    print("====== F5_v5 [1-9] 號，參數比較（本次回測） ======")
    print("回測期 | 窗口期 | (00)門檻 | 有號期 | 命中3+ | 命中2+ | 命中1+ | 00期 | 命中00 | 錯失00 | 分數")
    for item in ranking:
        print(
            f"{to_int(item['backtest_draw_count']):>6} | {to_int(item['window_draw_count']):>6} | "
            f"{to_float(item['after_none_threshold']):>7.0%} | "
            f"{to_int(item['actual_has_num_count']):>4} | "
            f"{to_int(item['hit_3_plus_count']):>3}({to_float(item['hit_3_plus_effective_rate']):>4.0%}) | "
            f"{to_int(item['hit_2_plus_count']):>3}({to_float(item['hit_2_plus_effective_rate']):>4.0%}) | "
            f"{to_int(item['hit_1_plus_count']):>3}({to_float(item['hit_1_plus_effective_rate']):>4.0%}) | "
            f"{to_int(item['actual_none_count']):>3} | "
            f"{to_int(item['correct_no_prediction_count']):>4} | "
            f"{to_int(item['missed_no_prediction_count']):>4} | {to_int(item['score']):>4}"
        )
    print()


def print_detail_view(rows: list[BacktestRow], best: dict[str, object]) -> None:
    print("====== 最佳參數逐期獨立分析與核對 ======")
    print(
        f"最佳參數：回測期 {to_int(best.get('backtest_draw_count'))}，"
        f"窗口期 {to_int(best.get('window_draw_count'))}，"
        f"(00) 門檻 {to_float(best.get('after_none_threshold')):.0%}"
    )
    for rank, row in enumerate(rows, start=1):
        categories = row["window_categories"]
        print("------------------------------------------------------------")
        print(
            f"/> {rank} 回測期：{row['backtest_date']} {row['backtest_draw_display']} "
            f"/> {row['backtest_1_31_count']} 球"
        )
        print(
            f"     - 核對期：{row['check_date']}，{row['check_draw_display']} "
            f"/> {row['check_1_31_count']} 球"
        )
        print(
            f"窗口分類：00={categories['none']}，"
            f"1球={categories['single']}，2球+={categories['multi']}"
        )
        print(
            f"{COLD_WARN_GAP} 期冷號：{format_nums(row['window_cold_nums'])}，"
            f"{DEEP_COLD_WARN_GAP} 期很冷號：{format_nums(row['deep_cold_nums'])}"
        )
        for offset, recent in enumerate(row["recent_rows"], start=1):
            near_index = len(row["recent_rows"]) - offset + 1
            count_text = "None" if to_int(recent["count"]) == 0 else f"{to_int(recent['count'])} 球"
            numbers = recent["nums"] if isinstance(recent["nums"], list) else []
            print(f"最近 {near_index} 期：{recent['date']}，{format_nums(numbers)} = {count_text}")
        if row["prediction_mode"] == "不發球":
            result = "正確避開" if row["allocation_correct"] else "錯失發球"
            score_text = "+ 3 球" if row["allocation_correct"] else "- 3 球"
            print(
                f"預測：None（不發球），1-9 開獎 {format_nums(row['actual_1_9_nums'])} "
                f"{row['actual_1_9_count']} 球，{result}，{score_text}"
            )
        else:
            print(f"預測：{format_pairs(row['predictions'])} -> {format_nums(row['candidate_nums'])}")
            print(f"核對命中：{format_nums(row['hit_nums'])} / {row['hit_count']} 球")
    print("------------------------------------------------------------")
    print()


def print_simple_view(rows: list[BacktestRow], best: dict[str, object]) -> None:
    print("====== 最佳參數逐期核對 ======")
    print(
        f"最佳參數：回測期 {to_int(best.get('backtest_draw_count'))}，"
        f"窗口期 {to_int(best.get('window_draw_count'))}，"
        f"(00) 門檻 {to_float(best.get('after_none_threshold')):.0%}"
    )
    total_rows = len(rows)
    for display_index, row in enumerate(rows, start=1):
        near_index = total_rows - display_index + 1
        if row["prediction_mode"] == "不發球":
            result = "正確避開" if row["allocation_correct"] else "錯失發球"
            score_text = "+ 3 球" if row["allocation_correct"] else "- 3 球"
            print(
                f"/> {near_index}，核對期：{row['check_date']}，預測：None（不發球），"
                f"1-9 開獎 {format_nums(row['actual_1_9_nums'])} "
                f"{row['actual_1_9_count']} 球，{result}，{score_text}"
            )
            continue
        print(
            f"/> {near_index}，核對期：{row['check_date']}，預測：{format_pairs(row['predictions'])} "
            f"-> {format_nums(row['candidate_nums'])}，"
            f"開獎 {format_nums(row['actual_1_9_nums']) if row['actual_1_9_count'] else '(00)'}，"
            f"命中 {format_nums(row['hit_nums'])} / {row['hit_count']} 球"
        )
    print()


def print_detail(rows: list[BacktestRow], best: dict[str, object]) -> None:
    if DETAIL_DISPLAY_MODE == "simple":
        print_simple_view(rows, best)
        return
    print_detail_view(rows, best)


def print_backtest_result(rows: list[BacktestRow]) -> None:
    actual_none = [row for row in rows if row["actual_1_9_count"] == 0]
    actual_one = [row for row in rows if row["actual_1_9_count"] == 1]
    actual_two = [row for row in rows if row["actual_1_9_count"] == 2]
    actual_three_plus = [row for row in rows if row["actual_1_9_count"] >= 3]
    actual_has_nums = [row for row in rows if row["actual_1_9_count"] > 0]
    hit_1_plus = sum(
        row["prediction_mode"] == "發球" and row["actual_1_9_count"] > 0 and row["hit_count"] >= 1
        for row in rows
    )
    hit_2_plus = sum(
        row["prediction_mode"] == "發球" and row["actual_1_9_count"] > 0 and row["hit_count"] >= 2
        for row in rows
    )
    hit_3_plus = sum(
        row["prediction_mode"] == "發球" and row["actual_1_9_count"] > 0 and row["hit_count"] >= 3
        for row in rows
    )
    zero_hit_with_nums = sum(
        row["prediction_mode"] == "發球" and row["actual_1_9_count"] > 0 and row["hit_count"] == 0
        for row in rows
    )
    correct_no_prediction = sum(
        row["prediction_mode"] == "不發球" and row["actual_1_9_count"] == 0
        for row in rows
    )
    missed_no_prediction = sum(
        row["prediction_mode"] == "不發球" and row["actual_1_9_count"] > 0
        for row in rows
    )
    cold_prediction_rows = [row for row in rows if row["predicted_cold_nums"]]
    cold_success_rows = [row for row in cold_prediction_rows if row["cold_hit_nums"]]
    cold_failed_rows = [row for row in cold_prediction_rows if not row["cold_hit_nums"]]

    print("====== F5_v5 [1-9] 回測結果檢測 ======")
    print("------------------------------------------")
    print(f"回測期檢測：{len(rows)} 期")
    print(f"實際 (00)：{len(actual_none)} 期")
    print(f"實際 == 1 球：{len(actual_one)} 期")
    print(f"實際 == 2 球：{len(actual_two)} 期")
    print(f"實際 >= 3 球：{len(actual_three_plus)} 期")
    print(f"實際有 1-9 號：{len(actual_has_nums)} 期")
    print("------------------------------------------")
    print("發球命中率只計：真實有 1-9 號的期數。")
    print(
        f"命中 >= 1 球：{hit_1_plus} 期 / 真實有 1-9：{len(actual_has_nums)} 期，"
        f"{hit_1_plus / len(actual_has_nums):.2%}" if actual_has_nums else "命中 >= 1 球：0 期 / 真實有 1-9：0 期"
    )
    print(
        f"命中 >= 2 球：{hit_2_plus} 期 / 真實有 1-9：{len(actual_has_nums)} 期，"
        f"{hit_2_plus / len(actual_has_nums):.2%}" if actual_has_nums else "命中 >= 2 球：0 期 / 真實有 1-9：0 期"
    )
    print(
        f"命中 >= 3 球：{hit_3_plus} 期 / 真實有 1-9：{len(actual_has_nums)} 期，"
        f"{hit_3_plus / len(actual_has_nums):.2%}" if actual_has_nums else "命中 >= 3 球：0 期 / 真實有 1-9：0 期"
    )
    print(f"有 1-9 但發球不中：{zero_hit_with_nums} 期 / 真實有 1-9：{len(actual_has_nums)} 期")
    print("------------------------------------------")
    print(
        f"命中 (00)：{correct_no_prediction} 期 / 實際 (00)：{len(actual_none)} 期，"
        f"{correct_no_prediction / len(actual_none):.2%}" if actual_none else "命中 (00)：0 期 / 實際 (00)：0 期"
    )
    print(f"預測 (00) 失敗：{missed_no_prediction} 期 / 實際有 1-9 號：{len(actual_has_nums)} 期")
    print("------------------------------------------")
    print(f"冷號預測期數：{len(cold_prediction_rows)} 期")
    print(f"冷號預測成功：{len(cold_success_rows)} 期 / 冷號預測期數：{len(cold_prediction_rows)} 期")
    print(f"冷號預測失敗：{len(cold_failed_rows)} 期 / 冷號預測期數：{len(cold_prediction_rows)} 期")
    print(f"合共：{len(rows)} 期")
    print("------------------------------------------")
    print()


def print_next_prediction(draws: list[DrawRow], best: dict[str, object]) -> list[tuple[int, int]]:
    window_count = to_int(best.get("window_draw_count"), WINDOW_DRAW_COUNT_LIST[0])
    threshold = to_float(best.get("after_none_threshold"), AFTER_NONE_HIT_RATE_THRESHOLD_LIST[0])
    predict_1_9 = should_predict_1_9(draws, len(draws), window_count, threshold)
    window_rows = draws[-window_count:]
    pairs = select_pairs(window_rows) if predict_1_9 else []
    candidates = sorted({num for pair in pairs for num in pair})
    categories = count_categories(window_rows)
    latest_row = draws[-1]
    cold_nums = cold_numbers(window_rows, COLD_WARN_GAP)
    deep_cold_nums = cold_numbers(draws, DEEP_COLD_WARN_GAP)

    print("====== F5_v5 下期預測 ======")
    print(
        f"最佳參數：回測期 {to_int(best.get('backtest_draw_count'))}，"
        f"窗口期 {window_count}，(00) 門檻 {threshold:.0%}"
    )
    print("------------------------------------------------------------")
    print(
        f"最新開獎期：{latest_row['date']} {format_1_31_draw(latest_row)} "
        f"/> {count_1_31_draw(latest_row)} 球"
    )
    print(f"下期日期：{read_next_draw_date()}")
    print(
        f"窗口分類：00={categories['none']}，"
        f"1球={categories['single']}，2球+={categories['multi']}"
    )
    print(
        f"{COLD_WARN_GAP} 期冷號：{format_nums(sorted(cold_nums))}，"
        f"{DEEP_COLD_WARN_GAP} 期很冷號：{format_nums(sorted(deep_cold_nums))}"
    )
    print("------------------------------------------")
    for offset, row in enumerate(window_rows[-RECENT_DRAW_COUNT:], start=1):
        near_index = len(window_rows[-RECENT_DRAW_COUNT:]) - offset + 1
        numbers = sorted(birthday_nums(row))
        count_text = "None" if not numbers else f"{len(numbers)} 球"
        print(f"最近 {near_index} 期：{row['date']}，{format_nums(numbers)} = {count_text}")
    print("------------------------------------------")
    if not predict_1_9:
        print("預測：None（不發球，保留 1-9 配額）")
    else:
        print(f"預測雙球：{format_pairs(pairs)}")
        print(f"合併候選球：{format_nums(candidates)}")
    print("============== 完結 ==============")
    return pairs


def main() -> None:
    draws = read_draws()
    if not draws:
        raise RuntimeError("沒有可用開獎資料。")
    best, ranking, rows, all_details = run_parameter_search(draws)
    print_ranking(ranking)
    print_detail(rows, best)
    print_backtest_result(rows)
    next_pairs = print_next_prediction(draws, best)
    save_json(best, ranking, rows, all_details, next_pairs)


if __name__ == "__main__":
    main()
