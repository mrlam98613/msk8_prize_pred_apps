from pathlib import Path
import csv
import itertools
import json
import sys
from collections import Counter
from typing import TypedDict


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from msk_marksix_function_app.res_func_num_convert_RBG_Dict import res_List_To_rbg_Dict_func

M6_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"
M3_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M3_lotto_prize_results.csv"
JSON_DIR = CURRENT_DIR / "json_data"
BET_DATA_DIR = CURRENT_DIR / "bet_data"
BEST_PARAMS_JSON = JSON_DIR / "C2_v4_best_params.json"
BET_RECORDS_CSV = BET_DATA_DIR / "bet_records.csv"
WIN_RESULTS_CSV = BET_DATA_DIR / "win_results.csv"
NEXTDRAW_CSV = BET_DATA_DIR / "nextdraw_pred.csv"

# C2_v5 只需要修改以下 2 個參數。
RUN_MODE = "backtest"  # 可選："backtest" 或 "predict"
BACKTEST_DETAIL_COUNT = 30

# 以下是 C2_v4 演算法固定設定，C2_v5 由 JSON 讀入最佳窗口期 / topN / 權重，不在此處手動調參。
PRIZE_OPTION = 3
MATCH_COUNT = 2
MATCH_MODE = ">="
GROUPS = {
    1: ("1-9", 1, 9),
    2: ("10-20", 10, 20),
    3: ("21-31", 21, 31),
}
PAIR_DETAIL_MIN_HIT_COUNT = 1
PAIR_SUMMARY_MIN_HIT_COUNT = 2
PAIR_SORT_MODE = "index"
GROUP_PREDICT_COUNT = 3
PRIZE_RANK_SCORE_LIST = [7, 6, 5, 4, 3, 2, 1]
DEFAULT_DATE_RECENT_SCORE_LIST = [7, 6, 5, 4, 3, 2, 1]
HIT_SCORE_LIST = [6.0, 5.5, 5.0, 4.5, 4.0, 3.5, 3.0, 2.5, 2.0, 1.5, 1.0, 0.5, 0.0]
PRIZE_LABELS = {
    6.0: "一獎",
    5.5: "二獎",
    5.0: "三獎",
    4.5: "四獎",
    4.0: "五獎",
    3.5: "六獎",
    3.0: "七獎",
}

# 以下是程式內部使用中的參數，由 C2_v4 JSON 最佳組合自動套入。
ACTIVE_PAIR_CORE_SCORE = 10
ACTIVE_SINGLE_HIT_SCORE = 1
ACTIVE_DATE_RECENT_SCORE_LIST = DEFAULT_DATE_RECENT_SCORE_LIST

# 舊 C2_v4 工具函數保留但不由 C2_v5 main 使用；以下只是避免舊函數出現未定義。
_LEGACY_BACKTEST_DRAW_COUNT_LIST = [24]
_LEGACY_WINDOW_DRAW_COUNT_LIST = [28]
_LEGACY_TOP_PRIZE_DRAW_COUNT_LIST = [7]
_LEGACY_PAIR_CORE_SCORE_LIST = [15]
_LEGACY_SINGLE_HIT_SCORE_LIST = [1]
_LEGACY_DATE_RECENT_SCORE_PROFILE_LIST = [DEFAULT_DATE_RECENT_SCORE_LIST]
_LEGACY_HIT_SCORE_WEIGHT = {
    6.0: 80,
    5.5: 60,
    5.0: 45,
    4.5: 25,
    4.0: 20,
    3.5: 10,
    3.0: 8,
    2.5: 3,
    2.0: 2,
    1.5: 1,
    1.0: 0,
    0.5: 0,
    0.0: -3,
}
_LEGACY_SHOW_TOP_RANK_COUNT = 10
_LEGACY_PRINT_ALL_RANK_ROWS = False





class DrawRow(TypedDict):
    date: str
    nums: list[int]
    special: int | None
    prize_count: float


class PairSource(TypedDict):
    date: str
    prize_count: float
    prize_score: int
    date_score: int


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames:
            reader.fieldnames = [name.strip().lstrip("\ufeff") for name in reader.fieldnames]
        return [
            {(key or "").strip().lstrip("\ufeff"): (value or "").strip() for key, value in row.items()}
            for row in reader
        ]


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


def to_int_list(value: object) -> list[int]:
    if not isinstance(value, list):
        return []
    return [to_int(item, 1) for item in value]


def parse_m6_row(row: dict[str, str]) -> DrawRow:
    nums = [to_int(row.get(f"N{idx}")) for idx in range(1, 7)]
    special = to_int(row.get("N7"))
    return {
        "date": row.get("nDdate", ""),
        "nums": nums,
        "special": special if 1 <= special <= 49 else None,
        "prize_count": to_float(row.get(f"prize{PRIZE_OPTION}")),
    }


def read_draws() -> list[DrawRow]:
    rows = [parse_m6_row(row) for row in read_csv_rows(M6_CSV)]
    return [row for row in rows if row["date"]]


def read_next_draw_date() -> str:
    if not M3_CSV.exists():
        return "未設定"
    with M3_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 2 or row[0].strip() != "開獎日期":
                continue
            date_text = row[1].strip().split()[0]
            return (
                date_text
                .replace("年", "-")
                .replace("月", "-")
                .replace("日", "")
            )
    return "未設定"


def read_best_params() -> dict[str, object]:
    if not BEST_PARAMS_JSON.exists():
        raise FileNotFoundError(f"找不到 C2_v4 最佳參數 JSON：{BEST_PARAMS_JSON}")
    data = json.loads(BEST_PARAMS_JSON.read_text(encoding="utf-8"))
    best = data.get("best_params", {})
    if not isinstance(best, dict):
        raise ValueError("C2_v4_best_params.json 內沒有 best_params")
    return best


