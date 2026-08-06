#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
N1-N6 區間 + RBG 顏色規則回測及預測。

輸出重點：
預測：[0,2,3,3,4,4] + [r,r,r,b,b,g]
實際：[0,1,1,2,3,4] + [r,r,b,b,g,g]
/> 區間位置命中2，區間數量命中4，RBG數量命中：R2,B2,G1 / 共5，RBG位置命中：R2,B1,G1 / 共4
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import res_func_num_convert_RBG_Dict


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CURRENT_DIR = Path(__file__).resolve().parent
DATA_PATH = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M2_last_upgrade_lotto_data.csv"
OUTPUT_DIR = CURRENT_DIR / "rbg_data"

DEFAULT_WINDOWS = [6, 7, 8, 9,10]
DEFAULT_BACKTEST_DRAWS = 30
DEFAULT_TOP_N = 5
INTERVAL_IDS = [0, 1, 2, 3, 4]
RBG_LABELS = {1: "R", 2: "B", 3: "G"}
PRIZE_SCORES = [6.0, 5.5, 5.0, 4.5, 4.0, 3.5, 3.0]
PRIZE_LABELS = {
    6.0: "一獎  6 正號      ",
    5.5: "二獎  5 正 + 特別號",
    5.0: "三獎  5 正號      ",
    4.5: "四獎  4 正 + 特別號",
    4.0: "五獎  4 正號      ",
    3.5: "六獎  3 正 + 特別號",
    3.0: "七獎  3 正號      ",
}


@dataclass(frozen=True)
class DrawRow:
    """單期開獎資料：6 個正號加 1 個特號。"""

    ndate: str
    nums: list[int]
    special: int


def load_draw_rows(path: Path = DATA_PATH) -> list[DrawRow]:
    """讀取 M2 開獎歷史，只保留日期、N1-N6 正號及 N7 特號。"""

    rows: list[DrawRow] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                nums = [int(row[f"N{i}"]) for i in range(1, 7)]
                special = int(row["N7"])
            except (KeyError, TypeError, ValueError):
                continue
            if len(nums) == 6 and all(1 <= n <= 49 for n in nums):
                rows.append(DrawRow(str(row["ndate"]).strip(), nums, special))
    return rows


def get_num49_interval_map(nums: list[int]) -> list[int]:
    """
    將 1-49 號碼轉成區間編號。

    區間定義：
    0 = 1-10
    1 = 11-20
    2 = 21-30
    3 = 31-40
    4 = 41-49
    """

    result = []
    for num in nums:
        if 1 <= num <= 10:
            result.append(0)
        elif 11 <= num <= 20:
            result.append(1)
        elif 21 <= num <= 30:
            result.append(2)
        elif 31 <= num <= 40:
            result.append(3)
        elif 41 <= num <= 49:
            result.append(4)
    return result


def get_rbg_rule(nums: list[int]) -> list[str]:
    """
    將號碼轉成 RBG 顏色位置規則。

    沿用 res_func_num_convert_RBG_Dict.py：
    1 = Red  -> R
    2 = Blue -> B
    3 = Green -> G
    """

    rbg_ids = res_func_num_convert_RBG_Dict.res_list_to_RBG123_list_func(nums)
    return [RBG_LABELS.get(int(color_id), "?") for color_id in rbg_ids]


def build_global_candidate_pools(pred_interval: list[int], pred_rbg: list[str]) -> list[list[int]]:
    """
    依照「區間 + RBG」規則，從 1-49 全域球號建立 6 個位置候選池。

    例如 P1 規則是 interval=0 且 rbg=r，
    就把所有 1-49 中符合這兩個條件的號碼放入 P1 候選池。
    """

    candidate_pools: list[list[int]] = []
    for interval_id, color in zip(pred_interval, pred_rbg):
        candidates = []
        for num in range(1, 50):
            num_interval = get_num49_interval_map([num])[0]
            num_color = get_rbg_rule([num])[0]
            if num_interval == interval_id and num_color == color:
                candidates.append(num)
        candidate_pools.append(candidates)
    return candidate_pools


