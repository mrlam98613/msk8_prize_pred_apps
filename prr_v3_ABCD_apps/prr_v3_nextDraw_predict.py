from __future__ import annotations

from datetime import datetime
from pathlib import Path
import csv
import sys
from typing import TypedDict


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from prr_v3_ABCD_apps import ppr_v3_once_backtest_mode as engine  # noqa: E402
from prr_v3_ABCD_apps import prr_v3_range_backtest_mode as range_backtest  # noqa: E402


BET_PRED_DIR = CURRENT_DIR / "bet_pred_data"
BET_PRED_POOLS_CSV = BET_PRED_DIR / "bet_pred_pools.csv"
SUMMARY_SCORE_VALUES = [6.0, 5.5, 5.0, 4.5, 4.0, 3.5, 3.0]
SECTION_LINE = "-----------------------------------------------------------"
AUTO_RUN_RANGE_BACKTEST_BEFORE_PREDICT = True


class GroupAnalysisRow(TypedDict):
    code: str
    name: str
    quota: int
    hot_nums: list[int]
    final_nums: list[int]
    dan_nums: list[int]
    partner_nums: list[int]
    weak_nums: list[int]


def to_float(value: object, default: float = 0.0) -> float:
    """安全轉換 JSON / CSV 讀入的數值。"""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def weekday_text(date_text: str) -> str:
    """把 YYYY-MM-DD 轉成中文星期文字。"""
    try:
        weekday_index = datetime.strptime(date_text, "%Y-%m-%d").weekday()
    except ValueError:
        return ""
    return ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][weekday_index]


def format_date_with_weekday(date_text: str) -> str:
    """格式化日期與星期。"""
    weekday = weekday_text(date_text)
    return f"{date_text}  ({weekday})" if weekday else date_text


def range_backtest_period_text(draws: list[engine.DrawRow]) -> str:
    """格式化 range backtest 實際核對日期範圍。"""
    latest_index = len(draws) - 1
    start_index = latest_index - range_backtest.RANGE_BACKTEST_FROM + 1
    end_index = latest_index - range_backtest.RANGE_BACKTEST_TO + 1
    if start_index < 0 or end_index < 0 or start_index >= len(draws) or end_index >= len(draws):
        return "資料總回測期 ＝資料不足"
    period_count = range_backtest.RANGE_BACKTEST_FROM - range_backtest.RANGE_BACKTEST_TO + 1
    return f"資料總回測期 ＝{period_count} 期 ，{draws[start_index]['date']} 至 {draws[end_index]['date']}"


def reset_bet_pred_pools_csv() -> None:
    """建立真實下期預測投注池 CSV。"""
    BET_PRED_DIR.mkdir(parents=True, exist_ok=True)
    with BET_PRED_POOLS_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "date",
            "pool_name",
            "window_count",
            "A(1-9)",
            "B(10-20)",
            "C(21-31)",
            "D(32-40)",
            "candidate_pool",
            "count",
        ])


def refresh_range_backtest_window_csvs() -> None:
    """預測前先執行 range backtest，更新窗口期命中 CSV。"""
    if not AUTO_RUN_RANGE_BACKTEST_BEFORE_PREDICT:
        return
    range_backtest.configure_engine_for_range()
    draws = engine.read_draws()
    if not draws:
        raise FileNotFoundError(f"找不到或未能讀取 M6：{engine.M6_CSV}")
    latest_draw_date = draws[-1]["date"]
    if not range_backtest.range_backtest_needs_update(draws):
        print(f"====== range backtest 已是最新，最後開獎日期：{latest_draw_date}，略過更新 ======")
        print()
        return
    print("====== 先執行 range backtest，更新窗口期 CSV ======")
    range_backtest.run_range_backtest(verbose=False)
    print("====== range backtest 更新完成，開始真實下期預測 ======")
    print()


def append_bet_pred_pool(
    next_draw_date: str,
    pool_name: str,
    window_count: int,
    candidate_pool: list[int],
) -> None:
    """追加一組下期投注候選池。"""
    with BET_PRED_POOLS_CSV.open("a", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            next_draw_date,
            pool_name,
            window_count,
            engine.format_nums(engine.nums_in_range(candidate_pool, 1, 9)),
            engine.format_nums(engine.nums_in_range(candidate_pool, 10, 20)),
            engine.format_nums(engine.nums_in_range(candidate_pool, 21, 31)),
            engine.format_nums(engine.nums_in_range(candidate_pool, 32, 40)),
            engine.format_nums(sorted(candidate_pool)),
            len(candidate_pool),
        ])