def selected_nums(nums: list[int], group_id: int) -> list[int]:
    _name, start_num, end_num = GROUPS[group_id]
    return sorted(num for num in nums if start_num <= num <= end_num)


def selected_birthday_nums(nums: list[int], special: int | None) -> list[int]:
    birthday_nums = [num for num in nums if 1 <= num <= 31]
    if special is not None and 1 <= special <= 31:
        birthday_nums.append(special)
    return sorted(birthday_nums)


def calc_hit_score(pred_nums: list[int], check_row: DrawRow) -> float:
    normal_hits = len(set(pred_nums) & set(num for num in check_row["nums"] if 1 <= num <= 31))
    special_hit = 0.5 if check_row["special"] in set(pred_nums) else 0.0
    return normal_hits + special_hit


def is_matched(count: int) -> bool:
    if MATCH_MODE == "==":
        return count == MATCH_COUNT
    return count >= MATCH_COUNT


def format_nums(nums: list[int]) -> str:
    return "[" + ",".join(str(num) for num in nums) + "]"


def format_rbg_lines(nums: list[int]) -> list[str]:
    rbg_dict = res_List_To_rbg_Dict_func(sorted(nums))
    return [
        f"R：{format_nums(sorted(rbg_dict.get(0, [])))} /> {len(rbg_dict.get(0, []))} 球",
        f"B：{format_nums(sorted(rbg_dict.get(1, [])))} /> {len(rbg_dict.get(1, []))} 球",
        f"G：{format_nums(sorted(rbg_dict.get(2, [])))} /> {len(rbg_dict.get(2, []))} 球",
    ]


def format_draw_nums(row: DrawRow) -> str:
    special_text = str(row["special"]) if row["special"] is not None else "-"
    return f"{format_nums(row['nums'])} {special_text}"


def format_birthday_slots(row: DrawRow) -> tuple[str, int]:
    slots: list[str] = []
    birthday_count = 0
    for num in row["nums"]:
        if 1 <= num <= 31:
            slots.append(str(num))
            birthday_count += 1
        else:
            slots.append("_")

    special = row["special"]
    if special is not None and 1 <= special <= 31:
        slots.append(str(special))
        birthday_count += 1
    else:
        slots.append("_")

    return "[" + ",".join(slots) + "]", birthday_count


def format_check_draw(row: DrawRow) -> str:
    slots: list[str] = []
    for num in row["nums"]:
        slots.append(str(num) if 1 <= num <= 31 else "-")
    special = row["special"]
    slots.append(str(special) if special is not None and 1 <= special <= 31 else "-")
    return f"[{row['date']}: {','.join(slots)}]"


def split_hit_nums(pred_nums: list[int], check_row: DrawRow) -> tuple[list[int], list[int], float]:
    pred_set = set(pred_nums)
    normal_hits = sorted(pred_set & set(num for num in check_row["nums"] if 1 <= num <= 31))
    special_hits = [check_row["special"]] if check_row["special"] in pred_set else []
    hit_score = len(normal_hits) + (0.5 if special_hits else 0.0)
    return normal_hits, special_hits, hit_score


def format_hit_text(normal_hits: list[int], special_hits: list[int]) -> str:
    normal_text = format_nums(normal_hits) if normal_hits else "[-]"
    if special_hits:
        return f"命中{normal_text} + 特號{format_nums(special_hits)}"
    return f"命中{normal_text}"


def prize_label(hit_score: float) -> str:
    return PRIZE_LABELS.get(hit_score, "未中獎")


def build_window_rows(draws: list[DrawRow], target_index: int, window_count: int) -> list[DrawRow]:
    return draws[max(0, target_index - window_count):target_index]


def build_group_samples(window_rows: list[DrawRow], group_id: int, top_prize_count: int) -> list[DrawRow]:
    matched_rows: list[DrawRow] = []
    for row in window_rows:
        if is_matched(len(selected_nums(row["nums"], group_id))):
            matched_rows.append(row)
    return sorted(matched_rows, key=lambda item: (-item["prize_count"], item["date"]))[:top_prize_count]


def count_group_matched_rows(window_rows: list[DrawRow], group_id: int) -> int:
    return sum(1 for row in window_rows if is_matched(len(selected_nums(row["nums"], group_id))))


def print_step_1_setting() -> None:
    print("====== C2_v3 第一步：回測窗口及 prize3 取樣驗證 ======")
    print(f"回測期列表：{_LEGACY_BACKTEST_DRAW_COUNT_LIST}")
    print(f"窗口期列表：{_LEGACY_WINDOW_DRAW_COUNT_LIST}")
    print(f"3獎注數前N期列表：{_LEGACY_TOP_PRIZE_DRAW_COUNT_LIST}")
    print("參數檢查：窗口期必須 >= 3獎中獎注數前N期，否則分析資料不足。")
    print(f"取樣條件：每組生日號 {MATCH_MODE}{MATCH_COUNT} 球，按 prize{PRIZE_OPTION} 中獎注數排序")
    print("分組：1-9 / 10-20 / 21-31")
    print()


def validate_window_top_prize_count(window_count: int, top_prize_count: int) -> bool:
    if window_count >= top_prize_count:
        return True
    print(
        f"資料不足：窗口期 {window_count} 少於 "
        f"3獎中獎注數前 {top_prize_count} 期，略過此組參數。"
    )
    print()
    return False


def print_window_rows(window_rows: list[DrawRow]) -> None:
    print(f"====== 窗口期資料：{len(window_rows)} 期  1-31 N1..N7，3 獎注數 ======")
    for idx, row in enumerate(window_rows, start=1):
        birthday_slots, birthday_count = format_birthday_slots(row)
        print(
            f"{idx:>2}，{row['date']}，{birthday_slots} "
            f"/> {birthday_count} 球，{row['prize_count']:g}"
        )
    print()