def candidate_pools_display(candidate_pools: list[list[int]]) -> str:
    """將 6 個位置候選池整理成 P1:[...] | P2:[...] 格式。"""

    return " | ".join(
        f"P{idx}:{list_display(candidates)}"
        for idx, candidates in enumerate(candidate_pools, start=1)
    )


def candidate_pool_counts_display(candidate_pools: list[list[int]]) -> str:
    """只顯示 P1-P6 每個候選池的球號數量。"""

    total_count = sum(len(candidates) for candidates in candidate_pools)
    unique_count = len({num for candidates in candidate_pools for num in candidates})
    counts = "，".join(
        f"P{idx}={len(candidates)}球"
        for idx, candidates in enumerate(candidate_pools, start=1)
    )
    return f"{counts} / 合共{total_count}球，不重複{unique_count}球"


def candidate_pool_hits(candidate_pools: list[list[int]], actual_nums: list[int]) -> tuple[list[int], int, list[str]]:
    """
    計算全域候選池命中。

    pool_hit_nums：只要實際號碼出現在任何一個位置候選池，就算候選池覆蓋命中。
    position_hit_labels：實際 N1 對 P1、N2 對 P2，逐位置命中才記錄。
    """

    all_candidates = set()
    for candidates in candidate_pools:
        all_candidates.update(candidates)

    pool_hit_nums = [num for num in actual_nums if num in all_candidates]
    position_hit_labels = []
    for idx, (actual_num, candidates) in enumerate(zip(actual_nums, candidate_pools), start=1):
        if actual_num in candidates:
            position_hit_labels.append(f"P{idx}={actual_num}")
    return pool_hit_nums, len(position_hit_labels), position_hit_labels


def score_candidate_balls(history_rows: list[DrawRow], window: int) -> tuple[Counter, list[Counter]]:
    """
    根據最近 window 期建立候選球分數。

    total_counter：號碼在最近 window 期 N1-N6 出現次數。
    position_counters：號碼在相同位置 P1-P6 出現次數。
    """

    total_counter: Counter = Counter()
    position_counters = [Counter() for _ in range(6)]
    for row in history_rows[-window:]:
        for idx, num in enumerate(row.nums):
            total_counter.update([num])
            position_counters[idx].update([num])
    return total_counter, position_counters


def build_single_bet_from_candidates(
    candidate_pools: list[list[int]],
    history_rows: list[DrawRow],
    window: int,
) -> list[int]:
    """
    從 6 個位置候選池中建立一注單式 6 球。

    選球規則：
    1. 同位置近期出現次數 * 3
    2. 全部位置近期出現次數 * 1
    3. 不重複選球
    4. 同分選較小號碼
    """

    total_counter, position_counters = score_candidate_balls(history_rows, window)
    selected = []
    used = set()

    for idx, candidates in enumerate(candidate_pools):
        ranked = sorted(
            candidates,
            key=lambda num: (
                -(position_counters[idx].get(num, 0) * 3 + total_counter.get(num, 0)),
                num,
            ),
        )
        pick = next((num for num in ranked if num not in used), None)
        if pick is None:
            pick = next((num for num in range(1, 50) if num not in used), 0)
        selected.append(pick)
        used.add(pick)

    return sorted(selected)


def single_bet_hits(single_bet: list[int], actual_nums: list[int]) -> tuple[list[int], int]:
    """計算一注單式與實際 N1-N6 正號命中。"""

    hit_nums = sorted(set(single_bet) & set(actual_nums))
    return hit_nums, len(hit_nums)


def calc_prize_result(single_bet: list[int], actual_nums: list[int], special_num: int) -> dict[str, Any]:
    """
    計算單式投注獎項。

    正號命中每球 1 分，特別號命中加 0.5 分。
    例如 5 正 + 特別號 = 5.5 分 = 二獎。
    """

    main_hit_nums, main_hit_count = single_bet_hits(single_bet, actual_nums)
    special_hit = int(special_num in set(single_bet))
    score = main_hit_count + (0.5 if special_hit else 0.0)
    prize_label = "未中獎"
    for prize_score in PRIZE_SCORES:
        if score >= prize_score:
            prize_label = PRIZE_LABELS[prize_score]
            break
    return {
        "main_hit_nums": main_hit_nums,
        "main_hit_count": main_hit_count,
        "special_hit": special_hit,
        "score": score,
        "prize_label": prize_label,
    }


