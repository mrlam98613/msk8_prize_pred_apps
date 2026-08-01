from collections import Counter
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import random

import pandas as pd

import res_func_num_convert_RBG_Dict
import res_predict_N1_N6_interval_BackTest


"""
C5：3獎雙模式回測及投注策略

功能：
1. 只使用 3獎資料，不使用 2獎、1獎功能。
2. 以 3獎中獎注數最多及每注獎金作排序，取出高特徵號碼。
3. 套入 res_predict_N1_N6_interval_BackTest.py 的下期 N1-N6 區間預測。
4. 可切換回測 / 預測投注模式。
5. 每期手動參數產生 1-3 注單式投注。

注意：
本程式第一版只打印分析及投注組合，不寫入網站用 CSV。
"""


CURRENT_DIR = Path(__file__).resolve().parent
DATA_DIR = CURRENT_DIR.parent / "A_msk_lottery_data_folder"
DRAW_HISTORY_CSV = DATA_DIR / "M2_last_upgrade_lotto_data.csv"
PRIZE_HISTORY_CSV = DATA_DIR / "M6_lotto_history_prize.csv"
BET_DATA_DIR = CURRENT_DIR / "bet_data"
PRIZE_BET_CSV = BET_DATA_DIR / "prize_bet.csv"
PRIZE_WIN_RESULTS_CSV = BET_DATA_DIR / "prize_win_results.csv"
PRIZE_NEXT_DRAW_BET_CSV = BET_DATA_DIR / "prize_nextDraw_bet.csv"

# ---------------------------- 手動參數 ----------------------------
RUN_MODE = "predict"  # "predict" / "backtest"
BACKTEST_DRAW = 10  # 回測最近幾期。
# ---------------------------- 內部參數 ----------------------------
FEATURE_LOOKBACK_DRAW = 24  # 每次分析 3獎時，往前看最近幾期。
PRIZE3_TOP_DRAW = 7  # 3獎中獎注數最多，取前幾期作特徵。
BET_COUNT = 3  # 每期產生 1-3 注單式。
INTERVAL_WINDOW_LIST = [6]  # 區間預測窗口。
FIXED_INTERVAL_MODE = "none"  # "head_tail" / "tail_only" / "none"
RANDOM_SEED = 42

DRAW_COLUMNS = ["ndate", "N1", "N2", "N3", "N4", "N5", "N6", "N7"]
BET_COLUMNS = ["bet_date", "N1", "N2", "N3", "N4", "N5", "N6"]
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


def reset_output_csvs():
    """回測模式使用：刪除並重新建立 C5 使用的三個 CSV。"""
    BET_DATA_DIR.mkdir(parents=True, exist_ok=True)
    for path in [PRIZE_BET_CSV, PRIZE_WIN_RESULTS_CSV, PRIZE_NEXT_DRAW_BET_CSV]:
        if path.exists():
            path.unlink()
        pd.DataFrame(columns=BET_COLUMNS).to_csv(path, index=False, encoding="utf-8-sig")


def ensure_output_csvs():
    """預測模式使用：只確保三個 CSV 存在，不刪除舊資料。"""
    BET_DATA_DIR.mkdir(parents=True, exist_ok=True)
    for path in [PRIZE_BET_CSV, PRIZE_WIN_RESULTS_CSV, PRIZE_NEXT_DRAW_BET_CSV]:
        if not path.exists():
            pd.DataFrame(columns=BET_COLUMNS).to_csv(path, index=False, encoding="utf-8-sig")


def rows_from_bets(bet_date, bets):
    """將多注單式轉成 CSV row dict。"""
    rows = []
    for bet in bets:
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
        })
    return rows


def append_csv_rows(path, rows):
    """累加寫入 CSV rows。"""
    if not rows:
        return
    old_df = pd.read_csv(path, encoding="utf-8-sig") if path.exists() else pd.DataFrame(columns=BET_COLUMNS)
    new_df = pd.DataFrame(rows, columns=BET_COLUMNS)
    pd.concat([old_df, new_df], ignore_index=True).to_csv(path, index=False, encoding="utf-8-sig")


