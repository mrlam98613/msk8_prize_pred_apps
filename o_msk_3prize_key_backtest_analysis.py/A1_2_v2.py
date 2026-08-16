from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import csv
import itertools
import math


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
M6_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"

BACKTEST_WINDOW = 70  # 回測窗口期數：每次只用目標期之前最近多少期做分析
PREDICT_BET_COUNT = 7  # 每一期產生多少注模擬投注
PREDICT_NUM_COUNT_PATTERN = [4, 5, 6]  # 每注號碼數量循環模式，例如 4號注、5號注、6號注
BIRTHDAY_NUM_MIN = 1  # 分析號碼範圍最小值
BIRTHDAY_NUM_MAX = 31  # 分析號碼範圍最大值
NUMBER_GROUPS = [(1, 9), (10, 19), (20, 31)]  # 分區計算組合權重，避免全部 1-31 混在一起
COMBINATION_TAKE_COUNTS = [2, 3]  # 組合權重使用幾多個號碼一組
PRIZE_OPTION = 3  # 權重參考獎項注數，可選 1、2、3；3 即 prize3 注數

HOT_PRIZE_PERCENTILE = 0.7  # prize 注數排最高 70% 或以上，視為熱門組合來源
COLD_PRIZE_PERCENTILE = 0.3  # prize 注數排最低 30% 或以下，視為冷門/次選組合來源
HOT_COMBO_RATIO = 0.7  # 產生投注時，熱門組合約佔比例
MAX_OVERLAP_PER_BET = 3  # 新投注與已產生投注最多可重疊幾個號碼

SHOW_RECENT_DETAIL_COUNT = 10  # 最後顯示最近多少期的命中明細
MIN_PRINT_HIT_COUNT = 3  # 命中明細只顯示中幾個正號或以上的投注
SHOW_TOP_COMBOS = True  # 是否顯示最後一期窗口的熱門/冷門組合排名
TOP_COMBO_PRINT_COUNT = 12  # 熱門/冷門組合排名顯示多少組


@dataclass(frozen=True)
class DrawRow:
    date: str
    nums: tuple[int, ...]
    prize_count: float


@dataclass
class ComboStat:
    combo: tuple[int, ...]
    group_label: str
    pool_type: str
    score: float = 0.0
    hit_count: int = 0
    prize_sum: float = 0.0
    last_seen_step: int = 0


@dataclass(frozen=True)
class BetResult:
    draw_date: str
    bet_index: int
    bet_nums: tuple[int, ...]
    draw_nums: tuple[int, ...]
    hit_nums: tuple[int, ...]


def read_m6_lotto_history(csv_path: Path = M6_CSV) -> list[DrawRow]:
    """讀入 M6 歷史開獎資料，整理日期、N1-N6 正號及指定獎項注數。"""

    if not csv_path.exists():
        raise FileNotFoundError(f"找不到 M6 CSV：{csv_path}")

    rows: list[DrawRow] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames:
            reader.fieldnames = [name.strip().lstrip("\ufeff") for name in reader.fieldnames]

        for row in reader:
            nums = []
            for idx in range(1, 7):
                try:
                    nums.append(int((row.get(f"N{idx}") or "").strip()))
                except ValueError:
                    nums.append(0)

            try:
                prize_count = float((row.get(f"prize{PRIZE_OPTION}") or "0").strip())
            except ValueError:
                prize_count = 0.0

            rows.append(
                DrawRow(
                    date=(row.get("nDdate") or "").strip(),
                    nums=tuple(nums),
                    prize_count=prize_count,
                )
            )
    return rows


def selected_birthday_nums(nums: tuple[int, ...]) -> tuple[int, ...]:
    """只保留設定範圍內的號碼，例如 1-31 生日號範圍。"""

    return tuple(sorted(num for num in nums if BIRTHDAY_NUM_MIN <= num <= BIRTHDAY_NUM_MAX))


