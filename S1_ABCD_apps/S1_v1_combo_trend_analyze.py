from pathlib import Path
import csv
from typing import Optional, TypedDict


'''
S1 組合走趨分析：獨立腳本，不依賴其它程式。

用途：
1. 追蹤 ABC / BCD / ABCD 大組合是否連續合條件。
2. 找出連續型態、間斷期、回補訊號。
3. 給出投注提示：單式 / 複式 7 字 / 多組合貼拖 / 聰明組合 12 球。
'''

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
M6_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"
M3_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M3_lotto_prize_results.csv"
M4_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M4_lotto_prize_summary.csv"
OUTPUT_DIR = CURRENT_DIR / "backtest_pred_data"
TREND_BACKTEST_CSV = OUTPUT_DIR / "trend_backtest.csv"
TREND_PRED_CSV = OUTPUT_DIR / "trend_pred.csv"


VERSION = "S1_v1 1-40 Trend Predict Analyze"
MODE = "backtest" # "backtest" 不包含核對期；"predict" 包含最後一期已開號。
BACKTEST_DRAW_COUNT_LIST = [1]
WINDOW_DRAW_COUNT_LIST = [10]
ABCD_POOL_MIN_FUND = 20_000_000.0

# LOTTO_LIST=True 時，所選組別號碼合併成一個 [] 顯示；False 則按 A/B/C/D 分組顯示。
''' 
False = 近 10期:2026-08-27，[12,17]，[25,31]，[*35] /> 4.5 球
True  = 近 10期:2026-08-27，[12,17,25,31,*35] /> 4.5 球
'''
LOTTO_LIST = False

# 走勢提示門檻。
RECENT_WINDOW_SHORT = 5 # 近期短窗口：統計最近 5 期合條件次數。
RECENT_WINDOW_LONG = 10 # 近期長窗口：統計最近 10 期合條件次數，用於走勢分數。
HOT_STREAK_STRONG = 3 # 強勢連續門檻：最近連續合條件達 3 期即判斷偏強。
RECENT5_STRONG_COUNT = 4 # 近 5 期強勢門檻：近 5 期中 4 期合條件即判斷偏強。
RECENT5_WEAK_COUNT = 2 # 近 5 期弱勢門檻：近 5 期合條件少於或等於 2 期即判斷偏弱。
BREAK_STREAK_STOP = 2 # 中斷門檻：最近連續 2 期不合條件即判斷走勢已斷。

GROUPS = {
    1: ("A", "1-9", 1, 9),
    2: ("B", "10-20", 10, 20),
    3: ("C", "21-31", 21, 31),
    4: ("D", "32-40", 32, 40),
}

class DrawRow(TypedDict):
    date: str
    nums: list[int]
    special: Optional[int]


class TrendGroupConfig(TypedDict):
    group_ids: tuple[int, ...]
    take_count: int
    match_mode: str
    note: str


class PrizeFundInfo(TypedDict):
    snowball: float
    estimated_first_prize_fund: float


class NextDrawInfo(TypedDict):
    next_draw_date: str
    next_draw_prize_fund: float


class BacktestTrendStats(TypedDict):
    total: int
    hit: int
    failed: int
    selected_counts: dict[str, int]
    hit_counts: dict[str, int]


TREND_GROUP_SETS: dict[str, TrendGroupConfig] = {
    "ABC": {
        "group_ids": (1, 2, 3),
        "take_count": 4,
        "match_mode": ">=",
        "note": "31 球池，>=4 球追蹤 5 獎型態",
    },
    "BCD": {
        "group_ids": (2, 3, 4),
        "take_count": 4,
        "match_mode": ">=",
        "note": "31 球池，>=4 球追蹤 5 獎型態",
    },
    "ABCD": {
        "group_ids": (1, 2, 3, 4),
        "take_count": 5,
        "match_mode": ">=",
        "note": "40 球池，>=5 球追蹤大池型態",
    },
}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    ''' 讀取 CSV 並清理欄位名稱與文字空白。 '''
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


