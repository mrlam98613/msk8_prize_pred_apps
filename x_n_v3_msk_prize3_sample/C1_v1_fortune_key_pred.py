from pathlib import Path
import csv
import itertools
import json
import sys
from typing import TypedDict
'''
5+ = 5、5.5、6 球
4+ = 4、4.5 球
3+ = 3、3.5 球

'''


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from x_n_v2_msk_prize_31_num_backtest_pred.res_func_num_convert_RBG_Dict import res_List_To_rbg_Dict_func

M6_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"
M4_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M4_lotto_prize_summary.csv"
JSON_PATH = CURRENT_DIR / "json_data" / "C1_v1_simple_best_params.json"
BET_DATA_DIR = CURRENT_DIR / "bet_data"
NEXTDRAW_PRED_CSV = BET_DATA_DIR / "C1_v1_nextdraw_pred.csv"
BACKTEST_CHECK_CSV = BET_DATA_DIR / "C1_v1_backtest_check_rows.csv"

# 簡化版只保留核心列表；回測會自動選最佳組合，再給預測模式讀入。
BACKTEST_DRAW_COUNT_LIST = [30]
WINDOW_DRAW_COUNT_LIST = [12,18,21]
TOP_PRIZE_DRAW_COUNT_LIST = [5,7]
PRIZE_OPTION = 3
MATCH_COUNT = 2
MATCH_MODE = ">="
GROUP_QUOTA_LIST = [
    (3, 3, 3),
    # (2, 2, 3),
    # (2, 3, 2),
    # (3, 2, 2),
]
GROUPS = {
    1: ("1-9", 1, 9),
    2: ("10-20", 10, 20),
    3: ("21-31", 21, 31),
}

PAIR_HIT_WEIGHT = 7
NUM_HIT_WEIGHT = 1
PRIZE_WEIGHT = 1.0
RECENCY_WEIGHTS = [7, 6, 5, 4, 3, 2, 1]
SCORE_WEIGHTS = {
    6.0: 80,
    5.5: 60,
    5.0: 45,
    4.5: 30,
    4.0: 20,
    3.5: 12,
    3.0: 8,
    2.5: 5,
    2.0: 3,
    1.5: 2,
    1.0: 1,
    0.5: 0.5,
    0.0: -2,
}

# ======================== Start of C1_v1 core functions ========================
class DrawRow(TypedDict):
    date: str
    nums: list[int]
    special: int | None
    prize_count: float


class BacktestRow(TypedDict):
    rank: int
    check_date: str
    predictions: dict[str, list[int]]
    hit_nums: list[int]
    special_hit: int | None
    hit_score: float
    prize_level: str


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames:
            reader.fieldnames = [name.strip().lstrip("\ufeff") for name in reader.fieldnames]
        return [
            {(key or "").strip().lstrip("\ufeff"): (value or "").strip() for key, value in row.items()}
            for row in reader
        ]


def to_int(value: object, default: int = 0) -> int:
    if not isinstance(value, (int, float, str)):
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def to_float(value: object, default: float = 0.0) -> float:
    if not isinstance(value, (int, float, str)):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_m6_row(row: dict[str, str]) -> DrawRow:
    nums = [to_int(row.get(f"N{idx}")) for idx in range(1, 7)]
    special = to_int(row.get("N7"))
    return {
        "date": row.get("nDdate", ""),
        "nums": nums,
        "special": special if 1 <= special <= 49 else None,
        "prize_count": to_float(row.get(f"prize{PRIZE_OPTION}")),
    }


def read_draws() -> list[DrawRow]:
    rows = [parse_m6_row(row) for row in read_csv_rows(M6_CSV)]
    return [row for row in rows if row["date"]]


def read_next_draw_date() -> str:
    rows = read_csv_rows(M4_CSV)
    return rows[-1].get("next_draw_date", "") if rows else ""


def group_name(group_id: int) -> str:
    return GROUPS[group_id][0]


def selected_nums(nums: list[int], group_id: int) -> list[int]:
    _name, start_num, end_num = GROUPS[group_id]
    return sorted(num for num in nums if start_num <= num <= end_num)