def selected_group_nums(nums: tuple[int, ...], group_min: int, group_max: int) -> tuple[int, ...]:
    """只保留指定分區內的號碼，例如 1-9、10-19、20-31。"""

    return tuple(sorted(num for num in nums if group_min <= num <= group_max))


def validate_params() -> None:
    """檢查所有手動參數是否合理，避免回測前輸入錯誤設定。"""

    if BACKTEST_WINDOW < 1:
        raise ValueError("BACKTEST_WINDOW 必須大於 0")
    if PREDICT_BET_COUNT < 1:
        raise ValueError("PREDICT_BET_COUNT 必須大於 0")
    if not PREDICT_NUM_COUNT_PATTERN:
        raise ValueError("PREDICT_NUM_COUNT_PATTERN 不可空白")
    if BIRTHDAY_NUM_MIN < 1 or BIRTHDAY_NUM_MAX > 49 or BIRTHDAY_NUM_MIN > BIRTHDAY_NUM_MAX:
        raise ValueError("BIRTHDAY_NUM_MIN / MAX 必須介乎 1 至 49，且最小不可大於最大")
    available_count = BIRTHDAY_NUM_MAX - BIRTHDAY_NUM_MIN + 1
    if max(PREDICT_NUM_COUNT_PATTERN) > available_count:
        raise ValueError(f"投注號碼數不可大於查詢範圍號碼數量 {available_count}")
    for group_min, group_max in NUMBER_GROUPS:
        if group_min < BIRTHDAY_NUM_MIN or group_max > BIRTHDAY_NUM_MAX or group_min > group_max:
            raise ValueError(f"NUMBER_GROUPS 分區不正確：{group_min}-{group_max}")
    for take_count in COMBINATION_TAKE_COUNTS:
        if take_count < 1 or take_count > available_count:
            raise ValueError(f"COMBINATION_TAKE_COUNTS 內的 {take_count} 不可使用")
    if PRIZE_OPTION not in {1, 2, 3}:
        raise ValueError("PRIZE_OPTION 只可選 1、2、3")
    if not 0 <= COLD_PRIZE_PERCENTILE <= HOT_PRIZE_PERCENTILE <= 1:
        raise ValueError("冷熱 prize 百分位設定不正確")
    if MAX_OVERLAP_PER_BET < 0:
        raise ValueError("MAX_OVERLAP_PER_BET 不可小於 0")


def percentile(values: list[float], ratio: float) -> float:
    """計算簡單百分位數，用於分開熱門及冷門 prize 注數期。"""

    if not values:
        return 0.0
    sorted_values = sorted(values)
    index = min(len(sorted_values) - 1, max(0, math.ceil(len(sorted_values) * ratio) - 1))
    return sorted_values[index]


def prize_pool_type(prize_count: float, hot_line: float, cold_line: float) -> str:
    """根據 prize 注數把該期分類為 HOT、COLD 或 NORMAL。"""

    if prize_count >= hot_line:
        return "HOT"
    if prize_count <= cold_line:
        return "COLD"
    return "NORMAL"


def recency_weight(step: int, window_size: int) -> float:
    """用三段式近期權重，最近 10 期較高，中段正常，較舊較低。"""

    if window_size <= 0:
        return 1.0
    recent_start = max(1, window_size - 9)
    middle_start = max(1, window_size - 19)
    if step >= recent_start:
        return 1.5
    if step >= middle_start:
        return 1.0
    return 0.7


