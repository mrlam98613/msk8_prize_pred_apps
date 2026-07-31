#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Z3 新版六合彩爬蟲主程式。

功能：
1. 建立 Lotto_Data_Folder，並複製歷史底表 M0_MSK_2002_2024.csv
2. 從 lottolyzer 下載最新六合彩歷史資料，儲存為 Lotto_Data_Folder/M1_ZH_lotto_data.csv
3. 合併 M0 舊歷史資料與 M1 新下載資料，儲存為 Lotto_Data_Folder/M2_last_upgrade_lotto_data.csv
4. 下載最新一期獎金及下一期資料，儲存為 Lotto_Data_Folder/M3_lotto_prize_results.csv
5. 從 M3 摘要出下一期資訊，儲存為 Lotto_Data_Folder/M4_lotto_prize_summary.csv
6. 下載最近 N 期獎項注數明細，儲存 M6 原始紀錄
7. 複製 CSV 到專案根目錄的 A_msk_lottery_data_folder/
"""

from __future__ import annotations

import csv
import re
import shutil
import time
from pathlib import Path
from typing import TypedDict, cast

import pandas as pd
import requests
from bs4 import BeautifulSoup
from bs4.element import Tag
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import A2_lotto_history_prize
import A4_mark_six_open_days

# === 路徑設定 ===
PROJECT_DIR = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_DIR.parent

# 新版資料一律存放在自己的資料夾下。
DATA_DIR = PROJECT_DIR / "Lotto_Data_Folder"
LOG_PATH = PROJECT_DIR / "log" / "lotto_download_log.txt"

# M1-M4 最後會複製到這個資料夾，供 Streamlit / Web App 使用。
WEBAPP_DATA_DIR = REPO_ROOT / "A_msk_lottery_data_folder"

# 合併 M2 時需要歷史底表；第一次執行會先從舊專案複製一份到新版資料夾。
LOCAL_HISTORY_CSV = DATA_DIR / "M0_MSK_2002_2024.csv"
OLD_HISTORY_CSV = (
    REPO_ROOT
    / "Z1_lotto_2026_download_project"
    / "Lotto_Data_Folder"
    / "M0_MSK_2002_2024.csv"
)

M1_CSV = DATA_DIR / "M1_ZH_lotto_data.csv"
M2_CSV = DATA_DIR / "M2_last_upgrade_lotto_data.csv"
M3_CSV = DATA_DIR / "M3_lotto_prize_results.csv"
M4_CSV = DATA_DIR / "M4_lotto_prize_summary.csv"
M6_CSV = DATA_DIR / "M6_lotto_history_prize.csv"
M7_CSV = DATA_DIR / "M7_lotto_open_days.csv"

REQUIRED_M2_COLUMNS = ["ndate", "N1", "N2", "N3", "N4", "N5", "N6", "N7"]
REQUIRED_M4_COLUMNS = [
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
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

LOTTO_HISTORY_URL = (
    "https://zh.lottolyzer.com/history/hong-kong/mark-six/page/"
    "{page}/per-page/50/summary-view"
)
LOTTO_HOME_URL = "https://zh.lottolyzer.com/home/hong-kong/mark-six"


# ====================== 載入六合彩開獎紀錄
# connect timeout, read timeout；避免網站回應太慢時長時間卡住。
REQUEST_TIMEOUT = (8, 12)
DOWNLOAD_PAGES = range(1, 3) # 載入歷史資料 1- 3 頁，每頁有50期開獎紀錄。
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0 Safari/537.36"
    )
}
# =====================================

class LatestDrawInfo(TypedDict):
    """首頁最新一期開獎資料。"""

    draw_number: str
    draw_date: str
    numbers: list[str]
    prizes: list[tuple[str, str, str]]


class NextDrawInfo(TypedDict):
    """首頁下一期開獎資料。"""

    draw_name: str
    draw_date: str
    prize_fund: str


def ensure_folders() -> None:
    """建立本程式需要的資料夾。"""

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    WEBAPP_DATA_DIR.mkdir(parents=True, exist_ok=True)


def ensure_local_history_csv() -> None:
    """確保新版資料夾內有 M0 歷史底表，M2 合併才有完整資料來源。"""

    if LOCAL_HISTORY_CSV.exists():
        return

    if not OLD_HISTORY_CSV.exists():
        raise FileNotFoundError(f"找不到可複製的 M0 歷史底表：{OLD_HISTORY_CSV}")

    shutil.copy2(OLD_HISTORY_CSV, LOCAL_HISTORY_CSV)


def now_string() -> str:
    """回傳統一格式的目前時間字串。"""

    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def write_log(message: str) -> None:
    """寫入執行結果；每次執行覆蓋舊 log。"""

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text(message + "\n", encoding="utf-8")


def format_timing_report(timings: list[tuple[str, float]]) -> str:
    """格式化每個步驟耗時。"""

    total_seconds = sum(seconds for _, seconds in timings)
    lines = ["/> 耗時明細："]
    for label, seconds in timings:
        lines.append(f"   - {label}: {seconds:.2f} 秒")
    lines.append(f"   - 總耗時: {total_seconds:.2f} 秒")
    return "\n".join(lines)


def run_timed_step(label: str, func, timings: list[tuple[str, float]]) -> None:
    """執行單一步驟並記錄耗時。"""

    print(f"▶️ {label} ...")
    start_time = time.perf_counter()
    func()
    elapsed = time.perf_counter() - start_time
    timings.append((label, elapsed))
    print(f"   ✅ {label} 完成，用時 {elapsed:.2f} 秒")


def require_tag(parent: BeautifulSoup | Tag, selector: str, label: str) -> Tag:
    """用 CSS selector 取得必要 HTML 元素；不存在時直接報錯。"""

    tag = parent.select_one(selector)
    if tag is None:
        raise ValueError(f"找不到 {label}")
    return tag


def require_text(parent: BeautifulSoup | Tag, selector: str, label: str) -> str:
    """取得必要 HTML 元素文字。"""

    return require_tag(parent, selector, label).get_text(strip=True)


def is_valid_date(value: object) -> bool:
    """檢查日期欄位是否為 YYYY-MM-DD。"""

    return bool(DATE_PATTERN.match(str(value).strip()))


def read_csv_required(path: Path, required_columns: list[str]) -> pd.DataFrame:
    """讀取 CSV 並確認必要欄位存在。"""

    if not path.exists():
        raise FileNotFoundError(f"找不到 CSV：{path}")

    df = pd.read_csv(path, encoding="utf-8-sig")
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise ValueError(f"{path.name} 缺少欄位：{missing}")
    if df.empty:
        raise ValueError(f"{path.name} 沒有資料")
    return df


def latest_m2_draw_date(path: Path) -> str | None:
    """取得 M2 最新一期開獎日期；沒有有效資料時回傳 None。"""

    if not path.exists():
        return None

    df = read_csv_required(path, REQUIRED_M2_COLUMNS)
    dates = df["ndate"].astype(str).str.strip()
    valid_dates = dates[dates.map(is_valid_date)]
    if valid_dates.empty:
        return None
    return str(valid_dates.max())


def validate_generated_files() -> tuple[str, str, str]:
    """確認本次產生的 M2/M4 完整，回傳最新期、下期日期、星期。"""

    latest_draw_date = latest_m2_draw_date(M2_CSV)
    if latest_draw_date is None:
        raise ValueError("M2 找不到有效最新開獎日期")

    m4_df = read_csv_required(M4_CSV, REQUIRED_M4_COLUMNS)
    m4_df = m4_df.copy()
    m4_df["last_draw_date"] = m4_df["last_draw_date"].astype(str).str.strip()
    m4_df["next_draw_date"] = m4_df["next_draw_date"].astype(str).str.strip()
    m4_df = m4_df[
        m4_df["last_draw_date"].map(is_valid_date)
        & m4_df["next_draw_date"].map(is_valid_date)
        & m4_df["week"].notna()
    ]
    if m4_df.empty:
        raise ValueError("M4 找不到有效 next_draw_date / week")

    latest_m4 = m4_df.sort_values("last_draw_date").iloc[-1]
    if str(latest_m4["last_draw_date"]) != latest_draw_date:
        raise ValueError(
            "M2 最新期與 M4 最新摘要不一致："
            f"M2={latest_draw_date}, M4={latest_m4['last_draw_date']}"
        )

    week = str(latest_m4["week"]).strip()
    if week.endswith(".0"):
        week = week[:-2]
    if week not in {"1", "2", "3", "4", "5", "6", "7"}:
        raise ValueError(f"M4 week 不正確：{latest_m4['week']}")

    return latest_draw_date, str(latest_m4["next_draw_date"]), week


def should_copy_to_webapp() -> tuple[bool, str | None, str]:
    """比較本次下載結果與 WebApp 現有資料，判斷是否需要複製。"""

    new_latest = latest_m2_draw_date(M2_CSV)
    if new_latest is None:
        raise ValueError("本次下載後 M2 沒有有效最新期數")

    target_m2 = WEBAPP_DATA_DIR / M2_CSV.name
    old_latest = latest_m2_draw_date(target_m2)

    if old_latest is not None and new_latest <= old_latest:
        return False, old_latest, new_latest

    return True, old_latest, new_latest


def build_http_session() -> requests.Session:
    """建立可重試的 HTTP Session，降低偶發網絡慢速或斷線造成的失敗。"""

    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=1,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.headers.update(REQUEST_HEADERS)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def fetch_soup(url: str) -> BeautifulSoup:
    """下載網頁並轉成 BeautifulSoup，失敗時直接拋出錯誤。"""

    response = HTTP_SESSION.get(url, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    response.encoding = "utf-8"
    return BeautifulSoup(response.text, "html.parser")


HTTP_SESSION = build_http_session()


def download_lotto_page(page: int) -> pd.DataFrame:
    """下載單頁六合彩歷史資料，整理成 ndate, N1-N7 欄位。"""

    soup = fetch_soup(LOTTO_HISTORY_URL.format(page=page))
    table = soup.select_one("table")

    if table is None:
        raise ValueError(f"Page {page} 找不到資料表")
    table = cast(Tag, table)

    headers = [th.get_text(strip=True) for th in table.find_all("th")]
    rows: list[list[str]] = []

    for tr in table.find_all("tr")[1:]:
        cells = [td.get_text(strip=True) for td in tr.find_all("td")]
        if cells:
            rows.append(cells)

    df = pd.DataFrame(rows, columns=headers)
    required_columns = {"日期", "中獎號碼", "特別號碼"}

    if not required_columns.issubset(df.columns):
        raise ValueError(f"Page {page} 缺少必要欄位：{required_columns}")

    df = df[["日期", "中獎號碼", "特別號碼"]].copy()
    df["中獎號碼"] = df["中獎號碼"].str.replace(" ", ",", regex=False)
    number_df = df["中獎號碼"].str.split(",", expand=True)

    if number_df.shape[1] != 6:
        raise ValueError(f"Page {page} 中獎號碼數量不是 6 個")

    df[["N1", "N2", "N3", "N4", "N5", "N6"]] = number_df
    df = df[["日期", "N1", "N2", "N3", "N4", "N5", "N6", "特別號碼"]]
    df.columns = ["ndate", "N1", "N2", "N3", "N4", "N5", "N6", "N7"]
    return df[df["ndate"] != "日期"]


def create_m1_latest_history() -> None:
    """產生 M1：下載最近數頁六合彩歷史資料。"""

    dataframes = []
    for page in DOWNLOAD_PAGES:
        # print(f"   - 下載歷史資料第 {page} 頁 ...", flush=True)
        dataframes.append(download_lotto_page(page))

    combined_df = pd.concat(dataframes, ignore_index=True)
    combined_df = combined_df.sort_values(by="ndate", ascending=True).reset_index(drop=True)
    combined_df.to_csv(M1_CSV, index=False)


def get_history_csv_path() -> Path:
    """取得 M2 合併時要使用的舊歷史底表。"""

    ensure_local_history_csv()
    return LOCAL_HISTORY_CSV


def create_m2_merged_history() -> None:
    """產生 M2：合併歷史底表和 M1 最新資料。"""

    history_csv = get_history_csv_path()
    old_df = pd.read_csv(history_csv)
    new_df = pd.read_csv(M1_CSV)

    columns = ["ndate", "N1", "N2", "N3", "N4", "N5", "N6", "N7"]
    old_df.columns = columns
    new_df.columns = columns

    combined_df = pd.concat([old_df, new_df], ignore_index=True)
    combined_df = combined_df.drop_duplicates(subset="ndate", keep="first")
    combined_df = combined_df[columns]
    combined_df = combined_df.sort_values(by="ndate", ascending=True).reset_index(drop=True)
    combined_df.to_csv(M2_CSV, index=False)


def parse_latest_draw_info(soup: BeautifulSoup) -> LatestDrawInfo:
    """解析最新一期開獎資料和獎金資料。"""

    draw_number = require_text(soup, "span#latest_draw", "最新期數")
    draw_date = require_text(soup, "span#latest_date", "最新開獎日期")
    numbers = [
        str(img.get("alt", "")).strip()
        for img in soup.select("#latest_numbers img.ball")
        if str(img.get("alt", "")).strip()
    ]
    if len(numbers) != 7:
        raise ValueError(f"最新一期號碼數量不是 7 個：{numbers}")

    prize_table = soup.select_one(".divisions-full table")
    if prize_table is None:
        raise ValueError("找不到最新一期獎金表")
    prize_table = cast(Tag, prize_table)

    prizes: list[tuple[str, str, str]] = []
    for row in prize_table.select("tbody tr"):
        tds = row.find_all("td")
        if len(tds) >= 3:
            prizes.append(
                (
                    tds[0].get_text(strip=True),
                    tds[1].get_text(strip=True),
                    tds[2].get_text(strip=True),
                )
            )

    return {
        "draw_number": draw_number,
        "draw_date": draw_date,
        "numbers": numbers,
        "prizes": prizes,
    }


def parse_next_draw_info(soup: BeautifulSoup) -> NextDrawInfo:
    """解析下一期開獎日期和預估頭獎。"""

    next_draw = soup.select_one("div.upcoming")
    if next_draw is None:
        raise ValueError("找不到下一期開獎資料")
    next_draw = cast(Tag, next_draw)

    return {
        "draw_name": require_text(next_draw, "span.draw-data", "下一期期數名稱"),
        "draw_date": require_text(next_draw, "span.date-data", "下一期開獎日期"),
        "prize_fund": require_text(next_draw, "span.prize-data", "下一期預估頭獎"),
    }


def create_m3_prize_results() -> None:
    """產生 M3：最新一期開獎、獎金，以及下一期資料。"""

    soup = fetch_soup(LOTTO_HOME_URL)
    latest = parse_latest_draw_info(soup)
    next_draw = parse_next_draw_info(soup)

    with M3_CSV.open(mode="w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)

        writer.writerow(["🔴 最新一期"])
        writer.writerow(["期數", latest["draw_number"]])
        writer.writerow(["日期", latest["draw_date"]])
        writer.writerow(["號碼", ", ".join(latest["numbers"])])
        writer.writerow([])

        writer.writerow(["獎項", "獎金", "中獎注數"])
        for prize in latest["prizes"]:
            writer.writerow(prize)
        writer.writerow([])

        writer.writerow(["🟢 下一期"])
        writer.writerow(["期數名稱", next_draw["draw_name"]])
        writer.writerow(["開獎日期", next_draw["draw_date"]])
        writer.writerow(["預估頭獎", next_draw["prize_fund"]])


def extract_lotto_summary(text: str) -> dict[str, str]:
    """從 M3 文字內容抽出 M4 需要的一列摘要資料。"""

    week_map = {"一": "1", "二": "2", "三": "3", "四": "4", "五": "5", "六": "6", "日": "7"}

    last_draw_date_match = re.search(r"日期,(\d{4})年(\d{2})月(\d{2})日", text)
    lotto_match = re.search(r"號碼,\"([^\"]+)\"", text)
    next_draw_match = re.search(r"開獎日期,(\d{4})年(\d{2})月(\d{2})日\s+\((.)\)", text)
    prize_match = re.search(r"預估頭獎,\"?\$([\d,]+)\"?", text)

    if (
        last_draw_date_match is None
        or lotto_match is None
        or next_draw_match is None
        or prize_match is None
    ):
        raise ValueError("M3 內容格式不符合預期，無法產生 M4 摘要")

    lotto_list = [num.strip() for num in lotto_match.group(1).split(",") if num.strip()]
    if len(lotto_list) != 7:
        raise ValueError(f"號碼數量不等於 7，實際為 {len(lotto_list)}：{lotto_list}")

    return {
        "last_draw_date": (
            f"{last_draw_date_match.group(1)}-"
            f"{last_draw_date_match.group(2)}-"
            f"{last_draw_date_match.group(3)}"
        ),
        "N1": lotto_list[0],
        "N2": lotto_list[1],
        "N3": lotto_list[2],
        "N4": lotto_list[3],
        "N5": lotto_list[4],
        "N6": lotto_list[5],
        "N7": lotto_list[6],
        "next_draw_date": (
            f"{next_draw_match.group(1)}-"
            f"{next_draw_match.group(2)}-"
            f"{next_draw_match.group(3)}"
        ),
        "week": week_map.get(next_draw_match.group(4), ""),
        "next_draw_prize_fund": prize_match.group(1).replace(",", ""),
    }


def create_m4_prize_summary() -> None:
    """產生 M4：若同一期已存在，就不重複新增。"""

    raw_text = M3_CSV.read_text(encoding="utf-8-sig")
    row_data = extract_lotto_summary(raw_text)
    new_df = pd.DataFrame([row_data])

    if not M4_CSV.exists():
        new_df.to_csv(M4_CSV, index=False, encoding="utf-8-sig")
        return

    existing_df = pd.read_csv(M4_CSV, encoding="utf-8-sig")
    if row_data["last_draw_date"] in existing_df["last_draw_date"].values:
        return

    combined_df = pd.concat([existing_df, new_df], ignore_index=True)
    combined_df.to_csv(M4_CSV, index=False, encoding="utf-8-sig")


def copy_m1_to_m4_to_webapp_folder() -> None:
    """複製 M1-M4 與 M7 CSV 到 A_msk_lottery_data_folder；M6 由 A2 產生時複製。"""

    for csv_path in [M1_CSV, M2_CSV, M3_CSV, M4_CSV, M7_CSV]:
        if not csv_path.exists():
            raise FileNotFoundError(f"找不到要複製的檔案：{csv_path}")
        shutil.copy2(csv_path, WEBAPP_DATA_DIR / csv_path.name)


def create_m6_lotto_history_prize() -> None:
    """產生 M6 最近獎項注數與每注獎金明細。"""

    A2_lotto_history_prize.run()


def create_m7_open_days_csv() -> None:
    """產生/更新 M7 開獎日期 CSV；若本月與下月資料已存在則直接跳過。"""

    A4_mark_six_open_days.download_fixtures_to_csv()


def run() -> bool:
    """主流程：下載並比對；只有發現新期數才複製到 Web App 資料夾。"""

    timings: list[tuple[str, float]] = []
    ensure_folders()

    try:
        run_timed_step("M0 準備歷史底表", ensure_local_history_csv, timings)
        run_timed_step("M1 下載最新六合彩歷史資料", create_m1_latest_history, timings)
        run_timed_step("M2 合併新舊歷史資料", create_m2_merged_history, timings)
        run_timed_step("M3 下載最新獎金和下一期資料", create_m3_prize_results, timings)
        run_timed_step("M4 產生下一期摘要", create_m4_prize_summary, timings)
        run_timed_step("M6 下載獎項注數明細", create_m6_lotto_history_prize, timings)
        run_timed_step("M7 馬會攪珠開獎日期 CSV", create_m7_open_days_csv, timings)
        
        timing_report = format_timing_report(timings)

        latest_draw_date, next_draw_date, week = validate_generated_files()
        should_copy, old_latest, new_latest = should_copy_to_webapp()

        run_timed_step("複製 M1-M4 與 M7 到 A_msk_lottery_data_folder", copy_m1_to_m4_to_webapp_folder, timings)
        timing_report = format_timing_report(timings)

        if not should_copy:
            message = (
                f"{now_string()} \n /> A, 沒有新開獎資料，但已同步目前資料檔。\n"
                f"/>{old_latest}；下載最新期：{new_latest}\n"
                f"/> C, 下期開獎日期：{next_draw_date}，星期：{week}。\n"
                f"{timing_report}"
            )
            write_log(message)
            print(f"ℹ️ {message}")
            return True

    except KeyboardInterrupt:
        message = f"{now_string()} 使用者中斷下載，流程未完成。\n{format_timing_report(timings)}"
        write_log(message)
        print(f"\n⚠️ {message}")
        return False
    except Exception as exc:
        message = f"{now_string()} 執行失敗：{exc}\n{format_timing_report(timings)}"
        write_log(message)
        print(f"❌ {message}")
        return False

    message = (
        f"{now_string()} \n /> 1, 有發現新開獎資料並已複製完成。\n"
        f"/> 2, 最新一期：{latest_draw_date}\n"
        f"/> 3, 馬會下期開獎日期：{next_draw_date}，星期：{week}。\n"
        f"{timing_report}"
    )
    write_log(message)
    print(f"✅ {message}")
    
    
    return True


if __name__ == "__main__":
    run()
