from pathlib import Path
import csv
import itertools
from collections import Counter
from typing import TypedDict


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
M6_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"

# E3_v1：只做 1-9 回測預測，不做真正下期預測。
BACKTEST_DRAW_COUNT = 50
WINDOW_DRAW_COUNT_LIST = [12]
BIRTHDAY_NUM_MIN = 1
BIRTHDAY_NUM_MAX = 9
PREDICT_NUM_COUNT = 3 # pred 3,4 balls
SHOW_WINDOW_DETAIL = False  # True 顯示窗口期雙球組合明細；False 只顯示回測核對列表
MAX_SAME_PREDICT_STREAK = 2  # 同一組預測最多連續出現幾期；超過會改用下一組高分候選
RECENT_REPEAT_CHECK_COUNT = 1  # 檢查窗口期最近幾期是否與預測球重複太多
MAX_RECENT_REPEAT_COUNT = 1  # 超過此數量即提示；1 代表重複 2 球或以上會提示


class DrawRow(TypedDict):
    date: str
    nums: list[int]
    special: int | None


class PairStat(TypedDict):
    index: int
    pair: tuple[int, int]
    hit_periods: list[int]
    hit_count: int
    recent_index: int


class WindowDetail(TypedDict):
    check_no: int
    window_count: int
    pair_stats: list[PairStat]


def to_int(value: object, default: int = 0) -> int:
    if not isinstance(value, (int, float, str)):
        return default
    try:
        return int(float(value))
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


def format_nums(nums: list[int]) -> str:
    if not nums:
        return "[]"
    return "[" + ",".join(str(num) for num in nums) + "]"


def format_check_nums(row: DrawRow) -> str:
    parts = [str(num) for num in normal_group_nums(row)]
    special = row["special"]
    if special is not None and BIRTHDAY_NUM_MIN <= special <= BIRTHDAY_NUM_MAX:
        parts.append(f"-{special}")
    return "[" + ",".join(parts) + "]" if parts else "[]"


def pair_index_map() -> dict[tuple[int, int], int]:
    return {
        pair: idx
        for idx, pair in enumerate(
            itertools.combinations(range(BIRTHDAY_NUM_MIN, BIRTHDAY_NUM_MAX + 1), 2),
            start=1,
        )
    }


def build_window_rows(draws: list[DrawRow], check_index: int, window_count: int) -> list[DrawRow]:
    return draws[max(0, check_index - window_count):check_index]


def build_pair_stats(window_rows: list[DrawRow]) -> list[PairStat]:
    total_rows = len(window_rows)
    pair_hits: dict[tuple[int, int], list[int]] = {
        pair: []
        for pair in itertools.combinations(range(BIRTHDAY_NUM_MIN, BIRTHDAY_NUM_MAX + 1), 2)
    }
    for display_index, row in enumerate(window_rows, start=1):
        near_index = total_rows - display_index + 1
        nums = group_nums(row)
        if len(nums) < 2:
            continue
        for pair in itertools.combinations(nums, 2):
            pair_hits[pair].append(near_index)

    index_by_pair = pair_index_map()
    stats: list[PairStat] = []
    for pair, hit_periods in pair_hits.items():
        if not hit_periods:
            continue
        stats.append(
            {
                "index": index_by_pair[pair],
                "pair": pair,
                "hit_periods": hit_periods,
                "hit_count": len(hit_periods),
                "recent_index": min(hit_periods),
            }
        )
    return sorted(stats, key=lambda item: (-item["hit_count"], item["recent_index"], item["index"]))


def score_nums_from_pair_stats(pair_stats: list[PairStat]) -> Counter[int]:
    num_scores: Counter[int] = Counter()
    for rank, stat in enumerate(pair_stats, start=1):
        recent_bonus = max(0, 10 - stat["recent_index"])
        score = stat["hit_count"] * 10 + recent_bonus
        for num in stat["pair"]:
            num_scores[num] += score
        if rank >= 8:
            break
    return num_scores


def predict_from_pair_stats(pair_stats: list[PairStat]) -> list[int]:
    num_scores = score_nums_from_pair_stats(pair_stats)

    return [
        num
        for num, _score in sorted(num_scores.items(), key=lambda item: (-item[1], item[0]))[:PREDICT_NUM_COUNT]
    ]


def build_alternate_prediction(pair_stats: list[PairStat], previous_prediction: list[int]) -> list[int]:
    num_scores = score_nums_from_pair_stats(pair_stats)
    ranked_nums = [num for num, _score in sorted(num_scores.items(), key=lambda item: (-item[1], item[0]))]
    previous_key = tuple(sorted(previous_prediction))

    best_combo: tuple[int, ...] | None = None
    best_score = -1
    for combo in itertools.combinations(ranked_nums[: min(len(ranked_nums), 7)], PREDICT_NUM_COUNT):
        combo_key = tuple(sorted(combo))
        if combo_key == previous_key:
            continue
        combo_score = sum(num_scores[num] for num in combo)
        if combo_score > best_score:
            best_score = combo_score
            best_combo = combo

    if best_combo is None:
        return previous_prediction
    return sorted(best_combo, key=lambda num: (-num_scores[num], num))


def calc_hit(pred_nums: list[int], check_row: DrawRow) -> tuple[list[int], list[int], float]:
    pred_set = set(pred_nums)
    normal_hits = sorted(pred_set & set(normal_group_nums(check_row)))
    special = check_row["special"]
    special_hits = [special] if special is not None and special in pred_set else []
    return normal_hits, special_hits, len(normal_hits) + (0.5 if special_hits else 0.0)


