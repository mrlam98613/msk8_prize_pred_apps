#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A3.py 一次性建立 M0_2008_2025_history_prize.csv。

用途：
1. 獨立下載 2008-2025 舊開獎中獎紀錄。
2. M0 欄位與 A2 產生的 M6 完全一致。
3. 新增頭獎、二獎、三獎每注獎金欄位，供 A2 合併最新資料時直接對齊。

輸出：
Lotto_Data_Folder/M0_2008_2025_history_prize.csv

欄位：
nDdate,N1,N2,N3,N4,N5,N6,N7,prize1,prize2,prize3,prize1_unit,prize2_unit,prize3_unit
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import A2_lotto_history_prize as a2


def get_cli_page_range() -> tuple[int, int]:
    """測試用參數：python3 A3.py 1 52。"""

    if len(sys.argv) <= 1:
        return a2.HISTORY_PAGE_START, a2.HISTORY_PAGE_END

    try:
        page_start = int(sys.argv[1])
        page_end = int(sys.argv[2]) if len(sys.argv) >= 3 else page_start
    except ValueError as exc:
        raise ValueError("參數必須是整數，例如：python3 A3.py 1 52") from exc

    if page_start <= 0 or page_end <= 0:
        raise ValueError("頁數必須大於 0")
    if page_start > page_end:
        raise ValueError("起始頁數不能大於結束頁數")
    return page_start, page_end


def validate_csv_fields(csv_path: Path) -> None:
    """確認 M0 欄位與 A2/M6 標準欄位一致。"""

    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames != a2.CSV_FIELDNAMES:
            raise ValueError(
                f"M0 欄位不一致：{reader.fieldnames}，預期：{a2.CSV_FIELDNAMES}"
            )


def build_m0_history_prize_csv(
    page_start: int = a2.HISTORY_PAGE_START,
    page_end: int = a2.HISTORY_PAGE_END,
) -> Path:
    """一次性下載 2008-2025 舊資料，建立可與 A2/M6 合併的 M0 CSV。"""

    rows = a2.fetch_page_range_draws(page_start, page_end)
    rows = a2.filter_rows_by_date(rows, a2.M0_START_DATE, a2.M0_END_DATE)
    rows = a2.dedupe_sort_rows(rows)
    a2.write_local_csv(a2.M0_HISTORY_PRIZE_CSV, rows)
    validate_csv_fields(a2.M0_HISTORY_PRIZE_CSV)
    return a2.M0_HISTORY_PRIZE_CSV


def main() -> None:
    page_start, page_end = get_cli_page_range()
    print(
        f"一次性建立 M0：下載 detail-view page {page_start} 至 {page_end}，"
        f"日期範圍 {a2.M0_START_DATE} 至 {a2.M0_END_DATE}"
    )
    output_path = build_m0_history_prize_csv(page_start, page_end)
    print(f"已建立 M0：{output_path}")
    print("欄位已確認與 A2/M6 一致")


if __name__ == "__main__":
    main()