def read_window_hit_summary(path: Path) -> tuple[list[int], dict[float, dict[int, int]]]:
    """讀取 range backtest 的窗口期命中累積表。"""
    if not path.exists():
        return [], {}

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        window_counts = [
            int(fieldname.removeprefix("window_"))
            for fieldname in fieldnames
            if fieldname.startswith("window_") and fieldname.removeprefix("window_").isdigit()
        ]
        rows: dict[float, dict[int, int]] = {}
        for row in reader:
            hit_count = engine.to_int(row.get("hit_count"), default=-1)
            raw_hit_count = str(row.get("hit_count", "")).strip()
            try:
                hit_value = float(raw_hit_count)
            except ValueError:
                hit_value = float(hit_count)
            if hit_value < 0:
                continue
            rows[hit_value] = {
                window_count: engine.to_int(row.get(f"window_{window_count}"))
                for window_count in window_counts
            }
    return window_counts, rows


def score_window_summary(
    window_counts: list[int],
    rows: dict[float, dict[int, int]],
) -> dict[int, float]:
    """用命中球數作權重，計算每個窗口期累積分數。"""
    scores: dict[int, float] = {window_count: 0.0 for window_count in window_counts}
    for hit_count in SUMMARY_SCORE_VALUES:
        for window_count in window_counts:
            scores[window_count] += hit_count * rows.get(hit_count, {}).get(window_count, 0)
    return scores


def best_window_by_score(scores: dict[int, float]) -> int | None:
    """取分數最高的窗口期；同分時取較短窗口。"""
    if not scores:
        return None
    return max(scores, key=lambda window_count: (scores[window_count], -window_count))


def read_window_hit_score(path: Path) -> tuple[list[int], dict[int, float], int | None]:
    """讀取窗口期命中統計並計算最佳窗口期。"""
    window_counts, rows = read_window_hit_summary(path)
    scores = score_window_summary(window_counts, rows)
    best_window = best_window_by_score(scores)
    return window_counts, scores, best_window


def print_hit_windows_from_summary(
    title: str,
    window_counts: list[int],
    rows: dict[float, dict[int, int]],
) -> None:
    """按「命中球數 = 累計期數/窗口期」格式打印 range CSV 累計結果。"""
    print(title)
    if not window_counts or not rows:
        print("沒有 3 球或以上命中")
        print()
        return

    printed = False
    for hit_count in SUMMARY_SCORE_VALUES:
        parts: list[str] = []
        for window_count in window_counts:
            periods = rows.get(hit_count, {}).get(window_count, 0)
            if periods > 0:
                parts.append(f"{periods}/{window_count}")
        if parts:
            printed = True
            hit_label = f"{engine.format_ball_count(hit_count)} 球"
            print(f"{hit_label:<6} = {'，'.join(parts)}")
    if not printed:
        print("沒有 3 球或以上命中")
    print()


def print_recent_hit_reference() -> None:
    """打印 range 回測 CSV 累計命中摘要，供用戶選窗口期。"""
    print("---- 回測窗口期命中參考：期數 / 窗口期 ---")
    abcd_windows, abcd_rows = read_window_hit_summary(engine.ABCD_WINDOW_HIT_SUMMARY_CSV)
    high_freq_windows, high_freq_rows = read_window_hit_summary(engine.HIGH_FREQ_DAN_WINDOW_HIT_SUMMARY_CSV)
    print_hit_windows_from_summary(
        "ABCD 預測候選球，期數 / 窗口期",
        abcd_windows,
        abcd_rows,
    )
    print_hit_windows_from_summary(
        "ABCD 全部高頻膽號合併，期數 / 窗口期",
        high_freq_windows,
        high_freq_rows,
    )