def build_interval_transition(interval_sequences: list[list[int]]) -> dict[int, dict[int, int]]:
    """建立區間轉移表：上一期出現過的區間，下一期通常轉到哪些區間。"""

    transition: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for idx in range(len(interval_sequences) - 1):
        current_seq = interval_sequences[idx]
        next_seq = interval_sequences[idx + 1]
        for cur_zone in set(current_seq):
            for next_zone in set(next_seq):
                transition[cur_zone][next_zone] += 1
    return transition


def score_next_intervals(
    transition: dict[int, dict[int, int]],
    current_seq: list[int],
    alpha: float = 1.0,
) -> dict[int, float]:
    """根據當期區間及轉移表，計算下一期各區間分數。"""

    score: dict[int, float] = defaultdict(float)
    for cur_zone in set(current_seq):
        row = transition.get(cur_zone, {})
        total = sum(row.values()) + alpha * len(INTERVAL_IDS)
        for next_zone in INTERVAL_IDS:
            score[next_zone] += (row.get(next_zone, 0) + alpha) / total
    return score


def build_pred_interval_rule(history_rows: list[DrawRow], window: int) -> list[int]:
    """
    用最近 window 期建立下一期區間預測規則。

    目前沿用既有區間策略：
    - 固定加入頭尾區間 0 和 4
    - 中間 4 個位置取分數最高的區間
    - 最後排序成 6 個區間 pattern
    """

    window_rows = history_rows[-window:]
    interval_sequences = [get_num49_interval_map(row.nums) for row in window_rows]
    if len(interval_sequences) < 2:
        return []

    transition = build_interval_transition(interval_sequences)
    score = score_next_intervals(transition, interval_sequences[-1])
    sorted_zones = [
        zone for zone, _ in sorted(score.items(), key=lambda item: item[1], reverse=True)
    ]
    middle_pred = (sorted_zones * 4)[:4] if len(sorted_zones) < 4 else sorted_zones[:4]
    return sorted([0, *middle_pred, 4])


def build_pred_rbg_rule(history_rows: list[DrawRow], window: int) -> list[str]:
    """
    用最近 window 期預測 6 個位置的 RBG 顏色。

    每個位置分開統計，例如 N1 位置最近最常出 r/b/g 哪一色，
    就用該色作為下一期 N1 的預測顏色。
    """

    window_rows = history_rows[-window:]
    position_counters = [Counter() for _ in range(6)]
    for row in window_rows:
        rule = get_rbg_rule(row.nums)
        for idx, color in enumerate(rule):
            position_counters[idx].update([color])

    pred = []
    for counter in position_counters:
        if counter:
            pred.append(counter.most_common(1)[0][0])
        else:
            pred.append("r")
    return pred


def count_hits_by_position(pred: list[Any], actual: list[Any]) -> int:
    """逐位置計算命中數，例如 N1 對 N1、N2 對 N2。"""

    return sum(1 for p, a in zip(pred, actual) if p == a)


def count_hits_by_quantity(pred: list[Any], actual: list[Any]) -> int:
    """用數量集合計算命中數，不理會位置，只看各類別出現次數。"""

    return sum((Counter(pred) & Counter(actual)).values())


def rbg_quantity_hits(pred: list[str], actual: list[str]) -> dict[str, int]:
    """計算 R/B/G 三色各自的數量命中。"""

    common = Counter(pred) & Counter(actual)
    return {color: common.get(color, 0) for color in ["r", "b", "g"]}


