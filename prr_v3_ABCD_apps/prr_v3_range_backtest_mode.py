from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import sys


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from prr_v3_ABCD_apps import ppr_v3_once_backtest_mode as engine  # noqa: E402


# range backtest：預設由倒數第 50 期逐期回測至倒數第 1 期。
RANGE_BACKTEST_FROM = 30
RANGE_BACKTEST_TO = 1
BACKTEST_DRAW_COUNT_LIST = list(range(RANGE_BACKTEST_FROM, RANGE_BACKTEST_TO - 1, -1))

# CSV 窗口命中統計只使用 JSON 內最近 N 個有效核對日期重算。
BACKTEST_WINDOW_HIT_DRAW = 30

# range 專用輸出檔案，避免與 once 人工單期分析混在一起。
RANGE_DATA_DIR = engine.DATA_DIR / "range"
BACKTEST_RECORD_CSV = RANGE_DATA_DIR / "prr_v3_range_backtest_records.csv"
ABCD_WINDOW_HIT_SUMMARY_CSV = RANGE_DATA_DIR / "range_abcd_window_hit_summary.csv"
HIGH_FREQ_DAN_WINDOW_HIT_SUMMARY_CSV = RANGE_DATA_DIR / "range_high_freq_dan_window_hit_summary.csv"
WEIGHT_JSON = engine.JSON_DIR / "prr_v3_range_weight_trace.json"
BACKTEST_RESULT_JSON = engine.JSON_DIR / "prr_v3_range_backtest_results.json"
RANGE_BACKTEST_STATE_JSON = engine.JSON_DIR / "prr_v3_range_backtest_state.json"


def range_backtest_signature(draws: list[engine.DrawRow]) -> dict[str, object]:
    """建立判斷 range backtest 是否需要重跑的資料簽名。"""
    latest_row = draws[-1] if draws else None
    return {
        "last_draw_date": latest_row["date"] if latest_row else "",
        "range_backtest_from": RANGE_BACKTEST_FROM,
        "range_backtest_to": RANGE_BACKTEST_TO,
        "backtest_window_hit_draw": BACKTEST_WINDOW_HIT_DRAW,
        "window_draw_count_list": list(engine.WINDOW_DRAW_COUNT_LIST),
        "base_group_take_counts": {
            engine.GROUPS[group_id][0]: engine.BASE_GROUP_TAKE_COUNTS[group_id]
            for group_id in engine.GROUPS
        },
        "auto_distribute_group_take": engine.AUTO_DISTRIBUTE_GROUP_TAKE,
        "auto_distribute_max_transfer": engine.AUTO_DISTRIBUTE_MAX_TRANSFER,
        "auto_distribute_min_group_take": engine.AUTO_DISTRIBUTE_MIN_GROUP_TAKE,
        "auto_distribute_min_gap_percent": engine.AUTO_DISTRIBUTE_MIN_GAP_PERCENT,
        "combination_take_count": engine.COMBINATION_TAKE_COUNT,
        "birthday_num_match_mode": engine.BIRTHDAY_NUM_MATCH_MODE,
        "high_freq_min_pair_count": engine.HIGH_FREQ_MIN_PAIR_COUNT,
        "high_freq_dan_take": engine.HIGH_FREQ_DAN_TAKE,
        "high_freq_partner_take": engine.HIGH_FREQ_PARTNER_TAKE,
        "weak_num_take": engine.WEAK_NUM_TAKE,
        "weak_num_random_seed": engine.WEAK_NUM_RANDOM_SEED,
    }


def load_range_backtest_state() -> dict[str, object]:
    """讀取上次 range backtest 的資料簽名。"""
    if not RANGE_BACKTEST_STATE_JSON.exists():
        return {}
    try:
        with RANGE_BACKTEST_STATE_JSON.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def save_range_backtest_state(signature: dict[str, object]) -> None:
    """保存本次 range backtest 的資料簽名。"""
    engine.JSON_DIR.mkdir(parents=True, exist_ok=True)
    with RANGE_BACKTEST_STATE_JSON.open("w", encoding="utf-8") as handle:
        json.dump(signature, handle, ensure_ascii=False, indent=2)


def range_output_files_exist() -> bool:
    """確認 nextDraw 需要讀取的 range CSV 是否存在。"""
    return (
        ABCD_WINDOW_HIT_SUMMARY_CSV.exists()
        and HIGH_FREQ_DAN_WINDOW_HIT_SUMMARY_CSV.exists()
        and BACKTEST_RECORD_CSV.exists()
    )


def range_backtest_needs_update(draws: list[engine.DrawRow]) -> bool:
    """資料最後日期或設定有變時才需要重跑 range backtest。"""
    configure_engine_for_range()
    if not draws:
        return True
    if not range_output_files_exist():
        return True
    return load_range_backtest_state() != range_backtest_signature(draws)


def configure_engine_for_range() -> None:
    """把共用 engine 切換成 range backtest 的設定與輸出檔案。"""
    engine.MODE = "backtest"
    engine.BACKTEST_DRAW_COUNT_LIST = BACKTEST_DRAW_COUNT_LIST
    engine.BACKTEST_WINDOW_HIT_DRAW = BACKTEST_WINDOW_HIT_DRAW
    engine.BACKTEST_RECORD_CSV = BACKTEST_RECORD_CSV
    engine.ABCD_WINDOW_HIT_SUMMARY_CSV = ABCD_WINDOW_HIT_SUMMARY_CSV
    engine.HIGH_FREQ_DAN_WINDOW_HIT_SUMMARY_CSV = HIGH_FREQ_DAN_WINDOW_HIT_SUMMARY_CSV
    engine.WEIGHT_JSON = WEIGHT_JSON
    engine.BACKTEST_RESULT_JSON = BACKTEST_RESULT_JSON


def run_range_backtest(verbose: bool = True) -> None:
    """執行 range backtest，建立 nextDraw 使用的窗口期命中 CSV。"""
    configure_engine_for_range()
    engine.migrate_once_backtest_results_from_weight_json()
    draws = engine.read_draws()
    if not draws:
        raise FileNotFoundError(f"找不到或未能讀取 M6：{engine.M6_CSV}")
    signature = range_backtest_signature(draws)

    if verbose:
        print("====== PRR v3 range backtest ======")
        print(f"回測期：倒數第 {RANGE_BACKTEST_FROM} 期 至 倒數第 {RANGE_BACKTEST_TO} 期")
        print(f"窗口期列表：{engine.WINDOW_DRAW_COUNT_LIST}")
        print(f"CSV 最近有效回測統計上限：{BACKTEST_WINDOW_HIT_DRAW} 期")
        print()
        engine.run_backtest(draws)
        save_range_backtest_state(signature)
        return

    with contextlib.redirect_stdout(io.StringIO()):
        engine.run_backtest(draws)
    save_range_backtest_state(signature)


def main() -> None:
    run_range_backtest(verbose=True)


if __name__ == "__main__":
    main()
