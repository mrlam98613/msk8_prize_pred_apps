from pathlib import Path
import csv
import itertools
import json
from typing import TypedDict


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
M6_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"
COMB_DATA_DIR = CURRENT_DIR / "comb_data"
JSON_DIR = CURRENT_DIR / "json_data"
E4_COMB_CSV = COMB_DATA_DIR / "E4_num_1_9_comb.csv"
E4_JSON = JSON_DIR / "E4_v2.json"

# E4_v2：獨立回測核對版。
# 每一期核對都用「該核對期之前的窗口期」建立 1-9 追蹤資料，再用 E4 模型預測雙球組合。
BACKTEST_DRAW_COUNT = 24  # 回測核對期數；1=只核對最後一期，之後可改 10、24。
WINDOW_DRAW_COUNT_LIST = [21, 48]  # 多組窗口期；窗口期不包括核對期。
COMBINATION_TAKE_COUNT = 2  # 每期開獎號包含多少個生日號，1=單球，2=雙球，3=三球。
BIRTHDAY_NUM_MIN = 1  # 分析號碼範圍最小值。
BIRTHDAY_NUM_MAX = 9  # 分析號碼範圍最大值。
BIRTHDAY_NUM_MATCH_MODE = ">="  # 分析號碼匹配模式，">=" 或 "=="。
PRIZE_OPTION = 3  # 查詢中獎注數，1=頭獎，2=二獎，3=三獎。

# 模型參數：跟 E4_v1 同一套公式，方便比較。
MIN_PAIR_HIT_COUNT = 1  # 雙球組合最少出現幾次才進入排名。
PAIR_HIT_WEIGHT = 10  # 雙球本身出現次數權重。
SINGLE_HIT_WEIGHT = 2  # 兩個單球各自出現次數支撐權重。
CYCLE_PRESSURE_WEIGHT = 20  # 週期壓力權重。
RBG_MIX_BONUS = 3  # RBG 不同色組合加分。
ZONE_MIX_BONUS = 2  # 小中大不同段組合加分。
PREDICT_PAIR_COUNT = 2  # 每期預測幾組 1-9 雙球組合。
PAIR_SELECT_MODE = "bridge"  # bridge=兩組可共用核心號，合併多數 3 號；spread=兩組不共用號，合併多數 4 號。
NONE_PRESSURE_WARN = 0.85  # (00) 無 1-9 壓力提示門檻。

# 窗口期評分：用來自動選出下一期預測應採用的最佳窗口期。
FULL_PAIR_HIT_SCORE = 20  # 預測雙球組合全中，一期加分。
HIT_2_SCORE = 10  # 命中 2 球，一期加分。
HIT_1_5_SCORE = 6  # 命中 1.5 球，一期加分。
HIT_1_SCORE = 2  # 命中 1 球，一期加分。
HIT_0_PENALTY = -5  # 命中 0 球，一期扣分。
NONE_HIT_SCORE = 8  # 預測 (00)=None 且該期真的無 1-9，一期加分。


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
    rows = [parse_draw_row(row) for row in read_csv_rows(M6_CSV)]
    return [row for row in rows if row["date"]]


def group_nums(row: DrawRow) -> list[int]:
    nums = {num for num in row["nums"] if BIRTHDAY_NUM_MIN <= num <= BIRTHDAY_NUM_MAX}
    special = row["special"]
    if special is not None and BIRTHDAY_NUM_MIN <= special <= BIRTHDAY_NUM_MAX:
        nums.add(special)
    return sorted(nums)


def normal_group_nums(row: DrawRow) -> list[int]:
    return sorted(num for num in row["nums"] if BIRTHDAY_NUM_MIN <= num <= BIRTHDAY_NUM_MAX)


def is_matched(row: DrawRow) -> bool:
    count = len(normal_group_nums(row))
    if BIRTHDAY_NUM_MATCH_MODE == "==":
        return count == COMBINATION_TAKE_COUNT
    return count >= COMBINATION_TAKE_COUNT


def format_nums(nums: list[int] | tuple[int, ...]) -> str:
    if not nums:
        return "[]"
    return "[" + ",".join(str(num) for num in nums) + "]"


