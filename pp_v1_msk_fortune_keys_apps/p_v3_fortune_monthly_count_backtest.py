from pathlib import Path
import csv
from collections import Counter, defaultdict
from typing import TypedDict


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
M6_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"
M4_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M4_lotto_prize_summary.csv"


# MODE 可選："backtest" 或 "predict"。
MODE = "backtest"
BACKTEST_DRAW_COUNT_LIST = [100]
WINDOW_DRAW_COUNT_LIST = [100]

# 只分析 1-9 命中球數，不分析實際號碼命中。
FORTUNE_NUM_MIN = 1
FORTUNE_NUM_MAX = 9

# 預測分類：0球、1球、2球、3球以上。
PREDICT_BUCKETS = (0, 1, 2, 3)

# 固定配額基準：每期固定配 3 球或 2 球，先看不用公式的基本命中率。
FIXED_QUOTA_LIST = [3, 2]

# 走趨樣版：用核對日前近 1/3/5/7/9 期的 1-9 開出球數序列，找歷史相同樣版。
TREND_LOOKBACK_LIST = [1, 3, 5, 7, 9]
TREND_WEIGHT_BY_LENGTH = {
    1: 1.0,
    3: 1.5,
    5: 2.0,
    7: 2.5,
    9: 3.0,
}
MONTH_POSITION_WEIGHT = 1.0
RECENT_FALLBACK_COUNT = 12

# 是否打印每期回測明細。
PRINT_BACKTEST_DETAIL = False

# 是否打印完整預測 x 實際交叉表；平時看簡單統計已足夠。
PRINT_CROSS_TABLE = False


class DrawRow(TypedDict):
    date: str
    nums: list[int]
    special: int | None
    prize_count: float


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    """讀取 CSV 並清理欄位名稱與文字空白。"""
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
    """安全轉換數值為 int。"""
    if not isinstance(value, (int, float, str)):
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def to_float(value: object, default: float = 0.0) -> float:
    """安全轉換數值為 float。"""
    if not isinstance(value, (int, float, str)):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_m6_row(row: dict[str, str]) -> DrawRow:
    """將 M6 原始 CSV 一行轉成標準 DrawRow。"""
    special = to_int(row.get("N7"))
    return {
        "date": row.get("nDdate", ""),
        "nums": [to_int(row.get(f"N{index}")) for index in range(1, 7)],
        "special": special if 1 <= special <= 49 else None,
        "prize_count": to_float(row.get("prize3")),
    }


def read_draws() -> list[DrawRow]:
    """讀取所有有效歷史開獎紀錄。"""
    return [row for row in [parse_m6_row(raw) for raw in read_csv_rows(M6_CSV)] if row["date"]]


def read_next_draw_date() -> str:
    """從 M4 摘要讀取下一期開獎日期。"""
    rows = read_csv_rows(M4_CSV)
    return rows[-1].get("next_draw_date", "") if rows else ""


def fortune_count(row: DrawRow) -> int:
    """計算一期正號 N1..N6 中 1-9 出現球數。"""
    return sum(1 for num in row["nums"] if FORTUNE_NUM_MIN <= num <= FORTUNE_NUM_MAX)


def fortune_bucket(count: int) -> int:
    """將命中球數歸類成 0、1、2、3；3 代表 3球或以上。"""
    if count >= 3:
        return 3
    return count


def month_key(date_text: str) -> str:
    """取得 YYYY-MM 月份鍵。"""
    return date_text[:7]


def format_nums(nums: list[int]) -> str:
    """格式化號碼列表。"""
    return "[" + ",".join(str(num) for num in nums) + "]"


def fortune_nums(row: DrawRow) -> list[int]:
    """取得一期 1-9 正號。"""
    return sorted(num for num in row["nums"] if FORTUNE_NUM_MIN <= num <= FORTUNE_NUM_MAX)


def month_bucket_counts(rows: list[DrawRow]) -> dict[str, Counter[int]]:
    """按月份統計 0球、1球、2球、3球以上期數。"""
    result: dict[str, Counter[int]] = defaultdict(Counter)
    for row in rows:
        result[month_key(row["date"])][fortune_bucket(fortune_count(row))] += 1
    return result


def month_average_counts(rows: list[DrawRow]) -> dict[int, float]:
    """計算窗口期內每月平均 0/1/2/3 球期數，只作觀察不作預測。"""
    by_month = month_bucket_counts(rows)
    if not by_month:
        return {bucket: 0.0 for bucket in PREDICT_BUCKETS}
    return {
        bucket: sum(counter[bucket] for counter in by_month.values()) / len(by_month)
        for bucket in PREDICT_BUCKETS
    }


