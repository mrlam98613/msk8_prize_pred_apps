#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新版種子投注主流程。
主要回傳程式，
1, seed_lotto_strategy.py 內的種子投注策略，會被 A1_seedBet_main.py 呼叫。
    see_lotto_strategy, 
    包含：res_predict_N1.._n6.py
    func2_RBG_collect_5balls_.py
    
2, 這支程式雙模式，核對 + 預測。
3, 刪除 bet_data/*.csv 後，全新輸入回測期數，會自動重新初始化回測。

重設回測參數：
1. 不改動舊版 msk_seedLotto_apps/ 任何檔案。
2. 只讀取 A_msk_lottery_data_folder/ 內已由 Z3 驗證/複製的開獎資料。
3. 所有投注結果只寫入本資料夾 bet_data/。
4. 刪除 bet_data/*.csv 後，下次執行會自動重新初始化回測。
"""

from __future__ import annotations

import csv
import datetime as dt
import random
import re
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import pandas as pd
from pandas.errors import ParserWarning

''' 重點傳入種子投注策略 '''
import seed_lotto_strategy

CURRENT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = CURRENT_DIR.parent
# 預測data目錄
BET_DATA_DIR = CURRENT_DIR / "bet_data"
# 所有開獎紀錄目錄
DATA_DIR = WORKSPACE_ROOT / "A_msk_lottery_data_folder"

# 2002_lastDraw開獎紀錄
DRAW_HISTORY_CSV = DATA_DIR / "M2_last_upgrade_lotto_data.csv"
# 最後派彩結果紀錄
DRAW_PRIZE_CSV = DATA_DIR / "M3_lotto_prize_results.csv"

BET_RECORD_CSV = BET_DATA_DIR / "my_bet_records.csv" # 投注總紀錄
WIN_RECORD_CSV = BET_DATA_DIR / "my_win_results.csv" #核對中獎總紀錄
NEXT_RECORD_CSV = BET_DATA_DIR / "nextBetDraw_record.csv" # 下期投注紀錄
NEXT_SUMMARY_CSV = BET_DATA_DIR / "nextBetDraw_summary.csv" # 下期日期及種子提示

# ---------------------------------------- parmater -----------------------------|
BACKTEST_LAST_DRAW = 40 # 刪除data, 重新輸入回測期數
BET_UNIT = 10 # 計算以 10 元投注為單位。
COLLECT_BALLS_BREAK = 9 # RBG 三種顏色球收集 9 球以上就停止。
DRAW_SAME_COLOR = 3 #收集該期有周一顏色的球數。例如該期紅色球有 3 球以上。
# ===============================================================================
DRAW_COLUMNS = ["ndate", "N1", "N2", "N3", "N4", "N5", "N6", "N7"]
BET_COLUMNS = ["bet_date", "N1", "N2", "N3", "N4", "N5", "N6"]
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ZH_DATE_PATTERN = re.compile(r"(\d{4})年(\d{2})月(\d{2})日(?:\s+\((.)\))?")

PRIZE_TABLE = {
    6.0: 10000000,
    5.5: 1100000,
    5.0: 300000,
    4.5: 9600,
    4.0: 640,
    3.5: 320,
    3.0: 40,
}

PRIZE_LABELS = {
    6.0: "一獎  6 正號      ",
    5.5: "二獎  5 正 + 特別號",
    5.0: "三獎  5 正號      ",
    4.5: "四獎  4 正 + 特別號",
    4.0: "五獎  4 正號      ",
    3.5: "六獎  3 正 + 特別號",
    3.0: "七獎  3 正號      ",
}

WEEK_ZH = {
    "1": "星期一",
    "2": "星期二",
    "3": "星期三",
    "4": "星期四",
    "5": "星期五",
    "6": "星期六",
    "7": "星期日",
}
ZH_WEEK_TO_NUM = {"一": "1", "二": "2", "三": "3", "四": "4", "五": "5", "六": "6", "日": "7"}


@dataclass(frozen=True)
class NextDrawInfo:
    """下一期開獎資料。"""

    date: str
    week: str
    anchor_date: str


@dataclass
class SettlementResult:
    """單期核對後的策略輸入資料。"""

    matched_numbers: list[int]
    win_rows: list[list[int]]
    last_bet: list[int]
    total_prize: int
    total_bets: int
    hit_counter: dict[float, int]


def is_valid_date(value: object) -> bool:
    return bool(DATE_PATTERN.match(str(value).strip()))


def ensure_bet_data_dir() -> None:
    BET_DATA_DIR.mkdir(parents=True, exist_ok=True)


def read_csv_required(path: Path, required_columns: list[str]) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"找不到資料檔：{path}")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ParserWarning)
        df = pd.read_csv(path, encoding="utf-8-sig", index_col=False)
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise ValueError(f"{path.name} 缺少欄位：{missing}")
    if df.empty:
        raise ValueError(f"{path.name} 沒有資料")
    return df


def load_draw_history() -> pd.DataFrame:
    """讀取並清理 M2 開獎歷史。"""

    df = read_csv_required(DRAW_HISTORY_CSV, DRAW_COLUMNS)
    df = df[DRAW_COLUMNS].copy()
    df["ndate"] = df["ndate"].astype(str).str.strip()
    df = df[df["ndate"].map(is_valid_date)]

    for col in DRAW_COLUMNS[1:]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=DRAW_COLUMNS[1:]).copy()
    for col in DRAW_COLUMNS[1:]:
        df[col] = df[col].astype(int)

    df = df.drop_duplicates(subset="ndate", keep="last")
    df = df.sort_values("ndate").reset_index(drop=True)
    if df.empty:
        raise ValueError("M2 找不到有效開獎資料")
    return df


def parse_zh_date(value: str) -> tuple[str, str | None]:
    """解析 M3 內的中文日期，回傳 (YYYY-MM-DD, week_or_none)。"""

    match = ZH_DATE_PATTERN.search(value.strip())
    if match is None:
        raise ValueError(f"日期格式不正確：{value}")

    date_text = f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    week_text = match.group(4)
    return date_text, ZH_WEEK_TO_NUM.get(week_text) if week_text else None


def read_m3_rows() -> list[list[str]]:
    """讀取 M3 原始列。M3 是章節式 CSV，不適合用 DataFrame 當表格讀。"""

    if not DRAW_PRIZE_CSV.exists():
        raise FileNotFoundError(f"找不到資料檔：{DRAW_PRIZE_CSV}")

    with DRAW_PRIZE_CSV.open("r", encoding="utf-8-sig", newline="") as file:
        return [[cell.strip() for cell in row] for row in csv.reader(file) if row]


def load_next_draw_info(df_all: pd.DataFrame) -> NextDrawInfo:
    """從 M3 讀取最後一期與下期開獎資料，並確認它對上 M2 最新期。"""

    rows = read_m3_rows()
    row_map = {row[0]: row[1:] for row in rows if len(row) >= 2}

    if "日期" not in row_map or "號碼" not in row_map or "開獎日期" not in row_map:
        raise ValueError("M3 缺少 日期 / 號碼 / 開獎日期 資料")

    anchor_date, _ = parse_zh_date(row_map["日期"][0])
    next_draw_date, next_week = parse_zh_date(row_map["開獎日期"][0])
    if next_week is None:
        raise ValueError(f"M3 下期開獎日期缺少星期：{row_map['開獎日期'][0]}")

    m3_numbers = [int(n.strip()) for n in row_map["號碼"][0].split(",") if n.strip()]
    if len(m3_numbers) != 7:
        raise ValueError(f"M3 最新一期號碼數量不是 7 個：{m3_numbers}")

    latest_row = df_all.iloc[-1]
    latest_draw_date = str(latest_row["ndate"])
    latest_numbers = [int(latest_row[f"N{i}"]) for i in range(1, 8)]
    if anchor_date != latest_draw_date:
        raise ValueError(f"M2/M3 最新期不一致：M2={latest_draw_date}, M3={anchor_date}")
    if m3_numbers != latest_numbers:
        raise ValueError(f"M2/M3 最新期號碼不一致：M2={latest_numbers}, M3={m3_numbers}")

    return NextDrawInfo(date=next_draw_date, week=next_week, anchor_date=anchor_date)


def normalize_bets(bets: Iterable[Iterable[int]] | Iterable[int]) -> list[list[int]]:
    """接受單注或多注，統一轉成 list[list[int]]。"""

    # 若 bets 是單一 int，直接包成 list[list[int]]
    if isinstance(bets, int):
        return [[int(bets)]]
    # 若 bets 是 str/bytes，視為錯誤
    if isinstance(bets, (str, bytes)):
        raise TypeError("投注資料不能是字串型別")
    # 若 bets 是 numpy array 或 pandas Series，轉成 list
    try:
        import numpy as np
        import pandas as pd
        if isinstance(bets, (np.ndarray, pd.Series)):
            bet_list = bets.tolist()
        else:
            bet_list = list(bets)
    except ImportError:
        bet_list = list(bets)
    if not bet_list:
        return []
    # 嚴格檢查 bet_list 內容型別
    if all(isinstance(x, (int, float, str)) for x in bet_list):
        # 確保 bet_list 不是單一 Iterable[int] 物件
        def _to_int_safe(n):
            if not isinstance(n, (int, float, str)):
                raise TypeError(f"投注號碼型別錯誤: {n} ({type(n)})")
            return int(n)
        return [sorted(_to_int_safe(n) for n in bet_list)]
    elif all(isinstance(x, (list, tuple)) and all(isinstance(y, (int, float, str)) for y in x) for x in bet_list):
        # bet_list 是 Iterable[Iterable[int]]
        assert all(hasattr(bet, '__iter__') for bet in bet_list), "bet 不是可疊代型別"
        from typing import Iterable as _IterableType
        bet_list_typed: list[_IterableType[int | float | str]] = bet_list  # type: ignore
        def _to_int_safe(n):
            if not isinstance(n, (int, float, str)):
                raise TypeError(f"投注號碼型別錯誤: {n} ({type(n)})")
            return int(n)
        return [sorted(_to_int_safe(n) for n in bet) for bet in bet_list_typed]
    else:
        raise TypeError(f"投注資料型別不正確: {bet_list}")


def normalize_position_rows(rows: Iterable[Iterable[int]]) -> list[list[int]]:
    """保留 N1..N6 位置順序，用於中獎位置標記。"""

    return [[int(n) for n in row] for row in rows]


def rows_from_bets(bet_date: str, bets: list[list[int]]) -> list[dict[str, int | str]]:
    return [
        {
            "bet_date": bet_date,
            "N1": bet[0],
            "N2": bet[1],
            "N3": bet[2],
            "N4": bet[3],
            "N5": bet[4],
            "N6": bet[5],
        }
        for bet in bets
    ]


def replace_rows_for_date(path: Path, date_col: str, date_value: str, rows: list[dict[str, int | str]]) -> None:
    ensure_bet_data_dir()
    new_df = pd.DataFrame(rows)

    if path.exists() and path.stat().st_size > 0:
        old_df = pd.read_csv(path)
        if date_col in old_df.columns:
            old_df = old_df[old_df[date_col].astype(str) != str(date_value)]
        out_df = pd.concat([old_df, new_df], ignore_index=True)
    else:
        out_df = new_df

    out_df.to_csv(path, index=False)

''' 儲存下期預測投注紀錄 '''
def save_bet_record(bet_date: str, bets: Iterable[Iterable[int]] | Iterable[int]) -> None:
    bet_rows = rows_from_bets(bet_date, normalize_bets(bets))
    replace_rows_for_date(BET_RECORD_CSV, "bet_date", bet_date, bet_rows)

''' 儲存投注中獎種除紀錄 '''
def save_win_record(bet_date: str, win_rows: Iterable[Iterable[int]]) -> None:
    rows = rows_from_bets(bet_date, normalize_position_rows(win_rows))
    replace_rows_for_date(WIN_RECORD_CSV, "bet_date", bet_date, rows)

''' 儲存下期預測投注紀錄 '''
def save_next_prediction(bet_date: str, bets: Iterable[Iterable[int]] | Iterable[int]) -> None:
    rows = rows_from_bets(bet_date, normalize_bets(bets))
    ensure_bet_data_dir()
    pd.DataFrame(rows, columns=BET_COLUMNS).to_csv(NEXT_RECORD_CSV, index=False)


def save_next_prediction_summary(next_info: NextDrawInfo, seed_numbers: list[int]) -> None:
    """輸出給網頁顯示用的下期預測摘要。"""

    ensure_bet_data_dir()
    seed_text = ",".join(str(n) for n in seed_numbers) if seed_numbers else "無"
    row = {
        "bet_date": next_info.date,
        "week": next_info.week,
        "week_zh": WEEK_ZH.get(next_info.week, next_info.week),
        "seed_numbers": seed_text,
        "seed_count": len(seed_numbers),
        "has_seed": "yes" if seed_numbers else "no",
    }
    pd.DataFrame([row]).to_csv(NEXT_SUMMARY_CSV, index=False)



def read_bets_for_date(bet_date: str) -> pd.DataFrame:
    if not BET_RECORD_CSV.exists() or BET_RECORD_CSV.stat().st_size == 0:
        return pd.DataFrame(columns=BET_COLUMNS)
    df = pd.read_csv(BET_RECORD_CSV)
    if "bet_date" not in df.columns:
        return pd.DataFrame(columns=BET_COLUMNS)
    return df[df["bet_date"].astype(str) == str(bet_date)]


def read_next_prediction() -> pd.DataFrame:
    if not NEXT_RECORD_CSV.exists() or NEXT_RECORD_CSV.stat().st_size == 0:
        return pd.DataFrame(columns=BET_COLUMNS)
    df = pd.read_csv(NEXT_RECORD_CSV)
    if not set(BET_COLUMNS).issubset(df.columns):
        return pd.DataFrame(columns=BET_COLUMNS)
    df = df[BET_COLUMNS].copy()
    df["bet_date"] = df["bet_date"].astype(str).str.strip()
    df = df[df["bet_date"].map(is_valid_date)]
    return df


def latest_seed_numbers_from_win_record() -> list[int]:
    """從 my_win_results.csv 最後一期讀取種子球號。"""

    if not WIN_RECORD_CSV.exists() or WIN_RECORD_CSV.stat().st_size == 0:
        return []

    df = pd.read_csv(WIN_RECORD_CSV)
    if df.empty or "bet_date" not in df.columns:
        return []

    df["bet_date"] = df["bet_date"].astype(str).str.strip()
    valid_df = df[df["bet_date"].map(is_valid_date)].copy()
    if valid_df.empty:
        return []

    last_date = str(valid_df["bet_date"].max())
    last_rows = valid_df[valid_df["bet_date"] == last_date]
    seeds = {
        int(value)
        for _, row in last_rows.iterrows()
        for value in row.iloc[1:7]
        if pd.notna(value) and int(value) > 0
    }
    return sorted(seeds)


def format_seed_numbers(seed_numbers: list[int]) -> str:
    if not seed_numbers:
        return "無"
    return "[ " + "，".join(str(n) for n in seed_numbers) + " ]"


def is_initialized() -> bool:
    return (
        BET_RECORD_CSV.exists()
        and BET_RECORD_CSV.stat().st_size > 0
        and WIN_RECORD_CSV.exists()
        and WIN_RECORD_CSV.stat().st_size > 0
    )


def clear_result_csvs() -> None:
    for path in [BET_RECORD_CSV, WIN_RECORD_CSV, NEXT_RECORD_CSV, NEXT_SUMMARY_CSV]:
        if path.exists():
            path.unlink()


def random_base_draw(n_balls: int = 6, seed_val: int | None = None) -> list[int]:
    rng = random.Random(seed_val)
    return sorted(rng.sample(range(1, 50), n_balls))


def row_balls(row: pd.Series) -> tuple[list[int], int]:
    return [int(row[f"N{i}"]) for i in range(1, 7)], int(row["N7"])


def bet_values(row: pd.Series) -> list[int]:
    return [int(row[f"N{i}"]) for i in range(1, 7)]


def check_and_score(bet: list[int], draw_balls: list[int], special: int) -> tuple[set[int], bool, float, int]:
    matched = set(bet) & set(draw_balls)
    special_hit = special in set(bet)
    score = float(len(matched)) + 0.5 if special_hit else float(len(matched))
    return matched, special_hit, score, PRIZE_TABLE.get(score, 0)


''' -------- 重點回傳，種子投注策略 ---------- '''
def build_next_bets(
    matched_numbers: list[int],
    last_bet: list[int],
    seed_base: int,
    anchor_date: str,
    df_all: pd.DataFrame,
    ) -> list[list[int]]:
    
    return seed_lotto_strategy.generate_next_bets_with_strategy(
        sorted_matched=matched_numbers,
        last_bet_vals=last_bet,
        anchor_date=anchor_date,
        df_all=df_all,
        seed_base=seed_base,
        collect_balls_break=COLLECT_BALLS_BREAK,
        draw_same_color=DRAW_SAME_COLOR,
    )


def settle_draw(bet_date: str, bets: pd.DataFrame, draw_balls: list[int], special: int) -> SettlementResult:
    all_matched: set[int] = set()
    win_rows: list[list[int]] = []
    last_bet: list[int] = []
    total_prize = 0
    total_bets = 0
    hit_counter = {score: 0 for score in PRIZE_TABLE}

    for _, bet_row in bets.iterrows():
        total_bets += 1
        bet = bet_values(bet_row)
        last_bet = bet
        matched, special_hit, score, prize = check_and_score(bet, draw_balls, special)
        total_prize += prize
        if prize > 0:
            hit_counter[score] += 1

        all_matched |= matched
        win_rows.append([n if n in matched else 0 for n in bet])

        special_text = f" + 特[{special}]" if special_hit else ""
        if prize > 0:
            print(f"   投注 {sorted(bet)} -> 中 {sorted(matched)}{special_text} 命中={score} 派彩 ${prize:,}")
        elif matched or special_hit:
            print(f"   投注 {sorted(bet)} -> 中 {sorted(matched)}{special_text} 命中={score}")
        else:
            print(f"   投注 {sorted(bet)} -> 未中獎")

    save_win_record(bet_date, win_rows)
    return SettlementResult(
        matched_numbers=sorted(all_matched),
        win_rows=win_rows,
        last_bet=last_bet,
        total_prize=total_prize,
        total_bets=total_bets,
        hit_counter=hit_counter,
    )


def print_next_header(next_info: NextDrawInfo) -> None:
    print("=" * 56)
    print(f"上期種子球號 ： {format_seed_numbers(latest_seed_numbers_from_win_record())}")
    print(f"下期投注日期: {next_info.date} ({WEEK_ZH.get(next_info.week, next_info.week)})")

    next_df = read_next_prediction()
    if not next_df.empty and str(next_df["bet_date"].iloc[0]) == next_info.date:
        print()
        print("系統下期預測投注號碼：")
        for i, (_, row) in enumerate(next_df.iterrows(), 1):
            print(f"   {i}. {bet_values(row)}")
    print("=" * 56)


def print_next_bets(title: str, bet_date: str, bets: list[list[int]], seed_numbers: list[int] | None = None) -> None:
    print("\n" + "=" * 56)
    if seed_numbers is not None:
        print(f"上期種子球號 ： {format_seed_numbers(seed_numbers)}")
    print(f"{title}: {bet_date}")
    for i, bet in enumerate(bets, 1):
        print(f"   {i}. {bet}")
    print("=" * 56)


def run_backtest_init(df_all: pd.DataFrame, next_info: NextDrawInfo) -> None:
    """沒有 bet_data 結果時，用最近 N 期重新初始化回測。"""

    print(f"【初始化回測】使用最近 {BACKTEST_LAST_DRAW} 期建立新 bet_data")
    clear_result_csvs()

    recent = df_all.tail(BACKTEST_LAST_DRAW).reset_index(drop=True)
    if recent.empty:
        raise ValueError("沒有可回測的開獎資料")

    first_date = str(recent.iloc[0]["ndate"])
    save_bet_record(first_date, [random_base_draw(seed_val=len(df_all) - len(recent))])

    total_bets = 0
    total_prize = 0
    hit_counter = {score: 0 for score in PRIZE_TABLE}

    start_seed = len(df_all) - len(recent)
    for pos, (_, draw_row) in enumerate(recent.iterrows()):
        draw_date = str(draw_row["ndate"])
        draw_balls, special = row_balls(draw_row)
        print(f"\n/> {draw_date} 真實開獎: {draw_balls} + 特[{special}]")

        bets = read_bets_for_date(draw_date)
        if bets.empty:
            save_bet_record(draw_date, [random_base_draw(seed_val=start_seed + pos)])
            bets = read_bets_for_date(draw_date)

        result = settle_draw(draw_date, bets, draw_balls, special)
        total_bets += result.total_bets
        total_prize += result.total_prize
        for score, count in result.hit_counter.items():
            hit_counter[score] += count

        next_bet_date = next_info.date if pos == len(recent) - 1 else str(recent.iloc[pos + 1]["ndate"])
        next_bets = build_next_bets(
            matched_numbers=result.matched_numbers,
            last_bet=result.last_bet,
            seed_base=start_seed + pos + 1000,
            anchor_date=draw_date,
            df_all=df_all,
        )
        save_bet_record(next_bet_date, next_bets)

        if pos == len(recent) - 1:
            save_next_prediction(next_info.date, next_bets)
            save_next_prediction_summary(next_info, result.matched_numbers)
            print_next_bets("已寫入下期投注", next_info.date, next_bets, result.matched_numbers)

    print_backtest_summary(total_bets, total_prize, hit_counter)


def print_backtest_summary(total_bets: int, total_prize: int, hit_counter: dict[float, int]) -> None:
    total_amount = total_bets * BET_UNIT
    print("\n" + "=" * 56)
    print("【回測統計】")
    print(f"總投注: {total_bets} 注 / 總金額: ${total_amount:,}")
    for score, label in PRIZE_LABELS.items():
        count = hit_counter.get(score, 0)
        prize = PRIZE_TABLE[score] * count
        extra = f" / 獎金 ${prize:,}" if count else ""
        print(f"  {label} 命中={score}: {count} 次{extra}")
    print(f"回測中獎總額: ${total_prize:,}")
    print(f"損益: ${total_prize - total_amount:,}")
    print("=" * 56)


def rebuild_next_prediction(df_all: pd.DataFrame, next_info: NextDrawInfo) -> bool:
    """nextBetDraw_record.csv 缺失時，從最近已核對結果重建下期投注。"""

    if not WIN_RECORD_CSV.exists() or WIN_RECORD_CSV.stat().st_size == 0:
        print("缺少中獎紀錄，無法重建下期投注。")
        return False

    win_df = pd.read_csv(WIN_RECORD_CSV)
    if win_df.empty or "bet_date" not in win_df.columns:
        print("中獎紀錄格式不完整，無法重建下期投注。")
        return False

    last_settled_date = str(win_df["bet_date"].astype(str).max())
    win_rows = win_df[win_df["bet_date"].astype(str) == last_settled_date]
    matched = sorted({int(v) for _, row in win_rows.iterrows() for v in row.iloc[1:7] if int(v) > 0})

    bet_rows = read_bets_for_date(last_settled_date)
    last_bet = bet_values(bet_rows.iloc[-1]) if not bet_rows.empty else random_base_draw()
    next_bets = build_next_bets(
        matched_numbers=matched,
        last_bet=last_bet,
        seed_base=int(dt.datetime.now().timestamp()) % 100000,
        anchor_date=last_settled_date,
        df_all=df_all,
    )
    save_bet_record(next_info.date, next_bets)
    save_next_prediction(next_info.date, next_bets)
    save_next_prediction_summary(next_info, matched)
    print_next_bets("已重建下期投注", next_info.date, next_bets, matched)
    return True


def run_live_check(df_all: pd.DataFrame, next_info: NextDrawInfo) -> None:
    """核對目前 nextBetDraw_record.csv，若已開獎則生成下一期投注。"""

    next_df = read_next_prediction()
    if next_df.empty:
        rebuild_next_prediction(df_all, next_info)
        return

    pending_date = str(next_df["bet_date"].iloc[0])
    print(f"待核對期數: {pending_date}")

    draw_rows = df_all[df_all["ndate"].astype(str) == pending_date]
    if draw_rows.empty:
        print(f"開獎資料尚未包含 {pending_date}，等待 Z3 更新後再核對。")
        return

    draw_balls, special = row_balls(draw_rows.iloc[0])
    print(f"開獎號碼: {draw_balls} + 特[{special}]")

    bets = read_bets_for_date(pending_date)
    if bets.empty:
        bets = next_df
        save_bet_record(pending_date, [bet_values(row) for _, row in bets.iterrows()])

    result = settle_draw(pending_date, bets, draw_balls, special)
    if result.total_prize > 0:
        print(f"本期派彩: ${result.total_prize:,}")

    seed_base = int(dt.datetime.now().timestamp()) % 100000
    next_bets = build_next_bets(
        matched_numbers=result.matched_numbers,
        last_bet=result.last_bet,
        seed_base=seed_base,
        anchor_date=pending_date,
        df_all=df_all,
    )
    save_bet_record(next_info.date, next_bets)
    save_next_prediction(next_info.date, next_bets)
    save_next_prediction_summary(next_info, result.matched_numbers)
    print_next_bets("下期投注", next_info.date, next_bets, result.matched_numbers)


def main() -> None:
    
    ensure_bet_data_dir()
    df_all = load_draw_history()
    next_info = load_next_draw_info(df_all)

    print_next_header(next_info)
    save_next_prediction_summary(next_info, latest_seed_numbers_from_win_record())
    if not is_initialized():
        run_backtest_init(df_all, next_info)
        return

    run_live_check(df_all, next_info)


if __name__ == "__main__":
    main()
