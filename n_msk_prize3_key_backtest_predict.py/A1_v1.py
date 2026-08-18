from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import csv
import itertools

'''

====== 3獎組合權重回測：窗口 30 期，每期產生 10 注，每注 4-6 號 ======
號碼範圍：1-31，組合：[2, 3]，權重參考 prize3 注數
回測期數：2557，總模擬注數：25570
命中 4 個正號：1 注，0.00%
命中 3 個正號：151 注，0.59%
命中 2 個正號：1855 注，7.25%
命中 1 個正號：9213 注，36.03%
命中 0 個正號：14350 注，56.12%
命中 >= 3 個正號：152 注
命中 >= 4 個正號：1 注

====== 最近 10 期，命中 >= 3 個正號明細 ======
'''


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
M6_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"

BACKTEST_WINDOW = 30  # 回測窗口期數：每次只用目標期之前最近多少期做分析
PREDICT_BET_COUNT = 10  # 每一期產生多少注模擬投注
PREDICT_NUM_COUNT_MIN = 4  # 每注最少產生幾個號碼
PREDICT_NUM_COUNT_MAX = 6  # 每注最多產生幾個號碼
BIRTHDAY_NUM_MIN = 1  # 分析號碼範圍最小值，例如 1、10、20
BIRTHDAY_NUM_MAX = 31  # 分析號碼範圍最大值，例如 9、19、31
COMBINATION_TAKE_COUNTS = [2, 3]  # 組合權重使用幾多個號碼一組，例如 [2]、[3]、[2, 3]
PRIZE_OPTION = 3  # 權重參考獎項注數，可選 1、2、3；3 即 prize3 注數

SHOW_RECENT_DETAIL_COUNT = 10  # 最後顯示最近多少期的命中明細
MIN_PRINT_HIT_COUNT = 3  # 命中明細只顯示中幾個正號或以上的投注


@dataclass(frozen=True)
class DrawRow:
    date: str
    nums: tuple[int, ...]
    prize_count: float


@dataclass
class ComboStat:
    combo: tuple[int, ...]
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


def validate_params() -> None:
    """檢查所有手動參數是否合理，避免回測前輸入錯誤設定。"""

    if BACKTEST_WINDOW < 1:
        raise ValueError("BACKTEST_WINDOW 必須大於 0")
    if PREDICT_BET_COUNT < 1:
        raise ValueError("PREDICT_BET_COUNT 必須大於 0")
    if PREDICT_NUM_COUNT_MIN < 1 or PREDICT_NUM_COUNT_MAX < PREDICT_NUM_COUNT_MIN:
        raise ValueError("PREDICT_NUM_COUNT_MIN / MAX 設定不正確")
    if BIRTHDAY_NUM_MIN < 1 or BIRTHDAY_NUM_MAX > 49 or BIRTHDAY_NUM_MIN > BIRTHDAY_NUM_MAX:
        raise ValueError("BIRTHDAY_NUM_MIN / MAX 必須介乎 1 至 49，且最小不可大於最大")
    available_count = BIRTHDAY_NUM_MAX - BIRTHDAY_NUM_MIN + 1
    if PREDICT_NUM_COUNT_MAX > available_count:
        raise ValueError(f"PREDICT_NUM_COUNT_MAX 不可大於查詢範圍號碼數量 {available_count}")
    for take_count in COMBINATION_TAKE_COUNTS:
        if take_count < 1 or take_count > available_count:
            raise ValueError(f"COMBINATION_TAKE_COUNTS 內的 {take_count} 不可使用")
    if PRIZE_OPTION not in {1, 2, 3}:
        raise ValueError("PRIZE_OPTION 只可選 1、2、3")


def build_combo_stats(window_rows: list[DrawRow]) -> list[ComboStat]:
    """用回測窗口內資料建立 2號/3號組合權重排名。"""

    stats: dict[tuple[int, ...], ComboStat] = {}
    window_size = max(len(window_rows), 1)

    for step, row in enumerate(window_rows, start=1):
        nums = selected_birthday_nums(row.nums)
        recency_weight = step / window_size
        prize_weight = row.prize_count / 100.0

        for take_count in COMBINATION_TAKE_COUNTS:
            if len(nums) < take_count:
                continue
            for combo in itertools.combinations(nums, take_count):
                stat = stats.setdefault(combo, ComboStat(combo=combo))
                stat.hit_count += 1
                stat.prize_sum += row.prize_count
                stat.last_seen_step = step
                stat.score += 1.0 + prize_weight + recency_weight

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


def build_number_scores(combo_stats: list[ComboStat]) -> dict[int, float]:
    """將組合權重拆回單號分數，用作補足每注號碼及排序。"""

    number_scores: dict[int, float] = defaultdict(float)
    for stat in combo_stats:
        for num in stat.combo:
            number_scores[num] += stat.score
    return dict(number_scores)


def normalize_bet_nums(nums: set[int], number_scores: dict[int, float]) -> tuple[int, ...]:
    """整理單注號碼；如超出最多號碼數，保留分數較高的號碼。"""

    if len(nums) > PREDICT_NUM_COUNT_MAX:
        nums = set(
            sorted(
                nums,
                key=lambda num: (number_scores.get(num, 0.0), -num),
                reverse=True,
            )[:PREDICT_NUM_COUNT_MAX]
        )
    return tuple(sorted(nums))


