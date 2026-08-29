from pathlib import Path
import csv
import json
from typing import TypedDict

"""
A1_v2_brithday_group_quota_pred：
用 12 / 6 / 3 期分組趨勢，產生 1-9、10-20、21-31 動態配額預測。
同時回測固定 3+3+3 與動態 2/3/4 配額，核對下一期 N1-N6 正號及 N7 特號。
"""


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
M6_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"
M4_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M4_lotto_prize_summary.csv"
BET_DATA_DIR = CURRENT_DIR / "bet_prize_data"
JSON_DATA_DIR = CURRENT_DIR / "json_data"
BET_RECORDS_CSV = BET_DATA_DIR / "bet_records.csv"
NEXT_BET_CSV = BET_DATA_DIR / "nextBetDraw_record.csv"
WIN_RESULTS_CSV = BET_DATA_DIR / "win_results.csv"
BACKTEST_SCORE_JSON = JSON_DATA_DIR / "A1_v2_backtest_score.json"

# ---- 回測 / 預測模式
RUN_MODE = "predict"  # 可選："backtest" 重建回測CSV；"predict" 更新下期預測及追加投注記錄
BACKTEST_DRAW_COUNT = 20  # 回測最近多少期
'''
比較穩的範圍：最高權重：10
[(12, 2), (6, 3), (2, 5)]
[(12, 3), (6, 4), (2, 5)]
[(12, 1), (6, 3), (2, 6)]
[(14, 3), (7, 4), (3, 5)]
'''
TREND_PERIOD_WEIGHTS = [(14, 3), (7, 4), (3, 5)]  # 分組趨勢期數及權重（1-10)  ：越近期權重越高
TREND_PERIODS = [period for period, _weight in TREND_PERIOD_WEIGHTS]
PERIOD_WEIGHTS = dict(TREND_PERIOD_WEIGHTS)
PRINT_GROUP_OPTIONS = [1, 2, 3]  # 分組：1=1-9，2=10-20，3=21-31
TOTAL_PREDICT_NUM_COUNT = 9  # 三組合共預測球數，標準 9 球
SHOW_DETAIL_COUNT = 20  # 顯示最近多少期回測明細；0 = 不顯示
SAVE_BET_CSV = True  # 可選：True 將 A1_v2 回測及下期預測寫入 bet_prize_data
HIGH_JACKPOT_FUND = 20_000_000  # 下期估計頭獎達到此金額，多加一注 2組+3組

# ---- 權重參數
SPECIAL_NUM_WEIGHT = 2  # 特號只作輔助加分，不壓過正號
ZERO_PENALTY_WEIGHT = 2  # 分組 0 球期數扣分
LOW_PRIZE_PENALTY_WEIGHT = 1  # 低人氣輕微扣分，初版保守

# ---- 單式投注組合參數
BASE_BET_GROUP_PAIRS = [(1, 2), (1, 3)]  # 平時投注：1組+2組、1組+3組
EXTRA_JACKPOT_GROUP_PAIR = (2, 3)  # 頭獎金較多時加注：2組+3組


BIRTHDAY_GROUPS: dict[int, tuple[int, int]] = {
    1: (1, 9),
    2: (10, 20),
    3: (21, 31),
}


class GroupTrend(TypedDict):
    group_option: int
    group_range: str
    strength_score: float
    quota: int
    num_scores: dict[int, float]
    predicted_nums: list[int]


class BacktestResult(TypedDict):
    rank: int
    target_date: str
    check_date: str
    check_nums_1_31_slots: list[int | None]
    predictions: dict[int, list[int]]
    normal_hit_nums: list[int]
    special_hit_num: int | None
    hit_score: float
    bets: list[list[int]]


class NextDrawInfo(TypedDict):
    next_draw_date: str
    next_draw_prize_fund: float


HIT_LEVELS = [6, 5.5, 5, 4.5, 4, 3.5, 3, 2.5, 2, 1.5, 1, 0.5, 0]
MODEL_SCORE_WEIGHTS = {
    6: 80,
    5.5: 60,
    5: 45,
    4.5: 30,
    4: 20,
    3.5: 12,
    3: 8,
    2.5: 5,
    2: 3,
    1.5: 2,
    1: 1,
    0.5: 0.5,
    0: -2,
}


def birthday_range(group_option: int) -> tuple[int, int]:
    """取得生日號分組範圍。"""

    if group_option not in BIRTHDAY_GROUPS:
        raise ValueError("PRINT_GROUP_OPTIONS 只可選 1、2、3")
    return BIRTHDAY_GROUPS[group_option]


