from collections import Counter
from pathlib import Path
import random
import sys
import pandas as pd
import res_func_num_convert_RBG_Dict


"""
C6：1,2,3獎 RBG + 特式 + 區間投注策略

功能：
1. 由 C5 雙模式思路延伸，保留 predict / backtest。
2. C5 原檔不改，本檔使用獨立 bet_prize_data CSV。
3. 投注模式獨立拆開：prize3 / prize2 / prize1 / all。
4. 每個模式各產生 1 注單式；all 模式產生 3 注。
5. 各模式使用自己的 RBG 分析、特式加權及 interval 區間 pattern。

執行例：
    python c6_lotto_prize_123_pred_bet.py predict all
    python c6_lotto_prize_123_pred_bet.py predict prize2
    python c6_lotto_prize_123_pred_bet.py backtest all
"""


CURRENT_DIR = Path(__file__).resolve().parent
DATA_DIR = CURRENT_DIR.parent / "A_msk_lottery_data_folder"
DRAW_HISTORY_CSV = DATA_DIR / "M2_last_upgrade_lotto_data.csv"
PRIZE_HISTORY_CSV = DATA_DIR / "M6_lotto_history_prize.csv"
PRIZE_SUMMARY_CSV = DATA_DIR / "M4_lotto_prize_summary.csv"
BET_PRIZE_DATA_DIR = CURRENT_DIR / "bet_prize_data"
PRIZE123_BET_CSV = BET_PRIZE_DATA_DIR / "prize123_bet.csv"
PRIZE123_NEXT_DRAW_BET_CSV = BET_PRIZE_DATA_DIR / "prize123_nextDraw_bet.csv"
PRIZE123_WIN_RESULTS_CSV = BET_PRIZE_DATA_DIR / "prize123_win_results.csv"

# ---------------------------- 手動參數 ----------------------------
RUN_MODE = "predict"  # "predict" / "backtest"
BET_MODE = "all"  # "prize3" / "prize2" / "prize1" / "all"
BACKTEST_DRAW = 24

# ---------------------------- 分析參數 ----------------------------
FEATURE_LOOKBACK_DRAW = 24
PRIZE3_TOP_DRAW = 11
PRIZE2_TOP_DRAW = 7
HEAD_PRIZE_ZERO_TOP_DRAW = 7
RECENT_LOOKBACK_DRAW = 14
RANDOM_SEED = 42

DRAW_COLUMNS = ["ndate", "N1", "N2", "N3", "N4", "N5", "N6", "N7"]
BET_COLUMNS = ["bet_date", "N1", "N2", "N3", "N4", "N5", "N6", "prize"]
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

MODE_ORDER = ["prize3", "prize2", "prize1"]
MODE_LABELS = {
    "prize3": "第1注：3獎 RBG 分析預測",
    "prize2": "第2注：2獎 RBG 分析預測",
    "prize1": "第3注：頭獎無人中 RBG 分析預測",
}
MODE_PRIZE_VALUES = {
    "prize3": 3,
    "prize2": 2,
    "prize1": 1,
}

FEATURE_PROFILES = {
    "prize3": {"birthday": 1.2, "same_tail": 0.8, "round_tens": 0.3},
    "prize2": {"birthday": 1.5, "same_tail": 1.0, "round_tens": 1.1},
    "prize1": {"birthday": 1.2, "same_tail": 1.4, "round_tens": 1.0},
}


def reset_output_csvs():
    """回測模式使用：刪除並重建 C6 三個 CSV。"""
    BET_PRIZE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    for path in [PRIZE123_BET_CSV, PRIZE123_NEXT_DRAW_BET_CSV, PRIZE123_WIN_RESULTS_CSV]:
        if path.exists():
            path.unlink()
        pd.DataFrame(columns=BET_COLUMNS).to_csv(path, index=False, encoding="utf-8-sig")


def ensure_output_csvs():
    """預測模式使用：確保 C6 三個 CSV 存在。"""
    BET_PRIZE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    for path in [PRIZE123_BET_CSV, PRIZE123_NEXT_DRAW_BET_CSV, PRIZE123_WIN_RESULTS_CSV]:
        if not path.exists():
            pd.DataFrame(columns=BET_COLUMNS).to_csv(path, index=False, encoding="utf-8-sig")