def build_combo_stats(window_rows: list[DrawRow]) -> list[ComboStat]:
    """分區建立 2號/3號組合權重，並把高 prize/低 prize 分池。"""

    prize_values = [row.prize_count for row in window_rows]
    hot_line = percentile(prize_values, HOT_PRIZE_PERCENTILE)
    cold_line = percentile(prize_values, COLD_PRIZE_PERCENTILE)
    stats: dict[tuple[tuple[int, ...], str, str], ComboStat] = {}
    window_size = max(len(window_rows), 1)

    for step, row in enumerate(window_rows, start=1):
        pool_type = prize_pool_type(row.prize_count, hot_line, cold_line)
        prize_weight = row.prize_count / 100.0
        age_weight = recency_weight(step, window_size)

        for group_min, group_max in NUMBER_GROUPS:
            group_nums = selected_group_nums(row.nums, group_min, group_max)
            group_label = f"{group_min}-{group_max}"
            for take_count in COMBINATION_TAKE_COUNTS:
                if len(group_nums) < take_count:
                    continue
                for combo in itertools.combinations(group_nums, take_count):
                    key = (combo, group_label, pool_type)
                    stat = stats.setdefault(
                        key,
                        ComboStat(combo=combo, group_label=group_label, pool_type=pool_type),
                    )
                    pool_weight = 1.2 if pool_type == "HOT" else 0.85 if pool_type == "COLD" else 1.0
                    stat.hit_count += 1
                    stat.prize_sum += row.prize_count
                    stat.last_seen_step = step
                    stat.score += (1.0 + prize_weight) * age_weight * pool_weight

    return sorted(
        stats.values(),
        key=lambda item: (
            item.score,
            item.hit_count,
            item.prize_sum,
            item.last_seen_step,
            item.combo,
        ),
        reverse=True,
    )


def split_combo_pools(combo_stats: list[ComboStat]) -> tuple[list[ComboStat], list[ComboStat]]:
    """拆出熱門組合池及冷門/次選組合池。"""

    hot_stats = [stat for stat in combo_stats if stat.pool_type == "HOT"]
    cold_stats = [stat for stat in combo_stats if stat.pool_type == "COLD"]
    if not cold_stats:
        cold_stats = [stat for stat in combo_stats if stat.pool_type == "NORMAL"]
    return hot_stats, cold_stats


def build_number_scores(combo_stats: list[ComboStat]) -> dict[int, float]:
    """將組合權重拆回單號分數，用作補足每注號碼及排序。"""

    number_scores: dict[int, float] = defaultdict(float)
    for stat in combo_stats:
        for num in stat.combo:
            number_scores[num] += stat.score
    return dict(number_scores)


def target_bet_size(bet_index: int) -> int:
    """按投注序號循環取得每注號碼數量。"""

    return PREDICT_NUM_COUNT_PATTERN[(bet_index - 1) % len(PREDICT_NUM_COUNT_PATTERN)]


def normalize_bet_nums(
    nums: set[int],
    number_scores: dict[int, float],
    bet_size: int,
) -> tuple[int, ...]:
    """整理單注號碼；如超出指定號碼數，保留分數較高的號碼。"""

    if len(nums) > bet_size:
        nums = set(
            sorted(
                nums,
                key=lambda num: (number_scores.get(num, 0.0), -num),
                reverse=True,
            )[:bet_size]
        )
    return tuple(sorted(nums))


def has_too_much_overlap(
    bet_nums: tuple[int, ...],
    existing_bets: list[tuple[int, ...]],
    overlap_limit: int,
) -> bool:
    """檢查新投注與已產生投注是否重疊太多，避免 20 注太相似。"""

    bet_set = set(bet_nums)
    return any(len(bet_set.intersection(existing_bet)) > overlap_limit for existing_bet in existing_bets)


