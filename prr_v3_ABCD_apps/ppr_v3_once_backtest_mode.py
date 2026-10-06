from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import csv
import json
import random
from typing import Optional, TypedDict


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
M6_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"
M4_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M4_lotto_prize_summary.csv"
DATA_DIR = CURRENT_DIR / "data"
ONCE_DATA_DIR = DATA_DIR / "once"
BACKTEST_RECORD_CSV = ONCE_DATA_DIR / "ppr_v3_once_backtest_records.csv"
NEXT_DRAW_RECORD_CSV = ONCE_DATA_DIR / "ppr_v3_next_draw_bet_records.csv"
ABCD_WINDOW_HIT_SUMMARY_CSV = ONCE_DATA_DIR / "once_abcd_window_hit_summary.csv"
HIGH_FREQ_DAN_WINDOW_HIT_SUMMARY_CSV = ONCE_DATA_DIR / "once_high_freq_dan_window_hit_summary.csv"
JSON_DIR = CURRENT_DIR / "json"
WEIGHT_JSON = JSON_DIR / "ppr_v3_once_weight_trace.json"
BACKTEST_RESULT_JSON = JSON_DIR / "ppr_v3_once_backtest_results.json"
'''
這支程式，核心分析總結。
1， ABCD , 4 組查詢 窗口期開號，>= 1, 篩選出過往曾開出獎號。
2，條件查詢後，用遠近期數，按權重給累計球號 >= 1 次出配的球號打分。
3，總結出 ：
A，權重熱門號，ABCD
B，該組窗口期內 未出現球號 ，未出現球號：ABCD
C，將各組同期出現  >=2 次的 雙號或 3 球號分析，
C1 : 高頻膽號：一定要在窗口期內 >= 2,  出配超過 2 次，超過 2 球，可用權重排出先後。
C2: 高頻配腳號： 高頻膽的另一配腳，配腳排序先後，選取時，建議隨機，令各配腳都有機會入選配額。
D，最後考慮最近 1 期開號，避免投注 重復上一期開號。

所以同一個回測期，例如 2026-10-03，你跑 10 次，CSV 只會計算最後一次，不會累加 10 次。

----- (回測期 核對期=倒數第 20 期) 日期=2026-08-08, 窗口期 = [16, 18, 24, 36, 40] -----
----- ABCD 預測候選球：窗口期命中比較表 ----
統計內容如下：
----- ABCD 全部高頻膽號合併一注：窗口期命中比較表 ----
統計內容如下：
2，自動配額：窗口期16=A=3，B=6，C=5，D=2，合共16球；
窗口期18=A=4，B=5，C=5，D=2，合共16球；
窗口期24=A=3，B=5，C=6，D=2，合共16球
'''


# 1-6 重點參數。
MODE = "backtest"
# backtest mode：數值代表「倒數第 N 期」作唯一核對期，不是最近 N 期逐期回測。
BACKTEST_DRAW_COUNT_LIST = [1]
WINDOW_DRAW_COUNT_LIST = [13] 
# CSV 窗口命中統計只使用 JSON 內最近 N 個有效核對日期重算，避免太舊回測長期累加。
BACKTEST_WINDOW_HIT_DRAW = 50 # 50 /100 期
GROUP_RUN_LIST = [(1,), (2,), (3,), (4,)]
COMBINATION_TAKE_COUNT = 5
BIRTHDAY_NUM_MATCH_MODE = ">="

# 是否顯示每期新舊權重比較。
PRINT_WEIGHT_COMPARE = False

# 高頻膽號：合條件窗口結果中，同組配對出現超過門檻次數才列入。
PRINT_HIGH_FREQ_PAIR_ANALYSIS = True
HIGH_FREQ_MIN_PAIR_COUNT = 2 # 高頻膽號必須出現超過此次數。
HIGH_FREQ_DAN_TAKE = 5 # 高頻膽號顯示數量
HIGH_FREQ_PARTNER_TAKE = 9 # 高頻配腳號顯示數量

# 弱號：窗口期內只出現 1 次，可隨配額取得入選機會。
PRINT_WEAK_NUM_ANALYSIS = True
WEAK_NUM_TAKE = 1 # 每組最多抽取幾個弱號補入候選。
WEAK_NUM_RANDOM_SEED: Optional[int] = 20261003

# predict mode 最後投注分組顯示。
PRINT_PREDICT_BET_GROUPS = True

# backtest mode 額外統計：ABCD 全部高頻膽號合併成一組投注候選。
PRINT_HIGH_FREQ_DAN_BACKTEST = True


# A/B/C/D 每組基礎預測球數，預設 3 + 5 + 5 + 3 = 16 球。
BASE_GROUP_TAKE_COUNTS = {
    1: 3,  # A: 1-9 = 9 球 
    2: 5,  # B: 10-20 ＝ 11 球 
    3: 5,  # C: 21-31 ＝ 11 球
    4: 3,  # D: 32-40 ＝ 9 球 
}

AUTO_DISTRIBUTE_GROUP_TAKE = True # 是否按窗口條件統計自動調配 ABCD 配額。
AUTO_DISTRIBUTE_MAX_TRANSFER = 2 # 每期最多由最弱組轉給最強組的球數。
AUTO_DISTRIBUTE_MIN_GROUP_TAKE = 2 # 自動調配後單組最少保留球數。
AUTO_DISTRIBUTE_MIN_GAP_PERCENT = 10 # 強弱組窗口命中率差距達此百分點才調配。

RECENT_DRAW_SCORE_PENALTY = 1.0 # 最近一期出現號碼改為扣分，不再硬排除。
HIGH_FREQ_PARTNER_POOL_TAKE = 9 # 高頻配腳先取前 N 個強配腳。

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


class NumWeight(TypedDict):
    num: int
    count: int
    recent_score: float
    repeat_score: float
    score: float
    latest_rank: Optional[int]


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    """讀取 CSV 並清理欄名、欄值前後空白與 BOM。"""
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
    """將字串、整數或浮點數轉成 int；失敗時回傳預設值。"""
    if not isinstance(value, (int, float, str)):
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def parse_m6_row(row: dict[str, str]) -> DrawRow:
    """將 M6 CSV 單列資料轉成內部開獎資料格式。"""
    special = to_int(row.get("N7"))
    return {
        "date": row.get("nDdate", ""),
        "nums": [to_int(row.get(f"N{index}")) for index in range(1, 7)],
        "special": special if 1 <= special <= 49 else None,
    }


def read_draws() -> list[DrawRow]:
    """讀取 M6 歷史開獎資料，並排除沒有日期的列。"""
    return [row for row in [parse_m6_row(raw) for raw in read_csv_rows(M6_CSV)] if row["date"]]


def read_next_draw_date() -> str:
    """從 M4 摘要 CSV 讀取下一期開獎日期；沒有資料則回傳空字串。"""
    if not M4_CSV.exists():
        return ""
    rows = read_csv_rows(M4_CSV)
    return rows[-1].get("next_draw_date", "") if rows else ""


def format_nums(nums: list[int], special: Optional[int] = None) -> str:
    """將球號列表格式化為 [1,2,3]；特別號會以 * 標示。"""
    parts = [str(num) for num in nums]
    if special is not None:
        parts.append(f"*{special}")
    return "[" + ",".join(parts) + "]"


def format_ball_count(value: float) -> str:
    """格式化命中球數；整數不顯示小數，半球保留精簡格式。"""
    return str(int(value)) if value.is_integer() else f"{value:g}"


def total_candidate_count() -> int:
    """計算 ABCD 各組候選配額合計球數。"""
    return sum(BASE_GROUP_TAKE_COUNTS.values())


def format_group_quota(take_counts: Optional[dict[int, int]] = None) -> str:
    """格式化 ABCD 各組配額與總候選球數。"""
    counts = take_counts or BASE_GROUP_TAKE_COUNTS
    quota_parts = [f"{GROUPS[group_id][0]}={counts[group_id]}" for group_id in GROUPS]
    return "，".join(quota_parts) + f"，合共{sum(counts.values())}球"