def print_group_samples(window_rows: list[DrawRow], top_prize_count: int) -> None:
    print(f"====== prize{PRIZE_OPTION} 前 {top_prize_count} 期取樣資料 ======")
    group_status_rows: list[tuple[int, str, int, bool]] = []
    for group_id, (group_label, _start_num, _end_num) in GROUPS.items():
        matched_count = count_group_matched_rows(window_rows, group_id)
        is_enough = matched_count >= top_prize_count
        group_status_rows.append((group_id, group_label, matched_count, is_enough))

    if not all(is_enough for _group_id, _group_label, _matched_count, is_enough in group_status_rows):
        print("/==========================")
        print("1-9")
        print("10-20")
        print("21-31")
        for group_id, group_label, matched_count, is_enough in group_status_rows:
            status = "pass" if is_enough else "資料不足"
            print(f"[{group_id}] {group_label}：符合條件 {matched_count}/{top_prize_count} 期，{status}")
        print()
        print("資料不足提示：1，2，3 分組未能全部合理採樣。")
        print(f"建議 1：加大窗口期，目前窗口期 {len(window_rows)}，可改大至下一組窗口期。")
        print(f"建議 2：降低 3獎中獎注數前N期，目前 top={top_prize_count}。")
        print(f"建議 3：降低取樣條件，目前每組生日號 {MATCH_MODE}{MATCH_COUNT} 球。")
        print("三組全部 pass 後，才顯示集合球號及出現次數。")
        print()
        return

    print()
    for group_id, group_label, _matched_count, _is_enough in group_status_rows:
        sample_rows = build_group_samples(window_rows, group_id, top_prize_count)
        print(f"[{group_id}] {group_label} 取樣明細：")
        for idx, row in enumerate(sample_rows, start=1):
            group_nums = selected_nums(row["nums"], group_id)
            print(
                f"   {idx}，{row['date']}，{group_label}:{format_nums(group_nums)} "
                f"/> {len(group_nums)} 球，pz{PRIZE_OPTION}:{row['prize_count']:g}"
            )
    print("/==========================")
    print("1-9")
    print("10-20")
    print("21-31")
    for group_id, group_label, matched_count, is_enough in group_status_rows:
        status = "pass" if is_enough else "資料不足"
        print(f"[{group_id}] {group_label}：符合條件 {matched_count}/{top_prize_count} 期，{status}")
    print()


def build_pair_index(group_id: int) -> dict[tuple[int, int], int]:
    _group_label, start_num, end_num = GROUPS[group_id]
    pairs = itertools.combinations(range(start_num, end_num + 1), 2)
    return {pair: idx for idx, pair in enumerate(pairs, start=1)}


def build_sample_pair_counts(sample_rows: list[DrawRow], group_id: int) -> Counter[tuple[int, int]]:
    counter: Counter[tuple[int, int]] = Counter()
    for row in sample_rows:
        nums = selected_nums(row["nums"], group_id)
        counter.update(itertools.combinations(sorted(set(nums)), 2))
    return counter


def format_pair_label(idx: int, pair: tuple[int, int]) -> str:
    return f"{idx}組（{pair[0]}-{pair[1]})"


def build_pair_group_summary(
    group_id: int,
    group_label: str,
    total_pair_count: int,
    pair_rows: list[tuple[tuple[int, int], int, int]],
) -> dict[str, object]:
    appeared_rows = [(pair, idx, count) for pair, idx, count in pair_rows if count > 0]
    shown_rows = [(pair, idx, count) for pair, idx, count in pair_rows if count >= PAIR_SUMMARY_MIN_HIT_COUNT]
    if not shown_rows:
        return {
            "group_id": group_id,
            "group_label": group_label,
            "total_pair_count": total_pair_count,
            "appeared_count": len(appeared_rows),
            "summary_count": 0,
            "top_indexes": "",
            "related_text": "-",
        }

    max_count = max(count for _pair, _idx, count in shown_rows)
    top_rows = [(pair, idx, count) for pair, idx, count in shown_rows if count == max_count]
    top_indexes = "，".join(f"{idx}組" for _pair, idx, _count in top_rows)

    related_rows: list[tuple[tuple[int, int], int, int]] = []
    for top_pair, _top_idx, _top_count in top_rows:
        if top_pair[1] - top_pair[0] > 2:
            continue
        related_nums = set(range(top_pair[0], top_pair[1] + 1))
        for pair, idx, count in shown_rows:
            if pair[0] in related_nums and pair[1] in related_nums and (pair, idx, count) not in related_rows:
                related_rows.append((pair, idx, count))
    related_text = "，".join(format_pair_label(idx, pair) for pair, idx, _count in related_rows)
    return {
        "group_id": group_id,
        "group_label": group_label,
        "total_pair_count": total_pair_count,
        "appeared_count": len(appeared_rows),
        "summary_count": len(shown_rows),
        "top_indexes": top_indexes,
        "related_text": related_text or "-",
    }


