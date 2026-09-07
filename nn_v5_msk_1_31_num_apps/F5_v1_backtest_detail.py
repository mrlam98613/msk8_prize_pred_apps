from pathlib import Path
import csv
import itertools
from typing import TypedDict


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
M6_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"
M4_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M4_lotto_prize_summary.csv"
COMB_DATA_DIR = CURRENT_DIR / "comb_data"
F5_CSV = COMB_DATA_DIR / "F5_v1.csv"

# F5_v1 最基本參數：只分析 1-9 生日號。
BACKTEST_DRAW_COUNT_LIST = [3]
WINDOW_DRAW_COUNT_LIST = [12]
COMBINATION_TAKE_COUNT = 2
BIRTHDAY_NUM_MIN = 1
BIRTHDAY_NUM_MAX = 9
BIRTHDAY_NUM_MATCH_MODE = ">="
PRIZE_OPTION = 3
COLD_WARN_GAP = 12
DEEP_COLD_WARN_GAP = 18
RECENT_DRAW_COUNT = 5


class DrawRow(TypedDict):
    date: str
    nums: list[int]
    special: int | None
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
        raise FileNotFoundError(f"找不到 CSV：{path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [
            {(key or "").strip(): (value or "").strip() for key, value in row.items()}
            for row in reader
        ]


def read_draws() -> list[DrawRow]:
    rows: list[DrawRow] = []
    for row in read_csv_rows(M6_CSV):
        date = row.get("nDdate", "")
        if not date:
            continue
        rows.append({
            "date": date,
            "nums": [to_int(row.get(f"N{index}")) for index in range(1, 7)],
            "special": to_int(row.get("N7"), 0) or None,
            "prize_count": to_float(row.get(f"prize{PRIZE_OPTION}")),
        })
    return rows


def read_next_draw_date() -> str:
    rows = read_csv_rows(M4_CSV)
    return rows[-1].get("next_draw_date", "") if rows else ""


def all_draw_nums(row: DrawRow) -> list[int]:
    nums = [num for num in row["nums"] if 1 <= num <= 49]
    if row["special"] is not None and 1 <= row["special"] <= 49:
        nums.append(row["special"])
    return nums


def selected_nums(row: DrawRow) -> list[int]:
    return sorted({
        num for num in all_draw_nums(row)
        if BIRTHDAY_NUM_MIN <= num <= BIRTHDAY_NUM_MAX
    })


def is_matched(count: int) -> bool:
    if BIRTHDAY_NUM_MATCH_MODE == "==":
        return count == COMBINATION_TAKE_COUNT
    return count >= COMBINATION_TAKE_COUNT


def format_nums(nums: list[int]) -> str:
    return "[" + ",".join(str(num) for num in nums) + "]"


def pair_hits(rows: list[DrawRow]) -> dict[tuple[int, int], list[int]]:
    pairs = {pair: [] for pair in itertools.combinations(range(BIRTHDAY_NUM_MIN, BIRTHDAY_NUM_MAX + 1), 2)}
    total = len(rows)
    for display_index, row in enumerate(rows, start=1):
        nums = selected_nums(row)
        if not is_matched(len(nums)):
            continue
        near_index = total - display_index + 1
        for pair in itertools.combinations(nums, 2):
            pairs[pair].append(near_index)
    return pairs


def count_categories(rows: list[DrawRow]) -> dict[str, int]:
    counts = {"none": 0, "single": 0, "multi": 0}
    for row in rows:
        count = len(selected_nums(row))
        if count == 0:
            counts["none"] += 1
        elif count == 1:
            counts["single"] += 1
        else:
            counts["multi"] += 1
    return counts


def cold_numbers(rows: list[DrawRow], gap: int) -> list[int]:
    recent = rows[-gap:]
    appeared = {num for row in recent for num in selected_nums(row)}
    return [num for num in range(BIRTHDAY_NUM_MIN, BIRTHDAY_NUM_MAX + 1) if num not in appeared]


def number_waits(rows: list[DrawRow]) -> dict[int, int]:
    waits: dict[int, int] = {}
    for num in range(BIRTHDAY_NUM_MIN, BIRTHDAY_NUM_MAX + 1):
        wait = 0
        for row in reversed(rows):
            if num in selected_nums(row):
                break
            wait += 1
        waits[num] = wait
    return waits


