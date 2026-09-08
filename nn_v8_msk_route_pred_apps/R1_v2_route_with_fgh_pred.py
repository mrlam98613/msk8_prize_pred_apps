from pathlib import Path
import csv
import json
import sys
from typing import TypedDict


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from n_v2_msk_prize_31_num_backtest_pred.res_func_num_convert_RBG_Dict import res_List_To_rbg_Dict_func

M6_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"
M4_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M4_lotto_prize_summary.csv"
JSON_PATH = CURRENT_DIR / "json_data" / "R1_v2_route_with_fgh_pred.json"
NEXT_BET_RECORD_CSV = CURRENT_DIR / "bet_data" / "nextBetDraw_record.csv"
F5_JSON_PATH = PROJECT_ROOT / "nn_v5_msk_1_9_num_apps" / "json_data" / "F5_v6_best_params.json"
G1_JSON_PATH = PROJECT_ROOT / "nn_v6_msk_10_20_num_apps" / "json_data" / "G1_v1_best_params.json"
H1_JSON_PATH = PROJECT_ROOT / "nn_v7_msk_21_31_num_apps" / "json_data" / "H1_v1_best_params.json"

# R1_v2 先用 R1 配額判斷 F/G/H 發球數，再讀入 F5/G1/H1 候選球協調成總候選池。
# F = 1-9，G = 10-20，H = 21-31。
BACKTEST_DRAW_COUNT_LIST = [50]
WINDOW_DRAW_COUNT_LIST = [12, 18, 24]
RECENT_DRAW_COUNT = 5
BASE_GROUP_QUOTA = 3  # 基準配額：F3 + G3 + H3。
MIN_GROUP_QUOTA = 0
MAX_GROUP_QUOTA = 5
STRONG_GROUP_COUNT = 3  # N1..N7 中同組 >=3 球，視為該組主力。
MIN_TOTAL_CANDIDATE_COUNT = 6  # 最終候選池最少球數；F/G/H 來源不足時會自動補球。

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
    hit_ball_count: int
    check_counts: dict[str, int]
    window_count: int
    route_score_text: str
    reason: str


class GroupPrediction(TypedDict):
    group_key: str
    label: str
    json_path: str
    bet_date: str
    source_candidates: list[int]
    quota: int
    final_candidates: list[int]
    shortage_count: int


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


def read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        raw_data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return raw_data if isinstance(raw_data, dict) else {}


def list_from_object(value: object) -> list[int]:
    if not isinstance(value, list):
        return []
    return [to_int(item) for item in value if 1 <= to_int(item) <= 49]


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


def strong_text(route: list[str]) -> str:
    return "+".join(route) if route else "未達3球"


def quota_text(quota: dict[str, int]) -> str:
    return " + ".join(f"{key}{quota.get(key, 0)}" for key in GROUPS)


def counts_text(counts: dict[str, int]) -> str:
    return "，".join(f"{key}={counts[key]}" for key in GROUPS)


def actual_counts_text(counts: dict[str, int]) -> str:
    parts: list[str] = []
    for key in GROUPS:
        count = counts.get(key, 0)
        parts.append(f"{key}={count}" if count > 0 else "___")
    return "，".join(parts)


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
        predicted_active = [key for key in GROUPS if predicted_quota.get(key, 0) > 0]
        hit_route = [key for key in predicted_active if actual_info["counts"].get(key, 0) > 0]
        hit_ball_count = sum(
            min(predicted_quota.get(key, 0), actual_info["counts"].get(key, 0))
            for key in hit_route
        )
        rows.append({
            "check_date": check_row["date"],
            "predicted_quota": predicted_quota,
            "predicted_strong": predicted_strong,
            "actual_strong": actual_strong,
            "hit_route": hit_route,
            "hit_count": len(hit_route),
            "hit_ball_count": hit_ball_count,
            "check_counts": actual_info["counts"],
            "window_count": window_count,
            "route_score_text": score_text,
            "reason": reason,
        })
    return rows


