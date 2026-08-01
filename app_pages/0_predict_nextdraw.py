from pathlib import Path
import base64
import csv
import re
from datetime import datetime
import streamlit as st
import sys


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PRIZE_RESULTS_PATH = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M3_lotto_prize_results.csv"
LOTTO_RESULTS_PATH = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M2_last_upgrade_lotto_data.csv"
BET_RECORDS_PATH = PROJECT_ROOT / "msk_new_seed_apps" / "bet_data" / "my_bet_records.csv"
BALLS_DIR = PROJECT_ROOT / "A_msk_balls_png"

# 新增：讀取 nextBetDraw_record.csv 作為下期預測球號來源
NEXT_BET_DRAW_RECORD_PATH = PROJECT_ROOT / "msk_new_seed_apps" / "bet_data" / "nextBetDraw_record.csv"
NEXT_BET_DRAW_SUMMARY_PATH = PROJECT_ROOT / "msk_new_seed_apps" / "bet_data" / "nextBetDraw_summary.csv"


PRIZE_TABLE = {
    6.0: 10_000_000,
    5.5: 1_100_000,
    5.0: 300_000,
    4.5: 9_600,
    4.0: 640,
    3.5: 320,
    3.0: 40,
}

def load_next_bet_draw_records(path: Path):
    """讀取 nextBetDraw_record.csv，回傳每一注的號碼（list of list）。"""
    if not path.exists():
        return []
    result = []
    with path.open("r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        for row in reader:
            nums = [int(x) for x in row if x.isdigit() and 1 <= int(x) <= 49]
            if len(nums) >= 6:
                result.append(nums)
    return result


def load_next_bet_draw_summary(path: Path):
    """讀取 nextBetDraw_summary.csv，回傳下期投注摘要。"""
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames:
            reader.fieldnames = [name.strip().lstrip("\ufeff") for name in reader.fieldnames]

        for row in reader:
            return {(k or "").strip().lstrip("\ufeff"): (v or "").strip() for k, v in row.items()}

    return {}


@st.cache_data(show_spinner=False)
def load_ball_image_base64(num: int):
    img_path = BALLS_DIR / f"{num}.png"
    if not img_path.exists():
        return ""
    return base64.b64encode(img_path.read_bytes()).decode("utf-8")


def extract_ymd(text: str):
    if not text:
        return None

    m_iso = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if m_iso:
        return f"{m_iso.group(1)}-{m_iso.group(2)}-{m_iso.group(3)}"

    m_zh = re.search(r"(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日", text)
    if m_zh:
        y = m_zh.group(1)
        mm = m_zh.group(2).zfill(2)
        dd = m_zh.group(3).zfill(2)
        return f"{y}-{mm}-{dd}"

    return None


def format_date_with_weekday(date_text: str):
    if not date_text:
        return "-"

    try:
        dt = datetime.strptime(date_text, "%Y-%m-%d")
    except ValueError:
        return date_text

    weekday_map = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]
    return f"{date_text}（{weekday_map[dt.weekday()]}）"


def parse_num_list(text: str):
    if not text:
        return []
    nums = [int(x) for x in re.findall(r"\d+", text)]
    return [n for n in nums if 1 <= n <= 49]


def format_seed_numbers(nums):
    if not nums:
        return "[無]"
    return "[ " + "，".join(str(n) for n in nums) + " ]"