def rbg_position_hits(pred: list[str], actual: list[str]) -> dict[str, int]:
    """計算 R/B/G 三色各自的逐位置命中。"""

    hits = {"r": 0, "b": 0, "g": 0}
    for pred_color, actual_color in zip(pred, actual):
        if pred_color == actual_color and actual_color in hits:
            hits[actual_color] += 1
    return hits


def list_display(values: list[Any]) -> str:
    """統一輸出成 [0,1,2] 或 [r,b,g] 這類易讀格式。"""

    return "[" + ",".join(str(v) for v in values) + "]"


def build_summary_text(
    pred_interval: list[int],
    actual_interval: list[int],
    pred_rbg: list[str],
    actual_rbg: list[str],
    candidate_pools: list[list[int]] | None = None,
    actual_nums: list[int] | None = None,
    single_bet: list[int] | None = None,
    special_num: int | None = None,
) -> str:
    """建立每一期回測明細文字，方便直接閱讀預測與實際差異。"""

    interval_pos_hits = count_hits_by_position(pred_interval, actual_interval)
    interval_qty_hits = count_hits_by_quantity(pred_interval, actual_interval)
    rbg_qty = rbg_quantity_hits(pred_rbg, actual_rbg)
    rbg_pos = rbg_position_hits(pred_rbg, actual_rbg)
    rbg_qty_total = sum(rbg_qty.values())
    rbg_pos_total = sum(rbg_pos.values())
    text = (
        f"預測：{list_display(pred_interval)} + {list_display(pred_rbg)}\n"
        f"實際：{list_display(actual_interval)} + {list_display(actual_rbg)} "
        f"/> 區間位置命中{interval_pos_hits}，區間數量命中{interval_qty_hits}，"
        f"RBG數量命中：R{rbg_qty['r']},B{rbg_qty['b']},G{rbg_qty['g']} / 共{rbg_qty_total}，"
        f"RBG位置命中：R{rbg_pos['r']},B{rbg_pos['b']},G{rbg_pos['g']} / 共{rbg_pos_total}"
    )
    if candidate_pools is not None and actual_nums is not None:
        pool_hit_nums, position_hit_count, position_hit_labels = candidate_pool_hits(candidate_pools, actual_nums)
        text += (
            f"\n候選池：{candidate_pools_display(candidate_pools)}"
            f"\n候選池球數：{candidate_pool_counts_display(candidate_pools)}"
            f"\n候選池命中：{list_display(pool_hit_nums)} / 共{len(pool_hit_nums)}，"
            f"位置命中：{position_hit_count} ({','.join(position_hit_labels) or '-'})"
        )
    if single_bet is not None and actual_nums is not None:
        single_hit_nums, single_hit_count = single_bet_hits(single_bet, actual_nums)
        text += (
            f"\n單式投注：{list_display(single_bet)} "
            f"/> 命中號碼：{list_display(single_hit_nums)} / 共{single_hit_count}"
        )
        if special_num is not None:
            prize = calc_prize_result(single_bet, actual_nums, special_num)
            text += (
                f"，特號命中：{prize['special_hit']}，"
                f"score={prize['score']:.1f}，獎項：{prize['prize_label']}"
            )
    return text