def generate_prediction_bets(combo_stats: list[ComboStat]) -> list[tuple[int, ...]]:
    """根據熱門/冷門組合池產生每期模擬投注號碼。"""

    number_scores = build_number_scores(combo_stats)
    fallback_nums = [
        num
        for num, _score in sorted(
            number_scores.items(),
            key=lambda item: (item[1], -item[0]),
            reverse=True,
        )
    ]
    hot_stats, cold_stats = split_combo_pools(combo_stats)
    hot_target_count = round(PREDICT_BET_COUNT * HOT_COMBO_RATIO)

    bets: list[tuple[int, ...]] = []
    seen: set[tuple[int, ...]] = set()
    candidate_stats = hot_stats + cold_stats + combo_stats

    overlap_limits = list(range(MAX_OVERLAP_PER_BET, max(PREDICT_NUM_COUNT_PATTERN) + 1))
    for overlap_limit in overlap_limits:
        for start_idx, stat in enumerate(candidate_stats):
            bet_no = len(bets) + 1
            bet_size = target_bet_size(bet_no)
            prefer_hot = bet_no <= hot_target_count
            source_stats = hot_stats if prefer_hot and hot_stats else cold_stats if cold_stats else combo_stats
            paired_stats = cold_stats if prefer_hot and cold_stats else hot_stats if hot_stats else combo_stats
            nums = set(stat.combo)

            for next_stat in source_stats[start_idx % max(len(source_stats), 1) :]:
                nums.update(next_stat.combo)
                if len(nums) >= bet_size:
                    break

            for next_stat in paired_stats:
                if len(nums) >= bet_size:
                    break
                nums.update(next_stat.combo)

            for num in fallback_nums:
                if len(nums) >= bet_size:
                    break
                nums.add(num)

            bet_nums = normalize_bet_nums(nums, number_scores, bet_size)
            if (
                len(bet_nums) < bet_size
                or bet_nums in seen
                or has_too_much_overlap(bet_nums, bets, overlap_limit)
            ):
                continue

            seen.add(bet_nums)
            bets.append(bet_nums)
            if len(bets) >= PREDICT_BET_COUNT:
                return bets

    return bets


def run_backtest(rows: list[DrawRow]) -> list[BetResult]:
    """逐期回測：用前 N 期產生預測，再核對下一期實際開獎。"""

    results: list[BetResult] = []
    for target_idx in range(BACKTEST_WINDOW, len(rows)):
        window_rows = rows[target_idx - BACKTEST_WINDOW : target_idx]
        target_row = rows[target_idx]
        draw_nums = selected_birthday_nums(target_row.nums)
        draw_num_set = set(draw_nums)
        combo_stats = build_combo_stats(window_rows)
        bets = generate_prediction_bets(combo_stats)

        for bet_index, bet_nums in enumerate(bets, start=1):
            hit_nums = tuple(num for num in bet_nums if num in draw_num_set)
            results.append(
                BetResult(
                    draw_date=target_row.date,
                    bet_index=bet_index,
                    bet_nums=bet_nums,
                    draw_nums=draw_nums,
                    hit_nums=hit_nums,
                )
            )
    return results


def group_results_by_date(results: list[BetResult]) -> dict[str, list[BetResult]]:
    """按開獎日期整理回測結果，用來計算每期命中率。"""

    grouped: dict[str, list[BetResult]] = defaultdict(list)
    for result in results:
        grouped[result.draw_date].append(result)
    return dict(grouped)


def format_nums(nums: tuple[int, ...]) -> str:
    """將號碼 tuple 轉成逗號分隔文字，方便打印。"""

    return ",".join(str(num) for num in nums)