def rbg_label(num: int) -> str:
    color_id = (((num - 1) // 10) + (num - 1)) % 6
    return ("R", "R", "B", "B", "G", "G")[color_id]


def print_settings(total: int) -> None:
    print("====== F5_v1 生日號基本回測策略 ======")
    print(f"資料期數：{total}")
    print(f"回測核對期數列表：{BACKTEST_DRAW_COUNT_LIST}")
    print(f"窗口期列表：{WINDOW_DRAW_COUNT_LIST}")
    print(f"分析範圍：{BIRTHDAY_NUM_MIN}-{BIRTHDAY_NUM_MAX}，N1-N7 {BIRTHDAY_NUM_MATCH_MODE} {COMBINATION_TAKE_COUNT} 球")
    print(f"冷號提示：{COLD_WARN_GAP} 期、很冷號：{DEEP_COLD_WARN_GAP} 期")
    print(f"回測明細最近期數：{RECENT_DRAW_COUNT} 期")
    print()


def print_category_lines(rows: list[DrawRow]) -> None:
    counts = count_categories(rows)
    print("------------------------------------------")
    print(f"00 無 1-9：{counts['none']} 期")
    print(f"== 1 球：{counts['single']} 期")
    print(f">= 2 球：{counts['multi']} 期")
    print(f"合計：{len(rows)} 期")


def build_f5_csv_rows(rows: list[DrawRow]) -> list[dict[str, object]]:
    total = len(rows)
    pair_map = pair_hits(rows)
    selected_map = {num: [] for num in range(BIRTHDAY_NUM_MIN, BIRTHDAY_NUM_MAX + 1)}
    none_hits: list[int] = []
    for display_index, row in enumerate(rows, start=1):
        near_index = total - display_index + 1
        nums = selected_nums(row)
        if len(nums) == 0:
            none_hits.append(near_index)
        if len(nums) == 1:
            selected_map[nums[0]].append(near_index)

    rows_out: list[dict[str, object]] = []
    for index, (pair, hits) in enumerate(pair_map.items(), start=1):
        rows_out.append({
            "index": index,
            "type": "pair",
            "item_1_9": f"({pair[0]},{pair[1]})",
            "backtest_hit_periods": format_nums(hits),
            "hit_count": len(hits),
        })
    single_start = len(rows_out) + 1
    for offset, (num, hits) in enumerate(selected_map.items()):
        rows_out.append({
            "index": single_start + offset,
            "type": "single",
            "item_1_9": f"({num})",
            "backtest_hit_periods": format_nums(hits),
            "hit_count": len(hits),
        })
    none_index = len(rows_out) + 1
    rows_out.append({
        "index": none_index,
        "type": "none",
        "item_1_9": "(00)",
        "backtest_hit_periods": format_nums(none_hits),
        "hit_count": len(none_hits),
    })
    backdraw_index = none_index + 1
    rows_out.append({
        "index": backdraw_index,
        "type": "backdraw",
        "item_1_9": f"[{total}]",
        "backtest_hit_periods": "[]",
        "hit_count": total,
    })
    rbg_hits = {label: [] for label in ("R", "B", "G")}
    for display_index, row in enumerate(rows, start=1):
        near_index = total - display_index + 1
        color_counts = {label: 0 for label in rbg_hits}
        for num in all_draw_nums(row):
            color_counts[rbg_label(num)] += 1
        for label, count in color_counts.items():
            if count >= 3:
                rbg_hits[label].append(near_index)
    rbg_start = backdraw_index + 1
    for offset, (label, hits) in enumerate(rbg_hits.items()):
        rows_out.append({
            "index": rbg_start + offset,
            "type": "rbg_3_plus",
            "item_1_9": f"{label}>=3",
            "backtest_hit_periods": format_nums(hits),
            "hit_count": len(hits),
        })
    cold = cold_numbers(rows, COLD_WARN_GAP)
    deep = cold_numbers(rows, DEEP_COLD_WARN_GAP)
    rows_out.append({
        "index": rbg_start + 3,
        "type": "cold_num_12",
        "item_1_9": f"cold_num_{COLD_WARN_GAP}",
        "backtest_hit_periods": format_nums(cold),
        "hit_count": len(cold),
    })
    rows_out.append({
        "index": rbg_start + 4,
        "type": "deep_num_18",
        "item_1_9": f"deep_num_{DEEP_COLD_WARN_GAP}",
        "backtest_hit_periods": format_nums(deep),
        "hit_count": len(deep),
    })
    return rows_out


def write_f5_csv(rows: list[DrawRow]) -> None:
    COMB_DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_rows = build_f5_csv_rows(rows)
    with F5_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["index", "type", "item_1_9", "backtest_hit_periods", "hit_count"],
        )
        writer.writeheader()
        writer.writerows(output_rows)


def print_pair_summary(rows: list[DrawRow], label: str) -> None:
    pairs = pair_hits(rows)
    ranked = sorted(pairs.items(), key=lambda item: (-len(item[1]), item[0]))
    total_pairs = len(list(itertools.combinations(range(BIRTHDAY_NUM_MIN, BIRTHDAY_NUM_MAX + 1), 2)))
    appeared_pairs = sum(1 for hits in pairs.values() if hits)
    # print(f"====== 窗口期 {label}，2 球 1-9，{total_pairs} 組，雙球組合統計 ======")
    # print(f">= 1 期：{appeared_pairs}/{total_pairs} 組")
    # for pair, hits in ranked:
    #     if not hits:
    #         continue
    #     print(f"({pair[0]},{pair[1]})：出現 {len(hits)} 次，期數 {format_nums(hits)}")
    # print()


def print_cold_summary(rows: list[DrawRow], window_count: int) -> None:
    cold = cold_numbers(rows, COLD_WARN_GAP)
    deep = cold_numbers(rows, DEEP_COLD_WARN_GAP)
    print("------------------------------------------")
    print(f"{COLD_WARN_GAP} 期次冷號：{format_nums(cold)}")
    print(f"{DEEP_COLD_WARN_GAP} 期很冷號：{format_nums(deep)}")
    print()


def print_recent_summary(rows: list[DrawRow]) -> None:
    for index in range(min(RECENT_DRAW_COUNT, len(rows)), 0, -1):
        row = rows[-index]
        nums = selected_nums(row)
        count_text = "None" if not nums else f"{len(nums)} 球"
        print(f"最近 {index} 期：{row['date']}，{format_nums(nums)} = {count_text}")
    print()


def format_display_draw(row: DrawRow) -> str:
    normal_nums = [str(num) if 1 <= num <= 31 else "_" for num in row["nums"]]
    special = row["special"]
    special_text = f"*{special}" if special is not None and 1 <= special <= 31 else "_"
    return "[" + ",".join(normal_nums + [special_text]) + "]"


def count_display_nums(row: DrawRow) -> int:
    normal_count = sum(1 for num in row["nums"] if 1 <= num <= 31)
    special_count = 1 if row["special"] is not None and 1 <= row["special"] <= 31 else 0
    return normal_count + special_count


def print_backtest_detail(
    draws: list[DrawRow],
    check_index: int,
    rank: int,
    window_count: int,
) -> None:
    sample_end = check_index
    sample_rows = draws[max(0, sample_end - window_count):sample_end]
    check_row = draws[check_index]
    if len(sample_rows) < window_count:
        print(f"窗口期 {window_count}：資料不足，略過。")
        return
    base_row = sample_rows[-1]
    print(
        f"/> {rank} 回測期：{base_row['date']} {format_display_draw(base_row)} "
        f"/> {count_display_nums(base_row)} 球"
    )
    print(
        f"     - 核對期：{check_row['date']}，{format_display_draw(check_row)} "
        f"/> {count_display_nums(check_row)} 球"
    )
    print_category_lines(sample_rows)
    print_cold_summary(draws[:sample_end], window_count)
    print("------------------------------------------")
    print_recent_summary(sample_rows)


def main() -> None:
    draws = read_draws()
    if not draws:
        raise RuntimeError("沒有可用開獎資料。")
    print_settings(len(draws))
    for backtest_count in BACKTEST_DRAW_COUNT_LIST:
        if backtest_count <= 0:
            print(f"回測期數 {backtest_count}：必須大於 0，略過。")
            continue
        if len(draws) <= backtest_count:
            print(f"回測期數 {backtest_count}：資料不足，略過。")
            continue

        for window_count in WINDOW_DRAW_COUNT_LIST:
            sample_end = len(draws) - backtest_count
            sample_start = sample_end - window_count
            sample_rows = draws[max(0, sample_start):sample_end]
            if len(sample_rows) < window_count:
                print(f"窗口期 {window_count}：資料不足，略過。")
                continue
            write_f5_csv(sample_rows)
            print_pair_summary(sample_rows, str(window_count))
            print(f"====== F5_v1 回測 [{backtest_count}], 窗口期 [{window_count}] 核對 ======")
            first_check_index = len(draws) - backtest_count
            for offset, check_index in enumerate(range(first_check_index, len(draws))):
                rank = backtest_count - offset
                print_backtest_detail(draws, check_index, rank, window_count)
                if offset < backtest_count - 1:
                    print("------------------------------------------------------------")
            print("==================================")
            print(f"下期日期：{read_next_draw_date()}")
            print("============== 完結 ==============")
            print()


if __name__ == "__main__":
    main()