def rows_from_bets(bet_date, bets, prize_values=None):
    rows = []
    if prize_values is None:
        prize_values = [""] * len(bets)
    for bet, prize_value in zip(bets, prize_values):
        nums = sorted(int(num) for num in bet)
        if len(nums) != 6:
            continue
        rows.append({
            "bet_date": str(bet_date),
            "N1": nums[0],
            "N2": nums[1],
            "N3": nums[2],
            "N4": nums[3],
            "N5": nums[4],
            "N6": nums[5],
            "prize": prize_value,
        })
    return rows


def rows_from_mode_results(bet_date, mode_results, use_win_nums=False):
    rows = []
    for mode_result in mode_results:
        bet = mode_result["bet"]
        if use_win_nums:
            bet = mode_result.get("win_nums", bet)
        rows.extend(rows_from_bets(
            bet_date,
            [bet],
            prize_values=[MODE_PRIZE_VALUES.get(mode_result["mode"], "")],
        ))
    return rows


def append_csv_rows(path, rows):
    if not rows:
        return
    old_df = pd.read_csv(path, encoding="utf-8-sig") if path.exists() else pd.DataFrame(columns=BET_COLUMNS)
    new_df = pd.DataFrame(rows, columns=BET_COLUMNS)
    pd.concat([old_df, new_df], ignore_index=True).to_csv(path, index=False, encoding="utf-8-sig")


def read_bet_csv(path):
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame(columns=BET_COLUMNS)
    df = pd.read_csv(path, encoding="utf-8-sig")
    if "prize" not in df.columns:
        df["prize"] = ""
    if not set(BET_COLUMNS).issubset(df.columns):
        return pd.DataFrame(columns=BET_COLUMNS)
    return df[BET_COLUMNS].copy()


def has_records_for_date(path, bet_date):
    df = read_bet_csv(path)
    if df.empty:
        return False
    return str(bet_date) in set(df["bet_date"].astype(str))


def delete_records_for_date(path, bet_date):
    """刪除指定日期投注列，用於單一模式重新產生最新預測。"""
    df = read_bet_csv(path)
    if df.empty:
        return 0
    before_count = len(df)
    cleaned_df = df[df["bet_date"].astype(str) != str(bet_date)].copy()
    removed_count = before_count - len(cleaned_df)
    if removed_count:
        cleaned_df.to_csv(path, index=False, encoding="utf-8-sig")
    return removed_count


def append_bet_records(bet_date, mode_results):
    append_csv_rows(PRIZE123_BET_CSV, rows_from_mode_results(bet_date, mode_results))


def append_next_draw_bets_if_missing(bet_date, mode_results):
    if has_records_for_date(PRIZE123_NEXT_DRAW_BET_CSV, bet_date):
        print(f"prize123_nextDraw_bet.csv 已有 {bet_date} 紀錄，不重複加入。")
        return
    append_csv_rows(PRIZE123_NEXT_DRAW_BET_CSV, rows_from_mode_results(bet_date, mode_results))


def replace_next_draw_bets(bet_date, mode_results):
    """下期預測檔只保留目前最新下期，供 Streamlit 頁面直接讀取。"""

    BET_PRIZE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    rows = rows_from_mode_results(bet_date, mode_results)
    pd.DataFrame(rows, columns=BET_COLUMNS).to_csv(
        PRIZE123_NEXT_DRAW_BET_CSV,
        index=False,
        encoding="utf-8-sig",
    )


def append_bet_records_if_missing(bet_date, mode_results):
    if has_records_for_date(PRIZE123_BET_CSV, bet_date):
        print(f"prize123_bet.csv 已有 {bet_date} 投注紀錄，不重複加入。")
        return
    append_bet_records(bet_date, mode_results)


def replace_predict_records_for_date(bet_date, mode_results):
    """單一模式預測：刪除同日期舊預測，再寫入最新投注。"""
    removed_bet = delete_records_for_date(PRIZE123_BET_CSV, bet_date)
    removed_next = delete_records_for_date(PRIZE123_NEXT_DRAW_BET_CSV, bet_date)
    append_bet_records(bet_date, mode_results)
    append_csv_rows(PRIZE123_NEXT_DRAW_BET_CSV, rows_from_mode_results(bet_date, mode_results))
    print(f"已更新 {bet_date} 單一模式預測，刪除舊投注 {removed_bet} 注 / 舊下期投注 {removed_next} 注。")