def build_recent_repeat_alert(pred_nums: list[int], window_rows: list[DrawRow]) -> str:
    if not window_rows:
        return ""
    pred_set = set(pred_nums)
    recent_rows = window_rows[-RECENT_REPEAT_CHECK_COUNT:]
    alert_parts: list[str] = []
    for row in recent_rows:
        repeated_nums = sorted(pred_set & set(group_nums(row)))
        if len(repeated_nums) > MAX_RECENT_REPEAT_COUNT:
            alert_parts.append(f"{row['date']} 重複{format_nums(repeated_nums)}")
    if not alert_parts:
        return ""
    return "短期重複提示：" + "；".join(alert_parts)


def print_pair_stats(pair_stats: list[PairStat], limit: int = 8) -> None:
    print("雙球組合：命中期數最多在上")
    for stat in pair_stats[:limit]:
        print(
            f'{stat["index"]},"({stat["pair"][0]},{stat["pair"][1]})",'
            f'"{format_nums(stat["hit_periods"])}",{stat["hit_count"]}'
        )


def print_hit_summary(hit_scores: list[float], no_group_count: int, window_count: int) -> None:
    total_count = len(hit_scores)
    one_or_more_count = sum(score >= 1 for score in hit_scores)
    target_count = sum(score >= 1.5 for score in hit_scores)
    good_count = sum(score >= 2 for score in hit_scores)
    zero_count = sum(score == 0 for score in hit_scores)
    print("----------------------")
    print("1-9 命中統計")
    print(f"4+ = {sum(score >= 4 for score in hit_scores)} 期")
    print(f"3+ = {sum(score >= 3 for score in hit_scores)} 期")
    print(f"2 = {sum(score == 2 for score in hit_scores)} 期")
    print(f"1.5 = {sum(score == 1.5 for score in hit_scores)} 期")
    print(f"1 = {sum(score == 1 for score in hit_scores)} 期")
    print(f"0 = {sum(score == 0 for score in hit_scores)} 期")
    print(f"1球以上合格率 = {one_or_more_count}/{total_count}，{one_or_more_count / total_count * 100:.2f}%")
    print(f"1.5球以上合格率 = {target_count}/{total_count}，{target_count / total_count * 100:.2f}%")
    print(f"2球以上良好率 = {good_count}/{total_count}，{good_count / total_count * 100:.2f}%")
    print(f"0球失敗率 = {zero_count}/{total_count}，{zero_count / total_count * 100:.2f}%")
    print(f"每期回測，窗口 {window_count} 期，有 {no_group_count}/{total_count} 期，1-9 包含特號，沒有出現。")
    print()


def run_backtest(draws: list[DrawRow]) -> None:
    last_check_index = len(draws) - 1
    first_check_index = max(0, last_check_index - BACKTEST_DRAW_COUNT + 1)
    check_indices = list(range(first_check_index, last_check_index + 1))
    window_details: list[WindowDetail] = []

    print("====== E3_v1 1-9 雙球預測回測 ======")
    print(f"資料期數：{len(draws)}")
    print(f"BACKTEST_DRAW_COUNT = {BACKTEST_DRAW_COUNT}")
    print(f"WINDOW_DRAW_COUNT_LIST = {WINDOW_DRAW_COUNT_LIST}")
    print("回測定義：每一期都是獨立核對期；窗口期不包括該核對期。")
    print("核對口徑：N1-N6 命中每球 = 1；N7 特號命中 = 0.5。")
    print()

    for window_count in WINDOW_DRAW_COUNT_LIST:
        hit_scores: list[float] = []
        no_group_count = 0
        last_prediction_key: tuple[int, ...] | None = None
        same_prediction_streak = 0
        print(f"====== 窗口期 {window_count} 期 回測核對 ======")
        for idx, check_index in enumerate(check_indices, start=1):
            check_row = draws[check_index]
            window_rows = build_window_rows(draws, check_index, window_count)
            pair_stats = build_pair_stats(window_rows)
            window_details.append(
                {
                    "check_no": idx,
                    "window_count": window_count,
                    "pair_stats": pair_stats,
                }
            )
            prediction = predict_from_pair_stats(pair_stats)
            prediction_key = tuple(sorted(prediction))
            if prediction_key == last_prediction_key:
                same_prediction_streak += 1
            else:
                same_prediction_streak = 1

            if same_prediction_streak > MAX_SAME_PREDICT_STREAK:
                prediction = build_alternate_prediction(pair_stats, prediction)
                prediction_key = tuple(sorted(prediction))
                same_prediction_streak = 1

            last_prediction_key = prediction_key
            normal_hits, special_hits, hit_score = calc_hit(prediction, check_row)
            hit_scores.append(hit_score)
            if not group_nums(check_row):
                no_group_count += 1
            special_text = f" + 特號{format_nums(special_hits)}" if special_hits else ""

            print(
                f"{idx}，回測核對：{check_row['date']}，{format_check_nums(check_row)}，"
                f"預測{format_nums(prediction)}，"
                f"命中{format_nums(normal_hits)}{special_text} /> {hit_score:g} 球"
            )
        print_hit_summary(hit_scores, no_group_count, window_count)

    if SHOW_WINDOW_DETAIL:
        print("====== 窗口雙球組合明細 ======")
        for detail in window_details:
            print(
                f"/> === 核對回測分析第{detail['check_no']}期，"
                f"窗口期 {detail['window_count']} 期 ==="
            )
            print_pair_stats(detail["pair_stats"])
            print()


def main() -> None:
    draws = read_draws()
    if not draws:
        raise RuntimeError("M6 沒有可用開獎資料。")
    run_backtest(draws)


if __name__ == "__main__":
    main()
