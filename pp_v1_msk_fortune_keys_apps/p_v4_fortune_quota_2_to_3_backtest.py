from pathlib import Path
import csv
import json
from collections import Counter, defaultdict
from typing import TypedDict


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
M6_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"
M3_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M3_lotto_prize_results.csv"
M4_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M4_lotto_prize_summary.csv"
JSON_DIR = CURRENT_DIR / "json_data"
JSON_OUTPUT = JSON_DIR / "p_v4_fortune_quota_2_to_3_backtest.json"
CSV_DIR = CURRENT_DIR / "csv_data"
MONTH_YEAR_MASTER_CSV = CSV_DIR / "p_v4_mon_year_fortune_key.csv"


# MODE 可選："backtest" 或 "predict"。
MODE = "predict"
BACKTEST_DRAW_COUNT_LIST = [200] # backtest mode 期數 才生效 
WINDOW_DRAW_COUNT_LIST = [100]
PREDICT_REFERENCE_BACKTEST_COUNT = 200

# 只分析 1-9 正號命中球數，不分析實際號碼。
FORTUNE_NUM_MIN = 1
FORTUNE_NUM_MAX = 9

# 基本策略：每期固定配 2 球；日期範圍訊號出現時升級配 3 球。
BASE_QUOTA = 2
UPGRADE_QUOTA = 3

# 升級條件：窗口期內 >=3 球的日期範圍，加上目標月份 3球以上尚未達月平均。
UPGRADE_MATCH_COUNT = 3

# 日期範圍收窄：用最近 1/3/5 次 >=3球 的日期範圍觀察，預設用最近3次判斷升級。
RECENT_THREE_PLUS_RANGE_LIST = [1, 3, 5]
UPGRADE_RECENT_RANGE_COUNT = 3

# 是否打印每期回測明細。
PRINT_BACKTEST_DETAIL = False

# 是否打印最後一期真實滾動回測快照。
PRINT_LAST_ROLLING_SNAPSHOT = False

# 是否打印第一期真實滾動回測快照，用來核對回測起點與窗口期。
PRINT_FIRST_ROLLING_SNAPSHOT = False

# 是否打印簡化版的整段跨年份月份表。
PRINT_RANGE_YEAR_MONTH_TABLE = True

# 是否將每一期真實滾動回測快照寫入 JSON。
SAVE_ANALYSIS_JSON = True


class DrawRow(TypedDict):
    date: str
    nums: list[int]
    special: int | None
    prize_count: float


class DayRange(TypedDict):
    start_day: int | None
    end_day: int | None


class RollingSnapshot(TypedDict):
    check_date: str
    window_start: str
    window_end: str
    target_year: str
    target_month: int
    target_day: int
    base_quota: int
    suggest_quota: int
    actual_count: int
    hit: bool
    reason: str
    three_plus_day_range: DayRange
    month_average_three_plus: float
    year_month_distribution: dict[str, dict[str, int]]


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
    """優先從 M3 讀取下一期開獎日期，失敗時回退 M4 摘要。"""
    m3_date = read_next_draw_date_from_m3()
    if m3_date:
        return m3_date

    rows = read_csv_rows(M4_CSV)
    return rows[-1].get("next_draw_date", "") if rows else ""


def read_next_draw_date_from_m3() -> str:
    """從 M3 的「開獎日期,2026年09月17日 (四)」轉成 YYYY-MM-DD。"""
    if not M3_CSV.exists():
        return ""

    with M3_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line.startswith("開獎日期,"):
                continue
            date_text = line.split(",", 1)[1].split(" ", 1)[0]
            return (
                date_text
                .replace("年", "-")
                .replace("月", "-")
                .replace("日", "")
            )
    return ""


def month_key(date_text: str) -> str:
    """取得 YYYY-MM 月份鍵。"""
    return date_text[:7]


def year_key(date_text: str) -> str:
    """取得 YYYY 年份鍵。"""
    return date_text[:4]


def day_of_month(date_text: str) -> int:
    """取得月份日數。"""
    return to_int(date_text[8:10])


def month_number(date_text: str) -> int:
    """取得月份數字 1-12。"""
    return to_int(date_text[5:7])


