from pathlib import Path
import csv
import json
from typing import TypedDict


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
M6_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"
M4_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M4_lotto_prize_summary.csv"
JSON_PATH = CURRENT_DIR / "json_data" / "R1_v1_route_best_params.json"

# R1_v1 只分析分組配額路線，不產生具體球號。
# F = 1-9，G = 10-20，H = 21-31。
BACKTEST_DRAW_COUNT_LIST = [30]
WINDOW_DRAW_COUNT_LIST = [12, 18, 24]
RECENT_DRAW_COUNT = 5
BASE_GROUP_QUOTA = 3  # 基準配額：F3 + G3 + H3。
MIN_GROUP_QUOTA = 0
MAX_GROUP_QUOTA = 5
STRONG_GROUP_COUNT = 3  # N1..N7 中同組 >=3 球，視為該組主力。

# 投注人氣權重：F/G 較貼近主觀記憶與投注人氣，H 保留但稍降權。
GROUP_POPULARITY_WEIGHT = {
    "F": 1.20,
    "G": 1.15,
    "H": 0.85,
}

# 分組路線代號。每一期 N1-N6 + N7 特號都會被映射到 F/G/H。
GROUPS = {
    "F": ("1-9", 1, 9),
    "G": ("10-20", 10, 20),
    "H": ("21-31", 21, 31),
}


class DrawRow(TypedDict):
    date: str
    nums: list[int]
    special: int | None


class RouteInfo(TypedDict):
    counts: dict[str, int]
    active: list[str]


class BacktestRow(TypedDict):
    check_date: str
    predicted_quota: dict[str, int]
    predicted_strong: list[str]
    actual_strong: list[str]
    hit_route: list[str]
    hit_count: int
    check_counts: dict[str, int]
    window_count: int
    route_score_text: str
    reason: str


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
        return [{(key or "").strip(): (value or "").strip() for key, value in row.items()} for row in reader]


def read_draws() -> list[DrawRow]:
    draws: list[DrawRow] = []
    for row in read_csv_rows(M6_CSV):
        date = row.get("nDdate", "")
        if not date:
            continue
        special = to_int(row.get("N7"))
        draws.append({
            "date": date,
            "nums": [to_int(row.get(f"N{index}")) for index in range(1, 7)],
            "special": special if 1 <= special <= 49 else None,
        })
    return draws


def read_next_draw_date() -> str:
    rows = read_csv_rows(M4_CSV)
    return rows[-1].get("next_draw_date", "") if rows else ""


def all_draw_nums(row: DrawRow) -> list[int]:
    nums = [num for num in row["nums"] if 1 <= num <= 49]
    if row["special"] is not None:
        nums.append(row["special"])
    return nums


def route_info(row: DrawRow) -> RouteInfo:
    counts = {key: 0 for key in GROUPS}
    for num in all_draw_nums(row):
        for key, (_, start, end) in GROUPS.items():
            if start <= num <= end:
                counts[key] += 1
                break
    return {
        "counts": counts,
        "active": [key for key in GROUPS if counts[key] > 0],
    }


def route_text(route: list[str]) -> str:
    return "+".join(route) if route else "(00)"


def quota_text(quota: dict[str, int]) -> str:
    return " + ".join(f"{key}{quota.get(key, 0)}" for key in GROUPS)


def counts_text(counts: dict[str, int]) -> str:
    return "，".join(f"{key}={counts[key]}" for key in GROUPS)


def route_scores(window_rows: list[DrawRow]) -> dict[str, float]:
    scores = {key: 0.0 for key in GROUPS}
    total = len(window_rows)
    for index, row in enumerate(window_rows):
        info = route_info(row)
        recent_bonus = (index + 1) / total if total else 0.0
        for key in info["active"]:
            scores[key] += (1.0 + recent_bonus) * GROUP_POPULARITY_WEIGHT[key]
    return scores


def recent_route_reason(window_rows: list[DrawRow], scores: dict[str, float]) -> str:
    recent_rows = window_rows[-RECENT_DRAW_COUNT:]
    recent_counts = {key: 0 for key in GROUPS}
    for row in recent_rows:
        for key in route_info(row)["active"]:
            recent_counts[key] += 1
    hot = sorted(recent_counts.items(), key=lambda item: (-item[1], item[0]))
    score_rank = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return (
        f"最近{RECENT_DRAW_COUNT}期："
        f"{', '.join(f'{key}:{count}' for key, count in hot)}；"
        f"窗口分：{', '.join(f'{key}:{score:.1f}' for key, score in score_rank)}"
    )


def strong_groups(counts: dict[str, int]) -> list[str]:
    return [key for key in GROUPS if counts[key] >= STRONG_GROUP_COUNT]