def format_check_nums(row: DrawRow) -> str:
    parts = [str(num) for num in normal_group_nums(row)]
    special = row["special"]
    if special is not None and BIRTHDAY_NUM_MIN <= special <= BIRTHDAY_NUM_MAX:
        parts.append(f"-{special}")
    return "[" + ",".join(parts) + "]" if parts else "[]"


def build_track_rows(window_rows: list[DrawRow]) -> list[TrackRow]:
    total_rows = len(window_rows)
    pair_hits: dict[tuple[int, int], list[int]] = {
        pair: []
        for pair in itertools.combinations(range(BIRTHDAY_NUM_MIN, BIRTHDAY_NUM_MAX + 1), 2)
    }
    single_hits: dict[int, list[int]] = {
        num: []
        for num in range(BIRTHDAY_NUM_MIN, BIRTHDAY_NUM_MAX + 1)
    }
    no_group_hits: list[int] = []

    for display_index, row in enumerate(window_rows, start=1):
        near_index = total_rows - display_index + 1
        row_nums = group_nums(row)
        if not row_nums:
            no_group_hits.append(near_index)
        for num in row_nums:
            single_hits[num].append(near_index)
        for pair in itertools.combinations(row_nums, 2):
            pair_hits[pair].append(near_index)

    rows: list[TrackRow] = [
        {
            "index": idx,
            "row_type": "pair",
            "item": f"({pair[0]},{pair[1]})",
            "periods": hit_periods,
            "hit_count": len(hit_periods),
        }
        for idx, (pair, hit_periods) in enumerate(pair_hits.items(), start=1)
    ]
    rows.extend(
        {
            "index": 36 + num,
            "row_type": "single",
            "item": f"({num})",
            "periods": hit_periods,
            "hit_count": len(hit_periods),
        }
        for num, hit_periods in single_hits.items()
    )
    rows.append(
        {
            "index": 46,
            "row_type": "none",
            "item": "(00)",
            "periods": no_group_hits,
            "hit_count": len(no_group_hits),
        }
    )
    rows.append(
        {
            "index": 47,
            "row_type": "backdraw",
            "item": f"[{total_rows}]",
            "periods": [],
            "hit_count": total_rows,
        }
    )
    return rows


def get_backdraw(rows: list[TrackRow]) -> int:
    backdraw = next((row for row in rows if row["row_type"] == "backdraw"), None)
    return backdraw["hit_count"] if backdraw else 0


def build_gap_stats(periods: list[int], backdraw: int) -> tuple[list[int], float, int, float]:
    sorted_periods = sorted(periods, reverse=True)
    gaps = [
        sorted_periods[idx] - sorted_periods[idx + 1]
        for idx in range(len(sorted_periods) - 1)
    ]
    avg_gap = sum(gaps) / len(gaps) if gaps else float(backdraw or 0)
    wait_count = min(sorted_periods) if sorted_periods else backdraw
    cycle_pressure = wait_count / avg_gap if avg_gap else 0.0
    return gaps, avg_gap, wait_count, cycle_pressure