def previous_month_number(month: int) -> int:
    """取得上一個月份數字。"""
    return 12 if month == 1 else month - 1


def fortune_count(row: DrawRow) -> int:
    """計算一期正號 N1..N6 中 1-9 出現球數。"""
    return sum(1 for num in row["nums"] if FORTUNE_NUM_MIN <= num <= FORTUNE_NUM_MAX)


def month_three_plus_counts(rows: list[DrawRow]) -> dict[str, int]:
    """按月份統計 >=3 球期數。"""
    result: dict[str, int] = defaultdict(int)
    for row in rows:
        if fortune_count(row) >= UPGRADE_MATCH_COUNT:
            result[month_key(row["date"])] += 1
    return result


def calendar_month_three_plus_counts(rows: list[DrawRow]) -> Counter[int]:
    """按 1-12 月統計 >=3 球期數。"""
    counter: Counter[int] = Counter()
    for row in rows:
        if fortune_count(row) >= UPGRADE_MATCH_COUNT:
            counter[month_number(row["date"])] += 1
    return counter


def year_month_three_plus_distribution(rows: list[DrawRow]) -> dict[str, dict[str, int]]:
    """按年份與 1-12 月統計 >=3 球期數。"""
    result: dict[str, dict[str, int]] = {}
    for row in rows:
        year = year_key(row["date"])
        month = str(month_number(row["date"]))
        result.setdefault(year, {str(index): 0 for index in range(1, 13)})
        if fortune_count(row) >= UPGRADE_MATCH_COUNT:
            result[year][month] += 1
    return result


def month_average_three_plus(rows: list[DrawRow]) -> float:
    """計算窗口期每月平均 >=3 球期數。"""
    month_rows: dict[str, int] = defaultdict(int)
    for row in rows:
        month_rows[month_key(row["date"])] += 1
    if not month_rows:
        return 0.0

    three_counts = month_three_plus_counts(rows)
    return sum(three_counts[month] for month in month_rows.keys()) / len(month_rows)


def rounded_month_average_three_plus(rows: list[DrawRow]) -> int:
    """用整數顯示每月平均 >=3 球期數。"""
    return round(month_average_three_plus(rows))


def three_plus_day_range(rows: list[DrawRow]) -> tuple[int | None, int | None]:
    """取得窗口期內 >=3 球開獎日的最早日與最遲日。"""
    days = [day_of_month(row["date"]) for row in rows if fortune_count(row) >= UPGRADE_MATCH_COUNT]
    if not days:
        return None, None
    return min(days), max(days)


def recent_three_plus_rows(rows: list[DrawRow], count: int) -> list[DrawRow]:
    """取得最近 count 次 >=3 球開獎期。"""
    matched_rows = [row for row in rows if fortune_count(row) >= UPGRADE_MATCH_COUNT]
    return matched_rows[-count:]


def recent_three_plus_day_range(rows: list[DrawRow], count: int) -> tuple[int | None, int | None]:
    """取得最近 count 次 >=3 球開獎日範圍。"""
    matched_rows = recent_three_plus_rows(rows, count)
    days = [day_of_month(row["date"]) for row in matched_rows]
    if not days:
        return None, None
    return min(days), max(days)


def recent_three_plus_range_text(rows: list[DrawRow]) -> str:
    """格式化最近 1/3/5 次 >=3 球日期範圍。"""
    parts: list[str] = []
    for count in RECENT_THREE_PLUS_RANGE_LIST:
        start_day, end_day = recent_three_plus_day_range(rows, count)
        if start_day is None or end_day is None:
            parts.append(f"最近{count}次=沒有資料")
        elif start_day == end_day:
            parts.append(f"最近{count}次={start_day}日")
        else:
            parts.append(f"最近{count}次={start_day}-{end_day}日")
    return "，".join(parts)


def current_month_three_plus_before(rows: list[DrawRow], target_date: str) -> int:
    """統計目標日期前，同月份已出現 >=3 球的期數。"""
    target_month = month_key(target_date)
    return sum(
        1
        for row in rows
        if row["date"] < target_date
        and month_key(row["date"]) == target_month
        and fortune_count(row) >= UPGRADE_MATCH_COUNT
    )