def render_balls(nums, label: str = "", highlight=None, show_numbers: bool = True):
    if highlight is None:
        highlight = {}
    if not nums:
        st.write("-")
        return

    parts = []
    for idx, n in enumerate(nums):
        if len(nums) >= 7 and idx == 6:
            parts.append("<span style='font-weight:700;margin:0 8px;'>+</span>")

        b64 = load_ball_image_base64(int(n))
        style = "width:32px;height:32px;object-fit:contain;margin-right:3px;"
        # 高亮樣式
        if highlight.get("main") and n in highlight["main"]:
            style += "border:2.5px solid red;border-radius:50%;box-sizing:border-box;"
        elif highlight.get("special") and n == highlight["special"]:
            style += "border:2.5px solid #0074D9;border-radius:6px;box-sizing:border-box;"

        if b64:
            parts.append(
                f"<img src='data:image/png;base64,{b64}' style='{style}'/>"
            )
        else:
            span_style = "display:inline-block;margin-right:6px;font-weight:600;"
            if highlight.get("main") and n in highlight["main"]:
                span_style += "border:2.5px solid red;border-radius:50%;box-sizing:border-box;padding:2px;"
            elif highlight.get("special") and n == highlight["special"]:
                span_style += "border:2.5px solid #0074D9;border-radius:6px;box-sizing:border-box;padding:2px;"
            parts.append(f"<span style='{span_style}'>{n}</span>")

    label_html = ""
    if label:
        label_html = f"<span style='font-weight:600;margin-right:8px;'>{label}</span>"
    nums_text_html = ""
    if show_numbers:
        nums_text = " ".join(str(n) for n in nums)
        nums_text_html = (
            f"<span style='font-size:0.9rem;font-weight:600;margin-right:8px;"
            f"white-space:nowrap;color:#444;'>[{nums_text}]</span>"
        )

    st.markdown(
        f"<div style='display:flex;align-items:center;justify-content:flex-start;flex-wrap:nowrap;overflow-x:auto;'>"
        f"{label_html}{nums_text_html}{''.join(parts)}"
        f"</div>",
        unsafe_allow_html=True,
    )


def load_prize_result_info(path: Path):
    latest_date_raw = ""
    latest_numbers_raw = ""
    next_draw_raw = ""

    if not path.exists():
        return latest_date_raw, latest_numbers_raw, next_draw_raw

    with path.open("r", encoding="utf-8-sig") as f:
        rows = list(csv.reader(line for line in f if line.strip()))

    in_latest = False
    in_next = False
    for row in rows:
        if not row:
            continue
        head = row[0].strip().lstrip("\ufeff")

        if head == "🔴 最新一期":
            in_latest = True
            in_next = False
            continue
        if head == "🟢 下一期":
            in_latest = False
            in_next = True
            continue

        if in_latest and len(row) >= 2:
            key = row[0].strip().lstrip("\ufeff")
            val = ",".join(row[1:]).strip()
            if key == "日期":
                latest_date_raw = val
            elif key == "號碼":
                latest_numbers_raw = val

        if in_next and len(row) >= 2:
            key = row[0].strip().lstrip("\ufeff")
            val = ",".join(row[1:]).strip()
            if key == "開獎日期":
                next_draw_raw = val

    return latest_date_raw, latest_numbers_raw, next_draw_raw


def load_prize_payout_rows(path: Path):
    """從 M3 CSV 解析最新一期的期數及七個獎級派彩明細。"""
    period = ""
    rows = []
    if not path.exists():
        return period, rows

    with path.open("r", encoding="utf-8-sig") as f:
        raw_rows = list(csv.reader(line for line in f if line.strip()))

    in_latest = False
    in_prizes = False
    for row in raw_rows:
        if not row:
            continue
        head = row[0].strip().lstrip("\ufeff")

        if head == "\U0001f534 最新一期":
            in_latest = True
            in_prizes = False
            continue
        if head == "\U0001f7e2 下一期":
            break

        if in_latest:
            if head == "期數" and len(row) >= 2:
                period = row[1].strip()
            elif head == "獎項":
                in_prizes = True
                continue
            elif in_prizes and len(row) >= 3:
                rows.append({
                    "獎項": row[0].strip(),
                    "獎金": row[1].strip(),
                    "中獎注數": row[2].strip(),
                })

    return period, rows


def load_predictions_for_date(path: Path, target_date: str):
    if not path.exists() or not target_date:
        return []

    result = []
    with path.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames:
            reader.fieldnames = [name.strip().lstrip("\ufeff") for name in reader.fieldnames]

        for row in reader:
            clean_row = {(k or "").strip().lstrip("\ufeff"): (v or "").strip() for k, v in row.items()}
            bet_date = clean_row.get("bet_date", "")
            if bet_date != target_date:
                continue

            nums = []
            for i in range(1, 7):
                val = clean_row.get(f"N{i}", "")
                if val.isdigit():
                    n = int(val)
                    if 1 <= n <= 49:
                        nums.append(n)
            if len(nums) == 6:
                result.append(nums)

    return result