def clamp_quota(value: int) -> int:
    return max(MIN_GROUP_QUOTA, min(MAX_GROUP_QUOTA, value))


def predict_quota(window_rows: list[DrawRow]) -> tuple[dict[str, int], list[str], str, str]:
    scores = route_scores(window_rows)
    latest_info = route_info(window_rows[-1])
    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    quota = {key: BASE_GROUP_QUOTA for key in GROUPS}

    none_groups = [key for key in GROUPS if latest_info["counts"][key] == 0]
    latest_strong = strong_groups(latest_info["counts"])
    reason_parts = [recent_route_reason(window_rows, scores)]

    # 固定 F3+G3+H3 起步；上一期某組消失，該組減 2 球，配額轉給高分組。
    for weak_key in none_groups:
        reduce_count = min(2, quota[weak_key])
        quota[weak_key] -= reduce_count
        for strong_key, _ in ranked:
            if strong_key == weak_key:
                continue
            if reduce_count <= 0:
                break
            quota[strong_key] += 1
            reduce_count -= 1

    # 上一期某組 >=3 球，視為主力偏強，加 1 球；由最低分非主力組扣 1 球。
    for strong_key in latest_strong:
        weak_candidates = [key for key, _ in reversed(ranked) if key != strong_key and quota[key] > MIN_GROUP_QUOTA]
        if not weak_candidates:
            continue
        quota[strong_key] += 1
        quota[weak_candidates[0]] -= 1

    quota = {key: clamp_quota(value) for key, value in quota.items()}
    predicted_strong = [key for key in GROUPS if quota[key] == max(quota.values())]
    if none_groups:
        reason_parts.append(f"上一期未出：{','.join(none_groups)}，該組減球")
    if latest_strong:
        reason_parts.append(f"上一期主力：{','.join(latest_strong)}，主力組加權")
    if not none_groups and not latest_strong:
        reason_parts.append("三組沒有明顯消失或主力，接近平均配額")
    return quota, predicted_strong, "；".join(reason_parts), ", ".join(f"{key}:{score:.1f}" for key, score in ranked)


def run_backtest_once(draws: list[DrawRow], backtest_count: int, window_count: int) -> list[BacktestRow]:
    if backtest_count <= 0 or len(draws) < backtest_count + window_count:
        return []
    rows: list[BacktestRow] = []
    first_check_index = len(draws) - backtest_count
    for check_index in range(first_check_index, len(draws)):
        window_rows = draws[check_index - window_count:check_index]
        check_row = draws[check_index]
        predicted_quota, predicted_strong, reason, score_text = predict_quota(window_rows)
        actual_info = route_info(check_row)
        actual_strong = strong_groups(actual_info["counts"])
        actual_target = actual_strong if actual_strong else actual_info["active"]
        hit_route = [key for key in predicted_strong if key in actual_target]
        rows.append({
            "check_date": check_row["date"],
            "predicted_quota": predicted_quota,
            "predicted_strong": predicted_strong,
            "actual_strong": actual_strong,
            "hit_route": hit_route,
            "hit_count": len(hit_route),
            "check_counts": actual_info["counts"],
            "window_count": window_count,
            "route_score_text": score_text,
            "reason": reason,
        })
    return rows


def summarize(backtest_count: int, window_count: int, rows: list[BacktestRow]) -> dict[str, object]:
    total = len(rows)
    hit_2 = sum(row["hit_count"] >= 2 for row in rows)
    hit_1 = sum(row["hit_count"] == 1 for row in rows)
    hit_0 = sum(row["hit_count"] == 0 for row in rows)
    score = hit_2 * 8 + hit_1 * 2 - hit_0 * 3
    return {
        "backtest_draw_count": backtest_count,
        "window_draw_count": window_count,
        "total": total,
        "hit_2_plus_count": hit_2,
        "hit_1_count": hit_1,
        "hit_0_count": hit_0,
        "hit_2_plus_rate": hit_2 / total if total else 0.0,
        "score": score,
    }


def sort_summaries(items: list[dict[str, object]]) -> list[dict[str, object]]:
    return sorted(items, key=lambda item: (
        -to_float(item.get("hit_2_plus_rate")),
        -to_int(item.get("score")),
        to_int(item.get("window_draw_count")),
    ))


def run_parameter_search(
    draws: list[DrawRow],
) -> tuple[dict[str, object], list[dict[str, object]], list[BacktestRow]]:
    summaries: list[dict[str, object]] = []
    detail_by_key: dict[tuple[int, int], list[BacktestRow]] = {}
    for backtest_count in BACKTEST_DRAW_COUNT_LIST:
        for window_count in WINDOW_DRAW_COUNT_LIST:
            rows = run_backtest_once(draws, backtest_count, window_count)
            detail_by_key[(backtest_count, window_count)] = rows
            summaries.append(summarize(backtest_count, window_count, rows))
    ranking = sort_summaries(summaries)
    best = ranking[0]
    best_key = (to_int(best["backtest_draw_count"]), to_int(best["window_draw_count"]))
    return best, ranking, detail_by_key[best_key]