def print_pair_index_counts(window_rows: list[DrawRow], top_prize_count: int) -> None:
    print(f"====== 第二步：2 球組合索引分布，prize{PRIZE_OPTION} 前 {top_prize_count} 期 ======")
    print(
        f"第二步參數：PAIR_DETAIL_MIN_HIT_COUNT={PAIR_DETAIL_MIN_HIT_COUNT}，"
        f"PAIR_SUMMARY_MIN_HIT_COUNT={PAIR_SUMMARY_MIN_HIT_COUNT}，"
        f"PAIR_SORT_MODE={PAIR_SORT_MODE}"
    )
    summaries: list[dict[str, object]] = []
    for group_id, (group_label, start_num, end_num) in GROUPS.items():
        pair_index = build_pair_index(group_id)
        pair_counts = build_sample_pair_counts(build_group_samples(window_rows, group_id, top_prize_count), group_id)
        print(f"[{group_id}] {group_label}，2 球組合 = {len(pair_index)} 組")
        printed_count = 0
        pair_rows = [(pair, idx, pair_counts.get(pair, 0)) for pair, idx in pair_index.items()]
        if PAIR_SORT_MODE == "hit":
            pair_rows = sorted(pair_rows, key=lambda item: (-item[2], item[1]))
        for pair, idx, count in pair_rows:
            if count < PAIR_DETAIL_MIN_HIT_COUNT:
                continue
            print(f"   {idx}，({pair[0]}-{pair[1]}) 出現 {count} 次")
            printed_count += 1
        if printed_count == 0:
            print("   沒有出現 2 球組合")
        summaries.append(build_pair_group_summary(group_id, group_label, len(pair_index), pair_rows))
    print()
    print("====== 第二步：1，2，3 分組分析結果總結 ======")
    for item in summaries:
        print(
            f"[{item['group_id']}] {item['group_label']}，"
            f"2 球組合 = {item['total_pair_count']} 組，"
            f"採樣出現組合 {item['appeared_count']} 組"
        )
    print()
    for item in summaries:
        if to_int(item["summary_count"]) <= 0:
            print(f"[{item['group_label']}]: 總共有 0 組")
            continue
        print(
            f"[{item['group_label']}]: 總共有 {item['summary_count']} 組，"
            f">= {PAIR_SUMMARY_MIN_HIT_COUNT} 次 {item['top_indexes']}，"
            f"關連組合，{item['related_text']}"
        )
    print()


def build_sample_score_maps(sample_rows: list[DrawRow]) -> tuple[dict[str, int], dict[str, int]]:
    prize_score_map: dict[str, int] = {}
    for row_idx, row in enumerate(sample_rows):
        prize_score_map[row["date"]] = (
            PRIZE_RANK_SCORE_LIST[row_idx]
            if row_idx < len(PRIZE_RANK_SCORE_LIST)
            else 1
        )

    date_score_map: dict[str, int] = {}
    date_ranked_rows = sorted(sample_rows, key=lambda item: item["date"], reverse=True)
    for row_idx, row in enumerate(date_ranked_rows):
        date_score_map[row["date"]] = (
            ACTIVE_DATE_RECENT_SCORE_LIST[row_idx]
            if row_idx < len(ACTIVE_DATE_RECENT_SCORE_LIST)
            else 1
        )
    return prize_score_map, date_score_map


def build_pair_sources(
    sample_rows: list[DrawRow],
    group_id: int,
) -> dict[tuple[int, int], list[PairSource]]:
    prize_score_map, date_score_map = build_sample_score_maps(sample_rows)
    sources: dict[tuple[int, int], list[PairSource]] = {}
    for row in sample_rows:
        row_pairs = itertools.combinations(sorted(set(selected_nums(row["nums"], group_id))), 2)
        for pair in row_pairs:
            sources.setdefault(pair, []).append(
                {
                    "date": row["date"],
                    "prize_count": row["prize_count"],
                    "prize_score": prize_score_map.get(row["date"], 1),
                    "date_score": date_score_map.get(row["date"], 1),
                }
            )
    return sources


def build_single_num_scores(sample_rows: list[DrawRow], group_id: int) -> dict[int, float]:
    prize_score_map, date_score_map = build_sample_score_maps(sample_rows)
    scores: dict[int, float] = {}
    for row in sample_rows:
        prize_score = prize_score_map.get(row["date"], 1)
        date_score = date_score_map.get(row["date"], 1)
        for num in selected_nums(row["nums"], group_id):
            scores[num] = scores.get(num, 0.0) + ACTIVE_SINGLE_HIT_SCORE + prize_score + date_score
    return scores


def format_num_scores(scores: dict[int, float]) -> str:
    if not scores:
        return "-"
    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return "，".join(f"{num}({score:g})" for num, score in ranked)


def build_pair_based_prediction(
    sample_rows: list[DrawRow],
    group_id: int,
) -> tuple[list[tuple[tuple[int, int], int, int, float, list[PairSource]]], list[int], list[int], list[int], dict[int, float]]:
    pair_index = build_pair_index(group_id)
    pair_counts = build_sample_pair_counts(sample_rows, group_id)
    pair_sources = build_pair_sources(sample_rows, group_id)
    pair_rows = [(pair, idx, pair_counts.get(pair, 0)) for pair, idx in pair_index.items()]
    repeat_pairs: list[tuple[tuple[int, int], int, int, float, list[PairSource]]] = [
        (
            pair,
            idx,
            count,
            count * ACTIVE_PAIR_CORE_SCORE
            + sum(source["prize_score"] for source in pair_sources.get(pair, []))
            + sum(source["date_score"] for source in pair_sources.get(pair, [])),
            pair_sources.get(pair, []),
        )
        for pair, idx, count in pair_rows
        if count >= PAIR_SUMMARY_MIN_HIT_COUNT
    ]
    repeat_pairs = sorted(repeat_pairs, key=lambda item: (-item[3], item[1]))
    single_scores = build_single_num_scores(sample_rows, group_id)
    final_scores = dict(single_scores)
    for pair, _idx, _count, pair_score, _sources in repeat_pairs:
        for num in pair:
            final_scores[num] = final_scores.get(num, 0.0) + pair_score / 2

    pair_pool = sorted({num for pair, _idx, _count, _score, _sources in repeat_pairs for num in pair})
    ranked_nums = [num for num, _score in sorted(final_scores.items(), key=lambda item: (-item[1], item[0]))]
    prediction: list[int] = []
    for num in ranked_nums:
        if num in pair_pool and num not in prediction:
            prediction.append(num)
        if len(prediction) >= GROUP_PREDICT_COUNT:
            return repeat_pairs, pair_pool, [], sorted(prediction), final_scores

    fill_nums: list[int] = []
    for num in ranked_nums:
        if num not in prediction:
            prediction.append(num)
            fill_nums.append(num)
        if len(prediction) >= GROUP_PREDICT_COUNT:
            break

    return repeat_pairs, pair_pool, fill_nums, sorted(prediction), final_scores