def calendar_month_three_plus_before(rows: list[DrawRow], target_date: str, month: int) -> int:
    """統計目標日期前，指定月份已出現 >=3 球的期數。"""
    return sum(
        1
        for row in rows
        if row["date"] < target_date
        and month_number(row["date"]) == month
        and fortune_count(row) >= UPGRADE_MATCH_COUNT
    )


def fixed_quota_hit(quota: int, actual_count: int) -> bool:
    """固定配額是否足夠覆蓋實際 1-9 開出球數。"""
    return 1 <= actual_count <= quota


def save_json(data: object, path: Path) -> None:
    """寫入 JSON 分析結果。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def month_distribution_csv_path(check_date: str) -> Path:
    """取得單一期年月分佈 CSV 路徑。"""
    return CSV_DIR / f"p_v4_month_distribution_{check_date}.csv"


def range_month_distribution_csv_path(backtest_count: int, window_count: int) -> Path:
    """取得整段回測年月分佈 CSV 路徑。"""
    return MONTH_YEAR_MASTER_CSV


def save_year_month_distribution_csv(
    distribution: dict[str, dict[str, int]],
    path: Path,
) -> None:
    """將年份 x 月份分佈寫成 CSV table。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    years = sorted(distribution.keys())
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["月份", *years])
        for month in range(1, 13):
            writer.writerow([
                f"{month}月",
                *[distribution[year].get(str(month), 0) for year in years],
            ])


def print_year_month_distribution_csv(path: Path) -> None:
    """由 CSV 讀取並打印年份 x 月份分佈表。"""
    rows = read_csv_rows(path)
    if not rows:
        return

    years = [key for key in rows[0].keys() if key != "月份"]
    print("月份分佈：")
    print("月份    " + "    ".join(years))
    for row in rows:
        value_text = "    ".join(f"{to_int(row.get(year)):>4}" for year in years)
        print(f"{row.get('月份', ''):>3}    {value_text}")


def print_reference_month_distribution(window_count: int) -> None:
    """predict mode 讀入整段回測月份分佈 CSV 作參考。"""
    path = MONTH_YEAR_MASTER_CSV
    if not path.exists():
        print(f"回測參考月份分佈 CSV 未建立：{path}")
        return

    print("----- 月份年份參考表 -----")
    print_year_month_distribution_csv(path)
    print()


def predict_quota(window_rows: list[DrawRow], target_date: str) -> tuple[int, str]:
    """用日期範圍決定是否由 2 球升級到 3 球。"""
    start_day, end_day = recent_three_plus_day_range(window_rows, UPGRADE_RECENT_RANGE_COUNT)
    if start_day is None or end_day is None:
        return BASE_QUOTA, "原因：\n窗口期 >=3球 常見日期範圍：沒有資料\n判斷：維持基本 2球"

    target_day = day_of_month(target_date)
    target_month = month_number(target_date)
    prev_month = previous_month_number(target_month)
    avg_three = month_average_three_plus(window_rows)
    current_three = current_month_three_plus_before(window_rows, target_date)
    prev_month_three = calendar_month_three_plus_before(window_rows, target_date, prev_month)
    in_day_range = start_day <= target_day <= end_day
    month_has_room = current_three < max(avg_three, prev_month_three)
    range_text = "在範圍內" if in_day_range else "不在範圍內"

    if in_day_range and month_has_room:
        return UPGRADE_QUOTA, (
            "原因：\n"
            f"下期日期：{target_month}月{target_day}日\n"
            f"窗口期 >=3球 日期範圍：{recent_three_plus_range_text(window_rows)}\n"
            f"採用判斷範圍：最近{UPGRADE_RECENT_RANGE_COUNT}次，每月 {start_day}日-{end_day}日\n"
            f"{target_month}月{target_day}日：{range_text}\n"
            f"{prev_month}月已出 >=3球：{prev_month_three}期\n"
            f"{target_month}月已出 >=3球：{current_three}期\n"
            f"窗口期每月平均 >=3球：{avg_three:.2f}期\n"
            f"判斷：仍未達平均，建議升級 {UPGRADE_QUOTA}球"
        )

    return BASE_QUOTA, (
        "原因：\n"
        f"下期日期：{target_month}月{target_day}日\n"
        f"窗口期 >=3球 日期範圍：{recent_three_plus_range_text(window_rows)}\n"
        f"採用判斷範圍：最近{UPGRADE_RECENT_RANGE_COUNT}次，每月 {start_day}日-{end_day}日\n"
        f"{target_month}月{target_day}日：{range_text}\n"
        f"{prev_month}月已出 >=3球：{prev_month_three}期\n"
        f"{target_month}月已出 >=3球：{current_three}期\n"
        f"窗口期每月平均 >=3球：{avg_three:.2f}期\n"
        f"判斷：未符合升級條件，維持基本 {BASE_QUOTA}球"
    )


