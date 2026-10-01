from pathlib import Path
import csv
from itertools import combinations
from typing import TypedDict


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
M6_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"


# 只測 1-9 fortune_keys：窗口期內 1-9 正號 >= FORTUNE_MATCH_COUNT 球的開獎期。
BACKTEST_DRAW_COUNT = 10
WINDOW_DRAW_COUNT = 30
FORTUNE_NUM_MIN = 1
FORTUNE_NUM_MAX = 40
FORTUNE_MATCH_COUNT = 5

# 評分權重：先用簡單可調版本，之後可逐步優化公式。
BASE_WEIGHT = 1.0
PZ3_WEIGHT = 1.0
RECENCY_WEIGHT = 1.0

# 是否打印 100 期逐期明細。
PRINT_BACKTEST_DETAIL = False


class DrawRow(TypedDict):
    date: str
    nums: list[int]
    special: int | None
    prize_count: float


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    """讀取 CSV 並清理欄位名稱與文字空白。"""
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
    """安全轉換數值為 int。"""
    if not isinstance(value, (int, float, str)):
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def to_float(value: object, default: float = 0.0) -> float:
    """安全轉換數值為 float。"""
    if not isinstance(value, (int, float, str)):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_m6_row(row: dict[str, str]) -> DrawRow:
    """將 M6 原始 CSV 一行轉成標準 DrawRow。"""
    special = to_int(row.get("N7"))
    return {
        "date": row.get("nDdate", ""),
        "nums": [to_int(row.get(f"N{index}")) for index in range(1, 7)],
        "special": special if 1 <= special <= 49 else None,
        "prize_count": to_float(row.get("prize3")),
    }


def read_draws() -> list[DrawRow]:
    """讀取所有有效歷史開獎紀錄。"""
    return [row for row in [parse_m6_row(raw) for raw in read_csv_rows(M6_CSV)] if row["date"]]


def format_nums(nums: list[int] | tuple[int, ...]) -> str:
    """格式化號碼列表。"""
    return "[" + ",".join(str(num) for num in nums) + "]"


def fortune_nums(row: DrawRow) -> list[int]:
    """取得一期內落在 1-9 的正號 N1..N6。"""
    return sorted(num for num in row["nums"] if FORTUNE_NUM_MIN <= num <= FORTUNE_NUM_MAX)


def is_fortune_key(row: DrawRow) -> bool:
    """判斷是否為 fortune_keys 開獎期。"""
    return len(fortune_nums(row)) >= FORTUNE_MATCH_COUNT


def score_fortune_nums(window_rows: list[DrawRow]) -> dict[int, float]:
    """用單號頻率、Pz3 權重、近期權重，為 1-9 每個球打分。"""
    scores = {num: 0.0 for num in range(FORTUNE_NUM_MIN, FORTUNE_NUM_MAX + 1)}
    fortune_rows = [row for row in window_rows if is_fortune_key(row)]
    max_prize = max((row["prize_count"] for row in fortune_rows), default=0.0)
    window_len = max(1, len(window_rows))

    for row_index, row in enumerate(window_rows, start=1):
        nums = fortune_nums(row)
        if len(nums) < FORTUNE_MATCH_COUNT:
            continue

        prize_score = row["prize_count"] / max_prize if max_prize else 0.0
        recency_score = row_index / window_len
        weight = BASE_WEIGHT + (PZ3_WEIGHT * prize_score) + (RECENCY_WEIGHT * recency_score)
        for num in nums:
            scores[num] += weight

    return scores


def candidate_pool(scores: dict[int, float], pool_size: int) -> list[int]:
    """按分數選出 N 個候選球。"""
    ranked_nums = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return sorted(num for num, _score in ranked_nums[:pool_size])


def top_nums_from(scores: dict[int, float], nums: list[int], take_count: int) -> list[int]:
    """在指定號碼池內按分數取 N 個號。"""
    ranked_nums = sorted(((num, scores.get(num, 0.0)) for num in nums), key=lambda item: (-item[1], item[0]))
    return [num for num, _score in ranked_nums[:take_count]]


