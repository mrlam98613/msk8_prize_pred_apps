from pathlib import Path
import ast
import csv
import json
from typing import TypedDict


CURRENT_DIR = Path(__file__).resolve().parent
COMB_CSV = CURRENT_DIR / "comb_data" / "E1_num_1_9_comb.csv"
JSON_DIR = CURRENT_DIR / "json_data"
MODEL_JSON = JSON_DIR / "E4_v1_19_pred_mode_params.json"

# E4_v1：1-9 追蹤預測模型。
# 流程：
# 1. 讀入 E1 產生的 47 行追蹤 CSV。
# 2. 36 組雙球做主體分析，9 個單球做交叉支撐，(00) 判斷是否不發 1-9。
# 3. 每組雙球用「出現次數 + 單球支撐 + 週期壓力 + RBG互補 + 小中大互補」計分。
# 4. 分數最高的 1-2 組雙球，作為 1-9 預測組合。

MIN_PAIR_HIT_COUNT = 1  # 雙球組合最少出現幾次才進入排名；1=全部曾出現組合都參考。
PAIR_HIT_WEIGHT = 10  # 雙球本身出現次數權重；越高越偏向熱門雙球組合。
SINGLE_HIT_WEIGHT = 2  # 兩個單球各自出現次數的支撐權重；用來補強低頻但單球熱門的組合。
CYCLE_PRESSURE_WEIGHT = 20  # 週期壓力權重；目前等待期越接近或超過平均相隔，分數越高。
RBG_MIX_BONUS = 3  # RBG 不同色組合加分；避免只集中同一顏色。
ZONE_MIX_BONUS = 2  # 小中大不同段組合加分；1-3=小，4-6=中，7-9=大。
PREDICT_PAIR_COUNT = 2  # 最後輸出幾組雙球預測；1 或 2 都可。
NONE_PRESSURE_WARN = 0.85  # (00) 無 1-9 週期壓力門檻；高於此值且高過雙球壓力，提示不發球。


class TrackRow(TypedDict):
    # E1 CSV 每一行的追蹤資料。
    index: int
    row_type: str
    item: str
    periods: list[int]
    hit_count: int


class PairScore(TypedDict):
    # 每一組雙球的交叉驗證計分結果。
    index: int
    pair: tuple[int, int]
    periods: list[int]  # 出現期數，數字越細代表越近。
    hit_count: int  # 出現總次數。
    gaps: list[int]  # 每次出現之間的相隔期數。
    avg_gap: float  # 平均相隔期數。
    wait_count: int  # 目前距離最近一次出現，已等待多少期。
    cycle_pressure: float  # 週期壓力 = 目前等待期 / 平均相隔期。
    single_support: int  # 兩個單球各自出現次數合計。
    rbg_type: str  # RBG 顏色組合，例如 R+B。
    zone_type: str  # 小中大組合，例如 小+大。
    score: float  # 最終模型分數。


