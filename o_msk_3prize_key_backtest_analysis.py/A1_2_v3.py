from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import csv
import itertools
import json
import math
import random


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
M6_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"

BACKTEST_WINDOW = 24  # 4 week. x 3(2,4,6) = 12 x 3(Month) = 48 期，回測窗口期數：每次只用目標期之前最近多少期做分析
PREDICT_BET_COUNT = 4  # 每一期產生多少注模擬投注；第 4 注為分區隨機 6 球
PREDICT_NUM_COUNT_PATTERN = [4, 5, 6]  # 前 3 注分別產生 4球、5球、6球單注組合
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

USE_COMBO_INDEX_MEMORY = True  # 是否啟用組合索引記憶加權
COMBO_INDEX_MEMORY_PATH = CURRENT_DIR / "combo_index_memory.json"  # 組合索引記憶 JSON
MEMORY_WINDOW = 24  # 更新記憶時，取最近多少期做組合核對統計
MEMORY_HIT_MIN_COUNT = 1  # 組合出現幾次或以上，才納入 index 記憶
MEMORY_CLUSTER_GAP = 3  # 命中 index 相隔多少以內，視為同一群組
MEMORY_CLUSTER_MIN_SIZE = 3  # 群組至少有多少個 index，才成為偏好區段
COMBO_INDEX_MEMORY_WEIGHT = 1.3  # 命中偏好 index 區段的組合，分數乘以此權重

ENABLE_GROUP_RANDOM_BET = True  # 是否加入第 4 注：1-9、10-19、20-31 每區隨機取 2 球
GROUP_RANDOM_BET_INDEX = 4  # 分區隨機投注放在第幾注
GROUP_RANDOM_PICK_COUNT = 2  # 分區隨機投注每個分區取幾個號碼
RANDOM_SEED_BASE = 20260816  # 固定亂數種子，確保每次回測結果一致


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
    take_count: int
    combo_index: int
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


def memory_key(group_label: str, take_count: int) -> str:
    """建立 JSON 記憶鍵，例如 20-31|2。"""

    return f"{group_label}|{take_count}"


def build_combo_index_map(group_min: int, group_max: int, take_count: int) -> dict[tuple[int, ...], int]:
    """建立某分區所有組合的固定索引表，索引由 1 開始。"""

    combinations = itertools.combinations(range(group_min, group_max + 1), take_count)
    return {combo: idx for idx, combo in enumerate(combinations, start=1)}