def is_matched(count: int) -> bool:
    if MATCH_MODE == "==":
        return count == MATCH_COUNT
    return count >= MATCH_COUNT


def build_window_samples(draws: list[DrawRow], target_index: int, group_id: int, window_count: int) -> list[DrawRow]:
    window_rows = draws[max(0, target_index - window_count):target_index]
    matched: list[DrawRow] = []
    for row in window_rows:
        if is_matched(len(selected_nums(row["nums"], group_id))):
            matched.append(row)
    return sorted(matched, key=lambda item: (-item["prize_count"], item["date"]))


def build_group_prediction(
    samples: list[DrawRow],
    group_id: int,
    top_prize_count: int,
    quota: int,
) -> list[int]:
    sample_rows = samples[:top_prize_count]
    scores: dict[int, float] = {}
    for idx, row in enumerate(sample_rows):
        nums = selected_nums(row["nums"], group_id)
        recency_weight = RECENCY_WEIGHTS[idx] if idx < len(RECENCY_WEIGHTS) else 1
        prize_bonus = max(1.0, row["prize_count"] / 100.0) * PRIZE_WEIGHT
        for num in nums:
            scores[num] = scores.get(num, 0.0) + NUM_HIT_WEIGHT + prize_bonus + recency_weight
        for pair in itertools.combinations(sorted(set(nums)), 2):
            pair_score = PAIR_HIT_WEIGHT + prize_bonus + recency_weight
            scores[pair[0]] = scores.get(pair[0], 0.0) + pair_score / 2
            scores[pair[1]] = scores.get(pair[1], 0.0) + pair_score / 2

    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return sorted(num for num, _score in ranked[:quota])


def quota_to_map(quota_tuple: tuple[int, int, int]) -> dict[int, int]:
    return {group_id: quota for group_id, quota in zip(GROUPS, quota_tuple)}


def format_quota(quota_tuple: tuple[int, int, int] | list[int]) -> str:
    return "+".join(str(num) for num in quota_tuple)


def format_nums(nums: list[int]) -> str:
    return "[" + ",".join(str(num) for num in nums) + "]"


def format_rbg_lines(nums: list[int]) -> list[str]:
    rbg_dict = res_List_To_rbg_Dict_func(sorted(nums))
    return [
        f"R：{format_nums(sorted(rbg_dict.get(0, [])))} /> {len(rbg_dict.get(0, []))} 球",
        f"B：{format_nums(sorted(rbg_dict.get(1, [])))} /> {len(rbg_dict.get(1, []))} 球",
        f"G：{format_nums(sorted(rbg_dict.get(2, [])))} /> {len(rbg_dict.get(2, []))} 球",
    ]


def get_hit_score(normal_hit_count: int, has_special_hit: bool) -> float:
    if normal_hit_count >= 6:
        return 6.0
    return normal_hit_count + (0.5 if has_special_hit else 0.0)


def get_prize_level(normal_hit_count: int, has_special_hit: bool) -> str:
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


def check_prediction(check_row: DrawRow, predictions: dict[str, list[int]], rank: int) -> BacktestRow:
    predicted_nums = {num for nums in predictions.values() for num in nums}
    check_1_31 = {num for num in check_row["nums"] if 1 <= num <= 31}
    hit_nums = sorted(predicted_nums & check_1_31)
    special_hit = check_row["special"] if check_row["special"] in predicted_nums else None
    return {
        "rank": rank,
        "check_date": check_row["date"],
        "predictions": predictions,
        "hit_nums": hit_nums,
        "special_hit": special_hit,
        "hit_score": get_hit_score(len(hit_nums), special_hit is not None),
        "prize_level": get_prize_level(len(hit_nums), special_hit is not None),
    }