def build_predictions_for_window(
    window_rows: list[DrawRow],
    top_prize_count: int,
) -> dict[str, list[int]]:
    group_predictions: dict[str, list[int]] = {}
    for group_id, (group_label, _start_num, _end_num) in GROUPS.items():
        sample_rows = build_group_samples(window_rows, group_id, top_prize_count)
        _repeat_pairs, _pair_pool, _fill_nums, prediction, _final_scores = build_pair_based_prediction(
            sample_rows,
            group_id,
        )
        group_predictions[group_label] = prediction
    return group_predictions


def flatten_predictions(group_predictions: dict[str, list[int]]) -> list[int]:
    return sorted({num for nums in group_predictions.values() for num in nums})


def set_predict_params(pair_core_score: int, single_hit_score: int, date_score_list: list[int]) -> None:
    global ACTIVE_PAIR_CORE_SCORE, ACTIVE_SINGLE_HIT_SCORE, ACTIVE_DATE_RECENT_SCORE_LIST
    ACTIVE_PAIR_CORE_SCORE = pair_core_score
    ACTIVE_SINGLE_HIT_SCORE = single_hit_score
    ACTIVE_DATE_RECENT_SCORE_LIST = date_score_list


def is_group_sample_enough(window_rows: list[DrawRow], top_prize_count: int) -> bool:
    return all(
        count_group_matched_rows(window_rows, group_id) >= top_prize_count
        for group_id in GROUPS
    )


def evaluate_param_set(
    draws: list[DrawRow],
    backtest_count: int,
    window_count: int,
    top_prize_count: int,
    pair_core_score: int,
    single_hit_score: int,
    date_score_list: list[int],
) -> dict[str, object]:
    set_predict_params(pair_core_score, single_hit_score, date_score_list)
    last_check_index = len(draws) - 1
    first_check_index = max(0, last_check_index - backtest_count + 1)
    check_indices = list(range(first_check_index, last_check_index + 1))
    check_rows: list[dict[str, object]] = []
    score = 0.0
    hit_5_plus = 0
    hit_4_plus = 0
    hit_3_plus = 0
    zero_hit = 0

    for check_index in check_indices:
        window_rows = build_window_rows(draws, check_index, window_count)
        check_row = draws[check_index]
        if len(window_rows) < window_count or not is_group_sample_enough(window_rows, top_prize_count):
            continue
        group_predictions = build_predictions_for_window(window_rows, top_prize_count)
        pred_nums = flatten_predictions(group_predictions)
        hit_score = calc_hit_score(pred_nums, check_row)
        hit_nums = sorted(set(pred_nums) & set(selected_birthday_nums(check_row["nums"], check_row["special"])))
        score += _LEGACY_HIT_SCORE_WEIGHT.get(hit_score, 0)
        if hit_score >= 5:
            hit_5_plus += 1
        if hit_score >= 4:
            hit_4_plus += 1
        if hit_score >= 3:
            hit_3_plus += 1
        if hit_score == 0:
            zero_hit += 1
        check_rows.append(
            {
                "date": check_row["date"],
                "pred_groups": group_predictions,
                "candidate_pool": pred_nums,
                "hit_nums": hit_nums,
                "hit_score": hit_score,
            }
        )

    return {
        "backtest_count": backtest_count,
        "window_count": window_count,
        "top_prize_count": top_prize_count,
        "pair_core_score": pair_core_score,
        "single_hit_score": single_hit_score,
        "date_score_list": date_score_list,
        "checked_count": len(check_rows),
        "hit_5_plus": hit_5_plus,
        "hit_4_plus": hit_4_plus,
        "hit_3_plus": hit_3_plus,
        "zero_hit": zero_hit,
        "score": score,
        "check_rows": check_rows,
    }


def run_param_backtests(draws: list[DrawRow]) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for backtest_count in _LEGACY_BACKTEST_DRAW_COUNT_LIST:
        for window_count in _LEGACY_WINDOW_DRAW_COUNT_LIST:
            for top_prize_count in _LEGACY_TOP_PRIZE_DRAW_COUNT_LIST:
                if window_count < top_prize_count:
                    continue
                for pair_core_score in _LEGACY_PAIR_CORE_SCORE_LIST:
                    for single_hit_score in _LEGACY_SINGLE_HIT_SCORE_LIST:
                        for date_score_list in _LEGACY_DATE_RECENT_SCORE_PROFILE_LIST:
                            results.append(
                                evaluate_param_set(
                                    draws,
                                    backtest_count,
                                    window_count,
                                    top_prize_count,
                                    pair_core_score,
                                    single_hit_score,
                                    date_score_list,
                                )
                            )
    return sorted(
        results,
        key=lambda item: (
            -to_float(item["score"]),
            -to_int(item["hit_5_plus"]),
            -to_int(item["hit_4_plus"]),
            -to_int(item["hit_3_plus"]),
            to_int(item["zero_hit"]),
            to_int(item["window_count"]),
        ),
    )


