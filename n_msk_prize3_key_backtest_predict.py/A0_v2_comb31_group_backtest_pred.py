from pathlib import Path
import csv
import itertools
from typing import TypedDict

"""
A0_v2 簡單版：
1. 讀入 M6_lotto_history_prize.csv。
2. 用回測期數 + 窗口期數取樣。
3. 查詢 N1-N6 在指定生日號範圍內，符合 >= 或 == 幾個號碼。
4. 只打印結果，不輸出 CSV。
"""


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
M6_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"

# ---- 重點參數
BACKTEST_DRAW_COUNT = 3  # 回測核對最近多少期，例如 10 = 用最近 10 期核對
WINDOW_DRAW_COUNT = 24  # 每次回測前，向前取多少期作窗口樣本統計
COMBINATION_TAKE_COUNT = 2  # 查詢開獎號符合範圍的號碼數量，例如 3
BIRTHDAY_NUM_MATCH_MODE = "=="  # 可選：">=" 或 "=="

# ---- 顯示核對參數
SHOW_BACKTEST_CHECK = True  # 可選：True 顯示每期回測核對明細；False 不顯示回測核對
# 生日號分組：
# 1 = 1-9
# 2 = 10-20
# 3 = 21-31
# 12 = 1-20
# 123 = 1-31
'''
PRINT_GROUP_OPTIONS = [1]
PRINT_GROUP_OPTIONS = [2]
PRINT_GROUP_OPTIONS = [3]
PRINT_GROUP_OPTIONS = [1, 2, 3]
'''
# 1-9，10-20，21-31 組合同時或分組特別參數顯示
PRINT_GROUP_OPTIONS = [1,2,3]  # 一次打印多組，例如 [1, 2, 3]；如只想單組，可改成 [1]
TOP_PRIZE_DRAW_COUNT = 7  # 每個分組只顯示中獎注數最多前多少期
LOW_PRIZE_DRAW_COUNT = 0  # 每個分組額外顯示中獎注數最少前多少期，不列入合併統計

# ------回測熱門組合參數
HOT_PAIR_COUNT = 2  # 每個分組試算：顯示幾組 2 球熱門組合
FALLBACK_PAIR_MIN_COUNT = 2  # 沒有重複 2 球組合時，最少產生幾組候選 2 球
FALLBACK_PAIR_MAX_COUNT = 3  # 沒有重複 2 球組合時，最多產生幾組候選 2 球
SECOND_CANDIDATE_NUM_COUNT = 3  # 次候選球只取幾個號碼

# -----其他參數顯示中獎項及 排序模式
PRIZE_OPTION = 3  # 可選：1、2、3；顯示 prize1 / prize2 / prize3 注數
SORT_MODE = "prize"  # 可選："prize" 中獎注多排上；"date" 日期遠在上、近在後


BIRTHDAY_GROUPS: dict[int, tuple[int, int]] = {
    1: (1, 9),
    2: (10, 20),
    3: (21, 31),
    12: (1, 20),
    123: (1, 31),
}


class DrawRow(TypedDict):
    date: str
    nums: list[int]
    selected_nums: list[int]
    prize_count: float


class PairCandidate(TypedDict):
    label: str
    pairs: list[tuple[int, int]]
    second_nums: list[int]
    predict_nums: list[int]


def birthday_range(group_option: int) -> tuple[int, int]:
    """按參數取得生日號查詢範圍。"""

    if group_option not in BIRTHDAY_GROUPS:
        raise ValueError("PRINT_GROUP_OPTIONS 只可選 1、2、3、12、123")
    return BIRTHDAY_GROUPS[group_option]