def choose_window(
    candidate_windows: list[int],
    default_window: int | None,
) -> int:
    """互動環境讓用戶選窗口期；非互動時使用最佳窗口。"""
    unique_windows = sorted(set(candidate_windows))
    if not unique_windows:
        return default_window or engine.WINDOW_DRAW_COUNT_LIST[0]
    if default_window is None:
        default_window = unique_windows[0]

    prompt = f"要回測分析的窗口期：窗口期 {unique_windows} 用戶輸入 = "
    if not sys.stdin.isatty():
        raw = sys.stdin.readline().strip()
        if raw:
            print(f"{prompt}{raw}")
        else:
            print(f"{prompt}{default_window}")
            return default_window
    else:
        raw = input(prompt).strip()
    if not raw:
        return default_window
    selected_window = engine.to_int(raw, default=0)
    if selected_window in unique_windows:
        return selected_window
    selected_index = selected_window
    if 1 <= selected_index <= len(unique_windows):
        return unique_windows[selected_index - 1]
    print(f"輸入無效，使用預設窗口期 {default_window}")
    return default_window


def build_prediction_for_window(
    draws: list[engine.DrawRow],
    window_count: int,
) -> tuple[
    list[int],
    list[int],
    dict[int, list[int]],
    dict[int, int],
    list[GroupAnalysisRow],
    list[tuple[int, engine.DrawRow]],
]:
    """按指定窗口期建立 ABCD 預測候選與高頻膽候選。"""
    latest_index = len(draws) - 1
    latest_row = draws[latest_index]
    window_start_index = max(0, latest_index - window_count + 1)
    window_rows = [
        (row_index, row)
        for row_index, row in enumerate(draws[window_start_index:latest_index + 1], start=window_start_index)
    ]

    take_counts = engine.dynamic_group_take_counts(window_rows)
    pair_data = engine.high_freq_pair_data(window_rows)
    weak_data = engine.weak_nums_data(window_rows, pair_data)
    recent_nums = engine.recent_draw_nums(latest_row)
    group_pred_map: dict[int, list[int]] = {}
    pred_nums: list[int] = []
    group_rows: list[GroupAnalysisRow] = []

    for group_id in engine.GROUPS:
        weights = engine.analyze_group_weights(window_rows, latest_index, group_id)
        hot_nums = engine.select_group_candidates(weights, group_id, take_counts)
        final_group_pred = engine.select_final_group_candidates(
            weights,
            group_id,
            pair_data,
            weak_data,
            recent_nums,
            take_counts,
        )
        group_pred_map[group_id] = final_group_pred
        pred_nums.extend(final_group_pred)
        code, name, _start_num, _end_num = engine.GROUPS[group_id]
        dan_nums, partner_nums = pair_data.get(group_id, ([], []))
        group_rows.append(
            {
                "code": code,
                "name": name,
                "quota": take_counts[group_id],
                "hot_nums": hot_nums,
                "final_nums": final_group_pred,
                "dan_nums": dan_nums,
                "partner_nums": partner_nums,
                "weak_nums": weak_data.get(group_id, []),
            }
        )

    high_freq_dan_nums = engine.select_high_freq_dan_backtest_nums(pair_data)
    return sorted(pred_nums), high_freq_dan_nums, group_pred_map, take_counts, group_rows, window_rows


def format_group_num_summary(label: str, group_rows: list[GroupAnalysisRow], key: str) -> str:
    """格式化 ABCD 各組號碼列表。"""
    parts: list[str] = []
    for row in group_rows:
        nums = row.get(key)
        parts.append(f"{row['code']}{engine.format_nums(nums if isinstance(nums, list) else [])}")
    return f"{label} = " + "，".join(parts)


def format_high_freq_quota(group_rows: list[GroupAnalysisRow]) -> str:
    """格式化 ABCD 高頻膽號各組球數。"""
    counts: dict[int, int] = {}
    for index, group_id in enumerate(engine.GROUPS):
        row = group_rows[index]
        counts[group_id] = len(row["dan_nums"])
    return "高頻膽號組配額：" + engine.format_group_quota(counts)