def month_average_positive_count(rows: list[DrawRow]) -> float:
    """計算窗口期每月平均有 1-9 正號的期數。"""
    by_month = month_bucket_counts(rows)
    if not by_month:
        return 0.0
    return sum(counter[1] + counter[2] + counter[3] for counter in by_month.values()) / len(by_month)


def current_month_counts_before(rows: list[DrawRow], target_date: str) -> Counter[int]:
    """統計目標日期前，同月份已出現的 0/1/2/3+ 球期數。"""
    target_month = month_key(target_date)
    counter: Counter[int] = Counter()
    for row in rows:
        if row["date"] < target_date and month_key(row["date"]) == target_month:
            counter[fortune_bucket(fortune_count(row))] += 1
    return counter


def month_position_scores(rows: list[DrawRow], target_date: str) -> dict[int, float]:
    """用目標日期所在月份的位置，估計 0球、有球、3球以上是否仍有空間。"""
    month_avg = month_average_counts(rows)
    positive_avg = month_average_positive_count(rows)
    current = current_month_counts_before(rows, target_date)
    current_positive = current[1] + current[2] + current[3]

    zero_gap = max(0.0, month_avg[0] - current[0])
    positive_gap = max(0.0, positive_avg - current_positive)
    three_gap = max(0.0, month_avg[3] - current[3])

    return {
        0: zero_gap,
        1: positive_gap * 0.45,
        2: positive_gap * 0.35,
        3: three_gap + positive_gap * 0.20,
    }


def bucket_sequence(rows: list[DrawRow]) -> list[int]:
    """將多期開獎轉成 0/1/2/3+ 球數走趨序列。"""
    return [fortune_bucket(fortune_count(row)) for row in rows]


def trend_next_counts(sequence: list[int], lookback: int) -> Counter[int]:
    """搜尋相同走趨樣版，統計樣版後下一期的球數分類。"""
    counter: Counter[int] = Counter()
    if len(sequence) <= lookback:
        return counter

    target = tuple(sequence[-lookback:])
    for end_index in range(lookback, len(sequence)):
        sample = tuple(sequence[end_index - lookback:end_index])
        if sample == target:
            counter[sequence[end_index]] += 1
    return counter


def recent_fallback_counts(sequence: list[int]) -> Counter[int]:
    """當走趨樣版不足時，用最近 N 期球數分布作保底參考。"""
    return Counter(sequence[-RECENT_FALLBACK_COUNT:])


def predict_bucket(
    window_rows: list[DrawRow],
    target_date: str,
) -> tuple[int, dict[int, float], dict[int, Counter[int]], dict[int, float]]:
    """用月份位置加近 1/3/5/7/9 期走趨樣版，預測目標日期 1-9 命中球數分類。"""
    sequence = bucket_sequence(window_rows)
    scores: dict[int, float] = {}
    trend_counts: dict[int, Counter[int]] = {}

    for bucket in PREDICT_BUCKETS:
        scores[bucket] = 0.0

    for lookback in TREND_LOOKBACK_LIST:
        counts = trend_next_counts(sequence, lookback)
        trend_counts[lookback] = counts
        total = sum(counts.values())
        if total == 0:
            continue
        weight = TREND_WEIGHT_BY_LENGTH.get(lookback, 1.0)
        for bucket in PREDICT_BUCKETS:
            scores[bucket] += weight * counts[bucket] / total

    position_scores = month_position_scores(window_rows, target_date)
    for bucket in PREDICT_BUCKETS:
        scores[bucket] += MONTH_POSITION_WEIGHT * position_scores[bucket]

    if all(score == 0.0 for score in scores.values()):
        fallback = recent_fallback_counts(sequence)
        total = sum(fallback.values())
        if total:
            for bucket in PREDICT_BUCKETS:
                scores[bucket] = fallback[bucket] / total

    best_bucket = sorted(scores.items(), key=lambda item: (-item[1], item[0]))[0][0]
    return best_bucket, scores, trend_counts, position_scores


def bucket_text(bucket: int) -> str:
    """顯示 bucket 文字。"""
    if bucket == 3:
        return "3球或以上"
    return f"{bucket}球"