def pattern_candidate_pools(scores: dict[int, float]) -> dict[str, list[int]]:
    """產生多種 1-9 結構候選池。"""
    odds = [1, 3, 5, 7, 9]
    evens = [2, 4, 6, 8]
    vertical_147 = [1, 4, 7]
    vertical_258 = [2, 5, 8]
    vertical_369 = [3, 6, 9]
    low_123 = [1, 2, 3]
    mid_456 = [4, 5, 6]
    high_789 = [7, 8, 9]

    return {
        "C9全包": list(range(1, 10)),
        "分數6球": candidate_pool(scores, 6),
        "單號5+雙號2": sorted(odds + top_nums_from(scores, evens, 2)),
        "雙號4+單號2": sorted(evens + top_nums_from(scores, odds, 2)),
        "縱列147+258": sorted(vertical_147 + vertical_258),
        "縱列147+369": sorted(vertical_147 + vertical_369),
        "縱列258+369": sorted(vertical_258 + vertical_369),
        "小中123+456": sorted(low_123 + mid_456),
        "小大123+789": sorted(low_123 + high_789),
        "中大456+789": sorted(mid_456 + high_789),
    }


def candidate_combs(pool: list[int]) -> list[tuple[int, ...]]:
    """由候選球產生 FORTUNE_MATCH_COUNT 球組合。"""
    return list(combinations(pool, FORTUNE_MATCH_COUNT))


def hit_combs(combs: list[tuple[int, ...]], check_row: DrawRow) -> list[tuple[int, ...]]:
    """核對組合是否全中下期 1-9 正號。"""
    check_nums = set(fortune_nums(check_row))
    return [comb for comb in combs if set(comb).issubset(check_nums)]


def candidate_ball_hit_count(pool: list[int], check_row: DrawRow) -> float:
    """用候選球直接核對開獎期；正號 1 球，特號命中 0.5 球。"""
    pool_set = set(pool)
    normal_count = sum(1 for num in check_row["nums"] if num in pool_set)
    special = check_row["special"]
    special_count = 0.5 if special is not None and special in pool_set else 0.0
    return normal_count + special_count


def format_ball_count(value: float) -> str:
    """格式化球數，整數不顯示小數點。"""
    return str(int(value)) if value.is_integer() else f"{value:g}"


def percent(part: int, total: int) -> str:
    """格式化百分比。"""
    if total == 0:
        return "0%"
    return f"{part / total * 100:.1f}%"


def print_query_setting() -> None:
    """打印本次測試設定。"""
    print("====== fortune_keys 1-9 公式回測 ======")
    print(f"回測期：{BACKTEST_DRAW_COUNT}")
    print(f"窗口期：{WINDOW_DRAW_COUNT}")
    print(f"fortune_keys 條件：1-9 正號 >= {FORTUNE_MATCH_COUNT} 球")
    print("測試候選池：C9全包、分數6球、奇偶 pattern、縱列 pattern、大小段 pattern")
    print(f"公式權重：base={BASE_WEIGHT}, pz3={PZ3_WEIGHT}, recency={RECENCY_WEIGHT}")
    print()


def print_real_fortune_keys(window_rows: list[DrawRow]) -> None:
    """打印最後核對日前窗口期內真實 1-9 達到 FORTUNE_MATCH_COUNT 的開獎期。"""
    fortune_rows = [row for row in window_rows if is_fortune_key(row)]
    print(
        f"----- 最後核對日前窗口 {len(window_rows)} 期內，"
        f"真實 1-9 >= {FORTUNE_MATCH_COUNT} 球：{len(fortune_rows)} 期 -----"
    )
    for row in fortune_rows:
        print(f"{row['date']}，1-9實開{format_nums(fortune_nums(row))}，Pz3: {row['prize_count']:g}")
    print()


def print_check_fortune_keys(check_rows: list[DrawRow]) -> None:
    """打印 100 個核對期內真實 1-9 達到 FORTUNE_MATCH_COUNT 的開獎期。"""
    fortune_rows = [row for row in check_rows if is_fortune_key(row)]
    print(
        f"----- 回測 {len(check_rows)} 個核對期內，"
        f"真實 1-9 >= {FORTUNE_MATCH_COUNT} 球：{len(fortune_rows)} 期 -----"
    )
    for row in fortune_rows:
        print(f"{row['date']}，1-9實開{format_nums(fortune_nums(row))}，Pz3: {row['prize_count']:g}")
    print()