def format_auto_distribute_status() -> str:
    """格式化自動配額開關與調配門檻。"""
    if not AUTO_DISTRIBUTE_GROUP_TAKE:
        return "自動配額：關閉，使用固定基礎配額"
    return (
        "自動配額：開啟，"
        f"強弱差距 >= {AUTO_DISTRIBUTE_MIN_GAP_PERCENT}% 時，"
        f"最多轉移 {AUTO_DISTRIBUTE_MAX_TRANSFER} 球，"
        f"每組最少 {AUTO_DISTRIBUTE_MIN_GROUP_TAKE} 球"
    )


def format_quota_adjustment(take_counts: dict[int, int]) -> str:
    """格式化本期實際配額相對固定基礎配額的變化。"""
    changes: list[str] = []
    for group_id in GROUPS:
        code = GROUPS[group_id][0]
        diff = take_counts[group_id] - BASE_GROUP_TAKE_COUNTS[group_id]
        if diff > 0:
            changes.append(f"{code}+{diff}")
        elif diff < 0:
            changes.append(f"{code}{diff}")
    return "調配變化：" + ("，".join(changes) if changes else "沒有變化")


def print_backtest_quota_header(take_counts_by_window: dict[int, dict[int, int]]) -> None:
    """打印回測標題下的固定配額與自動配額資訊。"""
    print(f"1，固定基礎配額：{format_group_quota()}")
    if not AUTO_DISTRIBUTE_GROUP_TAKE:
        print("2，自動配額：關閉，使用固定基礎配額")
        return

    unique_quota_texts = {
        format_group_quota(take_counts)
        for take_counts in take_counts_by_window.values()
    }
    if len(unique_quota_texts) == 1:
        print(f"2，自動配額：{next(iter(unique_quota_texts))}")
    else:
        quota_parts = [
            f"窗口期{window_count}={format_group_quota(take_counts)}"
            for window_count, take_counts in take_counts_by_window.items()
        ]
        print("2，自動配額：" + "；".join(quota_parts))
    print(
        f"   強弱差距 >= {AUTO_DISTRIBUTE_MIN_GAP_PERCENT}% 時，"
        f"最多轉移 {AUTO_DISTRIBUTE_MAX_TRANSFER} 球，"
        f"每組最少 {AUTO_DISTRIBUTE_MIN_GROUP_TAKE} 球"
    )


def group_nums(row: DrawRow, group_id: int) -> list[int]:
    """取出某期正號中落在指定 ABCD 組範圍內的球號。"""
    _code, _name, start_num, end_num = GROUPS[group_id]
    return sorted(num for num in row["nums"] if start_num <= num <= end_num)


def group_special(row: DrawRow, group_id: int) -> Optional[int]:
    """取出某期特別號是否落在指定 ABCD 組範圍內。"""
    _code, _name, start_num, end_num = GROUPS[group_id]
    special = row["special"]
    if special is None:
        return None
    return special if start_num <= special <= end_num else None


def display_ball_count(normal_count: int, special: Optional[int]) -> float:
    """計算顯示用球數；同組正號達 3 球且有特別號時加 0.5。"""
    if special is not None and normal_count >= 3:
        return normal_count + 0.5
    return float(normal_count)


def is_matched(count: int) -> bool:
    """按目前設定判斷某組當期球數是否符合查詢條件。"""
    if BIRTHDAY_NUM_MATCH_MODE == "==":
        return count == COMBINATION_TAKE_COUNT
    if BIRTHDAY_NUM_MATCH_MODE == "<=":
        return count <= COMBINATION_TAKE_COUNT
    return count >= COMBINATION_TAKE_COUNT


def recent_weight(rank: int, window_count: int) -> float:
    """rank=1 是最近一期；按窗口期比例分 4 段。"""
    if window_count <= 0:
        return 0.0
    ratio = rank / window_count
    if ratio <= 0.25:
        return 1.00
    if ratio <= 0.50:
        return 0.75
    if ratio <= 0.75:
        return 0.50
    return 0.25


def analyze_group_weights(
    window_rows: list[tuple[int, DrawRow]],
    target_index: int,
    group_id: int,
) -> list[NumWeight]:
    """用窗口期正號建立 count + 遠近比例 + 短期重複 的簡單權重。"""
    window_count = len(window_rows)
    _code, _name, start_num, end_num = GROUPS[group_id]
    counter: Counter[int] = Counter()
    recent_scores: defaultdict[int, float] = defaultdict(float)
    last5_counter: Counter[int] = Counter()
    last10_counter: Counter[int] = Counter()
    latest_rank: dict[int, int] = {}

    for row_index, row in window_rows:
        rank = target_index - row_index + 1
        nums = group_nums(row, group_id)
        for num in nums:
            counter[num] += 1
            recent_scores[num] += recent_weight(rank, window_count)
            if rank <= 5:
                last5_counter[num] += 1
            if rank <= 10:
                last10_counter[num] += 1
            if num not in latest_rank or rank < latest_rank[num]:
                latest_rank[num] = rank

    weights: list[NumWeight] = []
    for num in range(start_num, end_num + 1):
        repeat_score = 0.0
        if last5_counter[num] >= 2:
            repeat_score += 1.0
        if last10_counter[num] >= 3:
            repeat_score += 1.5
        recent_score = recent_scores.get(num, 0.0)
        score = counter[num] + recent_score + repeat_score
        weights.append(
            {
                "num": num,
                "count": counter[num],
                "recent_score": recent_score,
                "repeat_score": repeat_score,
                "score": float(score),
                "latest_rank": latest_rank.get(num),
            }
        )

    return sorted(
        weights,
        key=lambda item: (
            -item["score"],
            -(item["latest_rank"] is not None),
            item["latest_rank"] if item["latest_rank"] is not None else 9999,
            -item["count"],
            item["num"],
        ),
    )


def select_group_candidates(
    weights: list[NumWeight],
    group_id: int,
    take_counts: Optional[dict[int, int]] = None,
) -> list[int]:
    """依權重排序取出某組基礎熱號候選。"""
    take_count = (take_counts or BASE_GROUP_TAKE_COUNTS)[group_id]
    return sorted(item["num"] for item in weights[:take_count])


def row_all_check_text(row: DrawRow) -> str:
    """格式化核對期全部正號與特別號，超出 1-40 的號碼以 _ 顯示。"""
    nums = [str(num) if 1 <= num <= 40 else "_" for num in sorted(row["nums"])]
    special = row["special"]
    if special is not None:
        nums.append(f"*{special if 1 <= special <= 40 else '_'}")
    return "[" + ",".join(nums) + "]"


def check_row_group_condition_text(row: DrawRow) -> str:
    """格式化核對期本身在 ABCD 各組的球數與合條件組數。"""
    parts: list[str] = []
    matched_group_count = 0
    display_count_total = 0.0
    for group_id in GROUPS:
        code = GROUPS[group_id][0]
        nums = group_nums(row, group_id)
        special = group_special(row, group_id)
        ball_count = display_ball_count(len(nums), special)
        display_count_total += ball_count
        if is_matched(len(nums)):
            matched_group_count += 1
        parts.append(f"{code}={format_ball_count(ball_count)}球")
    return (
        f"{'，'.join(parts)}；"
        f"合條件組數={matched_group_count}/{len(GROUPS)}；"
        f"1-40 顯示合計={format_ball_count(display_count_total)}球"
    )


def check_row_total_ball_count(row: DrawRow) -> float:
    """計算核對期 1-40 正號與特別號總球數；特別號按 0.5 球。"""
    total_count = float(sum(1 for num in row["nums"] if 1 <= num <= 40))
    special = row["special"]
    if special is not None and 1 <= special <= 40:
        total_count += 0.5
    return total_count


def check_row_raw_1_40_count(row: DrawRow) -> int:
    """計算核對期 N1-N7 中落在 1-40 的原始球數。"""
    count = sum(1 for num in row["nums"] if 1 <= num <= 40)
    special = row["special"]
    if special is not None and 1 <= special <= 40:
        count += 1
    return count


def prediction_hit_text(pred_nums: list[int], check_row: DrawRow) -> tuple[str, float]:
    """比對預測球與核對期開獎號，回傳命中文字與命中球數。"""
    normal_hits = sorted(num for num in check_row["nums"] if num in pred_nums)
    special_hit = check_row["special"] if check_row["special"] in pred_nums else None
    hit_count = float(len(normal_hits)) + (0.5 if special_hit is not None else 0.0)
    special_text = f"[{special_hit}]" if special_hit is not None else "[]"
    return (
        f"命中 {format_nums(normal_hits)} + {special_text} /> {format_ball_count(hit_count)} 球",
        hit_count,
    )