def summarize(backtest_count: int, window_count: int, rows: list[BacktestRow]) -> dict[str, object]:
    total = len(rows)
    hit_3 = sum(row["hit_count"] == 3 for row in rows)
    hit_2 = sum(row["hit_count"] == 2 for row in rows)
    hit_1 = sum(row["hit_count"] == 1 for row in rows)
    hit_0 = sum(row["hit_count"] == 0 for row in rows)
    score = hit_3 * 12 + hit_2 * 8 + hit_1 * 2 - hit_0 * 3
    return {
        "backtest_draw_count": backtest_count,
        "window_draw_count": window_count,
        "total": total,
        "hit_3_count": hit_3,
        "hit_2_count": hit_2,
        "hit_2_plus_count": hit_3 + hit_2,
        "hit_1_count": hit_1,
        "hit_0_count": hit_0,
        "hit_2_plus_rate": (hit_3 + hit_2) / total if total else 0.0,
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
    print("====== R1_v2 路線回測參數比較 ======")
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
    print("====== R1_v2 最佳分組配額逐期核對 ======")
    print(
        f"最佳參數：回測期 {to_int(best.get('backtest_draw_count'))}，"
        f"窗口期 {to_int(best.get('window_draw_count'))}"
    )
    total = len(rows)
    for index, row in enumerate(rows, start=1):
        near_index = total - index + 1
        print(
            f"{near_index}，核對期：{row['check_date']}，"
            f"調整 {quota_text(row['predicted_quota'])}，"
            f"實際 {actual_counts_text(row['check_counts'])}，"
            f"命中 {route_text(row['hit_route'])} / {row['hit_count']} 組，"
            f"命中共 /> {row['hit_ball_count']} 球"
        )
    print()


def print_summary(rows: list[BacktestRow]) -> None:
    total = len(rows)
    group_hit_counts = {count: sum(row["hit_count"] == count for row in rows) for count in range(3, -1, -1)}
    ball_hit_counts = {count: sum(row["hit_ball_count"] == count for row in rows) for count in range(7, -1, -1)}

    def line(label: str, count: int) -> str:
        return f"{label} = {count} 期，{count / total:.2%}" if total else f"{label} = 0 期"

    print("====== R1_v2 路線命中率 ======")
    print(f"總回測期數：{total}")
    print()
    print("命中組別統計：")
    for count in range(3, -1, -1):
        print(line(f"命中 {count} 組", group_hit_counts[count]))
    print()
    print("命中總球數統計：")
    for count in range(7, -1, -1):
        print(line(f"{count} 球", ball_hit_counts[count]))
    print()


def read_group_prediction(group_key: str, quota: int) -> GroupPrediction:
    label, start, end = GROUPS[group_key]
    path_map = {
        "F": F5_JSON_PATH,
        "G": G1_JSON_PATH,
        "H": H1_JSON_PATH,
    }
    path = path_map[group_key]
    data = read_json(path)
    next_prediction = data.get("next_prediction")
    next_data = next_prediction if isinstance(next_prediction, dict) else {}
    source_candidates = [
        num for num in list_from_object(next_data.get("candidate_nums"))
        if start <= num <= end
    ]
    final_candidates = source_candidates[:quota]
    return {
        "group_key": group_key,
        "label": label,
        "json_path": str(path),
        "bet_date": str(next_data.get("bet_date", "")),
        "source_candidates": source_candidates,
        "quota": quota,
        "final_candidates": final_candidates,
        "shortage_count": max(0, quota - len(final_candidates)),
    }


def build_fgh_predictions(quota: dict[str, int]) -> list[GroupPrediction]:
    return [read_group_prediction(group_key, quota.get(group_key, 0)) for group_key in GROUPS]


def recent_group_candidates(window_rows: list[DrawRow], group_key: str, used_nums: set[int]) -> list[int]:
    """用預測窗口期內的近期出現次數，為來源不足的分組補球。"""

    _label, start, end = GROUPS[group_key]
    score_map = {num: 0.0 for num in range(start, end + 1)}
    total = len(window_rows)
    for row_index, row in enumerate(window_rows):
        recent_bonus = (row_index + 1) / total if total else 0.0
        for num in all_draw_nums(row):
            if start <= num <= end:
                score_map[num] += 1.0 + recent_bonus
    return [
        num
        for num, score in sorted(score_map.items(), key=lambda item: (-item[1], item[0]))
        if score > 0 and num not in used_nums
    ]


def fill_group_prediction_shortage(
    group_predictions: list[GroupPrediction],
    window_rows: list[DrawRow],
) -> None:
    """當 F5/G1/H1 來源球不足，先補足該組配額，再確保整體最少 6 球。"""

    used_nums = {num for item in group_predictions for num in item["final_candidates"]}

    # 第一輪：有配額但來源不足的分組，先在自己的號碼範圍內補足。
    for item in group_predictions:
        quota = item["quota"]
        if quota <= 0 or len(item["final_candidates"]) >= quota:
            continue
        for num in recent_group_candidates(window_rows, item["group_key"], used_nums):
            if len(item["final_candidates"]) >= quota:
                break
            item["final_candidates"].append(num)
            used_nums.add(num)

    # 第二輪：整合候選池仍少於 6 球，按 R1 配額高低補位。
    ranked_items = sorted(group_predictions, key=lambda item: (-item["quota"], item["group_key"]))
    for item in ranked_items:
        if len(used_nums) >= MIN_TOTAL_CANDIDATE_COUNT:
            break
        for num in recent_group_candidates(window_rows, item["group_key"], used_nums):
            if len(used_nums) >= MIN_TOTAL_CANDIDATE_COUNT:
                break
            item["final_candidates"].append(num)
            used_nums.add(num)

    for item in group_predictions:
        item["final_candidates"] = sorted(item["final_candidates"])
        item["shortage_count"] = max(0, item["quota"] - len(item["final_candidates"]))


def format_nums(nums: list[int]) -> str:
    return "[" + ",".join(str(num) for num in nums) + "]"


def print_rbg_candidates(nums: list[int]) -> None:
    rbg_dict = res_List_To_rbg_Dict_func(nums)
    color_rows = [
        ("R", sorted(rbg_dict.get(0, []))),
        ("B", sorted(rbg_dict.get(1, []))),
        ("G", sorted(rbg_dict.get(2, []))),
    ]
    print("----------------------------------------")
    for label, color_nums in color_rows:
        print(f"{label}: {format_nums(color_nums)} /> {len(color_nums)} 球")


def group_prediction_map(group_predictions: list[GroupPrediction]) -> dict[str, list[int]]:
    return {item["group_key"]: item["final_candidates"] for item in group_predictions}


def save_next_bet_record(bet_date: str, group_predictions: list[GroupPrediction]) -> None:
    NEXT_BET_RECORD_CSV.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["bet_date", "1-9", "10-20", "21-31"]
    prediction_map = group_prediction_map(group_predictions)
    new_row = {
        "bet_date": bet_date,
        "1-9": format_nums(prediction_map.get("F", [])),
        "10-20": format_nums(prediction_map.get("G", [])),
        "21-31": format_nums(prediction_map.get("H", [])),
    }

    rows: list[dict[str, str]] = []
    if NEXT_BET_RECORD_CSV.exists():
        with NEXT_BET_RECORD_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = [{field: (row.get(field) or "") for field in fieldnames} for row in reader]

    rows = [row for row in rows if row.get("bet_date") != bet_date]
    rows.append(new_row)
    rows.sort(key=lambda row: row.get("bet_date", ""))

    with NEXT_BET_RECORD_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def print_fgh_prediction(group_predictions: list[GroupPrediction]) -> list[int]:
    all_candidates = sorted({num for item in group_predictions for num in item["final_candidates"]})
    print("====== R1_v2 讀入 F5/G1/H1 協調候選球 ======")
    for item in group_predictions:
        shortage_text = f"，不足 {item['shortage_count']} 球" if item["shortage_count"] else ""
        print(
            f"{item['group_key']} {item['label']}："
            f"R1配額 {item['quota']} 球，"
            f"來源 {format_nums(item['source_candidates'])}，"
            f"採用 {format_nums(item['final_candidates'])}{shortage_text}"
        )
    print(f"整合候選池：{','.join(str(num) for num in all_candidates)} /> {len(all_candidates)} 球")
    print_rbg_candidates(all_candidates)
    print()
    return all_candidates


def print_next_prediction(draws: list[DrawRow], best: dict[str, object]) -> tuple[dict[str, int], list[GroupPrediction], list[int]]:
    window_count = to_int(best.get("window_draw_count"), WINDOW_DRAW_COUNT_LIST[0])
    window_rows = draws[-window_count:]
    quota, predicted_strong, reason, score_text = predict_quota(window_rows)
    group_predictions = build_fgh_predictions(quota)
    fill_group_prediction_shortage(group_predictions, window_rows)
    final_candidates = [num for item in group_predictions for num in item["final_candidates"]]
    latest_info = route_info(draws[-1])
    print("====== R1_v2 下期分組配額預測 ======")
    print(f"最新期：{draws[-1]['date']}，{counts_text(latest_info['counts'])}，實際路線 {route_text(latest_info['active'])}")
    print(f"下期日期：{read_next_draw_date()}")
    print(f"窗口期：{window_count}")
    print(f"路線分數：{score_text}")
    print("基準配額：F3 + G3 + H3")
    print(f"建議配額：{quota_text(quota)}")
    print(f"主力傾向：{route_text(predicted_strong)}")
    print(f"提示：{reason}")
    print()
    final_candidates = print_fgh_prediction(group_predictions)
    print("============== 完結 ==============")
    return quota, group_predictions, final_candidates


def save_json(
    best: dict[str, object],
    ranking: list[dict[str, object]],
    rows: list[BacktestRow],
    next_quota: dict[str, int],
    group_predictions: list[GroupPrediction],
    final_candidates: list[int],
) -> None:
    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "model": "R1_v2_group_quota_with_fgh_predict",
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
            "group_predictions": group_predictions,
            "candidate_nums": final_candidates,
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
    next_quota, group_predictions, final_candidates = print_next_prediction(draws, best)
    save_next_bet_record(read_next_draw_date(), group_predictions)
    print(f"已存檔：{NEXT_BET_RECORD_CSV}")
    save_json(best, ranking, rows, next_quota, group_predictions, final_candidates)


if __name__ == "__main__":
    main()