def quota_text(bucket: int) -> str:
    """顯示包含式配額文字。"""
    if bucket == 0:
        return "0球"
    if bucket == 3:
        return "1-3球"
    return f"1-{bucket}球"


def quota_hit(predicted_bucket: int, actual_bucket: int) -> bool:
    """判斷包含式配額是否命中。

    預測 3球 = 包含實際 1/2/3+ 球；
    預測 2球 = 包含實際 1/2 球；
    預測 1球 = 只包含實際 1 球；
    預測 0球 = 實際 0 球才命中。
    """
    if predicted_bucket == 0:
        return actual_bucket == 0
    return 1 <= actual_bucket <= predicted_bucket


def fixed_quota_hit(quota: int, actual_count: int) -> bool:
    """固定配額是否足夠覆蓋實際 1-9 開出球數。"""
    return 1 <= actual_count <= quota


def score_text(scores: dict[int, float]) -> str:
    """格式化走趨分數。"""
    return (
        f"0球={scores[0]:.2f}, "
        f"1球={scores[1]:.2f}, "
        f"2球={scores[2]:.2f}, "
        f"3球+={scores[3]:.2f}"
    )


def trend_counts_text(trend_counts: dict[int, Counter[int]]) -> str:
    """格式化各長度走趨樣版的歷史匹配次數。"""
    parts: list[str] = []
    for lookback in TREND_LOOKBACK_LIST:
        counts = trend_counts.get(lookback, Counter())
        total = sum(counts.values())
        parts.append(f"{lookback}期={total}")
    return "，".join(parts)


def position_score_text(position_scores: dict[int, float]) -> str:
    """格式化月份位置分。"""
    return (
        f"0球={position_scores[0]:.2f}, "
        f"1球={position_scores[1]:.2f}, "
        f"2球={position_scores[2]:.2f}, "
        f"3球+={position_scores[3]:.2f}"
    )


def print_query_setting() -> None:
    """打印模型設定。"""
    print("====== fortune_keys 月份節奏回測 ======")
    print(f"運作模式：{MODE}")
    print(f"回測期列表：{BACKTEST_DRAW_COUNT_LIST}")
    print(f"窗口期列表：{WINDOW_DRAW_COUNT_LIST}")
    print("分析目標：只預測 1-9 正號命中球數，不預測實際號碼")
    print("預測分類：0球 / 1球 / 2球 / 3球或以上")
    print(f"走趨樣版：近 {TREND_LOOKBACK_LIST} 期")
    print(f"月份位置權重：{MONTH_POSITION_WEIGHT}")
    print()


def print_window_month_summary(window_rows: list[DrawRow]) -> None:
    """打印窗口期每月 0/1/2/3 球節奏。"""
    by_month = month_bucket_counts(window_rows)
    print("----- 窗口期月份統計 -----")
    for month in sorted(by_month.keys()):
        counter = by_month[month]
        print(
            f"{month}："
            f"0球={counter[0]}期，"
            f"1球={counter[1]}期，"
            f"2球={counter[2]}期，"
            f"3球以上={counter[3]}期"
        )

    avg = month_average_counts(window_rows)
    positive_avg = month_average_positive_count(window_rows)
    print(
        "月平均："
        f"0球={avg[0]:.2f}期，"
        f"有1-9號={positive_avg:.2f}期，"
        f"1球={avg[1]:.2f}期，"
        f"2球={avg[2]:.2f}期，"
        f"3球以上={avg[3]:.2f}期"
    )
    print()