def prediction_hit_nums(pred_nums: list[int], check_row: DrawRow) -> tuple[list[int], list[int]]:
    """回傳命中的正號與特別號清單，用於回測 CSV 紀錄。"""
    normal_hits = sorted(num for num in check_row["nums"] if num in pred_nums)
    special_hit = check_row["special"] if check_row["special"] in pred_nums else None
    special_hits = [special_hit] if special_hit is not None else []
    return normal_hits, special_hits


def print_window_detail(
    window_rows: list[tuple[int, DrawRow]],
    target_index: int,
    group_id: int,
) -> None:
    """列印某組窗口期內符合查詢條件的每期明細。"""
    for row_index, row in window_rows:
        nums = group_nums(row, group_id)
        if not is_matched(len(nums)):
            continue
        special = group_special(row, group_id)
        rank = target_index - row_index + 1
        ball_count = display_ball_count(len(nums), special)
        print(
            f"近 {rank}期：{row['date']}，"
            f"{format_nums(nums, special)} /> {format_ball_count(ball_count)} 球"
        )


def print_group_weight_summary(weights: list[NumWeight], group_id: int) -> None:
    """準備某組權重排序文字；目前詳細輸出預設關閉。"""
    code, name, _start_num, _end_num = GROUPS[group_id]
    parts = [
        f"{item['num']}({item['score']:.2f}/次{item['count']})"
        for item in weights
    ]
    # print(f"{code}組 {name} 遠近權重排序：" + "，".join(parts))


def group_condition_stats(window_rows: list[tuple[int, DrawRow]]) -> dict[int, tuple[int, int, float]]:
    """統計各組窗口期符合條件期數、總期數與百分比。"""
    total_count = len(window_rows)
    stats: dict[int, tuple[int, int, float]] = {}
    for group_id in GROUPS:
        matched_count = sum(
            1
            for _row_index, row in window_rows
            if is_matched(len(group_nums(row, group_id)))
        )
        matched_percent = matched_count / total_count * 100 if total_count else 0
        stats[group_id] = (matched_count, total_count, matched_percent)
    return stats


def condition_stats_text(stats: dict[int, tuple[int, int, float]]) -> list[str]:
    """格式化各組窗口條件統計文字。"""
    lines: list[str] = []
    for group_id in GROUPS:
        code = GROUPS[group_id][0]
        matched_count, total_count, matched_percent = stats[group_id]
        lines.append(
            f"{code},結果合條件 {BIRTHDAY_NUM_MATCH_MODE} {COMBINATION_TAKE_COUNT} 球，"
            f"查詢 {matched_count} / {total_count} 期統計 = {matched_count}期 "
            f"({matched_percent:.0f} %)"
        )
    return lines


def dynamic_group_take_counts(window_rows: list[tuple[int, DrawRow]]) -> dict[int, int]:
    """按各組窗口條件強弱，從弱組轉移配額給強組。"""
    take_counts = dict(BASE_GROUP_TAKE_COUNTS)
    if not AUTO_DISTRIBUTE_GROUP_TAKE:
        return take_counts

    stats = group_condition_stats(window_rows)
    ranked_groups = sorted(
        GROUPS,
        key=lambda group_id: (stats[group_id][2], stats[group_id][0], -group_id),
    )
    weakest_group = ranked_groups[0]
    strongest_group = ranked_groups[-1]
    percent_gap = stats[strongest_group][2] - stats[weakest_group][2]
    if percent_gap < AUTO_DISTRIBUTE_MIN_GAP_PERCENT:
        return take_counts

    movable_count = min(
        AUTO_DISTRIBUTE_MAX_TRANSFER,
        take_counts[weakest_group] - AUTO_DISTRIBUTE_MIN_GROUP_TAKE,
    )
    if movable_count <= 0:
        return take_counts

    take_counts[weakest_group] -= movable_count
    take_counts[strongest_group] += movable_count
    return take_counts


def load_trace() -> dict[str, object]:
    """讀取權重追蹤 JSON；檔案不存在或格式錯誤時回傳空紀錄。"""
    if not WEIGHT_JSON.exists():
        return {"records": []}
    try:
        with WEIGHT_JSON.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (json.JSONDecodeError, OSError):
        return {"records": []}
    return data if isinstance(data, dict) else {"records": []}


def save_trace_record(record: dict[str, object]) -> None:
    """追加一筆權重追蹤紀錄，並只保留最近 500 筆。"""
    JSON_DIR.mkdir(parents=True, exist_ok=True)
    trace = load_trace()
    records = trace.get("records")
    if not isinstance(records, list):
        records = []
    records.append(record)
    trace["records"] = records[-500:]
    with WEIGHT_JSON.open("w", encoding="utf-8") as handle:
        json.dump(trace, handle, ensure_ascii=False, indent=2)


def load_once_backtest_results() -> dict[str, object]:
    """讀取單期多窗口回測摘要 JSON。"""
    if not BACKTEST_RESULT_JSON.exists():
        return {"once_backtest_results": []}
    try:
        with BACKTEST_RESULT_JSON.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (json.JSONDecodeError, OSError):
        return {"once_backtest_results": []}
    return data if isinstance(data, dict) else {"once_backtest_results": []}


def save_once_backtest_result(record: dict[str, object]) -> None:
    """保存單期多窗口回測摘要，供 predict mode 人工選窗口期讀取。"""
    JSON_DIR.mkdir(parents=True, exist_ok=True)
    data = load_once_backtest_results()
    records = data.get("once_backtest_results")
    if not isinstance(records, list):
        records = []
    records.append(record)
    data["once_backtest_results"] = records[-200:]
    with BACKTEST_RESULT_JSON.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def latest_trace_record(trace: dict[str, object]) -> Optional[dict[str, object]]:
    """從 trace 資料中取出最後一筆紀錄。"""
    records = trace.get("records")
    if isinstance(records, list) and records:
        latest = records[-1]
        return latest if isinstance(latest, dict) else None
    return None


def migrate_once_backtest_results_from_weight_json() -> None:
    """把舊權重 JSON 內混放的回測摘要搬到專用 JSON。"""
    if not WEIGHT_JSON.exists():
        return
    trace = load_trace()
    old_records = trace.get("once_backtest_results")
    if not isinstance(old_records, list) or not old_records:
        return

    data = load_once_backtest_results()
    existing_records = data.get("once_backtest_results")
    if not isinstance(existing_records, list):
        existing_records = []
    merged_records = existing_records + old_records
    data["once_backtest_results"] = merged_records[-200:]
    JSON_DIR.mkdir(parents=True, exist_ok=True)
    with BACKTEST_RESULT_JSON.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)

    trace.pop("once_backtest_results", None)
    with WEIGHT_JSON.open("w", encoding="utf-8") as handle:
        json.dump(trace, handle, ensure_ascii=False, indent=2)


def print_old_new_compare(old_record: Optional[dict[str, object]], new_record: dict[str, object]) -> None:
    """在開關啟用時，列印上一筆與新一筆權重分數差異。"""
    if not PRINT_WEIGHT_COMPARE:
        return

    if old_record is None:
        print("上一期權重紀錄：沒有舊紀錄")
        return

    old_scores = old_record.get("group_scores")
    new_scores = new_record.get("group_scores")
    if not isinstance(old_scores, dict) or not isinstance(new_scores, dict):
        print("上一期權重紀錄：格式不同，略過比較")
        return

    print("----- 新舊權重比較 -----")
    for group_id in GROUPS:
        code = GROUPS[group_id][0]
        old_group = old_scores.get(code, {})
        new_group = new_scores.get(code, {})
        if not isinstance(old_group, dict) or not isinstance(new_group, dict):
            continue
        compare_nums = sorted({int(num) for num in old_group.keys()} | {int(num) for num in new_group.keys()})
        changes: list[str] = []
        for num in compare_nums:
            old_score = float(old_group.get(str(num), 0))
            new_score = float(new_group.get(str(num), 0))
            diff = new_score - old_score
            if abs(diff) >= 0.01:
                direction = "增強" if diff > 0 else "減弱"
                changes.append(f"{num}:{old_score:.2f}->{new_score:.2f} {direction}{diff:+.2f}")
        print(f"{code}組：" + ("，".join(changes[:10]) if changes else "沒有明顯變化"))


