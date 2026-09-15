from pathlib import Path
import csv
import itertools
import json
from typing import TypedDict

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent

# 資料來源：
# M6 讀取歷史開獎與派彩資料；M4 讀取下一期開獎日期。
M6_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"
M4_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M4_lotto_prize_summary.csv"
JSON_PATH = CURRENT_DIR / "json_data" / "G1_v1_best_params.json"
COLD_REBOUND_JSON_PATH = CURRENT_DIR / "json_data" / "G1_v1_cold_rebound_best.json"

# G1_v1 獨立測試 10-20 分組，不依賴 F5 系列設定。
GROUP_LABEL = "10-20"
BIRTHDAY_NUM_MIN = 10
BIRTHDAY_NUM_MAX = 20

# G1_v1 自動比較的簡化參數。
BACKTEST_DRAW_COUNT_LIST = [10] # 回測期 
WINDOW_DRAW_COUNT_LIST = [12,18,24] # 窗口期：每期核對前即時計算 12 / 18 / 24 期
AFTER_NONE_HIT_RATE_THRESHOLD_LIST = [0.50, 0.60, 0.65]
PREDICT_PAIR_COUNT = 2 # 最多選 2 組雙球，合併後通常是 3-4 球
RECENT_DRAW_COUNT = 5
COLD_WARN_GAP = 12 #預設初步 冷號未開期 。
DEEP_COLD_WARN_GAP = 18 # 預設 深度冷號期。
DETAIL_DISPLAY_MODE = "detail"  # "detail" 顯示完整分析；"simple" 顯示簡單核對。
LOW_SIGNAL_PREDICT_COUNT = 2 # 弱訊號時只發 2 球，減少 10-20 配額消耗
NORMAL_SIGNAL_PREDICT_COUNT = 3 # 正常訊號時發 3 球
STRONG_SIGNAL_PREDICT_COUNT = 4 # 強訊號時最多發 4 球

# 固定策略參數：寫入 JSON，供下一期預測讀取。
COMBINATION_TAKE_COUNT = 2
MAX_PREVIOUS_DRAW_OVERLAP = 1
PAIR_HIT_WEIGHT = 10.0
RECENCY_PAIR_WEIGHT = 3.0
COLD_NUM_WEIGHT = 1.5


# 單一期開獎資料：N1-N6 存入 nums，N7 特號存入 special。
class DrawRow(TypedDict):
    date: str
    nums: list[int]
    special: int | None


# 每一期回測保存的資料：
# 包括窗口期、預測組合、核對命中、冷號命中、(00) 連續率及決策原因。
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
    predict_num_count: int
    allocation_reason: str
    cold_gap_used: int
    after_none_rate: float
    after_none_threshold: float
    pair_score_text: str


# 配額判斷結果：決定本期不發球、少發球、正常發球或強發球。
class AllocationDecision(TypedDict):
    prediction_mode: str
    predict_num_count: int
    reason: str


def to_float(value: object, default: float = 0.0) -> float:
    if not isinstance(value, (int, float, str)):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# 安全轉整數：CSV/JSON 有空白或異常文字時，用 default 保護流程。
def to_int(value: object, default: int = 0) -> int:
    if not isinstance(value, (int, float, str)):
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


# 讀 CSV 並清理欄位名稱及空白，避免資料檔有 BOM 或空格造成讀取錯誤。
def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"找不到 CSV：{path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [{(key or "").strip(): (value or "").strip() for key, value in row.items()} for row in reader]


