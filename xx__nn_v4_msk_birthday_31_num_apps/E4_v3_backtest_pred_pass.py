from pathlib import Path
import csv
import itertools
import json
import random
from typing import TypedDict


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
M6_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"
COMB_DATA_DIR = CURRENT_DIR / "comb_data"
JSON_DIR = CURRENT_DIR / "json_data"
E4_COMB_CSV = COMB_DATA_DIR / "E4_v3_num_1_9_comb.csv"
E4_JSON = JSON_DIR / "E4_v3.json"

# E4_v3：1-9 追蹤模型，包含回測核對 + 真實下期預測。
# 核心定義：
# 1. 回測模式：每一期核對都只用該期之前的窗口期，不偷看核對期。
# 2. 真實預測：用最佳窗口期，並包含最新開獎期作分析窗口。
# 3. 追蹤對象：36 組雙球 + 9 個單球 + (00) 無 1-9。
BACKTEST_DRAW_COUNT = 1 # 回測核對期數。
WINDOW_DRAW_COUNT_LIST = [24]  # 多窗口期回測比較。
COMBINATION_TAKE_COUNT = 2  # 每期 N1-N6 需符合多少個 1-9。
BIRTHDAY_NUM_MIN = 1
BIRTHDAY_NUM_MAX = 9
BIRTHDAY_NUM_MATCH_MODE = ">="
PRIZE_OPTION = 3

# 雙球選擇模式：bridge 偏集中 3 號，spread 偏分散 4 號。
PREDICT_PAIR_COUNT = 2
PAIR_SELECT_MODE = "bridge"
MIN_PAIR_HIT_COUNT = 1

# 電腦隨機基準：每期隨機發 1-9 三球，只作回測對照，不影響主模型發球。
RANDOM_PREDICT_NUM_COUNT = 4
RANDOM_SEED = 20260905

# (00) 不發球規則：上一期沒有 1-9，下一期先不發；命中可續追，最多 2 期。
SKIP_AFTER_LAST_NONE = True
MAX_SKIP_STREAK = 2

# 24 期人氣記憶與冷球定義。冷球用 N1-N7 包特號計算，避免正號/特號口徑混亂。
MEMORY_WINDOW_COUNT = 24
COLD_WARN_GAP = 12
DEEP_COLD_WARN_GAP = 18
INCLUDE_SPECIAL_IN_COLD = True
'''
0-11期未出:不算冷
12-17期未出:冷球
18-23期未出:深冷球
24期或以上:極冷球
13期未出 = 冷球
18期未出 = 深冷球
24期未出 = 極冷球
'''


# 模型分數。雙球本身是主體，單球、週期、冷球、顏色、大小段作交叉驗證。
PAIR_HIT_WEIGHT = 10
SINGLE_HIT_WEIGHT = 2
CYCLE_PRESSURE_WEIGHT = 20
COLD_SUPPORT_BONUS = 6
DEEP_COLD_SUPPORT_BONUS = 10
RBG_MIX_BONUS = 3
ZONE_MIX_BONUS = 2

# 窗口期回測評分，分數最高的窗口期會成為下期預測最佳參數。
FULL_PAIR_HIT_SCORE = 20
HIT_2_SCORE = 10
HIT_1_5_SCORE = 6
HIT_1_SCORE = 2
HIT_0_PENALTY = -5
NONE_HIT_SCORE = 8


class DrawRow(TypedDict):
    date: str
    nums: list[int]
    special: int | None
    prize_count: float


class TrackRow(TypedDict):
    index: int
    row_type: str
    item: str
    periods: list[int]
    hit_count: int


class PairScore(TypedDict):
    index: int
    pair: tuple[int, int]
    periods: list[int]
    hit_count: int
    gaps: list[int]
    avg_gap: float
    wait_count: int
    cycle_pressure: float
    single_support: int
    cold_nums: list[int]
    cold_support: int
    rbg_type: str
    zone_type: str
    score: float


class WindowScore(TypedDict):
    window_count: int
    full_pair_hit_count: int
    hit_2_count: int
    hit_1_5_count: int
    hit_1_count: int
    hit_0_count: int
    none_hit_count: int
    score: float


class NextPrediction(TypedDict):
    best_window: int
    latest_draw_date: str
    skip_1_9: bool
    prediction_pairs: list[tuple[int, int]]
    prediction_nums: list[int]
    deep_cold_nums: list[int]
    top_pair_scores: list[dict[str, object]]


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


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"找不到 M6 CSV：{path}")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames:
            reader.fieldnames = [name.strip().lstrip("\ufeff") for name in reader.fieldnames]
        return [
            {(key or "").strip().lstrip("\ufeff"): (value or "").strip() for key, value in row.items()}
            for row in reader
        ]