def load_combo_index_memory() -> dict[str, dict[str, object]]:
    """讀取組合 index 記憶 JSON；如不存在則回傳空記憶。"""

    if not USE_COMBO_INDEX_MEMORY or not COMBO_INDEX_MEMORY_PATH.exists():
        return {}
    try:
        with COMBO_INDEX_MEMORY_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def save_combo_index_memory(memory: dict[str, dict[str, object]]) -> None:
    """把最新組合 index 記憶寫入 JSON，供下次自動加載。"""

    if not USE_COMBO_INDEX_MEMORY:
        return
    with COMBO_INDEX_MEMORY_PATH.open("w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)


def normalize_memory_ranges(value: object) -> list[tuple[int, int]]:
    """把 JSON 讀出的 preferred_ranges 安全轉成 [(start, end)]。"""

    if not isinstance(value, list):
        return []

    ranges: list[tuple[int, int]] = []
    for item in value:
        if not isinstance(item, list | tuple) or len(item) != 2:
            continue
        start, end = item
        if not isinstance(start, int) or not isinstance(end, int):
            continue
        ranges.append((start, end))
    return ranges


def index_in_ranges(combo_index: int, ranges: list[tuple[int, int]]) -> bool:
    """檢查組合 index 是否落在記憶偏好區段內。"""

    return any(start <= combo_index <= end for start, end in ranges)


def find_index_clusters(hit_indexes: list[int]) -> list[list[int]]:
    """把命中的組合 index 整理成連續或接近的群聚區段。"""

    if not hit_indexes:
        return []

    clusters: list[list[int]] = []
    current_cluster = [hit_indexes[0]]
    for combo_index in hit_indexes[1:]:
        if combo_index - current_cluster[-1] <= MEMORY_CLUSTER_GAP:
            current_cluster.append(combo_index)
        else:
            if len(current_cluster) >= MEMORY_CLUSTER_MIN_SIZE:
                clusters.append([current_cluster[0], current_cluster[-1]])
            current_cluster = [combo_index]

    if len(current_cluster) >= MEMORY_CLUSTER_MIN_SIZE:
        clusters.append([current_cluster[0], current_cluster[-1]])
    return clusters


def update_combo_index_memory(rows: list[DrawRow]) -> dict[str, dict[str, object]]:
    """用最近 MEMORY_WINDOW 期更新組合 index 命中記憶。"""

    if not USE_COMBO_INDEX_MEMORY:
        return {}

    memory: dict[str, dict[str, object]] = {}
    window_rows = rows[-MEMORY_WINDOW:]
    last_update_date = window_rows[-1].date if window_rows else ""

    for group_min, group_max in NUMBER_GROUPS:
        group_label = f"{group_min}-{group_max}"
        for take_count in COMBINATION_TAKE_COUNTS:
            index_map = build_combo_index_map(group_min, group_max, take_count)
            hit_indexes: dict[int, int] = defaultdict(int)
            hit_combos: dict[int, str] = {}

            for row in window_rows:
                group_nums = selected_group_nums(row.nums, group_min, group_max)
                if len(group_nums) < take_count:
                    continue
                for combo in itertools.combinations(group_nums, take_count):
                    combo_index = index_map.get(combo)
                    if combo_index is None:
                        continue
                    hit_indexes[combo_index] += 1
                    hit_combos[combo_index] = format_nums(combo)

            qualified_indexes = sorted(
                combo_index
                for combo_index, hit_count in hit_indexes.items()
                if hit_count >= MEMORY_HIT_MIN_COUNT
            )
            preferred_ranges = find_index_clusters(qualified_indexes)
            key = memory_key(group_label, take_count)
            memory[key] = {
                "window": MEMORY_WINDOW,
                "group": group_label,
                "take_count": take_count,
                "total_combos": len(index_map),
                "preferred_ranges": preferred_ranges,
                "hit_indexes": {
                    str(combo_index): {
                        "combo": hit_combos[combo_index],
                        "hit_count": hit_indexes[combo_index],
                    }
                    for combo_index in qualified_indexes
                },
                "last_update_date": last_update_date,
            }

    save_combo_index_memory(memory)
    return memory


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
    if MEMORY_WINDOW < 1:
        raise ValueError("MEMORY_WINDOW 必須大於 0")
    if MEMORY_CLUSTER_GAP < 0:
        raise ValueError("MEMORY_CLUSTER_GAP 不可小於 0")
    if MEMORY_CLUSTER_MIN_SIZE < 1:
        raise ValueError("MEMORY_CLUSTER_MIN_SIZE 必須大於 0")
    if COMBO_INDEX_MEMORY_WEIGHT <= 0:
        raise ValueError("COMBO_INDEX_MEMORY_WEIGHT 必須大於 0")


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


def build_combo_stats(
    window_rows: list[DrawRow],
    combo_index_memory: dict[str, dict[str, object]] | None = None,
) -> list[ComboStat]:
    """分區建立 2號/3號組合權重，並把高 prize/低 prize 分池。"""

    combo_index_memory = combo_index_memory or {}
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
                index_map = build_combo_index_map(group_min, group_max, take_count)
                memory = combo_index_memory.get(memory_key(group_label, take_count), {})
                preferred_ranges = normalize_memory_ranges(memory.get("preferred_ranges", []))
                for combo in itertools.combinations(group_nums, take_count):
                    combo_index = index_map.get(combo, 0)
                    key = (combo, group_label, pool_type)
                    stat = stats.setdefault(
                        key,
                        ComboStat(
                            combo=combo,
                            group_label=group_label,
                            pool_type=pool_type,
                            take_count=take_count,
                            combo_index=combo_index,
                        ),
                    )
                    pool_weight = 1.2 if pool_type == "HOT" else 0.85 if pool_type == "COLD" else 1.0
                    memory_weight = (
                        COMBO_INDEX_MEMORY_WEIGHT
                        if index_in_ranges(combo_index, preferred_ranges)
                        else 1.0
                    )
                    stat.hit_count += 1
                    stat.prize_sum += row.prize_count
                    stat.last_seen_step = step
                    stat.score += (1.0 + prize_weight) * age_weight * pool_weight * memory_weight

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


def build_group_random_bet(window_rows: list[DrawRow], target_idx: int) -> tuple[int, ...]:
    """建立第 4 注分區隨機投注：每個分區從窗口候選球取 2 球。"""

    rng = random.Random(RANDOM_SEED_BASE + target_idx)
    bet_nums: list[int] = []

    for group_min, group_max in NUMBER_GROUPS:
        candidates = sorted(
            {
                num
                for row in window_rows
                for num in selected_group_nums(row.nums, group_min, group_max)
            }
        )
        if len(candidates) < GROUP_RANDOM_PICK_COUNT:
            candidates = list(range(group_min, group_max + 1))
        bet_nums.extend(rng.sample(candidates, GROUP_RANDOM_PICK_COUNT))

    return tuple(sorted(bet_nums))


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
            if ENABLE_GROUP_RANDOM_BET and len(bets) + 1 == GROUP_RANDOM_BET_INDEX:
                break
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


def run_backtest(
    rows: list[DrawRow],
    combo_index_memory: dict[str, dict[str, object]],
) -> list[BetResult]:
    """逐期回測：用前 N 期產生預測，再核對下一期實際開獎。"""

    results: list[BetResult] = []
    for target_idx in range(BACKTEST_WINDOW, len(rows)):
        window_rows = rows[target_idx - BACKTEST_WINDOW : target_idx]
        target_row = rows[target_idx]
        draw_nums = selected_birthday_nums(target_row.nums)
        draw_num_set = set(draw_nums)
        combo_stats = build_combo_stats(window_rows, combo_index_memory)
        bets = generate_prediction_bets(combo_stats)
        if ENABLE_GROUP_RANDOM_BET and len(bets) < PREDICT_BET_COUNT:
            bets.append(build_group_random_bet(window_rows, target_idx))

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

    print("====== A1_2_v3 3獎分區組合權重 + index 記憶回測 ======")
    print(
        f"窗口：{BACKTEST_WINDOW} 期，每期：{PREDICT_BET_COUNT} 注，"
        f"前 3 注投注號碼數：{PREDICT_NUM_COUNT_PATTERN}"
    )
    if ENABLE_GROUP_RANDOM_BET:
        print(
            f"第 {GROUP_RANDOM_BET_INDEX} 注："
            f"{NUMBER_GROUPS} 每區隨機 {GROUP_RANDOM_PICK_COUNT} 球，合共 6 球"
        )
    print(
        f"號碼範圍：{BIRTHDAY_NUM_MIN}-{BIRTHDAY_NUM_MAX}，"
        f"分區：{NUMBER_GROUPS}，組合：{COMBINATION_TAKE_COUNTS}，"
        f"權重參考 prize{PRIZE_OPTION} 注數"
    )
    if USE_COMBO_INDEX_MEMORY:
        print(
            f"index記憶：最近 {MEMORY_WINDOW} 期，"
            f"群距 {MEMORY_CLUSTER_GAP}，最少 {MEMORY_CLUSTER_MIN_SIZE} 個 index 成群，"
            f"加權 x{COMBO_INDEX_MEMORY_WEIGHT:g}"
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

    single_hit_3_count = sum(1 for result in results if len(result.hit_nums) >= 3)
    single_hit_3_rate = single_hit_3_count / len(results) * 100
    draw_hit_3_count = sum(
        1
        for draw_results in grouped.values()
        if any(len(result.hit_nums) >= 3 for result in draw_results)
    )
    draw_hit_3_rate = draw_hit_3_count / len(grouped) * 100
    print()
    print(
        f"重點指標 >=3 正號：單注 {single_hit_3_count} 注，{single_hit_3_rate:.2f}% / "
        f"每期 {draw_hit_3_count} 期，{draw_hit_3_rate:.2f}%"
    )


def print_recent_hit_detail(results: list[BetResult]) -> None:
    """打印最近期數中，每期全部預測注及命中球數。"""

    grouped = group_results_by_date(results)
    recent_dates = list(grouped.keys())[-SHOW_RECENT_DETAIL_COUNT:]

    print()
    print(f"====== 最近 {len(recent_dates)} 期，預測 4/5/6 球注核對明細 ======")
    for idx, draw_date in enumerate(recent_dates):
        draw_order = len(recent_dates) - idx
        draw_results = grouped[draw_date]
        draw_nums_text = format_nums(draw_results[0].draw_nums) if draw_results else ""
        print()
        print(f"{draw_order}. 核對下期 {draw_date} ： {draw_nums_text}")
        for result in draw_results:
            hit_text = format_nums(result.hit_nums)
            hit_suffix = f"：{hit_text}" if hit_text else ""
            print(
                f"{result.bet_index:>2}， {format_nums(result.bet_nums)} "
                f"中/> {len(result.hit_nums)} 球{hit_suffix}"
            )

    print()
    print(f"====== 最近 {len(recent_dates)} 期命中率統計 ======")
    print("每期命中率：")
    for threshold in [3, 4, 5]:
        draw_hit_count = sum(
            1
            for draw_date in recent_dates
            if any(len(result.hit_nums) >= threshold for result in grouped[draw_date])
        )
        rate = draw_hit_count / len(recent_dates) * 100 if recent_dates else 0
        print(f"至少 1 注命中 >= {threshold} 個正號：{draw_hit_count} 期，{rate:.2f}%")


def print_last_window_top_combos(
    rows: list[DrawRow],
    combo_index_memory: dict[str, dict[str, object]],
) -> None:
    """打印最後一期預測窗口的熱門/冷門組合排名，方便觀察權重來源。"""

    if not SHOW_TOP_COMBOS or len(rows) <= BACKTEST_WINDOW:
        return

    window_rows = rows[-BACKTEST_WINDOW:]
    combo_stats = build_combo_stats(window_rows, combo_index_memory)
    hot_stats, cold_stats = split_combo_pools(combo_stats)

    print()
    print(
        f"====== 最後 {BACKTEST_WINDOW} 期熱門組合 Top {TOP_COMBO_PRINT_COUNT}，"
        "組合球該期資訊 ======"
    )
    for idx, stat in enumerate(hot_stats[:TOP_COMBO_PRINT_COUNT], start=1):
        print(
            f"{idx:>2}. {stat.group_label} {format_nums(stat.combo)} /> "
            f"index {stat.combo_index} / 分數 {stat.score:.2f} / 出次數 {stat.hit_count} / "
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
            f"index {stat.combo_index} / 分數 {stat.score:.2f} / 出次數 {stat.hit_count} / "
            f"中{PRIZE_OPTION}獎 {stat.prize_sum:g} 注"
        )


def print_combo_index_memory(memory: dict[str, dict[str, object]]) -> None:
    """打印目前 JSON 記憶中的組合 index 偏好區段。"""

    if not USE_COMBO_INDEX_MEMORY:
        return

    print()
    print(f"====== 組合 index 記憶偏好區段，最近 {MEMORY_WINDOW} 期 ======")
    for key in sorted(memory):
        item = memory[key]
        ranges = normalize_memory_ranges(item.get("preferred_ranges", []))
        total_combos = item.get("total_combos", 0)
        hit_indexes = item.get("hit_indexes", {})
        hit_count = len(hit_indexes) if isinstance(hit_indexes, dict) else 0
        range_text = ", ".join(f"{start}-{end}" for start, end in ranges) if ranges else "沒有成群"
        print(f"{key} / 共 {total_combos} 組 / 命中index {hit_count} 個 / 偏好區段：{range_text}")


def build_merged_rgb_groups(bets: list[tuple[int, ...]]) -> tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]:
    """將 1-4 注合併後按球位分成 R/B/G：R=1,2 位；B=3,4 位；G=5,6 位。"""

    r_nums: set[int] = set()
    b_nums: set[int] = set()
    g_nums: set[int] = set()
    for bet_nums in bets:
        r_nums.update(bet_nums[0:2])
        b_nums.update(bet_nums[2:4])
        g_nums.update(bet_nums[4:6])
    return tuple(sorted(r_nums)), tuple(sorted(b_nums)), tuple(sorted(g_nums))


def build_next_draw_prediction(
    rows: list[DrawRow],
    combo_index_memory: dict[str, dict[str, object]],
) -> list[tuple[int, ...]]:
    """用最新窗口資料產生下期未開獎的 1-4 注預測。"""

    window_rows = rows[-BACKTEST_WINDOW:]
    combo_stats = build_combo_stats(window_rows, combo_index_memory)
    bets = generate_prediction_bets(combo_stats)
    if ENABLE_GROUP_RANDOM_BET and len(bets) < PREDICT_BET_COUNT:
        bets.append(build_group_random_bet(window_rows, len(rows)))
    return bets[:PREDICT_BET_COUNT]


def print_next_draw_prediction(
    rows: list[DrawRow],
    combo_index_memory: dict[str, dict[str, object]],
) -> None:
    """打印下期未開獎預測及 R/B/G 分組。"""

    if len(rows) < BACKTEST_WINDOW:
        return

    bets = build_next_draw_prediction(rows, combo_index_memory)
    print()
    print("====== 下期組合號預測 ======")
    for idx, bet_nums in enumerate(bets, start=1):
        print(f"{idx:>2}， {format_nums(bet_nums)}")

    print()
    print("====== 下期組合號 R/B/G 分組 ======")
    print("1-4 注合併：R=每注第 1,2 球 / B=每注第 3,4 球 / G=每注第 5,6 球")
    r_nums, b_nums, g_nums = build_merged_rgb_groups(bets)
    print(f"R：{format_nums(r_nums)}")
    print(f"B：{format_nums(b_nums)}")
    print(f"G：{format_nums(g_nums)}")


def main() -> None:
    """主程式入口：驗證參數、讀取資料、執行回測、打印結果。"""

    validate_params()
    rows = read_m6_lotto_history()
    loaded_memory = load_combo_index_memory()
    results = run_backtest(rows, loaded_memory)
    updated_memory = update_combo_index_memory(rows)
    print_summary(results)
    print_recent_hit_detail(results)
    print_last_window_top_combos(rows, updated_memory)
    print_combo_index_memory(updated_memory)
    print_next_draw_prediction(rows, updated_memory)


if __name__ == "__main__":
    main()