def rbg_num(num: int) -> int:
    j_num = num - 1
    return (((j_num // 10) + j_num) % 6 // 2) + 1


def rbg_pair_type(pair: tuple[int, int]) -> str:
    labels = {1: "R", 2: "B", 3: "G"}
    return "+".join(labels[rbg_num(num)] for num in pair)


def zone_num(num: int) -> int:
    if BIRTHDAY_NUM_MIN <= num <= 3:
        return 1
    if 4 <= num <= 6:
        return 2
    return 3


def zone_pair_type(pair: tuple[int, int]) -> str:
    labels = {1: "小", 2: "中", 3: "大"}
    return "+".join(labels[zone_num(num)] for num in pair)


def parse_pair(item: str) -> tuple[int, int] | None:
    if not (item.startswith("(") and item.endswith(")")):
        return None
    parts = [part.strip() for part in item.strip("()").split(",")]
    if len(parts) != 2:
        return None
    return to_int(parts[0]), to_int(parts[1])


def build_pair_scores(rows: list[TrackRow]) -> list[PairScore]:
    backdraw = get_backdraw(rows)
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
        gaps, avg_gap, wait_count, cycle_pressure = build_gap_stats(row["periods"], backdraw)
        single_support = single_hits.get(pair[0], 0) + single_hits.get(pair[1], 0)
        rbg_bonus = RBG_MIX_BONUS if rbg_num(pair[0]) != rbg_num(pair[1]) else 0
        zone_bonus = ZONE_MIX_BONUS if zone_num(pair[0]) != zone_num(pair[1]) else 0
        score = (
            row["hit_count"] * PAIR_HIT_WEIGHT
            + single_support * SINGLE_HIT_WEIGHT
            + cycle_pressure * CYCLE_PRESSURE_WEIGHT
            + rbg_bonus
            + zone_bonus
        )
        scores.append(
            {
                "index": row["index"],
                "pair": pair,
                "periods": row["periods"],
                "hit_count": row["hit_count"],
                "gaps": gaps,
                "avg_gap": avg_gap,
                "wait_count": wait_count,
                "cycle_pressure": cycle_pressure,
                "single_support": single_support,
                "rbg_type": rbg_pair_type(pair),
                "zone_type": zone_pair_type(pair),
                "score": score,
            }
        )
    return sorted(scores, key=lambda item: (-item["score"], -item["hit_count"], item["wait_count"], item["index"]))


def build_none_pressure(rows: list[TrackRow]) -> tuple[list[int], list[int], float, int, float]:
    none_row = next((row for row in rows if row["row_type"] == "none"), None)
    backdraw = get_backdraw(rows)
    if none_row is None:
        return [], [], 0.0, backdraw, 0.0
    gaps, avg_gap, wait_count, pressure = build_gap_stats(none_row["periods"], backdraw)
    return none_row["periods"], gaps, avg_gap, wait_count, pressure


def select_pairs_by_mode(pair_scores: list[PairScore]) -> list[PairScore]:
    if PREDICT_PAIR_COUNT <= 1:
        return pair_scores[:1]
    if not pair_scores:
        return []

    selected = [pair_scores[0]]
    first_pair_nums = set(pair_scores[0]["pair"])
    for item in pair_scores[1:]:
        pair_nums = set(item["pair"])
        overlap_count = len(first_pair_nums & pair_nums)
        if PAIR_SELECT_MODE == "spread" and overlap_count == 0:
            selected.append(item)
            break
        if PAIR_SELECT_MODE == "bridge" and overlap_count == 1:
            selected.append(item)
            break

    if len(selected) < PREDICT_PAIR_COUNT:
        for item in pair_scores[1:]:
            if item not in selected:
                selected.append(item)
            if len(selected) >= PREDICT_PAIR_COUNT:
                break
    return selected[:PREDICT_PAIR_COUNT]


def select_prediction(pair_scores: list[PairScore], rows: list[TrackRow]) -> tuple[list[PairScore], bool]:
    none_pressure = build_none_pressure(rows)
    predictions = select_pairs_by_mode(pair_scores)
    should_skip = none_pressure[4] >= NONE_PRESSURE_WARN and none_pressure[4] > max(
        (item["cycle_pressure"] for item in predictions),
        default=0.0,
    )
    return predictions, should_skip


def calc_pair_hit(predictions: list[PairScore], check_row: DrawRow) -> tuple[list[int], list[int], float]:
    pred_nums = {num for item in predictions for num in item["pair"]}
    normal_hits = sorted(pred_nums & set(normal_group_nums(check_row)))
    special = check_row["special"]
    special_hits = [special] if special is not None and special in pred_nums else []
    return normal_hits, special_hits, len(normal_hits) + (0.5 if special_hits else 0.0)


def count_full_hit_pairs(predictions: list[PairScore], check_row: DrawRow) -> int:
    check_nums = set(group_nums(check_row))
    return sum(1 for item in predictions if set(item["pair"]).issubset(check_nums))


def build_window_score(window_count: int, hit_scores: list[float], full_pair_hit_count: int, none_hit_count: int) -> WindowScore:
    hit_2_count = sum(score == 2 for score in hit_scores)
    hit_1_5_count = sum(score == 1.5 for score in hit_scores)
    hit_1_count = sum(score == 1 for score in hit_scores)
    hit_0_count = sum(score == 0 for score in hit_scores)
    score = (
        full_pair_hit_count * FULL_PAIR_HIT_SCORE
        + hit_2_count * HIT_2_SCORE
        + hit_1_5_count * HIT_1_5_SCORE
        + hit_1_count * HIT_1_SCORE
        + hit_0_count * HIT_0_PENALTY
        + none_hit_count * NONE_HIT_SCORE
    )
    return {
        "window_count": window_count,
        "full_pair_hit_count": full_pair_hit_count,
        "hit_2_count": hit_2_count,
        "hit_1_5_count": hit_1_5_count,
        "hit_1_count": hit_1_count,
        "hit_0_count": hit_0_count,
        "none_hit_count": none_hit_count,
        "score": score,
    }


def print_window_summary(window_score: WindowScore) -> None:
    print("----------------------")
    print("窗口期核對命中統計")
    print(f"命中雙球組合 = {window_score['full_pair_hit_count']} 期")
    print("每期命中球數統計")
    print("4 = 0 期")
    print("3 = 0 期")
    print(f"2 = {window_score['hit_2_count']} 期")
    print(f"1.5 = {window_score['hit_1_5_count']} 期")
    print(f"1 = {window_score['hit_1_count']} 期")
    print(f"0 = {window_score['hit_0_count']} 期")
    print(f"命中 (00) = {window_score['none_hit_count']} 期")
    print(f"窗口期模型分數 = {window_score['score']:g}")
    print()


def write_e4_comb_csv(rows: list[TrackRow]) -> None:
    COMB_DATA_DIR.mkdir(parents=True, exist_ok=True)
    with E4_COMB_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["index", "type", "item_1_9", "backtest_hit_periods", "hit_count"],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "index": row["index"],
                    "type": row["row_type"],
                    "item_1_9": row["item"],
                    "backtest_hit_periods": format_nums(row["periods"]),
                    "hit_count": row["hit_count"],
                }
            )


def write_json(results: list[dict[str, object]], window_scores: list[WindowScore]) -> None:
    best_window = window_scores[0] if window_scores else None
    JSON_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": "E4_v2_backtest_pred",
        "params": {
            "backtest_draw_count": BACKTEST_DRAW_COUNT,
            "window_draw_count_list": WINDOW_DRAW_COUNT_LIST,
            "combination_take_count": COMBINATION_TAKE_COUNT,
            "birthday_num_min": BIRTHDAY_NUM_MIN,
            "birthday_num_max": BIRTHDAY_NUM_MAX,
            "birthday_num_match_mode": BIRTHDAY_NUM_MATCH_MODE,
            "prize_option": PRIZE_OPTION,
            "predict_pair_count": PREDICT_PAIR_COUNT,
            "pair_select_mode": PAIR_SELECT_MODE,
        },
        "score_params": {
            "full_pair_hit_score": FULL_PAIR_HIT_SCORE,
            "hit_2_score": HIT_2_SCORE,
            "hit_1_5_score": HIT_1_5_SCORE,
            "hit_1_score": HIT_1_SCORE,
            "hit_0_penalty": HIT_0_PENALTY,
            "none_hit_score": NONE_HIT_SCORE,
        },
        "best_window": best_window,
        "window_scores": window_scores,
        "results": results,
    }
    with E4_JSON.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def print_settings(draw_count: int) -> None:
    print("====== E4_v2 1-9 追蹤模型回測核對 ======")
    print(f"資料期數：{draw_count}")
    print(f"BACKTEST_DRAW_COUNT = {BACKTEST_DRAW_COUNT}")
    print(f"WINDOW_DRAW_COUNT_LIST = {WINDOW_DRAW_COUNT_LIST}")
    print(f"PAIR_SELECT_MODE = {PAIR_SELECT_MODE}")
    print(
        f"查詢參數：{BIRTHDAY_NUM_MIN}-{BIRTHDAY_NUM_MAX}，"
        f"N1-N6 {BIRTHDAY_NUM_MATCH_MODE} {COMBINATION_TAKE_COUNT} 球，"
        f"PZ{PRIZE_OPTION}"
    )
    print("回測定義：每一期都是獨立核對期；窗口期不包括該核對期。")
    print("核對口徑：N1-N6 命中每球 = 1；N7 特號命中 = 0.5。")
    print()


