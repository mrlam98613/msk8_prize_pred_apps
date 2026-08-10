#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
明報六合彩後備追加工具。

用途：
1. 後備使用，不會被 A0_main.py 自動呼叫。
2. 嘗試由明報六合彩頁抽取最新一期開獎、1-7 獎派彩及下期資料。
3. 只在資料日期比本地 M2 新時，追加一筆新資料。

預設 dry-run，不會寫檔；需要真正追加時使用：
    python3 A1_mingpao_fallback_append.py --apply
"""

from __future__ import annotations

import argparse
import csv
import re
import shutil
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from bs4 import BeautifulSoup


PROJECT_DIR = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_DIR.parent
DATA_DIR = PROJECT_DIR / "Lotto_Data_Folder"
WEBAPP_DATA_DIR = REPO_ROOT / "A_msk_lottery_data_folder"
LOG_PATH = PROJECT_DIR / "log" / "lotto_download_log.txt"

MINGPAO_URL = "https://news.mingpao.com/pns/%E5%85%AD%E5%90%88%E5%BD%A9/marksix"

M2_CSV = DATA_DIR / "M2_last_upgrade_lotto_data.csv"
M3_CSV = DATA_DIR / "M3_lotto_prize_results.csv"
M4_CSV = DATA_DIR / "M4_lotto_prize_summary.csv"
M6_CSV = DATA_DIR / "M6_lotto_history_prize.csv"

WEBAPP_M2_CSV = WEBAPP_DATA_DIR / "M2_last_upgrade_lotto_data.csv"
WEBAPP_M3_CSV = WEBAPP_DATA_DIR / "M3_lotto_prize_results.csv"
WEBAPP_M4_CSV = WEBAPP_DATA_DIR / "M4_lotto_prize_summary.csv"
WEBAPP_M6_CSV = WEBAPP_DATA_DIR / "M6_lotto_history_prize.csv"

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

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-HK,zh;q=0.9,en;q=0.8",
}

PRIZE_NAME_TO_KEY = {
    "頭獎": "1",
    "二獎": "2",
    "三獎": "3",
    "四獎": "4",
    "五獎": "5",
    "六獎": "6",
    "七獎": "7",
}


@dataclass(frozen=True)
class MingpaoDraw:
    draw_id: str
    draw_date: str
    numbers: list[int]
    extra_number: int
    prizes: dict[str, int]
    winning_units: dict[str, float]
    next_draw_date: str
    next_jackpot: int
    next_prize_fund: int


def now_string() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def write_log(message: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("w", encoding="utf-8") as f:
        f.write(message.rstrip() + "\n\n")


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def clean_int(value: Any, default: int = 0) -> int:
    text = str(value).replace(",", "").replace("$", "").replace("港元", "").strip()
    if text in {"", "-", "—", "--"}:
        return default
    try:
        return int(float(text))
    except ValueError:
        return default


def clean_float(value: Any, default: float = 0.0) -> float:
    text = str(value).replace(",", "").strip()
    if text in {"", "-", "—", "--"}:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def parse_date_text(value: str) -> str | None:
    text = clean_text(value)
    patterns = [
        r"(\d{4})[年/-](\d{1,2})[月/-](\d{1,2})日?",
        r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})",
    ]
    for idx, pattern in enumerate(patterns):
        match = re.search(pattern, text)
        if not match:
            continue
        parts = [int(item) for item in match.groups()]
        if idx == 0:
            year, month, day = parts
        else:
            day, month, year = parts
        try:
            return datetime(year, month, day).strftime("%Y-%m-%d")
        except ValueError:
            return None
    return None


def fetch_html() -> str:
    response = requests.get(MINGPAO_URL, headers=REQUEST_HEADERS, timeout=(8, 15))
    if response.status_code != 200:
        raise RuntimeError(f"明報下載失敗：HTTP {response.status_code} {response.reason}")
    response.encoding = response.apparent_encoding or response.encoding
    return response.text


def page_text_from_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return clean_text(soup.get_text(" "))


def parse_numbers(text: str) -> tuple[list[int], int]:
    main_patterns = [
        r"(?:攪出號碼|中獎號碼|開獎號碼|攪珠號碼)[:：]?\s*([0-9,\s、，]+)",
        r"正選號碼[:：]?\s*([0-9,\s、，]+)",
    ]
    numbers: list[int] = []
    for pattern in main_patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        numbers = [int(item) for item in re.findall(r"\d{1,2}", match.group(1))]
        if len(numbers) >= 6:
            numbers = numbers[:6]
            break
    extra_match = re.search(r"(?:特別號碼|特別號|特號)[:：]?\s*(\d{1,2})", text)
    if len(numbers) != 6 or not extra_match:
        raise ValueError("未能從明報頁抽出完整 6 個正號及特別號")
    extra_number = int(extra_match.group(1))
    if not all(1 <= num <= 49 for num in [*numbers, extra_number]):
        raise ValueError("明報頁號碼超出 1-49 範圍")
    return numbers, extra_number


def parse_draw_id(text: str) -> str:
    match = re.search(r"(?:期數|今期攪珠期數)[:：]?\s*(\d{2}/\d{3})", text)
    return match.group(1) if match else ""


def parse_draw_date(text: str) -> str:
    patterns = [
        r"(?:攪珠日期|開獎日期|日期)[:：]?\s*([0-9年月日/\-\s()（）星期一二三四五六日]+)",
        r"六合彩結果\s*[:：]?\s*([0-9年月日/\-\s()（）星期一二三四五六日]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        parsed = parse_date_text(match.group(1))
        if parsed:
            return parsed
    raise ValueError("未能從明報頁抽出開獎日期")


def parse_next_draw_date(text: str) -> str:
    match = re.search(
        r"(?:下期攪珠|下一期|下期開獎|下期).*?(?:攪珠日期|開獎日期|日期)[:：]?\s*([0-9年月日/\-\s()（）星期一二三四五六日]+)",
        text,
    )
    if match:
        parsed = parse_date_text(match.group(1))
        if parsed:
            return parsed
    raise ValueError("未能從明報頁抽出下期開獎日期")


def parse_next_prize_fund(text: str) -> int:
    match = re.search(r"估計頭獎基金[:：]?\s*\*{0,2}\$?([0-9,.]+)", text)
    if not match:
        match = re.search(r"(?:下期頭獎基金|頭獎獨贏)[:：]?\s*\*{0,2}\$?([0-9,.]+)", text)
    return clean_int(match.group(1), 0) if match else 0


def parse_next_jackpot(text: str) -> int:
    match = re.search(r"(?:多寶\s*/\s*金多寶|金多寶|多寶)[:：]?\s*\*{0,2}\$?([0-9,.]+)", text)
    return clean_int(match.group(1), 0) if match else 0


def parse_prizes(text: str) -> tuple[dict[str, int], dict[str, float]]:
    prizes: dict[str, int] = {}
    winning_units: dict[str, float] = {}
    for name, key in PRIZE_NAME_TO_KEY.items():
        pattern = rf"{name}\s+[$—\-0-9,]+\s+[0-9,.—\-]+"
        match = re.search(pattern, text)
        if not match:
            continue
        parts = match.group(0).split()
        if len(parts) < 3:
            continue
        prizes[key] = clean_int(parts[-2])
        winning_units[key] = clean_float(parts[-1])
    if not prizes:
        raise ValueError("未能從明報頁抽出派彩表")
    return prizes, winning_units


def parse_mingpao_draw(html: str) -> MingpaoDraw:
    text = page_text_from_html(html)
    numbers, extra_number = parse_numbers(text)
    prizes, winning_units = parse_prizes(text)
    return MingpaoDraw(
        draw_id=parse_draw_id(text),
        draw_date=parse_draw_date(text),
        numbers=numbers,
        extra_number=extra_number,
        prizes=prizes,
        winning_units=winning_units,
        next_draw_date=parse_next_draw_date(text),
        next_jackpot=parse_next_jackpot(text),
        next_prize_fund=parse_next_prize_fund(text),
    )


def latest_m2_date() -> str:
    path = M2_CSV if M2_CSV.exists() else WEBAPP_M2_CSV
    if not path.exists():
        return ""
    df = pd.read_csv(path, encoding="utf-8-sig")
    return str(df["ndate"].astype(str).max()).strip()


def backup_file(path: Path) -> None:
    if not path.exists():
        return
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = PROJECT_DIR / "backup" / f"mingpao_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup_dir / path.name)


def append_unique_row(path: Path, row: dict[str, Any], columns: list[str], date_column: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        backup_file(path)
        df = pd.read_csv(path, encoding="utf-8-sig")
        df.columns = [str(col).strip().lstrip("\ufeff") for col in df.columns]
        for col in columns:
            if col not in df.columns:
                df[col] = ""
        df = pd.concat([df[columns], pd.DataFrame([row], columns=columns)], ignore_index=True)
        df[date_column] = df[date_column].astype(str).str.strip()
        df = df.drop_duplicates(subset=[date_column], keep="last")
        df = df.sort_values(date_column).reset_index(drop=True)
    else:
        df = pd.DataFrame([row], columns=columns)
    df.to_csv(path, index=False, encoding="utf-8-sig")


def format_zh_date(date_text: str) -> str:
    dt = datetime.strptime(date_text, "%Y-%m-%d")
    return f"{dt.year}年{dt.month:02d}月{dt.day:02d}日"


def format_zh_date_with_week(date_text: str) -> str:
    dt = datetime.strptime(date_text, "%Y-%m-%d")
    week_text = "一二三四五六日"[dt.isoweekday() - 1]
    return f"{format_zh_date(date_text)} ({week_text})"


def write_m3(draw: MingpaoDraw, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_file(path)
    numbers_text = ", ".join(str(num) for num in [*draw.numbers, draw.extra_number])
    rows = [
        ["🔴 最新一期"],
        ["期數", f"第{draw.draw_id}期" if draw.draw_id else ""],
        ["日期", format_zh_date(draw.draw_date)],
        ["號碼", numbers_text],
        ["獎項", "獎金", "中獎注數"],
    ]
    prize_names = [("頭獎", "1"), ("二獎", "2"), ("三獎", "3"), ("四獎", "4"), ("五獎", "5"), ("六獎", "6"), ("七獎", "7")]
    for prize_name, key in prize_names:
        rows.append([prize_name, str(draw.prizes.get(key, 0)), str(draw.winning_units.get(key, 0.0))])
    rows.extend([
        ["🟢 下一期"],
        ["開獎日期", format_zh_date_with_week(draw.next_draw_date)],
        ["多寶 / 金多寶", str(draw.next_jackpot)],
        ["估計頭獎基金", str(draw.next_prize_fund)],
    ])
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        csv.writer(f).writerows(rows)


def apply_append(draw: MingpaoDraw) -> None:
    m2_row = {
        "ndate": draw.draw_date,
        "N1": draw.numbers[0],
        "N2": draw.numbers[1],
        "N3": draw.numbers[2],
        "N4": draw.numbers[3],
        "N5": draw.numbers[4],
        "N6": draw.numbers[5],
        "N7": draw.extra_number,
    }
    m4_row = {
        "last_draw_date": draw.draw_date,
        "N1": draw.numbers[0],
        "N2": draw.numbers[1],
        "N3": draw.numbers[2],
        "N4": draw.numbers[3],
        "N5": draw.numbers[4],
        "N6": draw.numbers[5],
        "N7": draw.extra_number,
        "next_draw_date": draw.next_draw_date,
        "week": datetime.strptime(draw.next_draw_date, "%Y-%m-%d").isoweekday(),
        "next_draw_prize_fund": draw.next_prize_fund,
    }
    m6_row = {
        "nDdate": draw.draw_date,
        "N1": draw.numbers[0],
        "N2": draw.numbers[1],
        "N3": draw.numbers[2],
        "N4": draw.numbers[3],
        "N5": draw.numbers[4],
        "N6": draw.numbers[5],
        "N7": draw.extra_number,
        "prize1": draw.winning_units.get("1", 0.0),
        "prize2": draw.winning_units.get("2", 0.0),
        "prize3": draw.winning_units.get("3", 0.0),
        "prize1_unit": draw.prizes.get("1", 0),
        "prize2_unit": draw.prizes.get("2", 0),
        "prize3_unit": draw.prizes.get("3", 0),
    }
    for path in [M2_CSV, WEBAPP_M2_CSV]:
        append_unique_row(path, m2_row, M2_COLUMNS, "ndate")
    for path in [M4_CSV, WEBAPP_M4_CSV]:
        append_unique_row(path, m4_row, M4_COLUMNS, "last_draw_date")
    for path in [M6_CSV, WEBAPP_M6_CSV]:
        append_unique_row(path, m6_row, M6_COLUMNS, "nDdate")
    for path in [M3_CSV, WEBAPP_M3_CSV]:
        write_m3(draw, path)


def run(apply: bool = False) -> bool:
    try:
        draw = parse_mingpao_draw(fetch_html())
        current_latest = latest_m2_date()
        if current_latest and draw.draw_date <= current_latest:
            message = (
                f"{now_string()} 明報後備：沒有新資料。\n"
                f"/> 明報日期：{draw.draw_date}\n"
                f"/> 本地最新：{current_latest}"
            )
            print(message)
            write_log(message)
            return False
        if apply:
            apply_append(draw)
            action = "已追加"
        else:
            action = "dry-run，未寫檔"
        message = (
            f"{now_string()} 明報後備解析成功（{action}）。\n"
            f"/> 期數：{draw.draw_id or '-'}\n"
            f"/> 開獎日期：{draw.draw_date}\n"
            f"/> 號碼：{', '.join(str(num) for num in draw.numbers)} + 特{draw.extra_number}\n"
            f"/> 下期開獎日期：{draw.next_draw_date}\n"
            f"/> 多寶 / 金多寶：{draw.next_jackpot}\n"
            f"/> 估計頭獎基金：{draw.next_prize_fund}"
        )
        print(message)
        write_log(message)
        return apply
    except Exception as exc:
        message = f"{now_string()} 明報後備失敗：{exc}"
        print(message)
        write_log(message)
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="明報六合彩後備一期追加工具")
    parser.add_argument("--apply", action="store_true", help="真正寫入 CSV；預設只做 dry-run")
    args = parser.parse_args()
    run(apply=args.apply)


if __name__ == "__main__":
    main()
