#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""檢查 M2/M3 最新開獎日期是否一致。"""

from __future__ import annotations

import csv
import re
import time
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "A_msk_lottery_data_folder"
M2_CSV = DATA_DIR / "M2_last_upgrade_lotto_data.csv"
M3_CSV = DATA_DIR / "M3_lotto_prize_results.csv"

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ZH_DATE_PATTERN = re.compile(r"(\d{4})年(\d{2})月(\d{2})日")


def now_string() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def write_log(message: str) -> None:
    print(message)


def is_valid_date(value: object) -> bool:
    return bool(DATE_PATTERN.match(str(value).strip()))


def latest_m2_date() -> str:
    if not M2_CSV.exists():
        raise FileNotFoundError(f"找不到 M2：{M2_CSV}")

    df = pd.read_csv(M2_CSV, encoding="utf-8-sig", index_col=False)
    if "ndate" not in df.columns or df.empty:
        raise ValueError("M2 缺少 ndate 或沒有資料")

    dates = df["ndate"].astype(str).str.strip()
    valid_dates = dates[dates.map(is_valid_date)]
    if valid_dates.empty:
        raise ValueError("M2 找不到有效 ndate")
    return str(valid_dates.max())


def parse_zh_date(value: str) -> str:
    match = ZH_DATE_PATTERN.search(value.strip())
    if match is None:
        raise ValueError(f"M3 日期格式不正確：{value}")
    return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"


def m3_dates() -> tuple[str, str]:
    if not M3_CSV.exists():
        raise FileNotFoundError(f"找不到 M3：{M3_CSV}")

    with M3_CSV.open("r", encoding="utf-8-sig", newline="") as file:
        rows = [[cell.strip() for cell in row] for row in csv.reader(file) if row]

    row_map = {row[0]: row[1:] for row in rows if len(row) >= 2}
    if "日期" not in row_map or "開獎日期" not in row_map:
        raise ValueError("M3 缺少 日期 / 開獎日期")

    return parse_zh_date(row_map["日期"][0]), parse_zh_date(row_map["開獎日期"][0])


def main() -> int:
    try:
        m2_latest = latest_m2_date()
        m3_latest, m3_next = m3_dates()
        if m2_latest != m3_latest:
            write_log(f"{now_string()} M2/M3 最新期不一致。M2={m2_latest}；M3={m3_latest}")
            return 1

        write_log(f"{now_string()} M2/M3 最新期一致。最新期={m2_latest}；下期={m3_next}")
        return 0
    except Exception as exc:
        write_log(f"{now_string()} 檢查資料失敗：{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