def append_win_results(bet_date, mode_results, hit_rows):
    win_mode_results = []
    for mode_result, hit_row in zip(mode_results, hit_rows):
        matched_set = set(hit_row["matched"])
        win_nums = [num if num in matched_set else 0 for num in hit_row["bet"]]
        win_result = mode_result.copy()
        win_result["win_nums"] = win_nums
        win_mode_results.append(win_result)
    append_csv_rows(PRIZE123_WIN_RESULTS_CSV, rows_from_mode_results(bet_date, win_mode_results, use_win_nums=True))


def remove_placeholder_next_draw_rows():
    """清除舊版用「下一期」作日期的預測列。"""
    for path in [PRIZE123_BET_CSV, PRIZE123_NEXT_DRAW_BET_CSV]:
        df = read_bet_csv(path)
        if df.empty:
            continue
        cleaned_df = df[df["bet_date"].astype(str) != "下一期"].copy()
        if len(cleaned_df) != len(df):
            cleaned_df.to_csv(path, index=False, encoding="utf-8-sig")


def load_draw_history():
    """讀取 M2 開獎歷史。"""
    df = pd.read_csv(DRAW_HISTORY_CSV, encoding="utf-8-sig")
    df = df[DRAW_COLUMNS].copy()
    df["ndate"] = df["ndate"].astype(str).str.strip()
    for col in DRAW_COLUMNS[1:]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    return df.sort_values("ndate").reset_index(drop=True)