def write_csv_rows(path: Path, rows: list[dict[str, object]]) -> None:
    ''' 寫出 CSV；使用 utf-8-sig 方便試算表直接讀中文。 '''
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return

    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def to_int(value: object, default: int = 0) -> int:
    ''' 安全轉換數值為 int，失敗時回傳 default。 '''
    if not isinstance(value, (int, float, str)):
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def to_money(value: object, default: float = 0.0) -> float:
    ''' 安全轉換金額文字為 float。 '''
    if not isinstance(value, (int, float, str)):
        return default
    try:
        text = str(value).replace(",", "").replace("$", "").strip()
        return float(text)
    except (TypeError, ValueError):
        return default


def parse_m6_row(row: dict[str, str]) -> DrawRow:
    ''' 將 M6 原始 CSV 一行轉成標準 DrawRow。 '''
    special = to_int(row.get("N7"))
    return {
        "date": row.get("nDdate", ""),
        "nums": [to_int(row.get(f"N{index}")) for index in range(1, 7)],
        "special": special if 1 <= special <= 49 else None,
    }


def read_draws() -> list[DrawRow]:
    ''' 讀取所有有效歷史開獎紀錄。 '''
    return [row for row in [parse_m6_row(raw) for raw in read_csv_rows(M6_CSV)] if row["date"]]


def read_prize_fund_info() -> PrizeFundInfo:
    ''' 從 M3 讀取多寶 / 金多寶與估計頭獎基金。 '''
    info: PrizeFundInfo = {
        "snowball": 0.0,
        "estimated_first_prize_fund": 0.0,
    }
    if not M3_CSV.exists():
        return info

    with M3_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        for row in reader:
            if len(row) < 2:
                continue
            label = row[0].strip()
            amount = to_money(row[1])
            if label == "多寶 / 金多寶":
                info["snowball"] = amount
            elif label == "估計頭獎基金":
                info["estimated_first_prize_fund"] = amount
    return info


def read_historical_prize_funds() -> dict[str, float]:
    ''' 從 M4 讀取每個 next_draw_date 的估計頭獎基金。 '''
    if not M4_CSV.exists():
        return {}

    funds: dict[str, float] = {}
    for row in read_csv_rows(M4_CSV):
        next_draw_date = row.get("next_draw_date", "")
        if not next_draw_date:
            continue
        funds[next_draw_date] = to_money(row.get("next_draw_prize_fund"))
    return funds


def read_next_draw_infos() -> dict[str, NextDrawInfo]:
    ''' 從 M4 讀取每個 last_draw_date 對應的下期日期與估計頭獎基金。 '''
    if not M4_CSV.exists():
        return {}

    infos: dict[str, NextDrawInfo] = {}
    for row in read_csv_rows(M4_CSV):
        last_draw_date = row.get("last_draw_date", "")
        next_draw_date = row.get("next_draw_date", "")
        if not last_draw_date or not next_draw_date:
            continue
        infos[last_draw_date] = {
            "next_draw_date": next_draw_date,
            "next_draw_prize_fund": to_money(row.get("next_draw_prize_fund")),
        }
    return infos


def is_abcd_pool_fund_eligible(prize_fund: PrizeFundInfo) -> bool:
    ''' 判斷是否達到採用 ABCD 全候選池的多寶/基金門檻。 '''
    return (
        prize_fund["snowball"] >= ABCD_POOL_MIN_FUND
        or prize_fund["estimated_first_prize_fund"] >= ABCD_POOL_MIN_FUND
    )


def is_abcd_pool_amount_eligible(amount: float) -> bool:
    ''' 判斷單一基金金額是否達到採用 ABCD 全候選池門檻。 '''
    return amount >= ABCD_POOL_MIN_FUND


def format_group_ids(group_ids: tuple[int, ...]) -> str:
    ''' 格式化組別 ID。 '''
    return "(" + ", ".join(str(group_id) for group_id in group_ids) + ")"


def format_nums(nums: list[int], special: Optional[int] = None) -> str:
    ''' 格式化號碼列表，特號以 *號碼 放在最後。 '''
    parts = [str(num) for num in nums]
    if special is not None:
        parts.append(f"*{special}")
    return "[" + ",".join(parts) + "]"


def selected_group_nums(row: DrawRow, group_id: int) -> tuple[list[int], Optional[int]]:
    ''' 取得某一期在指定 A/B/C/D 組內的正號與特號。 '''
    _code, _name, start_num, end_num = GROUPS[group_id]
    nums = sorted(num for num in row["nums"] if start_num <= num <= end_num)
    special = row["special"]
    group_special = special if special is not None and start_num <= special <= end_num else None
    return nums, group_special