def group_window_num_counts(window_rows: list[tuple[int, DrawRow]]) -> dict[int, Counter[int]]:
    """統計各組窗口期內正號與同組特號出現次數。"""
    counters: dict[int, Counter[int]] = {group_id: Counter() for group_id in GROUPS}
    for _row_index, row in window_rows:
        for group_id in GROUPS:
            for num in group_nums(row, group_id):
                counters[group_id][num] += 1
            special = group_special(row, group_id)
            if special is not None:
                counters[group_id][special] += 1
    return counters


def missing_nums_text(window_rows: list[tuple[int, DrawRow]]) -> str:
    """顯示窗口期內 A/B/C/D 各組沒有出現過的號碼。"""
    group_counts = group_window_num_counts(window_rows)
    parts: list[str] = []
    for group_id in GROUPS:
        code, _name, start_num, end_num = GROUPS[group_id]
        missing = [num for num in range(start_num, end_num + 1) if group_counts[group_id][num] == 0]
        parts.append(f"{code}{format_nums(missing)}")
    return "ABCD 沒出現球號 = " + "，".join(parts)


def weak_nums_data(
    window_rows: list[tuple[int, DrawRow]],
    pair_data: Optional[dict[int, tuple[list[int], list[int]]]] = None,
) -> dict[int, list[int]]:
    """回傳扣除沒出現、高頻膽、高頻配腳後的其餘弱號。"""
    group_counts = group_window_num_counts(window_rows)
    if pair_data is None:
        pair_data = high_freq_pair_data(window_rows)
    result: dict[int, list[int]] = {}
    for group_id in GROUPS:
        _code, _name, start_num, end_num = GROUPS[group_id]
        dan_nums, partner_nums = pair_data.get(group_id, ([], []))
        assigned_nums = set(dan_nums) | set(partner_nums)
        weak_nums = [
            num
            for num in range(start_num, end_num + 1)
            if group_counts[group_id][num] > 0 and num not in assigned_nums
        ]
        if weak_nums:
            result[group_id] = weak_nums
    return result


def weak_nums_text(
    window_rows: list[tuple[int, DrawRow]],
    pair_data: Optional[dict[int, tuple[list[int], list[int]]]] = None,
) -> list[str]:
    """格式化 ABCD 弱號顯示文字。"""
    if not PRINT_WEAK_NUM_ANALYSIS:
        return []
    weak_data = weak_nums_data(window_rows, pair_data)
    parts: list[str] = []
    for group_id in GROUPS:
        code = GROUPS[group_id][0]
        parts.append(f"{code}{format_nums(weak_data.get(group_id, []))}")
    return ["ABCD 弱號 = " + "，".join(parts)]


def high_freq_pair_data(window_rows: list[tuple[int, DrawRow]]) -> dict[int, tuple[list[int], list[int]]]:
    """回傳每組的高頻膽號與同場非膽配腳號。"""
    result: dict[int, tuple[list[int], list[int]]] = {}

    for group_id in GROUPS:
        pair_rows: list[list[int]] = []
        for _row_index, row in window_rows:
            nums = group_nums(row, group_id)
            special = group_special(row, group_id)
            pair_nums = sorted(set(nums + ([special] if special is not None else [])))
            if is_matched(len(nums)) and len(pair_nums) >= 2:
                pair_rows.append(pair_nums)

        dan_counter: Counter[int] = Counter()
        partner_counter_by_dan: dict[int, Counter[int]] = {}

        for nums in pair_rows:
            for dan_num in nums:
                dan_counter[dan_num] += 1
                partner_counter = partner_counter_by_dan.setdefault(dan_num, Counter())
                for partner_num in nums:
                    if partner_num == dan_num:
                        continue
                    partner_counter[partner_num] += 1

        all_dan_nums = [
            num
            for num, count in sorted(dan_counter.items(), key=lambda item: (-item[1], item[0]))
            if count > HIGH_FREQ_MIN_PAIR_COUNT
        ]
        dan_nums = all_dan_nums[:HIGH_FREQ_DAN_TAKE]
        if not dan_nums:
            continue

        partner_counter: Counter[int] = Counter()
        for dan_num in dan_nums:
            partner_counter.update(partner_counter_by_dan.get(dan_num, Counter()))
        for dan_num in dan_nums:
            partner_counter.pop(dan_num, None)

        partner_pool = sorted(
            partner_counter,
            key=lambda partner_num: (-partner_counter[partner_num], partner_num),
        )[:HIGH_FREQ_PARTNER_POOL_TAKE]
        partners = sorted(partner_pool[:HIGH_FREQ_PARTNER_TAKE])

        result[group_id] = (dan_nums, partners)

    return result


def high_freq_pair_text(
    window_rows: list[tuple[int, DrawRow]],
    pair_data: Optional[dict[int, tuple[list[int], list[int]]]] = None,
) -> list[str]:
    """分析合條件窗口結果中的高頻膽號與伴號。"""
    if not PRINT_HIGH_FREQ_PAIR_ANALYSIS:
        return []

    if pair_data is None:
        pair_data = high_freq_pair_data(window_rows)
    dan_parts: list[str] = []
    partner_parts: list[str] = []
    for group_id in GROUPS:
        if group_id not in pair_data:
            continue
        code = GROUPS[group_id][0]
        dan_nums, partners = pair_data[group_id]
        dan_parts.append(f"{code}{format_nums(dan_nums)}")
        partner_parts.append(f"{code}{format_nums(partners)}")

    if not dan_parts:
        return []
    return [
        "ABCD 高頻膽號 = " + "，".join(dan_parts),
        "ABCD 高頻配腳號 = " + "，".join(partner_parts),
    ]


def recent_draw_nums(row: Optional[DrawRow]) -> set[int]:
    """取得某期全部正號與特別號，用於避開最近一期重複號。"""
    if row is None:
        return set()
    nums = {num for num in row["nums"] if 1 <= num <= 49}
    if row["special"] is not None:
        nums.add(row["special"])
    return nums


def append_unique_candidate(
    candidates: list[int],
    num: int,
    take_count: int,
) -> None:
    """在未超出配額且未重複時加入候選球。"""
    if len(candidates) >= take_count:
        return
    if num in candidates:
        return
    candidates.append(num)


def recent_penalized_weights(weights: list[NumWeight], recent_nums: set[int]) -> list[NumWeight]:
    """將最近一期出現號碼扣分後重新排序，不再直接排除。"""
    return sorted(
        weights,
        key=lambda item: (
            -(item["score"] - (RECENT_DRAW_SCORE_PENALTY if item["num"] in recent_nums else 0.0)),
            item["num"] in recent_nums,
            item["latest_rank"] if item["latest_rank"] is not None else 9999,
            -item["count"],
            item["num"],
        ),
    )


def select_final_group_candidates(
    weights: list[NumWeight],
    group_id: int,
    pair_data: dict[int, tuple[list[int], list[int]]],
    weak_data: dict[int, list[int]],
    recent_nums: set[int],
    take_counts: Optional[dict[int, int]] = None,
) -> list[int]:
    """高頻膽 1 + 高頻配腳 1 + 弱號機會 + 扣分後權重補滿。"""
    counts = take_counts or BASE_GROUP_TAKE_COUNTS
    take_count = counts[group_id]
    candidates: list[int] = []
    dan_nums, partner_nums = pair_data.get(group_id, ([], []))
    weak_nums = [num for num in weak_data.get(group_id, []) if num not in candidates]
    ranked_weights = recent_penalized_weights(weights, recent_nums)
    recent_penalty_rank = {item["num"]: index for index, item in enumerate(ranked_weights)}

    for num in sorted(dan_nums[:1], key=lambda value: (value in recent_nums, recent_penalty_rank.get(value, 9999), value)):
        append_unique_candidate(candidates, num, take_count)

    for num in sorted(partner_nums[:1], key=lambda value: (value in recent_nums, recent_penalty_rank.get(value, 9999), value)):
        append_unique_candidate(candidates, num, take_count)

    if weak_nums and WEAK_NUM_TAKE > 0:
        if WEAK_NUM_RANDOM_SEED is None:
            selected_weak_nums = random.sample(weak_nums, min(WEAK_NUM_TAKE, len(weak_nums)))
        else:
            rng = random.Random(WEAK_NUM_RANDOM_SEED + group_id)
            selected_weak_nums = rng.sample(weak_nums, min(WEAK_NUM_TAKE, len(weak_nums)))
        for num in sorted(selected_weak_nums):
            append_unique_candidate(candidates, num, take_count)

    for item in ranked_weights:
        append_unique_candidate(candidates, item["num"], take_count)

    # 極端情況下候選不足，按原始權重補滿。
    if len(candidates) < take_count:
        for item in weights:
            if len(candidates) >= take_count:
                break
            if item["num"] not in candidates:
                candidates.append(item["num"])

    return sorted(candidates[:take_count])


