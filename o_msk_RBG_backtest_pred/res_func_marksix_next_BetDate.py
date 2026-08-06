#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""讀取下一期開獎日期。

新版改為讀取 M3_lotto_prize_results.csv。

M3 內同時保存：
1. 最新一期開獎日期及號碼
2. 下一期開獎日期及星期

保留舊函式名稱 get_JC_next_Date()，讓其他策略模組不用修改。
"""

from __future__ import annotations

import csv
import datetime as dt
import re
from pathlib import Path


CURRENT_DIR = Path(__file__).resolve().parent
DATA_DIR = CURRENT_DIR.parent / "A_msk_lottery_data_folder"
M3_CSV = DATA_DIR / "M3_lotto_prize_results.csv"

ZH_WEEK_TO_NUM = {"一": "1", "二": "2", "三": "3", "四": "4", "五": "5", "六": "6", "日": "7"}
ZH_DATE_PATTERN = re.compile(r"(\d{4})年(\d{2})月(\d{2})日(?:\s+\((.)\))?")


def parse_zh_date(value: str) -> tuple[str, str | None]:
    """解析中文日期，回傳 (YYYY-MM-DD, week_or_none)。"""

    match = ZH_DATE_PATTERN.search(value.strip())
    if match is None:
        raise ValueError(f"日期格式不正確：{value}")

    date_text = f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    week_text = match.group(4)
    return date_text, ZH_WEEK_TO_NUM.get(week_text) if week_text else None


def iso_week_from_date(date_text: str) -> str:
    """由 YYYY-MM-DD 日期推算星期數字；星期一=1，星期日=7。"""

    return str(dt.datetime.strptime(date_text, "%Y-%m-%d").isoweekday())


def read_m3_rows() -> list[list[str]]:
    """讀取 M3 原始列。"""

    if not M3_CSV.exists():
        raise FileNotFoundError(f"找不到資料檔：{M3_CSV}")

    with M3_CSV.open("r", encoding="utf-8-sig", newline="") as file:
        return [[cell.strip() for cell in row] for row in csv.reader(file) if row]


def get_JC_next_Date() -> tuple[str, str]:
    """從 M3 取得下一期開獎日期與星期數字。"""

    rows = read_m3_rows()
    row_map = {row[0]: row[1:] for row in rows if len(row) >= 2}
    if "開獎日期" not in row_map:
        raise ValueError("M3 缺少下一期開獎日期")

    next_draw_date, next_draw_week = parse_zh_date(row_map["開獎日期"][0])
    if next_draw_week is None:
        next_draw_week = iso_week_from_date(next_draw_date)

    return next_draw_date, next_draw_week


def main() -> tuple[str, str]:
    return get_JC_next_Date()


if __name__ == "__main__":
    print(main())