def pool_lotto_text(row: DrawRow, group_ids: tuple[int, ...]) -> str:
    ''' 依 LOTTO_LIST 格式化大組合池開獎號。 '''
    if LOTTO_LIST:
        return format_nums(pool_nums(row, group_ids), pool_special(row, group_ids))

    return "，".join(
        format_nums(*selected_group_nums(row, group_id))
        for group_id in group_ids
    )


def is_matched(count: int, take_count: int, match_mode: str) -> bool:
    ''' 判斷球數是否符合追蹤條件。 '''
    if match_mode == "==":
        return count == take_count
    if match_mode == "<=":
        return count <= take_count
    return count >= take_count


def selected_group_ranges(group_ids: tuple[int, ...]) -> list[tuple[int, int]]:
    ''' 取得選中大組合的號碼範圍。 '''
    return [(GROUPS[group_id][2], GROUPS[group_id][3]) for group_id in group_ids]


def pool_nums(row: DrawRow, group_ids: tuple[int, ...]) -> list[int]:
    ''' 取得某期在大組合池內的正號。 '''
    ranges = selected_group_ranges(group_ids)
    nums = [
        num
        for num in row["nums"]
        if any(start_num <= num <= end_num for start_num, end_num in ranges)
    ]
    return sorted(nums)


def pool_special(row: DrawRow, group_ids: tuple[int, ...]) -> Optional[int]:
    ''' 取得某期在大組合池內的特號。 '''
    special = row["special"]
    if special is None:
        return None
    for start_num, end_num in selected_group_ranges(group_ids):
        if start_num <= special <= end_num:
            return special
    return None


def pool_ball_count(row: DrawRow, group_ids: tuple[int, ...]) -> int:
    ''' 計算大組合池每期開球總數；特號以 1 球計入。 '''
    return len(pool_nums(row, group_ids)) + (1 if pool_special(row, group_ids) is not None else 0)


def pool_desc(group_ids: tuple[int, ...]) -> str:
    ''' 格式化大組合說明。 '''
    codes = "".join(GROUPS[group_id][0] for group_id in group_ids)
    start_num = min(GROUPS[group_id][2] for group_id in group_ids)
    end_num = max(GROUPS[group_id][3] for group_id in group_ids)
    return f"{codes} = {start_num}-{end_num}"


def streak_from_end(values: list[bool], expected: bool) -> int:
    ''' 計算最近連續 True 或 False 期數。 '''
    count = 0
    for value in reversed(values):
        if value != expected:
            break
        count += 1
    return count


def longest_hot_streak(values: list[bool]) -> int:
    ''' 計算最長連續合條件期數。 '''
    longest = 0
    current = 0
    for value in values:
        if value:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def has_recent_rebound(values: list[bool]) -> bool:
    ''' 判斷最近是否出現中斷後回補，例如 -H 或 --H。 '''
    if len(values) < 2 or not values[-1]:
        return False
    return not values[-2] or (len(values) >= 3 and not values[-3])


def trend_score(values: list[bool]) -> float:
    ''' 計算簡單走勢分數。 '''
    hot_streak = streak_from_end(values, True)
    break_streak = streak_from_end(values, False)
    recent5 = sum(values[-RECENT_WINDOW_SHORT:])
    recent10 = sum(values[-RECENT_WINDOW_LONG:])
    return hot_streak * 2 + recent5 + recent10 * 0.5 - break_streak * 2


def trend_level(values: list[bool]) -> str:
    ''' 依近期連續、近 5 期、間斷狀態判斷強弱。 '''
    hot_streak = streak_from_end(values, True)
    break_streak = streak_from_end(values, False)
    recent5 = sum(values[-RECENT_WINDOW_SHORT:])
    if break_streak >= BREAK_STREAK_STOP:
        return "已斷"
    if hot_streak >= HOT_STREAK_STRONG or recent5 >= RECENT5_STRONG_COUNT:
        return "強"
    if recent5 <= RECENT5_WEAK_COUNT:
        return "弱"
    if has_recent_rebound(values):
        return "中，間斷後回補"
    return "中"