def write_best_json(results: list[dict[str, object]]) -> None:
    JSON_DIR.mkdir(parents=True, exist_ok=True)
    best = results[0] if results else {}
    payload = {
        "best_params": {
            key: best.get(key)
            for key in [
                "backtest_count",
                "window_count",
                "top_prize_count",
                "pair_core_score",
                "single_hit_score",
                "date_score_list",
                "checked_count",
                "hit_5_plus",
                "hit_4_plus",
                "hit_3_plus",
                "zero_hit",
                "score",
            ]
        },
        "rank_rows": [
            {
                key: result.get(key)
                for key in [
                    "backtest_count",
                    "window_count",
                    "top_prize_count",
                    "pair_core_score",
                    "single_hit_score",
                    "date_score_list",
                    "checked_count",
                    "hit_5_plus",
                    "hit_4_plus",
                    "hit_3_plus",
                    "zero_hit",
                    "score",
                ]
            }
            for result in results[:_LEGACY_SHOW_TOP_RANK_COUNT]
        ],
    }
    BEST_PARAMS_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def print_param_backtest_summary(results: list[dict[str, object]]) -> None:
    print("====== C2_v4 多參數回測比較，寫入 JSON ======")
    print(f"總參數組合：{len(results)} 組")
    rank_rows: list[dict[str, object]] = []
    display_results = results if _LEGACY_PRINT_ALL_RANK_ROWS else results[:_LEGACY_SHOW_TOP_RANK_COUNT]
    for idx, item in enumerate(display_results, start=1):
        date_score_text = ",".join(str(value) for value in to_int_list(item.get("date_score_list")))
        rank_rows.append(
            {
                "排名": idx,
                "回測期": to_int(item["backtest_count"]),
                "窗口期": to_int(item["window_count"]),
                "prize前N": to_int(item["top_prize_count"]),
                "pair分": to_int(item["pair_core_score"]),
                "單球分": to_int(item["single_hit_score"]),
                "日期分": date_score_text,
                "5球+": to_int(item["hit_5_plus"]),
                "4球+": to_int(item["hit_4_plus"]),
                "3球+": to_int(item["hit_3_plus"]),
                "0球": to_int(item["zero_hit"]),
                "分數": to_float(item["score"]),
            }
        )
    print_table(rank_rows)
    if results:
        best = results[0]
        print()
        print(
            "最佳組合："
            f"回測期 {best['backtest_count']}，窗口期 {best['window_count']}，"
            f"prize前N {best['top_prize_count']}，pair分 {best['pair_core_score']}，"
            f"單球分 {best['single_hit_score']}，3球以上 {best['hit_3_plus']} 期，"
            f"4球以上 {best['hit_4_plus']} 期，5球以上 {best['hit_5_plus']} 期，"
            f"分數 {best['score']:g}"
        )
    print(f"JSON 已寫入：{BEST_PARAMS_JSON}")
    print()


def print_table(rows: list[dict[str, object]]) -> None:
    if not rows:
        print("沒有資料")
        return
    headers = list(rows[0].keys())
    widths: dict[str, int] = {}
    for header in headers:
        widths[header] = max(len(str(header)), *(len(str(row.get(header, ""))) for row in rows))
    header_line = "  ".join(str(header).ljust(widths[header]) for header in headers)
    sep_line = "  ".join("-" * widths[header] for header in headers)
    print(header_line)
    print(sep_line)
    for row in rows:
        print("  ".join(str(row.get(header, "")).rjust(widths[header]) for header in headers))


def save_nextdraw_csv(next_date: str, group_predictions: dict[str, list[int]]) -> None:
    BET_DATA_DIR.mkdir(parents=True, exist_ok=True)
    with NEXTDRAW_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "group_1_9", "group_10_20", "group_21_31", "candidate_pool"])
        writer.writerow(
            [
                next_date,
                format_nums(group_predictions.get("1-9", [])),
                format_nums(group_predictions.get("10-20", [])),
                format_nums(group_predictions.get("21-31", [])),
                format_nums(flatten_predictions(group_predictions)),
            ]
        )


def format_group_prediction_text(group_predictions: dict[str, list[int]]) -> str:
    return (
        f"{format_nums(group_predictions.get('1-9', []))},"
        f"{format_nums(group_predictions.get('10-20', []))},"
        f"{format_nums(group_predictions.get('21-31', []))}"
    )


def print_backtest_last_check(draws: list[DrawRow], window_count: int, top_prize_count: int) -> None:
    if len(draws) < window_count + 1:
        return
    check_index = len(draws) - 1
    check_row = draws[-1]
    window_rows = build_window_rows(draws, check_index, window_count)
    group_predictions = build_predictions_for_window(window_rows, top_prize_count)
    candidate_pool = flatten_predictions(group_predictions)
    hit_score = calc_hit_score(candidate_pool, check_row)
    hit_nums = sorted(set(candidate_pool) & set(selected_birthday_nums(check_row["nums"], check_row["special"])))

    print("====== C2_v4 最後一期回測核對 ======")
    print(f"回測窗口：不包括核對期 {check_row['date']}")
    print(f"回測預測：{format_group_prediction_text(group_predictions)}")
    print(f"候選池：{','.join(str(num) for num in candidate_pool)} /> {len(candidate_pool)} 球")
    print(
        f"核對：{check_row['date']}，{format_birthday_slots(check_row)[0]}，"
        f"命中{format_nums(hit_nums)} /> {hit_score:g} 球"
    )
    print()