def run_backtest(draws: list[DrawRow]) -> None:
    last_check_index = len(draws) - 1
    first_check_index = max(0, last_check_index - BACKTEST_DRAW_COUNT + 1)
    check_indices = list(range(first_check_index, last_check_index + 1))
    json_results: list[dict[str, object]] = []
    window_scores: list[WindowScore] = []

    print_settings(len(draws))
    for window_count in WINDOW_DRAW_COUNT_LIST:
        hit_scores: list[float] = []
        full_pair_hit_count = 0
        none_hit_count = 0
        print(f"====== 窗口期 {window_count} 期 回測核對 ======")
        for idx, check_index in enumerate(check_indices, start=1):
            check_row = draws[check_index]
            window_rows = draws[max(0, check_index - window_count):check_index]
            track_rows = build_track_rows(window_rows)
            pair_scores = build_pair_scores(track_rows)
            predictions, should_skip = select_prediction(pair_scores, track_rows)
            write_e4_comb_csv(track_rows)

            if should_skip:
                print(f"{idx}，回測核對：{check_row['date']}，{format_check_nums(check_row)}，預測(00)=None")
                hit_score = 0.0
                normal_hits: list[int] = []
                special_hits: list[int] = []
                pred_pairs: list[str] = []
                if not group_nums(check_row):
                    none_hit_count += 1
            else:
                normal_hits, special_hits, hit_score = calc_pair_hit(predictions, check_row)
                if count_full_hit_pairs(predictions, check_row) > 0:
                    full_pair_hit_count += 1
                special_text = f" + 特號{format_nums(special_hits)}" if special_hits else ""
                pred_pairs = [f"({item['pair'][0]},{item['pair'][1]})" for item in predictions]
                print(
                    f"{idx}，回測核對：{check_row['date']}，{format_check_nums(check_row)}，"
                    f"預測{'，'.join(pred_pairs)}，"
                    f"命中{format_nums(normal_hits)}{special_text} /> {hit_score:g} 球"
                )
            hit_scores.append(hit_score)

            json_results.append(
                {
                    "window_count": window_count,
                    "check_no": idx,
                    "check_date": check_row["date"],
                    "check_nums": format_check_nums(check_row),
                    "prediction": "(00)=None" if should_skip else pred_pairs,
                    "normal_hits": normal_hits,
                    "special_hits": special_hits,
                    "hit_score": hit_score,
                    "top_pair_scores": [
                        {
                            "index": item["index"],
                            "pair": item["pair"],
                            "hit_count": item["hit_count"],
                            "periods": item["periods"],
                            "score": round(item["score"], 2),
                        }
                        for item in pair_scores[:10]
                    ],
                }
            )
        window_score = build_window_score(window_count, hit_scores, full_pair_hit_count, none_hit_count)
        window_scores.append(window_score)
        print_window_summary(window_score)

    window_scores.sort(
        key=lambda item: (
            -item["score"],
            -item["full_pair_hit_count"],
            -item["hit_2_count"],
            item["hit_0_count"],
            item["window_count"],
        )
    )

    print("====== 窗口期最佳優化參數提示 ======")
    print("排名 | 窗口期 | 雙球全中 | 2球 | 1.5球 | 1球 | 0球 | (00) | 分數")
    for rank, item in enumerate(window_scores, start=1):
        print(
            f"{rank:>2} | {item['window_count']:>4} | {item['full_pair_hit_count']:>4} | "
            f"{item['hit_2_count']:>2} | {item['hit_1_5_count']:>4} | "
            f"{item['hit_1_count']:>2} | {item['hit_0_count']:>2} | "
            f"{item['none_hit_count']:>4} | {item['score']:>5g}"
        )
    if window_scores:
        best = window_scores[0]
        print(
            f"最佳優化下期預測參數：窗口期 {best['window_count']}，"
            f"分數 {best['score']:g}，雙球全中 {best['full_pair_hit_count']} 期，"
            f"2球 {best['hit_2_count']} 期，0球 {best['hit_0_count']} 期。"
        )
    print()

    write_json(json_results, window_scores)
    print(f"E4 追蹤 CSV 已建立：{E4_COMB_CSV}")
    print(f"E4_v2 JSON 已建立：{E4_JSON}")


def main() -> None:
    draws = read_draws()
    if not draws:
        raise RuntimeError("M6 沒有可用開獎資料。")
    run_backtest(draws)


if __name__ == "__main__":
    main()