def read_bet_csv(path):
    """讀取 C5 bet CSV，若不存在則回傳空表。"""
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame(columns=BET_COLUMNS)
    df = pd.read_csv(path, encoding="utf-8-sig")
    if not set(BET_COLUMNS).issubset(df.columns):
        return pd.DataFrame(columns=BET_COLUMNS)
    return df[BET_COLUMNS].copy()


def has_records_for_date(path, bet_date):
    """檢查指定 CSV 是否已有某日期紀錄。"""
    df = read_bet_csv(path)
    if df.empty:
        return False
    return str(bet_date) in set(df["bet_date"].astype(str))


def append_bet_records(bet_date, bets):
    """回測投注紀錄累加寫入 prize_bet.csv。"""
    append_csv_rows(PRIZE_BET_CSV, rows_from_bets(bet_date, bets))


def append_win_results(bet_date, hit_rows):
    """回測核對結果累加寫入 prize_win_results.csv。"""
    rows = []
    for hit_row in hit_rows:
        matched_set = set(hit_row["matched"])
        win_nums = [num if num in matched_set else 0 for num in hit_row["bet"]]
        rows.extend(rows_from_bets(bet_date, [win_nums]))
    append_csv_rows(PRIZE_WIN_RESULTS_CSV, rows)


def append_next_draw_bets_if_missing(bet_date, bets):
    """預測模式：下一期投注若不存在才追尾加入。"""
    if has_records_for_date(PRIZE_NEXT_DRAW_BET_CSV, bet_date):
        print(f"prize_nextDraw_bet.csv 已有 {bet_date} 紀錄，不重複加入。")
        return
    append_csv_rows(PRIZE_NEXT_DRAW_BET_CSV, rows_from_bets(bet_date, bets))


def append_bet_records_if_missing(bet_date, bets):
    """預測模式：prize_bet.csv 若沒有該期投注，才追尾加入。"""
    if has_records_for_date(PRIZE_BET_CSV, bet_date):
        print(f"prize_bet.csv 已有 {bet_date} 投注紀錄，不重複加入。")
        return
    append_bet_records(bet_date, bets)


def save_next_draw_bets(bet_date, bets):
    """保留給手動覆蓋用途：只寫入下一期投注，不累加。"""
    rows = rows_from_bets(bet_date, bets)
    pd.DataFrame(rows, columns=BET_COLUMNS).to_csv(
        PRIZE_NEXT_DRAW_BET_CSV,
        index=False,
        encoding="utf-8-sig",
    )


def load_draw_history():
    """讀取 M2 開獎歷史。"""
    df = pd.read_csv(DRAW_HISTORY_CSV, encoding="utf-8-sig")
    df = df[DRAW_COLUMNS].copy()
    df["ndate"] = df["ndate"].astype(str).str.strip()
    for col in DRAW_COLUMNS[1:]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    return df.sort_values("ndate").reset_index(drop=True)