def predict_nextdraw_with_best(draws: list[DrawRow], best: dict[str, object]) -> None:
    window_count = to_int(best.get("window_count"), 21)
    top_prize_count = to_int(best.get("top_prize_count"), 7)
    pair_core_score = to_int(best.get("pair_core_score"), 15)
    single_hit_score = to_int(best.get("single_hit_score"), 1)
    date_score_value = best.get("date_score_list")
    date_score_list = date_score_value if isinstance(date_score_value, list) else _LEGACY_DATE_RECENT_SCORE_PROFILE_LIST[0]
    date_score_list = [to_int(value, 1) for value in date_score_list]
    set_predict_params(pair_core_score, single_hit_score, date_score_list)

    print_backtest_last_check(draws, window_count, top_prize_count)

    window_rows = draws[-window_count:]
    group_predictions = build_predictions_for_window(window_rows, top_prize_count)
    candidate_pool = flatten_predictions(group_predictions)
    latest_date = draws[-1]["date"]
    next_date = read_next_draw_date()
    save_nextdraw_csv(next_date, group_predictions)

    print("====== C2_v4 真正預測下一期 ======")
    print(
        f"讀入最佳參數：窗口期 {window_count}，prize前N {top_prize_count}，"
        f"pair分 {pair_core_score}，單球分 {single_hit_score}，日期分 {date_score_list}"
    )
    print(f"預測窗口：包括最新開獎期 {latest_date}")
    print(f"下一期開獎日期：{next_date}，未開獎，不能核對")
    print(f"預測：{format_group_prediction_text(group_predictions)}")
    print(f"候選池：{','.join(str(num) for num in candidate_pool)} /> {len(candidate_pool)} 球")
    for line in format_rbg_lines(candidate_pool):
        print(line)
    print(f"CSV 已寫入：{NEXTDRAW_CSV}")
    print()


def format_pair_sources(sources: list[PairSource]) -> str:
    if not sources:
        return "-"
    ranked = sorted(sources, key=lambda item: item["date"])
    return "；".join(
        f"{source['date']} pz{PRIZE_OPTION}:{source['prize_count']:g} "
        f"人氣{source['prize_score']} 日期{source['date_score']}"
        for source in ranked
    )


def print_collect_predictions(
    window_rows: list[DrawRow],
    top_prize_count: int,
    check_row: DrawRow,
) -> None:
    print(f"====== 第三步：由人氣 2 球組合產生分組預測，prize{PRIZE_OPTION} 前 {top_prize_count} 期 ======")
    print(
        f"第三步參數：GROUP_PREDICT_COUNT={GROUP_PREDICT_COUNT}，"
        f"PAIR_CORE_SCORE={ACTIVE_PAIR_CORE_SCORE}，SINGLE_HIT_SCORE={ACTIVE_SINGLE_HIT_SCORE}"
    )
    print(
        f"人氣分={PRIZE_RANK_SCORE_LIST}，"
        f"日期遠近分={ACTIVE_DATE_RECENT_SCORE_LIST}"
    )
    group_predictions: dict[str, list[int]] = {}
    for group_id, (group_label, _start_num, _end_num) in GROUPS.items():
        sample_rows = build_group_samples(window_rows, group_id, top_prize_count)
        repeat_pairs, pair_pool, fill_nums, prediction, final_scores = build_pair_based_prediction(sample_rows, group_id)
        group_predictions[group_label] = prediction
        print(f"[{group_id}] {group_label}")
        print("   重複人氣組合：")
        if repeat_pairs:
            for pair, idx, count, pair_score, sources in repeat_pairs:
                print(f"      {idx}組({pair[0]}-{pair[1]})x{count}，pair分數 {pair_score:g}")
                print(f"         來源：{format_pair_sources(sources)}")
        else:
            print("      -")
        if repeat_pairs:
            print(f"   pair集合球：{format_nums(pair_pool)} /> {len(pair_pool)} 球")
        else:
            print("   無重複 pair，使用 prize3 單球人氣補位")
        if fill_nums:
            print(f"   補位球：{format_nums(fill_nums)}")
        print(f"   單球分數：{format_num_scores(final_scores)}")
        print(f"   預測球：{format_nums(prediction)} /> {len(prediction)} 球")
    candidate_pool = sorted({num for nums in group_predictions.values() for num in nums})
    print()
    print(
        f"第三步預測總結："
        f"{format_nums(group_predictions.get('1-9', []))},"
        f"{format_nums(group_predictions.get('10-20', []))},"
        f"{format_nums(group_predictions.get('21-31', []))}"
    )
    print(f"候選池：{','.join(str(num) for num in candidate_pool)} /> {len(candidate_pool)} 球")
    check_nums = selected_birthday_nums(check_row["nums"], check_row["special"])
    hit_nums = sorted(set(candidate_pool) & set(check_nums))
    print(
        f"核對最後一期：{check_row['date']}，"
        f"{format_birthday_slots(check_row)[0]}，"
        f"命中{format_nums(hit_nums)} /> {len(hit_nums)} 球"
    )
    print()


def apply_best_params(best: dict[str, object]) -> tuple[int, int, int, int, list[int]]:
    window_count = to_int(best.get("window_count"), 21)
    top_prize_count = to_int(best.get("top_prize_count"), 5)
    pair_core_score = to_int(best.get("pair_core_score"), 10)
    single_hit_score = to_int(best.get("single_hit_score"), 1)
    date_score_list = to_int_list(best.get("date_score_list")) or DEFAULT_DATE_RECENT_SCORE_LIST
    set_predict_params(pair_core_score, single_hit_score, date_score_list)
    return window_count, top_prize_count, pair_core_score, single_hit_score, date_score_list