def run_backtest_once(
    draws: list[DrawRow],
    backtest_count: int,
    window_count: int,
    top_prize_count: int,
    quota_tuple: tuple[int, int, int],
) -> list[BacktestRow]:
    if len(draws) <= window_count + 1:
        return []
    last_check_index = len(draws) - 1
    first_check_index = max(window_count, last_check_index - backtest_count + 1)
    check_indices = list(range(first_check_index, last_check_index + 1))
    total_targets = len(check_indices)
    result_rows: list[BacktestRow] = []
    quotas = quota_to_map(quota_tuple)

    for display_index, check_index in enumerate(check_indices, start=1):
        predictions: dict[str, list[int]] = {}
        for group_id in GROUPS:
            samples = build_window_samples(draws, check_index, group_id, window_count)
            predictions[group_name(group_id)] = build_group_prediction(
                samples,
                group_id,
                top_prize_count,
                quotas[group_id],
            )
        check_row = draws[check_index]
        result_rows.append(check_prediction(check_row, predictions, total_targets - display_index + 1))
    return result_rows


def exact_counts(backtest_rows: list[BacktestRow]) -> dict[float, int]:
    levels = [6, 5.5, 5, 4.5, 4, 3.5, 3, 2.5, 2, 1.5, 1, 0.5, 0]
    counts = {float(level): 0 for level in levels}
    for row in backtest_rows:
        score = row["hit_score"]
        counts[score] = counts.get(score, 0) + 1
    return counts


def model_score(counts: dict[float, int]) -> float:
    return sum(counts.get(level, 0) * weight for level, weight in SCORE_WEIGHTS.items())


def summarize_result(
    backtest_count: int,
    window_count: int,
    top_prize_count: int,
    quota_tuple: tuple[int, int, int],
    backtest_rows: list[BacktestRow],
) -> dict[str, object]:
    counts = exact_counts(backtest_rows)
    total_count = len(backtest_rows)
    hit_5_or_above = sum(count for level, count in counts.items() if level >= 5)
    hit_4_or_above = sum(count for level, count in counts.items() if level >= 4)
    hit_3_or_above = sum(count for level, count in counts.items() if level >= 3)
    zero_count = counts.get(0, 0)
    score = model_score(counts)
    prize_counts = {
        f"prize_{prize}_count": sum(1 for row in backtest_rows if row["prize_level"] == f"{prize}獎")
        for prize in range(1, 8)
    }
    prize_counts["no_prize_count"] = sum(1 for row in backtest_rows if row["prize_level"] == "未中獎")
    prize_counts["target_prize_count"] = sum(
        prize_counts[f"prize_{prize}_count"] for prize in range(3, 8)
    )
    grouped_counts = {
        "hit_5_plus_count": sum(counts.get(level, 0) for level in (5.0, 5.5, 6.0)),
        "hit_4_plus_count": sum(counts.get(level, 0) for level in (4.0, 4.5)),
        "hit_3_plus_count": sum(counts.get(level, 0) for level in (3.0, 3.5)),
    }
    return {
        "backtest_draw_count": backtest_count,
        "window_draw_count": window_count,
        "top_prize_draw_count": top_prize_count,
        "group_quota": list(quota_tuple),
        "group_quota_text": format_quota(quota_tuple),
        "total_count": total_count,
        "hit_5_or_above": hit_5_or_above,
        "hit_4_or_above": hit_4_or_above,
        "hit_3_or_above": hit_3_or_above,
        "zero_count": zero_count,
        "hit_5_rate": hit_5_or_above / total_count if total_count else 0.0,
        "hit_4_rate": hit_4_or_above / total_count if total_count else 0.0,
        "hit_3_rate": hit_3_or_above / total_count if total_count else 0.0,
        "zero_rate": zero_count / total_count if total_count else 0.0,
        "average_score": score / total_count if total_count else 0.0,
        "score": score,
        **prize_counts,
        **grouped_counts,
        "exact_counts": {f"{level:g}": count for level, count in counts.items()},
        "check_dates": [row["check_date"] for row in backtest_rows],
    }