def parse_draw_row(row: dict[str, str]) -> DrawRow:
    nums = [to_int(row.get(f"N{idx}")) for idx in range(1, 7)]
    special = to_int(row.get("N7"))
    return {
        "date": row.get("nDdate", ""),
        "nums": nums,
        "special": special if 1 <= special <= 49 else None,
        "prize_count": to_float(row.get(f"prize{PRIZE_OPTION}")),
    }


def read_draws() -> list[DrawRow]:
    return [row for row in (parse_draw_row(raw) for raw in read_csv_rows(M6_CSV)) if row["date"]]


def normal_group_nums(row: DrawRow) -> list[int]:
    return sorted(num for num in row["nums"] if BIRTHDAY_NUM_MIN <= num <= BIRTHDAY_NUM_MAX)


def group_nums(row: DrawRow) -> list[int]:
    nums = set(normal_group_nums(row))
    special = row["special"]
    if special is not None and BIRTHDAY_NUM_MIN <= special <= BIRTHDAY_NUM_MAX:
        nums.add(special)
    return sorted(nums)


def format_nums(nums: list[int] | tuple[int, ...]) -> str:
    return "[" + ",".join(str(num) for num in nums) + "]" if nums else "[]"


def format_check_nums(row: DrawRow) -> str:
    parts = [str(num) for num in normal_group_nums(row)]
    special = row["special"]
    if special is not None and BIRTHDAY_NUM_MIN <= special <= BIRTHDAY_NUM_MAX:
        parts.append(f"-{special}")
    return "[" + ",".join(parts) + "]" if parts else "[]"


def format_draw_1_31(row: DrawRow) -> str:
    # 明細顯示 N1-N6 + N7：1-31 顯示號碼，32-49 用 _，特號用 * 標示。
    parts = [str(num) if 1 <= num <= 31 else "_" for num in row["nums"]]
    special = row["special"]
    if special is not None and 1 <= special <= 31:
        parts.append(f"*{special}")
    else:
        parts.append("_")
    return "[" + ",".join(parts) + "]"


def build_track_rows(window_rows: list[DrawRow]) -> list[TrackRow]:
    # 生成 47 行追蹤資料：36 pair + 9 single + (00) + backdraw。
    total_rows = len(window_rows)
    pair_hits = {
        pair: []
        for pair in itertools.combinations(range(BIRTHDAY_NUM_MIN, BIRTHDAY_NUM_MAX + 1), 2)
    }
    single_hits = {num: [] for num in range(BIRTHDAY_NUM_MIN, BIRTHDAY_NUM_MAX + 1)}
    no_group_hits: list[int] = []

    for display_index, row in enumerate(window_rows, start=1):
        near_index = total_rows - display_index + 1
        row_nums = group_nums(row)
        if not row_nums:
            no_group_hits.append(near_index)
        if len(row_nums) == 1:
            for num in row_nums:
                single_hits[num].append(near_index)
        if len(row_nums) >= 2:
            for pair in itertools.combinations(row_nums, 2):
                pair_hits[pair].append(near_index)

    rows: list[TrackRow] = []
    for idx, (pair, periods) in enumerate(pair_hits.items(), start=1):
        rows.append({"index": idx, "row_type": "pair", "item": f"({pair[0]},{pair[1]})", "periods": periods, "hit_count": len(periods)})
    for num, periods in single_hits.items():
        rows.append({"index": 36 + num, "row_type": "single", "item": f"({num})", "periods": periods, "hit_count": len(periods)})
    rows.append({"index": 46, "row_type": "none", "item": "(00)", "periods": no_group_hits, "hit_count": len(no_group_hits)})
    rows.append({"index": 47, "row_type": "backdraw", "item": f"[{total_rows}]", "periods": [], "hit_count": total_rows})
    return rows


def get_backdraw(rows: list[TrackRow]) -> int:
    backdraw = next((row for row in rows if row["row_type"] == "backdraw"), None)
    return backdraw["hit_count"] if backdraw else 0


def build_gap_stats(periods: list[int], backdraw: int) -> tuple[list[int], float, int, float]:
    sorted_periods = sorted(periods, reverse=True)
    gaps = [sorted_periods[idx] - sorted_periods[idx + 1] for idx in range(len(sorted_periods) - 1)]
    avg_gap = sum(gaps) / len(gaps) if gaps else float(backdraw or 0)
    wait_count = min(sorted_periods) if sorted_periods else backdraw
    cycle_pressure = wait_count / avg_gap if avg_gap else 0.0
    return gaps, avg_gap, wait_count, cycle_pressure


