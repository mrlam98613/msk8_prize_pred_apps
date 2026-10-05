from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import csv
import json
import random
from typing import TypedDict


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
M6_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"
M4_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M4_lotto_prize_summary.csv"
DATA_DIR = CURRENT_DIR / "data"
BACKTEST_RECORD_CSV = DATA_DIR / "prr_v3_bet_pred_records.csv"
JSON_DIR = CURRENT_DIR / "json_data"
WEIGHT_JSON = JSON_DIR / "prr_v3_ABCD_weight_trace.json"
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

'''

# 1-6 重點參數。
MODE = "backtest"
BACKTEST_DRAW_COUNT_LIST = [1]
WINDOW_DRAW_COUNT_LIST = [30]
GROUP_RUN_LIST = [(1,), (2,), (3,), (4,)]
COMBINATION_TAKE_COUNT = 1
BIRTHDAY_NUM_MATCH_MODE = ">="

# 是否顯示每期新舊權重比較。
PRINT_WEIGHT_COMPARE = False

# 高頻膽號：合條件窗口結果中，同組配對出現 >= 2 次才列入。
PRINT_HIGH_FREQ_PAIR_ANALYSIS = True
HIGH_FREQ_MIN_PAIR_COUNT = 2 # 高頻配對最少出現次數
HIGH_FREQ_DAN_TAKE = 2 # 高頻膽號選取數量
HIGH_FREQ_PARTNER_TAKE = 5 # 高頻配腳號選取數量
HIGH_FREQ_PARTNER_RANDOM_SEED: int | None = None # 高頻配腳隨機種子；None 表示每次執行都不同。

# predict mode 最後投注分組顯示。
PRINT_PREDICT_BET_GROUPS = True
RANDOM_BET_GROUP_TAKE = 9 # 在下期預測顯示中，系統在總候選球中，隨機取出 9 球。
RANDOM_BET_GROUP_SEED: int | None = 20261003


# A/B/C/D 每組預測球數，預設 4 + 5 + 5 + 4 = 18 球。
GROUP_TAKE_COUNTS = {
    1: 4,  # A: 1-9
    2: 5,  # B: 10-20
    3: 4,  # C: 21-31
    4: 3,  # D: 32-40
}

GROUPS = {
    1: ("A", "1-9", 1, 9),
    2: ("B", "10-20", 10, 20),
    3: ("C", "21-31", 21, 31),
    4: ("D", "32-40", 32, 40),
}


class DrawRow(TypedDict):
    date: str
    nums: list[int]
    special: int | None


class NumWeight(TypedDict):
    num: int
    count: int
    recent_score: float
    repeat_score: float
    score: float
    latest_rank: int | None


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


def format_nums(nums: list[int], special: int | None = None) -> str:
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
    return sum(GROUP_TAKE_COUNTS.values())


def format_group_quota() -> str:
    """格式化 ABCD 各組配額與總候選球數。"""
    quota_parts = [f"{GROUPS[group_id][0]}={GROUP_TAKE_COUNTS[group_id]}" for group_id in GROUPS]
    return "，".join(quota_parts) + f"，合共{total_candidate_count()}球"


def group_nums(row: DrawRow, group_id: int) -> list[int]:
    """取出某期正號中落在指定 ABCD 組範圍內的球號。"""
    _code, _name, start_num, end_num = GROUPS[group_id]
    return sorted(num for num in row["nums"] if start_num <= num <= end_num)


def group_special(row: DrawRow, group_id: int) -> int | None:
    """取出某期特別號是否落在指定 ABCD 組範圍內。"""
    _code, _name, start_num, end_num = GROUPS[group_id]
    special = row["special"]
    if special is None:
        return None
    return special if start_num <= special <= end_num else None


def display_ball_count(normal_count: int, special: int | None) -> float:
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


def select_group_candidates(weights: list[NumWeight], group_id: int) -> list[int]:
    """依權重排序取出某組基礎熱號候選。"""
    take_count = GROUP_TAKE_COUNTS[group_id]
    return sorted(item["num"] for item in weights[:take_count])


def row_all_check_text(row: DrawRow) -> str:
    """格式化核對期全部正號與特別號，超出 1-40 的號碼以 _ 顯示。"""
    nums = [str(num) if 1 <= num <= 40 else "_" for num in sorted(row["nums"])]
    special = row["special"]
    if special is not None:
        nums.append(f"*{special if 1 <= special <= 40 else '_'}")
    return "[" + ",".join(nums) + "]"


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


def latest_trace_record(trace: dict[str, object]) -> dict[str, object] | None:
    """從 trace 資料中取出最後一筆紀錄。"""
    records = trace.get("records")
    if isinstance(records, list) and records:
        latest = records[-1]
        return latest if isinstance(latest, dict) else None
    return None


def print_old_new_compare(old_record: dict[str, object] | None, new_record: dict[str, object]) -> None:
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


def missing_nums_text(window_rows: list[tuple[int, DrawRow]]) -> str:
    """顯示窗口期內 A/B/C/D 各組沒有出現過的正號。"""
    seen_nums = {
        num
        for _row_index, row in window_rows
        for num in row["nums"]
        if 1 <= num <= 40
    }
    parts: list[str] = []
    for group_id in GROUPS:
        code, _name, start_num, end_num = GROUPS[group_id]
        missing = [num for num in range(start_num, end_num + 1) if num not in seen_nums]
        parts.append(f"{code}{format_nums(missing)}")
    return "ABCD 沒出現球號 = " + "，".join(parts)


def high_freq_pair_data(window_rows: list[tuple[int, DrawRow]]) -> dict[int, tuple[list[int], list[int]]]:
    """回傳每組的高頻膽號與隨機抽取的高頻伴號。"""
    result: dict[int, tuple[list[int], list[int]]] = {}
    rng = random.Random(HIGH_FREQ_PARTNER_RANDOM_SEED)

    for group_id in GROUPS:
        pair_rows: list[list[int]] = []
        for _row_index, row in window_rows:
            nums = group_nums(row, group_id)
            if is_matched(len(nums)) and len(nums) >= 2:
                pair_rows.append(nums)

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

        dan_nums = [
            num
            for num, count in sorted(dan_counter.items(), key=lambda item: (-item[1], item[0]))
            if count >= HIGH_FREQ_MIN_PAIR_COUNT
        ][:HIGH_FREQ_DAN_TAKE]
        if not dan_nums:
            continue

        partner_pool = sorted(
            {
                partner_num
                for dan_num in dan_nums
                for partner_num in partner_counter_by_dan.get(dan_num, Counter())
                if partner_num not in dan_nums
            }
        )
        partner_take = min(HIGH_FREQ_PARTNER_TAKE, len(partner_pool))
        partners = sorted(rng.sample(partner_pool, partner_take)) if partner_take else []

        result[group_id] = (dan_nums, partners)

    return result


def high_freq_pair_text(
    window_rows: list[tuple[int, DrawRow]],
    pair_data: dict[int, tuple[list[int], list[int]]] | None = None,
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


def recent_draw_nums(row: DrawRow | None) -> set[int]:
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
    avoid_nums: set[int],
    take_count: int,
) -> None:
    """在未超出配額、未重複、未命中避開清單時加入候選球。"""
    if len(candidates) >= take_count:
        return
    if num in avoid_nums or num in candidates:
        return
    candidates.append(num)


def select_final_group_candidates(
    weights: list[NumWeight],
    group_id: int,
    pair_data: dict[int, tuple[list[int], list[int]]],
    avoid_nums: set[int],
) -> list[int]:
    """高頻膽 1 + 高頻配腳 1 + 權重補滿；優先避開最近一期開號。"""
    take_count = GROUP_TAKE_COUNTS[group_id]
    candidates: list[int] = []
    dan_nums, partner_nums = pair_data.get(group_id, ([], []))

    for num in dan_nums[:1]:
        append_unique_candidate(candidates, num, avoid_nums, take_count)

    for num in partner_nums[:1]:
        append_unique_candidate(candidates, num, avoid_nums, take_count)

    for item in weights:
        append_unique_candidate(candidates, item["num"], avoid_nums, take_count)

    # 極端情況下避開最近一期後不夠數，才放寬補滿。
    if len(candidates) < take_count:
        for item in weights:
            if len(candidates) >= take_count:
                break
            if item["num"] not in candidates:
                candidates.append(item["num"])

    return sorted(candidates[:take_count])


def print_hit_count_summary(
    backtest_count: int,
    window_count: int,
    hit_stats: Counter[float],
) -> None:
    """打印回測期內預測候選球命中球數統計。"""
    pred_count = total_candidate_count()
    total_periods = sum(hit_stats.values())
    summary_values = [6.0, 5.5, 5.0, 4.5, 4.0, 3.5, 3.0]

    print("----- 回測期命中統計 -----")
    print(f"回測期設定 = {backtest_count}，實際統計 = {total_periods} 期，窗口期 = {window_count}，預測候選球 = {pred_count} 球/期")
    print(f"ABCD 配額：{format_group_quota()}")
    print("-----------------------------------------")
    for value in summary_values:
        label = format_ball_count(value)
        hit_periods = hit_stats.get(value, 0)
        hit_percent = hit_periods / total_periods * 100 if total_periods else 0
        print(f"{label:>3} = {hit_periods} 期 ({hit_percent:.1f}%)")
    print()


def reset_backtest_record_csv() -> None:
    """建立新的回測投注紀錄 CSV；每次回測前會刪除舊檔。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if BACKTEST_RECORD_CSV.exists():
        BACKTEST_RECORD_CSV.unlink()
    with BACKTEST_RECORD_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "bet_date",
            "A(1-9)",
            "B(10-20)",
            "C(21-31)",
            "D(32-40)",
            "pred_list(1-40)",
            "count",
            "hit_num",
            "hit_sp_num",
        ])


def append_backtest_record_csv(
    bet_date: str,
    group_pred_map: dict[int, list[int]],
    pred_nums: list[int],
    hit_nums: list[int],
    hit_sp_nums: list[int],
) -> None:
    """追加一筆回測預測投注紀錄到 CSV。"""
    with BACKTEST_RECORD_CSV.open("a", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            bet_date,
            format_nums(group_pred_map.get(1, [])),
            format_nums(group_pred_map.get(2, [])),
            format_nums(group_pred_map.get(3, [])),
            format_nums(group_pred_map.get(4, [])),
            format_nums(pred_nums),
            len(pred_nums),
            format_nums(hit_nums),
            format_nums(hit_sp_nums),
        ])


def build_score_record(
    check_row: DrawRow,
    window_count: int,
    group_weights: dict[int, list[NumWeight]],
    pred_nums: list[int],
    hit_count: float,
) -> dict[str, object]:
    """建立一筆可寫入 JSON 的回測/預測權重紀錄。"""
    group_scores: dict[str, dict[str, float]] = {}
    group_candidates: dict[str, list[int]] = {}
    for group_id, weights in group_weights.items():
        code = GROUPS[group_id][0]
        group_scores[code] = {str(item["num"]): round(item["score"], 4) for item in weights}
        group_candidates[code] = select_group_candidates(weights, group_id)

    return {
        "check_date": check_row["date"],
        "window_count": window_count,
        "group_scores": group_scores,
        "group_candidates": group_candidates,
        "prediction_nums": pred_nums,
        "prediction_count": len(pred_nums),
        "hit_count": hit_count,
    }


def run_backtest(draws: list[DrawRow]) -> None:
    """執行回測模式：用核對期之前的窗口資料預測並統計命中。"""
    latest_index = len(draws) - 1
    trace = load_trace()
    old_record = latest_trace_record(trace)
    reset_backtest_record_csv()

    for backtest_count in BACKTEST_DRAW_COUNT_LIST:
        first_check_index = max(0, latest_index - backtest_count + 1)
        check_indices = range(first_check_index, latest_index + 1)

        for window_count in WINDOW_DRAW_COUNT_LIST:
            print(f"====== ABCD 權重預測回測：窗口期={window_count}，回測期={backtest_count} ======")
            print(f"本輪回測參數：{format_group_quota()}，每期預測候選球 = {total_candidate_count()} 球")
            hit_stats: Counter[float] = Counter()
            for display_index, check_index in enumerate(check_indices, start=1):
                check_row = draws[check_index]
                window_start_index = max(0, check_index - window_count)
                window_rows = [
                    (row_index, row)
                    for row_index, row in enumerate(draws[window_start_index:check_index], start=window_start_index)
                ]

                print(f"----- 回測 {display_index}：{check_row['date']} 核對 -----")
                print("backtest：窗口期不包括核對期，預留核對預測")

                group_weights: dict[int, list[NumWeight]] = {}
                pair_data = high_freq_pair_data(window_rows)
                previous_row = draws[check_index - 1] if check_index > 0 else None
                avoid_nums = recent_draw_nums(previous_row)
                pred_nums: list[int] = []
                group_pred_map: dict[int, list[int]] = {}
                for group_id in GROUPS:
                    code, name, _start_num, _end_num = GROUPS[group_id]
                    matched_count = sum(1 for _row_index, row in window_rows if is_matched(len(group_nums(row, group_id))))
                    matched_percent = matched_count / len(window_rows) * 100 if window_rows else 0
                    print(f"--- {code}組 {name} ---")
                    print_window_detail(window_rows, check_index - 1, group_id)
                    print(
                        f"結果合條件 {BIRTHDAY_NUM_MATCH_MODE} {COMBINATION_TAKE_COUNT} 球，"
                        f"查詢 {matched_count} / {len(window_rows)} 期統計 = {matched_count}期 "
                        f"({matched_percent:.0f} %)"
                    )
                    weights = analyze_group_weights(window_rows, check_index - 1, group_id)
                    group_weights[group_id] = weights
                    print_group_weight_summary(weights, group_id)
                    group_pred = select_group_candidates(weights, group_id)
                    print(f"{code}組權重熱號 {GROUP_TAKE_COUNTS[group_id]} 球：{format_nums(group_pred)}")
                    final_group_pred = select_final_group_candidates(weights, group_id, pair_data, avoid_nums)
                    group_pred_map[group_id] = final_group_pred
                    pred_nums.extend(final_group_pred)
                    print(f"{code}組最終候選 {GROUP_TAKE_COUNTS[group_id]} 球：{format_nums(final_group_pred)}")
                    print()

                pred_nums = sorted(pred_nums)
                hit_text, hit_count = prediction_hit_text(pred_nums, check_row)
                hit_nums, hit_sp_nums = prediction_hit_nums(pred_nums, check_row)
                hit_stats[hit_count] += 1
                print(f"核對日期：{check_row['date']}: {row_all_check_text(check_row)}")
                print(missing_nums_text(window_rows))
                for line in high_freq_pair_text(window_rows, pair_data):
                    print(line)
                pred_count = total_candidate_count()
                print(f"ABCD 預測候選球 {format_nums(pred_nums)} /> [{pred_count}] 球 ==> {hit_text}")
                append_backtest_record_csv(check_row["date"], group_pred_map, pred_nums, hit_nums, hit_sp_nums)

                new_record = build_score_record(check_row, window_count, group_weights, pred_nums, hit_count)
                print_old_new_compare(old_record, new_record)
                save_trace_record(new_record)
                old_record = new_record
                print()

            print_hit_count_summary(backtest_count, window_count, hit_stats)


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
        pair_data = high_freq_pair_data(window_rows)
        avoid_nums = recent_draw_nums(latest_row)
        for group_id in GROUPS:
            code, name, _start_num, _end_num = GROUPS[group_id]
            matched_count = sum(1 for _row_index, row in window_rows if is_matched(len(group_nums(row, group_id))))
            matched_percent = matched_count / len(window_rows) * 100 if window_rows else 0
            print(f"--- {code}組 {name} ---")
            print_window_detail(window_rows, latest_index, group_id)
            print(
                f"結果合條件 {BIRTHDAY_NUM_MATCH_MODE} {COMBINATION_TAKE_COUNT} 球，"
                f"查詢 {matched_count} / {len(window_rows)} 期統計 = {matched_count}期 "
                f"({matched_percent:.0f} %)"
            )
            weights = analyze_group_weights(window_rows, latest_index, group_id)
            print_group_weight_summary(weights, group_id)
            group_pred = select_group_candidates(weights, group_id)
            print(f"{code}組權重熱號 {GROUP_TAKE_COUNTS[group_id]} 球：{format_nums(group_pred)}")
            final_group_pred = select_final_group_candidates(weights, group_id, pair_data, avoid_nums)
            group_pred_map[group_id] = final_group_pred
            pred_nums.extend(final_group_pred)
            print(f"{code}組最終候選 {GROUP_TAKE_COUNTS[group_id]} 球：{format_nums(final_group_pred)}")
            print()

        pred_nums = sorted(pred_nums)
        pred_count = total_candidate_count()
        print(f"最後開獎日期：{latest_row['date']}: {row_all_check_text(latest_row)}")
        print(f"下期開獎日期：{next_draw_date or '未知'}")
        print(missing_nums_text(window_rows))
        for line in high_freq_pair_text(window_rows, pair_data):
            print(line)
        print(f"ABCD 下期預測候選球 {format_nums(pred_nums)} /> [{pred_count}] 球")
        print_predict_bet_groups(group_pred_map, pred_nums)
        print()


def print_predict_bet_groups(group_pred_map: dict[int, list[int]], pred_nums: list[int]) -> None:
    """列印 predict mode 的投注分組組合與隨機候選組。"""
    if not PRINT_PREDICT_BET_GROUPS:
        return

    abc_nums = sorted(group_pred_map.get(1, []) + group_pred_map.get(2, []) + group_pred_map.get(3, []))
    bcd_nums = sorted(group_pred_map.get(2, []) + group_pred_map.get(3, []) + group_pred_map.get(4, []))

    random_pool = sorted(set(pred_nums))
    if RANDOM_BET_GROUP_SEED is None:
        random_nums = sorted(random.sample(random_pool, min(RANDOM_BET_GROUP_TAKE, len(random_pool))))
    else:
        rng = random.Random(RANDOM_BET_GROUP_SEED)
        random_nums = sorted(rng.sample(random_pool, min(RANDOM_BET_GROUP_TAKE, len(random_pool))))

    print("----- 投注分組預測球組合 -----")
    print(
        f"1，A{GROUP_TAKE_COUNTS[1]} + B{GROUP_TAKE_COUNTS[2]} + C{GROUP_TAKE_COUNTS[3]} "
        f"= {format_nums(abc_nums)} /> [{len(abc_nums)}] 球"
    )
    print(
        f"2，B{GROUP_TAKE_COUNTS[2]} + C{GROUP_TAKE_COUNTS[3]} + D{GROUP_TAKE_COUNTS[4]} "
        f"= {format_nums(bcd_nums)} /> [{len(bcd_nums)}] 球"
    )
    print(f"3，系統自動 A+B+C+D 隨機選取 {len(random_nums)} 球 = {format_nums(random_nums)}")


def main() -> None:
    """程式進入點：讀取資料並依 MODE 執行回測或預測。"""
    draws = read_draws()
    if not draws:
        raise FileNotFoundError(f"找不到或未能讀取 M6：{M6_CSV}")

    print("====== ABCD 遠近權重候選球分析 ======")
    print(f"運作模式：{MODE}")
    print(f"回測期列表：{BACKTEST_DRAW_COUNT_LIST}")
    print(f"窗口期列表：{WINDOW_DRAW_COUNT_LIST}")
    print(f"ABCD 配額：{format_group_quota()}")
    print(f"符合條件：範圍內號碼數量 {BIRTHDAY_NUM_MATCH_MODE}{COMBINATION_TAKE_COUNT} 球")
    print("權重公式：出現次數 + 遠近比例權重 + 短期重複加分")
    print()

    if MODE == "backtest":
        run_backtest(draws)
    elif MODE == "predict":
        run_predict(draws)
    else:
        raise ValueError('MODE 只能是 "backtest" 或 "predict"。')


if __name__ == "__main__":
    main()