def bet_advice(level: str) -> str:
    ''' 依走勢強弱給出投注提示。 '''
    if level == "強":
        return "連續型態組合出現，可投注多組合貼拖，或聰明組合 12 個號碼投注。"
    if level.startswith("中"):
        return "走勢中，可用複式 7-9 字或小組合追蹤。"
    if level == "弱":
        return "走勢偏弱，只投注單式，或等待下一期確認。"
    return "連續型態組合已斷，只投注單式 或複式 7 字。"


def next_draw_bet_advice(name: str, level: str) -> str:
    ''' 依組合池與走勢強弱，產生下期投注走趨建議。 '''
    if name in ("ABC", "BCD"):
        if level == "強":
            return f"{name}：走勢強，可用單/複式，3+3+3 = 9 球以膽拖投注。"
        if level.startswith("中"):
            return f"{name}：走勢中，可小注單/複式，3+3+3 = 9 球以膽拖追蹤。"
        return f"{name}：走勢{level}，只投注單式 或複式 7 字，不建議 9 球膽拖加碼。"

    if level == "強":
        return f"{name}：走勢強，可用 強 12 球- 膽拖，或聰明組合。"
    if level.startswith("中"):
        return f"{name}：走勢中，可用 12 球膽拖小注追蹤，或降低組合注數。"
    return f"{name}：走勢{level}，只投注單式 或複式 7 字，暫不建議 12 球組合。"


def candidate_pool_name(name: str) -> str:
    ''' 格式化候選池投注名稱。 '''
    if name in ("ABC", "BCD"):
        return f"{name} 9 球膽拖池"
    return "ABCD 12 球全候選池"


def trend_sequence(values: list[bool]) -> str:
    ''' 將走勢轉成 H / - 序列。 '''
    return "".join("H" if value else "-" for value in values)


def print_window_rows(
    window_rows: list[tuple[int, DrawRow]],
    target_index: int,
    group_ids: tuple[int, ...],
    take_count: int,
    match_mode: str,
) -> list[bool]:
    ''' 列印窗口期每期走勢，並回傳合條件序列。 '''
    matches: list[bool] = []
    for row_index, row in window_rows:
        rank = target_index - row_index + 1
        nums = pool_nums(row, group_ids)
        special = pool_special(row, group_ids)
        count = len(nums) + (1 if special is not None else 0)
        matched = is_matched(count, take_count, match_mode)
        matches.append(matched)
        mark = "H" if matched else "-"
        result_text = f"{pool_lotto_text(row, group_ids)} /> {count} 球" if matched else ""
        print(f"近 {rank:>2}期：{row['date']}，{mark}，{result_text}")
    return matches


def print_trend_summary(values: list[bool]) -> None:
    ''' 列印連續走勢統計與系統提示。 '''
    hot_streak = streak_from_end(values, True)
    break_streak = streak_from_end(values, False)
    recent5_count = sum(values[-RECENT_WINDOW_SHORT:])
    recent10_count = sum(values[-RECENT_WINDOW_LONG:])
    longest_streak = longest_hot_streak(values)
    level = trend_level(values)
    print("/> -------------")
    print(f"走勢序列：{trend_sequence(values)}")
    print(f"最近連續合條件：{hot_streak}期")
    print(f"最近連續中斷：{break_streak}期")
    print(f"最近{RECENT_WINDOW_SHORT}期合條件：{recent5_count}/{min(RECENT_WINDOW_SHORT, len(values))}")
    print(f"最近{RECENT_WINDOW_LONG}期合條件：{recent10_count}/{min(RECENT_WINDOW_LONG, len(values))}")
    print(f"最長連續合條件：{longest_streak}期")
    print(f"走勢分數：{trend_score(values):.1f}")
    print(f"走勢判斷：{level}")
    print(f"系統提示：{bet_advice(level)}")


def trend_matches_for_rows(
    window_rows: list[tuple[int, DrawRow]],
    group_ids: tuple[int, ...],
    take_count: int,
    match_mode: str,
) -> list[bool]:
    ''' 只計算窗口期走勢序列，不列印。 '''
    return [
        is_matched(pool_ball_count(row, group_ids), take_count, match_mode)
        for _row_index, row in window_rows
    ]