def rbg_num(num: int) -> int:
    j_num = num - 1
    return (((j_num // 10) + j_num) % 6 // 2) + 1


def rbg_pair_type(pair: tuple[int, int]) -> str:
    return "+".join({1: "R", 2: "B", 3: "G"}[rbg_num(num)] for num in pair)


def zone_num(num: int) -> int:
    if num <= 3:
        return 1
    if num <= 6:
        return 2
    return 3


def zone_pair_type(pair: tuple[int, int]) -> str:
    return "+".join({1: "小", 2: "中", 3: "大"}[zone_num(num)] for num in pair)


def parse_pair(item: str) -> tuple[int, int] | None:
    parts = [part.strip() for part in item.strip("()").split(",")]
    if len(parts) != 2:
        return None
    return to_int(parts[0]), to_int(parts[1])


def build_cold_gaps(memory_rows: list[DrawRow]) -> dict[int, int]:
    # 冷球用最近 24 期記憶窗口計算；N7 特號可加入，符合用戶直觀記憶。
    gaps: dict[int, int] = {}
    for num in range(BIRTHDAY_NUM_MIN, BIRTHDAY_NUM_MAX + 1):
        gaps[num] = len(memory_rows) + 1
        for gap, row in enumerate(reversed(memory_rows), start=1):
            row_nums = group_nums(row) if INCLUDE_SPECIAL_IN_COLD else normal_group_nums(row)
            if num in row_nums:
                gaps[num] = gap - 1
                break
    return gaps


def cold_nums_from_gaps(cold_gaps: dict[int, int], min_gap: int = DEEP_COLD_WARN_GAP) -> list[int]:
    return [
        num
        for num in range(BIRTHDAY_NUM_MIN, BIRTHDAY_NUM_MAX + 1)
        if cold_gaps.get(num, 0) >= min_gap
    ]


def build_pair_scores(rows: list[TrackRow], memory_rows: list[DrawRow]) -> list[PairScore]:
    backdraw = get_backdraw(rows)
    cold_gaps = build_cold_gaps(memory_rows)
    single_hits = {
        to_int(row["item"].strip("()")): row["hit_count"]
        for row in rows
        if row["row_type"] == "single"
    }
    scores: list[PairScore] = []
    for row in rows:
        if row["row_type"] != "pair" or row["hit_count"] < MIN_PAIR_HIT_COUNT:
            continue
        pair = parse_pair(row["item"])
        if pair is None:
            continue
        gaps, avg_gap, wait_count, pressure = build_gap_stats(row["periods"], backdraw)
        single_support = single_hits.get(pair[0], 0) + single_hits.get(pair[1], 0)
        pair_cold_nums = [num for num in pair if cold_gaps[num] >= COLD_WARN_GAP]
        cold_support = sum(
            DEEP_COLD_SUPPORT_BONUS if cold_gaps[num] >= DEEP_COLD_WARN_GAP
            else COLD_SUPPORT_BONUS if cold_gaps[num] >= COLD_WARN_GAP
            else 0
            for num in pair
        )
        score = (
            row["hit_count"] * PAIR_HIT_WEIGHT
            + single_support * SINGLE_HIT_WEIGHT
            + pressure * CYCLE_PRESSURE_WEIGHT
            + cold_support
            + (RBG_MIX_BONUS if rbg_num(pair[0]) != rbg_num(pair[1]) else 0)
            + (ZONE_MIX_BONUS if zone_num(pair[0]) != zone_num(pair[1]) else 0)
        )
        scores.append({
            "index": row["index"],
            "pair": pair,
            "periods": row["periods"],
            "hit_count": row["hit_count"],
            "gaps": gaps,
            "avg_gap": avg_gap,
            "wait_count": wait_count,
            "cycle_pressure": pressure,
            "single_support": single_support,
            "cold_nums": pair_cold_nums,
            "cold_support": cold_support,
            "rbg_type": rbg_pair_type(pair),
            "zone_type": zone_pair_type(pair),
            "score": score,
        })
    return sorted(scores, key=lambda item: (-item["score"], -item["hit_count"], item["wait_count"], item["index"]))


def select_pairs_by_mode(pair_scores: list[PairScore]) -> list[PairScore]:
    if PREDICT_PAIR_COUNT <= 1:
        return pair_scores[:1]
    if not pair_scores:
        return []
    selected = [pair_scores[0]]
    first_nums = set(pair_scores[0]["pair"])
    for item in pair_scores[1:]:
        overlap = len(first_nums & set(item["pair"]))
        if PAIR_SELECT_MODE == "spread" and overlap == 0:
            selected.append(item)
            break
        if PAIR_SELECT_MODE == "bridge" and overlap == 1:
            selected.append(item)
            break
    for item in pair_scores[1:]:
        if len(selected) >= PREDICT_PAIR_COUNT:
            break
        if item not in selected:
            selected.append(item)
    return selected[:PREDICT_PAIR_COUNT]


def select_prediction(pair_scores: list[PairScore], should_skip: bool) -> tuple[list[PairScore], bool]:
    predictions = [] if should_skip else select_pairs_by_mode(pair_scores)
    return predictions, should_skip


def should_skip_by_none_rule(window_rows: list[DrawRow], skip_streak: int, last_skip_hit: bool) -> bool:
    if not SKIP_AFTER_LAST_NONE or skip_streak >= MAX_SKIP_STREAK:
        return False
    last_draw_is_none = bool(window_rows) and not group_nums(window_rows[-1])
    return last_draw_is_none or (skip_streak > 0 and last_skip_hit)


def should_skip_next_by_none_rule(draws: list[DrawRow]) -> bool:
    if not SKIP_AFTER_LAST_NONE or not draws or group_nums(draws[-1]):
        return False
    consecutive_none = 0
    for row in reversed(draws):
        if group_nums(row):
            break
        consecutive_none += 1
    return consecutive_none <= MAX_SKIP_STREAK


def merged_prediction_nums(predictions: list[PairScore]) -> list[int]:
    return sorted({num for item in predictions for num in item["pair"]})


def calc_nums_hit(prediction_nums: list[int], check_row: DrawRow) -> tuple[list[int], list[int], float]:
    pred_nums = set(prediction_nums)
    normal_hits = sorted(pred_nums & set(normal_group_nums(check_row)))
    special = check_row["special"]
    special_hits = [special] if special is not None and special in pred_nums else []
    return normal_hits, special_hits, len(normal_hits) + (0.5 if special_hits else 0.0)


def calc_hit(predictions: list[PairScore], check_row: DrawRow) -> tuple[list[int], list[int], float]:
    return calc_nums_hit(merged_prediction_nums(predictions), check_row)


def build_random_prediction(check_index: int, window_count: int) -> list[int]:
    # 固定 seed 加上回測位置，令每次執行可重現同一組隨機基準。
    rng = random.Random(RANDOM_SEED + check_index * 1000 + window_count)
    nums = range(BIRTHDAY_NUM_MIN, BIRTHDAY_NUM_MAX + 1)
    return sorted(rng.sample(list(nums), RANDOM_PREDICT_NUM_COUNT))


def format_hit_result(prefix: str, normal_hits: list[int], special_hits: list[int], hit_score: float) -> str:
    special_text = f" + 特號{format_nums(special_hits)}" if special_hits else ""
    return f"{prefix}命中{format_nums(normal_hits)}{special_text} /> {hit_score:g} 球"


def calc_group_score(row: DrawRow) -> float:
    # 統計採集口徑：N1-N7 每球都算 1；特號 0.5 只用在命中核對獎項。
    return float(len(group_nums(row)))


def count_group_comb_nums(row: DrawRow) -> int:
    # 統計可產生 1-36 雙球組合的實際球數；N7 特號在 1-9 內也當一個球加入。
    return len(group_nums(row))


def count_pair_combinations(num_count: int) -> int:
    return num_count * (num_count - 1) // 2 if num_count >= 2 else 0


def format_recent_status(row: DrawRow) -> str:
    score = calc_group_score(row)
    if score == 0:
        return "None"
    if score == 1:
        return "單球"
    return f"{score:g} 球"


def print_recent_window_hint(window_rows: list[DrawRow]) -> None:
    # 顯示當期預測前可見的最近 3 期，用來觀察短期 1-9 是否連續出現或轉弱。
    recent_rows = window_rows[-3:]
    start_label = len(recent_rows)
    for offset, row in enumerate(recent_rows):
        label = start_label - offset
        print(f"   最近 {label} 期 {format_draw_1_31(row)} = {format_recent_status(row)}")


def count_full_hit_pairs(predictions: list[PairScore], check_row: DrawRow) -> int:
    check_nums = set(group_nums(check_row))
    return sum(1 for item in predictions if set(item["pair"]).issubset(check_nums))


def build_window_score(window_count: int, hit_scores: list[float], full_pair_hit_count: int, none_hit_count: int) -> WindowScore:
    score = (
        full_pair_hit_count * FULL_PAIR_HIT_SCORE
        + sum(hit == 2 for hit in hit_scores) * HIT_2_SCORE
        + sum(hit == 1.5 for hit in hit_scores) * HIT_1_5_SCORE
        + sum(hit == 1 for hit in hit_scores) * HIT_1_SCORE
        + sum(hit == 0 for hit in hit_scores) * HIT_0_PENALTY
        + none_hit_count * NONE_HIT_SCORE
    )
    return {
        "window_count": window_count,
        "full_pair_hit_count": full_pair_hit_count,
        "hit_2_count": sum(hit == 2 for hit in hit_scores),
        "hit_1_5_count": sum(hit == 1.5 for hit in hit_scores),
        "hit_1_count": sum(hit == 1 for hit in hit_scores),
        "hit_0_count": sum(hit == 0 for hit in hit_scores),
        "none_hit_count": none_hit_count,
        "score": float(score),
    }


def write_comb_csv(rows: list[TrackRow]) -> None:
    COMB_DATA_DIR.mkdir(parents=True, exist_ok=True)
    with E4_COMB_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["index", "type", "item_1_9", "backtest_hit_periods", "hit_count"])
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "index": row["index"],
                "type": row["row_type"],
                "item_1_9": row["item"],
                "backtest_hit_periods": format_nums(row["periods"]),
                "hit_count": row["hit_count"],
            })