def print_summary(results: list[BetResult]) -> None:
    """打印整體回測命中率統計，包含單注命中率及每期命中率。"""

    print("====== A1_2_v2 3獎分區組合權重回測 ======")
    print(
        f"窗口：{BACKTEST_WINDOW} 期，每期：{PREDICT_BET_COUNT} 注，"
        f"投注號碼數：{PREDICT_NUM_COUNT_PATTERN}"
    )
    print(
        f"號碼範圍：{BIRTHDAY_NUM_MIN}-{BIRTHDAY_NUM_MAX}，"
        f"分區：{NUMBER_GROUPS}，組合：{COMBINATION_TAKE_COUNTS}，"
        f"權重參考 prize{PRIZE_OPTION} 注數"
    )

    if not results:
        print("沒有可回測資料。")
        return

    grouped = group_results_by_date(results)
    print(f"回測期數：{len(grouped)}，總模擬注數：{len(results)}")

    print()
    print("單注命中率：")
    max_hit_count = max(len(result.bet_nums) for result in results)
    for hit_count in range(max_hit_count, -1, -1):
        count = sum(1 for result in results if len(result.hit_nums) == hit_count)
        if count > 0:
            rate = count / len(results) * 100
            print(f"命中 {hit_count} 個正號：{count} 注，{rate:.2f}%")

    print()
    print("每期命中率：")
    for threshold in [3, 4, 5]:
        draw_hit_count = sum(
            1
            for draw_results in grouped.values()
            if any(len(result.hit_nums) >= threshold for result in draw_results)
        )
        rate = draw_hit_count / len(grouped) * 100
        print(f"至少 1 注命中 >= {threshold} 個正號：{draw_hit_count} 期，{rate:.2f}%")


def print_recent_hit_detail(results: list[BetResult]) -> None:
    """打印最近期數中，每期全部預測注及命中球數。"""

    grouped = group_results_by_date(results)
    recent_dates = list(grouped.keys())[-SHOW_RECENT_DETAIL_COUNT:]

    print()
    print(f"====== 最近 {len(recent_dates)} 期，預測 {PREDICT_NUM_COUNT_PATTERN} 球注核對明細 ======")
    for draw_date in recent_dates:
        draw_results = grouped[draw_date]
        draw_nums_text = format_nums(draw_results[0].draw_nums) if draw_results else ""
        print()
        print(f"核對下期 {draw_date} ： {draw_nums_text}")
        for result in draw_results:
            hit_text = format_nums(result.hit_nums)
            hit_suffix = f"：{hit_text}" if hit_text else ""
            print(
                f"{result.bet_index:>2}， {format_nums(result.bet_nums)} "
                f"中/> {len(result.hit_nums)} 球{hit_suffix}"
            )


def print_last_window_top_combos(rows: list[DrawRow]) -> None:
    """打印最後一期預測窗口的熱門/冷門組合排名，方便觀察權重來源。"""

    if not SHOW_TOP_COMBOS or len(rows) <= BACKTEST_WINDOW:
        return

    window_rows = rows[-BACKTEST_WINDOW:]
    combo_stats = build_combo_stats(window_rows)
    hot_stats, cold_stats = split_combo_pools(combo_stats)

    print()
    print(
        f"====== 最後 {BACKTEST_WINDOW} 期熱門組合 Top {TOP_COMBO_PRINT_COUNT}，"
        "組合球該期資訊 ======"
    )
    for idx, stat in enumerate(hot_stats[:TOP_COMBO_PRINT_COUNT], start=1):
        print(
            f"{idx:>2}. {stat.group_label} {format_nums(stat.combo)} /> "
            f"分數 {stat.score:.2f} / 出次數 {stat.hit_count} / "
            f"中{PRIZE_OPTION}獎 {stat.prize_sum:g} 注"
        )

    print()
    print(
        f"====== 最後 {BACKTEST_WINDOW} 期冷門/次選組合 Top {TOP_COMBO_PRINT_COUNT}，"
        "組合球該期資訊 ======"
    )
    for idx, stat in enumerate(cold_stats[:TOP_COMBO_PRINT_COUNT], start=1):
        print(
            f"{idx:>2}. {stat.group_label} {format_nums(stat.combo)} /> "
            f"分數 {stat.score:.2f} / 出次數 {stat.hit_count} / "
            f"中{PRIZE_OPTION}獎 {stat.prize_sum:g} 注"
        )


def main() -> None:
    """主程式入口：驗證參數、讀取資料、執行回測、打印結果。"""

    validate_params()
    rows = read_m6_lotto_history()
    results = run_backtest(rows)
    print_summary(results)
    print_recent_hit_detail(results)
    print_last_window_top_combos(rows)


if __name__ == "__main__":
    main()
