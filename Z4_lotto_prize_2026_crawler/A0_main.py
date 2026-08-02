#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""

# 馬會六合彩開獎紀錄網站英文
# https://bet.hkjc.com/ch/marksix/home
# https://bet.hkjc.com/ch/marksix/results
Z4 六合彩開獎紀錄下載程式。

用途：
1. 取代舊版依賴第三方網站的開獎紀錄下載。
2. 從香港賽馬會官方 GraphQL 下載最新開獎紀錄及派彩注數。
3. 產生 M1 / M2 / M3 / M4 / M6 / M7，並同步到 A_msk_lottery_data_folder。

資料來源：
    https://info.cld.hkjc.com/graphql/base/
"""

from __future__ import annotations

import csv
import shutil
import time
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


PROJECT_DIR = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_DIR.parent
DATA_DIR = PROJECT_DIR / "Lotto_Data_Folder"
LOG_PATH = PROJECT_DIR / "log" / "lotto_download_log.txt"
WEBAPP_DATA_DIR = REPO_ROOT / "A_msk_lottery_data_folder"

M1_CSV = DATA_DIR / "M1_Z4_lotto_data.csv"
M2_CSV = DATA_DIR / "M2_last_upgrade_lotto_data.csv"
M3_CSV = DATA_DIR / "M3_lotto_prize_results.csv"
M4_CSV = DATA_DIR / "M4_lotto_prize_summary.csv"
M6_CSV = DATA_DIR / "M6_lotto_history_prize.csv"
M7_CSV = DATA_DIR / "M7_lotto_open_days.csv"

WEBAPP_M2_CSV = WEBAPP_DATA_DIR / "M2_last_upgrade_lotto_data.csv"
WEBAPP_M4_CSV = WEBAPP_DATA_DIR / "M4_lotto_prize_summary.csv"
WEBAPP_M7_CSV = WEBAPP_DATA_DIR / "M7_lotto_open_days.csv"
WEBAPP_M6_CSV = WEBAPP_DATA_DIR / "M6_lotto_history_prize.csv"

LOCAL_HISTORY_CSV = DATA_DIR / "M0_MSK_2002_2024.csv"

HKJC_GRAPHQL_URL = "https://info.cld.hkjc.com/graphql/base/"
DOWNLOAD_LIMIT = 100
REQUEST_TIMEOUT = (8, 15)
DRAW_WEEKDAYS = {2, 4, 6}  # Tuesday, Thursday, Saturday
M7_FIELD = "開獎日期 (Date)"
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
    "Origin": "https://bet.hkjc.com",
    "Referer": "https://bet.hkjc.com/ch/marksix/results",
}

M2_COLUMNS = ["ndate", "N1", "N2", "N3", "N4", "N5", "N6", "N7"]
M4_COLUMNS = [
    "last_draw_date",
    "N1",
    "N2",
    "N3",
    "N4",
    "N5",
    "N6",
    "N7",
    "next_draw_date",
    "week",
    "next_draw_prize_fund",
]
M6_COLUMNS = [
    "nDdate",
    "N1",
    "N2",
    "N3",
    "N4",
    "N5",
    "N6",
    "N7",
    "prize1",
    "prize2",
    "prize3",
    "prize1_unit",
    "prize2_unit",
    "prize3_unit",
]

MARKSIX_RESULT_QUERY = """
fragment lotteryDrawsFragment on LotteryDraw {
  id
  year
  no
  openDate
  closeDate
  drawDate
  status
  snowballCode
  snowballName_en
  snowballName_ch
  lotteryPool {
    sell
    status
    totalInvestment
    jackpot
    unitBet
    estimatedPrize
    derivedFirstPrizeDiv
    lotteryPrizes {
      type
      winningUnit
      dividend
    }
  }
  drawResult {
    drawnNo
    xDrawnNo
  }
}
query marksixResult($lastNDraw: Int, $startDate: String, $endDate: String, $drawType: LotteryDrawType) {
  lotteryDraws(lastNDraw: $lastNDraw, startDate: $startDate, endDate: $endDate, drawType: $drawType) {
    ...lotteryDrawsFragment
  }
}
"""

MARKSIX_HOME_QUERY = """
fragment lotteryDrawsFragment on LotteryDraw {
  id
  year
  no
  openDate
  closeDate
  drawDate
  status
  lotteryPool {
    sell
    status
    totalInvestment
    jackpot
    unitBet
    estimatedPrize
    derivedFirstPrizeDiv
    lotteryPrizes {
      type
      winningUnit
      dividend
    }
  }
  drawResult {
    drawnNo
    xDrawnNo
  }
}
query marksix {
  lotteryDraws {
    ...lotteryDrawsFragment
  }
}
"""

MARKSIX_FIXTURES_QUERY = """
fragment lotteryDrawsFragment on LotteryDraw {
  id
  year
  no
  drawDate
  status
  lotteryPool {
    sell
    estimatedPrize
    totalInvestment
  }
  drawResult {
    drawnNo
    xDrawnNo
  }
}
query marksixResult($startDate: String, $endDate: String, $drawType: LotteryDrawType) {
  lotteryDraws(startDate: $startDate, endDate: $endDate, drawType: $drawType) {
    ...lotteryDrawsFragment
  }
}
"""


@dataclass(frozen=True)
class DrawRecord:
    draw_id: str
    draw_date: str
    numbers: list[int]
    extra_number: int
    prizes: dict[str, int]
    winning_units: dict[str, float]
    unit_bet: int
    derived_first_prize_div: int
    estimated_prize: int
    turnover: int


@dataclass(frozen=True)
class NextDrawInfo:
    draw_id: str
    draw_date: str
    week: int
    estimated_prize: int
    turnover: int
    close_time: str


def ensure_folders() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    WEBAPP_DATA_DIR.mkdir(parents=True, exist_ok=True)


def now_string() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def write_log(message: str) -> None:
    LOG_PATH.write_text(message + "\n", encoding="utf-8")


def run_timed_step(label: str, func, timings: list[tuple[str, float]], *args, **kwargs):
    print(f"⏳ {label} 開始，下載網頁或產生檔案可能需要一些時間...")
    start_time = time.perf_counter()
    result = func(*args, **kwargs)
    elapsed = time.perf_counter() - start_time
    timings.append((label, elapsed))
    print(f"✅ {label} 完成，耗時 {elapsed:.2f} 秒")
    return result


def format_timing_report(timings: list[tuple[str, float]]) -> str:
    if not timings:
        return ""
    rows = ["下載/產生耗時："]
    rows.extend(f"- {label}: {elapsed:.2f} 秒" for label, elapsed in timings)
    return "\n".join(rows)


def make_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=0.8,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(REQUEST_HEADERS)
    return session


def next_month(year: int, month: int) -> tuple[int, int]:
    if month == 12:
        return year + 1, 1
    return year, month + 1


def target_months(today: date | None = None) -> list[tuple[int, int]]:
    today = today or date.today()
    months = [(today.year, today.month)]
    if today.day > 15:
        months.append(next_month(today.year, today.month))
    return months


def read_existing_m7_dates() -> set[str]:
    path = M7_CSV if M7_CSV.exists() else WEBAPP_M7_CSV
    if not path.exists():
        return set()

    existing_dates = set()
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            value = (row.get(M7_FIELD) or "").strip()
            if value:
                existing_dates.add(value)
    return existing_dates


def month_dates(year: int, month: int) -> list[str]:
    last_day = monthrange(year, month)[1]
    dates = []
    for day in range(1, last_day + 1):
        current = date(year, month, day)
        if current.isoweekday() in DRAW_WEEKDAYS:
            dates.append(current.strftime("%Y-%m-%d"))
    return dates


def fixed_dates_for_months(months: list[tuple[int, int]]) -> list[str]:
    dates = []
    for year, month in months:
        dates.extend(month_dates(year, month))
    return dates


def has_month(existing_dates: set[str], year: int, month: int) -> bool:
    expected = set(month_dates(year, month))
    return bool(expected) and expected.issubset(existing_dates)


def has_current_and_next_month(existing_dates: set[str], today: date | None = None) -> bool:
    today = today or date.today()
    next_year, next_month_value = next_month(today.year, today.month)
    return has_month(existing_dates, today.year, today.month) and has_month(existing_dates, next_year, next_month_value)


def has_non_fixed_draw_dates(existing_dates: set[str], months: list[tuple[int, int]]) -> bool:
    month_set = set(months)
    for value in existing_dates:
        try:
            current = datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            continue
        if (current.year, current.month) in month_set and current.isoweekday() not in DRAW_WEEKDAYS:
            return True
    return False


def should_download_m7(existing_dates: set[str], today: date | None = None) -> bool:
    today = today or date.today()
    current_and_next = [(today.year, today.month), next_month(today.year, today.month)]
    if has_non_fixed_draw_dates(existing_dates, current_and_next):
        return True
    if has_current_and_next_month(existing_dates, today):
        return False
    for year, month in target_months(today):
        if not has_month(existing_dates, year, month):
            return True
    return False


def fetch_hkjc_fixture_dates(months: list[tuple[int, int]]) -> list[str] | None:
    start_time = time.perf_counter()
    start_year, start_month = months[0]
    end_year, end_month = months[-1]
    start_date = f"{start_year}{start_month:02d}01"
    end_date = f"{end_year}{end_month:02d}{monthrange(end_year, end_month)[1]:02d}"

    print("🌐 正在嘗試下載馬會開獎日網頁資料，可能需要一些時間...")
    try:
        response = make_session().post(
            HKJC_GRAPHQL_URL,
            json={
                "query": MARKSIX_FIXTURES_QUERY,
                "variables": {
                    "startDate": start_date,
                    "endDate": end_date,
                    "drawType": "All",
                },
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data: dict[str, Any] = response.json()
    except (requests.RequestException, ValueError) as exc:
        print(f"⚠️ 馬會開獎日下載失敗：{exc}")
        return None
    finally:
        print(f"⏱️ 開獎日下載耗時：{time.perf_counter() - start_time:.2f} 秒")

    if data.get("errors"):
        print(f"⚠️ 馬會開獎日 GraphQL 回傳錯誤：{data['errors']}")
        return None

    dates = []
    for draw in data.get("data", {}).get("lotteryDraws") or []:
        draw_date = str(draw.get("drawDate", "")).strip()[:10]
        if not draw_date:
            continue
        try:
            dt = datetime.strptime(draw_date, "%Y-%m-%d").date()
        except ValueError:
            continue
        if dt.isoweekday() in DRAW_WEEKDAYS:
            dates.append(draw_date)

    return sorted(set(dates)) or None


def write_m7(dates: list[str]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    WEBAPP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    rows = [{M7_FIELD: draw_date} for draw_date in sorted(set(dates))]
    for path in [M7_CSV, WEBAPP_M7_CSV]:
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[M7_FIELD])
            writer.writeheader()
            writer.writerows(rows)


def download_fixtures_to_csv(today: date | None = None) -> bool:
    today = today or date.today()
    existing_dates = read_existing_m7_dates()
    if not should_download_m7(existing_dates, today):
        print("ℹ️ M7 已有需要月份的固定開獎日，跳過下載。")
        if existing_dates and not M7_CSV.exists():
            write_m7(sorted(existing_dates))
        return False

    months = target_months(today)
    dates = fetch_hkjc_fixture_dates(months)
    if dates is None:
        dates = fixed_dates_for_months(months)
        print("🧱 已使用固定 Tue/Thu/Sat 開獎日產生 M7。")

    write_m7(dates)
    print(f"✅ 已更新 M7_lotto_open_days.csv，共 {len(dates)} 個開獎日。")
    return True


def clean_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value).replace(",", "").replace("$", "").strip()))
    except (TypeError, ValueError):
        return default


def validate_draw(draw: dict[str, Any]) -> DrawRecord:
    draw_date = str(draw.get("drawDate") or draw.get("draw_date", "")).strip()[:10]
    datetime.strptime(draw_date, "%Y-%m-%d")

    draw_result = draw.get("drawResult") or {}
    numbers = [int(num) for num in (draw_result.get("drawnNo") or draw.get("numbers", []))]
    if len(numbers) != 6 or not all(1 <= num <= 49 for num in numbers):
        raise ValueError(f"開獎正號格式錯誤：{draw}")

    extra_number = int(draw_result.get("xDrawnNo") or draw.get("extra_number", 0))
    if not 1 <= extra_number <= 49:
        raise ValueError(f"特號格式錯誤：{draw}")

    lottery_pool = draw.get("lotteryPool") or {}
    unit_bet = clean_int(lottery_pool.get("unitBet", 10), default=10) or 10
    prizes = {}
    winning_units = {}
    for prize_row in lottery_pool.get("lotteryPrizes") or []:
        prize_type = str(prize_row.get("type", "")).strip()
        if not prize_type:
            continue
        prizes[prize_type] = clean_int(prize_row.get("dividend", 0))
        winning_units[prize_type] = clean_int(prize_row.get("winningUnit", 0)) / unit_bet

    return DrawRecord(
        draw_id=f"{str(draw.get('year', ''))[2:]}/{int(draw.get('no', 0)):03d}" if draw.get("year") and draw.get("no") else str(draw.get("draw_id", "")).strip(),
        draw_date=draw_date,
        numbers=numbers,
        extra_number=extra_number,
        prizes=prizes,
        winning_units=winning_units,
        unit_bet=unit_bet,
        derived_first_prize_div=clean_int(lottery_pool.get("derivedFirstPrizeDiv", 0)),
        estimated_prize=clean_int(lottery_pool.get("estimatedPrize", 0)),
        turnover=clean_int(lottery_pool.get("totalInvestment", draw.get("total_turnover", 0))),
    )


def parse_next_draw(draw: dict[str, Any]) -> NextDrawInfo | None:
    draw_date = str(draw.get("drawDate", "")).strip()[:10]
    if not draw_date:
        return None
    try:
        dt = datetime.strptime(draw_date, "%Y-%m-%d")
    except ValueError:
        return None

    lottery_pool = draw.get("lotteryPool") or {}
    draw_id = f"{str(draw.get('year', ''))[2:]}/{int(draw.get('no', 0)):03d}" if draw.get("year") and draw.get("no") else str(draw.get("id", "")).strip()
    close_time = str(draw.get("closeDate", "")).strip()
    return NextDrawInfo(
        draw_id=draw_id,
        draw_date=draw_date,
        week=dt.isoweekday(),
        estimated_prize=clean_int(lottery_pool.get("estimatedPrize", 0))
        or clean_int(lottery_pool.get("derivedFirstPrizeDiv", 0))
        or 8_000_000,
        turnover=clean_int(lottery_pool.get("totalInvestment", 0)),
        close_time=close_time,
    )


def download_draws(limit: int = DOWNLOAD_LIMIT) -> tuple[list[DrawRecord], NextDrawInfo | None]:
    session = make_session()
    response = session.post(
        HKJC_GRAPHQL_URL,
        json={
            "query": MARKSIX_RESULT_QUERY,
            "variables": {"lastNDraw": limit, "drawType": "All"},
        },
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    if data.get("errors"):
        raise ValueError(f"馬會 GraphQL 回傳錯誤：{data['errors']}")

    records = []
    next_draw = None
    for draw in data.get("data", {}).get("lotteryDraws", []):
        status = str(draw.get("status", "")).lower()
        draw_result = draw.get("drawResult") or {}
        has_result = bool(draw_result.get("drawnNo")) and bool(draw_result.get("xDrawnNo"))
        if status != "result" or not has_result:
            candidate = parse_next_draw(draw)
            if candidate and (next_draw is None or candidate.draw_date < next_draw.draw_date):
                next_draw = candidate
            continue
        records.append(validate_draw(draw))
    if not records:
        raise ValueError("API 沒有回傳任何開獎紀錄")
    records = sorted(records, key=lambda item: item.draw_date)
    if next_draw is None:
        next_draw = download_next_draw_from_home(session, records[-1].draw_date)
    return records, next_draw


def download_next_draw_from_home(session: requests.Session, latest_draw_date: str) -> NextDrawInfo | None:
    """馬會首頁 query 通常同時回傳最新一期及下一期。失敗時回傳 None。"""
    try:
        response = session.post(
            HKJC_GRAPHQL_URL,
            json={"query": MARKSIX_HOME_QUERY, "variables": {}},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError):
        return None

    if data.get("errors"):
        return None

    candidates = []
    for draw in data.get("data", {}).get("lotteryDraws") or []:
        candidate = parse_next_draw(draw)
        if candidate and candidate.draw_date > latest_draw_date:
            candidates.append(candidate)
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: item.draw_date)[0]


def draw_to_m2_row(record: DrawRecord) -> dict[str, Any]:
    return {
        "ndate": record.draw_date,
        "N1": record.numbers[0],
        "N2": record.numbers[1],
        "N3": record.numbers[2],
        "N4": record.numbers[3],
        "N5": record.numbers[4],
        "N6": record.numbers[5],
        "N7": record.extra_number,
    }


def create_m1_latest_history(records: list[DrawRecord]) -> None:
    rows = [draw_to_m2_row(record) for record in records]
    pd.DataFrame(rows, columns=M2_COLUMNS).to_csv(M1_CSV, index=False, encoding="utf-8-sig")


def ensure_local_history_csv() -> None:
    if LOCAL_HISTORY_CSV.exists():
        return
    if WEBAPP_M2_CSV.exists():
        shutil.copy2(WEBAPP_M2_CSV, LOCAL_HISTORY_CSV)
        return
    raise FileNotFoundError("找不到 M0/M2 歷史底表，無法合併 M2")


def create_m2_merged_history() -> None:
    ensure_local_history_csv()
    base_df = pd.read_csv(LOCAL_HISTORY_CSV, encoding="utf-8-sig")
    m1_df = pd.read_csv(M1_CSV, encoding="utf-8-sig")
    for df in [base_df, m1_df]:
        df.columns = [str(col).strip().lstrip("\ufeff") for col in df.columns]
    base_df = base_df[M2_COLUMNS].copy()
    m1_df = m1_df[M2_COLUMNS].copy()

    merged_df = pd.concat([base_df, m1_df], ignore_index=True)
    merged_df["ndate"] = merged_df["ndate"].astype(str).str.strip()
    for col in M2_COLUMNS[1:]:
        merged_df[col] = pd.to_numeric(merged_df[col], errors="coerce").fillna(0).astype(int)
    merged_df = merged_df.drop_duplicates(subset=["ndate"], keep="last")
    merged_df = merged_df.sort_values("ndate").reset_index(drop=True)
    merged_df.to_csv(M2_CSV, index=False, encoding="utf-8-sig")


def get_next_draw_date(last_draw_date: str, next_draw: NextDrawInfo | None = None) -> tuple[str, int]:
    if next_draw:
        return next_draw.draw_date, next_draw.week

    # Fallback：六合彩常見 Tue/Thu/Sat。不要用舊 M7，因為 M7 可能包含非六合彩日期。
    dt = datetime.strptime(last_draw_date, "%Y-%m-%d") + timedelta(days=1)
    while dt.isoweekday() not in {2, 4, 6}:
        dt += timedelta(days=1)
    return dt.strftime("%Y-%m-%d"), dt.isoweekday()


def estimate_next_prize_fund(latest: DrawRecord, next_draw: NextDrawInfo | None = None) -> int:
    if next_draw and next_draw.estimated_prize > 0:
        return next_draw.estimated_prize
    if latest.estimated_prize > 0:
        return latest.estimated_prize
    if latest.derived_first_prize_div > 0:
        return latest.derived_first_prize_div
    first_prize = latest.prizes.get("1", 0)
    return max(8_000_000, first_prize)


def record_to_m6_row(record: DrawRecord) -> dict[str, Any]:
    return {
        "nDdate": record.draw_date,
        "N1": record.numbers[0],
        "N2": record.numbers[1],
        "N3": record.numbers[2],
        "N4": record.numbers[3],
        "N5": record.numbers[4],
        "N6": record.numbers[5],
        "N7": record.extra_number,
        "prize1": record.winning_units.get("1", 0),
        "prize2": record.winning_units.get("2", 0),
        "prize3": record.winning_units.get("3", 0),
        "prize1_unit": record.prizes.get("1", 0),
        "prize2_unit": record.prizes.get("2", 0),
        "prize3_unit": record.prizes.get("3", 0),
    }


def create_m6_lotto_history_prize(records: list[DrawRecord]) -> None:
    new_df = pd.DataFrame([record_to_m6_row(record) for record in records], columns=M6_COLUMNS)

    old_m6_path = M6_CSV if M6_CSV.exists() else WEBAPP_M6_CSV
    if old_m6_path.exists():
        old_df = pd.read_csv(old_m6_path, encoding="utf-8-sig")
        old_df.columns = [str(col).strip().lstrip("\ufeff") for col in old_df.columns]
        for col in M6_COLUMNS:
            if col not in old_df.columns:
                old_df[col] = 0
        m6_df = pd.concat([old_df[M6_COLUMNS], new_df], ignore_index=True)
        m6_df["nDdate"] = m6_df["nDdate"].astype(str).str.strip()
        m6_df = m6_df.drop_duplicates(subset=["nDdate"], keep="last")
        m6_df = m6_df.sort_values("nDdate").reset_index(drop=True)
    else:
        m6_df = new_df

    m6_df.to_csv(M6_CSV, index=False, encoding="utf-8-sig")


def create_m4_prize_summary(records: list[DrawRecord], next_draw: NextDrawInfo | None = None) -> None:
    latest = records[-1]
    next_draw_date, week = get_next_draw_date(latest.draw_date, next_draw=next_draw)
    row = {
        "last_draw_date": latest.draw_date,
        "N1": latest.numbers[0],
        "N2": latest.numbers[1],
        "N3": latest.numbers[2],
        "N4": latest.numbers[3],
        "N5": latest.numbers[4],
        "N6": latest.numbers[5],
        "N7": latest.extra_number,
        "next_draw_date": next_draw_date,
        "week": week,
        "next_draw_prize_fund": estimate_next_prize_fund(latest, next_draw=next_draw),
    }

    old_m4_path = M4_CSV if M4_CSV.exists() else WEBAPP_M4_CSV
    if old_m4_path.exists():
        old_df = pd.read_csv(old_m4_path, encoding="utf-8-sig")
        old_df.columns = [str(col).strip().lstrip("\ufeff") for col in old_df.columns]
        for col in M4_COLUMNS:
            if col not in old_df.columns:
                old_df[col] = ""
        m4_df = pd.concat([old_df[M4_COLUMNS], pd.DataFrame([row], columns=M4_COLUMNS)], ignore_index=True)
        m4_df["last_draw_date"] = m4_df["last_draw_date"].astype(str).str.strip()
        m4_df = m4_df.drop_duplicates(subset=["last_draw_date"], keep="last")
        m4_df = m4_df.sort_values("last_draw_date").reset_index(drop=True)
    else:
        m4_df = pd.DataFrame([row], columns=M4_COLUMNS)

    m4_df.to_csv(M4_CSV, index=False, encoding="utf-8-sig")


def format_zh_date(date_text: str) -> str:
    dt = datetime.strptime(date_text, "%Y-%m-%d")
    return f"{dt.year}年{dt.month:02d}月{dt.day:02d}日"


def format_zh_date_with_week(date_text: str) -> str:
    dt = datetime.strptime(date_text, "%Y-%m-%d")
    week_text = "一二三四五六日"[dt.isoweekday() - 1]
    return f"{format_zh_date(date_text)} ({week_text})"


def create_m3_prize_results(records: list[DrawRecord], next_draw: NextDrawInfo | None = None) -> None:
    latest = records[-1]
    next_draw_date, _ = get_next_draw_date(latest.draw_date, next_draw=next_draw)
    numbers_text = ", ".join(str(num) for num in [*latest.numbers, latest.extra_number])
    rows = [
        ["🔴 最新一期"],
        ["期數", f"第{latest.draw_id}期" if latest.draw_id else ""],
        ["日期", format_zh_date(latest.draw_date)],
        ["號碼", numbers_text],
        ["獎項", "獎金", "中獎注數"],
    ]
    prize_names = [
        ("頭獎", "1st"),
        ("二獎", "2nd"),
        ("三獎", "3rd"),
        ("四獎", "4th"),
        ("五獎", "5th"),
        ("六獎", "6th"),
        ("七獎", "7th"),
    ]
    for prize_name, prize_key in prize_names:
        prize_type = prize_key.replace("st", "").replace("nd", "").replace("rd", "").replace("th", "")
        rows.append([
            prize_name,
            str(latest.prizes.get(prize_type, 0)),
            str(latest.winning_units.get(prize_type, 0)),
        ])
    rows.extend([
        ["🟢 下一期"],
        ["開獎日期", format_zh_date_with_week(next_draw_date)],
        ["下期頭獎基金", str(estimate_next_prize_fund(latest, next_draw=next_draw))],
    ])
    with M3_CSV.open("w", newline="", encoding="utf-8-sig") as f:
        csv.writer(f).writerows(rows)


def copy_to_webapp() -> None:
    for path in [M1_CSV, M2_CSV, M3_CSV, M4_CSV, M6_CSV, M7_CSV]:
        if not path.exists():
            raise FileNotFoundError(f"找不到要複製的檔案：{path}")
        target_name = "M1_ZH_lotto_data.csv" if path == M1_CSV else path.name
        shutil.copy2(path, WEBAPP_DATA_DIR / target_name)


def validate_outputs() -> tuple[str, str]:
    m2_df = pd.read_csv(M2_CSV, encoding="utf-8-sig")
    m4_df = pd.read_csv(M4_CSV, encoding="utf-8-sig")
    m6_df = pd.read_csv(M6_CSV, encoding="utf-8-sig")
    latest_date = str(m2_df["ndate"].max())
    next_date = str(m4_df.iloc[-1]["next_draw_date"])
    latest_m6_date = str(m6_df["nDdate"].max())
    if not latest_date or not next_date:
        raise ValueError("輸出檔缺少最新/下期日期")
    if latest_m6_date != latest_date:
        raise ValueError(f"M6 最新日期 {latest_m6_date} 與 M2 最新日期 {latest_date} 不一致")
    return latest_date, next_date


def run() -> bool:
    ensure_folders()
    timings: list[tuple[str, float]] = []
    try:
        run_timed_step("M7 開獎日期檔", download_fixtures_to_csv, timings)
        records, next_draw = run_timed_step("馬會官方開獎資料下載", download_draws, timings)
        run_timed_step("M1 最新紀錄", create_m1_latest_history, timings, records)
        run_timed_step("M2 合併紀錄", create_m2_merged_history, timings)
        run_timed_step("M3 最新及下期資料", create_m3_prize_results, timings, records, next_draw=next_draw)
        run_timed_step("M4 摘要資料", create_m4_prize_summary, timings, records, next_draw=next_draw)
        run_timed_step("M6 派彩紀錄", create_m6_lotto_history_prize, timings, records)
        run_timed_step("同步到 WebApp", copy_to_webapp, timings)
        latest_date, next_date = run_timed_step("輸出核對", validate_outputs, timings)
    except Exception as exc:
        timing_report = format_timing_report(timings)
        message = f"{now_string()} Z4 執行失敗：{exc}"
        if timing_report:
            message = f"{message}\n{timing_report}"
        write_log(message)
        print(f"❌ {message}")
        return False

    timing_report = format_timing_report(timings)
    message = (
        f"{now_string()} Z4 下載完成。\n"
        f"/> 最新一期：{latest_date}\n"
        f"/> 下期開獎日期：{next_date}\n"
        f"/> 下期期號：{next_draw.draw_id if next_draw else '-'}\n"
        f"/> 已同步 M1/M2/M3/M4/M6/M7 到 A_msk_lottery_data_folder。"
    )
    if timing_report:
        message = f"{message}\n{timing_report}"
    write_log(message)
    print(f"✅ {message}")
    return True


if __name__ == "__main__":
    run()
