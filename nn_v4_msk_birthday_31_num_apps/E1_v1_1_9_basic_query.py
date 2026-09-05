from pathlib import Path
import csv
import itertools
from typing import TypedDict


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
M6_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"
COMB_DATA_DIR = CURRENT_DIR / "comb_data"

# 第一版：生日號最基本查詢參數。
BACKTEST_DRAW_COUNT = 21 # 採樣本期數 ＝ 預測窗口期，同步寫入 CSV backdraw [100]

# 主採樣參數：只影響「查詢結果」及「1-36 雙球組合」統計。
COMBINATION_TAKE_COUNT = 2 # 雙球採樣條件，2=該期 1-9 至少有 2 球才產生雙球組合
BIRTHDAY_NUM_MATCH_MODE = ">="  # 雙球採樣模式，">=" 或 "=="

# 固定統計口徑：不受以上雙球採樣參數影響。
SINGLE_NUM_EXACT_COUNT = 1 # 單號統計固定只記錄該期 1-9 剛好出現 1 球
NONE_NUM_EXACT_COUNT = 0 # none (00) 固定只記錄該期 1-9 完全沒有出現

BIRTHDAY_NUM_MIN = 1  # 分析號碼範圍最小值
BIRTHDAY_NUM_MAX = 9  # 分析號碼範圍最大值

PRIZE_OPTION = 3 # 查詢中獎注數，1=頭獎，2=二獎，3=三獎
SHOW_PRIZE_COUNT = False  # True 顯示中獎注數；False 不顯示中獎注數

# 額外追蹤參數：用回測期每一期 N1..N7 統計 R/B/G 顏色 3+ 出現期數。
RBG_MIN_HIT_COUNT = 3
# [R, R, R, B, B, B, R] ，R, B 都紀錄。
# 冷球號追蹤：只針對目前分析範圍 1-9，N1..N7 包特號，特號作 1 球整數計。
COLD_NUM_WINDOW = 18
DEEP_COLD_NUM_WINDOW = 24


class DrawRow(TypedDict):
    date: str
    nums: list[int]
    special: int | None
    selected_nums: list[int]
    selected_count: int
    hit_score: float
    prize_count: float


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
    special_num = special if 1 <= special <= 49 else None
    selected_nums = [num for num in nums if BIRTHDAY_NUM_MIN <= num <= BIRTHDAY_NUM_MAX]
    selected_count = len(selected_nums)
    if special_num is not None and BIRTHDAY_NUM_MIN <= special_num <= BIRTHDAY_NUM_MAX:
        selected_count += 1
    return {
        "date": row.get("nDdate", ""),
        "nums": nums,
        "special": special_num,
        "selected_nums": sorted(selected_nums),
        "selected_count": selected_count,
        "hit_score": float(selected_count),
        "prize_count": to_float(row.get(f"prize{PRIZE_OPTION}")),
    }


def read_draws() -> list[DrawRow]:
    rows = [parse_draw_row(row) for row in read_csv_rows(M6_CSV)]
    return [row for row in rows if row["date"]]


def is_matched(count: int) -> bool:
    if BIRTHDAY_NUM_MATCH_MODE == "==":
        return count == COMBINATION_TAKE_COUNT
    return count >= COMBINATION_TAKE_COUNT


def birthday_range_nums() -> list[int]:
    return list(range(BIRTHDAY_NUM_MIN, BIRTHDAY_NUM_MAX + 1))


def birthday_range_label() -> str:
    return f"{BIRTHDAY_NUM_MIN}-{BIRTHDAY_NUM_MAX}"


def birthday_range_file_label() -> str:
    return f"{BIRTHDAY_NUM_MIN}_{BIRTHDAY_NUM_MAX}"


def num_comb_csv_path() -> Path:
    return COMB_DATA_DIR / f"E1_num_{birthday_range_file_label()}_comb.csv"


def pair_count() -> int:
    return len(list(itertools.combinations(birthday_range_nums(), 2)))


def all_draw_nums(row: DrawRow) -> list[int]:
    nums = [num for num in row["nums"] if 1 <= num <= 49]
    special = row["special"]
    if special is not None and 1 <= special <= 49:
        nums.append(special)
    return nums