def print_backtest_summary(stats: Counter[tuple[int, int]], total_count: int, hit_count: int) -> None:
    """打印簡化回測統計，避免交叉表太亂。"""
    actual_totals: Counter[int] = Counter()
    predict_totals: Counter[int] = Counter()
    actual_hits: Counter[int] = Counter()
    quota_hits: Counter[int] = Counter()
    quota_misses: Counter[int] = Counter()

    for (predicted, actual), count in stats.items():
        predict_totals[predicted] += count
        actual_totals[actual] += count
        if predicted == actual:
            actual_hits[actual] += count
        if quota_hit(predicted, actual):
            quota_hits[predicted] += count
        else:
            quota_misses[predicted] += count

    print("----- 回測命中統計 -----")
    print(f"總分類命中：{hit_count}/{total_count} = {hit_count / total_count * 100:.1f}%")

    print("實際分布：")
    for bucket in PREDICT_BUCKETS:
        print(f"{bucket_text(bucket):>5} = {actual_totals[bucket]} 期")

    print("預測分布：")
    for bucket in PREDICT_BUCKETS:
        print(f"{bucket_text(bucket):>5} = {predict_totals[bucket]} 期")

    print("各球數命中：")
    for bucket in PREDICT_BUCKETS:
        total = actual_totals[bucket]
        hit = actual_hits[bucket]
        percent = hit / total * 100 if total else 0.0
        print(f"{bucket_text(bucket):>5} = {hit}/{total} 期，{percent:.1f}%")

    print("包含式配額命中：")
    for bucket in PREDICT_BUCKETS:
        total = predict_totals[bucket]
        hit = quota_hits[bucket]
        miss = quota_misses[bucket]
        percent = hit / total * 100 if total else 0.0
        print(f"預測{quota_text(bucket):>4} = 命中 {hit}/{total} 期，{percent:.1f}%，不足/錯向 {miss} 期")

    if PRINT_CROSS_TABLE:
        print("交叉表：")
        for predicted in PREDICT_BUCKETS:
            row_text = []
            for actual in PREDICT_BUCKETS:
                row_text.append(f"實際{bucket_text(actual)}={stats[(predicted, actual)]}期")
            print(f"預測{bucket_text(predicted)}：" + "，".join(row_text))


def print_fixed_quota_summary(check_rows: list[DrawRow]) -> None:
    """打印固定 3球 / 2球配額基準統計。"""
    total_count = len(check_rows)
    actual_counts = Counter(fortune_count(row) for row in check_rows)
    positive_count = sum(count for balls, count in actual_counts.items() if balls >= 1)

    print(f"----- [1-9] 固定配額基準 {FIXED_QUOTA_LIST} -----")
    print(f"開獎期內有 1-9 號：{positive_count}/{total_count} 期，{positive_count / total_count * 100:.1f}%")
    for balls in range(6, -1, -1):
        if balls >= 5 and actual_counts[balls] == 0:
            continue
        if balls == 0:
            print(f"= 0 球：{actual_counts[balls]} 期")
        else:
            print(f"有 {balls:>2}球：{actual_counts[balls]} 期")

    for quota in FIXED_QUOTA_LIST:
        hit = sum(1 for row in check_rows if fixed_quota_hit(quota, fortune_count(row)))
        zero_miss = actual_counts[0]
        over_quota = sum(count for balls, count in actual_counts.items() if balls > quota)
        print(
            f"固定配 {quota} 球："
            f"命中 {hit}/{total_count} 期，{hit / total_count * 100:.1f}%，"
            f"0球失敗 {zero_miss} 期，超配額 {over_quota} 期"
        )


def run_backtest(draws: list[DrawRow]) -> None:
    """執行月份節奏 backtest。"""
    latest_index = len(draws) - 1
    for backtest_count in BACKTEST_DRAW_COUNT_LIST:
        for window_count in WINDOW_DRAW_COUNT_LIST:
            first_check_index = max(window_count, latest_index - backtest_count + 1)
            check_indices = list(range(first_check_index, latest_index + 1))
            print_fixed_quota_summary([draws[index] for index in check_indices])
            print()


def run_predict(draws: list[DrawRow]) -> None:
    """用最後窗口期預測下一期 1-9 命中球數分類。"""
    next_draw_date = read_next_draw_date()
    latest_row = draws[-1]
    for window_count in WINDOW_DRAW_COUNT_LIST:
        window_rows = draws[-window_count:]
        target_date = next_draw_date or latest_row["date"]
        predicted_bucket, scores, trend_counts, position_scores = predict_bucket(window_rows, target_date)
        print(f"====== 預測模式，窗口期={window_count} ======")
        print_window_month_summary(window_rows)
        print(
            f"最新日期：{latest_row['date']}，下期開獎日期：{next_draw_date or '未知'}，"
            f"預測 1-9：{bucket_text(predicted_bucket)}"
        )
        print(f"走趨匹配：{trend_counts_text(trend_counts)}")
        print(f"月份位置：{position_score_text(position_scores)}")
        print(f"分數：{score_text(scores)}")
        print()


def main() -> None:
    """主流程。"""
    draws = read_draws()
    if not draws:
        raise FileNotFoundError(f"找不到或未能讀取 M6：{M6_CSV}")

    print_query_setting()
    if MODE == "backtest":
        run_backtest(draws)
    elif MODE == "predict":
        run_predict(draws)
    else:
        raise ValueError('MODE 只能是 "backtest" 或 "predict"')


if __name__ == "__main__":
    main()