def analyze_trend_groups(
    window_rows: list[tuple[int, DrawRow]],
) -> tuple[dict[str, str], dict[str, float]]:
    ''' 回傳各組合池的走勢判斷與分數。 '''
    trend_levels: dict[str, str] = {}
    trend_scores: dict[str, float] = {}
    for name, config in TREND_GROUP_SETS.items():
        values = trend_matches_for_rows(
            window_rows,
            config["group_ids"],
            config["take_count"],
            config["match_mode"],
        )
        trend_levels[name] = trend_level(values)
        trend_scores[name] = trend_score(values)
    return trend_levels, trend_scores


def select_trend_pool(trend_scores: dict[str, float], abcd_eligible: bool) -> str:
    ''' 從 ABC / BCD / ABCD 三選一；ABCD 需先達基金門檻。 '''
    eligible_names = [
        name
        for name in TREND_GROUP_SETS
        if name != "ABCD" or abcd_eligible
    ]
    return max(eligible_names, key=lambda name: trend_scores.get(name, -9999.0))


def selected_pool_hit(check_row: DrawRow, selected_name: str) -> bool:
    ''' 用核對期實際開獎，判斷三選一候選池是否命中自身條件。 '''
    config = TREND_GROUP_SETS[selected_name]
    count = pool_ball_count(check_row, config["group_ids"])
    return is_matched(count, config["take_count"], config["match_mode"])


def selected_pool_check_text(check_row: DrawRow, selected_name: str) -> str:
    ''' 格式化核對期命中結果。 '''
    config = TREND_GROUP_SETS[selected_name]
    group_ids = config["group_ids"]
    nums = pool_nums(check_row, group_ids)
    special = pool_special(check_row, group_ids)
    count = len(nums) + (1 if special is not None else 0)
    matched = is_matched(count, config["take_count"], config["match_mode"])
    result = "命中" if matched else "失敗"
    return (
        f"核對期：{check_row['date']}，{selected_name} 開獎 {pool_lotto_text(check_row, group_ids)} "
        f"/> {count} 球，條件 {config['match_mode']} {config['take_count']} 球，{result}"
    )


def trend_values_for_name(window_rows: list[tuple[int, DrawRow]], name: str) -> list[bool]:
    ''' 取得指定組合池在窗口期的走勢序列。 '''
    config = TREND_GROUP_SETS[name]
    return trend_matches_for_rows(
        window_rows,
        config["group_ids"],
        config["take_count"],
        config["match_mode"],
    )


def build_backtest_trend_record(
    draws: list[DrawRow],
    check_index: int,
    backtest_count: int,
    window_count: int,
    backtest_index: int,
    total_backtest_count: int,
    historical_funds: dict[str, float],
) -> dict[str, object]:
    ''' 建立單一期回測三選一核對 CSV record。 '''
    window_start_index = max(0, check_index - window_count)
    window_rows = [
        (row_index, row)
        for row_index, row in enumerate(draws[window_start_index:check_index], start=window_start_index)
    ]
    trend_levels, trend_scores = analyze_trend_groups(window_rows)
    check_row = draws[check_index]
    historical_fund = historical_funds.get(check_row["date"], 0.0)
    abcd_eligible = is_abcd_pool_amount_eligible(historical_fund)
    selected_name = select_trend_pool(trend_scores, abcd_eligible)
    config = TREND_GROUP_SETS[selected_name]
    nums = pool_nums(check_row, config["group_ids"])
    special = pool_special(check_row, config["group_ids"])
    check_count = len(nums) + (1 if special is not None else 0)
    hit = is_matched(check_count, config["take_count"], config["match_mode"])

    return {
        "date": check_row["date"],
        "系統選mode": selected_name,
        "球膽拖池": 12 if selected_name == "ABCD" else 9,
        "走勢分數": f"{trend_scores.get(selected_name, 0.0):.1f}",
        "走勢判斷": trend_levels.get(selected_name, "弱"),
        "開獎號": format_nums(nums, special),
        "條件>=": config["take_count"],
        "核對預測": "中" if hit else "不中",
    }