def select_high_freq_dan_backtest_nums(
    pair_data: dict[int, tuple[list[int], list[int]]],
) -> list[int]:
    """合併 ABCD 各組全部高頻膽號，作為回測額外一注候選組。"""
    selected_nums: set[int] = set()
    for group_id in GROUPS:
        dan_nums, _partner_nums = pair_data.get(group_id, ([], []))
        selected_nums.update(dan_nums)
    return sorted(selected_nums)


def format_high_freq_dan_group_quota(pair_data: dict[int, tuple[list[int], list[int]]]) -> str:
    """格式化 ABCD 高頻膽號候選組各組球數。"""
    parts: list[str] = []
    total_count = 0
    for group_id in GROUPS:
        code = GROUPS[group_id][0]
        dan_nums, _partner_nums = pair_data.get(group_id, ([], []))
        parts.append(f"{code}={len(dan_nums)}")
        total_count += len(dan_nums)
    return "，".join(parts) + f"，合共{total_count}球"


def print_hit_count_summary(
    backtest_offset: int,
    window_count: int,
    hit_stats: Counter[float],
    high_freq_dan_hit_stats: Optional[Counter[float]] = None,
) -> None:
    """打印回測期內預測候選球命中球數統計。"""
    pred_count = total_candidate_count()
    total_periods = sum(hit_stats.values())
    summary_values = [6.0, 5.5, 5.0, 4.5, 4.0, 3.5, 3.0]

    print("----- 回測期命中統計 -----")
    print(f"核對期 = 倒數第 {backtest_offset} 期，實際統計 = {total_periods} 期，窗口期 = {window_count}，預測候選球 = {pred_count} 球/期")
    print(f"固定基礎配額：{format_group_quota()}")
    print(format_auto_distribute_status())
    print("-----------------------------------------")
    for value in summary_values:
        label = format_ball_count(value)
        hit_periods = hit_stats.get(value, 0)
        hit_percent = hit_periods / total_periods * 100 if total_periods else 0
        print(f"{label:>3} = {hit_periods} 期 ({hit_percent:.1f}%)")
    print()

    if high_freq_dan_hit_stats is None:
        return

    dan_total_periods = sum(high_freq_dan_hit_stats.values())
    print("----- ABCD 全部高頻膽號合併一注命中統計 -----")
    print(f"核對期 = 倒數第 {backtest_offset} 期，實際統計 = {dan_total_periods} 期，窗口期 = {window_count}")
    print("-----------------------------------------")
    for value in summary_values:
        label = format_ball_count(value)
        hit_periods = high_freq_dan_hit_stats.get(value, 0)
        hit_percent = hit_periods / dan_total_periods * 100 if dan_total_periods else 0
        print(f"{label:>3} = {hit_periods} 期 ({hit_percent:.1f}%)")
    print()


def format_summary_cell(stats: Counter[float], total_periods: int, value: float) -> str:
    """格式化比較表內單格命中統計。"""
    hit_periods = stats.get(value, 0)
    hit_percent = hit_periods / total_periods * 100 if total_periods else 0
    return f"{hit_periods}期 ({hit_percent:.1f}%)"