def print_selected_window_analysis(
    window_count: int,
    latest_row: engine.DrawRow,
    next_draw_date: str,
    pred_nums: list[int],
    high_freq_dan_nums: list[int],
    take_counts: dict[int, int],
    group_rows: list[GroupAnalysisRow],
    window_rows: list[tuple[int, engine.DrawRow]],
) -> None:
    """按用戶指定格式打印選定窗口期的 ABCD 分析明細。"""
    quota_label = "本期自動配額" if engine.AUTO_DISTRIBUTE_GROUP_TAKE else "本期固定配額"
    print(f"====== 用戶選定窗口期分析：{window_count} ======")
    print(f"固定基礎配額：{engine.format_group_quota()}")
    print(f"{quota_label}：{engine.format_group_quota(take_counts)}")
    print(engine.format_quota_adjustment(take_counts))
    print(SECTION_LINE)
    for line in engine.condition_stats_text(engine.group_condition_stats(window_rows)):
        print(line)
    print(SECTION_LINE)
    print(f"最後開獎日期：{latest_row['date']}: {engine.row_all_check_text(latest_row)}")
    print(f"下期投注預測日期：{next_draw_date}")
    print(SECTION_LINE)
    print(engine.missing_nums_text(window_rows))
    print(format_group_num_summary("ABCD 高頻膽號", group_rows, "dan_nums"))
    print(format_group_num_summary("ABCD 高頻配腳號", group_rows, "partner_nums"))
    print(format_group_num_summary("ABCD 弱號", group_rows, "weak_nums"))
    print(SECTION_LINE)

    print(f"ABCD 預測候選球 {engine.format_nums(pred_nums)} /> [{len(pred_nums)}] 球")
    print(
        f"ABCD 全部高頻膽號合併一注 {engine.format_nums(high_freq_dan_nums)} /> "
        f"[{len(high_freq_dan_nums)}] 球"
    )
    print(format_high_freq_quota(group_rows))
    print(SECTION_LINE)
    print()


def main() -> None:
    refresh_range_backtest_window_csvs()

    draws = engine.read_draws()
    if not draws:
        raise FileNotFoundError(f"找不到或未能讀取 M6：{engine.M6_CSV}")

    next_draw_date = engine.read_next_draw_date() or "未知"
    reset_bet_pred_pools_csv()

    print("====== PRR v3 真實下期預測 ======")
    print(f"最後開獎日期：{draws[-1]['date']}: {engine.row_all_check_text(draws[-1])}")
    print(f"下期開獎日期：{format_date_with_weekday(next_draw_date)}")
    print(SECTION_LINE)
    print(f"固定基礎配額：{engine.format_group_quota()}")
    print(engine.format_auto_distribute_status())
    print(SECTION_LINE)
    print(range_backtest_period_text(draws))
    print(f"多窗口期命中分析：{engine.WINDOW_DRAW_COUNT_LIST}")
    print(SECTION_LINE)
    print()

    abcd_windows, _abcd_scores, abcd_best_window = read_window_hit_score(engine.ABCD_WINDOW_HIT_SUMMARY_CSV)
    high_freq_windows, _high_freq_scores, high_freq_best_window = read_window_hit_score(engine.HIGH_FREQ_DAN_WINDOW_HIT_SUMMARY_CSV)
    print_recent_hit_reference()

    all_candidate_windows = list(engine.WINDOW_DRAW_COUNT_LIST)
    default_window = engine.WINDOW_DRAW_COUNT_LIST[0]
    if abcd_best_window in all_candidate_windows:
        default_window = abcd_best_window
    elif high_freq_best_window in all_candidate_windows:
        default_window = high_freq_best_window
    selected_window = choose_window(all_candidate_windows, default_window)
    print(f"本次下期預測使用窗口期：{selected_window}")
    print()

    pred_nums, high_freq_dan_nums, _group_pred_map, take_counts, group_rows, window_rows = build_prediction_for_window(
        draws,
        selected_window,
    )
    append_bet_pred_pool(next_draw_date, "ABCD 預測候選球", selected_window, pred_nums)
    append_bet_pred_pool(next_draw_date, "ABCD 全部高頻膽號合併", selected_window, high_freq_dan_nums)

    print_selected_window_analysis(
        selected_window,
        draws[-1],
        next_draw_date,
        pred_nums,
        high_freq_dan_nums,
        take_counts,
        group_rows,
        window_rows,
    )

    print(f"已寫入：{BET_PRED_POOLS_CSV}")


if __name__ == "__main__":
    main()
