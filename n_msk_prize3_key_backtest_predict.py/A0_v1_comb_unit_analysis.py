from pathlib import Path
import csv
import itertools
import json
from typing import TypedDict

'''
產生組合 1 to 31 取 3 個數字的所有組合: 4495

'''


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
M6_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"
COMB_DATA_DIR = CURRENT_DIR / "comb_data"

BACKTEST_DRAW_COUNT = 1  # 回測核對最近多少期，例如 1 = 用最新 1 期核對
WINDOW_DRAW_COUNT = 12  # 每次回測前，向前取多少期作窗口樣本統計
BIRTHDAY_NUM_MIN = 1  # 分析號碼範圍最小值
BIRTHDAY_NUM_MAX = 31  # 分析號碼範圍最大值
COMBINATION_TAKE_COUNT = 3  # 組合取幾個號碼，例如 2 或 3
# --
FOCUS_HIT_MIN_COUNT = 1  # 重點打印：3 球組合出現次數至少多少
FOCUS_PAIR_GROUP_MIN_COUNT = 3  # 重點打印：同一組 2 球相同，至少有多少個 3 球組合
WRITE_BACKTEST_MATCH = False  # 可選：True 才輸出回測核對；False 只做窗口分析

COMB_UNIT_CSV = COMB_DATA_DIR / f"comb_unit_{COMBINATION_TAKE_COUNT}.csv"
HIT_UNIT_CSV = COMB_DATA_DIR / f"hit_count_unit_{COMBINATION_TAKE_COUNT}.csv"
BACKTEST_MATCH_CSV = COMB_DATA_DIR / f"backtest_match_unit_{COMBINATION_TAKE_COUNT}.csv"
PAIR_FOCUS_GROUPS_JSON = COMB_DATA_DIR / f"pair_focus_groups_{COMBINATION_TAKE_COUNT}.json"


class DrawRow(TypedDict):
    date: str
    nums: list[int]


class ComboUnit(TypedDict):
    index: int
    combo: tuple[int, ...]
    hit_count: int
    hit_dates: list[str]


class BacktestMatchUnit(TypedDict):
    target_date: str
    index: int
    combo: tuple[int, ...]
    window_hit_count: int
    window_hit_dates: list[str]
    match_count: int


def validate_params() -> None:
    """檢查回測窗口、號碼範圍及組合取數是否合理。"""

    if BACKTEST_DRAW_COUNT < 1:
        raise ValueError("BACKTEST_DRAW_COUNT 必須大於 0")
    if WINDOW_DRAW_COUNT < 1:
        raise ValueError("WINDOW_DRAW_COUNT 必須大於 0")
    if BIRTHDAY_NUM_MIN < 1 or BIRTHDAY_NUM_MAX > 49:
        raise ValueError("分析號碼範圍必須介乎 1 至 49")
    if BIRTHDAY_NUM_MIN > BIRTHDAY_NUM_MAX:
        raise ValueError("BIRTHDAY_NUM_MIN 不可大於 BIRTHDAY_NUM_MAX")

    available_count = BIRTHDAY_NUM_MAX - BIRTHDAY_NUM_MIN + 1
    if COMBINATION_TAKE_COUNT < 1 or COMBINATION_TAKE_COUNT > available_count:
        raise ValueError(
            f"COMBINATION_TAKE_COUNT 必須介乎 1 至 {available_count}，"
            f"目前是 {COMBINATION_TAKE_COUNT}"
        )


def read_m6_lotto_history(csv_path: Path = M6_CSV) -> list[DrawRow]:
    """讀入 M6 歷史開獎資料，只整理日期及 N1-N6 正號。"""

    if not csv_path.exists():
        raise FileNotFoundError(f"找不到 M6 CSV：{csv_path}")

    rows: list[DrawRow] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames:
            reader.fieldnames = [name.strip().lstrip("\ufeff") for name in reader.fieldnames]

        for row in reader:
            nums: list[int] = []
            for idx in range(1, 7):
                try:
                    nums.append(int((row.get(f"N{idx}") or "").strip()))
                except ValueError:
                    nums.append(0)
            rows.append({"date": (row.get("nDdate") or "").strip(), "nums": nums})
    return rows


def selected_nums(nums: list[int]) -> list[int]:
    """只保留設定範圍內的號碼，例如 1-31。"""

    return sorted(num for num in nums if BIRTHDAY_NUM_MIN <= num <= BIRTHDAY_NUM_MAX)


def build_all_combo_units() -> dict[tuple[int, ...], ComboUnit]:
    """建立完整組合索引表，例如 1-31 選 3 共 4495 組。"""

    units: dict[tuple[int, ...], ComboUnit] = {}
    numbers = range(BIRTHDAY_NUM_MIN, BIRTHDAY_NUM_MAX + 1)
    for index, combo in enumerate(itertools.combinations(numbers, COMBINATION_TAKE_COUNT), start=1):
        units[combo] = {
            "index": index,
            "combo": combo,
            "hit_count": 0,
            "hit_dates": [],
        }
    return units