def sort_summaries(summaries: list[dict[str, object]]) -> list[dict[str, object]]:
    return sorted(
        summaries,
        key=lambda item: (
            -to_int(item.get("hit_5_plus_count")),
            -to_int(item.get("hit_4_plus_count")),
            -to_int(item.get("hit_3_plus_count")),
            -to_int(item.get("target_prize_count")),
            to_int(item.get("no_prize_count")),
            -to_float(item.get("score")),
            -to_int(item.get("total_count")),
            to_int(item.get("backtest_draw_count")),
            to_int(item.get("window_draw_count")),
            to_int(item.get("top_prize_draw_count")),
            str(item.get("group_quota_text", "")),
        ),
    )


def load_historical_rankings(current_latest_date: str) -> list[list[dict[str, object]]]:
    if not JSON_PATH.exists():
        return []
    try:
        data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    history = data.get("run_history", []) if isinstance(data, dict) else []
    if not isinstance(history, list):
        return []
    rankings: list[list[dict[str, object]]] = []
    for run in history:
        if not isinstance(run, dict):
            continue
        check_dates = run.get("check_dates", [])
        if current_latest_date and isinstance(check_dates, list) and current_latest_date in check_dates:
            continue
        ranking = run.get("ranking")
        if isinstance(ranking, list):
            rankings.append([item for item in ranking if isinstance(item, dict)])
    return rankings


def aggregate_summary_history(
    current_ranking: list[dict[str, object]],
    historical_rankings: list[list[dict[str, object]]],
) -> list[dict[str, object]]:
    active_keys = {
        (
            to_int(item.get("backtest_draw_count")),
            to_int(item.get("window_draw_count")),
            to_int(item.get("top_prize_draw_count")),
            str(item.get("group_quota_text", "")),
        )
        for item in current_ranking
    }
    current_by_key: dict[tuple[int, int, int, str], dict[str, object]] = {}
    for item in current_ranking:
        current_key = (
            to_int(item.get("backtest_draw_count")),
            to_int(item.get("window_draw_count")),
            to_int(item.get("top_prize_draw_count")),
            str(item.get("group_quota_text", "")),
        )
        current_by_key[current_key] = item

    grouped: dict[tuple[int, int, int, str], dict[str, object]] = {}
    for ranking in [*historical_rankings, current_ranking]:
        for item in ranking:
            key = (
                to_int(item.get("backtest_draw_count")),
                to_int(item.get("window_draw_count")),
                to_int(item.get("top_prize_draw_count")),
                str(item.get("group_quota_text", "")),
            )
            if key not in active_keys:
                continue
            if key not in grouped:
                grouped[key] = {
                    "backtest_draw_count": key[0],
                    "window_draw_count": key[1],
                    "top_prize_draw_count": key[2],
                    "group_quota": item.get("group_quota", []),
                    "group_quota_text": key[3],
                    "total_count": 0,
                    "hit_5_or_above": 0,
                    "hit_4_or_above": 0,
                    "hit_3_or_above": 0,
                    "zero_count": 0,
                    "score": 0.0,
                    "exact_counts": {},
                }
            total = to_int(item.get("total_count"))
            aggregate = grouped[key]
            aggregate["total_count"] = to_int(aggregate.get("total_count")) + total
            for field in ["hit_5_or_above", "hit_4_or_above", "hit_3_or_above", "zero_count"]:
                aggregate[field] = to_int(aggregate.get(field)) + to_int(item.get(field))
            aggregate["score"] = to_float(aggregate.get("score")) + to_float(item.get("score"))
            exact_counts = aggregate["exact_counts"]
            source_counts = item.get("exact_counts", {})
            if isinstance(exact_counts, dict) and isinstance(source_counts, dict):
                for level, count in source_counts.items():
                    exact_counts[str(level)] = to_int(exact_counts.get(str(level))) + to_int(count)

    for aggregate in grouped.values():
        total = to_int(aggregate.get("total_count"))
        aggregate["hit_5_rate"] = to_int(aggregate.get("hit_5_or_above")) / total if total else 0.0
        aggregate["hit_4_rate"] = to_int(aggregate.get("hit_4_or_above")) / total if total else 0.0
        aggregate["hit_3_rate"] = to_int(aggregate.get("hit_3_or_above")) / total if total else 0.0
        aggregate["zero_rate"] = to_int(aggregate.get("zero_count")) / total if total else 0.0
        aggregate["average_score"] = to_float(aggregate.get("score")) / total if total else 0.0
        current = current_by_key.get((
            to_int(aggregate.get("backtest_draw_count")),
            to_int(aggregate.get("window_draw_count")),
            to_int(aggregate.get("top_prize_draw_count")),
            str(aggregate.get("group_quota_text", "")),
        ), {})
        aggregate["current_total_count"] = to_int(current.get("total_count"))
        aggregate["current_hit_5_or_above"] = to_int(current.get("hit_5_or_above"))
        aggregate["current_hit_4_or_above"] = to_int(current.get("hit_4_or_above"))
        aggregate["current_hit_3_or_above"] = to_int(current.get("hit_3_or_above"))
        aggregate["current_zero_count"] = to_int(current.get("zero_count"))
        aggregate["current_score"] = to_float(current.get("score"))
    return list(grouped.values())