def range_draw_nums(row: DrawRow, start_num: int = BIRTHDAY_NUM_MIN, end_num: int = BIRTHDAY_NUM_MAX) -> set[int]:
    return {num for num in all_draw_nums(row) if start_num <= num <= end_num}


def rbg_num(num: int) -> int:
    # 1=R，2=B，3=G；沿用本專案六合彩 R/B/G 分色公式。
    j_num = num - 1
    return (((j_num // 10) + j_num) % 6 // 2) + 1


def rbg_label(color_id: int) -> str:
    return {1: "R", 2: "B", 3: "G"}[color_id]


def format_nums(nums: list[int]) -> str:
    if not nums:
        return "[]"
    return "[" + ",".join(str(num) for num in nums) + "]"


def format_selected_with_special(row: DrawRow) -> str:
    parts = [str(num) for num in row["selected_nums"]]
    special = row["special"]
    if special is not None and BIRTHDAY_NUM_MIN <= special <= BIRTHDAY_NUM_MAX:
        parts.append(f"-{special}")
    if not parts:
        return "[]"
    return "[" + ",".join(parts) + "]"


def find_cold_nums(draws: list[DrawRow], window_count: int) -> list[int]:
    window_rows = draws[-window_count:]
    appeared_nums: set[int] = set()
    for row in window_rows:
        appeared_nums.update(range_draw_nums(row, BIRTHDAY_NUM_MIN, BIRTHDAY_NUM_MAX))
    return [num for num in range(BIRTHDAY_NUM_MIN, BIRTHDAY_NUM_MAX + 1) if num not in appeared_nums]


def print_settings(total_draw_count: int) -> None:
    print("====== E1_v1 生日號基本查詢版 ======")
    print(f"資料期數：{total_draw_count}")
    print(
        f"查詢參數：最近 {BACKTEST_DRAW_COUNT} 期，"
        f"{birthday_range_label()}，"
        f"N1-N7 {BIRTHDAY_NUM_MATCH_MODE} {COMBINATION_TAKE_COUNT} 球，"
        f"PZ{PRIZE_OPTION}顯示={SHOW_PRIZE_COUNT}"
    )
    print("統計口徑：N1-N7 每球 = 1；N7 特號如在範圍內，用 - 號標示但統計作 1 球。")
    print(f"輸出 CSV：{num_comb_csv_path().name}")
    print(
        f"延伸統計：R/B/G >= {RBG_MIN_HIT_COUNT} 球出現期數；"
        f"冷球 {COLD_NUM_WINDOW} 期、深冷球 {DEEP_COLD_NUM_WINDOW} 期，均以 N1-N7 計。"
    )
    print()


def print_query_result(draws: list[DrawRow]) -> None:
    query_rows = draws[-BACKTEST_DRAW_COUNT:]
    print("====== 查詢結果 ======")
    matched_count = 0
    total_rows = len(query_rows)
    for display_index, row in enumerate(query_rows, start=1):
        near_index = total_rows - display_index + 1
        if not is_matched(row["selected_count"]):
            continue
        matched_count += 1
        prize_text = f"，PZ{PRIZE_OPTION}:{row['prize_count']:g}" if SHOW_PRIZE_COUNT else ""
        print(f"{near_index}，{row['date']}，{format_selected_with_special(row)} /> {row['hit_score']:g} 球{prize_text}")
    print()
    print(f"符合期數：{matched_count}/{len(query_rows)}")


def build_num_comb_rows(draws: list[DrawRow]) -> list[dict[str, object]]:
    query_rows = draws[-BACKTEST_DRAW_COUNT:]
    total_rows = len(query_rows)
    range_nums = birthday_range_nums()
    pair_total = pair_count()
    single_start_index = pair_total + 1
    none_index = pair_total + len(range_nums) + 1
    backdraw_index = none_index + 1
    rbg_start_index = backdraw_index + 1
    pair_hits: dict[tuple[int, int], list[int]] = {
        pair: []
        for pair in itertools.combinations(range_nums, 2)
    }
    single_hits: dict[int, list[int]] = {num: [] for num in range_nums}
    no_1_9_hits: list[int] = []
    rbg_3_plus_hits: dict[int, list[int]] = {color_id: [] for color_id in (1, 2, 3)}

    for display_index, row in enumerate(query_rows, start=1):
        near_index = total_rows - display_index + 1
        row_nums = range_draw_nums(row, BIRTHDAY_NUM_MIN, BIRTHDAY_NUM_MAX)
        if len(row_nums) == NONE_NUM_EXACT_COUNT:
            no_1_9_hits.append(near_index)
        if len(row_nums) == SINGLE_NUM_EXACT_COUNT:
            for num in row_nums:
                single_hits[num].append(near_index)
        if len(row_nums) >= 2:
            for pair in pair_hits:
                if pair[0] in row_nums and pair[1] in row_nums:
                    pair_hits[pair].append(near_index)
        rbg_counts = {color_id: 0 for color_id in (1, 2, 3)}
        for num in all_draw_nums(row):
            rbg_counts[rbg_num(num)] += 1
        for color_id, count in rbg_counts.items():
            if count >= RBG_MIN_HIT_COUNT:
                rbg_3_plus_hits[color_id].append(near_index)

    cold_num_18 = find_cold_nums(draws, COLD_NUM_WINDOW)
    deep_num_24 = find_cold_nums(draws, DEEP_COLD_NUM_WINDOW)

    rows = [
        {
            "index": idx,
            "type": "pair",
            "item_1_9": f"({pair[0]},{pair[1]})",
            "backtest_hit_periods": "[" + ",".join(str(value) for value in hit_periods) + "]",
            "hit_count": len(hit_periods),
        }
        for idx, (pair, hit_periods) in enumerate(pair_hits.items(), start=1)
    ]
    rows.extend(
        {
            "index": single_start_index + offset,
            "type": "single",
            "item_1_9": f"({num})",
            "backtest_hit_periods": "[" + ",".join(str(value) for value in hit_periods) + "]",
            "hit_count": len(hit_periods),
        }
        for offset, (num, hit_periods) in enumerate(single_hits.items())
    )
    rows.append(
        {
            "index": none_index,
            "type": "none",
            "item_1_9": "(00)",
            "backtest_hit_periods": "[" + ",".join(str(value) for value in no_1_9_hits) + "]",
            "hit_count": len(no_1_9_hits),
        }
    )
    rows.append(
        {
            "index": backdraw_index,
            "type": "backdraw",
            "item_1_9": f"[{BACKTEST_DRAW_COUNT}]",
            "backtest_hit_periods": "[]",
            "hit_count": BACKTEST_DRAW_COUNT,
        }
    )
    rows.extend(
        {
            "index": rbg_start_index + color_id - 1,
            "type": "rbg_3_plus",
            "item_1_9": f"{rbg_label(color_id)}>={RBG_MIN_HIT_COUNT}",
            "backtest_hit_periods": "[" + ",".join(str(value) for value in hit_periods) + "]",
            "hit_count": len(hit_periods),
        }
        for color_id, hit_periods in rbg_3_plus_hits.items()
    )
    rows.append(
        {
            "index": rbg_start_index + 3,
            "type": "cold_num_18",
            "item_1_9": f"cold_num_{COLD_NUM_WINDOW}",
            "backtest_hit_periods": "[" + ",".join(str(value) for value in cold_num_18) + "]",
            "hit_count": len(cold_num_18),
        }
    )
    rows.append(
        {
            "index": rbg_start_index + 4,
            "type": "deep_num_24",
            "item_1_9": f"deep_num_{DEEP_COLD_NUM_WINDOW}",
            "backtest_hit_periods": "[" + ",".join(str(value) for value in deep_num_24) + "]",
            "hit_count": len(deep_num_24),
        }
    )
    return rows


def write_num_comb_csv(draws: list[DrawRow]) -> None:
    COMB_DATA_DIR.mkdir(parents=True, exist_ok=True)
    rows = build_num_comb_rows(draws)
    csv_path = num_comb_csv_path()
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["index", "type", "item_1_9", "backtest_hit_periods", "hit_count"],
        )
        writer.writeheader()
        writer.writerows(rows)
    print()
    print(f"{birthday_range_label()} 追蹤 CSV 已建立：{csv_path}")
    print(
        f"固定追蹤：{pair_count()} 組雙球 + {len(birthday_range_nums())} 個單球 + "
        f"(00) 無 {birthday_range_label()}。N7 特號如在範圍內，會當整數球加入累計。"
    )


def print_num_comb_result(draws: list[DrawRow]) -> None:
    rows = build_num_comb_rows(draws)
    pair_rows = [row for row in rows if row["type"] == "pair"]
    single_rows = [row for row in rows if row["type"] == "single"]
    none_row = next(row for row in rows if row["type"] == "none")
    backdraw_row = next(row for row in rows if row["type"] == "backdraw")
    rbg_rows = [row for row in rows if row["type"] == "rbg_3_plus"]
    cold_row = next(row for row in rows if row["type"] == "cold_num_18")
    deep_cold_row = next(row for row in rows if row["type"] == "deep_num_24")
    display_rows = sorted(
        (row for row in pair_rows if to_int(row["hit_count"]) >= 1),
        key=lambda row: (-to_int(row["hit_count"]), to_int(row["index"])),
    )
    print()
    print(
        f"====== 回測期 [{BACKTEST_DRAW_COUNT}]，{birthday_range_label()} "
        f"雙球 [{len(pair_rows)}] 組合統計：命中期數最多在上 ======"
    )
    for row in display_rows:
        print(
            f'{row["index"]},"{row["item_1_9"]}",'
            f'"{row["backtest_hit_periods"]}",{row["hit_count"]}'
        )
    print("----------------")
    print(f"{birthday_range_label()} 雙位組合條件 >= 1：{len(display_rows)}/{len(pair_rows)} 組")
    print()
    print(f"====== 回測期 [{BACKTEST_DRAW_COUNT}]，{birthday_range_label()} 單球出現期數統計 ======")
    for row in sorted(single_rows, key=lambda item: (-to_int(item["hit_count"]), to_int(item["index"]))):
        print(
            f'{row["index"]},"{row["item_1_9"]}",'
            f'"{row["backtest_hit_periods"]}",{row["hit_count"]}'
        )
    print("----------------")
    print(
        f'{none_row["index"]},"{none_row["item_1_9"]}",'
        f'"{none_row["backtest_hit_periods"]}",{none_row["hit_count"]}'
    )
    print("----------------")
    print(
        f'{backdraw_row["index"]}, {backdraw_row["type"]},'
        f'{backdraw_row["item_1_9"]}'
    )
    print("----------------")
    print(f"回測期：{BACKTEST_DRAW_COUNT} 期")
    print()
    print(f"====== 回測期 [{BACKTEST_DRAW_COUNT}]，R/B/G 3+ 出現期數統計：1-49，N1..N7 ======")
    for row in rbg_rows:
        print(
            f'{row["index"]},{row["type"]},"{row["item_1_9"]}",'
            f'"{row["backtest_hit_periods"]}",{row["hit_count"]}'
        )
    print()
    print(f"====== {birthday_range_label()} 冷球號統計 N1..N7 ======")
    print(
        f'{cold_row["index"]},{cold_row["type"]},'
        f'{cold_row["item_1_9"]},{cold_row["backtest_hit_periods"]},{cold_row["hit_count"]}'
    )
    print(
        f'{deep_cold_row["index"]},{deep_cold_row["type"]},'
        f'{deep_cold_row["item_1_9"]},{deep_cold_row["backtest_hit_periods"]},{deep_cold_row["hit_count"]}'
    )


def main() -> None:
    draws = read_draws()
    if not draws:
        raise RuntimeError("M6 沒有可用開獎資料。")
    print_settings(len(draws))
    print_query_result(draws)
    write_num_comb_csv(draws)
    print_num_comb_result(draws)


if __name__ == "__main__":
    main()