def load_prize_history():
    """讀取 M6 3獎中獎注數及獎金資料。"""
    df = pd.read_csv(
        PRIZE_HISTORY_CSV,
        encoding="utf-8-sig",
        dtype={"nDdate": str},
    )
    df = df.rename(columns={"nDdate": "ndate"})
    df["ndate"] = df["ndate"].astype(str).str.strip()
    for col in ["N1", "N2", "N3", "N4", "N5", "N6", "N7"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    for col in ["prize3", "prize3_unit"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df.sort_values("ndate").reset_index(drop=True)


def get_main_nums(row):
    """取得 N1-N6 正號。"""
    return [int(row[f"N{i}"]) for i in range(1, 7)]


def get_num49_interval_map(nums):
    """將號碼轉成區間：0=1-9, 1=10-19, 2=20-29, 3=30-40, 4=41-49。"""
    interval_map = {
        0: list(range(1, 10)),
        1: list(range(10, 20)),
        2: list(range(20, 30)),
        3: list(range(30, 41)),
        4: list(range(41, 50)),
    }
    interval_idx = []
    for num in nums:
        for interval_id, interval_nums in interval_map.items():
            if int(num) in interval_nums:
                interval_idx.append(interval_id)
                break
    return interval_idx


def nums_in_interval(interval_id):
    """回傳指定區間的號碼清單。"""
    interval_map = {
        0: list(range(1, 10)),
        1: list(range(10, 20)),
        2: list(range(20, 30)),
        3: list(range(30, 41)),
        4: list(range(41, 50)),
    }
    return interval_map[interval_id]


def format_frequency_groups(nums):
    """將號碼按出現次數分組，多次出現排前，單次出現合併在最後。"""
    num_counter = Counter(int(num) for num in nums)
    repeated_groups = [
        [num] * count
        for num, count in sorted(
            num_counter.items(),
            key=lambda item: (-item[1], item[0]),
        )
        if count >= 2
    ]
    single_group = sorted(num for num, count in num_counter.items() if count == 1)
    if single_group:
        repeated_groups.append(single_group)
    return repeated_groups


def print_rbg_groups(title, nums):
    """列印號碼 R/B/G 三色分組。"""
    rbg_dict = res_func_num_convert_RBG_Dict.res_List_To_rbg_Dict_func(nums)
    print(f"\n====== {title} ======")
    print(f"R: {format_frequency_groups(rbg_dict.get(0, []))} /> {len(set(rbg_dict.get(0, [])))} 個不同球號")
    print(f"B: {format_frequency_groups(rbg_dict.get(1, []))} /> {len(set(rbg_dict.get(1, [])))} 個不同球號")
    print(f"G: {format_frequency_groups(rbg_dict.get(2, []))} /> {len(set(rbg_dict.get(2, [])))} 個不同球號")


def get_prize3_feature_rows(df_prize, anchor_date):
    """以 anchor_date 之前/當日資料，取最近 FEATURE_LOOKBACK_DRAW 期，再抽 3獎 top rows。"""
    history = df_prize[df_prize["ndate"] <= str(anchor_date)].tail(FEATURE_LOOKBACK_DRAW)
    return history.sort_values(
        by=["prize3", "prize3_unit", "ndate"],
        ascending=[False, False, False],
    ).head(PRIZE3_TOP_DRAW).reset_index(drop=True)


def build_feature_counter(feature_rows):
    """將 3獎 top rows 轉成候選球權重。"""
    counter = Counter()
    for rank, (_, row) in enumerate(feature_rows.iterrows(), 1):
        rank_bonus = PRIZE3_TOP_DRAW - rank + 1
        prize_bonus = max(1, int(float(row["prize3"]) // 50))
        for num in get_main_nums(row):
            counter[int(num)] += rank_bonus + prize_bonus
    return counter


def predict_interval(anchor_date, quiet=True):
    """呼叫區間預測程式，回傳下期區間預測結果。"""
    if quiet:
        with redirect_stdout(StringIO()):
            result = res_predict_N1_N6_interval_BackTest.predict_next_draw_intervals(
                window_list=INTERVAL_WINDOW_LIST,
                alpha=1.0,
                anchor_date=str(anchor_date),
                fixed_interval_mode=FIXED_INTERVAL_MODE,
            )
    else:
        result = res_predict_N1_N6_interval_BackTest.predict_next_draw_intervals(
            window_list=INTERVAL_WINDOW_LIST,
            alpha=1.0,
            anchor_date=str(anchor_date),
            fixed_interval_mode=FIXED_INTERVAL_MODE,
        )
    return result


def rank_interval_candidates(interval_id, feature_counter, recent_counter):
    """依 3獎特徵權重及近期出現次數排序指定區間候選球。"""
    candidates = []
    for num in nums_in_interval(interval_id):
        score = feature_counter.get(num, 0) * 10 + recent_counter.get(num, 0)
        if score > 0:
            candidates.append((num, score))
    if not candidates:
        candidates = [(num, recent_counter.get(num, 0)) for num in nums_in_interval(interval_id)]
    return [num for num, _ in sorted(candidates, key=lambda item: (-item[1], item[0]))]


def build_recent_counter(df_draw, anchor_date, lookback=14):
    """取 anchor_date 前後已知最近 lookback 期正號，作候選球 fallback。"""
    recent_rows = df_draw[df_draw["ndate"] <= str(anchor_date)].tail(lookback)
    nums = []
    for _, row in recent_rows.iterrows():
        nums.extend(get_main_nums(row))
    return Counter(nums)


def generate_bets_by_interval(pred_interval, feature_counter, recent_counter, bet_count):
    """依預測區間及 3獎特徵候選球，產生 1-3 注單式。"""
    rng = random.Random(RANDOM_SEED)
    interval_slots = sorted(int(interval_id) for interval_id in pred_interval)
    bets = []
    seen = set()

    for bet_idx in range(max(1, min(3, int(bet_count))) * 10):
        selected = []
        for slot_idx, interval_id in enumerate(interval_slots):
            ranked_nums = rank_interval_candidates(interval_id, feature_counter, recent_counter)
            offset = (bet_idx + slot_idx) % max(1, len(ranked_nums))
            rotated_nums = ranked_nums[offset:] + ranked_nums[:offset]
            picked = None
            for num in rotated_nums:
                if num not in selected:
                    picked = num
                    break
            if picked is None:
                picked = rng.choice([num for num in range(1, 50) if num not in selected])
            selected.append(picked)

        bet = tuple(sorted(selected))
        if len(bet) != 6 or bet in seen:
            continue
        seen.add(bet)
        bets.append(list(bet))
        if len(bets) >= max(1, min(3, int(bet_count))):
            break

    return bets


def build_bets_for_anchor(df_draw, df_prize, anchor_date, quiet_interval=True):
    """以指定 anchor_date 建立下一期 3獎策略投注組合。"""
    interval_result = predict_interval(anchor_date, quiet=quiet_interval)
    if not interval_result:
        return None

    feature_rows = get_prize3_feature_rows(df_prize, anchor_date)
    feature_counter = build_feature_counter(feature_rows)
    recent_counter = build_recent_counter(df_draw, anchor_date)
    bets = generate_bets_by_interval(
        pred_interval=interval_result["pred_interval"],
        feature_counter=feature_counter,
        recent_counter=recent_counter,
        bet_count=BET_COUNT,
    )

    return {
        "anchor_date": str(anchor_date),
        "next_draw_date": interval_result["next_draw_date"],
        "pred_interval": interval_result["pred_interval"],
        "feature_rows": feature_rows,
        "feature_counter": feature_counter,
        "bets": bets,
    }


def check_prize_hits(bets, draw_nums, special_num):
    """以每注為單位核對 1-7 獎，特別號命中加 0.5。"""
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
    """將 bet CSV DataFrame 轉成 list[list[int]]。"""
    bets = []
    for _, row in df.iterrows():
        bets.append([int(row[f"N{i}"]) for i in range(1, 7)])
    return bets


def sync_win_results_from_bets(df_draw):
    """依 prize_bet.csv 補核對 prize_win_results.csv，已有核對日期不重複追加。"""
    bet_df = read_bet_csv(PRIZE_BET_CSV)
    if bet_df.empty:
        return

    existing_win_dates = set(read_bet_csv(PRIZE_WIN_RESULTS_CSV)["bet_date"].astype(str))
    draw_date_set = set(df_draw["ndate"].astype(str))
    appended_dates = []

    for bet_date in sorted(set(bet_df["bet_date"].astype(str))):
        if bet_date in existing_win_dates:
            continue
        if bet_date not in draw_date_set:
            continue

        draw_row = df_draw[df_draw["ndate"].astype(str) == bet_date].iloc[-1]
        draw_nums = get_main_nums(draw_row)
        date_bets = bets_from_df(bet_df[bet_df["bet_date"].astype(str) == bet_date])
        hit_rows = check_prize_hits(date_bets, draw_nums, int(draw_row["N7"]))
        append_win_results(bet_date, hit_rows)
        appended_dates.append(bet_date)

    if appended_dates:
        print(f"已補核對 prize_win_results.csv 日期: {appended_dates}")


def print_strategy_result(result):
    """打印預測投注結果。"""
    print("\n====== C5 3獎策略預測投注 ======")
    print(f"最後一期: {result['anchor_date']}")
    print(f"下期日期: {result['next_draw_date']}")
    print(f"區間預測: {result['pred_interval']}")

    feature_nums = []
    for _, row in result["feature_rows"].iterrows():
        feature_nums.extend(get_main_nums(row))
    print_rbg_groups(
        f"3獎 top {len(result['feature_rows'])} 期 X 6 正號 = {len(feature_nums)} 球 RBG 分組",
        feature_nums,
    )

    print("\n====== 3獎特徵候選球權重 ======")
    for num, score in result["feature_counter"].most_common(20):
        print(f"{num}: {score}")

    print(f"\n====== 手動產生 {len(result['bets'])} 注單式 ======")
    for idx, bet in enumerate(result["bets"], 1):
        print(f"{idx}. {result['next_draw_date']} {bet}")


def run_predict():
    """以下一期為目標產生 3獎策略投注。"""
    df_draw = load_draw_history()
    df_prize = load_prize_history()
    sync_win_results_from_bets(df_draw)

    anchor_date = str(df_draw.iloc[-1]["ndate"])
    result = build_bets_for_anchor(df_draw, df_prize, anchor_date, quiet_interval=False)
    if result is None:
        print("未能產生預測投注。")
        return
    print_strategy_result(result)
    append_bet_records_if_missing(result["next_draw_date"], result["bets"])
    append_next_draw_bets_if_missing(result["next_draw_date"], result["bets"])
    print(f"\n已更新投注 CSV:")
    print(f"- {PRIZE_BET_CSV}")
    print(f"- {PRIZE_WIN_RESULTS_CSV}")
    print(f"- {PRIZE_NEXT_DRAW_BET_CSV}")


def run_backtest():
    """回測最近 BACKTEST_DRAW 期，每期以前一期作 anchor 預測目標期。"""
    df_draw = load_draw_history()
    df_prize = load_prize_history()
    start_idx = max(1, len(df_draw) - BACKTEST_DRAW)
    total_bets = 0
    prize_counter = Counter()

    print("\n====== C5 3獎策略回測 ======")
    print(f"回測最近 {len(df_draw) - start_idx} 期，每期 {BET_COUNT} 注")

    for target_idx in range(start_idx, len(df_draw)):
        anchor_row = df_draw.iloc[target_idx - 1]
        target_row = df_draw.iloc[target_idx]
        anchor_date = str(anchor_row["ndate"])
        target_date = str(target_row["ndate"])
        target_nums = get_main_nums(target_row)
        target_special = int(target_row["N7"])

        result = build_bets_for_anchor(df_draw, df_prize, anchor_date, quiet_interval=True)
        if result is None:
            continue

        hit_rows = check_prize_hits(result["bets"], target_nums, target_special)
        append_bet_records(target_date, result["bets"])
        append_win_results(target_date, hit_rows)
        print(f"\n>>> anchor={anchor_date} -> target={target_date}")
        print(f"    預測區間: {result['pred_interval']} / 真實區間: {get_num49_interval_map(target_nums)}")
        print(f"    真實正號: {target_nums} + 特號 {target_special}")
        for idx, row in enumerate(hit_rows, 1):
            total_bets += 1
            if row["score"] in PRIZE_LABELS:
                prize_counter[row["score"]] += 1
            special_text = f" + 特[{target_special}]" if row["special_hit"] else ""
            prize_text = row["prize_label"]
            print(
                f"    {idx}. {row['bet']} -> 中 {row['matched']}{special_text} "
                f"/ {row['score']:g} {prize_text}"
            )

    print("\n====== C5 回測總結 ======")
    print(f"總投注: {total_bets} 注")
    for score in PRIZE_SCORES:
        print(f"{PRIZE_LABELS[score]} = {prize_counter.get(score, 0)} 注")
    total_win = sum(prize_counter.values())
    print(f"總中獎注數: {total_win} 注")
    if total_bets:
        print(f"總中獎率: {(total_win / total_bets) * 100:.2f}%")


def main():
    if RUN_MODE == "backtest":
        reset_output_csvs()
        run_backtest()
    elif RUN_MODE == "predict":
        ensure_output_csvs()
        run_predict()
    else:
        raise ValueError(f"未知 RUN_MODE: {RUN_MODE}")


if __name__ == "__main__":
    main()