def print_window_compare_table(
    title: str,
    window_stats: dict[int, Counter[float]],
) -> None:
    """打印多窗口期命中統計比較表。"""
    summary_values = [6.0, 5.5, 5.0, 4.5, 4.0, 3.5, 3.0]
    window_counts = list(window_stats.keys())
    headers = ["命中球數"] + [f"窗口期={window_count}" for window_count in window_counts]
    rows: list[list[str]] = []
    for value in summary_values:
        row = [format_ball_count(value)]
        for window_count in window_counts:
            stats = window_stats[window_count]
            row.append(format_summary_cell(stats, sum(stats.values()), value))
        rows.append(row)

    widths = [
        max(len(header), *(len(row[index]) for row in rows))
        for index, header in enumerate(headers)
    ]
    print(title)
    print(" | ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    print("-+-".join("-" * width for width in widths))
    for row in rows:
        print(" | ".join(value.ljust(widths[index]) for index, value in enumerate(row)))
    print()


def print_hit_window_result(title: str, window_stats: dict[int, Counter[float]]) -> None:
    """列出有命中的球數與對應窗口期。"""
    summary_values = [6.0, 5.5, 5.0, 4.5, 4.0, 3.5, 3.0]
    print(title)
    has_result = False
    for value in summary_values:
        window_parts: list[str] = []
        for window_count, stats in window_stats.items():
            hit_periods = stats.get(value, 0)
            if hit_periods > 0:
                window_parts.append(f"{hit_periods}/{window_count}")
        if window_parts:
            has_result = True
            print(f"{format_ball_count(value)} 球 = {'，'.join(window_parts)}")
    if not has_result:
        print("沒有 3 球或以上命中")
    print()


def window_hit_result_rows(window_stats: dict[int, Counter[float]]) -> list[dict[str, object]]:
    """整理有命中的球數與窗口期，寫入 JSON 摘要。"""
    summary_values = [6.0, 5.5, 5.0, 4.5, 4.0, 3.5, 3.0]
    rows: list[dict[str, object]] = []
    for value in summary_values:
        windows: list[dict[str, int]] = []
        for window_count, stats in window_stats.items():
            hit_periods = stats.get(value, 0)
            if hit_periods > 0:
                windows.append({"periods": hit_periods, "window_count": window_count})
        if windows:
            rows.append({"hit_count": value, "label": format_ball_count(value), "windows": windows})
    return rows


def best_window_hits(window_stats: dict[int, Counter[float]]) -> list[dict[str, object]]:
    """每個窗口期取出該投注組合的最高命中球數。"""
    rows: list[dict[str, object]] = []
    for window_count, stats in window_stats.items():
        hit_values = [value for value, periods in stats.items() if periods > 0]
        best_hit = max(hit_values) if hit_values else 0.0
        rows.append(
            {
                "window_count": window_count,
                "hit_count": best_hit,
                "hit_label": format_ball_count(float(best_hit)),
            }
        )
    return rows


def summary_csv_headers(window_counts: Optional[list[int]] = None) -> list[str]:
    """建立窗口期累積命中 CSV 欄位。"""
    counts = window_counts or WINDOW_DRAW_COUNT_LIST
    return ["hit_count"] + [f"window_{window_count}" for window_count in counts] + ["total"]


def empty_summary_rows(window_counts: Optional[list[int]] = None) -> dict[str, dict[str, int]]:
    """建立 6 至 3 球的空累積統計列。"""
    counts = window_counts or WINDOW_DRAW_COUNT_LIST
    rows: dict[str, dict[str, int]] = {}
    for value in [6.0, 5.5, 5.0, 4.5, 4.0, 3.5, 3.0]:
        label = format_ball_count(value)
        rows[label] = {f"window_{window_count}": 0 for window_count in counts}
        rows[label]["total"] = 0
    return rows


def window_count_from_key(key: str) -> Optional[int]:
    """從 window_N 欄位名稱取出窗口期。"""
    if not key.startswith("window_"):
        return None
    value = to_int(key.removeprefix("window_"), default=-1)
    return value if value > 0 else None


def existing_summary_window_counts(paths: list[Path]) -> list[int]:
    """讀取既有 CSV 欄位中的窗口期，避免減少窗口時丟失舊欄。"""
    counts: set[int] = set()
    for path in paths:
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for fieldname in reader.fieldnames or []:
                window_count = window_count_from_key(fieldname)
                if window_count is not None:
                    counts.add(window_count)
    return sorted(counts)


def json_summary_window_counts(records: list[dict[str, object]]) -> list[int]:
    """讀取近期 JSON 回測結果內曾出現的窗口期。"""
    counts: set[int] = set()
    for record in records:
        window_counts = record.get("window_counts")
        if isinstance(window_counts, list):
            for window_count in window_counts:
                value = to_int(window_count)
                if value > 0:
                    counts.add(value)

        results = record.get("results")
        if not isinstance(results, dict):
            continue
        for result_key in ["abcd_prediction_candidates", "high_freq_dan_combined"]:
            result = results.get(result_key)
            if not isinstance(result, dict):
                continue
            best_by_window = result.get("best_by_window")
            if not isinstance(best_by_window, list):
                continue
            for row in best_by_window:
                if isinstance(row, dict):
                    value = to_int(row.get("window_count"))
                    if value > 0:
                        counts.add(value)
    return sorted(counts)


def read_window_summary_csv(path: Path) -> dict[str, dict[str, int]]:
    """讀取窗口期命中累積 CSV；沒有檔案時回傳空統計。"""
    rows = empty_summary_rows()
    if not path.exists():
        return rows

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            label = str(raw.get("hit_count", "")).strip()
            if not label:
                continue
            existing = rows.setdefault(label, {})
            for key, value in raw.items():
                if key == "hit_count":
                    continue
                existing[key] = to_int(value)

    for label, values in rows.items():
        for window_count in WINDOW_DRAW_COUNT_LIST:
            values.setdefault(f"window_{window_count}", 0)
        values["total"] = sum(values.get(f"window_{window_count}", 0) for window_count in WINDOW_DRAW_COUNT_LIST)
    return rows


def write_window_summary_csv(
    path: Path,
    rows: dict[str, dict[str, int]],
    window_counts: Optional[list[int]] = None,
) -> None:
    """寫入窗口期命中累積 CSV。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    counts = window_counts or WINDOW_DRAW_COUNT_LIST
    headers = summary_csv_headers(counts)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        for value in [6.0, 5.5, 5.0, 4.5, 4.0, 3.5, 3.0]:
            label = format_ball_count(value)
            values = rows.get(label, {})
            writer.writerow(
                {
                    "hit_count": label,
                    **{f"window_{window_count}": values.get(f"window_{window_count}", 0) for window_count in counts},
                    "total": values.get("total", 0),
                }
            )


def recent_valid_once_backtest_records(records: list[object]) -> list[dict[str, object]]:
    """按核對日期取最近 N 筆有效回測，重複日期只保留最新一筆。"""
    selected_reversed: list[dict[str, object]] = []
    seen_dates: set[str] = set()
    for item in reversed(records):
        if not isinstance(item, dict):
            continue
        if item.get("eligible_for_prediction_eval") is not True:
            continue
        check_date = str(item.get("check_date", "")).strip()
        if not check_date or check_date in seen_dates:
            continue
        selected_reversed.append(item)
        seen_dates.add(check_date)
        if len(selected_reversed) >= BACKTEST_WINDOW_HIT_DRAW:
            break
    return list(reversed(selected_reversed))


def add_hit_windows_to_rows(rows: dict[str, dict[str, int]], hit_windows: object) -> None:
    """把 JSON hit_windows 結果加到 CSV 統計列。"""
    if not isinstance(hit_windows, list):
        return
    for item in hit_windows:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label", "")).strip()
        if not label:
            continue
        values = rows.setdefault(label, {})
        windows = item.get("windows")
        if not isinstance(windows, list):
            continue
        for window in windows:
            if not isinstance(window, dict):
                continue
            window_count = to_int(window.get("window_count"))
            periods = to_int(window.get("periods"))
            if window_count <= 0 or periods <= 0:
                continue
            window_key = f"window_{window_count}"
            values[window_key] = values.get(window_key, 0) + periods


def rebuild_window_summary_csvs_from_json() -> None:
    """用 JSON 最近 N 個有效核對日期重建 predict mode 參考 CSV。"""
    data = load_once_backtest_results()
    records = data.get("once_backtest_results")
    if not isinstance(records, list):
        records = []
    valid_records = recent_valid_once_backtest_records(records)
    summary_window_counts = sorted(
        set(WINDOW_DRAW_COUNT_LIST)
        | set(existing_summary_window_counts([ABCD_WINDOW_HIT_SUMMARY_CSV, HIGH_FREQ_DAN_WINDOW_HIT_SUMMARY_CSV]))
        | set(json_summary_window_counts(valid_records))
    )

    abcd_rows = empty_summary_rows(summary_window_counts)
    high_freq_rows = empty_summary_rows(summary_window_counts)
    for record in valid_records:
        results = record.get("results")
        if not isinstance(results, dict):
            continue
        abcd_result = results.get("abcd_prediction_candidates")
        if isinstance(abcd_result, dict):
            add_hit_windows_to_rows(abcd_rows, abcd_result.get("hit_windows"))
        high_freq_result = results.get("high_freq_dan_combined")
        if isinstance(high_freq_result, dict):
            add_hit_windows_to_rows(high_freq_rows, high_freq_result.get("hit_windows"))

    for rows in [abcd_rows, high_freq_rows]:
        for values in rows.values():
            values["total"] = sum(values.get(f"window_{window_count}", 0) for window_count in summary_window_counts)

    write_window_summary_csv(ABCD_WINDOW_HIT_SUMMARY_CSV, abcd_rows, summary_window_counts)
    write_window_summary_csv(HIGH_FREQ_DAN_WINDOW_HIT_SUMMARY_CSV, high_freq_rows, summary_window_counts)


def print_hit_result_section(
    check_row: DrawRow,
    pred_window_stats: dict[int, Counter[float]],
    high_freq_dan_window_stats: dict[int, Counter[float]],
) -> None:
    """集中打印核對期資訊與窗口期命中摘要。"""
    print("----命中球數 ＝ 期數 / 窗口期 ---")
    print(
        f"核對日期：{check_row['date']}: {row_all_check_text(check_row)} "
        f"/> {format_ball_count(check_row_total_ball_count(check_row))} 球。"
    )
    print()
    print_hit_window_result("ABCD 預測候選球，期數 / 窗口期", pred_window_stats)
    if PRINT_HIGH_FREQ_DAN_BACKTEST:
        print_hit_window_result("ABCD 全部高頻膽號合併，期數 / 窗口期", high_freq_dan_window_stats)


def reset_backtest_record_csv() -> None:
    """建立新的回測投注紀錄 CSV；每次回測前會刪除舊檔。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if BACKTEST_RECORD_CSV.exists():
        BACKTEST_RECORD_CSV.unlink()
    with BACKTEST_RECORD_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "bet_date",
            "window_count",
            "A(1-9)",
            "B(10-20)",
            "C(21-31)",
            "D(32-40)",
            "pred_list(1-40)",
            "count",
            "hit_num",
            "hit_sp_num",
            "high_freq_dan_list",
            "high_freq_dan_count",
            "high_freq_dan_hit_num",
            "high_freq_dan_hit_sp_num",
        ])


def append_backtest_record_csv(
    bet_date: str,
    window_count: int,
    group_pred_map: dict[int, list[int]],
    pred_nums: list[int],
    hit_nums: list[int],
    hit_sp_nums: list[int],
    high_freq_dan_nums: Optional[list[int]] = None,
    high_freq_dan_hit_nums: Optional[list[int]] = None,
    high_freq_dan_hit_sp_nums: Optional[list[int]] = None,
) -> None:
    """追加一筆回測預測投注紀錄到 CSV。"""
    dan_nums = high_freq_dan_nums or []
    dan_hit_nums = high_freq_dan_hit_nums or []
    dan_hit_sp_nums = high_freq_dan_hit_sp_nums or []
    with BACKTEST_RECORD_CSV.open("a", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            bet_date,
            window_count,
            format_nums(group_pred_map.get(1, [])),
            format_nums(group_pred_map.get(2, [])),
            format_nums(group_pred_map.get(3, [])),
            format_nums(group_pred_map.get(4, [])),
            format_nums(pred_nums),
            len(pred_nums),
            format_nums(hit_nums),
            format_nums(hit_sp_nums),
            format_nums(dan_nums),
            len(dan_nums),
            format_nums(dan_hit_nums),
            format_nums(dan_hit_sp_nums),
        ])