def print_ranking(ranking: list[dict[str, object]]) -> None:
    print("====== R1_v1 路線回測參數比較 ======")
    print("回測期 | 窗口期 | 命中2組+ | 命中1組 | 命中0組 | 分數")
    for item in ranking:
        print(
            f"{to_int(item['backtest_draw_count']):>6} | {to_int(item['window_draw_count']):>6} | "
            f"{to_int(item['hit_2_plus_count']):>5}({to_float(item.get('hit_2_plus_rate')):>5.1%}) | "
            f"{to_int(item['hit_1_count']):>5} | "
            f"{to_int(item['hit_0_count']):>5} | "
            f"{to_int(item['score']):>4}"
        )
    print()


def print_backtest_rows(rows: list[BacktestRow], best: dict[str, object]) -> None:
    print("====== R1_v1 最佳分組配額逐期核對 ======")
    print(
        f"最佳參數：回測期 {to_int(best.get('backtest_draw_count'))}，"
        f"窗口期 {to_int(best.get('window_draw_count'))}"
    )
    total = len(rows)
    for index, row in enumerate(rows, start=1):
        near_index = total - index + 1
        print(
            f"{near_index}，核對期：{row['check_date']}，"
            f"基準 F3+G3+H3，調整 {quota_text(row['predicted_quota'])}，"
            f"主力傾向 {route_text(row['predicted_strong'])}，"
            f"實際 {counts_text(row['check_counts'])}，"
            f"實際主力 {route_text(row['actual_strong'])}，"
            f"命中 {route_text(row['hit_route'])} / {row['hit_count']} 組"
        )
        print(f"  提示：{row['reason']}")
    print()


def print_summary(rows: list[BacktestRow]) -> None:
    total = len(rows)
    hit_2 = sum(row["hit_count"] >= 2 for row in rows)
    hit_1 = sum(row["hit_count"] == 1 for row in rows)
    hit_0 = sum(row["hit_count"] == 0 for row in rows)
    print("====== R1_v1 路線命中率 ======")
    print(f"總回測期數：{total}")
    print(f"命中 2 組以上：{hit_2} 期，{hit_2 / total:.2%}" if total else "命中 2 組以上：0 期")
    print(f"命中 1 組：{hit_1} 期，{hit_1 / total:.2%}" if total else "命中 1 組：0 期")
    print(f"命中 0 組：{hit_0} 期，{hit_0 / total:.2%}" if total else "命中 0 組：0 期")
    print()


def print_next_prediction(draws: list[DrawRow], best: dict[str, object]) -> dict[str, int]:
    window_count = to_int(best.get("window_draw_count"), WINDOW_DRAW_COUNT_LIST[0])
    window_rows = draws[-window_count:]
    quota, predicted_strong, reason, score_text = predict_quota(window_rows)
    latest_info = route_info(draws[-1])
    print("====== R1_v1 下期分組配額預測 ======")
    print(f"最新期：{draws[-1]['date']}，{counts_text(latest_info['counts'])}，實際路線 {route_text(latest_info['active'])}")
    print(f"下期日期：{read_next_draw_date()}")
    print(f"窗口期：{window_count}")
    print(f"路線分數：{score_text}")
    print("基準配額：F3 + G3 + H3")
    print(f"建議配額：{quota_text(quota)}")
    print(f"主力傾向：{route_text(predicted_strong)}")
    print(f"提示：{reason}")
    print("============== 完結 ==============")
    return quota


def save_json(
    best: dict[str, object],
    ranking: list[dict[str, object]],
    rows: list[BacktestRow],
    next_quota: dict[str, int],
) -> None:
    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "model": "R1_v1_group_quota_backtest_predict",
        "groups": GROUPS,
        "base_group_quota": BASE_GROUP_QUOTA,
        "group_popularity_weight": GROUP_POPULARITY_WEIGHT,
        "best": best,
        "ranking": ranking,
        "backtest_rows": rows,
        "next_prediction": {
            "bet_date": read_next_draw_date(),
            "quota": next_quota,
            "quota_text": quota_text(next_quota),
        },
    }
    JSON_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    draws = read_draws()
    if not draws:
        raise RuntimeError("沒有可用開獎資料。")
    best, ranking, rows = run_parameter_search(draws)
    print_ranking(ranking)
    print_backtest_rows(rows, best)
    print_summary(rows)
    next_quota = print_next_prediction(draws, best)
    save_json(best, ranking, rows, next_quota)


if __name__ == "__main__":
    main()