def run_backtest(draws: list[DrawRow]) -> None:
    """執行 100 期回測，測試 C(9,N)、C(6,N) 等命中率。"""
    latest_index = len(draws) - 1
    first_check_index = max(WINDOW_DRAW_COUNT, latest_index - BACKTEST_DRAW_COUNT + 1)
    check_indices = list(range(first_check_index, latest_index + 1))
    check_rows = [draws[index] for index in check_indices]
    latest_window_rows = draws[max(0, latest_index - WINDOW_DRAW_COUNT):latest_index]

    pattern_labels = [
        "C9全包",
        "分數6球",
        "單號5+雙號2",
        "雙號4+單號2",
        "縱列147+258",
        "縱列147+369",
        "縱列258+369",
        "小中123+456",
        "小大123+789",
        "中大456+789",
    ]
    stats = {
        label: {
            "check_count": 0,
            "fortune_check_count": 0,
            "hit_count": 0,
            "fortune_hit_count": 0,
            "hit_comb_count": 0,
        }
        for label in pattern_labels
    }
    ball_hit_buckets = [6, 5.5, 5, 4.5, 4, 3.5, 3, 2.5, 2, 1.5, 1, 0.5, 0]
    ball_hit_stats = {bucket: 0 for bucket in ball_hit_buckets}
    detail_rows: list[str] = []

    print_real_fortune_keys(latest_window_rows)
    print_check_fortune_keys(check_rows)

    for check_index in check_indices:
        check_row = draws[check_index]
        window_rows = draws[max(0, check_index - WINDOW_DRAW_COUNT):check_index]
        scores = score_fortune_nums(window_rows)
        check_nums = fortune_nums(check_row)
        check_is_fortune = len(check_nums) >= FORTUNE_MATCH_COUNT
        pools = pattern_candidate_pools(scores)
        score_pool_hit_count = candidate_ball_hit_count(pools["分數6球"], check_row)
        if score_pool_hit_count not in ball_hit_stats:
            ball_hit_stats[score_pool_hit_count] = 0
        ball_hit_stats[score_pool_hit_count] += 1

        detail_parts = []
        candidate_text = f"分數6球{format_nums(pools['分數6球'])}，單號5+雙號2{format_nums(pools['單號5+雙號2'])}，雙號4+單號2{format_nums(pools['雙號4+單號2'])}"
        for label in pattern_labels:
            pool = pools[label]
            combs = candidate_combs(pool)
            hits = hit_combs(combs, check_row)

            stat = stats[label]
            stat["check_count"] += 1
            stat["hit_comb_count"] += len(hits)
            if check_is_fortune:
                stat["fortune_check_count"] += 1
            if hits:
                stat["hit_count"] += 1
                if check_is_fortune:
                    stat["fortune_hit_count"] += 1

            detail_parts.append(f"{label}: C({len(pool)},{FORTUNE_MATCH_COUNT})={len(combs)} 命中{len(hits)}組")

        detail_rows.append(
            f"回測日期：{draws[check_index - 1]['date']}：\n"
            f"核對日期：{check_row['date']}，1-9實開{format_nums(check_nums)}\n"
            f"候選 1-9：{candidate_text}\n"
            + "；".join(detail_parts)
        )

    print("----- 回測命中率 -----")
    for label in pattern_labels:
        stat = stats[label]
        print(
            f"{label}："
            f"全期命中 {stat['hit_count']}/{stat['check_count']} = {percent(stat['hit_count'], stat['check_count'])}，"
            f"fortune期命中 {stat['fortune_hit_count']}/{stat['fortune_check_count']} = {percent(stat['fortune_hit_count'], stat['fortune_check_count'])}，"
            f"命中組合總數：{stat['hit_comb_count']}"
        )

    print()
    print("----- 分數6球，直接核對開獎期命中球數統計 -----")
    for bucket in sorted(ball_hit_stats.keys(), reverse=True):
        print(f"{format_ball_count(float(bucket)):>3} = {ball_hit_stats[bucket]} 期")

    if PRINT_BACKTEST_DETAIL:
        print()
        print("----- 回測逐期明細 -----")
        for detail in detail_rows:
            print(detail)
            print()


def main() -> None:
    """主流程。"""
    draws = read_draws()
    if not draws:
        raise FileNotFoundError(f"找不到或未能讀取 M6：{M6_CSV}")

    print_query_setting()
    run_backtest(draws)


if __name__ == "__main__":
    main()
