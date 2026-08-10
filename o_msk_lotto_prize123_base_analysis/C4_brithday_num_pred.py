# -*- coding: utf-8 -*-
"""
每期生日號分析。

讀入 M6_lotto_history_prize.csv，將 N1-N6 正號中 1-31 的號碼視為生日號。
每個回測目標期會用前面指定窗口期收集生日號池，收集滿上限即停止，
再核對目標期開號中的生日號命中。
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

import res_func_num_convert_RBG_Dict


current_dir = Path(__file__).resolve().parent
PRIZE_CSV_DATA = current_dir.parent / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"
OUTPUT_JSON = current_dir / "birthday_num_backtest_params.json"
DEFAULT_BACKTEST_DRAW = 10
DEFAULT_WINDOW_DRAW = 30
DEFAULT_COLLECT_LIMIT = [20]
DEFAULT_MIN_DRAW_BIRTHDAY_COUNT = [5]
BIRTHDAY_MIN = 1
BIRTHDAY_MAX = 31
PRIZE_SCORES = [6.0, 5.5, 5.0, 4.5, 4.0, 3.5, 3.0]
PRIZE_LABELS = {
    6.0: "一獎  6    ",
    5.5: "二獎  5 +  ",
    5.0: "三獎  5    ",
    4.5: "四獎  4 +  ",
    4.0: "五獎  4    ",
    3.5: "六獎  3 +  ",
    3.0: "七獎  3    ",
}


def load_lotto_history_prize() -> pd.DataFrame:
    """取得全部歷史開獎及 1,2,3 獎中獎紀錄。"""

    df = pd.read_csv(
        PRIZE_CSV_DATA,
        dtype={
            "nDdate": str,
            "N1": int,
            "N2": int,
            "N3": int,
            "N4": int,
            "N5": int,
            "N6": int,
            "N7": int,
            "prize1": float,
            "prize2": float,
            "prize3": float,
            "prize1_unit": float,
            "prize2_unit": float,
            "prize3_unit": float,
        },
    )
    df = df.rename(columns={"nDdate": "ndate"})
    return df.reset_index(drop=True)


def get_main_nums(row: pd.Series) -> list[int]:
    """回傳 N1-N6 正號。"""

    return [int(row[f"N{i}"]) for i in range(1, 7)]


def get_birthday_nums(nums: list[int]) -> list[int]:
    """回傳 1-31 生日號組。"""

    return sorted(num for num in nums if BIRTHDAY_MIN <= num <= BIRTHDAY_MAX)


def group_birthday_pool(birthday_pool: list[int]) -> dict[str, list[int]]:
    """將生日號池分成 0-9、10-20、21-31 三組。"""

    return {
        "0-9": [num for num in birthday_pool if 0 <= num <= 9],
        "10-20": [num for num in birthday_pool if 10 <= num <= 20],
        "21-31": [num for num in birthday_pool if 21 <= num <= 31],
    }


def format_group_pool(group_pool: dict[str, list[int]]) -> str:
    """將生日號分組池轉成簡單文字。"""

    return " | ".join(f"{group}:{nums}" for group, nums in group_pool.items())


def group_rbg_pool(birthday_pool: list[int]) -> dict[str, list[int]]:
    """將生日候選號池轉成 R/B/G 分組。"""

    rbg_dict = res_func_num_convert_RBG_Dict.res_List_To_rbg_Dict_func(birthday_pool)
    return {
        "R": sorted(int(num) for num in rbg_dict.get(0, [])),
        "B": sorted(int(num) for num in rbg_dict.get(1, [])),
        "G": sorted(int(num) for num in rbg_dict.get(2, [])),
    }


def calc_prize_result(candidate_pool: list[int], nums: list[int], special_num: int) -> dict[str, Any]:
    """用生日候選池核對正號與特號，回傳獎項結果。"""

    pool_set = set(candidate_pool)
    main_hit_nums = sorted(set(nums) & pool_set)
    special_hit = int(special_num in pool_set)
    score = len(main_hit_nums) + (0.5 if special_hit else 0.0)
    prize_label = "未中獎"
    for prize_score in PRIZE_SCORES:
        if score >= prize_score:
            prize_label = PRIZE_LABELS[prize_score]
            break
    return {
        "main_hit_nums": main_hit_nums,
        "main_hit_count": len(main_hit_nums),
        "special_hit": special_hit,
        "score": score,
        "prize_label": prize_label,
    }


def collect_birthday_pool(
    df_all: pd.DataFrame,
    target_idx: int,
    window_draws: int,
    collect_limit: int,
    min_draw_birthday_count: int,
) -> tuple[list[int], int]:
    """
    從目標期之前最多 window_draws 期收集不重複生日號。

    由最近一期向前收集，收集到 collect_limit 個生日球就跳出。
    每一期 N1-N6+N7 的生日號數量要 >= min_draw_birthday_count 才納入候選。
    回傳：(生日號池, 實際使用期數)。
    """

    birthday_pool: list[int] = []
    used_nums = set()
    start_idx = max(0, target_idx - window_draws)
    used_draws = 0

    for idx in range(target_idx - 1, start_idx - 1, -1):
        row = df_all.iloc[idx]
        used_draws += 1
        seven_nums = get_main_nums(row) + [int(row["N7"])]
        seven_birthday_nums = get_birthday_nums(seven_nums)
        if len(seven_birthday_nums) < min_draw_birthday_count:
            continue
        for num in seven_birthday_nums:
            if num in used_nums:
                continue
            birthday_pool.append(num)
            used_nums.add(num)
            if len(birthday_pool) >= collect_limit:
                return sorted(birthday_pool), used_draws

    return sorted(birthday_pool), used_draws


def evaluate_birthday_pool_params(
    df_all: pd.DataFrame,
    backtest_draws: int,
    window_draws: int,
    collect_limit: int,
    min_draw_birthday_count: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """回測單組生日號池參數，回傳每期明細與統計。"""

    start_idx = max(window_draws, len(df_all) - backtest_draws)
    detail_rows: list[dict[str, Any]] = []
    hit_dist: Counter = Counter()
    prize_dist: Counter = Counter()
    total_hits = 0
    total_actual_birthday_nums = 0
    total_pool_size = 0

    for seq, target_idx in enumerate(range(start_idx, len(df_all)), start=1):
        target_row = df_all.iloc[target_idx]
        ndate = str(target_row["ndate"])
        nums = get_main_nums(target_row)
        special_num = int(target_row["N7"])
        actual_birthday_nums = get_birthday_nums(nums)

        birthday_pool, used_draws = collect_birthday_pool(
            df_all=df_all,
            target_idx=target_idx,
            window_draws=window_draws,
            collect_limit=collect_limit,
            min_draw_birthday_count=min_draw_birthday_count,
        )
        group_pool = group_birthday_pool(birthday_pool)
        rbg_pool = group_rbg_pool(birthday_pool)
        hit_nums = sorted(set(actual_birthday_nums) & set(birthday_pool))
        prize_result = calc_prize_result(birthday_pool, nums, special_num)

        total_hits += len(hit_nums)
        total_actual_birthday_nums += len(actual_birthday_nums)
        total_pool_size += len(birthday_pool)
        hit_dist.update([len(hit_nums)])
        prize_dist.update([prize_result["prize_label"]])

        detail_rows.append({
            "seq": seq,
            "target_date": ndate,
            "nums": nums,
            "special_num": special_num,
            "actual_birthday_nums": actual_birthday_nums,
            "actual_birthday_count": len(actual_birthday_nums),
            "birthday_pool": birthday_pool,
            "birthday_pool_count": len(birthday_pool),
            "group_pool": group_pool,
            "rbg_pool": rbg_pool,
            "used_draws": used_draws,
            "hit_nums": hit_nums,
            "hit_count": len(hit_nums),
            "main_hit_nums": prize_result["main_hit_nums"],
            "main_hit_count": prize_result["main_hit_count"],
            "special_hit": prize_result["special_hit"],
            "prize_score": prize_result["score"],
            "prize_label": prize_result["prize_label"],
        })

    total_cases = len(detail_rows)
    avg_hits = total_hits / total_cases if total_cases else 0
    coverage_rate = (
        total_hits / total_actual_birthday_nums
        if total_actual_birthday_nums
        else 0
    )
    avg_pool_size = total_pool_size / total_cases if total_cases else 0

    stats = {
        "backtest_draws": total_cases,
        "window_draws": window_draws,
        "collect_limit": collect_limit,
        "min_draw_birthday_count": min_draw_birthday_count,
        "total_hits": total_hits,
        "avg_hits": round(avg_hits, 4),
        "coverage_rate": round(coverage_rate, 4),
        "avg_pool_size": round(avg_pool_size, 4),
        "hit_dist": dict(sorted(hit_dist.items())),
        "prize_dist": dict(prize_dist),
    }
    return detail_rows, stats


def print_prize_summary(stats: dict[str, Any]) -> None:
    """打印生日號池獎項統計。"""

    prize_dist = Counter(stats.get("prize_dist", {}))
    print("\n====== 生日號池獎項統計 ======")
    for prize_score in PRIZE_SCORES:
        label = PRIZE_LABELS[prize_score]
        print(f">>> {label}: {prize_dist.get(label, 0)} 次")
    print(f">>> 未中獎: {prize_dist.get('未中獎', 0)} 次")


def choose_best_param(param_results: list[dict[str, Any]]) -> dict[str, Any]:
    """依命中率自動選最佳參數，平手取較小球池與較嚴入池條件。"""

    return max(
        param_results,
        key=lambda row: (
            row["stats"]["coverage_rate"],
            row["stats"]["avg_hits"],
            -row["stats"]["avg_pool_size"],
            row["stats"]["min_draw_birthday_count"],
            -row["stats"]["collect_limit"],
        ),
    )


def write_json(path: Path, data: dict[str, Any]) -> None:
    """寫出 JSON 回測參數結果。"""

    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def print_birthday_backtest(df_history: pd.DataFrame) -> Counter:
    """用簡單列表顯示每期生日號組，並回傳生日號頻率。"""

    birthday_counter: Counter = Counter()
    count_dist: Counter = Counter()

    print(f"====== 最近 {len(df_history)} 期生日號分析 ======")
    for idx, (_, row) in enumerate(df_history.iterrows(), start=1):
        ndate = str(row["ndate"])
        nums = get_main_nums(row)
        special_num = int(row["N7"])
        birthday_nums = get_birthday_nums(nums)
        birthday_counter.update(birthday_nums)
        count_dist.update([len(birthday_nums)])

        print(
            f"{idx:>2}, {ndate} {nums} {special_num},  "
            f"生日號組 : {birthday_nums} /> {len(birthday_nums)} 球"
        )

    return birthday_counter


def print_birthday_pool_backtest(
    df_all: pd.DataFrame,
    backtest_draws: int,
    window_draws: int,
    collect_limit: int,
    min_draw_birthday_count: int,
) -> dict[str, Any]:
    """回測生日號池，核對每個目標期的下期開號。"""

    detail_rows, stats = evaluate_birthday_pool_params(
        df_all=df_all,
        backtest_draws=backtest_draws,
        window_draws=window_draws,
        collect_limit=collect_limit,
        min_draw_birthday_count=min_draw_birthday_count,
    )

    print("\n====== 生日號分組球號池回測 ======")
    print(
        f"回測期數={stats['backtest_draws']}，窗口期={window_draws}，"
        f"集合生日球上限={collect_limit}，"
        f"入池條件=N1-N6+N7 生日號 >= {min_draw_birthday_count} 球"
    )

    for row in detail_rows:
        print(
            f"\n{row['seq']:>2}, {row['target_date']} {row['nums']} {row['special_num']},  "
            f"下期生日號組 : {row['actual_birthday_nums']} /> {row['actual_birthday_count']} 球"
        )
        print(f"   分組球號池 : {format_group_pool(row['group_pool'])}")
        print(f"   R: {row['rbg_pool']['R']} /> {len(row['rbg_pool']['R'])} 球")
        print(f"   B: {row['rbg_pool']['B']} /> {len(row['rbg_pool']['B'])} 球")
        print(f"   G: {row['rbg_pool']['G']} /> {len(row['rbg_pool']['G'])} 球")
        print(f"   核對命中 : {row['hit_nums']} /> {row['hit_count']} 球")
    return {"details": detail_rows, "stats": stats}


def run_param_grid_backtest(
    df_all: pd.DataFrame,
    backtest_draws: int,
    window_draws: int,
    collect_limits: list[int],
    min_draw_birthday_counts: list[int],
) -> dict[str, Any]:
    """跑多組生日號池參數，寫 JSON，並打印最佳參數。"""

    param_results = []
    for collect_limit in collect_limits:
        for min_count in min_draw_birthday_counts:
            details, stats = evaluate_birthday_pool_params(
                df_all=df_all,
                backtest_draws=backtest_draws,
                window_draws=window_draws,
                collect_limit=collect_limit,
                min_draw_birthday_count=min_count,
            )
            param_results.append({
                "params": {
                    "window_draws": window_draws,
                    "collect_limit": collect_limit,
                    "min_draw_birthday_count": min_count,
                },
                "stats": stats,
                "details": details,
            })

    best = choose_best_param(param_results)
    output = {
        "backtest_draws": backtest_draws,
        "window_draws": window_draws,
        "collect_limits": collect_limits,
        "min_draw_birthday_counts": min_draw_birthday_counts,
        "best": best,
        "param_results": param_results,
    }
    write_json(OUTPUT_JSON, output)

    return output


def parse_args() -> argparse.Namespace:
    """解析命令列參數。"""

    parser = argparse.ArgumentParser(description="每期生日號分析")
    parser.add_argument(
        "--backtest-draws",
        type=int,
        default=DEFAULT_BACKTEST_DRAW,
        help="最近回測期數，例如 --backtest-draws 24",
    )
    parser.add_argument(
        "--window-draws",
        type=int,
        default=DEFAULT_WINDOW_DRAW,
        help="回測窗口期，預設 14 期",
    )
    parser.add_argument(
        "--collect-limit",
        nargs="+",
        type=int,
        default=DEFAULT_COLLECT_LIMIT,
        help="集合生日球上限，可多個，例如 --collect-limit 15 20 23",
    )
    parser.add_argument(
        "--min-draw-birthday-count",
        nargs="+",
        type=int,
        default=DEFAULT_MIN_DRAW_BIRTHDAY_COUNT,
        help="窗口內單期 N1-N6+N7 至少幾個生日號才取入候選池，可多個，例如 4 5",
    )
    return parser.parse_args()


def main() -> None:
    """命令列入口。"""

    args = parse_args()
    df_all = load_lotto_history_prize()
    df_history = df_all.iloc[-args.backtest_draws:, :].reset_index(drop=True)
    print_birthday_backtest(df_history)
    param_result = run_param_grid_backtest(
        df_all=df_all,
        backtest_draws=args.backtest_draws,
        window_draws=args.window_draws,
        collect_limits=args.collect_limit,
        min_draw_birthday_counts=args.min_draw_birthday_count,
    )
    best_stats = param_result["best"]["stats"]
    final_result = print_birthday_pool_backtest(
        df_all=df_all,
        backtest_draws=args.backtest_draws,
        window_draws=args.window_draws,
        collect_limit=best_stats["collect_limit"],
        min_draw_birthday_count=best_stats["min_draw_birthday_count"],
    )
    print_prize_summary(final_result["stats"])


if __name__ == "__main__":
    main()