def to_int(value: object, default: int = 0) -> int:
    if not isinstance(value, (int, float, str)):
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def parse_periods(value: str) -> list[int]:
    # CSV 內的 "[22,13,10,3]" 文字轉回 list[int]。
    try:
        data = ast.literal_eval(value)
    except (SyntaxError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    return [to_int(item) for item in data if to_int(item) > 0]


def parse_pair(value: str) -> tuple[int, int] | None:
    # CSV 內的 "(1,7)" 文字轉回 tuple[int, int]。
    try:
        data = ast.literal_eval(value)
    except (SyntaxError, ValueError):
        return None
    if (
        isinstance(data, tuple)
        and len(data) == 2
        and isinstance(data[0], int)
        and isinstance(data[1], int)
    ):
        return data
    return None


def read_track_rows() -> list[TrackRow]:
    # 只讀 E1 新版 47 行格式，避免舊 CSV 欄位混入造成模型錯判。
    if not COMB_CSV.exists():
        raise FileNotFoundError(f"找不到 E1 追蹤 CSV，請先執行 E1_v1_1_9_basic_query.py：{COMB_CSV}")

    with COMB_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {"index", "type", "item_1_9", "backtest_hit_periods", "hit_count"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise RuntimeError("E1_num_1_9_comb.csv 不是新版 47 行追蹤格式，請先重新執行 E1_v1_1_9_basic_query.py。")
        return [
            {
                "index": to_int(row.get("index")),
                "row_type": row.get("type", ""),
                "item": row.get("item_1_9", ""),
                "periods": parse_periods(row.get("backtest_hit_periods", "[]")),
                "hit_count": to_int(row.get("hit_count")),
            }
            for row in reader
        ]


def get_backdraw(rows: list[TrackRow]) -> int:
    # 第 47 行 backdraw 記錄 E1 的回測期數，也等於本模型的分析窗口。
    backdraw = next((row for row in rows if row["row_type"] == "backdraw"), None)
    if backdraw is None:
        return 0
    return backdraw["hit_count"]


def build_gap_stats(periods: list[int], backdraw: int) -> tuple[list[int], float, int, float]:
    # 由出現期數計算相隔、平均相隔、目前等待期及週期壓力。
    # 例：[22,13,10,3] -> 相隔 [9,3,7]，目前等待 3 期。
    sorted_periods = sorted(periods, reverse=True)
    gaps = [
        sorted_periods[idx] - sorted_periods[idx + 1]
        for idx in range(len(sorted_periods) - 1)
    ]
    avg_gap = sum(gaps) / len(gaps) if gaps else float(backdraw or 0)
    wait_count = min(sorted_periods) if sorted_periods else backdraw
    cycle_pressure = wait_count / avg_gap if avg_gap else 0.0
    return gaps, avg_gap, wait_count, cycle_pressure


def rbg_num(num: int) -> int:
    # 依六合彩 R/B/G 規則把號碼轉成 1=R, 2=B, 3=G。
    j_num = num - 1
    return (((j_num // 10) + j_num) % 6 // 2) + 1


def rbg_pair_type(pair: tuple[int, int]) -> str:
    labels = {1: "R", 2: "B", 3: "G"}
    return "+".join(labels[rbg_num(num)] for num in pair)


def zone_num(num: int) -> int:
    # 1-9 內再分三段：1-3 小，4-6 中，7-9 大。
    if 1 <= num <= 3:
        return 1
    if 4 <= num <= 6:
        return 2
    return 3


def zone_pair_type(pair: tuple[int, int]) -> str:
    labels = {1: "小", 2: "中", 3: "大"}
    return "+".join(labels[zone_num(num)] for num in pair)


def build_pair_scores(rows: list[TrackRow]) -> list[PairScore]:
    # 核心模型：雙球出現次數是主體，單球次數、週期壓力、RBG、小中大作交叉驗證。
    backdraw = get_backdraw(rows)
    single_hits = {
        to_int(row["item"].strip("()")): row["hit_count"]
        for row in rows
        if row["row_type"] == "single"
    }
    scores: list[PairScore] = []
    for row in rows:
        if row["row_type"] != "pair" or row["hit_count"] < MIN_PAIR_HIT_COUNT:
            continue
        pair = parse_pair(row["item"])
        if pair is None:
            continue
        gaps, avg_gap, wait_count, cycle_pressure = build_gap_stats(row["periods"], backdraw)
        single_support = single_hits.get(pair[0], 0) + single_hits.get(pair[1], 0)
        rbg_bonus = RBG_MIX_BONUS if rbg_num(pair[0]) != rbg_num(pair[1]) else 0
        zone_bonus = ZONE_MIX_BONUS if zone_num(pair[0]) != zone_num(pair[1]) else 0
        # 總分越高代表越值得列入 1-9 雙球預測。
        score = (
            row["hit_count"] * PAIR_HIT_WEIGHT
            + single_support * SINGLE_HIT_WEIGHT
            + cycle_pressure * CYCLE_PRESSURE_WEIGHT
            + rbg_bonus
            + zone_bonus
        )
        scores.append(
            {
                "index": row["index"],
                "pair": pair,
                "periods": row["periods"],
                "hit_count": row["hit_count"],
                "gaps": gaps,
                "avg_gap": avg_gap,
                "wait_count": wait_count,
                "cycle_pressure": cycle_pressure,
                "single_support": single_support,
                "rbg_type": rbg_pair_type(pair),
                "zone_type": zone_pair_type(pair),
                "score": score,
            }
        )
    return sorted(scores, key=lambda item: (-item["score"], -item["hit_count"], item["wait_count"], item["index"]))


def build_none_pressure(rows: list[TrackRow]) -> tuple[list[int], list[int], float, int, float]:
    # (00) 代表該期 N1-N6 + N7 特號完全沒有 1-9，用來判斷是否要提示不發球。
    none_row = next((row for row in rows if row["row_type"] == "none"), None)
    backdraw = get_backdraw(rows)
    if none_row is None:
        return [], [], 0.0, backdraw, 0.0
    gaps, avg_gap, wait_count, pressure = build_gap_stats(none_row["periods"], backdraw)
    return none_row["periods"], gaps, avg_gap, wait_count, pressure


def format_nums(nums: list[int] | tuple[int, ...]) -> str:
    return "[" + ",".join(str(num) for num in nums) + "]"


def write_model_json(rows: list[TrackRow], pair_scores: list[PairScore], none_pressure: tuple[list[int], list[int], float, int, float]) -> None:
    # JSON 保存本次模型參數與前 10 名結果，給下一版自動比較/升級用。
    JSON_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": "E4_v1_19_pred_mode",
        "source_csv": str(COMB_CSV),
        "backdraw": get_backdraw(rows),
        "params": {
            "min_pair_hit_count": MIN_PAIR_HIT_COUNT,
            "pair_hit_weight": PAIR_HIT_WEIGHT,
            "single_hit_weight": SINGLE_HIT_WEIGHT,
            "cycle_pressure_weight": CYCLE_PRESSURE_WEIGHT,
            "rbg_mix_bonus": RBG_MIX_BONUS,
            "zone_mix_bonus": ZONE_MIX_BONUS,
            "predict_pair_count": PREDICT_PAIR_COUNT,
            "none_pressure_warn": NONE_PRESSURE_WARN,
        },
        "none_group": {
            "periods": none_pressure[0],
            "gaps": none_pressure[1],
            "avg_gap": round(none_pressure[2], 2),
            "wait_count": none_pressure[3],
            "cycle_pressure": round(none_pressure[4], 2),
        },
        "top_pair_scores": [
            {
                "index": item["index"],
                "pair": item["pair"],
                "periods": item["periods"],
                "hit_count": item["hit_count"],
                "gaps": item["gaps"],
                "avg_gap": round(item["avg_gap"], 2),
                "wait_count": item["wait_count"],
                "cycle_pressure": round(item["cycle_pressure"], 2),
                "single_support": item["single_support"],
                "rbg_type": item["rbg_type"],
                "zone_type": item["zone_type"],
                "score": round(item["score"], 2),
            }
            for item in pair_scores[:10]
        ],
    }
    with MODEL_JSON.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def print_result(rows: list[TrackRow], pair_scores: list[PairScore]) -> None:
    # 打印分三段：(00) 風險、雙球排名、最後預測結果。
    none_periods, none_gaps, none_avg_gap, none_wait, none_pressure = build_none_pressure(rows)
    predictions = pair_scores[:PREDICT_PAIR_COUNT]
    should_skip = none_pressure >= NONE_PRESSURE_WARN and none_pressure > max(
        (item["cycle_pressure"] for item in predictions),
        default=0.0,
    )

    print("====== E4_v1 1-9 追蹤預測模型 ======")
    print(f"讀入 CSV：{COMB_CSV}")
    print(f"回測期 / 預測窗口：{get_backdraw(rows)} 期")
    print("模型口徑：36 組雙球 + 9 個單球 + (00) 無 1-9，N7 特號加入追蹤累計。")
    print()

    print("====== (00) 無 1-9 追蹤 ======")
    print(
        f"(00) 出現期數：{format_nums(none_periods)}，"
        f"相隔{format_nums(none_gaps)}，平均{none_avg_gap:.2f}期，"
        f"目前等待{none_wait}期，壓力{none_pressure:.2f}"
    )
    if should_skip:
        print("預測提示：(00) = None，1-9 可能不出現，暫不發球。")
    else:
        print("預測提示：(00) 未達不發球條件，可以發雙球組合。")
    print()

    print("====== 雙球組合交叉驗證排名 ======")
    print("排名 | 索引 | 組合 | 出現 | 期數 | 相隔 | 平均 | 等待 | 單球支撐 | RBG | 小中大 | 分數")
    for rank, item in enumerate(pair_scores[:10], start=1):
        print(
            f"{rank:>2} | {item['index']:>2} | ({item['pair'][0]},{item['pair'][1]}) | "
            f"{item['hit_count']:>2} | {format_nums(item['periods'])} | "
            f"{format_nums(item['gaps'])} | {item['avg_gap']:.2f} | "
            f"{item['wait_count']:>2} | {item['single_support']:>2} | "
            f"{item['rbg_type']} | {item['zone_type']} | {item['score']:.2f}"
        )
    print()

    print("====== E4_v1 預測結果 ======")
    if should_skip:
        print("1，(00) = None")
    else:
        pred_text = "，".join(f"({item['pair'][0]},{item['pair'][1]})" for item in predictions)
        print(f"1，雙球組合預測：{pred_text}")
        print("2，(00) = None 未啟動")
    write_model_json(rows, pair_scores, (none_periods, none_gaps, none_avg_gap, none_wait, none_pressure))
    print()
    print(f"JSON 已寫入：{MODEL_JSON}")


def main() -> None:
    rows = read_track_rows()
    pair_scores = build_pair_scores(rows)
    print_result(rows, pair_scores)


if __name__ == "__main__":
    main()