def build_backtest_detail_rows(
    draws: list[DrawRow],
    backtest_count: int,
    window_count: int,
    top_prize_count: int,
) -> list[dict[str, object]]:
    last_check_index = len(draws) - 1
    first_check_index = max(0, last_check_index - backtest_count + 1)
    rows: list[dict[str, object]] = []
    for check_index in range(first_check_index, last_check_index + 1):
        window_rows = build_window_rows(draws, check_index, window_count)
        if len(window_rows) < window_count or not is_group_sample_enough(window_rows, top_prize_count):
            continue
        check_row = draws[check_index]
        group_predictions = build_predictions_for_window(window_rows, top_prize_count)
        candidate_pool = flatten_predictions(group_predictions)
        normal_hits, special_hits, hit_score = split_hit_nums(candidate_pool, check_row)
        rows.append(
            {
                "check_date": check_row["date"],
                "check_draw": format_check_draw(check_row),
                "group_1_9": group_predictions.get("1-9", []),
                "group_10_20": group_predictions.get("10-20", []),
                "group_21_31": group_predictions.get("21-31", []),
                "candidate_pool": candidate_pool,
                "normal_hits": normal_hits,
                "special_hits": special_hits,
                "hit_score": hit_score,
                "prize": prize_label(hit_score),
            }
        )
    return rows


def write_backtest_csv(rows: list[dict[str, object]]) -> None:
    BET_DATA_DIR.mkdir(parents=True, exist_ok=True)
    with BET_RECORDS_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "group_1_9", "group_10_20", "group_21_31", "candidate_pool"])
        for row in rows:
            writer.writerow(
                [
                    row["check_date"],
                    format_nums(to_int_list(row["group_1_9"])),
                    format_nums(to_int_list(row["group_10_20"])),
                    format_nums(to_int_list(row["group_21_31"])),
                    format_nums(to_int_list(row["candidate_pool"])),
                ]
            )
    with WIN_RESULTS_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "normal_hits", "special_hits", "hit_score", "prize"])
        for row in rows:
            writer.writerow(
                [
                    row["check_date"],
                    format_nums(to_int_list(row["normal_hits"])),
                    format_nums(to_int_list(row["special_hits"])),
                    f"{to_float(row['hit_score']):g}",
                    row["prize"],
                ]
            )


def print_backtest_details(rows: list[dict[str, object]]) -> None:
    print("====== C2_v5 回測模式：讀入 C2_v4 最佳參數 ======")
    total_count = len(rows)
    for idx, row in enumerate(rows, start=1):
        near_idx = total_count - idx + 1
        normal_hits = to_int_list(row["normal_hits"])
        special_hits = to_int_list(row["special_hits"])
        hit_score = to_float(row["hit_score"])
        prize = prize_label(hit_score)
        prize_text = f" / 獎級：{prize}" if prize != "未中獎" else ""
        print(
            f"近 {near_idx}期：核對期號 {row['check_draw']}，"
            f"{format_nums(to_int_list(row['group_1_9']))}，"
            f"{format_nums(to_int_list(row['group_10_20']))}，"
            f"{format_nums(to_int_list(row['group_21_31']))}，"
            f"{format_hit_text(normal_hits, special_hits)} /> {hit_score:g} 球{prize_text}"
        )
    print()


def print_hit_summary(rows: list[dict[str, object]]) -> None:
    total_count = len(rows)
    print("====== 每分組最佳權重合併回測命中率：分組 [1, 2, 3] 1-9 + 10-20 + 21-31 ======")
    print(f"總回測期數：{total_count}")
    print("最高命中球數統計：")
    counter: Counter[float] = Counter(to_float(row["hit_score"]) for row in rows)
    for score in HIT_SCORE_LIST:
        count = counter.get(score, 0)
        rate = (count / total_count * 100) if total_count else 0.0
        print(f"{f'{score:g} 球'.ljust(7)}= {count} 期，{rate:.2f}%")
    print()


def run_backtest_mode(draws: list[DrawRow], best: dict[str, object]) -> None:
    window_count, top_prize_count, pair_core_score, single_hit_score, date_score_list = apply_best_params(best)
    print(
        f"讀入最佳參數：窗口期 {window_count}，prize前N {top_prize_count}，"
        f"pair分 {pair_core_score}，單球分 {single_hit_score}，日期分 {date_score_list}"
    )
    rows = build_backtest_detail_rows(draws, BACKTEST_DETAIL_COUNT, window_count, top_prize_count)
    write_backtest_csv(rows)
    print_backtest_details(rows)
    print_hit_summary(rows)
    # print(f"已寫入：{BET_RECORDS_CSV}")
    # print(f"已寫入：{WIN_RESULTS_CSV}")
    print()


def run_predict_mode(draws: list[DrawRow], best: dict[str, object]) -> None:
    window_count, top_prize_count, pair_core_score, single_hit_score, date_score_list = apply_best_params(best)
    window_rows = draws[-window_count:]
    group_predictions = build_predictions_for_window(window_rows, top_prize_count)
    candidate_pool = flatten_predictions(group_predictions)
    latest_date = draws[-1]["date"]
    next_date = read_next_draw_date()
    save_nextdraw_csv(next_date, group_predictions)

    print("====== C2_v5 預測模式：真正預測下一期 ======")
    print(
        f"讀入最佳參數：窗口期 {window_count}，prize前N {top_prize_count}，"
        f"pair分 {pair_core_score}，單球分 {single_hit_score}，日期分 {date_score_list}"
    )
    print(f"預測窗口：包括最新開獎期 {latest_date}")
    print(f"下一期開獎日期：{next_date}，未開獎，不能核對")
    print(f"預測：{format_group_prediction_text(group_predictions)}")
    print(f"候選池：{','.join(str(num) for num in candidate_pool)} /> {len(candidate_pool)} 球")
    for line in format_rbg_lines(candidate_pool):
        print(line)
    # print(f"已寫入：{NEXTDRAW_CSV}")
    print()


def main() -> None:
    draws = read_draws()
    if not draws:
        raise FileNotFoundError(f"找不到或未能讀取 M6：{M6_CSV}")

    best = read_best_params()
    if RUN_MODE == "predict":
        run_predict_mode(draws, best)
    else:
        run_backtest_mode(draws, best)


if __name__ == "__main__":
    main()