# 從 M6 建立開獎列表，日期由舊至新排列，方便用 index 做回測窗口。
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
    """讀取 G1_v1_cold_rebound.py 產生的最佳冷號門檻。"""

    if not COLD_REBOUND_JSON_PATH.exists():
        return {}
    try:
        data = json.loads(COLD_REBOUND_JSON_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    group = data.get("analysis_group", {})
    if not isinstance(group, dict) or group.get("key") != "10_20":
        return {}
    best = data.get("best", {})
    return best if isinstance(best, dict) else {}


# 只用於預測顯示下一期日期，不參與回測命中計算。
def read_next_draw_date() -> str:
    rows = read_csv_rows(M4_CSV)
    return rows[-1].get("next_draw_date", "") if rows else ""


# 取 N1-N6 加 N7 特號；本系列統計將特號視為一球。
def all_draw_nums(row: DrawRow) -> set[int]:
    nums = {num for num in row["nums"] if 1 <= num <= 49}
    if row["special"] is not None:
        nums.add(row["special"])
    return nums


# 取出目前分組號碼。G1 固定為 10-20。
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


def is_ball_prediction(row: BacktestRow) -> bool:
    return row["prediction_mode"] != "不發球"


# 統計窗口期內 10-20 的開號形態：
# none=(00)，single=只開 1 球，multi=開 2 球或以上。
def count_categories(rows: list[DrawRow]) -> dict[str, int]:
    counts = {"none": 0, "single": 0, "multi": 0}
    for row in rows:
        count = len(birthday_nums(row))
        counts["none" if count == 0 else "single" if count == 1 else "multi"] += 1
    return counts


# 冷號：最近 gap 期內完全沒有在 N1-N7 出現的 10-20 號碼。
def cold_numbers(rows: list[DrawRow], gap: int) -> set[int]:
    appeared = {num for row in rows[-gap:] for num in birthday_nums(row)}
    return set(range(BIRTHDAY_NUM_MIN, BIRTHDAY_NUM_MAX + 1)) - appeared


def best_cold_gap() -> int:
    best = load_cold_rebound_best()
    gap = to_int(best.get("cold_gap"), COLD_WARN_GAP)
    return gap if gap > 0 else COLD_WARN_GAP


# 雙球組合評分：
# 出現次數是主分，越近期出現加少量分，冷號再加少量補位分。
def pair_scores(rows: list[DrawRow], cold_gap: int) -> dict[tuple[int, int], float]:
    scores = {pair: 0.0 for pair in itertools.combinations(range(BIRTHDAY_NUM_MIN, BIRTHDAY_NUM_MAX + 1), 2)}
    total = len(rows)
    cold = cold_numbers(rows, cold_gap)
    for index, row in enumerate(rows):
        nums = sorted(birthday_nums(row))
        recency = (index + 1) / total if total else 0.0
        for pair in itertools.combinations(nums, 2):
            scores[pair] += PAIR_HIT_WEIGHT + RECENCY_PAIR_WEIGHT * recency
    for pair in scores:
        scores[pair] += COLD_NUM_WEIGHT * sum(num in cold for num in pair)
    return scores


# 顯示已選 pair 的分數，方便 detail 模式檢查為什麼選出該組合。
def format_pair_score_text(
    pairs: list[tuple[int, int]],
    scores: dict[tuple[int, int], float],
) -> str:
    if not pairs:
        return "-"
    return "，".join(f"({left},{right})={scores.get((left, right), 0.0):.2f}" for left, right in pairs)


# (00) 連續率：
# 在窗口內找出「上一期沒有 10-20」後，下一期仍然沒有 10-20 的比例。
def after_none_rate(draws: list[DrawRow], check_index: int, window_count: int) -> float:
    history = draws[max(0, check_index - window_count - 1):check_index]
    none_count = 0
    continued_none_count = 0
    for previous, following in zip(history, history[1:]):
        if not birthday_nums(previous):
            none_count += 1
            continued_none_count += not birthday_nums(following)
    return continued_none_count / none_count if none_count else 0.0


# 每期獨立決定配額：
# 1. 上一期是 (00)，用 (00) 連續率決定不發球或少發球；
# 2. 上一期只開 1 球，少發球；
# 3. 最近 5 期多次出現 2球+，強發球；
# 4. 其他情況正常發球。
def decide_1_9_allocation(
    draws: list[DrawRow],
    check_index: int,
    window_count: int,
    after_none_threshold: float,
) -> AllocationDecision:
    window_rows = draws[check_index - window_count:check_index]
    previous_nums = birthday_nums(draws[check_index - 1])
    categories = count_categories(window_rows)
    recent_multi_count = sum(len(birthday_nums(row)) >= 2 for row in window_rows[-RECENT_DRAW_COUNT:])
    if not previous_nums:
        rate = after_none_rate(draws, check_index, window_count)
        if rate >= after_none_threshold:
            return {
                "prediction_mode": "不發球",
                "predict_num_count": 0,
                "reason": f"上一期(00)，上下期(00)連續率 {rate:.0%} >= 門檻 {after_none_threshold:.0%}",
            }
        return {
            "prediction_mode": "少發球",
            "predict_num_count": LOW_SIGNAL_PREDICT_COUNT,
            "reason": f"上一期(00)，上下期(00)連續率 {rate:.0%} < 門檻 {after_none_threshold:.0%}",
        }
    if len(previous_nums) == 1:
        return {
            "prediction_mode": "少發球",
            "predict_num_count": LOW_SIGNAL_PREDICT_COUNT,
            "reason": f"上一期只開 1 球，先減少 {GROUP_LABEL} 發球",
        }
    if recent_multi_count >= 3 and categories["multi"] >= categories["none"]:
        return {
            "prediction_mode": "強發球",
            "predict_num_count": STRONG_SIGNAL_PREDICT_COUNT,
            "reason": f"最近 {RECENT_DRAW_COUNT} 期有 {recent_multi_count} 期 2球+",
        }
    return {
        "prediction_mode": "正常發球",
        "predict_num_count": NORMAL_SIGNAL_PREDICT_COUNT,
        "reason": f"近期有 {GROUP_LABEL}，按正常配額發球",
    }


# 根據窗口 pair 分數選出最多 PREDICT_PAIR_COUNT 組雙球。
# 同時限制與上一期開號重複太多，避免短期重複過重。
def select_pairs(window_rows: list[DrawRow], predict_num_count: int, cold_gap: int) -> list[tuple[int, int]]:
    if predict_num_count <= 0:
        return []
    previous_nums = birthday_nums(window_rows[-1]) if window_rows else set()
    ranked = sorted(pair_scores(window_rows, cold_gap).items(), key=lambda item: (-item[1], item[0]))
    selected: list[tuple[int, int]] = []
    selected_nums: set[int] = set()
    for pair, _ in ranked:
        if len(set(pair) & previous_nums) > MAX_PREVIOUS_DRAW_OVERLAP:
            continue
        if pair in selected:
            continue
        selected.append(pair)
        selected_nums.update(pair)
        if len(selected) >= PREDICT_PAIR_COUNT or len(selected_nums) >= predict_num_count:
            break
    return selected


# 單組參數回測：
# 每一期只使用核對期之前的 window_rows 產生預測，再用核對期開獎檢查命中。
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
    cold_gap = best_cold_gap()
    for check_index in range(first_check_index, len(draws)):
        window_rows = draws[check_index - window_count:check_index]
        decision = decide_1_9_allocation(
            draws, check_index, window_count, after_none_threshold
        )
        prediction_mode = decision["prediction_mode"]
        pairs = select_pairs(window_rows, decision["predict_num_count"], cold_gap)
        pair_score_text = format_pair_score_text(pairs, pair_scores(window_rows, cold_gap))
        candidates = sorted({num for pair in pairs for num in pair})
        backtest_row = window_rows[-1]
        check_row = draws[check_index]
        actual_nums = birthday_nums(check_row)
        window_cold_nums = cold_numbers(window_rows, cold_gap)
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
        allocation_correct = bool(actual_nums) if prediction_mode != "不發球" else not actual_nums
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
            "predict_num_count": decision["predict_num_count"],
            "allocation_reason": decision["reason"],
            "cold_gap_used": cold_gap,
            "after_none_rate": after_none_rate(draws, check_index, window_count),
            "after_none_threshold": after_none_threshold,
            "pair_score_text": pair_score_text,
        })
    return results