def collect_window_combo_units(rows: list[DrawRow]) -> dict[tuple[int, ...], ComboUnit]:
    """每個回測目標期前，取窗口期開獎號，累計組合出現次數。"""

    units = build_all_combo_units()

    for target_index in backtest_target_indices(rows):
        window_rows = get_window_rows(rows, target_index)
        for row in window_rows:
            nums = selected_nums(row["nums"])
            if len(nums) < COMBINATION_TAKE_COUNT:
                continue
            for combo in itertools.combinations(nums, COMBINATION_TAKE_COUNT):
                unit = units.get(combo)
                if unit is None:
                    continue
                unit["hit_count"] += 1
                if row["date"] not in unit["hit_dates"]:
                    unit["hit_dates"].append(row["date"])

    return units


def backtest_target_indices(rows: list[DrawRow]) -> range:
    """取得需要核對的回測目標期位置；最新期在最後。"""

    if len(rows) <= WINDOW_DRAW_COUNT:
        raise ValueError("M6 資料不足，不能同時建立窗口期及回測期")

    first_target_index = max(WINDOW_DRAW_COUNT, len(rows) - BACKTEST_DRAW_COUNT)
    return range(first_target_index, len(rows))


def get_window_rows(rows: list[DrawRow], target_index: int) -> list[DrawRow]:
    """取得目標期之前的窗口期資料，不包含目標期本身。"""

    start_index = max(0, target_index - WINDOW_DRAW_COUNT)
    return rows[start_index:target_index]


def build_backtest_match_units(
    rows: list[DrawRow],
    window_units: dict[tuple[int, ...], ComboUnit],
) -> list[BacktestMatchUnit]:
    """用窗口期產生的候選組合，核對回測目標期是否重現。"""

    matches: list[BacktestMatchUnit] = []
    for target_index in backtest_target_indices(rows):
        row = rows[target_index]
        nums = selected_nums(row["nums"])
        if len(nums) < COMBINATION_TAKE_COUNT:
            continue

        for combo in itertools.combinations(nums, COMBINATION_TAKE_COUNT):
            unit = window_units.get(combo)
            if unit is None or unit["hit_count"] <= 0:
                continue
            matches.append(
                {
                    "target_date": row["date"],
                    "index": unit["index"],
                    "combo": unit["combo"],
                    "window_hit_count": unit["hit_count"],
                    "window_hit_dates": unit["hit_dates"],
                    "match_count": 1,
                }
            )

    return sorted(matches, key=lambda item: (item["target_date"], item["index"]))


def combo_header() -> list[str]:
    """建立 CSV 欄位名稱，例如 index,N1,N2,N3,hit_count,hit_dates。"""

    return [
        "index",
        *(f"N{i}" for i in range(1, COMBINATION_TAKE_COUNT + 1)),
        "hit_count",
        "hit_dates",
    ]


def combo_to_csv_row(unit: ComboUnit) -> list[object]:
    """將組合統計資料轉成 CSV row。"""

    return [
        unit["index"],
        *unit["combo"],
        unit["hit_count"],
        "|".join(unit["hit_dates"]),
    ]


def backtest_match_header() -> list[str]:
    """建立回測核對 CSV 欄位名稱。"""

    return [
        "target_date",
        "index",
        *(f"N{i}" for i in range(1, COMBINATION_TAKE_COUNT + 1)),
        "window_hit_count",
        "window_hit_dates",
        "match_count",
    ]


def backtest_match_to_csv_row(unit: BacktestMatchUnit) -> list[object]:
    """將回測核對命中資料轉成 CSV row。"""

    return [
        unit["target_date"],
        unit["index"],
        *unit["combo"],
        unit["window_hit_count"],
        "|".join(unit["window_hit_dates"]),
        unit["match_count"],
    ]


def write_combo_csv_files(
    units: dict[tuple[int, ...], ComboUnit],
    backtest_matches: list[BacktestMatchUnit] | None = None,
) -> None:
    """輸出完整組合索引表、窗口統計表及回測核對命中表。"""

    COMB_DATA_DIR.mkdir(parents=True, exist_ok=True)
    sorted_units = sorted(units.values(), key=lambda unit: unit["index"])
    hit_units = sorted(
        (unit for unit in sorted_units if unit["hit_count"] > 0),
        key=lambda unit: (-unit["hit_count"], unit["index"]),
    )

    with COMB_UNIT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(combo_header())
        writer.writerows(combo_to_csv_row(unit) for unit in sorted_units)

    with HIT_UNIT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(combo_header())
        writer.writerows(combo_to_csv_row(unit) for unit in hit_units)

    if backtest_matches is not None:
        with BACKTEST_MATCH_CSV.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(backtest_match_header())
            writer.writerows(backtest_match_to_csv_row(unit) for unit in backtest_matches)
    elif BACKTEST_MATCH_CSV.exists():
        with BACKTEST_MATCH_CSV.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(backtest_match_header())