def run_auto_backtest(draws: list[DrawRow]) -> tuple[dict[str, object], list[dict[str, object]], list[BacktestRow]]:
    summaries: list[dict[str, object]] = []
    backtest_by_key: dict[tuple[int, int, int, str], list[BacktestRow]] = {}
    for backtest_count in BACKTEST_DRAW_COUNT_LIST:
        for window_count in WINDOW_DRAW_COUNT_LIST:
            for top_prize_count in TOP_PRIZE_DRAW_COUNT_LIST:
                for quota_tuple in GROUP_QUOTA_LIST:
                    rows = run_backtest_once(draws, backtest_count, window_count, top_prize_count, quota_tuple)
                    backtest_by_key[
                        (backtest_count, window_count, top_prize_count, format_quota(quota_tuple))
                    ] = rows
                    summaries.append(
                        summarize_result(backtest_count, window_count, top_prize_count, quota_tuple, rows)
                    )

    ranked = sort_summaries(summaries)
    best = ranked[0]
    best_key = (
        to_int(best.get("backtest_draw_count")),
        to_int(best.get("window_draw_count")),
        to_int(best.get("top_prize_draw_count")),
        str(best.get("group_quota_text", "")),
    )
    best_rows = backtest_by_key.get(best_key)
    if best_rows is None:
        best_quota_raw = best.get("group_quota", GROUP_QUOTA_LIST[0])
        if isinstance(best_quota_raw, list) and len(best_quota_raw) == len(GROUPS):
            best_quota: tuple[int, int, int] = (
                to_int(best_quota_raw[0], 3),
                to_int(best_quota_raw[1], 3),
                to_int(best_quota_raw[2], 3),
            )
        else:
            best_quota = GROUP_QUOTA_LIST[0]
        best_rows = run_backtest_once(
            draws,
            to_int(best.get("backtest_draw_count")),
            to_int(best.get("window_draw_count")),
            to_int(best.get("top_prize_draw_count")),
            best_quota,
        )
    return best, ranked, best_rows