# 匯總單組參數回測結果，計算命中率、(00) 命中率和排序分數。
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
        is_ball_prediction(row) and row["actual_1_9_count"] > 0 and row["hit_count"] >= 1
        for row in rows
    )
    hit_2_plus_count = sum(
        is_ball_prediction(row) and row["actual_1_9_count"] > 0 and row["hit_count"] >= 2
        for row in rows
    )
    hit_3_plus_count = sum(
        is_ball_prediction(row) and row["actual_1_9_count"] > 0 and row["hit_count"] >= 3
        for row in rows
    )
    correct_no_prediction_count = sum(
        row["prediction_mode"] == "不發球" and row["allocation_correct"] for row in rows
    )
    missed_no_prediction_count = sum(
        row["prediction_mode"] == "不發球" and not row["allocation_correct"] for row in rows
    )
    incorrect_prediction_count = sum(
        is_ball_prediction(row) and not row["allocation_correct"] for row in rows
    )
    # 分數只用作不同參數排序：
    # 重視 3+ / 2+ 命中；正確不發球加分；錯失不發球或發球方向錯誤扣分。
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
        "cold_gap_used": rows[0]["cold_gap_used"] if rows else best_cold_gap(),
        "predict_pair_count": PREDICT_PAIR_COUNT,
    }