def print_pair_detail(prefix: str, predictions: list[PairScore], should_skip: bool, cold_nums: list[int]) -> None:
    print(f"   18期內未出冷號：{format_nums(cold_nums) if cold_nums else '-'}")
    if should_skip:
        print(f"   {prefix}：(00)=None，不發 1-9")
        return
    pairs_text = "，".join(f"({item['pair'][0]},{item['pair'][1]})" for item in predictions)
    print(f"   {prefix}：{pairs_text} -> 合併球 {format_nums(merged_prediction_nums(predictions))}")
    for item in predictions:
        print(
            f"   明細：({item['pair'][0]},{item['pair'][1]}) 出現{item['hit_count']}次，"
            f"等待{item['wait_count']}期，單球支撐{item['single_support']}，"
            f"冷號{format_nums(item['cold_nums']) if item['cold_nums'] else '-'}，"
            f"{item['rbg_type']}，{item['zone_type']}。"
        )


def run_backtest(draws: list[DrawRow]) -> tuple[list[WindowScore], list[dict[str, object]]]:
    last_check_index = len(draws) - 1
    first_check_index = max(0, last_check_index - BACKTEST_DRAW_COUNT + 1)
    check_indices = list(range(first_check_index, last_check_index + 1))
    all_results: list[dict[str, object]] = []
    window_scores: list[WindowScore] = []

    print("====== E4_v3 1-9 追蹤模型回測核對 ======")
    print(f"BACKTEST_DRAW_COUNT = {BACKTEST_DRAW_COUNT}")
    print(f"WINDOW_DRAW_COUNT_LIST = {WINDOW_DRAW_COUNT_LIST}")
    print(f"PAIR_SELECT_MODE = {PAIR_SELECT_MODE}")
    print(f"(00)規則：上一期無 1-9 先不發；命中可續追；最多 {MAX_SKIP_STREAK} 期。")
    print(f"冷球：{COLD_WARN_GAP}期未出；深冷：{DEEP_COLD_WARN_GAP}期未出；記憶窗口：{MEMORY_WINDOW_COUNT}期。")
    print()

    for window_count in WINDOW_DRAW_COUNT_LIST:
        hit_scores: list[float] = []
        full_pair_hit_count = 0
        none_hit_count = 0
        skip_streak = 0
        last_skip_hit = False
        print(f"====== 窗口期 {window_count} 期 回測核對 ======")
        for idx, check_index in enumerate(check_indices, start=1):
            check_row = draws[check_index]
            window_rows = draws[max(0, check_index - window_count):check_index]
            backtest_row = window_rows[-1] if window_rows else check_row
            memory_rows = draws[max(0, check_index - MEMORY_WINDOW_COUNT):check_index]
            deep_cold_nums = cold_nums_from_gaps(build_cold_gaps(memory_rows))
            track_rows = build_track_rows(window_rows)
            pair_scores = build_pair_scores(track_rows, memory_rows)
            should_skip = should_skip_by_none_rule(window_rows, skip_streak, last_skip_hit)
            predictions, should_skip = select_prediction(pair_scores, should_skip)
            random_prediction = build_random_prediction(check_index, window_count)
            random_normal_hits, random_special_hits, random_hit_score = calc_nums_hit(random_prediction, check_row)
            write_comb_csv(track_rows)

            if should_skip:
                hit_score = 0.0
                normal_hits: list[int] = []
                special_hits: list[int] = []
                if not group_nums(check_row):
                    none_hit_count += 1
                print(
                    f"{idx}，回測期 {backtest_row['date']} {format_draw_1_31(backtest_row)}，"
                    f"核對期：{check_row['date']}，{format_draw_1_31(check_row)}"
                )
                print_pair_detail("預測", predictions, should_skip, deep_cold_nums)
                print_recent_window_hint(window_rows)
                print("   命中[] /> 0 球")
                print(f"   隨機預測{format_nums(random_prediction)}，{format_hit_result('隨機', random_normal_hits, random_special_hits, random_hit_score)}")
                if idx < len(check_indices):
                    print("/ ------------------------------------------------")
            else:
                normal_hits, special_hits, hit_score = calc_hit(predictions, check_row)
                if count_full_hit_pairs(predictions, check_row):
                    full_pair_hit_count += 1
                print(
                    f"{idx}，回測期 {backtest_row['date']} {format_draw_1_31(backtest_row)}，"
                    f"核對期：{check_row['date']}，{format_draw_1_31(check_row)}"
                )
                print_pair_detail("預測", predictions, should_skip, deep_cold_nums)
                print_recent_window_hint(window_rows)
                print(f"   {format_hit_result('', normal_hits, special_hits, hit_score)}")
                print(f"   隨機預測{format_nums(random_prediction)}，{format_hit_result('隨機', random_normal_hits, random_special_hits, random_hit_score)}")
                if idx < len(check_indices):
                    print("/ ------------------------------------------------")
            hit_scores.append(hit_score)
            all_results.append({
                "window_count": window_count,
                "check_no": idx,
                "check_date": check_row["date"],
                "check_nums": format_check_nums(check_row),
                "skip_1_9": should_skip,
                "prediction_pairs": [] if should_skip else [item["pair"] for item in predictions],
                "prediction_nums": [] if should_skip else merged_prediction_nums(predictions),
                "deep_cold_nums": deep_cold_nums,
                "normal_hits": normal_hits,
                "special_hits": special_hits,
                "hit_score": hit_score,
                "check_group_score": calc_group_score(check_row),
                "check_group_nums_count": count_group_comb_nums(check_row),
                "random_prediction_nums": random_prediction,
                "random_normal_hits": random_normal_hits,
                "random_special_hits": random_special_hits,
                "random_hit_score": random_hit_score,
            })
            last_skip_hit = should_skip and not group_nums(check_row)
            skip_streak = skip_streak + 1 if should_skip else 0
        summary = build_window_score(window_count, hit_scores, full_pair_hit_count, none_hit_count)
        window_scores.append(summary)
        print("----------------------")
        print(
            f"窗口統計：雙球全中 {summary['full_pair_hit_count']} 期，"
            f"2球 {summary['hit_2_count']} 期，1.5球 {summary['hit_1_5_count']} 期，"
            f"1球 {summary['hit_1_count']} 期，0球 {summary['hit_0_count']} 期，"
            f"(00)命中 {summary['none_hit_count']} 期，分數 {summary['score']:g}"
        )
        print()
    window_scores.sort(key=lambda item: (-item["score"], -item["full_pair_hit_count"], -item["hit_2_count"], item["hit_0_count"], item["window_count"]))
    return window_scores, all_results


