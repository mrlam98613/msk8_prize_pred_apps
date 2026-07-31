#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A2.py 下載邏輯。
M0_2008_2025_history_prize.csv 舊開獎中獎紀錄由 A3.py 一次性建立。
日常下載最近 N 期後，讀入 M0 舊資料，合併成完整 M6_lotto_history_prize.csv。

直接儲存最近 N 期開獎號碼，以及頭獎、二獎、三獎中獎注數與每注獎金。

輸出：
Lotto_Data_Folder/M0_2008_2025_history_prize.csv
Lotto_Data_Folder/M6_lotto_history_prize.csv
A_msk_lottery_data_folder/M6_lotto_history_prize.csv

欄位：

nDdate,N1,N2,N3,N4,N5,N6,N7,prize1,prize2,prize3,prize1_unit,prize2_unit,prize3_unit

"""

from __future__ import annotations

import csv
import re
import shutil
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from typing import NamedTuple
from urllib.error import URLError
from urllib.request import Request, urlopen

PROJECT_DIR = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_DIR.parent
DATA_DIR = PROJECT_DIR / "Lotto_Data_Folder"
WEBAPP_DATA_DIR = REPO_ROOT / "A_msk_lottery_data_folder"
M0_HISTORY_PRIZE_CSV = DATA_DIR / "M0_2008_2025_history_prize.csv"
M6_CSV = DATA_DIR / "M6_lotto_history_prize.csv"


# 網站 detail-view 每頁最多穩定取得 50 期；需要 100 期時會自動下載 page 1 + page 2。
DETAIL_VIEW_URL_TEMPLATE = (
    "https://zh.lottolyzer.com/history/hong-kong/mark-six/"
    "page/{page}/per-page/{per_page}/detail-view"
)

RECENT_DRAW_LIMIT = 100  # 下載最近多少期。
PER_PAGE_LIMIT = 50  # 每頁下載多少期；lottolyzer detail-view 建議保持 50。
HISTORY_PAGE_START = 1  # 一次性 M0 舊資料下載起始頁。
HISTORY_PAGE_END = 52  # 一次性 M0 舊資料下載結束頁。
M0_START_DATE = "2008-01-01"
M0_END_DATE = "2025-12-31"

REQUEST_TIMEOUT = 15
REQUEST_RETRY_LIMIT = 3
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0 Safari/537.36"
    )
}


class Token(NamedTuple):
    kind: str
    value: str


class DetailViewHTMLParser(HTMLParser):
    """將 detail-view 頁面轉成文字與球號圖片 alt token。"""

    def __init__(self) -> None:
        super().__init__()
        self.tokens: list[Token] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "img":
            return

        attr_dict = dict(attrs)
        alt = (attr_dict.get("alt") or "").strip()
        if alt:
            self.tokens.append(Token("img", alt))

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if text:
            self.tokens.append(Token("text", text))


def fetch_detail_view_html(page: int) -> str:
    """下載 detail-view HTML。"""

    url = DETAIL_VIEW_URL_TEMPLATE.format(page=page, per_page=PER_PAGE_LIMIT)
    request = Request(url, headers=REQUEST_HEADERS)
    last_error: Exception | None = None

    for attempt in range(1, REQUEST_RETRY_LIMIT + 1):
        try:
            with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                return response.read().decode("utf-8", errors="replace")
        except (TimeoutError, URLError, OSError) as exc:
            last_error = exc
            if attempt >= REQUEST_RETRY_LIMIT:
                break
            wait_seconds = attempt * 2
            print(
                f"page {page}: 下載失敗，第 {attempt}/{REQUEST_RETRY_LIMIT} 次，"
                f"{wait_seconds} 秒後重試：{exc}",
                flush=True,
            )
            time.sleep(wait_seconds)

    raise RuntimeError(f"page {page}: 下載失敗，已重試 {REQUEST_RETRY_LIMIT} 次") from last_error


def zh_date_to_iso(text: str) -> str:
    """將 2026年06月14日 (星期日) 轉成 2026-06-14。"""

    match = re.search(r"(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日", text)
    if match is None:
        raise ValueError(f"日期格式不符合預期：{text}")

    year, month, day = match.groups()
    return f"{year}-{month.zfill(2)}-{day.zfill(2)}"


def parse_winner_count(value: str) -> str:
    """抽出中獎注數，移除逗號；'-' 視為 0。"""

    value = value.strip().replace(",", "")
    if value == "-":
        return "0"
    return value


def parse_prize_winner_count(record_text: str, prize_name: str) -> str:
    """從單期文字中抽出頭獎/二獎/三獎的中獎注數。"""

    if "暫時沒有獎項資料" in record_text:
        return "0"

    pattern = rf"{re.escape(prize_name)}\s+(?:\$[\d,.]+|-)\s+([\d,.-]+)\s+(?:\$[\d,.]+|-)"
    match = re.search(pattern, record_text)
    if match is None:
        raise ValueError(f"找不到 {prize_name} 中獎注數：{record_text[:160]}")
    return parse_winner_count(match.group(1))


def parse_money_amount(value: str) -> str:
    """抽出金額，移除 $, 逗號與小數；'-' 視為 0。"""

    value = value.strip().replace("$", "").replace(",", "")
    if value == "-":
        return "0"
    return value.split(".", 1)[0]


def parse_prize_unit_amount(record_text: str, prize_name: str) -> str:
    """從單期文字中抽出頭獎/二獎/三獎的每注獎金。"""

    if "暫時沒有獎項資料" in record_text:
        return "0"

    pattern = rf"{re.escape(prize_name)}\s+(?:\$[\d,.]+|-)\s+[\d,.-]+\s+(\$[\d,.]+|-)"
    match = re.search(pattern, record_text)
    if match is None:
        raise ValueError(f"找不到 {prize_name} 每注獎金：{record_text[:160]}")
    return parse_money_amount(match.group(1))


def is_draw_number(value: str) -> bool:
    """檢查是否為 26/064 這類期數。"""

    return bool(re.fullmatch(r"\d{2}/\d{3}", value.strip()))


def is_lotto_ball_alt(value: str) -> bool:
    """檢查 img alt 是否為 1..49 球號。"""

    if not value.isdigit():
        return False
    return 1 <= int(value) <= 49


def parse_detail_view_draws(html: str) -> list[dict[str, str]]:
    """解析單頁 detail-view，回傳 M6 CSV 所需資料列。"""

    parser = DetailViewHTMLParser()
    parser.feed(html)
    tokens = parser.tokens

    draw_starts = [
        idx
        for idx, token in enumerate(tokens)
        if token.kind == "text" and is_draw_number(token.value)
    ]

    rows: list[dict[str, str]] = []
    for pos, start_idx in enumerate(draw_starts):
        end_idx = draw_starts[pos + 1] if pos + 1 < len(draw_starts) else len(tokens)
        record_tokens = tokens[start_idx:end_idx]

        if len(record_tokens) < 2:
            continue

        draw_date = ""
        for token in record_tokens[1:6]:
            if token.kind == "text" and "年" in token.value and "月" in token.value:
                draw_date = zh_date_to_iso(token.value)
                break
        if not draw_date:
            raise ValueError(f"找不到開獎日期：{record_tokens[:8]}")

        numbers = [
            int(token.value)
            for token in record_tokens
            if token.kind == "img" and is_lotto_ball_alt(token.value)
        ]
        if len(numbers) < 7:
            raise ValueError(f"{draw_date} 找不到 7 個開獎號碼：{numbers}")
        numbers = numbers[:7]

        record_text = " ".join(
            token.value for token in record_tokens if token.kind == "text"
        )

        rows.append(
            {
                "nDdate": draw_date,
                "N1": str(numbers[0]),
                "N2": str(numbers[1]),
                "N3": str(numbers[2]),
                "N4": str(numbers[3]),
                "N5": str(numbers[4]),
                "N6": str(numbers[5]),
                "N7": str(numbers[6]),
                "prize1": parse_prize_winner_count(record_text, "頭獎"),
                "prize2": parse_prize_winner_count(record_text, "二獎"),
                "prize3": parse_prize_winner_count(record_text, "三獎"),
                "prize1_unit": parse_prize_unit_amount(record_text, "頭獎"),
                "prize2_unit": parse_prize_unit_amount(record_text, "二獎"),
                "prize3_unit": parse_prize_unit_amount(record_text, "三獎"),
            }
        )

    return rows


def fetch_recent_draws(limit: int = RECENT_DRAW_LIMIT) -> list[dict[str, str]]:
    """按需要自動翻頁，下載最近 limit 期。"""

    rows: list[dict[str, str]] = []
    page = 1

    while len(rows) < limit:
        html = fetch_detail_view_html(page)
        page_rows = parse_detail_view_draws(html)
        if not page_rows:
            break

        rows.extend(page_rows)
        used_count = min(len(rows), limit)
        print(f"page {page}: 解析到 {len(page_rows)} 期，已取用 {used_count}/{limit} 期", flush=True)
        page += 1

    rows = rows[:limit]
    if len(rows) != limit:
        raise ValueError(f"只解析到 {len(rows)} 期，預期 {limit} 期")

    return rows


def fetch_page_range_draws(page_start: int, page_end: int) -> list[dict[str, str]]:
    """下載指定頁數範圍的 detail-view 開獎中獎紀錄。"""

    rows: list[dict[str, str]] = []
    for page in range(page_start, page_end + 1):
        html = fetch_detail_view_html(page)
        page_rows = parse_detail_view_draws(html)
        rows.extend(page_rows)
        print(f"page {page}: 解析到 {len(page_rows)} 期，累計 {len(rows)} 期", flush=True)

    return rows


def filter_rows_by_date(
    rows: list[dict[str, str]],
    start_date: str,
    end_date: str,
) -> list[dict[str, str]]:
    """依 nDdate 篩選日期範圍。"""

    return [
        row
        for row in rows
        if start_date <= str(row["nDdate"]) <= end_date
    ]


CSV_FIELDNAMES = [
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


def normalize_row_fields(row: dict[str, str]) -> dict[str, str]:
    """補齊 CSV 欄位，讓舊 M0 rows 也可合併寫入新版 M6。"""

    return {field: str(row.get(field, "")) for field in CSV_FIELDNAMES}


def dedupe_sort_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """用 nDdate 去重，並按日期由舊至新排序，最新紀錄在最後。"""

    deduped: dict[str, dict[str, str]] = {}
    for row in rows:
        normalized_row = normalize_row_fields(row)
        deduped[str(normalized_row["nDdate"])] = normalized_row
    return sorted(
        deduped.values(),
        key=lambda row: str(row["nDdate"]),
    )


def write_csv(csv_path: Path, rows: list[dict[str, str]]) -> None:
    """寫出日期由舊至新的 CSV，並複製到 Web App 資料夾。"""

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    WEBAPP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    rows = dedupe_sort_rows(rows)

    with csv_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    shutil.copy2(csv_path, WEBAPP_DATA_DIR / csv_path.name)


def write_local_csv(csv_path: Path, rows: list[dict[str, str]]) -> None:
    """只寫日期由舊至新的 CSV 到 Lotto_Data_Folder，不複製到 Web App 資料夾。"""

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    rows = dedupe_sort_rows(rows)
    with csv_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def read_csv_rows(csv_path: Path) -> list[dict[str, str]]:
    """讀入標準開獎中獎 CSV。"""

    if not csv_path.exists():
        raise FileNotFoundError(f"找不到 CSV：{csv_path}")

    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        rows = list(reader)

    if not rows:
        raise ValueError(f"CSV 沒有資料：{csv_path}")
    return rows


def build_m0_history_prize_csv(
    page_start: int = HISTORY_PAGE_START,
    page_end: int = HISTORY_PAGE_END,
) -> Path:
    """一次性下載 2008-2025 舊開獎中獎紀錄，建立 M0 CSV。"""

    rows = fetch_page_range_draws(page_start, page_end)
    rows = filter_rows_by_date(rows, M0_START_DATE, M0_END_DATE)
    rows = dedupe_sort_rows(rows)
    write_local_csv(M0_HISTORY_PRIZE_CSV, rows)
    print(f"已建立 M0：{M0_HISTORY_PRIZE_CSV}，共 {len(rows)} 期")
    return M0_HISTORY_PRIZE_CSV


def write_m6_csv(rows: list[dict[str, str]]) -> None:
    """寫出 M6 最近 N 期原始開獎及中獎紀錄。"""

    write_csv(M6_CSV, rows)


def build_m6_rows(recent_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """讀入 M0 舊資料，合併近期下載資料，產生完整 M6 rows。"""

    m0_rows = read_csv_rows(M0_HISTORY_PRIZE_CSV)
    return dedupe_sort_rows(recent_rows + m0_rows)


def read_m6_csv() -> list[dict[str, str]]:
    """從已建立的 M6 CSV 讀入開獎及中獎紀錄。"""

    if not M6_CSV.exists():
        raise FileNotFoundError(f"找不到 M6 CSV：{M6_CSV}")

    with M6_CSV.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        rows = list(reader)

    if not rows:
        raise ValueError(f"M6 CSV 沒有資料：{M6_CSV}")

    return rows


def get_cli_limit() -> int:
    """測試用參數：python3 A2_lotto_history_prize.py 100。"""

    if len(sys.argv) <= 1:
        return RECENT_DRAW_LIMIT

    try:
        recent_limit = int(sys.argv[1])
    except ValueError as exc:
        raise ValueError(
            "參數必須是整數，例如：python3 A2_lotto_history_prize.py 100"
        ) from exc

    if recent_limit <= 0:
        raise ValueError("下載期數必須大於 0")
    return recent_limit


def run(limit: int = RECENT_DRAW_LIMIT) -> Path:
    """下載最近 N 期，合併 M0 舊資料，產生完整 M6 CSV。"""

    recent_rows = fetch_recent_draws(limit)
    rows = build_m6_rows(recent_rows)
    write_m6_csv(rows)
    return M6_CSV


def main() -> None:
    if len(sys.argv) >= 2 and sys.argv[1] == "build-m0":
        print("M0 一次性建立已改由 A3.py 執行。")
        print("請執行：python3 A3.py")
        return

    limit = get_cli_limit()
    print(f"下載最近 {limit} 期開獎明細")
    print(f"讀入 M0 舊資料：{M0_HISTORY_PRIZE_CSV}")
    m6_path = run(limit)
    print(f"已儲存 M6：{m6_path}")
    print(f"已複製 M6：{WEBAPP_DATA_DIR / m6_path.name}")

    
    

if __name__ == "__main__":
    main()
