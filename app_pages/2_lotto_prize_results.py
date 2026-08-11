from collections import defaultdict
import csv
from datetime import datetime
from pathlib import Path
import base64
import sys

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from css import white_black_style

PRIZE_HISTORY_PATH = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"
BALLS_DIR = PROJECT_ROOT / "A_msk_balls_png"


# 本身會影響更新，但現在加了檔案指紋後，可以保留 cache，又能更新資料。
@st.cache_data(show_spinner=False)
def load_ball_image_base64(num: int):
    img_path = BALLS_DIR / f"{num}.png"
    if not img_path.exists():
        return ""
    return base64.b64encode(img_path.read_bytes()).decode("utf-8")


def get_file_signature(path: Path) -> tuple[int, int]:
    """回傳檔案更新指紋，避免 Streamlit 長駐服務讀到舊 cache。"""

    if not path.exists():
        return (0, 0)
    stat = path.stat()
    return (stat.st_mtime_ns, stat.st_size)

# 本身會影響更新，但現在加了檔案指紋後，可以保留 cache，又能更新資料。
@st.cache_data(show_spinner=False)

def load_prize_history(file_signature: tuple[int, int]):
    _ = file_signature
    if not PRIZE_HISTORY_PATH.exists():
        return []
    with PRIZE_HISTORY_PATH.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames:
            reader.fieldnames = [name.strip().lstrip("\ufeff") for name in reader.fieldnames]
        return [
            {(key or "").strip().lstrip("\ufeff"): (value or "").strip() for key, value in row.items()}
            for row in reader
        ]


def format_weekday(date_text: str):
    try:
        dt = datetime.strptime(str(date_text), "%Y-%m-%d")
    except ValueError:
        return ""
    return "一二三四五六日"[dt.weekday()]


def format_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "0"
    return f"{number:g}"


def get_consecutive_groups(nums):
    sorted_nums = sorted(set(int(num) for num in nums))
    groups = []
    current_group = []

    for num in sorted_nums:
        if not current_group or num == current_group[-1] + 1:
            current_group.append(num)
            continue
        if len(current_group) >= 2:
            groups.append(current_group)
        current_group = [num]

    if len(current_group) >= 2:
        groups.append(current_group)
    return groups


def get_same_tail_groups(nums):
    tail_map = defaultdict(list)
    for num in sorted(set(int(num) for num in nums)):
        tail_map[num % 10].append(num)
    return {tail: group for tail, group in tail_map.items() if len(group) >= 2}


def get_num49_interval_map(nums):
    interval_idx = []
    for num in nums:
        num = int(num)
        if 1 <= num <= 9:
            interval_idx.append(0)
        elif 10 <= num <= 19:
            interval_idx.append(1)
        elif 20 <= num <= 29:
            interval_idx.append(2)
        elif 30 <= num <= 40:
            interval_idx.append(3)
        elif 41 <= num <= 49:
            interval_idx.append(4)
    return interval_idx