def build_predict_trend_record(
    draws: list[DrawRow],
    window_count: int,
    next_draw_infos: dict[str, NextDrawInfo],
) -> dict[str, object]:
    ''' 建立下期預測三選一 CSV record。 '''
    latest_index = len(draws) - 1
    window_start_index = max(0, latest_index - window_count + 1)
    window_rows = [
        (row_index, row)
        for row_index, row in enumerate(draws[window_start_index:latest_index + 1], start=window_start_index)
    ]
    trend_levels, trend_scores = analyze_trend_groups(window_rows)
    latest_row = draws[latest_index]
    next_draw_info = next_draw_infos.get(latest_row["date"])
    prize_fund = read_prize_fund_info()
    abcd_eligible = is_abcd_pool_fund_eligible(prize_fund)
    selected_name = select_trend_pool(trend_scores, abcd_eligible)

    return {
        "nextDraw date": next_draw_info["next_draw_date"] if next_draw_info else "",
        "pred_mode": selected_name,
        "走趨分析": "選 12 球 以膽拖投注" if selected_name == "ABCD" else "選 9 球 以膽拖投注",
        "走勢分數": f"{trend_scores.get(selected_name, 0.0):.1f}",
        "走勢判斷": trend_levels.get(selected_name, "弱"),
    }


def print_combo_trend_sections(
    window_rows: list[tuple[int, DrawRow]],
    target_index: int,
    mode: str,
    check_row: Optional[DrawRow] = None,
    next_draw_info: Optional[NextDrawInfo] = None,
    historical_fund: Optional[float] = None,
) -> None:
    ''' 列印各組合池的走趨分析區塊。 '''
    print("追蹤條件：各組合池獨立門檻，特號 N7 以 1 球計入")
    trend_levels: dict[str, str] = {}
    trend_scores: dict[str, float] = {}

    for name, config in TREND_GROUP_SETS.items():
        group_ids = config["group_ids"]
        take_count = config["take_count"]
        match_mode = config["match_mode"]
        note = config["note"]
        print()
        print(f"---------------- {name} {format_group_ids(group_ids)} 連續組合走趨 ----------------")
        print(f"追蹤組合：{pool_desc(group_ids)}")
        print(f"組合條件：每期合併分組總球數 {match_mode} {take_count} 球 (包括特號)")
        print(f"型態說明：{note}")
        values = print_window_rows(window_rows, target_index, group_ids, take_count, match_mode)
        print_trend_summary(values)
        trend_levels[name] = trend_level(values)
        trend_scores[name] = trend_score(values)
    if mode == "backtest":
        if check_row is None:
            raise ValueError("backtest 模式需要 check_row")
        print_backtest_check_summary(trend_levels, trend_scores, check_row, historical_fund or 0.0)
    else:
        print_next_draw_bet_summary(trend_levels, trend_scores, next_draw_info)
    print()


def print_backtest_check_summary(
    trend_levels: dict[str, str],
    trend_scores: dict[str, float],
    check_row: DrawRow,
    historical_fund: float,
) -> None:
    ''' 列印回測模式的核對期分組分析。 '''
    abcd_fund_eligible = is_abcd_pool_amount_eligible(historical_fund)
    selected_name = select_trend_pool(trend_scores, abcd_fund_eligible)

    print()
    print("---------------- 回測核對走趨總結 ----------------")
    if abcd_fund_eligible:
        print(f"核對期日期：{check_row['date']}；頭獎基金：{historical_fund:,.0f}；適合多組包圍投注。")
    else:
        print(f"核對期日期：{check_row['date']}；頭獎基金：{historical_fund:,.0f}；不宜包圍投注。")
    for name in TREND_GROUP_SETS:
        level = trend_levels.get(name, "弱")
        print(next_draw_bet_advice(name, level))
    print("/> -------------")
    print(
        f"系統三選一核對：{selected_name}，{candidate_pool_name(selected_name)}，"
        f"走勢分數 {trend_scores.get(selected_name, 0.0):.1f}，"
        f"走勢判斷：{trend_levels.get(selected_name, '弱')}"
    )
    print(selected_pool_check_text(check_row, selected_name))