def validate_params() -> None:
    """檢查主要參數。"""

    if RUN_MODE not in {"backtest", "predict"}:
        raise ValueError('RUN_MODE 只可選 "backtest" 或 "predict"')
    if BACKTEST_DRAW_COUNT < 1:
        raise ValueError("BACKTEST_DRAW_COUNT 必須大於 0")
    if not TREND_PERIODS:
        raise ValueError("TREND_PERIODS 不可空白")
    for period_count in TREND_PERIODS:
        if period_count < 1:
            raise ValueError("TREND_PERIODS 內所有期數必須大於 0")
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
    """讀入一般 CSV，供檢查 bet_prize_data 現有檔案格式。"""

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


def read_next_draw_info(csv_path: Path = M4_CSV) -> NextDrawInfo:
    """從 M4 讀取最新一筆下期投注日期及估計頭獎。"""

    rows = read_csv_rows(csv_path)
    if not rows:
        return {"next_draw_date": "", "next_draw_prize_fund": 0.0}

    latest_row = rows[-1]
    try:
        prize_fund = float(latest_row.get("next_draw_prize_fund", "0") or 0)
    except ValueError:
        prize_fund = 0.0
    return {
        "next_draw_date": latest_row.get("next_draw_date", ""),
        "next_draw_prize_fund": prize_fund,
    }


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
    """抽取 prize3 中獎注數，暫作人氣參考。"""

    try:
        return float(row.get("prize3", "0") or 0)
    except ValueError:
        return 0.0


def selected_nums(nums: list[int], group_option: int) -> list[int]:
    """只保留指定分組範圍內的正號。"""

    start_num, end_num = birthday_range(group_option)
    return sorted(num for num in nums if start_num <= num <= end_num)


def get_window_rows(rows: list[dict[str, str]], target_index: int, period_count: int) -> list[dict[str, str]]:
    """取得核對期之前的趨勢窗口，不包含核對期。"""

    window_start = max(0, target_index - period_count)
    return rows[window_start:target_index]


def build_group_strength(rows: list[dict[str, str]], target_index: int, group_option: int) -> float:
    """計算分組強弱分，決定該組配額。"""

    score = 0.0
    for period_count in TREND_PERIODS:
        period_rows = get_window_rows(rows, target_index, period_count)
        weight = PERIOD_WEIGHTS.get(period_count, 1)
        for row in period_rows:
            hit_count = len(selected_nums(parse_nums(row), group_option))
            if hit_count == 0:
                score -= ZERO_PENALTY_WEIGHT * weight
            else:
                score += hit_count * weight
    return score