def backtest_window(rows: list[DrawRow], window: int, backtest_draws: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    回測單一窗口期。

    對最近 backtest_draws 期逐期回測：
    1. 只用目標期之前的歷史資料預測
    2. 產生區間規則和 RBG 位置規則
    3. 對比目標期實際開獎
    4. 累計位置命中、數量命中及 exact hit 統計
    """

    start_idx = max(window, len(rows) - backtest_draws)
    detail_rows = []
    totals = Counter()

    for target_idx in range(start_idx, len(rows)):
        history_rows = rows[:target_idx]
        target_row = rows[target_idx]

        pred_interval = build_pred_interval_rule(history_rows, window)
        pred_rbg = build_pred_rbg_rule(history_rows, window)
        actual_interval = get_num49_interval_map(target_row.nums)
        actual_rbg = get_rbg_rule(target_row.nums)

        if len(pred_interval) != 6 or len(pred_rbg) != 6:
            continue

        interval_pos_hits = count_hits_by_position(pred_interval, actual_interval)
        interval_qty_hits = count_hits_by_quantity(pred_interval, actual_interval)
        rbg_qty = rbg_quantity_hits(pred_rbg, actual_rbg)
        rbg_pos = rbg_position_hits(pred_rbg, actual_rbg)
        rbg_qty_total = sum(rbg_qty.values())
        rbg_pos_total = sum(rbg_pos.values())
        candidate_pools = build_global_candidate_pools(pred_interval, pred_rbg)
        single_bet = build_single_bet_from_candidates(candidate_pools, history_rows, window)
        pool_hit_nums, candidate_pos_hits, candidate_pos_labels = candidate_pool_hits(
            candidate_pools,
            target_row.nums,
        )
        single_hit_nums, single_hit_count = single_bet_hits(single_bet, target_row.nums)
        prize_result = calc_prize_result(single_bet, target_row.nums, target_row.special)

        totals["trials"] += 1
        totals["interval_pos_hits"] += interval_pos_hits
        totals["interval_qty_hits"] += interval_qty_hits
        totals["rbg_qty_hits"] += rbg_qty_total
        totals["rbg_pos_hits"] += rbg_pos_total
        totals["candidate_pool_hits"] += len(pool_hit_nums)
        totals["candidate_pos_hits"] += candidate_pos_hits
        totals["single_bet_hits"] += single_hit_count
        totals["single_bet_3plus_hits"] += int(single_hit_count >= 3)
        totals["single_bet_prize_hits"] += int(prize_result["prize_label"] != "未中獎")
        totals[f"prize_label::{prize_result['prize_label']}"] += 1
        totals[f"score::{prize_result['score']:.1f}"] += 1
        totals["interval_exact_hits"] += int(pred_interval == actual_interval)
        totals["rbg_qty_exact_hits"] += int(Counter(pred_rbg) == Counter(actual_rbg))
        totals["rbg_pos_exact_hits"] += int(pred_rbg == actual_rbg)

        detail_rows.append({
            "target_date": target_row.ndate,
            "window": window,
            "actual_nums": list_display(target_row.nums),
            "actual_special": target_row.special,
            "pred_interval_rule": list_display(pred_interval),
            "actual_interval_rule": list_display(actual_interval),
            "candidate_pools": candidate_pools_display(candidate_pools),
            "candidate_pool_counts": candidate_pool_counts_display(candidate_pools),
            "candidate_pool_hit_nums": list_display(pool_hit_nums),
            "candidate_pool_hits_total": len(pool_hit_nums),
            "candidate_position_hits": candidate_pos_hits,
            "candidate_position_hit_labels": ",".join(candidate_pos_labels),
            "single_bet_nums": list_display(single_bet),
            "single_bet_hit_nums": list_display(single_hit_nums),
            "single_bet_hits_total": single_hit_count,
            "single_bet_special_hit": prize_result["special_hit"],
            "single_bet_score": f"{prize_result['score']:.1f}",
            "single_bet_prize_label": prize_result["prize_label"],
            "interval_pos_hits": interval_pos_hits,
            "interval_qty_hits": interval_qty_hits,
            "pred_rbg_rule": list_display(pred_rbg),
            "actual_rbg_rule": list_display(actual_rbg),
            "rbg_qty_hit_R": rbg_qty["r"],
            "rbg_qty_hit_B": rbg_qty["b"],
            "rbg_qty_hit_G": rbg_qty["g"],
            "rbg_qty_hits_total": rbg_qty_total,
            "rbg_pos_hit_R": rbg_pos["r"],
            "rbg_pos_hit_B": rbg_pos["b"],
            "rbg_pos_hit_G": rbg_pos["g"],
            "rbg_pos_hits_total": rbg_pos_total,
            "summary_text": build_summary_text(
                pred_interval,
                actual_interval,
                pred_rbg,
                actual_rbg,
                candidate_pools=candidate_pools,
                actual_nums=target_row.nums,
                single_bet=single_bet,
                special_num=target_row.special,
            ),
        })

    trials = totals["trials"] or 1
    stats = {
        "window": window,
        "trials": totals["trials"],
        "avg_interval_pos_hits": round(totals["interval_pos_hits"] / trials, 4),
        "avg_interval_qty_hits": round(totals["interval_qty_hits"] / trials, 4),
        "avg_rbg_qty_hits": round(totals["rbg_qty_hits"] / trials, 4),
        "avg_rbg_pos_hits": round(totals["rbg_pos_hits"] / trials, 4),
        "avg_candidate_pool_hits": round(totals["candidate_pool_hits"] / trials, 4),
        "avg_candidate_position_hits": round(totals["candidate_pos_hits"] / trials, 4),
        "avg_single_bet_hits": round(totals["single_bet_hits"] / trials, 4),
        "single_bet_3plus_hits": totals["single_bet_3plus_hits"],
        "single_bet_3plus_hit_rate": round(totals["single_bet_3plus_hits"] / trials, 4),
        "single_bet_prize_hits": totals["single_bet_prize_hits"],
        "single_bet_prize_hit_rate": round(totals["single_bet_prize_hits"] / trials, 4),
        "interval_exact_hits": totals["interval_exact_hits"],
        "interval_exact_hit_rate": round(totals["interval_exact_hits"] / trials, 4),
        "rbg_qty_exact_hits": totals["rbg_qty_exact_hits"],
        "rbg_qty_exact_hit_rate": round(totals["rbg_qty_exact_hits"] / trials, 4),
        "rbg_pos_exact_hits": totals["rbg_pos_exact_hits"],
        "rbg_pos_exact_hit_rate": round(totals["rbg_pos_exact_hits"] / trials, 4),
    }
    prize_stats = {}
    for prize_score in PRIZE_SCORES:
        label = PRIZE_LABELS[prize_score]
        hits = totals[f"prize_label::{label}"]
        prize_stats[label.strip()] = {
            "hits": hits,
            "hit_rate": round(hits / trials, 4),
        }
    no_prize_hits = totals["prize_label::未中獎"]
    prize_stats["未中獎"] = {
        "hits": no_prize_hits,
        "hit_rate": round(no_prize_hits / trials, 4),
    }
    stats["prize_stats"] = prize_stats
    score_stats = {}
    for prize_score in PRIZE_SCORES:
        score_key = f"{prize_score:.1f}"
        score_stats[score_key] = totals[f"score::{score_key}"]
    stats["score_stats"] = score_stats
    stats["combined_avg_score"] = round(
        stats["avg_interval_qty_hits"]
        + stats["avg_rbg_qty_hits"]
        + stats["avg_rbg_pos_hits"]
        + stats["avg_candidate_pool_hits"],
        4,
    )
    return detail_rows, stats


def choose_best_window(window_stats: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """
    自動選擇最佳窗口期。

    排序優先：
    1. combined_avg_score 越高越好
    2. RBG 位置平均命中越高越好
    3. 區間數量平均命中越高越好
    4. 平手時選較短窗口
    """

    best_key, best_stats = max(
        window_stats.items(),
        key=lambda item: (
            item[1]["combined_avg_score"],
            item[1]["avg_rbg_pos_hits"],
            item[1]["avg_interval_qty_hits"],
            -int(item[0]),
        ),
    )
    return {
        "metric": "combined_avg_score",
        "window": int(best_key),
        **best_stats,
    }


def calc_next_draw_date(last_date: str) -> str:
    """根據最後一期日期推算下一個 Tue/Thu/Sat 開獎日。"""

    dt = datetime.strptime(last_date, "%Y-%m-%d") + timedelta(days=1)
    while dt.isoweekday() not in {2, 4, 6}:
        dt += timedelta(days=1)
    return dt.strftime("%Y-%m-%d")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    """寫出 CSV，供之後檢查回測明細或接其他程式使用。"""

    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, data: dict[str, Any]) -> None:
    """寫出 JSON 統計，保留最佳窗口和各窗口回測結果。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def write_text(path: Path, text: str) -> None:
    """寫出純文字回測報告，方便直接打開閱讀每期結果。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_backtest_report(
    detail_rows: list[dict[str, Any]],
    selected_window: int,
    best: dict[str, Any],
    latest_prediction: dict[str, Any],
) -> str:
    """建立最佳窗口的每期回測報告。"""

    lines = [
        "區間 + RBG 每期回測結果",
        "=" * 60,
        f"最佳窗口：{selected_window}",
        f"combined_avg_score：{best['combined_avg_score']}",
        f"平均區間數量命中：{best['avg_interval_qty_hits']}",
        f"平均 RBG 數量命中：{best['avg_rbg_qty_hits']}",
        f"平均 RBG 位置命中：{best['avg_rbg_pos_hits']}",
        f"平均候選池命中：{best['avg_candidate_pool_hits']}",
        f"平均候選位置命中：{best['avg_candidate_position_hits']}",
        f"平均單式命中：{best['avg_single_bet_hits']}",
        f"單式 3+ 命中率：{best['single_bet_3plus_hit_rate']}",
        f"單式獎項命中率：{best['single_bet_prize_hit_rate']}",
        f"下期預測：{latest_prediction['rule_display']}",
        f"下期候選池：{latest_prediction['candidate_pools']}",
        f"下期候選池球數：{latest_prediction['candidate_pool_counts']}",
        f"下期單式：{latest_prediction['single_bet_nums']}",
        "",
    ]

    for idx, row in enumerate(detail_rows, start=1):
        lines.append(f">>> 第 {idx} 期 {row['target_date']} | window={row['window']} | 開獎號碼={row['actual_nums']}")
        lines.append(str(row["summary_text"]))
        lines.append("-" * 60)

    lines.extend([
        "",
        "單式 score 中獎統計",
        "=" * 60,
    ])
    score_stats = best.get("score_stats", {})
    for prize_score in PRIZE_SCORES:
        score_key = f"{prize_score:.1f}"
        score_display = str(int(prize_score)) if prize_score.is_integer() else score_key
        lines.append(f"{score_display:<4} = {score_stats.get(score_key, 0)} 次")

    return "\n".join(lines) + "\n"


def run(windows: list[int], backtest_draws: int, top_n: int) -> None:
    """
    主流程：跑多窗口回測、選最佳窗口、產生下一期預測及輸出檔案。

    top_n 暫時保留給下一版 TopN pattern 使用；目前第一版只輸出最佳窗口的一組規則。
    """

    rows = load_draw_rows()
    if len(rows) < max(windows) + 2:
        raise RuntimeError("歷史資料不足，不能回測。")

    all_detail_rows = []
    window_stats = {}
    for window in windows:
        detail_rows, stats = backtest_window(rows, window, backtest_draws)
        all_detail_rows.extend(detail_rows)
        window_stats[str(window)] = stats

    best = choose_best_window(window_stats)
    selected_window = int(best["window"])
    pred_interval = build_pred_interval_rule(rows, selected_window)
    pred_rbg = build_pred_rbg_rule(rows, selected_window)
    next_candidate_pools = build_global_candidate_pools(pred_interval, pred_rbg)
    next_single_bet = build_single_bet_from_candidates(next_candidate_pools, rows, selected_window)
    next_draw_date = calc_next_draw_date(rows[-1].ndate)

    latest_prediction = {
        "next_draw_date": next_draw_date,
        "selected_window": selected_window,
        "pred_interval_rule": list_display(pred_interval),
        "pred_rbg_rule": list_display(pred_rbg),
        "rule_display": f"{list_display(pred_interval)} + {list_display(pred_rbg)}",
        "candidate_pools": candidate_pools_display(next_candidate_pools),
        "candidate_pool_counts": candidate_pool_counts_display(next_candidate_pools),
        "single_bet_nums": list_display(next_single_bet),
    }
    stats_json = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "windows_tested": windows,
        "backtest_draws": backtest_draws,
        "top_n": top_n,
        "best": best,
        "window_stats": window_stats,
        "latest_prediction": latest_prediction,
    }

    selected_params = {
        "selected_window": selected_window,
        "metric": best["metric"],
        "combined_avg_score": best["combined_avg_score"],
        "avg_interval_qty_hits": best["avg_interval_qty_hits"],
        "avg_rbg_qty_hits": best["avg_rbg_qty_hits"],
        "avg_rbg_pos_hits": best["avg_rbg_pos_hits"],
        "avg_candidate_pool_hits": best["avg_candidate_pool_hits"],
        "avg_candidate_position_hits": best["avg_candidate_position_hits"],
        "avg_single_bet_hits": best["avg_single_bet_hits"],
        "single_bet_3plus_hit_rate": best["single_bet_3plus_hit_rate"],
        "single_bet_prize_hit_rate": best["single_bet_prize_hit_rate"],
        "prize_stats": best["prize_stats"],
        "score_stats": best["score_stats"],
    }

    next_row = {
        "next_draw_date": next_draw_date,
        "selected_window": selected_window,
        "pred_interval_rule": list_display(pred_interval),
        "pred_rbg_rule": list_display(pred_rbg),
        "rule_display": latest_prediction["rule_display"],
        "candidate_pools": candidate_pools_display(next_candidate_pools),
        "candidate_pool_counts": candidate_pool_counts_display(next_candidate_pools),
        "single_bet_nums": list_display(next_single_bet),
    }
    for idx, candidates in enumerate(next_candidate_pools, start=1):
        next_row[f"P{idx}_candidates"] = list_display(candidates)
    next_rows = [next_row]
    selected_detail_rows = [
        row for row in all_detail_rows if int(row["window"]) == selected_window
    ]
    report_text = build_backtest_report(
        selected_detail_rows,
        selected_window=selected_window,
        best=best,
        latest_prediction=latest_prediction,
    )

    write_csv(OUTPUT_DIR / "interval_RBG_backtest.csv", all_detail_rows)
    write_csv(OUTPUT_DIR / "interval_RBG_best_window_backtest.csv", selected_detail_rows)
    write_csv(OUTPUT_DIR / "interval_RBG_nextDraw_pred.csv", next_rows)
    write_json(OUTPUT_DIR / "interval_RBG_window_stats.json", stats_json)
    write_json(OUTPUT_DIR / "interval_RBG_selected_params.json", selected_params)
    write_text(OUTPUT_DIR / "interval_RBG_best_window_backtest_report.txt", report_text)

    print("/> 區間 + RBG 回測及預測完成")
    print(f"/> 測試窗口：{windows}")
    print(f"/> 最佳窗口：{selected_window} / combined_avg_score={best['combined_avg_score']}")
    print(f"/> 下期日期：{next_draw_date}")
    print(f"/> 下期預測：{latest_prediction['rule_display']}")
    print(f"/> 下期候選池：{latest_prediction['candidate_pools']}")
    print(f"/> 下期候選池球數：{latest_prediction['candidate_pool_counts']}")
    print(f"/> 下期單式：{latest_prediction['single_bet_nums']}")
    print("\n/> 最佳窗口每期回測結果：")
    print(report_text)
    print(f"/> 輸出目錄：{OUTPUT_DIR}")


def parse_args() -> argparse.Namespace:
    """解析命令列參數，讓窗口期和回測期數可以自由調整。"""

    parser = argparse.ArgumentParser(description="N1-N6 區間 + RBG 顏色規則回測及預測")
    parser.add_argument("--windows", nargs="+", type=int, default=DEFAULT_WINDOWS, help="回測窗口，例如 --windows 7 8 9")
    parser.add_argument("--backtest-draws", type=int, default=DEFAULT_BACKTEST_DRAWS, help="最近回測期數")
    parser.add_argument("--top-n", type=int, default=DEFAULT_TOP_N, help="保留參數，供後續 TopN pattern 使用")
    return parser.parse_args()


def main() -> None:
    """命令列入口。"""

    args = parse_args()
    run(windows=args.windows, backtest_draws=args.backtest_draws, top_n=args.top_n)


if __name__ == "__main__":
    main()
