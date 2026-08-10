from pathlib import Path
import base64
import csv
from datetime import datetime
import re
import sys

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from css import white_black_style


M3_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M3_lotto_prize_results.csv"
BALLS_DIR = PROJECT_ROOT / "A_msk_balls_png"


@st.cache_data(show_spinner=False)
def load_ball_image_base64(num: int) -> str:
    img_path = BALLS_DIR / f"{num}.png"
    if not img_path.exists():
        return ""
    return base64.b64encode(img_path.read_bytes()).decode("utf-8")


def clean_key(value: str) -> str:
    return str(value or "").strip().lstrip("\ufeff")


def parse_numbers(value: str) -> list[int]:
    nums = [int(num) for num in re.findall(r"\d+", str(value or ""))]
    return [num for num in nums if 1 <= num <= 49]


def parse_money(value: str) -> int:
    text = str(value or "").replace("$", "").replace(",", "").strip()
    try:
        return int(float(text))
    except ValueError:
        return 0


def format_money(value: str | int | float) -> str:
    return f"${parse_money(str(value)):,}"


def format_date_with_weekday(value: str) -> str:
    text = str(value or "").strip()
    if not text or "(" in text or "（" in text:
        return text

    match = re.search(r"(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日?", text)
    if not match:
        return text

    try:
        dt = datetime(
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3)),
        )
    except ValueError:
        return text

    weekday = "一二三四五六日"[dt.isoweekday() - 1]
    return f"{dt.year}年{dt.month:02d}月{dt.day:02d}日 ({weekday})"


def get_file_signature(path: Path) -> tuple[int, int]:
    """回傳檔案更新指紋，避免 Streamlit 長駐服務讀到舊 cache。"""

    if not path.exists():
        return (0, 0)
    stat = path.stat()
    return (stat.st_mtime_ns, stat.st_size)


@st.cache_data(show_spinner=False)
def load_m3_info(path: Path, file_signature: tuple[int, int]) -> dict[str, object]:
    info = {
        "period": "",
        "latest_date": "",
        "numbers": [],
        "next_draw_date": "",
        "jackpot": "",
        "estimated_prize": "",
        "prizes": [],
    }
    _ = file_signature
    if not path.exists():
        return info

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(line for line in f if line.strip()))

    section = ""
    in_prize_table = False
    for row in rows:
        if not row:
            continue
        key = clean_key(row[0])

        if key == "🔴 最新一期":
            section = "latest"
            in_prize_table = False
            continue
        if key == "🟢 下一期":
            section = "next"
            in_prize_table = False
            continue

        if section == "latest":
            if key == "期數" and len(row) >= 2:
                info["period"] = row[1].strip()
            elif key == "日期" and len(row) >= 2:
                info["latest_date"] = row[1].strip()
            elif key == "號碼" and len(row) >= 2:
                info["numbers"] = parse_numbers(",".join(row[1:]))
            elif key == "獎項":
                in_prize_table = True
            elif in_prize_table and len(row) >= 3:
                info["prizes"].append({
                    "name": row[0].strip(),
                    "payout": row[1].strip(),
                    "units": row[2].strip(),
                })

        if section == "next" and len(row) >= 2:
            if key == "開獎日期":
                info["next_draw_date"] = row[1].strip()
            elif key in {"多寶 / 金多寶", "多寶", "金多寶"}:
                info["jackpot"] = row[1].strip()
            elif key in {"估計頭獎基金", "下期頭獎基金"}:
                info["estimated_prize"] = row[1].strip()

    return info


def render_balls(nums: list[int]) -> None:
    parts = []
    for idx, num in enumerate(nums):
        if idx == 6:
            parts.append("<span class='lotto-plus'>+</span>")
        b64 = load_ball_image_base64(num)
        if b64:
            parts.append(
                f"<img src='data:image/png;base64,{b64}' alt='{num}' class='lotto-ball-img'/>"
            )
        else:
            parts.append(f"<span class='lotto-ball-fallback'>{num}</span>")

    st.markdown(
        f"<div class='lotto-balls'>{''.join(parts)}</div>",
        unsafe_allow_html=True,
    )


def main() -> None:
    st.markdown(white_black_style, unsafe_allow_html=True)
    st.markdown(
        """
        <style>
        .lotto-info-title {
            font-size: 1.45rem;
            font-weight: 900;
            margin: 0.25rem 0 0.75rem;
        }
        .lotto-next-row {
            font-size: 1.28rem;
            font-weight: 900;
            line-height: 1.35;
            margin: 0.45rem 0;
        }
        .lotto-next-label {
            color: #0057b8 !important;
        }
        .lotto-money {
            color: #d40000 !important;
        }
        .lotto-divider {
            margin: 0.9rem 0 0.8rem;
            border: 0;
            border-top: 2px solid #222222;
        }
        .lotto-info-row {
            font-size: 1.05rem;
            font-weight: 800;
            margin: 0.35rem 0;
        }
        .lotto-balls {
            display: flex;
            align-items: center;
            flex-wrap: nowrap;
            overflow-x: auto;
            gap: 4px;
            margin: 0.55rem 0 1rem;
        }
        .lotto-ball-img,
        .lotto-ball-fallback {
            width: 36px;
            height: 36px;
            min-width: 36px;
        }
        .lotto-ball-img {
            object-fit: contain;
        }
        .lotto-ball-fallback {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            border: 1px solid #999;
            border-radius: 50%;
            font-weight: 900;
        }
        .lotto-plus {
            font-weight: 900;
            margin: 0 4px;
        }
        .lotto-prize-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 0.65rem;
            font-size: 0.95rem;
        }
        .lotto-prize-table th,
        .lotto-prize-table td {
            border-bottom: 1px solid #dddddd;
            padding: 6px 4px;
            text-align: left;
            font-weight: 700;
        }
        .lotto-prize-table th {
            font-weight: 900;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    info = load_m3_info(M3_CSV, get_file_signature(M3_CSV))
    if not M3_CSV.exists():
        st.warning(f"找不到 M3 檔案：{M3_CSV}")
        return

    st.markdown(
        f"<div class='lotto-next-row lotto-next-label'>下期開獎日期：{info['next_draw_date']}</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div class='lotto-next-row lotto-next-label'>"
        f"多寶 / 金多寶：<span class='lotto-money'>{format_money(info['jackpot'])}</span></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div class='lotto-next-row lotto-next-label'>"
        f"估計頭獎基金：<span class='lotto-money'>{format_money(info['estimated_prize'])}</span></div>",
        unsafe_allow_html=True,
    )
    st.markdown("<hr class='lotto-divider'>", unsafe_allow_html=True)
    st.markdown("<div class='lotto-info-title'>最新開獎號碼及獎金</div>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='lotto-info-row'>期數：{info['period']}</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div class='lotto-info-row'>日期：{format_date_with_weekday(info['latest_date'])}</div>",
        unsafe_allow_html=True,
    )
    render_balls(info["numbers"])

    prize_rows = info["prizes"]
    if prize_rows:
        table_rows = "".join(
            "<tr>"
            f"<td>{row['name']}</td>"
            f"<td>{format_money(row['payout'])}</td>"
            f"<td>{row['units']}</td>"
            "</tr>"
            for row in prize_rows
        )
        st.markdown(
            """
            <table class="lotto-prize-table">
                <thead><tr><th>獎項</th><th>獎金</th><th>中獎注數</th></tr></thead>
                <tbody>
            """
            + table_rows
            + """
                </tbody>
            </table>
            """,
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    main()