def build_group_num_scores(
    rows: list[dict[str, str]],
    target_index: int,
    group_option: int,
) -> dict[int, float]:
    """計算分組內每個號碼分數，用作選球。"""

    start_num, end_num = birthday_range(group_option)
    scores = {num: 0.0 for num in range(start_num, end_num + 1)}

    for period_count in TREND_PERIODS:
        period_rows = get_window_rows(rows, target_index, period_count)
        weight = PERIOD_WEIGHTS.get(period_count, 1)
        prize_values = sorted(parse_prize3(row) for row in period_rows)
        low_prize_line = prize_values[len(prize_values) // 3] if prize_values else 0

        for row in period_rows:
            nums = selected_nums(parse_nums(row), group_option)
            prize3 = parse_prize3(row)
            for num in nums:
                scores[num] += weight
                if prize3 <= low_prize_line:
                    scores[num] -= LOW_PRIZE_PENALTY_WEIGHT

            special_num = parse_special_num(row)
            if special_num is not None and start_num <= special_num <= end_num:
                scores[special_num] += SPECIAL_NUM_WEIGHT

    return scores


def allocate_dynamic_quotas(group_scores: dict[int, float]) -> dict[int, int]:
    """按分組強弱分分配 9 球配額，三組基本為 2/3/4。"""

    active_groups = list(PRINT_GROUP_OPTIONS)
    quotas = {group_option: 3 for group_option in active_groups}
    if len(active_groups) != 3 or TOTAL_PREDICT_NUM_COUNT != 9:
        return quotas

    sorted_groups = sorted(active_groups, key=lambda group: (-group_scores[group], group))
    quotas[sorted_groups[0]] = 4
    quotas[sorted_groups[1]] = 3
    quotas[sorted_groups[2]] = 2
    return quotas


def build_group_prediction(num_scores: dict[int, float], quota: int) -> list[int]:
    """按號碼分數取指定配額的預測號。"""

    ranked_nums = sorted(num_scores.items(), key=lambda item: (-item[1], item[0]))
    return sorted(num for num, _score in ranked_nums[:quota])


def build_predictions(
    rows: list[dict[str, str]],
    target_index: int,
    *,
    dynamic_quota: bool,
) -> dict[int, list[int]]:
    """產生固定或動態分組預測。"""

    group_scores = {
        group_option: build_group_strength(rows, target_index, group_option)
        for group_option in PRINT_GROUP_OPTIONS
    }
    quotas = allocate_dynamic_quotas(group_scores) if dynamic_quota else {
        group_option: 3 for group_option in PRINT_GROUP_OPTIONS
    }

    predictions: dict[int, list[int]] = {}
    for group_option in PRINT_GROUP_OPTIONS:
        num_scores = build_group_num_scores(rows, target_index, group_option)
        predictions[group_option] = build_group_prediction(num_scores, quotas[group_option])
    return predictions


def build_all_num_scores(rows: list[dict[str, str]], target_index: int) -> dict[int, float]:
    """合併三個分組的號碼分數，供單式注補號或截取排序。"""

    all_scores: dict[int, float] = {}
    for group_option in PRINT_GROUP_OPTIONS:
        group_scores = build_group_num_scores(rows, target_index, group_option)
        all_scores.update(group_scores)
    return all_scores


def normalize_bet_nums(nums: list[int], all_num_scores: dict[int, float]) -> list[int]:
    """將分組合併號碼修正為 6 個號碼，符合單式投注格式。"""

    unique_nums = sorted(set(nums))
    if len(unique_nums) > 6:
        ranked_nums = sorted(unique_nums, key=lambda num: (-all_num_scores.get(num, 0), num))
        return sorted(ranked_nums[:6])

    if len(unique_nums) < 6:
        ranked_candidates = sorted(all_num_scores.items(), key=lambda item: (-item[1], item[0]))
        for num, _score in ranked_candidates:
            if num not in unique_nums:
                unique_nums.append(num)
            if len(unique_nums) >= 6:
                break

    return sorted(unique_nums[:6])


def build_bet_lines(
    rows: list[dict[str, str]],
    target_index: int,
    predictions: dict[int, list[int]],
    *,
    include_extra_bet: bool,
) -> list[list[int]]:
    """由分組預測組成單式投注注項。"""

    group_pairs = list(BASE_BET_GROUP_PAIRS)
    if include_extra_bet:
        group_pairs.append(EXTRA_JACKPOT_GROUP_PAIR)

    all_num_scores = build_all_num_scores(rows, target_index)
    bet_lines: list[list[int]] = []
    for group_a, group_b in group_pairs:
        if group_a not in predictions or group_b not in predictions:
            continue
        bet_nums = normalize_bet_nums(
            predictions[group_a] + predictions[group_b],
            all_num_scores,
        )
        if bet_nums not in bet_lines:
            bet_lines.append(bet_nums)
    return bet_lines


def format_check_num_slots(nums: list[int | None]) -> str:
    """格式化核對號碼，32-49 顯示為空位。"""

    return ",".join(str(num) if num is not None else "-" for num in nums)


def format_hit_score(hit_score: float) -> str:
    """格式化命中球數。"""

    return f"{hit_score:g}"


def hit_score_key(hit_score: float) -> str:
    """JSON 統一用字串 key 儲存 3、3.5、4 等命中檔位。"""

    return format_hit_score(hit_score)


def get_hit_score(normal_hit_count: int, has_special_hit: bool) -> float:
    """中特號加 0.5 球，6 個正號時仍以 6 球計。"""

    if normal_hit_count >= 6:
        return 6.0
    return normal_hit_count + (0.5 if has_special_hit else 0.0)


def summarize_hits(results: list[BacktestResult]) -> dict[str, object]:
    """統計命中分佈及模型評分，供打印和 JSON 比較。"""

    total_count = len(results)
    distribution: dict[str, dict[str, float]] = {}
    score = 0.0
    for level in HIT_LEVELS:
        count = sum(1 for item in results if item["hit_score"] == level)
        rate = count / total_count * 100 if total_count else 0.0
        distribution[hit_score_key(level)] = {
            "count": count,
            "rate": round(rate, 2),
        }
        score += count * MODEL_SCORE_WEIGHTS[level]

    return {
        "total_count": total_count,
        "distribution": distribution,
        "score": round(score, 2),
        "hit_4_or_above": sum(1 for item in results if item["hit_score"] >= 4),
        "hit_3_or_above": sum(1 for item in results if item["hit_score"] >= 3),
        "hit_2_or_above": sum(1 for item in results if item["hit_score"] >= 2),
        "zero_count": sum(1 for item in results if item["hit_score"] == 0),
    }


def run_backtest(rows: list[dict[str, str]], *, dynamic_quota: bool) -> list[BacktestResult]:
    """執行多期回測。"""

    max_period = max(TREND_PERIODS)
    last_target_index = len(rows) - 2
    first_target_index = max(max_period, last_target_index - BACKTEST_DRAW_COUNT + 1)
    target_indices = list(range(first_target_index, last_target_index + 1))
    total_targets = len(target_indices)
    results: list[BacktestResult] = []

    for display_index, target_index in enumerate(target_indices, start=1):
        rank = total_targets - display_index + 1
        target_row = rows[target_index]
        check_row = rows[target_index + 1]
        check_nums = parse_nums(check_row)
        special_num = parse_special_num(check_row)
        predictions = build_predictions(rows, target_index, dynamic_quota=dynamic_quota)
        bets = build_bet_lines(rows, target_index, predictions, include_extra_bet=False)
        predicted_nums = {num for nums in predictions.values() for num in nums}
        normal_hit_nums = sorted(predicted_nums & set(check_nums))
        special_hit_num = special_num if special_num in predicted_nums else None
        hit_score = get_hit_score(len(normal_hit_nums), special_hit_num is not None)

        results.append(
            {
                "rank": rank,
                "target_date": target_row.get("nDdate", ""),
                "check_date": check_row.get("nDdate", ""),
                "check_nums_1_31_slots": [
                    *[num if 1 <= num <= 31 else None for num in sorted(check_nums)],
                    special_num if special_num is not None and 1 <= special_num <= 31 else None,
                ],
                "predictions": predictions,
                "normal_hit_nums": normal_hit_nums,
                "special_hit_num": special_hit_num,
                "hit_score": hit_score,
                "bets": bets,
            }
        )
    return results


def build_bet_records(results: list[BacktestResult]) -> list[dict[str, str]]:
    """將回測每期預測注項轉成 bet_records.csv 格式。"""

    records: list[dict[str, str]] = []
    for item in results:
        for bet_nums in item["bets"]:
            records.append(build_bet_record(item["check_date"], bet_nums))
    return records


def build_bet_record(bet_date: str, bet_nums: list[int]) -> dict[str, str]:
    """建立一行投注 CSV 記錄。"""

    padded_nums = [*bet_nums[:6], *([0] * max(0, 6 - len(bet_nums)))]
    record = {"bet_date": bet_date}
    for idx, num in enumerate(padded_nums[:6], start=1):
        record[f"N{idx}"] = str(num) if num else ""
    return record


def build_win_results(records: list[dict[str, str]], rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """核對投注記錄，輸出 win_results.csv 格式。"""

    draw_by_date = {row.get("nDdate", ""): row for row in rows}
    win_rows: list[dict[str, str]] = []
    for record in records:
        bet_date = record["bet_date"]
        draw_row = draw_by_date.get(bet_date)
        if draw_row is None:
            win_rows.append(build_pending_win_record(record))
            continue

        draw_nums = set(parse_nums(draw_row))
        win_record = {"bet_date": bet_date}
        for idx in range(1, 7):
            value = record.get(f"N{idx}", "")
            try:
                bet_num = int(value)
            except ValueError:
                bet_num = 0
            win_record[f"N{idx}"] = str(bet_num) if bet_num in draw_nums else "0"
        win_rows.append(win_record)
    return win_rows


def build_pending_win_record(record: dict[str, str]) -> dict[str, str]:
    """建立未開獎核對記錄。"""

    return {
        "bet_date": record["bet_date"],
        **{f"N{idx}": "未開獎" for idx in range(1, 7)},
    }


def write_bet_csv(csv_path: Path, records: list[dict[str, str]]) -> None:
    """寫入 bet_prize_data CSV。"""

    BET_DATA_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = ["bet_date", "N1", "N2", "N3", "N4", "N5", "N6"]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def print_detail_results(results: list[BacktestResult], title: str) -> None:
    """打印最近回測明細。"""

    if SHOW_DETAIL_COUNT <= 0:
        return

    print()
    print(f"====== {title} 最近 {min(SHOW_DETAIL_COUNT, len(results))} 期明細 ======")
    for item in results[-SHOW_DETAIL_COUNT:]:
        prediction_text = "，".join(
            f"[{','.join(str(num) for num in item['predictions'][group_option])}]"
            for group_option in PRINT_GROUP_OPTIONS
        )
        hit_text = ",".join(str(num) for num in item["normal_hit_nums"]) if item["normal_hit_nums"] else "-"
        special_hit_text = (
            f" + 特號[{item['special_hit_num']}]"
            if item["special_hit_num"] is not None
            else ""
        )
        check_text = format_check_num_slots(item["check_nums_1_31_slots"])
        print(
            f"近 {item['rank']}期：核對 [{item['check_date']}: {check_text}]，"
            f"{prediction_text}，命中[{hit_text}]{special_hit_text} /> "
            f"{format_hit_score(item['hit_score'])} 球"
        )


def print_hit_summary(results: list[BacktestResult], title: str) -> None:
    """打印命中率總結。"""

    summary = summarize_hits(results)
    distribution = summary["distribution"]
    assert isinstance(distribution, dict)
    print()
    print(f"====== {title} ======")
    print(f"總回測期數：{summary['total_count']}")
    print(f"模型分數：{summary['score']}")
    print(
        f"3球以上：{summary['hit_3_or_above']} 期，"
        f"4球以上：{summary['hit_4_or_above']} 期，"
        f"0球：{summary['zero_count']} 期"
    )
    for level in HIT_LEVELS:
        level_info = distribution[hit_score_key(level)]
        count = int(level_info["count"])
        rate = float(level_info["rate"])
        level_text = f"{format_hit_score(level)} 球"
        print(f"{level_text:<6} = {count} 期，{rate:.2f}%")


def build_model_report(mode_key: str, mode_label: str, results: list[BacktestResult]) -> dict[str, object]:
    """建立單一模式精簡回測報告，只保留七獎以上比較數據。"""

    summary = summarize_hits(results)

    return {
        "mode_key": mode_key,
        "mode_label": mode_label,
        "score": summary["score"],
        "total_count": summary["total_count"],
        "hit_4_or_above": summary["hit_4_or_above"],
        "hit_3_or_above": summary["hit_3_or_above"],
        "hit_2_or_above": summary["hit_2_or_above"],
        "zero_count": summary["zero_count"],
    }


def to_float(value: object, default: float = 0.0) -> float:
    """將 JSON 讀出的分數安全轉成 float，避免型別檢查誤判。"""

    if not isinstance(value, (int, float, str)):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def model_report_score(report: dict[str, object]) -> float:
    """取得模型報告分數。"""

    return to_float(report.get("score", 0))


def choose_best_model_report(reports: dict[str, dict[str, object]]) -> dict[str, object]:
    """由固定及動態模式中選最高模型分數。"""

    return max(reports.values(), key=model_report_score)


def read_backtest_score_history() -> list[dict[str, object]]:
    """讀取歷史 JSON 回測結果。"""

    if not BACKTEST_SCORE_JSON.exists():
        return []
    with BACKTEST_SCORE_JSON.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def compact_model_report(report: object) -> dict[str, object]:
    """將舊 JSON 的完整明細壓縮成七獎以上比較摘要。"""

    if not isinstance(report, dict):
        return {}
    summary = report.get("summary", {})
    if isinstance(summary, dict):
        return {
            "mode_key": report.get("mode_key", ""),
            "mode_label": report.get("mode_label", ""),
            "score": summary.get("score", 0),
            "total_count": summary.get("total_count", 0),
            "hit_4_or_above": summary.get("hit_4_or_above", 0),
            "hit_3_or_above": summary.get("hit_3_or_above", 0),
            "hit_2_or_above": summary.get("hit_2_or_above", 0),
            "zero_count": summary.get("zero_count", 0),
        }
    return {
        "mode_key": report.get("mode_key", ""),
        "mode_label": report.get("mode_label", ""),
        "score": report.get("score", 0),
        "total_count": report.get("total_count", 0),
        "hit_4_or_above": report.get("hit_4_or_above", 0),
        "hit_3_or_above": report.get("hit_3_or_above", 0),
        "hit_2_or_above": report.get("hit_2_or_above", 0),
        "zero_count": report.get("zero_count", 0),
    }


def compact_backtest_entry(entry: dict[str, object]) -> dict[str, object]:
    """清走舊 JSON 每期 details，只保留參數及模型摘要。"""

    models = entry.get("models", {})
    compact_models = {}
    if isinstance(models, dict):
        compact_models = {
            str(mode_key): compact_model_report(report)
            for mode_key, report in models.items()
        }

    return {
        "trend_period_weights": entry.get("trend_period_weights", []),
        "period_weights": entry.get("period_weights", {}),
        "backtest_draw_count": entry.get("backtest_draw_count", 0),
        "print_group_options": entry.get("print_group_options", []),
        "total_predict_num_count": entry.get("total_predict_num_count", 0),
        "special_num_weight": entry.get("special_num_weight", 0),
        "zero_penalty_weight": entry.get("zero_penalty_weight", 0),
        "low_prize_penalty_weight": entry.get("low_prize_penalty_weight", 0),
        "latest_data_date": entry.get("latest_data_date", ""),
        "models": compact_models,
        "best_model_key": entry.get("best_model_key", ""),
        "best_model_label": entry.get("best_model_label", ""),
        "best_model_score": entry.get("best_model_score", 0),
    }


def write_backtest_score_json(rows: list[dict[str, str]], fixed_results: list[BacktestResult], dynamic_results: list[BacktestResult]) -> None:
    """將本次回測兩大模式精簡寫入 JSON，供 predict 選最佳參數。"""

    JSON_DATA_DIR.mkdir(parents=True, exist_ok=True)
    reports = {
        "fixed_3_3_3": build_model_report("fixed_3_3_3", "固定 3+3+3", fixed_results),
        "dynamic_quota": build_model_report("dynamic_quota", "動態 2/3/4 配額", dynamic_results),
    }
    best_report = choose_best_model_report(reports)
    entry = {
        "trend_period_weights": [[period, weight] for period, weight in TREND_PERIOD_WEIGHTS],
        "period_weights": {str(period): weight for period, weight in PERIOD_WEIGHTS.items()},
        "backtest_draw_count": BACKTEST_DRAW_COUNT,
        "print_group_options": PRINT_GROUP_OPTIONS,
        "total_predict_num_count": TOTAL_PREDICT_NUM_COUNT,
        "special_num_weight": SPECIAL_NUM_WEIGHT,
        "zero_penalty_weight": ZERO_PENALTY_WEIGHT,
        "low_prize_penalty_weight": LOW_PRIZE_PENALTY_WEIGHT,
        "latest_data_date": rows[-1].get("nDdate", "") if rows else "",
        "models": reports,
        "best_model_key": best_report["mode_key"],
        "best_model_label": best_report["mode_label"],
        "best_model_score": model_report_score(best_report),
    }

    history = [compact_backtest_entry(entry) for entry in read_backtest_score_history()]
    signature = (
        entry["trend_period_weights"],
        entry["backtest_draw_count"],
        entry["print_group_options"],
        entry["total_predict_num_count"],
        entry["special_num_weight"],
        entry["zero_penalty_weight"],
        entry["low_prize_penalty_weight"],
    )

    updated = False
    for idx, old_entry in enumerate(history):
        old_signature = (
            old_entry.get("trend_period_weights"),
            old_entry.get("backtest_draw_count"),
            old_entry.get("print_group_options"),
            old_entry.get("total_predict_num_count"),
            old_entry.get("special_num_weight"),
            old_entry.get("zero_penalty_weight"),
            old_entry.get("low_prize_penalty_weight"),
        )
        if old_signature == signature:
            history[idx] = entry
            updated = True
            break
    if not updated:
        history.append(entry)

    history = sorted(history, key=lambda item: to_float(item.get("best_model_score", 0)), reverse=True)
    with BACKTEST_SCORE_JSON.open("w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    print()
    print("====== 回測 JSON 已更新 ======")
    print(f"檔案：{BACKTEST_SCORE_JSON}")
    print(f"本次最佳模式：{entry['best_model_label']}，分數：{entry['best_model_score']}")
    print(f"JSON 已保存參數組數：{len(history)}")


def read_best_backtest_entry() -> dict[str, object] | None:
    """讀取 JSON 最高分參數。"""

    history = read_backtest_score_history()
    if not history:
        return None
    return max(history, key=lambda item: to_float(item.get("best_model_score", 0)))


def apply_best_backtest_entry() -> tuple[bool, str]:
    """predict 模式套用 JSON 最佳期數權重及模式。"""

    global TREND_PERIOD_WEIGHTS, TREND_PERIODS, PERIOD_WEIGHTS

    best_entry = read_best_backtest_entry()
    if best_entry is None:
        return True, "dynamic_quota"

    raw_weights = best_entry.get("trend_period_weights", [])
    if not isinstance(raw_weights, list):
        return True, "dynamic_quota"

    parsed_weights: list[tuple[int, int]] = []
    for item in raw_weights:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            continue
        try:
            parsed_weights.append((int(item[0]), int(item[1])))
        except (TypeError, ValueError):
            continue
    if parsed_weights:
        TREND_PERIOD_WEIGHTS = parsed_weights
        TREND_PERIODS = [period for period, _weight in TREND_PERIOD_WEIGHTS]
        PERIOD_WEIGHTS = dict(TREND_PERIOD_WEIGHTS)

    best_model_key = str(best_entry.get("best_model_key", "dynamic_quota") or "dynamic_quota")
    dynamic_quota = best_model_key != "fixed_3_3_3"

    print()
    print("====== 已讀入 JSON 最佳回測參數 ======")
    print(f"最佳期數權重：{TREND_PERIOD_WEIGHTS}")
    print(f"最佳投注模式：{best_entry.get('best_model_label', best_model_key)}")
    print(f"最佳模型分數：{best_entry.get('best_model_score', 0)}")
    return dynamic_quota, best_model_key


def print_model_compare(fixed_results: list[BacktestResult], dynamic_results: list[BacktestResult]) -> None:
    """打印固定及動態模式高層比較。"""

    fixed_report = build_model_report("fixed_3_3_3", "固定 3+3+3", fixed_results)
    dynamic_report = build_model_report("dynamic_quota", "動態 2/3/4 配額", dynamic_results)
    best_report = choose_best_model_report({
        "fixed_3_3_3": fixed_report,
        "dynamic_quota": dynamic_report,
    })
    print()
    print("====== 模型比較 ======")
    for report in [fixed_report, dynamic_report]:
        print(
            f"{report['mode_label']}：{report['score']} 分，"
            f"3球以上 {report['hit_3_or_above']} 期，"
            f"4球以上 {report['hit_4_or_above']} 期，"
            f"0球 {report['zero_count']} 期"
        )
    print(f"建議採用：{best_report['mode_label']}")


def print_next_prediction(rows: list[dict[str, str]], *, dynamic_quota: bool) -> list[dict[str, str]]:
    """用最新已開獎資料，產生真正下期分組預測。"""

    target_index = len(rows)
    next_draw_info = read_next_draw_info()
    include_extra_bet = next_draw_info["next_draw_prize_fund"] >= HIGH_JACKPOT_FUND
    group_scores = {
        group_option: build_group_strength(rows, target_index, group_option)
        for group_option in PRINT_GROUP_OPTIONS
    }
    quotas = allocate_dynamic_quotas(group_scores) if dynamic_quota else {
        group_option: 3 for group_option in PRINT_GROUP_OPTIONS
    }
    predictions: dict[int, list[int]] = {}
    for group_option in PRINT_GROUP_OPTIONS:
        num_scores = build_group_num_scores(rows, target_index, group_option)
        predictions[group_option] = build_group_prediction(num_scores, quotas[group_option])

    print()
    mode_label = "動態 2/3/4 配額" if dynamic_quota else "固定 3+3+3"
    print(f"====== 下期分組配額預測：{mode_label} ======")
    print(
        f"下期投注日期：{next_draw_info['next_draw_date']}，"
        f"下期估計頭獎：{next_draw_info['next_draw_prize_fund']:g}"
    )
    for group_option in PRINT_GROUP_OPTIONS:
        start_num, end_num = birthday_range(group_option)
        nums_text = ",".join(str(num) for num in predictions[group_option])
        print(f"[{group_option}] {start_num}-{end_num}：{nums_text} /> {quotas[group_option]} 球")

    bet_lines = build_bet_lines(
        rows,
        target_index,
        predictions,
        include_extra_bet=include_extra_bet,
    )
    next_bet_records = [
        build_bet_record(next_draw_info["next_draw_date"], bet_nums)
        for bet_nums in bet_lines
    ]

    if all(group in predictions for group in [1, 2, 3]):
        print("單式參考：")
        for idx, bet_nums in enumerate(bet_lines, start=1):
            print(f"注{idx}：{','.join(str(num) for num in bet_nums)}")
        if include_extra_bet:
            print("下期估計頭獎較高，已加第三注 2組+3組。")
    return next_bet_records


def save_backtest_csv(
    rows: list[dict[str, str]],
    results: list[BacktestResult],
) -> None:
    """重建回測投注 CSV 及核對結果 CSV。"""

    if not SAVE_BET_CSV:
        return

    old_bet_count = len(read_csv_rows(BET_RECORDS_CSV))
    old_win_count = len(read_csv_rows(WIN_RESULTS_CSV))

    bet_records = build_bet_records(results)
    win_results = build_win_results(bet_records, rows)
    write_bet_csv(BET_RECORDS_CSV, bet_records)
    write_bet_csv(WIN_RESULTS_CSV, win_results)

    print()
    print("====== 回測 CSV 已重新建立 ======")
    print(f"讀入舊 bet_records.csv：{old_bet_count} 行，重建寫入：{len(bet_records)} 行")
    print(f"讀入舊 win_results.csv：{old_win_count} 行，重建寫入：{len(win_results)} 行")


def save_next_bet_csv(next_bet_records: list[dict[str, str]]) -> None:
    """重建下期預測投注 CSV。"""

    if not SAVE_BET_CSV:
        return

    old_next_count = len(read_csv_rows(NEXT_BET_CSV))
    write_bet_csv(NEXT_BET_CSV, next_bet_records)

    print()
    print("====== 下期預測 CSV 已重新建立 ======")
    print(f"讀入舊 nextBetDraw_record.csv：{old_next_count} 行，已寫入：{len(next_bet_records)} 行")


def append_next_bet_to_bet_records(next_bet_records: list[dict[str, str]]) -> None:
    """將下期預測追加到 bet_records.csv；同日期舊預測先移除。"""

    if not SAVE_BET_CSV or not next_bet_records:
        return

    bet_date = next_bet_records[0]["bet_date"]
    old_records = read_csv_rows(BET_RECORDS_CSV)
    kept_records = [record for record in old_records if record.get("bet_date", "") != bet_date]
    updated_records = [*kept_records, *next_bet_records]
    write_bet_csv(BET_RECORDS_CSV, updated_records)

    removed_count = len(old_records) - len(kept_records)
    print()
    print("====== 下期預測已追加到 bet_records.csv ======")
    print(f"投注日期：{bet_date}")
    print(f"刪除同日期舊記錄：{removed_count} 行")
    print(f"追加最新預測：{len(next_bet_records)} 行")
    print(f"bet_records.csv 現有總行數：{len(updated_records)} 行")


def sync_win_results_from_bet_records(rows: list[dict[str, str]]) -> None:
    """用最新 M6 開獎資料同步核對 bet_records.csv，重建 win_results.csv。"""

    if not SAVE_BET_CSV:
        return

    bet_records = read_csv_rows(BET_RECORDS_CSV)
    old_win_count = len(read_csv_rows(WIN_RESULTS_CSV))
    win_results = build_win_results(bet_records, rows)
    write_bet_csv(WIN_RESULTS_CSV, win_results)

    opened_count = sum(
        1
        for record in win_results
        if record.get("N1", "") != "未開獎"
    )
    pending_count = len(win_results) - opened_count

    print()
    print("====== win_results.csv 已同步最新開獎結果 ======")
    print(f"讀入 bet_records.csv：{len(bet_records)} 行")
    print(f"讀入舊 win_results.csv：{old_win_count} 行，重建寫入：{len(win_results)} 行")
    print(f"已核對開獎：{opened_count} 行，未開獎：{pending_count} 行")


def main() -> None:
    """主程式入口。"""

    validate_params()
    rows = read_m6_rows()
    print("====== A1_v2 分組配額預測回測 ======")
    print(f"執行模式：{RUN_MODE}")
    print(f"資料總期數：{len(rows)}")
    print(f"趨勢期數：{TREND_PERIODS}")

    if RUN_MODE == "backtest":
        print(f"回測期數：{BACKTEST_DRAW_COUNT}")
        fixed_results = run_backtest(rows, dynamic_quota=False)
        dynamic_results = run_backtest(rows, dynamic_quota=True)
        fixed_report = build_model_report("fixed_3_3_3", "固定 3+3+3", fixed_results)
        dynamic_report = build_model_report("dynamic_quota", "動態 2/3/4 配額", dynamic_results)
        best_report = choose_best_model_report({
            "fixed_3_3_3": fixed_report,
            "dynamic_quota": dynamic_report,
        })
        best_results = fixed_results if best_report["mode_key"] == "fixed_3_3_3" else dynamic_results

        print_detail_results(dynamic_results, "動態 2/3/4 配額預測")
        print_detail_results(fixed_results, "固定 3+3+3 預測")
        print_hit_summary(fixed_results, "固定 3+3+3 回測命中率")
        print_hit_summary(dynamic_results, "動態 2/3/4 配額回測命中率")
        print_model_compare(fixed_results, dynamic_results)
        save_backtest_csv(rows, best_results)
        write_backtest_score_json(rows, fixed_results, dynamic_results)

    if RUN_MODE == "predict":
        dynamic_quota, _best_model_key = apply_best_backtest_entry()
        next_bet_records = print_next_prediction(rows, dynamic_quota=dynamic_quota)
        save_next_bet_csv(next_bet_records)
        append_next_bet_to_bet_records(next_bet_records)
        sync_win_results_from_bet_records(rows)


if __name__ == "__main__":
    main()
