from pathlib import Path
import csv
import json
from typing import TypedDict

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
M6_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"

# G1_v1 冷號回補優化：10-20 獨立版本，邏輯跟 F5_v6 對齊。
ACTIVE_GROUP_KEY = "10_20"
GROUP_LABEL = "10-20"
BIRTHDAY_NUM_MIN = 10
BIRTHDAY_NUM_MAX = 20
JSON_PATH = CURRENT_DIR / "json_data" / "G1_v1_cold_rebound_best.json"

# 冷號回補驗證：每個門檻代表該 1-9 號連續未出多少期後開始觀察。
COLD_GAP_LIST = list(range(12, 25))
REBOUND_HORIZONS = [1, 3, 6]
INCLUDE_SPECIAL_NUM = True


class DrawRow(TypedDict):
    date: str
    nums: list[int]
    special: int | None


class ReboundCase(TypedDict):
    num: int
    cold_gap: int
    rebound_date: str
    rebound_after_draws: int
    rebound_in_special: bool


def to_float(value: object, default: float = 0.0) -> float:
    if not isinstance(value, (int, float, str)):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def to_int(value: object, default: int = 0) -> int:
    if not isinstance(value, (int, float, str)):
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def read_draws() -> list[DrawRow]:
    if not M6_CSV.exists():
        raise FileNotFoundError(f"找不到 CSV：{M6_CSV}")
    with M6_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        draws: list[DrawRow] = []
        for row in reader:
            date = (row.get("nDdate") or "").strip()
            if not date:
                continue
            special = to_int(row.get("N7"))
            draws.append({
                "date": date,
                "nums": [to_int(row.get(f"N{index}")) for index in range(1, 7)],
                "special": special if 1 <= special <= 49 else None,
            })
    return draws


def draw_has_num(row: DrawRow, num: int) -> bool:
    if num in row["nums"]:
        return True
    return INCLUDE_SPECIAL_NUM and row["special"] == num


def is_special_only(row: DrawRow, num: int) -> bool:
    return row["special"] == num and num not in row["nums"]


def build_rebound_cases(draws: list[DrawRow], cold_gap: int) -> list[ReboundCase]:
    cases: list[ReboundCase] = []
    for num in range(BIRTHDAY_NUM_MIN, BIRTHDAY_NUM_MAX + 1):
        last_seen_index: int | None = None
        for index, row in enumerate(draws):
            if not draw_has_num(row, num):
                continue
            if last_seen_index is not None:
                absent_count = index - last_seen_index - 1
                if absent_count >= cold_gap:
                    cases.append({
                        "num": num,
                        "cold_gap": cold_gap,
                        "rebound_date": row["date"],
                        "rebound_after_draws": absent_count - cold_gap + 1,
                        "rebound_in_special": is_special_only(row, num),
                    })
            last_seen_index = index
    return cases


def current_cold_nums(draws: list[DrawRow], cold_gap: int) -> list[int]:
    recent = draws[-cold_gap:]
    return [
        num for num in range(BIRTHDAY_NUM_MIN, BIRTHDAY_NUM_MAX + 1)
        if not any(draw_has_num(row, num) for row in recent)
    ]


def summarize_gap(draws: list[DrawRow], cold_gap: int) -> dict[str, object]:
    cases = build_rebound_cases(draws, cold_gap)
    total = len(cases)
    summary: dict[str, object] = {
        "cold_gap": cold_gap,
        "case_count": total,
        "average_rebound_after_draws": (
            sum(case["rebound_after_draws"] for case in cases) / total if total else 0.0
        ),
        "special_only_rebound_count": sum(case["rebound_in_special"] for case in cases),
        "current_cold_nums": current_cold_nums(draws, cold_gap),
        "recent_cases": cases[-10:],
    }
    for horizon in REBOUND_HORIZONS:
        hit_count = sum(case["rebound_after_draws"] <= horizon for case in cases)
        summary[f"rebound_within_{horizon}_count"] = hit_count
        summary[f"rebound_within_{horizon}_rate"] = hit_count / total if total else 0.0
    return summary


def sort_summaries(summaries: list[dict[str, object]]) -> list[dict[str, object]]:
    return sorted(
        summaries,
        key=lambda item: (
            -to_float(item.get("rebound_within_1_rate")),
            -to_float(item.get("rebound_within_3_rate")),
            -to_int(item.get("case_count")),
            to_float(item.get("average_rebound_after_draws")),
            to_int(item.get("cold_gap")),
        ),
    )


def print_summary(summary: dict[str, object]) -> None:
    gap = to_int(summary.get("cold_gap"))
    total = to_int(summary.get("case_count"))
    print(f"冷號門檻：{gap} 期")
    print(f"歷史回補案例：{total} 次")
    for horizon in REBOUND_HORIZONS:
        hit_count = to_int(summary.get(f"rebound_within_{horizon}_count"))
        hit_rate = to_float(summary.get(f"rebound_within_{horizon}_rate"))
        print(f"達 {gap} 期冷號後，{horizon} 期內回補：{hit_count}/{total}，{hit_rate:.1%}")
    print(f"平均回補等待：{to_float(summary.get('average_rebound_after_draws')):.2f} 期")
    print(f"只在特號回補：{to_int(summary.get('special_only_rebound_count'))} 次")
    print(f"目前冷號：{summary.get('current_cold_nums', [])}")


def main() -> None:
    draws = read_draws()
    summaries = sort_summaries([summarize_gap(draws, gap) for gap in COLD_GAP_LIST])
    best = summaries[0] if summaries else {}
    print(f"====== G1_v1 {GROUP_LABEL} 冷號回補回測 ======")
    print("每個案例只在號碼首次達到冷號門檻後計一次，避免同一段未出連續重複計分。")
    for summary in summaries:
        print("------------------------------------------")
        print_summary(summary)
    print("==========================================")
    print(
        f"本次最佳參考門檻：{to_int(best.get('cold_gap'))} 期，"
        f"下一期回補率 {to_float(best.get('rebound_within_1_rate')):.1%}"
    )
    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(
        json.dumps(
            {
                "model": "G1_v1_cold_rebound_backtest",
                "include_special_num": INCLUDE_SPECIAL_NUM,
                "analysis_group": {
                    "key": ACTIVE_GROUP_KEY,
                    "label": GROUP_LABEL,
                    "min": BIRTHDAY_NUM_MIN,
                    "max": BIRTHDAY_NUM_MAX,
                },
                "best": best,
                "ranking": summaries,
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