def get_rbg_color_id(num):
    j_num = int(num) - 1
    return (((j_num // 10) + j_num) % 6 // 2) + 1


def get_rbg_pattern(nums):
    counts = {1: 0, 2: 0, 3: 0}
    for num in nums:
        counts[get_rbg_color_id(num)] += 1
    return f"{counts[1]}-{counts[2]}-{counts[3]}"


def render_balls(main_nums, special_num):
    html = '<div class="balls-row">'
    for num in main_nums:
        b64 = load_ball_image_base64(int(num))
        if b64:
            html += (
                f"<img src='data:image/png;base64,{b64}' alt='{int(num)}' "
                "style='width:32px;height:32px;object-fit:contain;margin-right:3px;'/>"
            )
        else:
            html += f"<span class='ball-fallback'>{int(num)}</span>"
    html += "<span class='plus-mark'>+</span>"
    b64 = load_ball_image_base64(int(special_num))
    if b64:
        html += (
            f"<img src='data:image/png;base64,{b64}' alt='{int(special_num)}' "
            "style='width:32px;height:32px;object-fit:contain;margin-right:3px;'/>"
        )
    else:
        html += f"<span class='ball-fallback'>{int(special_num)}</span>"
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def render_draw_record(draw_no, row):
    main_nums = [int(row[f"N{i}"]) for i in range(1, 7)]
    special_num = int(row["N7"])
    birthday_nums = [num for num in main_nums if 1 <= num <= 31]
    round_tens = [num for num in main_nums if num in {10, 20, 30, 40}]

    st.markdown(
        f"<div class='draw-title'>第 {draw_no} 期 {row['nDdate']} 星期：{format_weekday(row['nDdate'])}</div>",
        unsafe_allow_html=True,
    )
    render_balls(main_nums, special_num)
    st.markdown(
        f"""
        <div class="draw-detail">prize3: {format_number(row.get("prize3"))}，prize2: {format_number(row.get("prize2"))}</div>
        <div class="draw-detail">RBG pattern: {get_rbg_pattern(main_nums)}</div>
        <div class="draw-detail">區間 pattern: {"-".join(str(i) for i in sorted(get_num49_interval_map(main_nums)))}</div>
        <div class="draw-detail">連號: {get_consecutive_groups(main_nums)}</div>
        <div class="draw-detail">同尾: {get_same_tail_groups(main_nums)}</div>
        <div class="draw-detail">生日號組(1-31): {birthday_nums} /> {len(birthday_nums)} 球</div>
        <div class="draw-detail">10/20/30/40 特色號碼: {round_tens}</div>
        <hr>
        """,
        unsafe_allow_html=True,
    )


def main():
    st.markdown(white_black_style, unsafe_allow_html=True)
    st.markdown(
        """
        <style>
        .draw-title {
            font-size: 1.08rem;
            font-weight: 800;
            margin: 12px 0 6px;
        }
        .balls-row {
            display: flex;
            align-items: center;
            flex-wrap: nowrap;
            overflow-x: auto;
            margin: 2px 0 8px;
        }
        .plus-mark {
            font-size: 1.15rem;
            font-weight: 800;
            margin: 0 6px 0 3px;
        }
        .ball-fallback {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 32px;
            height: 32px;
            margin-right: 3px;
            border: 1px solid #999;
            border-radius: 50%;
            font-weight: 800;
        }
        .draw-detail {
            font-size: 0.98rem;
            font-weight: 700;
            margin: 2px 0 2px 18px;
        }
        hr {
            margin: 10px 0 !important;
            border: 0 !important;
            border-top: 1px solid #d9d9d9 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div style="font-size:1.25rem;font-weight:800;margin-bottom:8px;">六合彩派彩特色紀錄</div>',
        unsafe_allow_html=True,
    )

    # 重要：將 M6 檔案修改時間/大小放入 cache key。
    # Zeabur 網站是 Streamlit 長駐服務；crawler 更新 CSV 後，這行會令網頁重新讀取最新資料。
    rows = load_prize_history(get_file_signature(PRIZE_HISTORY_PATH))
    
    if not rows:
        st.warning(f"找不到資料檔：{PRIZE_HISTORY_PATH}")
        return

    required_cols = {"nDdate", "N1", "N2", "N3", "N4", "N5", "N6", "N7", "prize2", "prize3"}
    missing_cols = required_cols - set(rows[0].keys())
    if missing_cols:
        st.error(f"M6_lotto_history_prize.csv 缺少欄位：{', '.join(sorted(missing_cols))}")
        return

    period_options = [20, 50, 100] if len(rows) >= 100 else [20, 50] if len(rows) >= 50 else [len(rows)]
    num_periods = st.selectbox(
        "顯示最近幾期",
        period_options,
        index=0,
        format_func=lambda value: f"{value} 期",
        key="lotto_prize_results_num_periods",
    )

    start_draw_no = len(rows) - num_periods + 1
    display_rows = []
    for offset, row in enumerate(rows[-num_periods:]):
        display_row = dict(row)
        display_row["draw_no"] = start_draw_no + offset
        display_rows.append(display_row)

    for row in reversed(display_rows):
        render_draw_record(int(row["draw_no"]), row)


if __name__ == "__main__":
    main()
