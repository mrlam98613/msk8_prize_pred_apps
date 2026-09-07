from pathlib import Path
import csv
import json
from typing import TypedDict


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
M6_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"
JSON_PATH = CURRENT_DIR / "json_data" / "F5_v2_none_transition.json"

# 基本參數：每個核對期都只使用此前窗口資料。
BACKTEST_DRAW_COUNT = 12
WINDOW_DRAW_COUNT_LIST = [12, 18]
BIRTHDAY_NUM_MIN = 1
BIRTHDAY_NUM_MAX = 9

# 若回測期前一期為 (00)，本模組預測核對期會出現至少 1 個 1-9 號。
PREDICT_AFTER_NONE = True
MIN_AFTER_NONE_HIT_RATE = 0.65


class DrawRow(TypedDict):
    date: str
    nums: list[int]
    special: int | None


class ResultRow(TypedDict):
    check_date: str
    previous_date: str
    previous_is_none: bool
    predicted_has_1_9: bool
    actual_1_9_count: int
    is_correct: bool


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


def read_draws() -> list[DrawRow]:
    if not M6_CSV.exists():
        raise FileNotFoundError(f"找不到 CSV：{M6_CSV}")
    with M6_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        draws: list[DrawRow] = []
        for row in reader:
            date = (row.get("nDdate") or "").strip()
            if not date:
                continue
            special = to_int(row.get("N7"))
            draws.append({
                "date": date,
                "nums": [to_int(row.get(f"N{index}")) for index in range(1, 7)],
                "special": special if 1 <= special <= 49 else None,
            })
    return draws


def count_1_9(row: DrawRow) -> int:
    nums = {num for num in row["nums"] if BIRTHDAY_NUM_MIN <= num <= BIRTHDAY_NUM_MAX}
    if row["special"] is not None and BIRTHDAY_NUM_MIN <= row["special"] <= BIRTHDAY_NUM_MAX:
        nums.add(row["special"])
    return len(nums)


def none_run_length(draws: list[DrawRow], before_index: int) -> int:
    length = 0
    for row in reversed(draws[:before_index]):
        if count_1_9(row) != 0:
            break
        length += 1
    return length


def after_none_rate(draws: list[DrawRow], end_index: int, window_count: int) -> tuple[int, int, float]:
    history = draws[max(0, end_index - window_count - 1):end_index]
    triggered = 0
    returned = 0
    for previous, following in zip(history, history[1:]):
        if count_1_9(previous) == 0:
            triggered += 1
            returned += count_1_9(following) > 0
    return triggered, returned, returned / triggered if triggered else 0.0


def run_backtest(draws: list[DrawRow], backtest_count: int, window_count: int) -> list[ResultRow]:
    if len(draws) < backtest_count + window_count + 1:
        return []
    start_index = len(draws) - backtest_count
    results: list[ResultRow] = []
    for check_index in range(start_index, len(draws)):
        window_rows = draws[check_index - window_count:check_index]
        previous = window_rows[-1]
        previous_is_none = count_1_9(previous) == 0
        _, _, history_rate = after_none_rate(draws, check_index, window_count)
        predicted_has_1_9 = previous_is_none and PREDICT_AFTER_NONE and history_rate >= MIN_AFTER_NONE_HIT_RATE
        actual_count = count_1_9(draws[check_index])
        results.append({
            "check_date": draws[check_index]["date"],
            "previous_date": previous["date"],
            "previous_is_none": previous_is_none,
            "predicted_has_1_9": predicted_has_1_9,
            "actual_1_9_count": actual_count,
            "is_correct": predicted_has_1_9 == (actual_count > 0),
        })
    return results


def summarize(draws: list[DrawRow], rows: list[ResultRow], window_count: int) -> dict[str, object]:
    previous_none_rows = [row for row in rows if row["previous_is_none"]]
    predicted_rows = [row for row in previous_none_rows if row["predicted_has_1_9"]]
    hit_rows = [row for row in predicted_rows if row["actual_1_9_count"] > 0]
    failed_rows = [row for row in predicted_rows if row["actual_1_9_count"] == 0]
    missed_rows = [
        row for row in previous_none_rows
        if not row["predicted_has_1_9"] and row["actual_1_9_count"] > 0
    ]
    return {
        "window_draw_count": window_count,
        "backtest_draw_count": len(rows),
        "previous_none_count": len(previous_none_rows),
        "prediction_count": len(predicted_rows),
        "prediction_hit_count": len(hit_rows),
        "prediction_failed_count": len(failed_rows),
        "missed_has_1_9_count": len(missed_rows),
        "after_none_hit_rate": len(hit_rows) / len(predicted_rows) if predicted_rows else 0.0,
        "current_none_run": none_run_length(draws, len(draws)),
        "minimum_after_none_hit_rate": MIN_AFTER_NONE_HIT_RATE,
        "result_rows": rows,
    }


def print_summary(summary: dict[str, object]) -> None:
    previous_none = to_int(summary.get("previous_none_count"))
    predicted = to_int(summary.get("prediction_count"))
    hit = to_int(summary.get("prediction_hit_count"))
    rate = to_float(summary.get("after_none_hit_rate"))
    print(f"窗口期 {to_int(summary.get('window_draw_count'))}，回測 {to_int(summary.get('backtest_draw_count'))} 期")
    print(f"(00) 歷史發球門檻：{to_float(summary.get('minimum_after_none_hit_rate')):.0%}")
    print(f"前一期 (00)：{previous_none} 期")
    print(f"符合門檻並發球：{predicted} 期")
    print(f"發球後命中 1-9：{hit}/{predicted} 期，命中率 {rate:.1%}")
    print(f"發球後仍為 (00)：{to_int(summary.get('prediction_failed_count'))} 期")
    print(f"未發球但下一期有 1-9：{to_int(summary.get('missed_has_1_9_count'))} 期")
    print(f"目前連續 (00)：{to_int(summary.get('current_none_run'))} 期")


def main() -> None:
    draws = read_draws()
    summaries = [summarize(draws, run_backtest(draws, BACKTEST_DRAW_COUNT, window), window) for window in WINDOW_DRAW_COUNT_LIST]
    print("====== F5_v2 (00) 上下期轉移回測 ======")
    for summary in summaries:
        print_summary(summary)
        print("------------------------------------------")
    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(json.dumps({"model": "F5_v2_none_transition", "summaries": summaries}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