def validate_params() -> None:
    """檢查回測、窗口、查詢模式及獎項參數。"""

    if BACKTEST_DRAW_COUNT < 1:
        raise ValueError("BACKTEST_DRAW_COUNT 必須大於 0")
    if WINDOW_DRAW_COUNT < 1:
        raise ValueError("WINDOW_DRAW_COUNT 必須大於 0")
    if COMBINATION_TAKE_COUNT < 1:
        raise ValueError("COMBINATION_TAKE_COUNT 必須大於 0")
    if BIRTHDAY_NUM_MATCH_MODE not in {">=", "=="}:
        raise ValueError('BIRTHDAY_NUM_MATCH_MODE 只可選 ">=" 或 "=="')
    if PRIZE_OPTION not in {1, 2, 3}:
        raise ValueError("PRIZE_OPTION 只可選 1、2、3")
    if SORT_MODE not in {"prize", "date"}:
        raise ValueError('SORT_MODE 只可選 "prize" 或 "date"')
    for group_option in PRINT_GROUP_OPTIONS:
        birthday_range(group_option)


def read_m6_rows(csv_path: Path = M6_CSV) -> list[dict[str, str]]:
    """讀入 M6 歷史開獎資料。"""

    if not csv_path.exists():
        raise FileNotFoundError(f"找不到 M6 CSV：{csv_path}")

    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames:
            reader.fieldnames = [name.strip().lstrip("\ufeff") for name in reader.fieldnames]
        return [
            {(key or "").strip().lstrip("\ufeff"): (value or "").strip() for key, value in row.items()}
            for row in reader
        ]


def parse_nums(row: dict[str, str]) -> list[int]:
    """抽取 N1-N6 正號。"""

    nums: list[int] = []
    for idx in range(1, 7):
        try:
            nums.append(int(row.get(f"N{idx}", "0")))
        except ValueError:
            nums.append(0)
    return nums


def parse_prize_count(row: dict[str, str]) -> float:
    """抽取指定獎項的中獎注數。"""

    try:
        return float(row.get(f"prize{PRIZE_OPTION}", "0") or 0)
    except ValueError:
        return 0.0


def selected_nums(nums: list[int], group_option: int) -> list[int]:
    """只保留生日號範圍內的開獎號。"""

    start_num, end_num = birthday_range(group_option)
    return sorted(num for num in nums if start_num <= num <= end_num)


def is_matched(count: int) -> bool:
    """判斷符合號碼數量是否達到查詢條件。"""

    if BIRTHDAY_NUM_MATCH_MODE == "==":
        return count == COMBINATION_TAKE_COUNT
    return count >= COMBINATION_TAKE_COUNT


def window_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """回測模式：窗口期不包含最後 BACKTEST_DRAW_COUNT 期。"""

    target_index = latest_backtest_target_index(rows)
    if target_index is None:
        return []
    return get_window_rows_for_target(rows, target_index)


def latest_backtest_target_index(rows: list[dict[str, str]]) -> int | None:
    """取得最近第 1 期回測核對位置，即 M6 最後一期。"""

    if not rows:
        return None
    return len(rows) - 1


def build_matched_rows(
    rows: list[dict[str, str]],
    group_option: int,
    target_index: int | None = None,
) -> list[DrawRow]:
    """建立符合條件的打印資料。"""

    matched_rows: list[DrawRow] = []
    source_rows = get_window_rows_for_target(rows, target_index) if target_index is not None else window_rows(rows)
    for row in source_rows:
        nums = parse_nums(row)
        selected = selected_nums(nums, group_option)
        if not is_matched(len(selected)):
            continue
        matched_rows.append(
            {
                "date": row.get("nDdate", ""),
                "nums": nums,
                "selected_nums": selected,
                "prize_count": parse_prize_count(row),
            }
        )

    if SORT_MODE == "prize":
        return sorted(matched_rows, key=lambda item: (-item["prize_count"], item["date"]))
    return sorted(matched_rows, key=lambda item: item["date"])


def get_window_rows_for_target(rows: list[dict[str, str]], target_index: int) -> list[dict[str, str]]:
    """取得指定回測目標期之前的窗口期，不包含目標期本身。"""

    window_start = max(0, target_index - WINDOW_DRAW_COUNT)
    return rows[window_start:target_index]


def format_prize(value: float) -> str:
    """格式化注數，整數不顯示 .0。"""

    return f"{value:g}"