def save_json(
    best: dict[str, object],
    ranking: list[dict[str, object]],
    backtest_rows: list[BacktestRow],
) -> None:
    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    previous: dict[str, object] = {}
    if JSON_PATH.exists():
        try:
            loaded = json.loads(JSON_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                previous = loaded
        except json.JSONDecodeError:
            previous = {}
    run_history = previous.get("run_history", [])
    if not isinstance(run_history, list):
        run_history = []
    run_history.append({
        "check_dates": [row["check_date"] for row in backtest_rows],
        "ranking": ranking,
        "best": best,
        "best_backtest_rows": backtest_rows,
    })
    data = {
        "model": "C1_v1_simple",
        "best": best,
        "ranking": ranking,
        "run_history": run_history[-30:],
        "fixed_params": {
            "groups": GROUPS,
            "prize_option": PRIZE_OPTION,
            "match_count": MATCH_COUNT,
            "match_mode": MATCH_MODE,
            "group_quota_list": GROUP_QUOTA_LIST,
            "pair_hit_weight": PAIR_HIT_WEIGHT,
            "num_hit_weight": NUM_HIT_WEIGHT,
            "prize_weight": PRIZE_WEIGHT,
            "recency_weights": RECENCY_WEIGHTS,
            "score_weights": SCORE_WEIGHTS,
        },
    }
    JSON_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_best_params() -> dict[str, object]:
    if not JSON_PATH.exists():
        return {}
    try:
        data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    best = data.get("best", {}) if isinstance(data, dict) else {}
    return best if isinstance(best, dict) else {}


def predict_next(draws: list[DrawRow], best: dict[str, object]) -> dict[str, list[int]]:
    window_count = to_int(best.get("window_draw_count"), WINDOW_DRAW_COUNT_LIST[0])
    top_prize_count = to_int(best.get("top_prize_draw_count"), TOP_PRIZE_DRAW_COUNT_LIST[0])
    quota_raw = best.get("group_quota", GROUP_QUOTA_LIST[0])
    quota_tuple = tuple(to_int(num, 3) for num in quota_raw) if isinstance(quota_raw, list) else GROUP_QUOTA_LIST[0]
    if len(quota_tuple) != len(GROUPS):
        quota_tuple = GROUP_QUOTA_LIST[0]
    quotas = quota_to_map(quota_tuple)  # type: ignore[arg-type]
    target_index = len(draws)
    predictions: dict[str, list[int]] = {}
    for group_id in GROUPS:
        samples = build_window_samples(draws, target_index, group_id, window_count)
        predictions[group_name(group_id)] = build_group_prediction(
            samples,
            group_id,
            top_prize_count,
            quotas[group_id],
        )
    return predictions


def save_nextdraw_pred_csv(bet_date: str, predictions: dict[str, list[int]]) -> None:
    BET_DATA_DIR.mkdir(parents=True, exist_ok=True)
    with NEXTDRAW_PRED_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["bet_date", "1-9", "10-20", "21-31"])
        writer.writeheader()
        writer.writerow(
            {
                "bet_date": bet_date,
                "1-9": format_nums(predictions.get("1-9", [])),
                "10-20": format_nums(predictions.get("10-20", [])),
                "21-31": format_nums(predictions.get("21-31", [])),
            }
        )


def save_backtest_check_csv(backtest_rows: list[BacktestRow]) -> None:
    BET_DATA_DIR.mkdir(parents=True, exist_ok=True)
    with BACKTEST_CHECK_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "1-9", "10-20", "21-31", "hit_nums", "special_hit", "hit_score"])
        writer.writeheader()
        for row in backtest_rows:
            writer.writerow(
                {
                    "date": row["check_date"],
                    "1-9": format_nums(row["predictions"].get("1-9", [])),
                    "10-20": format_nums(row["predictions"].get("10-20", [])),
                    "21-31": format_nums(row["predictions"].get("21-31", [])),
                    "hit_nums": format_nums(row["hit_nums"]),
                    "special_hit": row["special_hit"] or "",
                    "hit_score": f"{row['hit_score']:g}",
                }
            )


def print_backtest_setting() -> None:
    print("====== C1_v1 簡化回測設定 ======")
    print(f"回測期列表：{BACKTEST_DRAW_COUNT_LIST}")
    print(f"窗口期列表：{WINDOW_DRAW_COUNT_LIST}")
    print(f"3獎注數前N期列表：{TOP_PRIZE_DRAW_COUNT_LIST}")
    print(f"配額列表：{[format_quota(quota) for quota in GROUP_QUOTA_LIST]}")
    print("分組：1-9 / 10-20 / 21-31，系統自動比較配額")
    print(f"取樣條件：每組生日號 {MATCH_MODE}{MATCH_COUNT} 球，按 prize{PRIZE_OPTION} 中獎注數排序")
    print()