def print_query_setting() -> None:
    """打印模型設定。"""
    print("----- fortune_keys 2球基本盤，日期範圍升級3球 -----")
    print(f"運作模式：{MODE}")
    print(f"基本配額：{BASE_QUOTA}球")
    print(f"升級配額：{UPGRADE_QUOTA}球")
    print(
        f"升級條件：最近{UPGRADE_RECENT_RANGE_COUNT}次 >={UPGRADE_MATCH_COUNT} 球日期範圍 "
        "+ 目標月份未達上月/平均"
    )
    print()


def print_month_distribution(rows: list[DrawRow], title: str) -> None:
    """打印 1-12 月 >=3 球分佈統計。"""
    counter = calendar_month_three_plus_counts(rows)
    avg = rounded_month_average_three_plus(rows)
    over_months = [month for month in range(1, 13) if counter[month] > avg]
    empty_months = [month for month in range(1, 13) if counter[month] == 0]
    total_three = sum(counter.values())

    print(f"=== [1-9] 固定 [{UPGRADE_QUOTA}] 球，1-12 月分佈統計 ===")
    print(f"{title}，[1-9] 開獎期 >={UPGRADE_MATCH_COUNT} 球以上：{total_three} 期")
    print(f"每月平均：{avg} 期")
    print("月份分佈：")
    for month in range(1, 13):
        print(f"{month:>2}月：{counter[month]} 期")
    print("超過平均月份：" + (", ".join(f"{month}月" for month in over_months) if over_months else "沒有"))
    print("沒有 >=3 球月份：" + (", ".join(f"{month}月" for month in empty_months) if empty_months else "沒有"))
    print()


def print_backtest_range_summary(
    draws: list[DrawRow],
    first_check_index: int,
    latest_index: int,
    window_count: int,
    backtest_count: int,
) -> None:
    """打印真實滾動回測整段前後邊界。"""
    first_window_index = max(0, first_check_index - window_count)
    print(f"====== 真實滾動回測：窗口期={window_count}，回測期={backtest_count} ======")
    print(
        f"----- 前 {backtest_count} 期 {draws[first_check_index]['date']} 核對，"
        f"至最後一期 {draws[latest_index]['date']} -----"
    )
    print(f"整段分析邊界：{draws[first_window_index]['date']} 至 {draws[latest_index]['date']}")
    print()


def print_range_year_month_table(rows: list[DrawRow], csv_path: Path) -> None:
    """打印整段範圍內的年份 x 月份分佈表。"""
    distribution = year_month_three_plus_distribution(rows)
    save_year_month_distribution_csv(distribution, csv_path)
    print_year_month_distribution_csv(csv_path)
    print(f"整段月份分佈 CSV：{csv_path}")
    print()