def print_result(rows: list[DrawRow], group_option: int, target_date: str, backtest_rank: int) -> None:
    """打印查詢結果。"""

    start_num, end_num = birthday_range(group_option)
    print(f"回測最近第 {backtest_rank} 期，日期 {target_date} : {start_num}-{end_num}開獎號 /> 注數")

    if not rows:
        print("沒有符合條件的期數。")
        return

    high_rows = rows[:TOP_PRIZE_DRAW_COUNT]
    for idx, row in enumerate(high_rows, start=1):
        nums_text = ",".join(str(num) for num in row["selected_nums"])
        print(f"{idx:>3} {row['date']} : {nums_text} /> {format_prize(row['prize_count'])}")

    low_rows = sorted(rows, key=lambda item: (item["prize_count"], item["date"]))[:LOW_PRIZE_DRAW_COUNT]
    if not low_rows:
        return

    print(f"最少注數前 {LOW_PRIZE_DRAW_COUNT} 期：")
    for idx, row in enumerate(low_rows, start=1):
        nums_text = ",".join(str(num) for num in row["selected_nums"])
        print(f"{idx:>3} {row['date']} : {nums_text} /> {format_prize(row['prize_count'])}")

    print_hot_pair_candidates(high_rows + low_rows)


def print_hot_pair_candidates(rows: list[DrawRow]) -> None:
    """用已顯示期數試算 2 球熱門組合及次候選球。"""

    candidate = build_pair_candidate(rows)
    pair_text = ", ".join(f"[{pair[0]},{pair[1]}]" for pair in candidate["pairs"])
    second_text = ",".join(str(num) for num in candidate["second_nums"]) if candidate["second_nums"] else "-"
    print(f"{candidate['label']}：{pair_text} + [{second_text}]")


def build_pair_candidate(rows: list[DrawRow]) -> PairCandidate:
    """用已顯示期數計算 2 球熱門/候選組合及次候選球。"""

    pair_counts: dict[tuple[int, int], int] = {}
    num_counts: dict[int, int] = {}
    all_nums: set[int] = set()
    for row in rows:
        nums = sorted(set(row["selected_nums"]))
        all_nums.update(nums)
        for num in nums:
            num_counts[num] = num_counts.get(num, 0) + 1
        for pair in itertools.combinations(nums, 2):
            pair_counts[pair] = pair_counts.get(pair, 0) + 1

    if not pair_counts:
        return {"label": "2球熱門組合", "pairs": [], "second_nums": [], "predict_nums": []}

    repeated_pairs = [(pair, count) for pair, count in pair_counts.items() if count >= 2]
    if repeated_pairs:
        hot_pairs = sorted(repeated_pairs, key=lambda item: (-item[1], item[0]))[:HOT_PAIR_COUNT]
        label = "2球熱門組合"
    else:
        hot_pairs = build_fallback_pairs(num_counts)
        label = "2球候選組合"

    hot_pair_nums = {num for pair, _ in hot_pairs for num in pair}
    second_nums = sorted(all_nums - hot_pair_nums)[:SECOND_CANDIDATE_NUM_COUNT]
    pairs = [pair for pair, _ in hot_pairs]
    predict_nums = sorted(hot_pair_nums | set(second_nums))
    return {
        "label": label,
        "pairs": pairs,
        "second_nums": second_nums,
        "predict_nums": predict_nums,
    }


def build_fallback_pairs(num_counts: dict[int, int]) -> list[tuple[tuple[int, int], int]]:
    """沒有重複 pair 時，用單號累計次數產生 2 球候選組合。"""

    sorted_nums = sorted(num_counts.items(), key=lambda item: (-item[1], item[0]))
    candidate_nums = [num for num, _ in sorted_nums]
    pair_scores: list[tuple[tuple[int, int], int]] = []
    for raw_pair in itertools.combinations(candidate_nums, 2):
        num_a, num_b = sorted(raw_pair)
        pair = (num_a, num_b)
        score = num_counts[pair[0]] + num_counts[pair[1]]
        pair_scores.append((pair, score))

    pair_scores = sorted(pair_scores, key=lambda item: (-item[1], item[0]))
    pair_count = min(FALLBACK_PAIR_MAX_COUNT, len(pair_scores))
    pair_count = max(min(FALLBACK_PAIR_MIN_COUNT, len(pair_scores)), pair_count)
    return pair_scores[:pair_count]