def render_home_page():

    # 加入自訂 CSS，縮小行距與分隔線間距
    st.markdown("""
        <style>
        .stMarkdown p, .stMarkdown h6, .stMarkdown h7 {
            margin-bottom: 4px !important;
            margin-top: 4px !important;
        }
        hr {
            margin-top: 4px !important;
            margin-bottom: 4px !important;
        }
        .section-gap {
            margin: 34px 0 22px 0 !important;
            border: 0;
            border-top: 2px solid #888;
        }
        </style>
    """, unsafe_allow_html=True)
    get_bet_draw = int(st.session_state.get("setting_get_BetDraw", 2))

    latest_date_raw, latest_numbers_raw, next_draw_raw = load_prize_result_info(PRIZE_RESULTS_PATH)

    latest_date = extract_ymd(latest_date_raw)
    latest_numbers = parse_num_list(latest_numbers_raw)
    next_draw_date = extract_ymd(next_draw_raw)
    next_bet_summary = load_next_bet_draw_summary(NEXT_BET_DRAW_SUMMARY_PATH)
    summary_bet_date = next_bet_summary.get("bet_date", "")
    summary_week_zh = next_bet_summary.get("week_zh", "")
    seed_numbers = parse_num_list(
        next_bet_summary.get("seed_numbers", "") or next_bet_summary.get("seed_number", "")
    )
    latest_date_display = format_date_with_weekday(latest_date or latest_date_raw)
    next_draw_date_display = format_date_with_weekday(next_draw_date or next_draw_raw)
    if summary_bet_date and summary_week_zh:
        next_draw_date_display = f"{summary_bet_date} （{summary_week_zh}）"
    elif summary_bet_date:
        next_draw_date_display = format_date_with_weekday(summary_bet_date)

   
    # st.write(f"1.下期種子投注預測")
    st.markdown('<div style="margin-bottom:12px;margin-top:8px;"><h6 style="font-size:1.4rem; font-weight:bold;display:inline-block;">1.👍 下期種子投注預測</h6></div>', unsafe_allow_html=True)
    st.markdown(f"<div style='margin-bottom:8px'><span style='font-size:1.2rem; font-weight:bold;'>上期中獎種子號 ： {format_seed_numbers(seed_numbers)}</span></div>", unsafe_allow_html=True)
    st.markdown(f"<div style='margin-bottom:8px'><span style='font-size:1.2rem; font-weight:bold;'>投注日期：{next_draw_date_display}</span></div>", unsafe_allow_html=True)
    pred_rows = load_next_bet_draw_records(NEXT_BET_DRAW_RECORD_PATH)
    if pred_rows:
        for idx, nums in enumerate(pred_rows, start=1):
            render_balls(nums, label=f"{idx}注:", show_numbers=False)
    else:
        st.info("目前沒有找到 nextBetDraw_record.csv 內的預測號碼。")

    # 加入種子過去投注紀錄及檢對中獎結果
    st.markdown("<hr class='section-gap'>", unsafe_allow_html=True)
    # st.write("3.種子過去投注紀錄（核對中獎結果）")
    st.markdown('<div style="margin-bottom:2px"><h6 style="font-size:1.4rem; font-weight:bold;display:inline-block;">2.✌️ 種子投注過往紀錄</h6></div>', unsafe_allow_html=True)
    st.markdown('<div style="margin-bottom:2px"><h7 style="font-size:1.0rem; font-weight:bold;display:inline-block;"> ❤️ ---(核對預測投注結果)</h7></div>', unsafe_allow_html=True)
    st.markdown('<div style="margin-bottom:2px"><h7 style="font-size:1.0rem; font-weight:bold;display:inline-block;"> 🩷 ---⭕️ 中正號 🔲 中特號</h7></div>', unsafe_allow_html=True)
    # 讀取開獎號碼資料（欄位名稱與 B01_check_lottoWin.py 一致）
    lotto_results = {}
    with LOTTO_RESULTS_PATH.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            date = row.get("ndate")
            nums = [int(row.get(f"N{i}", 0)) for i in range(1, 7)]
            special = int(row.get("N7", 0))
            if date and all(1 <= n <= 49 for n in nums) and 1 <= special <= 49:
                lotto_results[date.strip()] = {"nums": set(nums), "special": special}

    st.markdown("---", unsafe_allow_html=True)
    # 讀取投注紀錄，並依日期倒序排列
    bet_records = []
    with BET_RECORDS_PATH.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            date = row.get("bet_date") or row.get("日期") or row.get("date")
            nums = [int(row.get(f"N{i}", 0)) for i in range(1, 7)]
            if date and all(1 <= n <= 49 for n in nums):
                bet_records.append({"date": date.strip(), "nums": nums})
    # 依日期倒序
    bet_records.sort(key=lambda x: x["date"], reverse=True)

    total_bet = 0
    total_win = 0
    total_count = 0
    win_count = 0
    bet_amount = 10



    for rec in bet_records:
        date = rec["date"]
        nums = rec["nums"]
        total_bet += bet_amount
        total_count += 1
        # st.markdown(f"<div style='margin-bottom:2px'><span style='font-weight:bold;'>日期：{date}每注：$ {bet_amount}</span></div>", unsafe_allow_html=True)
        st.markdown(
        f"<div style='margin-bottom:2px'>"
        f"<span style='font-weight:bold; margin-right:32px;'>日期：{date}</span>"
        f"<span style='font-weight:bold;'>每注：$ {bet_amount}</span>"
        f"</div>",
        unsafe_allow_html=True
        )
        # 判斷是否已開獎
        if date in lotto_results:
            result = lotto_results[date]
            win_main_set = set(nums) & result["nums"]
            win_special = result["special"] if result["special"] in nums else None
            win_score = len(win_main_set) + (0.5 if win_special else 0)
            # 判斷獎項
            prize = "0"
            payout = 0
            for k in sorted(PRIZE_TABLE.keys(), reverse=True):
                if win_score >= k:
                    payout = PRIZE_TABLE[k]
                    if k == 6.0:
                        prize = "頭獎"
                    elif k == 5.5:
                        prize = "二獎"
                    elif k == 5.0:
                        prize = "三獎"
                    elif k == 4.5:
                        prize = "四獎"
                    elif k == 4.0:
                        prize = "五獎"
                    elif k == 3.5:
                        prize = "六獎"
                    elif k == 3.0:
                        prize = "七獎"
                    break
            if payout > 0:
                win_count += 1
                total_win += payout
            # 高亮設定
            highlight = {"main": win_main_set}
            if win_special:
                highlight["special"] = win_special
            render_balls(nums, label="過去投注號：", highlight=highlight, show_numbers=False)
            # 中獎行
            if win_score == 0:
                st.markdown(f"<div style='margin-bottom:2px'><span style='font-weight:bold;'> 中 = {win_score} 球 |  獎項: {prize} | 派彩:$ {payout} --  😊</span></div>", unsafe_allow_html=True)
            elif 0 < win_score < 3:
                st.markdown(f"<div style='margin-bottom:2px'><span style='font-weight:bold;'> 中 = {win_score} 球 |  獎項: {prize} | 派彩:$ {payout} --  ✅</span></div>", unsafe_allow_html=True)
            elif win_score == 3:
                st.markdown(f"<div style='margin-bottom:2px'><span style='font-weight:bold;'> 中 = {win_score} 球 |  獎項: {prize} | 派彩:$ {payout} --  ❤️</span></div>", unsafe_allow_html=True)
            elif win_score > 3:
                st.markdown(f"<div style='margin-bottom:2px'><span style='font-weight:bold;'> 中 > {win_score} 球 |  獎項:{prize} | 派彩:$ {payout} --  🏆🏆🏆</span></div>", unsafe_allow_html=True)
        else:
            render_balls(nums, label="最新投注號：", highlight={}, show_numbers=False)
            # st.markdown("---")
            st.markdown("<div style='margin-bottom:2px'><span style='font-weight:bold;'> | 最新投注預測： 未開獎 👀 | </span></div>", unsafe_allow_html=True)
            st.markdown("---")
        # 每筆資料下方加分隔線
        st.markdown("<hr style='margin:2px 0;border:0;border-top:1px solid #e0e0e0;'>", unsafe_allow_html=True)

    st.markdown("---")
    st.write(f"投注注數：{total_count} 注 * 每注 $10")
    st.write(f"投注總金額 💰${total_bet}")
    st.write(f"中獎注數：{win_count} 注，派彩總金額 = 💰${total_win}")
    st.write(f"損益金額 = 💰${total_win - total_bet:+} ")
    st.markdown("---")
if __name__ == "__main__":
    render_home_page()