def print_next_draw_bet_summary(
    trend_levels: dict[str, str],
    trend_scores: dict[str, float],
    next_draw_info: Optional[NextDrawInfo],
) -> None:
    ''' 列印下期投注走趨總結。 '''
    prize_fund = read_prize_fund_info()
    abcd_fund_eligible = is_abcd_pool_fund_eligible(prize_fund)
    selected_name = select_trend_pool(trend_scores, abcd_fund_eligible)

    print()
    print("---------------- 下期投注走趨總結 ----------------")
    if next_draw_info is not None:
        print(
            f"下期日期：{next_draw_info['next_draw_date']}；"
            f"M4 估計頭獎基金：{next_draw_info['next_draw_prize_fund']:,.0f}"
        )
    print(
        f"多寶 / 金多寶：{prize_fund['snowball']:,.0f}；"
        f"估計頭獎基金：{prize_fund['estimated_first_prize_fund']:,.0f}；"
        f"ABCD 門檻：{ABCD_POOL_MIN_FUND:,.0f}"
    )
    if abcd_fund_eligible:
        print("ABCD 全候選池資格：達標，可納入三選一。")
    else:
        print("ABCD 全候選池資格：未達標，只觀察，不納入三選一投注建議。")
    for name in TREND_GROUP_SETS:
        level = trend_levels.get(name, "弱")
        print(next_draw_bet_advice(name, level))
    print(
        f"系統三選一：{selected_name}，{candidate_pool_name(selected_name)}，"
        f"走勢分數 {trend_scores.get(selected_name, 0.0):.1f}，"
        f"走勢判斷：{trend_levels.get(selected_name, '弱')}"
    )


def print_combo_trend_window(
    draws: list[DrawRow],
    check_index: int,
    backtest_count: int,
    window_count: int,
    backtest_index: int,
    total_backtest_count: int,
    historical_funds: dict[str, float],
) -> None:
    ''' 列印單一回測期、單一窗口期的組合走趨分析。 '''
    display_backtest_index = total_backtest_count - backtest_index + 1
    window_start_index = max(0, check_index - window_count)
    window_rows = [
        (row_index, row)
        for row_index, row in enumerate(draws[window_start_index:check_index], start=window_start_index)
    ]

    print(
        f"======[回測 {display_backtest_index}] {VERSION} 組合走趨分析，"
        f"回測期= {backtest_count}，窗口期 = {window_count} ======"
    )
    print("backtest：窗口期不包括核對期，預留核對預測")
    check_row = draws[check_index]
    print_combo_trend_sections(
        window_rows,
        check_index - 1,
        "backtest",
        check_row=check_row,
        historical_fund=historical_funds.get(check_row["date"], 0.0),
    )


def init_backtest_trend_stats() -> BacktestTrendStats:
    ''' 初始化走趨三選一回測統計。 '''
    return {
        "total": 0,
        "hit": 0,
        "failed": 0,
        "selected_counts": {name: 0 for name in TREND_GROUP_SETS},
        "hit_counts": {name: 0 for name in TREND_GROUP_SETS},
    }


def update_backtest_trend_stats(
    stats: BacktestTrendStats,
    draws: list[DrawRow],
    check_index: int,
    window_count: int,
    historical_funds: dict[str, float],
) -> None:
    ''' 以單一期回測資料更新三選一預測命中統計。 '''
    window_start_index = max(0, check_index - window_count)
    window_rows = [
        (row_index, row)
        for row_index, row in enumerate(draws[window_start_index:check_index], start=window_start_index)
    ]
    if not window_rows:
        return

    _trend_levels, trend_scores = analyze_trend_groups(window_rows)
    check_row = draws[check_index]
    historical_fund = historical_funds.get(check_row["date"], 0.0)
    selected_name = select_trend_pool(
        trend_scores,
        is_abcd_pool_amount_eligible(historical_fund),
    )
    stats["total"] += 1
    stats["selected_counts"][selected_name] += 1
    if selected_pool_hit(check_row, selected_name):
        stats["hit"] += 1
        stats["hit_counts"][selected_name] += 1
    else:
        stats["failed"] += 1