def print_backtest_summary(check_rows: list[DrawRow], quota_rows: list[tuple[DrawRow, int, str]]) -> None:
    """打印 2球基本盤與日期升級3球的回測統計。"""
    total_count = len(check_rows)
    actual_counts = Counter(fortune_count(row) for row in check_rows)
    base_hits = sum(1 for row in check_rows if fixed_quota_hit(BASE_QUOTA, fortune_count(row)))
    model_hits = sum(1 for row, quota, _ in quota_rows if fixed_quota_hit(quota, fortune_count(row)))
    upgrade_rows = [(row, quota, reason) for row, quota, reason in quota_rows if quota == UPGRADE_QUOTA]
    upgrade_counts = Counter(fortune_count(row) for row, _, _ in upgrade_rows)
    caught_three = sum(count for balls, count in upgrade_counts.items() if balls == 3)
    still_over = sum(count for balls, count in upgrade_counts.items() if balls > UPGRADE_QUOTA)
    extra_quota_ok = sum(count for balls, count in upgrade_counts.items() if 1 <= balls < UPGRADE_QUOTA)
    zero_fail = upgrade_counts[0]

    print("----- [1-9] 固定2球 vs 日期升級3球 -----")
    print(f"回測期數：{total_count} 期")
    for balls in range(6, -1, -1):
        if balls >= 5 and actual_counts[balls] == 0:
            continue
        if balls == 0:
            print(f"= 0 球：{actual_counts[balls]} 期")
        else:
            print(f"有 {balls:>2}球：{actual_counts[balls]} 期")

    print(
        f"固定配 {BASE_QUOTA} 球："
        f"命中 {base_hits}/{total_count} 期，{base_hits / total_count * 100:.1f}%"
    )
    print(
        f"日期升級模型："
        f"命中 {model_hits}/{total_count} 期，{model_hits / total_count * 100:.1f}%"
    )
    print(f"升級發 {UPGRADE_QUOTA} 球：{len(upgrade_rows)} 期")
    print(f"升級後捕捉 3球：{caught_three} 期")
    print(f"升級後多發但仍命中 1-2球：{extra_quota_ok} 期")
    print(f"升級後 0球失敗：{zero_fail} 期")
    print(f"升級後仍超配額：{still_over} 期")


def build_rolling_snapshot(
    check_row: DrawRow,
    window_rows: list[DrawRow],
    quota: int,
    reason: str,
) -> RollingSnapshot:
    """建立單一期真實滾動回測 JSON 快照。"""
    actual_count = fortune_count(check_row)
    start_day, end_day = three_plus_day_range(window_rows)
    avg_three = month_average_three_plus(window_rows)

    return {
        "check_date": check_row["date"],
        "window_start": window_rows[0]["date"] if window_rows else "",
        "window_end": window_rows[-1]["date"] if window_rows else "",
        "target_year": year_key(check_row["date"]),
        "target_month": month_number(check_row["date"]),
        "target_day": day_of_month(check_row["date"]),
        "base_quota": BASE_QUOTA,
        "suggest_quota": quota,
        "actual_count": actual_count,
        "hit": fixed_quota_hit(quota, actual_count),
        "reason": reason,
        "three_plus_day_range": {
            "start_day": start_day,
            "end_day": end_day,
        },
        "month_average_three_plus": avg_three,
        "year_month_distribution": year_month_three_plus_distribution(window_rows),
    }


def quota_result_text(snapshot: RollingSnapshot) -> str:
    """顯示配額核對結果。"""
    actual_count = snapshot["actual_count"]
    quota = snapshot["suggest_quota"]
    if snapshot["hit"]:
        return "命中"
    if actual_count == 0:
        return "失敗，0球"
    if actual_count > quota:
        return "失敗，超配額"
    return "失敗"


def print_year_month_distribution(distribution: dict[str, dict[str, int]]) -> None:
    """打印年份 x 月份分佈表。"""
    years = sorted(distribution.keys())
    if not years:
        return

    print("月份分佈：")
    print("月份    " + "    ".join(years))
    for month in range(1, 13):
        values = [distribution[year].get(str(month), 0) for year in years]
        value_text = "    ".join(f"{value:>4}" for value in values)
        print(f"{month:>2}月    {value_text}")


def print_rolling_snapshot(snapshot: RollingSnapshot, window_count: int, backtest_count: int) -> None:
    """打印單一期真實滾動回測快照。"""
    csv_path = month_distribution_csv_path(snapshot["check_date"])
    save_year_month_distribution_csv(snapshot["year_month_distribution"], csv_path)

    print(f"====== 真實滾動回測：窗口期={window_count}，回測期={backtest_count} ======")
    print()
    print(f"----- {snapshot['check_date']} 核對 -----")
    print(f"窗口期：{snapshot['window_start']} 至 {snapshot['window_end']}")
    print(f"下期月份：{snapshot['target_month']}月")
    print(f"建議配額：{snapshot['suggest_quota']}球")
    print(f"實際開出：{snapshot['actual_count']}球")
    print(f"結果：{quota_result_text(snapshot)}")
    print()
    print_year_month_distribution_csv(csv_path)
    print(f"月份分佈 CSV：{csv_path}")