# 排序規則：先看高命中率，再看 (00) 命中與整體分數。
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


# 多參數回測比較：目前比較回測期、窗口期、(00) 連續率門檻。
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


# 固定權重集中寫入 JSON，方便之後回看當時用什麼策略參數。
def fixed_weights() -> dict[str, object]:
    return {
        "pair_hit_weight": PAIR_HIT_WEIGHT,
        "recency_pair_weight": RECENCY_PAIR_WEIGHT,
        "cold_num_weight": COLD_NUM_WEIGHT,
        "max_previous_draw_overlap": MAX_PREVIOUS_DRAW_OVERLAP,
        "predict_pair_count": PREDICT_PAIR_COUNT,
        "low_signal_predict_count": LOW_SIGNAL_PREDICT_COUNT,
        "normal_signal_predict_count": NORMAL_SIGNAL_PREDICT_COUNT,
        "strong_signal_predict_count": STRONG_SIGNAL_PREDICT_COUNT,
        "recent_draw_count": RECENT_DRAW_COUNT,
        "cold_warn_gap": COLD_WARN_GAP,
        "deep_cold_warn_gap": DEEP_COLD_WARN_GAP,
        "cold_gap_used": best_cold_gap(),
        "after_none_hit_rate_threshold_list": AFTER_NONE_HIT_RATE_THRESHOLD_LIST,
    }


# 將最佳參數、排名、逐期回測、所有參數明細及下一期預測寫入 JSON。
def save_json(
    best: dict[str, object],
    ranking: list[dict[str, object]],
    rows: list[BacktestRow],
    all_details: dict[str, list[BacktestRow]],
    next_pairs: list[tuple[int, int]],
) -> None:
    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "model": "G1_v1_10_20_allocation_strategy",
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