def unique_nums_from_rows(rows: list[DrawRow]) -> list[int]:
    """合併每組注數最高期數內的唯一號碼。"""

    nums: set[int] = set()
    for row in rows[:TOP_PRIZE_DRAW_COUNT]:
        nums.update(row["selected_nums"])
    return sorted(nums)


def print_group_summary(group_results: dict[int, list[DrawRow]]) -> None:
    """打印每個分組的唯一號碼統計。"""

    print()
    print(f"====== 分組注數最多前 {TOP_PRIZE_DRAW_COUNT} 期，合併唯一統計 ======")
    for group_option in PRINT_GROUP_OPTIONS:
        start_num, end_num = birthday_range(group_option)
        nums = unique_nums_from_rows(group_results[group_option])
        nums_text = ",".join(str(num) for num in nums) if nums else "-"
        print(f"{start_num}-{end_num} : {nums_text} /> {len(nums)} 球")


def print_rbg_summary(group_results: dict[int, list[DrawRow]]) -> None:
    """按 R/B/G 顯示三個分組的合併唯一號碼。"""

    if PRINT_GROUP_OPTIONS != [1, 2, 3]:
        return

    r_nums = unique_nums_from_rows(group_results[1])
    b_nums = unique_nums_from_rows(group_results[2])
    g_nums = unique_nums_from_rows(group_results[3])
    total_nums = sorted(set(r_nums) | set(b_nums) | set(g_nums))

    print()
    print(f"====== prize{PRIZE_OPTION} 分組注數最多前 {TOP_PRIZE_DRAW_COUNT} 期 RBG 統計 ======")
    print(f"R: {','.join(str(num) for num in r_nums) if r_nums else '-'} /> {len(r_nums)} 球")
    print(f"B: {','.join(str(num) for num in b_nums) if b_nums else '-'} /> {len(b_nums)} 球")
    print(f"G: {','.join(str(num) for num in g_nums) if g_nums else '-'} /> {len(g_nums)} 球")
    print(f"總計: {','.join(str(num) for num in total_nums) if total_nums else '-'} /> {len(total_nums)} 球")


def print_backtest_predictions(rows: list[dict[str, str]]) -> None:
    """最近 BACKTEST_DRAW_COUNT 期逐期回測，核對三個分組預測命中。"""

    if len(rows) <= WINDOW_DRAW_COUNT:
        print()
        print("回測資料不足。")
        return

    first_target_index = max(WINDOW_DRAW_COUNT, len(rows) - BACKTEST_DRAW_COUNT)
    print()
    print(
        f"====== 最近 {len(rows) - first_target_index} 期回測核對，"
        f"每期用前 {WINDOW_DRAW_COUNT} 期窗口，不含核對期 ======"
    )
    for display_index, target_index in enumerate(range(first_target_index, len(rows)), start=1):
        target_row = rows[target_index]
        target_date = target_row.get("nDdate", "")
        target_nums = parse_nums(target_row)
        print()
        print(f"{display_index}. 核對期 {target_date} ：{','.join(str(num) for num in sorted(target_nums))}")
        for group_option in PRINT_GROUP_OPTIONS:
            matched_rows = build_matched_rows(rows, group_option, target_index=target_index)
            high_rows = matched_rows[:TOP_PRIZE_DRAW_COUNT]
            low_rows = sorted(matched_rows, key=lambda item: (item["prize_count"], item["date"]))[:LOW_PRIZE_DRAW_COUNT]
            candidate = build_pair_candidate(high_rows + low_rows)
            hit_nums = sorted(set(candidate["predict_nums"]) & set(selected_nums(target_nums, group_option)))
            print_backtest_group_line(group_option, candidate, hit_nums)