def predict_next(draws: list[DrawRow], best_window: int) -> NextPrediction:
    # 真實預測：窗口包含最新一期，因下一期未開獎，不能核對。
    window_rows = draws[-best_window:]
    memory_rows = draws[-MEMORY_WINDOW_COUNT:]
    deep_cold_nums = cold_nums_from_gaps(build_cold_gaps(memory_rows))
    track_rows = build_track_rows(window_rows)
    pair_scores = build_pair_scores(track_rows, memory_rows)
    should_skip = should_skip_next_by_none_rule(draws)
    predictions, should_skip = select_prediction(pair_scores, should_skip)
    write_comb_csv(track_rows)
    return {
        "best_window": best_window,
        "latest_draw_date": draws[-1]["date"],
        "skip_1_9": should_skip,
        "prediction_pairs": [] if should_skip else [item["pair"] for item in predictions],
        "prediction_nums": [] if should_skip else merged_prediction_nums(predictions),
        "deep_cold_nums": deep_cold_nums,
        "top_pair_scores": [
            {
                "index": item["index"],
                "pair": item["pair"],
                "hit_count": item["hit_count"],
                "wait_count": item["wait_count"],
                "single_support": item["single_support"],
                "cold_nums": item["cold_nums"],
                "cold_support": item["cold_support"],
                "score": round(item["score"], 2),
            }
            for item in pair_scores[:10]
        ],
    }