def run_backtest(draws: list[DrawRow]) -> None:
    """執行 backtest：每期基本2球，日期範圍訊號升級3球。"""
    latest_index = len(draws) - 1
    for backtest_count in BACKTEST_DRAW_COUNT_LIST:
        for window_count in WINDOW_DRAW_COUNT_LIST:
            # 回溯 N 期以「間隔」理解，包含起點與最新期兩端。
            # 例如最新 index=2597、回測期=200，第一核對 index=2397。
            first_check_index = max(window_count, latest_index - backtest_count)
            check_indices = list(range(first_check_index, latest_index + 1))
            check_rows = [draws[index] for index in check_indices]
            quota_rows: list[tuple[DrawRow, int, str]] = []
            snapshots: list[RollingSnapshot] = []

            for check_index in check_indices:
                check_row = draws[check_index]
                window_rows = draws[max(0, check_index - window_count):check_index]
                quota, reason = predict_quota(window_rows, check_row["date"])
                quota_rows.append((check_row, quota, reason))
                snapshots.append(build_rolling_snapshot(check_row, window_rows, quota, reason))

            print_backtest_summary(check_rows, quota_rows)
            if PRINT_RANGE_YEAR_MONTH_TABLE:
                first_window_index = max(0, first_check_index - window_count)
                range_rows = draws[first_window_index:latest_index + 1]
                print()
                print_backtest_range_summary(draws, first_check_index, latest_index, window_count, backtest_count)
                range_csv_path = range_month_distribution_csv_path(backtest_count, window_count)
                print_range_year_month_table(range_rows, range_csv_path)

            if PRINT_FIRST_ROLLING_SNAPSHOT and snapshots:
                print()
                print_rolling_snapshot(snapshots[0], window_count, backtest_count)

            if PRINT_LAST_ROLLING_SNAPSHOT and snapshots:
                print()
                print_rolling_snapshot(snapshots[-1], window_count, backtest_count)

            if SAVE_ANALYSIS_JSON:
                json_data = {
                    "mode": MODE,
                    "backtest_count": backtest_count,
                    "window_count": window_count,
                    "base_quota": BASE_QUOTA,
                    "upgrade_quota": UPGRADE_QUOTA,
                    "upgrade_match_count": UPGRADE_MATCH_COUNT,
                    "snapshot_count": len(snapshots),
                    "snapshots": snapshots,
                }
                save_json(json_data, JSON_OUTPUT)

            if PRINT_BACKTEST_DETAIL:
                print()
                print("----- 回測逐期明細 -----")
                for row, quota, reason in quota_rows:
                    actual = fortune_count(row)
                    result = "命中" if fixed_quota_hit(quota, actual) else "失敗"
                    print(f"{row['date']}：發{quota}球，實際{actual}球，{result}，{reason}")
            print()


def run_predict(draws: list[DrawRow]) -> None:
    """用最後窗口期預測下一期配額。"""
    next_draw_date = read_next_draw_date()
    latest_row = draws[-1]
    target_date = next_draw_date or latest_row["date"]
    for window_count in WINDOW_DRAW_COUNT_LIST:
        window_rows = draws[-window_count:]
        quota, reason = predict_quota(window_rows, target_date)
        print(f"====== predict mode，窗口期={window_count} ======")
        print(f"窗口期={window_count}，{window_rows[0]['date']} 至 {target_date}")
        print_reference_month_distribution(window_count)
        print("----- 最近100期窗口月份分佈 -----")
        print_month_distribution(window_rows, f"窗口期={window_count} 期")
        print(f"最新日期：{latest_row['date']}，下期開獎日期：{target_date}")
        target_month = month_number(target_date)
        month_counter = calendar_month_three_plus_counts(window_rows)
        print(f"下期月份：{target_month}月，窗口期同月份 >=3球：{month_counter[target_month]} 期")
        print(f"建議 1-9 發球配額：{quota} 球")
        print(reason)
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