def write_pair_focus_groups_json(
    focus_groups: list[tuple[tuple[int, int], list[ComboUnit]]],
) -> None:
    """將 2 球重疊組詳細內容存成 JSON，方便之後預測公式使用。"""

    COMB_DATA_DIR.mkdir(parents=True, exist_ok=True)
    json_rows: list[dict[str, object]] = []
    for rank, (pair, group_units) in enumerate(focus_groups, start=1):
        json_rows.append(
            {
                "rank": rank,
                "pair": list(pair),
                "group_count": len(group_units),
                "total_hit_count": sum(unit["hit_count"] for unit in group_units),
                "combo_units": [
                    {
                        "index": unit["index"],
                        "nums": list(unit["combo"]),
                        "hit_count": unit["hit_count"],
                        "hit_dates": unit["hit_dates"],
                    }
                    for unit in group_units
                ],
            }
        )

    with PAIR_FOCUS_GROUPS_JSON.open("w", encoding="utf-8") as f:
        json.dump(json_rows, f, ensure_ascii=False, indent=2)


def print_hit_combo_units(units: dict[tuple[int, ...], ComboUnit]) -> None:
    """只打印 2 球重疊組排名，詳細組合另存 JSON。"""

    total_group = len(units)
    hit_units = [unit for unit in sorted(units.values(), key=lambda item: item["index"]) if unit_hit(unit)]

    print(
        f"====== 回測 {BACKTEST_DRAW_COUNT} 期，窗口 {WINDOW_DRAW_COUNT} 期，"
        f"{BIRTHDAY_NUM_MIN}-{BIRTHDAY_NUM_MAX} 選 {COMBINATION_TAKE_COUNT} "
        f"組合窗口統計，共 {total_group} 組 ======"
    )
    if not hit_units:
        print("沒有命中的組合。")
        return

    focus_groups = build_focus_pair_groups(hit_units)
    if not focus_groups:
        print("沒有符合重點條件的組合。")
        return

    write_pair_focus_groups_json(focus_groups)
    print(
        f"重點條件：3球組合 hit >= {FOCUS_HIT_MIN_COUNT}，"
        f"同一對2球相同 + 有 {FOCUS_PAIR_GROUP_MIN_COUNT} 組以上"
    )
    for rank, (pair, group_units) in enumerate(focus_groups, start=1):
        pair_text = ",".join(str(num) for num in pair)
        print(f"{rank}. [{pair_text}]，共 {len(group_units)} 組")


def build_focus_pair_groups(hit_units: list[ComboUnit]) -> list[tuple[tuple[int, int], list[ComboUnit]]]:
    """找出同一對 2 球相同，並帶出 3 組以上命中 3 球組合的群組。"""

    if COMBINATION_TAKE_COUNT != 3:
        return []

    pair_groups: dict[tuple[int, int], list[ComboUnit]] = {}
    for unit in hit_units:
        if unit["hit_count"] < FOCUS_HIT_MIN_COUNT:
            continue
        for pair in itertools.combinations(unit["combo"], 2):
            pair_groups.setdefault(pair, []).append(unit)

    focus_groups: list[tuple[tuple[int, int], list[ComboUnit]]] = []
    for pair, group_units in pair_groups.items():
        unique_units = {unit["combo"]: unit for unit in group_units}
        sorted_units = sorted(unique_units.values(), key=lambda unit: unit["index"])
        if len(sorted_units) >= FOCUS_PAIR_GROUP_MIN_COUNT:
            focus_groups.append((pair, sorted_units))

    return sorted(
        focus_groups,
        key=lambda item: (
            -len(item[1]),
            -sum(unit["hit_count"] for unit in item[1]),
            item[0],
        ),
    )


def unit_hit(unit: ComboUnit) -> bool:
    """判斷組合是否有出現次數。"""

    return unit["hit_count"] > 0


def main() -> None:
    """主程式入口：讀取 M6、建立窗口統計；回測核對按參數選擇。"""

    validate_params()
    rows = read_m6_lotto_history()
    units = collect_window_combo_units(rows)
    backtest_matches = build_backtest_match_units(rows, units) if WRITE_BACKTEST_MATCH else None
    write_combo_csv_files(units, backtest_matches)
    print_hit_combo_units(units)
    print()
    print("CSV 輸出完成。")
    if WRITE_BACKTEST_MATCH:
        print("回測核對輸出：已開啟。")
    else:
        print("回測核對輸出：已關閉，只做窗口集合分析。")


if __name__ == "__main__":
    main()