def write_json(window_scores: list[WindowScore], results: list[dict[str, object]], next_pred: NextPrediction) -> None:
    JSON_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": "E4_v3",
        "params": {
            "backtest_draw_count": BACKTEST_DRAW_COUNT,
            "window_draw_count_list": WINDOW_DRAW_COUNT_LIST,
            "pair_select_mode": PAIR_SELECT_MODE,
            "memory_window_count": MEMORY_WINDOW_COUNT,
            "cold_warn_gap": COLD_WARN_GAP,
            "deep_cold_warn_gap": DEEP_COLD_WARN_GAP,
            "include_special_in_cold": INCLUDE_SPECIAL_IN_COLD,
        },
        "best_window": window_scores[0] if window_scores else None,
        "window_scores": window_scores,
        "next_prediction": next_pred,
        "backtest_results": results,
    }
    with E4_JSON.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def get_result_float(result: dict[str, object], key: str) -> float:
    value = result.get(key, 0)
    return to_float(value)


def get_result_int(result: dict[str, object], key: str) -> int:
    value = result.get(key, 0)
    return to_int(value)


def print_random_summary(best_window: int, results: list[dict[str, object]]) -> None:
    best_results = [row for row in results if get_result_int(row, "window_count") == best_window]
    total = len(best_results)
    scores = [get_result_float(row, "random_hit_score") for row in best_results]
    check_scores = [get_result_float(row, "check_group_score") for row in best_results]
    actual_1_plus_count = sum(score >= 1 for score in check_scores)
    actual_2_plus_count = sum(score >= 2 for score in check_scores)
    random_1_plus_hit_count = sum(score >= 1 for score in scores)
    random_2_plus_hit_count = sum(score >= 2 for score in scores)
    random_1_plus_hit_rate = (random_1_plus_hit_count / total * 100) if total else 0.0
    random_2_plus_hit_rate = (random_2_plus_hit_count / total * 100) if total else 0.0
    random_1_plus_valid_rate = (random_1_plus_hit_count / actual_1_plus_count * 100) if actual_1_plus_count else 0.0
    random_2_plus_valid_rate = (random_2_plus_hit_count / actual_2_plus_count * 100) if actual_2_plus_count else 0.0

    print(f"====== 隨機 1-9 發 {RANDOM_PREDICT_NUM_COUNT} 球回測命中率 N1..N6 + N7 ======")
    print(f"統計窗口期：{best_window} 期，回測期數：{total} 期")
    for score in [3.0, 2.5, 2.0, 1.5, 1.0, 0.5, 0.0]:
        count = sum(hit == score for hit in scores)
        percent = (count / total * 100) if total else 0.0
        print(f"{score:g} 球 = {count} 期 / {total} 期，{percent:.2f}%")
    print(f"隨機命中 >=1 球 = {random_1_plus_hit_count}期 / {total} 期，{random_1_plus_hit_rate:.2f}%")
    print(f"有效命中率：{random_1_plus_hit_count}/{actual_1_plus_count} 期，{random_1_plus_valid_rate:.2f}%（只計實際 >=1 球期）")
    print(f"隨機命中 >=2 球 = {random_2_plus_hit_count}期 / {total} 期，{random_2_plus_hit_rate:.2f}%")
    print(f"有效命中率：{random_2_plus_hit_count}/{actual_2_plus_count} 期，{random_2_plus_valid_rate:.2f}%（只計實際 >=2 球期）")
    print()