def generate_prediction_bets(combo_stats: list[ComboStat]) -> list[tuple[int, ...]]:
    """根據組合權重產生每期模擬投注號碼。"""

    number_scores = build_number_scores(combo_stats)
    fallback_nums = [
        num
        for num, _score in sorted(
            number_scores.items(),
            key=lambda item: (item[1], -item[0]),
            reverse=True,
        )
    ]

    bets: list[tuple[int, ...]] = []
    seen: set[tuple[int, ...]] = set()

    for start_idx, stat in enumerate(combo_stats):
        nums = set(stat.combo)
        for next_stat in combo_stats[start_idx + 1 :]:
            nums.update(next_stat.combo)
            if len(nums) >= PREDICT_NUM_COUNT_MIN:
                break

        for num in fallback_nums:
            if len(nums) >= PREDICT_NUM_COUNT_MIN:
                break
            nums.add(num)

        bet_nums = normalize_bet_nums(nums, number_scores)
        if len(bet_nums) < PREDICT_NUM_COUNT_MIN or bet_nums in seen:
            continue

        seen.add(bet_nums)
        bets.append(bet_nums)
        if len(bets) >= PREDICT_BET_COUNT:
            break

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


def format_nums(nums: tuple[int, ...]) -> str:
    """將號碼 tuple 轉成逗號分隔文字，方便打印。"""

    return ",".join(str(num) for num in nums)


def print_summary(results: list[BetResult]) -> None:
    """打印整體回測命中率統計。"""

    print(
        f"====== 3獎組合權重回測：窗口 {BACKTEST_WINDOW} 期，"
        f"每期產生 {PREDICT_BET_COUNT} 注，"
        f"每注 {PREDICT_NUM_COUNT_MIN}-{PREDICT_NUM_COUNT_MAX} 號 ======"
    )
    print(
        f"號碼範圍：{BIRTHDAY_NUM_MIN}-{BIRTHDAY_NUM_MAX}，"
        f"組合：{COMBINATION_TAKE_COUNTS}，權重參考 prize{PRIZE_OPTION} 注數"
    )

    if not results:
        print("沒有可回測資料。")
        return

    draw_count = len({result.draw_date for result in results})
    print(f"回測期數：{draw_count}，總模擬注數：{len(results)}")

    for hit_count in range(PREDICT_NUM_COUNT_MAX, -1, -1):
        count = sum(1 for result in results if len(result.hit_nums) == hit_count)
        if count > 0:
            rate = count / len(results) * 100
            print(f"命中 {hit_count} 個正號：{count} 注，{rate:.2f}%")

    at_least_3 = sum(1 for result in results if len(result.hit_nums) >= 3)
    at_least_4 = sum(1 for result in results if len(result.hit_nums) >= 4)
    print(f"命中 >= 3 個正號：{at_least_3} 注")
    print(f"命中 >= 4 個正號：{at_least_4} 注")


def print_recent_hit_detail(results: list[BetResult]) -> None:
    """打印最近期數中，命中達標的投注明細。"""

    hit_results = [result for result in results if len(result.hit_nums) >= MIN_PRINT_HIT_COUNT]
    if not hit_results:
        print()
        print(f"沒有命中 >= {MIN_PRINT_HIT_COUNT} 個正號的注。")
        return

    recent_dates = list(dict.fromkeys(result.draw_date for result in reversed(results)))
    recent_dates = list(reversed(recent_dates[:SHOW_RECENT_DETAIL_COUNT]))
    recent_hit_results = [result for result in hit_results if result.draw_date in recent_dates]

    print()
    print(
        f"====== 最近 {len(recent_dates)} 期，"
        f"命中 >= {MIN_PRINT_HIT_COUNT} 個正號明細 ======"
    )
    if not recent_hit_results:
        print("最近明細沒有符合條件的注。")
        return

    for result in recent_hit_results:
        print(
            f"{result.draw_date} 第{result.bet_index:>2}注 : "
            f"{format_nums(result.bet_nums)} /> "
            f"開獎 {format_nums(result.draw_nums)} /> "
            f"中 {len(result.hit_nums)} 個：{format_nums(result.hit_nums)}"
        )


def main() -> None:
    """主程式入口：驗證參數、讀取資料、執行回測、打印結果。"""

    validate_params()
    rows = read_m6_lotto_history()
    results = run_backtest(rows)
    print_summary(results)
    print_recent_hit_detail(results)


if __name__ == "__main__":
    main()

'''
====== 最近 24 期，N1-N6 包含 1-31 號數量 == 4，顯示 prize3 注數 ======
序號 日期 : 1-31開獎號 /> 注數
  1 2026-07-02 : 5,17,26,31 /> 58.5
  2 2026-07-09 : 1,7,18,21 /> 85.5
  3 2026-07-11 : 2,5,7,11 /> 65
  4 2026-07-16 : 18,21,26,30 /> 50
  5 2026-07-23 : 4,7,15,29 /> 57
  6 2026-08-01 : 1,7,16,22 /> 53
  7 2026-08-06 : 13,24,29,30 /> 84.5
  8 2026-08-08 : 1,3,7,31 /> 115.5

====== 1-31 選 3 組合核對統計，共 4495 組 ======
  33. 1,3,7, -----> 1
  57. 1,3,31, -----> 1
 144. 1,7,16, -----> 1
 146. 1,7,18, -----> 1
 149. 1,7,21, -----> 1
 150. 1,7,22, -----> 1
 159. 1,7,31, -----> 1
 321. 1,16,22, -----> 1
 347. 1,18,21, -----> 1
'''