# 打印多參數比較表。
def print_ranking(ranking: list[dict[str, object]]) -> None:
    print(f"====== G1_v1 [{GROUP_LABEL}] 號，參數比較（本次回測） ======")
    print("回測期 | 窗口期 | 冷期 | pair | (00)門檻 | 有號期 | 命中3+ | 命中2+ | 命中1+ | 00期 | 命中00 | 錯失00 | 分數")
    for item in ranking:
        print(
            f"{to_int(item['backtest_draw_count']):>6} | {to_int(item['window_draw_count']):>6} | "
            f"{to_int(item['cold_gap_used']):>4} | {to_int(item['predict_pair_count']):>4} | "
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


# detail 模式：每期顯示完整窗口分類、冷號、最近 5 期、pair 分及命中。
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
            f"(00) 上下期連續率：{row['after_none_rate']:.0%} / 預設門檻 {row['after_none_threshold']:.0%}"
        )
        print(
            f"{row['cold_gap_used']} 期冷號：{format_nums(row['window_cold_nums'])}，"
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
            print(f"配額判斷：不發球，pair分：{row['pair_score_text']}")
            print(f"原因：{row['allocation_reason']}")
            print(
                f"預測：None（不發球），{GROUP_LABEL} 開獎 {format_nums(row['actual_1_9_nums'])} "
                f"{row['actual_1_9_count']} 球，{result}，{score_text}"
            )
        else:
            print(
                f"配額判斷：{row['prediction_mode']}，目標 {row['predict_num_count']} 球，"
                f"pair分：{row['pair_score_text']}"
            )
            print(f"原因：{row['allocation_reason']}")
            print(f"預測：{format_pairs(row['predictions'])} -> {format_nums(row['candidate_nums'])}")
            print(f"核對命中：{format_nums(row['hit_nums'])} / {row['hit_count']} 球")
    print("------------------------------------------------------------")
    print()


# simple 模式：每期只顯示一行。
# 發球期顯示預測與命中；不發球期顯示 (00) 命中 Y/N。
def print_simple_view(rows: list[BacktestRow], best: dict[str, object]) -> None:
    print("====== 最佳參數逐期核對 ======")
    print(
        f"最佳參數：回測期 {to_int(best.get('backtest_draw_count'))}，"
        f"窗口期 {to_int(best.get('window_draw_count'))}，"
        f"(00) 連續率 {to_float(best.get('after_none_threshold')):.0%}"
    )
    total_rows = len(rows)
    for display_index, row in enumerate(rows, start=1):
        near_index = total_rows - display_index + 1
        actual_text = format_nums(row["actual_1_9_nums"]) if row["actual_1_9_count"] else "(00)"
        none_hit_flag = "Y" if row["prediction_mode"] == "不發球" and row["actual_1_9_count"] == 0 else "N"
        if row["prediction_mode"] == "不發球":
            hit_text = "" if row["actual_1_9_count"] == 0 else f" = {row['actual_1_9_count']} 球"
            print(
                f"/> {near_index}，核對期：{row['check_date']}，(00) 不發球，"
                f"開獎 {actual_text}，命中 [{none_hit_flag}]{hit_text}"
            )
        else:
            print(
                f"/> {near_index}，核對期：{row['check_date']}，{row['prediction_mode']} "
                f"{row['predict_num_count']} 球，預測：{format_pairs(row['predictions'])} "
                f"-> {format_nums(row['candidate_nums'])}，"
                f"開獎 {actual_text}，命中 {format_nums(row['hit_nums'])} / {row['hit_count']} 球"
            )
    print()


def print_detail(rows: list[BacktestRow], best: dict[str, object]) -> None:
    if DETAIL_DISPLAY_MODE == "simple":
        print_simple_view(rows, best)
        return
    print_detail_view(rows, best)


# 回測結果總結：
# 發球命中率只計真實有 10-20 的期數；(00) 不發球命中獨立統計。
def print_backtest_result(rows: list[BacktestRow]) -> None:
    actual_none = [row for row in rows if row["actual_1_9_count"] == 0]
    actual_one = [row for row in rows if row["actual_1_9_count"] == 1]
    actual_two = [row for row in rows if row["actual_1_9_count"] == 2]
    actual_three_plus = [row for row in rows if row["actual_1_9_count"] >= 3]
    actual_has_nums = [row for row in rows if row["actual_1_9_count"] > 0]
    hit_1_plus = sum(
        is_ball_prediction(row) and row["actual_1_9_count"] > 0 and row["hit_count"] >= 1
        for row in rows
    )
    hit_2_plus = sum(
        is_ball_prediction(row) and row["actual_1_9_count"] > 0 and row["hit_count"] >= 2
        for row in rows
    )
    hit_3_plus = sum(
        is_ball_prediction(row) and row["actual_1_9_count"] > 0 and row["hit_count"] >= 3
        for row in rows
    )
    zero_hit_with_nums = sum(
        is_ball_prediction(row) and row["actual_1_9_count"] > 0 and row["hit_count"] == 0
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

    print(f"====== G1_v1 [{GROUP_LABEL}] 回測結果檢測 ======")
    print("------------------------------------------")
    print(f"回測期檢測：{len(rows)} 期")
    print(f"實際 (00)：{len(actual_none)} 期")
    print(f"實際 == 1 球：{len(actual_one)} 期")
    print(f"實際 == 2 球：{len(actual_two)} 期")
    print(f"實際 >= 3 球：{len(actual_three_plus)} 期")
    print(f"實際有 {GROUP_LABEL} 號：{len(actual_has_nums)} 期")
    print("------------------------------------------")
    print(f"發球命中率只計：真實有 {GROUP_LABEL} 號的期數。")
    print(
        f"命中 >= 1 球：{hit_1_plus} 期 / 真實有 {GROUP_LABEL}：{len(actual_has_nums)} 期，"
        f"{hit_1_plus / len(actual_has_nums):.2%}" if actual_has_nums else f"命中 >= 1 球：0 期 / 真實有 {GROUP_LABEL}：0 期"
    )
    print(
        f"命中 >= 2 球：{hit_2_plus} 期 / 真實有 {GROUP_LABEL}：{len(actual_has_nums)} 期，"
        f"{hit_2_plus / len(actual_has_nums):.2%}" if actual_has_nums else f"命中 >= 2 球：0 期 / 真實有 {GROUP_LABEL}：0 期"
    )
    print(
        f"命中 >= 3 球：{hit_3_plus} 期 / 真實有 {GROUP_LABEL}：{len(actual_has_nums)} 期，"
        f"{hit_3_plus / len(actual_has_nums):.2%}" if actual_has_nums else f"命中 >= 3 球：0 期 / 真實有 {GROUP_LABEL}：0 期"
    )
    print(f"有 {GROUP_LABEL} 但發球不中：{zero_hit_with_nums} 期 / 真實有 {GROUP_LABEL}：{len(actual_has_nums)} 期")
    print("------------------------------------------")
    print(
        f"命中 (00)：{correct_no_prediction} 期 / 實際 (00)：{len(actual_none)} 期，"
        f"{correct_no_prediction / len(actual_none):.2%}" if actual_none else "命中 (00)：0 期 / 實際 (00)：0 期"
    )
    print(f"預測 (00) 失敗：{missed_no_prediction} 期 / 實際有 {GROUP_LABEL} 號：{len(actual_has_nums)} 期")
    print("------------------------------------------")
    print(f"冷號預測期數：{len(cold_prediction_rows)} 期")
    print(f"冷號預測成功：{len(cold_success_rows)} 期 / 冷號預測期數：{len(cold_prediction_rows)} 期")
    print(f"冷號預測失敗：{len(cold_failed_rows)} 期 / 冷號預測期數：{len(cold_prediction_rows)} 期")
    print(f"合共：{len(rows)} 期")
    print("------------------------------------------")
    print()


# 真正預測下一期：窗口包含最新開獎期，只輸出下期候選，不核對。
def print_next_prediction(draws: list[DrawRow], best: dict[str, object]) -> list[tuple[int, int]]:
    window_count = to_int(best.get("window_draw_count"), WINDOW_DRAW_COUNT_LIST[0])
    threshold = to_float(best.get("after_none_threshold"), AFTER_NONE_HIT_RATE_THRESHOLD_LIST[0])
    window_rows = draws[-window_count:]
    cold_gap = best_cold_gap()
    decision = decide_1_9_allocation(draws, len(draws), window_count, threshold)
    pairs = select_pairs(window_rows, decision["predict_num_count"], cold_gap)
    candidates = sorted({num for pair in pairs for num in pair})
    categories = count_categories(window_rows)
    latest_row = draws[-1]
    cold_nums = cold_numbers(window_rows, cold_gap)
    deep_cold_nums = cold_numbers(draws, DEEP_COLD_WARN_GAP)

    print(f"====== G1_v1 [{GROUP_LABEL}] 下期預測 ======")
    print(
        f"最佳參數：回測期 {to_int(best.get('backtest_draw_count'))}，"
        f"窗口期 {window_count}，(00) 門檻 {threshold:.0%}，冷號門檻 {cold_gap} 期"
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
        f"{cold_gap} 期冷號：{format_nums(sorted(cold_nums))}，"
        f"{DEEP_COLD_WARN_GAP} 期很冷號：{format_nums(sorted(deep_cold_nums))}"
    )
    print("------------------------------------------")
    for offset, row in enumerate(window_rows[-RECENT_DRAW_COUNT:], start=1):
        near_index = len(window_rows[-RECENT_DRAW_COUNT:]) - offset + 1
        numbers = sorted(birthday_nums(row))
        count_text = "None" if not numbers else f"{len(numbers)} 球"
        print(f"最近 {near_index} 期：{row['date']}，{format_nums(numbers)} = {count_text}")
    print("------------------------------------------")
    print(f"配額判斷：{decision['prediction_mode']}，目標 {decision['predict_num_count']} 球")
    print(f"原因：{decision['reason']}")
    if decision["prediction_mode"] == "不發球":
        print(f"預測：None（不發球，保留 {GROUP_LABEL} 配額）")
    else:
        print(f"預測雙球：{format_pairs(pairs)}")
        print(f"合併候選球：{format_nums(candidates)}")
    print("============== 完結 ==============")
    return pairs


# 主流程：讀資料 -> 多參數回測 -> 打印最佳明細 -> 輸出下期預測 -> 寫 JSON。
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