def print_check_group_summary(best_window: int, results: list[dict[str, object]]) -> None:
    best_results = [row for row in results if get_result_int(row, "window_count") == best_window]
    total = len(best_results)
    scores = [get_result_float(row, "check_group_score") for row in best_results]
    group_nums_counts = [get_result_int(row, "check_group_nums_count") for row in best_results]
    count_4 = sum(score == 4 for score in scores)
    count_3 = sum(score == 3 for score in scores)
    count_2 = sum(score == 2 for score in scores)
    count_1 = sum(score == 1 for score in scores)
    count_none = sum(score == 0 for score in scores)
    count_1_plus = sum(score >= 1 for score in scores)
    count_2_plus = sum(score >= 2 for score in scores)
    pair_comb_total = sum(count_pair_combinations(count) for count in group_nums_counts)
    model_1_plus_hit_count = sum(get_result_float(row, "hit_score") >= 1 for row in best_results)
    model_2_plus_hit_count = sum(get_result_float(row, "hit_score") >= 2 for row in best_results)
    actual_1_plus_rate = (count_1_plus / total * 100) if total else 0.0
    possible_2_hit_rate = (count_2_plus / total * 100) if total else 0.0
    model_1_plus_hit_rate = (model_1_plus_hit_count / total * 100) if total else 0.0
    model_2_plus_hit_rate = (model_2_plus_hit_count / total * 100) if total else 0.0
    model_1_plus_valid_rate = (model_1_plus_hit_count / count_1_plus * 100) if count_1_plus else 0.0
    model_2_plus_valid_rate = (model_2_plus_hit_count / count_2_plus * 100) if count_2_plus else 0.0

    print("====== 回測核對期 1-9 實際開出分布 ======")
    print(f"統計窗口期：{best_window} 期，回測期數：{total} 期")
    print("開獎期內 N1..N7 包含 1-9，有多少期。")
    print(f"4球 = {count_4} 期")
    print(f"3球 = {count_3} 期")
    print(f"2球 = {count_2} 期")
    print(f"1球 = {count_1} 期")
    print(f"00球 = {count_none} 期")
    print(f"實際 >=1 球：{count_1_plus}/{total} 期，{actual_1_plus_rate:.2f}%")
    print(f"回測：開獎 2 球號，產生 1-36 雙球組合：{count_2_plus}/{total} 期，{possible_2_hit_rate:.2f}%")
    print(f"回測：{total} 期內，有機會命中 2 球組合總數：{pair_comb_total} 組")
    print(f"回測 - 預測發球組合，真實命中 >=1 球 = {model_1_plus_hit_count}期 / {total} 期，{model_1_plus_hit_rate:.2f}%")
    print(f"有效命中率：{model_1_plus_hit_count}/{count_1_plus} 期，{model_1_plus_valid_rate:.2f}%（只計實際 >=1 球期）")
    print(f"回測 - 預測發球組合，真實命中 >=2 球 = {model_2_plus_hit_count}期 / {total} 期，{model_2_plus_hit_rate:.2f}%")
    print(f"有效命中率：{model_2_plus_hit_count}/{count_2_plus} 期，{model_2_plus_valid_rate:.2f}%（只計實際 >=2 球期）")
    print("說明：開獎期 1-9 號出現 [0球] 或 [1球]，不會產生 1-36 雙球組合。")
    print()