def nums_in_range(nums: list[int], start_num: int, end_num: int) -> list[int]:
    """從候選球中取出指定範圍內的號碼。"""
    return sorted(num for num in nums if start_num <= num <= end_num)


def reset_next_draw_record_csv() -> None:
    """建立新的下期投注紀錄 CSV。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if NEXT_DRAW_RECORD_CSV.exists():
        NEXT_DRAW_RECORD_CSV.unlink()
    with NEXT_DRAW_RECORD_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "date",
            "(1-9)",
            "(10_20)",
            "(21_31)",
            "(32-40)",
            "candidate_pool",
        ])


def append_next_draw_record_csv(next_draw_date: str, candidate_pool: list[int]) -> None:
    """追加一注下期投注候選球到 CSV。"""
    with NEXT_DRAW_RECORD_CSV.open("a", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            next_draw_date,
            format_nums(nums_in_range(candidate_pool, 1, 9)),
            format_nums(nums_in_range(candidate_pool, 10, 20)),
            format_nums(nums_in_range(candidate_pool, 21, 31)),
            format_nums(nums_in_range(candidate_pool, 32, 40)),
            format_nums(sorted(candidate_pool)),
        ])


def hit_level_text(hit_count: float) -> str:
    """依命中球數標記回測命中等級。"""
    if hit_count >= 5:
        return "prize3_like"
    if hit_count >= 4:
        return "high_hit"
    if hit_count >= 3:
        return "mid_hit"
    return "low_hit"


def config_snapshot(backtest_count: Optional[int], window_count: int, take_counts: Optional[dict[int, int]]) -> dict[str, object]:
    """保存本次回測/預測使用的核心參數，方便之後比較優化效果。"""
    counts = take_counts or BASE_GROUP_TAKE_COUNTS
    return {
        "mode": MODE,
        "backtest_count": backtest_count,
        "window_count": window_count,
        "combination_take_count": COMBINATION_TAKE_COUNT,
        "birthday_num_match_mode": BIRTHDAY_NUM_MATCH_MODE,
        "base_group_take_counts": {GROUPS[group_id][0]: BASE_GROUP_TAKE_COUNTS[group_id] for group_id in GROUPS},
        "actual_group_take_counts": {GROUPS[group_id][0]: counts[group_id] for group_id in GROUPS},
        "prediction_count": sum(counts.values()),
        "auto_distribute_group_take": AUTO_DISTRIBUTE_GROUP_TAKE,
        "auto_distribute_max_transfer": AUTO_DISTRIBUTE_MAX_TRANSFER,
        "auto_distribute_min_group_take": AUTO_DISTRIBUTE_MIN_GROUP_TAKE,
        "auto_distribute_min_gap_percent": AUTO_DISTRIBUTE_MIN_GAP_PERCENT,
        "recent_draw_score_penalty": RECENT_DRAW_SCORE_PENALTY,
        "high_freq_min_pair_count": HIGH_FREQ_MIN_PAIR_COUNT,
        "high_freq_dan_take": HIGH_FREQ_DAN_TAKE,
        "high_freq_partner_take": HIGH_FREQ_PARTNER_TAKE,
        "weak_num_take": WEAK_NUM_TAKE,
        "weak_num_random_seed": WEAK_NUM_RANDOM_SEED,
    }


def build_score_record(
    check_row: DrawRow,
    backtest_count: Optional[int],
    window_count: int,
    group_weights: dict[int, list[NumWeight]],
    pred_nums: list[int],
    hit_count: float,
    take_counts: Optional[dict[int, int]] = None,
) -> dict[str, object]:
    """建立一筆可寫入 JSON 的回測/預測權重紀錄。"""
    group_scores: dict[str, dict[str, float]] = {}
    group_candidates: dict[str, list[int]] = {}
    for group_id, weights in group_weights.items():
        code = GROUPS[group_id][0]
        group_scores[code] = {str(item["num"]): round(item["score"], 4) for item in weights}
        group_candidates[code] = select_group_candidates(weights, group_id, take_counts)

    return {
        "check_date": check_row["date"],
        "config": config_snapshot(backtest_count, window_count, take_counts),
        "window_count": window_count,
        "group_take_counts": {
            GROUPS[group_id][0]: (take_counts or BASE_GROUP_TAKE_COUNTS)[group_id]
            for group_id in GROUPS
        },
        "group_scores": group_scores,
        "group_candidates": group_candidates,
        "prediction_nums": pred_nums,
        "prediction_count": len(pred_nums),
        "hit_count": hit_count,
        "hit_level": hit_level_text(hit_count),
        "is_prize3_like": hit_count >= 5,
    }


def run_backtest(draws: list[DrawRow]) -> None:
    """執行回測模式：用核對期之前的窗口資料預測並統計命中。"""
    latest_index = len(draws) - 1
    trace = load_trace()
    old_record = latest_trace_record(trace)
    reset_backtest_record_csv()

    for backtest_offset in BACKTEST_DRAW_COUNT_LIST:
        check_index = latest_index - backtest_offset + 1
        if check_index < 0:
            print(f"倒數第 {backtest_offset} 期超出資料範圍，略過。")
            continue
        check_row = draws[check_index]
        pred_window_stats: dict[int, Counter[float]] = {}
        high_freq_dan_window_stats: dict[int, Counter[float]] = {}
        take_counts_by_window: dict[int, dict[int, int]] = {}

        for window_count in WINDOW_DRAW_COUNT_LIST:
            hit_stats: Counter[float] = Counter()
            high_freq_dan_hit_stats: Counter[float] = Counter()
            window_start_index = max(0, check_index - window_count)
            window_rows = [
                (row_index, row)
                for row_index, row in enumerate(draws[window_start_index:check_index], start=window_start_index)
            ]

            group_weights: dict[int, list[NumWeight]] = {}
            take_counts = dynamic_group_take_counts(window_rows)
            take_counts_by_window[window_count] = dict(take_counts)
            pair_data = high_freq_pair_data(window_rows)
            weak_data = weak_nums_data(window_rows, pair_data)
            previous_row = draws[check_index - 1] if check_index > 0 else None
            recent_nums = recent_draw_nums(previous_row)
            pred_nums: list[int] = []
            group_pred_map: dict[int, list[int]] = {}
            for group_id in GROUPS:
                weights = analyze_group_weights(window_rows, check_index - 1, group_id)
                group_weights[group_id] = weights
                final_group_pred = select_final_group_candidates(weights, group_id, pair_data, weak_data, recent_nums, take_counts)
                group_pred_map[group_id] = final_group_pred
                pred_nums.extend(final_group_pred)

            pred_nums = sorted(pred_nums)
            hit_text, hit_count = prediction_hit_text(pred_nums, check_row)
            hit_nums, hit_sp_nums = prediction_hit_nums(pred_nums, check_row)
            hit_stats[hit_count] += 1

            high_freq_dan_nums: list[int] = []
            dan_hit_nums: list[int] = []
            dan_hit_sp_nums: list[int] = []
            dan_hit_text = ""
            if PRINT_HIGH_FREQ_DAN_BACKTEST:
                high_freq_dan_nums = select_high_freq_dan_backtest_nums(pair_data)
                dan_hit_text, dan_hit_count = prediction_hit_text(high_freq_dan_nums, check_row)
                dan_hit_nums, dan_hit_sp_nums = prediction_hit_nums(high_freq_dan_nums, check_row)
                high_freq_dan_hit_stats[dan_hit_count] += 1

            pred_window_stats[window_count] = hit_stats
            high_freq_dan_window_stats[window_count] = high_freq_dan_hit_stats

            append_backtest_record_csv(
                check_row["date"],
                window_count,
                group_pred_map,
                pred_nums,
                hit_nums,
                hit_sp_nums,
                high_freq_dan_nums,
                dan_hit_nums,
                dan_hit_sp_nums,
            )

            new_record = build_score_record(check_row, backtest_offset, window_count, group_weights, pred_nums, hit_count, take_counts)
            print_old_new_compare(old_record, new_record)
            save_trace_record(new_record)
            old_record = new_record

        print(
            f"----- (回測期 核對期=倒數第 {backtest_offset} 期) "
            f"日期={check_row['date']}, 窗口期 = {WINDOW_DRAW_COUNT_LIST} -----"
        )
        print_backtest_quota_header(take_counts_by_window)
        print_window_compare_table("----- ABCD 預測候選球：窗口期命中比較表 ----", pred_window_stats)
        if PRINT_HIGH_FREQ_DAN_BACKTEST:
            print_window_compare_table("----- ABCD 全部高頻膽號合併一注：窗口期命中比較表 ----", high_freq_dan_window_stats)
        print_hit_result_section(check_row, pred_window_stats, high_freq_dan_window_stats)

        raw_1_40_count = check_row_raw_1_40_count(check_row)
        save_once_backtest_result(
            {
                "mode": "once_backtest",
                "purpose": "predict_mode_manual_window_selection",
                "check_offset": backtest_offset,
                "check_date": check_row["date"],
                "check_nums": row_all_check_text(check_row),
                "check_display_ball_count": check_row_total_ball_count(check_row),
                "check_raw_1_40_count_n1_to_n7": raw_1_40_count,
                "eligible_for_prediction_eval": raw_1_40_count >= 3,
                "eligibility_rule": "N1..N7 開出 1-40 號達 3 球或以上",
                "window_counts": WINDOW_DRAW_COUNT_LIST,
                "config": {
                    "base_group_take_counts": {
                        GROUPS[group_id][0]: BASE_GROUP_TAKE_COUNTS[group_id]
                        for group_id in GROUPS
                    },
                    "auto_distribute_group_take": AUTO_DISTRIBUTE_GROUP_TAKE,
                    "birthday_num_match_mode": BIRTHDAY_NUM_MATCH_MODE,
                    "combination_take_count": COMBINATION_TAKE_COUNT,
                },
                "results": {
                    "abcd_prediction_candidates": {
                        "hit_windows": window_hit_result_rows(pred_window_stats),
                        "best_by_window": best_window_hits(pred_window_stats),
                    },
                    "high_freq_dan_combined": {
                        "hit_windows": window_hit_result_rows(high_freq_dan_window_stats),
                        "best_by_window": best_window_hits(high_freq_dan_window_stats),
                    },
                },
            }
        )
        rebuild_window_summary_csvs_from_json()


def run_predict(draws: list[DrawRow]) -> None:
    """執行預測模式：用最新窗口資料產生下一期候選球。"""
    latest_index = len(draws) - 1
    latest_row = draws[latest_index]
    next_draw_date = read_next_draw_date()

    for window_count in WINDOW_DRAW_COUNT_LIST:
        window_start_index = max(0, latest_index - window_count + 1)
        window_rows = [
            (row_index, row)
            for row_index, row in enumerate(draws[window_start_index:latest_index + 1], start=window_start_index)
        ]

        print(f"====== ABCD 權重預測：窗口期={window_count} ======")
        print("predict：窗口期包括最後一期開獎，準備下期預測")

        pred_nums: list[int] = []
        group_pred_map: dict[int, list[int]] = {}
        take_counts = dynamic_group_take_counts(window_rows)
        condition_stats = group_condition_stats(window_rows)
        pair_data = high_freq_pair_data(window_rows)
        weak_data = weak_nums_data(window_rows, pair_data)
        recent_nums = recent_draw_nums(latest_row)
        for group_id in GROUPS:
            code, name, _start_num, _end_num = GROUPS[group_id]
            print(f"--- {code}組 {name} ---")
            print_window_detail(window_rows, latest_index, group_id)
            weights = analyze_group_weights(window_rows, latest_index, group_id)
            print_group_weight_summary(weights, group_id)
            group_pred = select_group_candidates(weights, group_id, take_counts)
            print(f"{code}組權重熱號 {take_counts[group_id]} 球：{format_nums(group_pred)}")
            final_group_pred = select_final_group_candidates(weights, group_id, pair_data, weak_data, recent_nums, take_counts)
            group_pred_map[group_id] = final_group_pred
            pred_nums.extend(final_group_pred)
            print(f"{code}組最終候選 {take_counts[group_id]} 球：{format_nums(final_group_pred)}")
            print()

        pred_nums = sorted(pred_nums)
        pred_count = sum(take_counts.values())
        print(f"固定基礎配額：{format_group_quota()}")
        print(format_auto_distribute_status())
        print(f"本期實際配額：{format_group_quota(take_counts)}")
        print(format_quota_adjustment(take_counts))
        for line in condition_stats_text(condition_stats):
            print(line)
        print(f"最後開獎日期：{latest_row['date']}: {row_all_check_text(latest_row)}")
        print(f"下期開獎日期：{next_draw_date or '未知'}")
        print(missing_nums_text(window_rows))
        for line in high_freq_pair_text(window_rows, pair_data):
            print(line)
        for line in weak_nums_text(window_rows, pair_data):
            print(line)
        print(f"ABCD 下期預測候選球 {format_nums(pred_nums)} /> [{pred_count}] 球")
        print_predict_bet_groups(group_pred_map, pair_data, next_draw_date, take_counts)
        print()


def print_predict_bet_groups(
    group_pred_map: dict[int, list[int]],
    pair_data: dict[int, tuple[list[int], list[int]]],
    next_draw_date: str,
    take_counts: Optional[dict[int, int]] = None,
) -> None:
    """列印 predict mode 的投注分組組合與高頻膽號候選組。"""
    if not PRINT_PREDICT_BET_GROUPS:
        return

    counts = take_counts or BASE_GROUP_TAKE_COUNTS
    abc_nums = sorted(group_pred_map.get(1, []) + group_pred_map.get(2, []) + group_pred_map.get(3, []))
    bcd_nums = sorted(group_pred_map.get(2, []) + group_pred_map.get(3, []) + group_pred_map.get(4, []))
    high_freq_dan_nums = select_high_freq_dan_backtest_nums(pair_data)

    reset_next_draw_record_csv()
    append_next_draw_record_csv(next_draw_date, abc_nums)
    append_next_draw_record_csv(next_draw_date, bcd_nums)
    append_next_draw_record_csv(next_draw_date, high_freq_dan_nums)

    print("----- 投注分組預測球組合 -----")
    print(
        f"1，A{counts[1]} + B{counts[2]} + C{counts[3]} "
        f"= {format_nums(abc_nums)} /> [{len(abc_nums)}] 球"
    )
    print(
        f"2，B{counts[2]} + C{counts[3]} + D{counts[4]} "
        f"= {format_nums(bcd_nums)} /> [{len(bcd_nums)}] 球"
    )
    print(
        f"3，ABCD 全部高頻膽號合併一注 "
        f"= {format_nums(high_freq_dan_nums)} /> [{len(high_freq_dan_nums)}] 球"
    )
    print(f"高頻膽號組配額：{format_high_freq_dan_group_quota(pair_data)}")


def main() -> None:
    """程式進入點：讀取資料並依 MODE 執行回測或預測。"""
    migrate_once_backtest_results_from_weight_json()
    draws = read_draws()
    if not draws:
        raise FileNotFoundError(f"找不到或未能讀取 M6：{M6_CSV}")

    if MODE == "backtest":
        run_backtest(draws)
    elif MODE == "predict":
        print("====== ABCD 遠近權重候選球分析 ======")
        print(f"運作模式：{MODE}")
        print(f"核對倒數期列表：{BACKTEST_DRAW_COUNT_LIST}")
        print(f"窗口期列表：{WINDOW_DRAW_COUNT_LIST}")
        print(f"固定基礎配額：{format_group_quota()}")
        print(format_auto_distribute_status())
        print(f"符合條件：範圍內號碼數量 {BIRTHDAY_NUM_MATCH_MODE}{COMBINATION_TAKE_COUNT} 球")
        print("權重公式：出現次數 + 遠近比例權重 + 短期重複加分")
        print()
        run_predict(draws)
    else:
        raise ValueError('MODE 只能是 "backtest" 或 "predict"。')


if __name__ == "__main__":
    main()