def print_ranking(ranking: list[dict[str, object]]) -> None:
    print("====== C1_v1 多期回測參數比較 ======")
    print("排名 | 回測期 | 窗口期 | prize前N | 配額 | 5+ | 4+ | 3+ | 分數")
    for rank, item in enumerate(ranking, start=1):
        print(
            f"{rank:>2} | "
            f"{to_int(item.get('backtest_draw_count')):>4} | "
            f"{to_int(item.get('window_draw_count')):>4} | "
            f"{to_int(item.get('top_prize_draw_count')):>7} | "
            f"{str(item.get('group_quota_text', '')):>5} | "
            f"{to_int(item.get('hit_5_plus_count')):>2} | "
            f"{to_int(item.get('hit_4_plus_count')):>2} | "
            f"{to_int(item.get('hit_3_plus_count')):>2} | "
            f"{to_float(item.get('score')):>5g}"
        )
    print()


def print_backtest_summary(backtest_rows: list[BacktestRow]) -> None:
    print("====== C1_v1 多期回測預測核對總結 ======")
    for row in backtest_rows:
        prediction_text = "，".join(
            format_nums(row["predictions"].get(name, []))
            for name in ["1-9", "10-20", "21-31"]
        )
        hit_text = format_nums(row["hit_nums"])
        special_text = f" + 特號[{row['special_hit']}]" if row["special_hit"] is not None else ""
        prize_text = f" / {row['prize_level']}" if row["prize_level"] != "未中獎" else ""
        print(
            f"近 {row['rank']}期：核對：{row['check_date']}，"
            f"{prediction_text}，命中{hit_text}{special_text} /> "
            f"{row['hit_score']:g} 球{prize_text}"
        )
    print()


def print_prediction(bet_date: str, predictions: dict[str, list[int]], best: dict[str, object]) -> None:
    candidate_pool = sorted({num for nums in predictions.values() for num in nums})
    print("====== C1_v1 下期預測 ======")
    print(
        f"已讀入最佳參數：回測期 {to_int(best.get('backtest_draw_count'))}，"
        f"窗口期 {to_int(best.get('window_draw_count'))}，"
        f"prize前 {to_int(best.get('top_prize_draw_count'))} 期，"
        f"配額 {best.get('group_quota_text', '')}，"
        f"分數 {to_float(best.get('score')):g}"
    )
    for name in ["1-9", "10-20", "21-31"]:
        nums = predictions.get(name, [])
        print(f"{name}: {format_nums(nums)} /> {len(nums)} 球")
    print(f"9球候選池：{','.join(str(num) for num in candidate_pool)}")
    for line in format_rbg_lines(candidate_pool):
        print(line)
    print(
        f"下期開獎日期：{bet_date}，預測 "
        f"{format_nums(predictions.get('1-9', []))},"
        f"{format_nums(predictions.get('10-20', []))},"
        f"{format_nums(predictions.get('21-31', []))}"
    )


def main() -> None:
    draws = read_draws()
    if not draws:
        raise FileNotFoundError(f"找不到或未能讀取 M6：{M6_CSV}")

    print_backtest_setting()
    best, ranking, best_rows = run_auto_backtest(draws)
    save_json(best, ranking, best_rows)
    save_backtest_check_csv(best_rows)
    print_ranking(ranking)
    print(
        f"最佳組合：回測期 {to_int(best.get('backtest_draw_count'))}，"
        f"窗口期 {to_int(best.get('window_draw_count'))}，"
        f"prize前 {to_int(best.get('top_prize_draw_count'))} 期，"
        f"配額 {best.get('group_quota_text', '')}，"
        f"5球以上 {to_int(best.get('hit_5_or_above'))} 期，"
        f"4球以上 {to_int(best.get('hit_4_or_above'))} 期，"
        f"3球以上 {to_int(best.get('hit_3_or_above'))} 期，"
        f"分數 {to_float(best.get('score')):g}"
    )
    print()
    print_backtest_summary(best_rows)

    best_params = load_best_params()
    predictions = predict_next(draws, best_params)
    bet_date = read_next_draw_date()
    print_prediction(bet_date, predictions, best_params)
    save_nextdraw_pred_csv(bet_date, predictions)


if __name__ == "__main__":
    main()