def print_best_and_next(draws: list[DrawRow], window_scores: list[WindowScore], results: list[dict[str, object]], next_pred: NextPrediction) -> None:
    print("====== E4_v3 窗口期最佳優化參數提示 ======")
    print("排名 | 窗口期 | 雙球全中 | 2球 | 1.5球 | 1球 | 0球 | (00) | 分數")
    for rank, item in enumerate(window_scores, start=1):
        print(
            f"{rank:>2} | {item['window_count']:>4} | {item['full_pair_hit_count']:>4} | "
            f"{item['hit_2_count']:>2} | {item['hit_1_5_count']:>4} | "
            f"{item['hit_1_count']:>2} | {item['hit_0_count']:>2} | "
            f"{item['none_hit_count']:>4} | {item['score']:>5g}"
        )
    print()

    print_check_group_summary(next_pred["best_window"], results)
    print_random_summary(next_pred["best_window"], results)

    print("====== E4_v3 真實下期預測 ======")
    print(f"預測窗口：包含最新開獎期 {next_pred['latest_draw_date']}")
    print(f"最佳窗口期：{next_pred['best_window']}")
    if next_pred["skip_1_9"]:
        print("預測：(00)=None，不發 1-9，配額可轉給 10-20 / 21-31。")
    else:
        pairs_text = "，".join(f"({pair[0]},{pair[1]})" for pair in next_pred["prediction_pairs"])
        print(f"預測雙球：{pairs_text}")
        print(f"合併候選球：{format_nums(next_pred['prediction_nums'])}")
    print("下一期未開獎，不能核對。")
    print()
    print(f"CSV 已寫入：{E4_COMB_CSV}")
    print(f"JSON 已寫入：{E4_JSON}")


def main() -> None:
    draws = read_draws()
    if not draws:
        raise RuntimeError("M6 沒有可用開獎資料。")
    window_scores, results = run_backtest(draws)
    best_window = window_scores[0]["window_count"] if window_scores else WINDOW_DRAW_COUNT_LIST[0]
    next_pred = predict_next(draws, best_window)
    write_json(window_scores, results, next_pred)
    print_best_and_next(draws, window_scores, results, next_pred)


if __name__ == "__main__":
    main()