def print_backtest_window_details(rows: list[dict[str, str]]) -> None:
    """最近 BACKTEST_DRAW_COUNT 期逐期打印完整窗口分析明細。"""

    if len(rows) <= WINDOW_DRAW_COUNT:
        print()
        print("回測資料不足。")
        return

    first_target_index = max(WINDOW_DRAW_COUNT, len(rows) - BACKTEST_DRAW_COUNT)
    target_indices = list(range(first_target_index, len(rows)))
    print(
        f"====== 最近 {len(target_indices)} 期回測窗口明細，"
        f"每期用前 {WINDOW_DRAW_COUNT} 期窗口，不含核對期 ======"
    )

    total_targets = len(target_indices)
    for display_index, target_index in enumerate(target_indices, start=1):
        backtest_rank = total_targets - display_index + 1
        if display_index > 1:
            print()
        print_one_backtest_window_detail(rows, target_index, backtest_rank)


def print_one_backtest_window_detail(
    rows: list[dict[str, str]],
    target_index: int,
    backtest_rank: int,
) -> None:
    """打印單一期回測的窗口分析明細。"""

    target_date = rows[target_index].get("nDdate", "")
    group_results: dict[int, list[DrawRow]] = {}
    for display_index, group_option in enumerate(PRINT_GROUP_OPTIONS):
        if display_index:
            print()
        matched_rows = build_matched_rows(rows, group_option, target_index=target_index)
        group_results[group_option] = matched_rows
        print_result(matched_rows, group_option, target_date, backtest_rank)

    print_group_summary(group_results)
    print_rbg_summary(group_results)


def print_backtest_group_line(
    group_option: int,
    candidate: PairCandidate,
    hit_nums: list[int],
) -> None:
    """打印單個分組的回測核對結果。"""

    start_num, end_num = birthday_range(group_option)
    pair_text = ", ".join(f"[{pair[0]},{pair[1]}]" for pair in candidate["pairs"]) or "-"
    second_text = ",".join(str(num) for num in candidate["second_nums"]) if candidate["second_nums"] else "-"
    hit_text = ",".join(str(num) for num in hit_nums) if hit_nums else "-"
    print(
        f"   {start_num}-{end_num} {candidate['label']}：{pair_text} + [{second_text}] "
        f"命中: {hit_text} /> {len(hit_nums)} 球"
    )


def main() -> None:
    """主程式入口。"""

    validate_params()
    rows = read_m6_rows()
    if SHOW_BACKTEST_CHECK:
        print_backtest_window_details(rows)
        return

    target_index = latest_backtest_target_index(rows)
    target_date = rows[target_index].get("nDdate", "") if target_index is not None else "-"
    group_results: dict[int, list[DrawRow]] = {}
    for display_index, group_option in enumerate(PRINT_GROUP_OPTIONS):
        if display_index:
            print()
        matched_rows = build_matched_rows(rows, group_option, target_index=target_index)
        group_results[group_option] = matched_rows
        print_result(matched_rows, group_option, target_date, 1)

    print_group_summary(group_results)
    print_rbg_summary(group_results)


if __name__ == "__main__":
    main()
    
    
'''

產生組合 1 to 9 取 2 個數字的所有組合: 36
產生組合 10 to 20 取 2 個數字的所有組合: 55
產生組合 21 to 31 取 2 個數字的所有組合: 55

產生組合 1 to 9 取 3 個數字的所有組合: 84
產生組合 10 to 20 取 3 個數字的所有組合: 165
產生組合 21 to 31 取 3 個數字的所有組合: 165

1-9 選 2  = 9C2  = 36
1-9 選 3  = 9C3  = 84

10-20 選 2 = 11C2 = 55
10-20 選 3 = 11C3 = 165

21-31 選 2 = 11C2 = 55
21-31 選 3 = 11C3 = 165

'''