def load_prize_history():
    """讀取 M6 1,2,3獎中獎注數及獎金資料。"""
    df = pd.read_csv(PRIZE_HISTORY_CSV, encoding="utf-8-sig", dtype={"nDdate": str})
    df = df.rename(columns={"nDdate": "ndate"})
    df["ndate"] = df["ndate"].astype(str).str.strip()
    for col in ["N1", "N2", "N3", "N4", "N5", "N6", "N7"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    for col in ["prize1", "prize2", "prize3", "prize1_unit", "prize2_unit", "prize3_unit"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df.sort_values("ndate").reset_index(drop=True)


def load_prize_summary():
    """讀取 M4 摘要，用最後一期日期取得真正下期開獎日期。"""
    if not PRIZE_SUMMARY_CSV.exists():
        return pd.DataFrame(columns=["last_draw_date", "next_draw_date"])
    df = pd.read_csv(PRIZE_SUMMARY_CSV, encoding="utf-8-sig", dtype=str)
    df.columns = [str(col).strip().lstrip("\ufeff") for col in df.columns]
    if "last_draw_date" not in df.columns or "next_draw_date" not in df.columns:
        return pd.DataFrame(columns=["last_draw_date", "next_draw_date"])
    df["last_draw_date"] = df["last_draw_date"].astype(str).str.strip()
    df["next_draw_date"] = df["next_draw_date"].astype(str).str.strip()
    return df


def get_main_nums(row):
    return [int(row[f"N{i}"]) for i in range(1, 7)]


def get_all_nums(row):
    return [int(row[f"N{i}"]) for i in range(1, 8)]


def get_num49_interval_map(nums):
    interval_idx = []
    for num in nums:
        n = int(num)
        if 1 <= n <= 9:
            interval_idx.append(0)
        elif 10 <= n <= 19:
            interval_idx.append(1)
        elif 20 <= n <= 29:
            interval_idx.append(2)
        elif 30 <= n <= 40:
            interval_idx.append(3)
        elif 41 <= n <= 49:
            interval_idx.append(4)
    return interval_idx


def nums_in_interval(interval_id):
    return {
        0: list(range(1, 10)),
        1: list(range(10, 20)),
        2: list(range(20, 30)),
        3: list(range(30, 41)),
        4: list(range(41, 50)),
    }[int(interval_id)]


def get_interval_pattern(nums):
    return tuple(sorted(get_num49_interval_map(nums)))


def format_frequency_groups(nums):
    num_counter = Counter(int(num) for num in nums)
    repeated_groups = [
        [num] * count
        for num, count in sorted(num_counter.items(), key=lambda item: (-item[1], item[0]))
        if count >= 2
    ]
    single_group = sorted(num for num, count in num_counter.items() if count == 1)
    if single_group:
        repeated_groups.append(single_group)
    return repeated_groups


def print_rbg_groups(title, nums):
    rbg_dict = res_func_num_convert_RBG_Dict.res_List_To_rbg_Dict_func(nums)
    print(f"\n====== {title} ======")
    print(f"R: {format_frequency_groups(rbg_dict.get(0, []))} /> {len(set(rbg_dict.get(0, [])))} 個不同球號")
    print(f"B: {format_frequency_groups(rbg_dict.get(1, []))} /> {len(set(rbg_dict.get(1, [])))} 個不同球號")
    print(f"G: {format_frequency_groups(rbg_dict.get(2, []))} /> {len(set(rbg_dict.get(2, [])))} 個不同球號")


def normalize_bet_mode(mode):
    mode = str(mode).strip().lower()
    if mode in {"1", "p1", "head"}:
        return "prize1"
    if mode in {"2", "p2"}:
        return "prize2"
    if mode in {"3", "p3"}:
        return "prize3"
    if mode in {"all", "prize1", "prize2", "prize3"}:
        return mode
    raise ValueError(f"未知 BET_MODE: {mode}")


def selected_modes(bet_mode):
    bet_mode = normalize_bet_mode(bet_mode)
    return MODE_ORDER if bet_mode == "all" else [bet_mode]


def get_mode_feature_rows(df_prize, anchor_date, mode):
    """每個投注模式獨立取得自己的 C4 分析特徵期。"""
    history = df_prize[df_prize["ndate"] <= str(anchor_date)].tail(FEATURE_LOOKBACK_DRAW)
    if mode == "prize3":
        return history.sort_values(
            by=["prize3", "prize3_unit", "ndate"],
            ascending=[False, False, False],
        ).head(PRIZE3_TOP_DRAW).reset_index(drop=True)
    if mode == "prize2":
        return history.sort_values(
            by=["prize2", "prize2_unit", "ndate"],
            ascending=[False, False, False],
        ).head(PRIZE2_TOP_DRAW).sort_values("ndate").reset_index(drop=True)
    if mode == "prize1":
        return history[history["prize1"] == 0].tail(HEAD_PRIZE_ZERO_TOP_DRAW).sort_values(
            "ndate",
        ).reset_index(drop=True)
    raise ValueError(f"未知 mode: {mode}")


def nums_for_mode_row(row, mode):
    """2獎分析使用 N1-N7，其餘投注模式使用 N1-N6。"""
    return get_all_nums(row) if mode == "prize2" else get_main_nums(row)


def build_feature_counter(feature_rows, mode):
    """RBG 分析號碼權重；2獎包含 N7 特號。"""
    counter = Counter()
    prize_col = {"prize3": "prize3", "prize2": "prize2", "prize1": "prize2"}[mode]
    top_draw = max(1, len(feature_rows))
    for rank, (_, row) in enumerate(feature_rows.iterrows(), 1):
        rank_bonus = top_draw - rank + 1
        prize_bonus = max(1, int(float(row.get(prize_col, 0)) // 3))
        for num in nums_for_mode_row(row, mode):
            counter[int(num)] += rank_bonus + prize_bonus
    return counter


def build_recent_counter(df_draw, anchor_date, lookback=RECENT_LOOKBACK_DRAW):
    recent_rows = df_draw[df_draw["ndate"] <= str(anchor_date)].tail(lookback)
    nums = []
    for _, row in recent_rows.iterrows():
        nums.extend(get_main_nums(row))
    return Counter(nums)


def choose_interval_slots(feature_rows, mode):
    """依各模式自己的 interval pattern 取 6 個投注 slot。"""
    pattern_counter = Counter()
    latest_seen = {}
    for row_idx, row in feature_rows.iterrows():
        pattern = get_interval_pattern(nums_for_mode_row(row, mode))
        pattern_counter[pattern] += 1
        latest_seen[pattern] = row_idx

    if not pattern_counter:
        return [0, 1, 2, 3, 3, 4], pattern_counter

    best_pattern = sorted(
        pattern_counter.items(),
        key=lambda item: (-item[1], -latest_seen[item[0]], item[0]),
    )[0][0]
    slots = list(best_pattern)

    if len(slots) > 6:
        interval_score = Counter()
        for pattern, count in pattern_counter.items():
            interval_score.update({interval_id: count for interval_id in pattern})
        remove_idx = min(
            range(len(slots)),
            key=lambda idx: (interval_score[slots[idx]], slots[idx], idx),
        )
        slots.pop(remove_idx)

    while len(slots) < 6:
        interval_frequency = Counter()
        for pattern, count in pattern_counter.items():
            interval_frequency.update({interval_id: count for interval_id in pattern})
        next_interval = interval_frequency.most_common(1)[0][0]
        slots.append(next_interval)

    return sorted(slots), pattern_counter


def build_tail_bonus(feature_counter):
    tail_counter = Counter(num % 10 for num in feature_counter)
    return {num: tail_counter[num % 10] for num in range(1, 50)}


def special_feature_score(num, feature_counter, profile, tail_bonus):
    score = 0.0
    tags = []
    if 1 <= num <= 31:
        score += profile["birthday"] * 4
        tags.append("生日")
    if tail_bonus.get(num, 0) >= 2:
        score += profile["same_tail"] * tail_bonus[num] * 2
        tags.append("同尾")
    if num in {10, 20, 30, 40}:
        score += profile["round_tens"] * 6
        tags.append("整十")
    if feature_counter.get(num, 0):
        tags.append("RBG")
    return score, tags


def rank_interval_candidates(interval_id, mode, feature_counter, recent_counter, selected):
    profile = FEATURE_PROFILES[mode]
    tail_bonus = build_tail_bonus(feature_counter)
    candidates = []
    for num in nums_in_interval(interval_id):
        if num in selected:
            continue
        feature_score = feature_counter.get(num, 0) * 10
        recent_score = recent_counter.get(num, 0)
        special_score, tags = special_feature_score(num, feature_counter, profile, tail_bonus)
        score = feature_score + recent_score + special_score
        candidates.append((num, score, tags))
    return sorted(candidates, key=lambda item: (-item[1], item[0]))


def generate_bet_for_mode(mode, interval_slots, feature_counter, recent_counter, variant=0):
    """每個獎項模式只產生 1 注單式。"""
    rng = random.Random(RANDOM_SEED + variant + MODE_ORDER.index(mode) * 100)
    selected = []
    selected_details = []

    for slot_idx, interval_id in enumerate(interval_slots):
        ranked = rank_interval_candidates(interval_id, mode, feature_counter, recent_counter, selected)
        if not ranked:
            pool = [num for num in nums_in_interval(interval_id) if num not in selected]
            picked = rng.choice(pool) if pool else rng.choice([num for num in range(1, 50) if num not in selected])
            selected.append(picked)
            selected_details.append((picked, 0, ["fallback"]))
            continue

        pick_idx = min(variant + slot_idx, len(ranked) - 1)
        picked, score, tags = ranked[pick_idx]
        selected.append(picked)
        selected_details.append((picked, score, tags))

    return sorted(selected), selected_details


def build_mode_prediction(df_draw, df_prize, anchor_date, mode, variant=0):
    feature_rows = get_mode_feature_rows(df_prize, anchor_date, mode)
    feature_counter = build_feature_counter(feature_rows, mode)
    recent_counter = build_recent_counter(df_draw, anchor_date)
    interval_slots, pattern_counter = choose_interval_slots(feature_rows, mode)
    bet, details = generate_bet_for_mode(
        mode=mode,
        interval_slots=interval_slots,
        feature_counter=feature_counter,
        recent_counter=recent_counter,
        variant=variant,
    )
    return {
        "mode": mode,
        "label": MODE_LABELS[mode],
        "anchor_date": str(anchor_date),
        "feature_rows": feature_rows,
        "feature_counter": feature_counter,
        "pattern_counter": pattern_counter,
        "interval_slots": interval_slots,
        "bet": bet,
        "details": details,
    }


def get_next_draw_date(df_draw, anchor_date, df_summary=None):
    if df_summary is not None and not df_summary.empty:
        matched = df_summary[df_summary["last_draw_date"] == str(anchor_date)]
        if not matched.empty:
            next_draw_date = str(matched.iloc[-1]["next_draw_date"]).strip()
            if next_draw_date:
                return next_draw_date

    future_rows = df_draw[df_draw["ndate"] > str(anchor_date)]
    if not future_rows.empty:
        return str(future_rows.iloc[0]["ndate"])
    return "下一期"


def build_bets_for_anchor(df_draw, df_prize, anchor_date, bet_mode, df_summary=None):
    results = []
    for variant, mode in enumerate(selected_modes(bet_mode)):
        results.append(build_mode_prediction(df_draw, df_prize, anchor_date, mode, variant=variant))
    return {
        "anchor_date": str(anchor_date),
        "next_draw_date": get_next_draw_date(df_draw, anchor_date, df_summary=df_summary),
        "mode_results": results,
        "bets": [result["bet"] for result in results],
    }


def check_prize_hits(bets, draw_nums, special_num):
    result = []
    draw_set = set(int(num) for num in draw_nums)
    special_num = int(special_num)
    for bet in bets:
        matched = sorted(set(bet) & draw_set)
        special_hit = special_num in set(bet)
        score = float(len(matched)) + (0.5 if special_hit else 0.0)
        result.append({
            "bet": bet,
            "matched": matched,
            "hit_count": len(matched),
            "special_hit": special_hit,
            "score": score,
            "prize_label": PRIZE_LABELS.get(score, ""),
        })
    return result


def bets_from_df(df):
    bets = []
    for _, row in df.iterrows():
        mode = {
            "3": "prize3",
            "2": "prize2",
            "1": "prize1",
            3: "prize3",
            2: "prize2",
            1: "prize1",
        }.get(row.get("prize", ""), "prize3")
        bets.append({
            "mode": mode,
            "bet": [int(row[f"N{i}"]) for i in range(1, 7)],
        })
    return bets


def sync_win_results_from_bets(df_draw):
    """預測模式啟動時，補核對已開獎但未寫入 win_results 的投注。"""
    bet_df = read_bet_csv(PRIZE123_BET_CSV)
    if bet_df.empty:
        return

    existing_win_dates = set(read_bet_csv(PRIZE123_WIN_RESULTS_CSV)["bet_date"].astype(str))
    draw_date_set = set(df_draw["ndate"].astype(str))
    appended_dates = []

    for bet_date in sorted(set(bet_df["bet_date"].astype(str))):
        if bet_date in existing_win_dates:
            continue
        if bet_date not in draw_date_set:
            continue

        draw_row = df_draw[df_draw["ndate"].astype(str) == bet_date].iloc[-1]
        draw_nums = get_main_nums(draw_row)
        date_mode_results = bets_from_df(bet_df[bet_df["bet_date"].astype(str) == bet_date])
        hit_rows = check_prize_hits([row["bet"] for row in date_mode_results], draw_nums, int(draw_row["N7"]))
        append_win_results(bet_date, date_mode_results, hit_rows)
        appended_dates.append(bet_date)

    if appended_dates:
        print(f"已補核對 prize123_win_results.csv 日期: {appended_dates}")


def print_feature_table(mode_result):
    cols = ["ndate", "N1", "N2", "N3", "N4", "N5", "N6"]
    mode = mode_result["mode"]
    if mode == "prize2":
        cols.append("N7")
    prize_col = {"prize3": "prize3", "prize2": "prize2", "prize1": "prize1"}[mode]
    cols.append(prize_col)
    table_df = mode_result["feature_rows"][cols].copy()
    table_df.insert(0, "檔位", range(1, len(table_df) + 1))
    print(table_df.to_string(index=False))


def print_mode_result(mode_result):
    mode = mode_result["mode"]
    nums = []
    for _, row in mode_result["feature_rows"].iterrows():
        nums.extend(nums_for_mode_row(row, mode))

    print(f"\n====== {mode_result['label']} ======")
    print_feature_table(mode_result)
    print_rbg_groups(f"{mode_result['label']} 特徵球 RBG 分組", nums)

    print("\ninterval pattern 統計:")
    for pattern, count in mode_result["pattern_counter"].most_common():
        print(f"{list(pattern)}: {count}")
    print(f"選用投注區間: {mode_result['interval_slots']}")

    print("\n候選球權重 Top 15:")
    for num, score in mode_result["feature_counter"].most_common(15):
        print(f"{num}: {score}")

    print("\n選球特式:")
    for num, score, tags in mode_result["details"]:
        tag_text = ",".join(tags) if tags else "-"
        print(f"{num}: score={score:.1f} / {tag_text}")
    print(f"投注號碼: {mode_result['bet']}")


def print_strategy_result(result):
    print("\n====== C6 1,2,3獎策略預測投注 ======")
    print(f"最後一期: {result['anchor_date']}")
    print(f"下期日期: {result['next_draw_date']}")
    print(f"產生注數: {len(result['bets'])}")
    for mode_result in result["mode_results"]:
        print_mode_result(mode_result)

    print("\n====== 最終單式投注 ======")
    for idx, bet in enumerate(result["bets"], 1):
        print(f"{idx}. {result['next_draw_date']} {bet}")


def run_predict(bet_mode):
    bet_mode = normalize_bet_mode(bet_mode)
    df_draw = load_draw_history()
    df_prize = load_prize_history()
    df_summary = load_prize_summary()
    remove_placeholder_next_draw_rows()
    sync_win_results_from_bets(df_draw)
    anchor_date = str(df_draw.iloc[-1]["ndate"])
    result = build_bets_for_anchor(df_draw, df_prize, anchor_date, bet_mode, df_summary=df_summary)
    print_strategy_result(result)
    if bet_mode == "all":
        append_bet_records_if_missing(result["next_draw_date"], result["mode_results"])
        replace_next_draw_bets(result["next_draw_date"], result["mode_results"])
    else:
        replace_predict_records_for_date(result["next_draw_date"], result["mode_results"])


def run_backtest(bet_mode):
    df_draw = load_draw_history()
    df_prize = load_prize_history()
    df_summary = load_prize_summary()
    start_idx = max(1, len(df_draw) - BACKTEST_DRAW)
    total_bets = 0
    prize_counter = Counter()

    print("\n====== C6 1,2,3獎策略回測 ======")
    print(f"回測最近 {len(df_draw) - start_idx} 期，模式: {normalize_bet_mode(bet_mode)}")

    for target_idx in range(start_idx, len(df_draw)):
        anchor_row = df_draw.iloc[target_idx - 1]
        target_row = df_draw.iloc[target_idx]
        anchor_date = str(anchor_row["ndate"])
        target_date = str(target_row["ndate"])
        target_nums = get_main_nums(target_row)
        target_special = int(target_row["N7"])

        result = build_bets_for_anchor(df_draw, df_prize, anchor_date, bet_mode, df_summary=df_summary)
        hit_rows = check_prize_hits(result["bets"], target_nums, target_special)
        append_bet_records(target_date, result["mode_results"])
        append_win_results(target_date, result["mode_results"], hit_rows)
        print(f"\n>>> anchor={anchor_date} -> target={target_date}")
        print(f"    真實正號: {target_nums} + 特號 {target_special}")
        for idx, row in enumerate(hit_rows, 1):
            total_bets += 1
            if row["score"] in PRIZE_LABELS:
                prize_counter[row["score"]] += 1
            special_text = f" + 特[{target_special}]" if row["special_hit"] else ""
            prize_text = row["prize_label"]
            mode_name = result["mode_results"][idx - 1]["mode"]
            print(
                f"    {idx}. {mode_name} {row['bet']} -> 中 {row['matched']}{special_text} "
                f"/ {row['score']:g} {prize_text}"
            )

    print("\n====== C6 回測總結 ======")
    print(f"總投注: {total_bets} 注")
    for score in PRIZE_SCORES:
        print(f"{PRIZE_LABELS[score]} = {prize_counter.get(score, 0)} 注")
    total_win = sum(prize_counter.values())
    print(f"總中獎注數: {total_win} 注")
    if total_bets:
        print(f"總中獎率: {(total_win / total_bets) * 100:.2f}%")
    # print("\n已更新回測 CSV:")
    # print(f"- {PRIZE123_BET_CSV}")
    # print(f"- {PRIZE123_WIN_RESULTS_CSV}")


def parse_args():
    run_mode = RUN_MODE
    bet_mode = BET_MODE
    if len(sys.argv) >= 2:
        run_mode = sys.argv[1].strip().lower()
    if len(sys.argv) >= 3:
        bet_mode = sys.argv[2].strip().lower()
    return run_mode, normalize_bet_mode(bet_mode)


def main():
    
    run_mode, bet_mode = parse_args()
    if run_mode == "backtest":
        reset_output_csvs()
        run_backtest(bet_mode)
    elif run_mode == "predict":
        ensure_output_csvs()
        run_predict(bet_mode)
    else:
        raise ValueError(f"未知 RUN_MODE: {run_mode}")


if __name__ == "__main__":
    main()