def print_backtest_trend_stats(stats: BacktestTrendStats, window_count: int) -> None:
    ''' 打印三選一預測走趨回測統計。 '''
    total = stats["total"]
    hit = stats["hit"]
    failed = stats["failed"]
    hit_percent = (hit / total * 100) if total else 0

    print()
    print(f"---------------- 預測走趨回測統計，窗口期 = {window_count} ----------------")
    print(f"預測走趨命中 {hit} / {total} 期，({hit_percent:.0f} %)")
    for name in TREND_GROUP_SETS:
        print(f"{name} = {stats['hit_counts'][name]} / {total}")
    print(f"失敗預測 = {failed} / {total}")


def print_predict_window(
    draws: list[DrawRow],
    window_count: int,
    next_draw_infos: dict[str, NextDrawInfo],
) -> None:
    ''' 列印 predict 模式最後窗口期；包含最後一期已開號。 '''
    latest_index = len(draws) - 1
    window_start_index = max(0, latest_index - window_count + 1)
    window_rows = [
        (row_index, row)
        for row_index, row in enumerate(draws[window_start_index:latest_index + 1], start=window_start_index)
    ]

    print(f"====== {VERSION} 組合走趨分析，predict，窗口期 = {window_count} ======")
    print("predict：窗口期包含最後一期已開號，用於預測下一期")
    print_combo_trend_sections(
        window_rows,
        latest_index,
        "predict",
        next_draw_info=next_draw_infos.get(draws[latest_index]["date"]),
    )


def print_query_setting() -> None:
    ''' 打印本次執行的主要參數。 '''
    print(f"======Vol:{VERSION} 組合走趨分析 ======")
    print(f"運作模式：{MODE}")
    if MODE == "backtest":
        print(f"回測期列表：{BACKTEST_DRAW_COUNT_LIST}")
    print(f"窗口期列表：{WINDOW_DRAW_COUNT_LIST}")
    print("符合條件：各組合池獨立門檻，特號 N7 以 1 球計入")
    setting_parts: list[str] = []
    for name, config in TREND_GROUP_SETS.items():
        group_ids = config["group_ids"]
        take_count = config["take_count"]
        match_mode = config["match_mode"]
        setting_parts.append(f"{name}{format_group_ids(group_ids)} {match_mode}{take_count}")
    print("追蹤組合：" + "，".join(setting_parts))
    print()


def main() -> None:
    ''' 主流程。 '''
    draws = read_draws()
    if not draws:
        raise FileNotFoundError(f"找不到或未能讀取 M6：{M6_CSV}")

    print_query_setting()
    latest_index = len(draws) - 1
    if MODE == "backtest":
        historical_funds = read_historical_prize_funds()
        for backtest_count in BACKTEST_DRAW_COUNT_LIST:
            first_check_index = max(0, latest_index - backtest_count + 1)
            check_indices = range(first_check_index, latest_index + 1)
            total_backtest_count = len(check_indices)
            for window_count in WINDOW_DRAW_COUNT_LIST:
                stats = init_backtest_trend_stats()
                backtest_records: list[dict[str, object]] = []
                for backtest_index, check_index in enumerate(check_indices, start=1):
                    print_combo_trend_window(
                        draws,
                        check_index,
                        backtest_count,
                        window_count,
                        backtest_index,
                        total_backtest_count,
                        historical_funds,
                    )
                    backtest_records.append(
                        build_backtest_trend_record(
                            draws,
                            check_index,
                            backtest_count,
                            window_count,
                            backtest_index,
                            total_backtest_count,
                            historical_funds,
                        )
                    )
                    update_backtest_trend_stats(
                        stats,
                        draws,
                        check_index,
                        window_count,
                        historical_funds,
                    )
                print_backtest_trend_stats(stats, window_count)
                write_csv_rows(TREND_BACKTEST_CSV, backtest_records)
                print(f"回測預測資料已存檔：{TREND_BACKTEST_CSV}")
    elif MODE == "predict":
        next_draw_infos = read_next_draw_infos()
        pred_records: list[dict[str, object]] = []
        for window_count in WINDOW_DRAW_COUNT_LIST:
            print_predict_window(draws, window_count, next_draw_infos)
            pred_records.append(build_predict_trend_record(draws, window_count, next_draw_infos))
        write_csv_rows(TREND_PRED_CSV, pred_records)
        print(f"下期預測資料已存檔：{TREND_PRED_CSV}")
    else:
        raise ValueError('MODE 只能是 "backtest" 或 "predict"')


if __name__ == "__main__":
    main()
