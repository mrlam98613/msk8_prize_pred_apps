from pathlib import Path
import base64
import csv
import json
import re
import sys
from datetime import datetime

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db import (  # noqa: E402
    add_member_bet,
    delete_all_member_bets,
    delete_member,
    delete_member_bet,
    get_all_members,
    get_member,
    init_member_bet_db,
    is_valid_local_phone,
    list_member_bets,
    member_bet_exists,
    update_member_simple,
)
from css import white_black_style  # noqa: E402
from member.member_custom_bet import render_custom_bet_page  # noqa: E402


PRIZE_RESULTS_PATH = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M3_lotto_prize_results.csv"
LOTTO_RESULTS_PATH = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M2_last_upgrade_lotto_data.csv"
BALLS_DIR = PROJECT_ROOT / "A_msk_balls_png"
NEXT_BET_DRAW_RECORD_PATH = (
    PROJECT_ROOT / "msk_new_seed_apps" / "bet_data" / "nextBetDraw_record.csv"
)

PRIZE_TABLE = {
    6.0: 10_000_000,
    5.5: 1_100_000,
    5.0: 300_000,
    4.5: 9_600,
    4.0: 640,
    3.5: 320,
    3.0: 40,
}


def require_login() -> str | None:
    """未登入時阻止使用會員投注中心。"""

    email = st.session_state.get("login_email_val")
    if not email:
        st.warning("請先登入會員，才可以使用會員投注中心。")
        st.info("請在上方功能選單選擇「會員登入投注」，完成登入後會自動進入投注中心。")
        return None

    init_member_bet_db(email)
    return email


def extract_ymd(text: str) -> str:
    """從中文日期或 ISO 日期取出 yyyy-mm-dd。"""

    if not text:
        return ""

    iso = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if iso:
        return f"{iso.group(1)}-{iso.group(2)}-{iso.group(3)}"

    zh = re.search(r"(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日", text)
    if zh:
        return f"{zh.group(1)}-{zh.group(2).zfill(2)}-{zh.group(3).zfill(2)}"

    return text


def load_next_draw_date() -> str:
    """從 M3_lotto_prize_results.csv 讀取下一期開獎日期。"""

    if not PRIZE_RESULTS_PATH.exists():
        return ""

    with PRIZE_RESULTS_PATH.open("r", encoding="utf-8-sig") as f:
        for row in csv.reader(f):
            if row and row[0].strip().lstrip("\ufeff") == "開獎日期" and len(row) >= 2:
                return extract_ymd(row[1].strip())

    return ""


def format_date_with_weekday(date_text: str) -> str:
    """把 yyyy-mm-dd 顯示成 yyyy-mm-dd（星期X）。"""

    if not date_text:
        return ""

    try:
        dt = datetime.strptime(date_text, "%Y-%m-%d")
    except ValueError:
        return date_text

    week_map = ["一", "二", "三", "四", "五", "六", "日"]
    return f"{date_text}（星期{week_map[dt.weekday()]}）"


def format_date_with_weekday_short(date_text: str) -> str:
    """把 yyyy-mm-dd 顯示成 yyyy-mm-dd (X)。"""

    if not date_text:
        return ""

    try:
        dt = datetime.strptime(date_text, "%Y-%m-%d")
    except ValueError:
        return date_text

    week_map = ["一", "二", "三", "四", "五", "六", "日"]
    return f"{date_text} ({week_map[dt.weekday()]})"


def load_system_prediction_rows() -> list[list[int]]:
    """讀取系統預測的下期單式投注號碼。"""

    if not NEXT_BET_DRAW_RECORD_PATH.exists():
        return []

    rows = []
    with NEXT_BET_DRAW_RECORD_PATH.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            nums = []
            for i in range(1, 7):
                value = (row.get(f"N{i}") or "").strip()
                if value.isdigit():
                    nums.append(int(value))
            if len(nums) == 6 and all(1 <= n <= 49 for n in nums):
                rows.append(nums)
    return rows


@st.cache_data(show_spinner=False)
def load_ball_image_base64(num: int) -> str:
    """讀取球號圖片並轉成 base64，方便 Streamlit 直接顯示。"""

    img_path = BALLS_DIR / f"{int(num)}.png"
    if not img_path.exists():
        return ""
    return base64.b64encode(img_path.read_bytes()).decode("utf-8")


def render_ball_images(nums: list[int], highlight: dict | None = None) -> None:
    """用球圖顯示投注號碼；中正號紅圈，中特號藍框。"""

    highlight = highlight or {}
    parts = []
    for num in nums:
        b64 = load_ball_image_base64(int(num))
        style = "width:34px;height:34px;object-fit:contain;margin-right:4px;"
        span_style = "display:inline-block;margin-right:6px;font-weight:700;"

        if highlight.get("main") and int(num) in highlight["main"]:
            style += "border:2.5px solid red;border-radius:50%;box-sizing:border-box;"
            span_style += "border:2.5px solid red;border-radius:50%;box-sizing:border-box;padding:2px;"
        elif highlight.get("special") and int(num) == int(highlight["special"]):
            style += "border:2.5px solid #0074D9;border-radius:6px;box-sizing:border-box;"
            span_style += "border:2.5px solid #0074D9;border-radius:6px;box-sizing:border-box;padding:2px;"

        if b64:
            parts.append(
                "<img "
                f"src='data:image/png;base64,{b64}' "
                f"alt='{int(num)}' "
                f"style='{style}'/>"
            )
        else:
            parts.append(
                f"<span style='{span_style}'>"
                f"{int(num):02d}</span>"
            )

    st.markdown(
        f"<div style='display:flex;align-items:center;gap:2px;flex-wrap:wrap;margin:4px 0;'>{''.join(parts)}</div>",
        unsafe_allow_html=True,
    )


def load_lotto_results() -> dict[str, dict]:
    """讀取已開獎結果，用於會員投注損益計算。"""

    results = {}
    if not LOTTO_RESULTS_PATH.exists():
        return results

    with LOTTO_RESULTS_PATH.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            date = (row.get("ndate") or "").strip()
            nums = []
            for i in range(1, 7):
                value = (row.get(f"N{i}") or "").strip()
                if value.isdigit():
                    nums.append(int(value))
            special = (row.get("N7") or "").strip()
            if date and len(nums) == 6 and special.isdigit():
                results[date] = {"main": set(nums), "special": int(special)}

    return results


def calculate_simple_payout(numbers: list[int], draw_result: dict, bet_unit: int = 10) -> int:
    """暫時計算單式派彩；複式和膽拖可在自定投注完成後再擴展。"""

    number_set = set(int(num) for num in numbers)
    hit_main = len(number_set & draw_result["main"])
    hit_special = draw_result["special"] in number_set
    score = hit_main + (0.5 if hit_special else 0.0)
    payout = PRIZE_TABLE.get(score, 0)

    if bet_unit == 5:
        return int(payout / 2)
    return int(payout)


def calculate_hit_summary(numbers: list[int], draw_result: dict | None) -> tuple[float | None, str, dict]:
    """計算中獎球數、獎項及球圖高亮。"""

    if not draw_result:
        return None, "-", {}

    number_set = {int(num) for num in numbers}
    win_main_set = number_set & draw_result["main"]
    win_special = draw_result["special"] if draw_result["special"] in number_set else None
    score = len(win_main_set) + (0.5 if win_special else 0.0)
    prize = "0"
    for rule_score in sorted(PRIZE_TABLE.keys(), reverse=True):
        if score >= rule_score:
            prize = {
                6.0: "頭獎",
                5.5: "二獎",
                5.0: "三獎",
                4.5: "四獎",
                4.0: "五獎",
                3.5: "六獎",
                3.0: "七獎",
            }.get(rule_score, "0")
            break

    highlight = {"main": win_main_set}
    if win_special:
        highlight["special"] = win_special
    return score, prize, highlight


def format_hit_score(score: float | None) -> str:
    """中獎球數格式，例如 0.5、1、1.5。"""

    if score is None:
        return "-"
    return str(int(score)) if float(score).is_integer() else f"{score:g}"


def format_result_mood(score: float | None) -> str:
    """根據中獎球數顯示開獎心情。"""

    if score is None:
        return "開獎心情 -- 等待開獎"
    if score == 0:
        return "開獎心情 -- 😊"
    if score < 3:
        return "開獎心情 -- 🩷"
    return "開獎心情 -- 🏆"


def enrich_bet_rows_with_results(rows: list[dict]) -> list[dict]:
    """把會員投注紀錄加上即時計算的開獎狀態和派彩。"""

    lotto_results = load_lotto_results()
    enriched_rows = []

    for row in rows:
        item = dict(row)
        numbers = json.loads(item.get("numbers") or "[]")
        bet_date = item.get("bet_date", "")
        bet_type = item.get("bet_type", "")

        if bet_date in lotto_results and bet_type == "六合彩單式":
            item["result_status"] = "已開獎"
            item["payout"] = calculate_simple_payout(
                numbers=numbers,
                draw_result=lotto_results[bet_date],
                bet_unit=int(item.get("bet_unit") or 10),
            )
        elif bet_date in lotto_results:
            item["result_status"] = "已開獎"
            item["payout"] = int(item.get("payout") or 0)
        else:
            item["result_status"] = "未開獎"
            item["payout"] = int(item.get("payout") or 0)

        enriched_rows.append(item)

    return enriched_rows


def render_system_prediction_tab(email: str) -> None:
    st.subheader("A. 系統預測投注")
    st.markdown(
        """
        <style>
        div[data-testid="stButton"] > button[kind="primary"] {
            background: #dc2626 !important;
            color: #ffffff !important;
            border: 1px solid #b91c1c !important;
            border-radius: 8px !important;
            font-weight: 700 !important;
        }
        div[data-testid="stButton"] > button[kind="primary"]:hover {
            background: #b91c1c !important;
            border-color: #991b1b !important;
            color: #ffffff !important;
        }
        div[data-testid="stButton"] > button[kind="primary"]:disabled {
            background: #f3f4f6 !important;
            color: #9ca3af !important;
            border-color: #e5e7eb !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    bet_date = load_next_draw_date()
    prediction_rows = load_system_prediction_rows()

    if bet_date:
        st.markdown(
            f'<h6 style="font-size:1.05rem;font-weight:800;color:#111827;margin:4px 0 10px 0;">投注日期：{format_date_with_weekday(bet_date)}</h6>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<h6 style="font-size:1.05rem;font-weight:800;color:#111827;margin:4px 0 10px 0;">投注日期：未找到下一期日期</h6>',
            unsafe_allow_html=True,
        )

    if not prediction_rows:
        st.info("目前沒有系統預測投注號碼。")
        return

    for index, nums in enumerate(prediction_rows, start=1):
        with st.container(border=True):
            st.write(f"第 {index} 注｜六合彩單式")
            render_ball_images(nums)
            st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)

            clicked = st.button(
                "🎯 將預測加入下期投注",
                key=f"add_system_bet_{index}",
                type="primary",
            )

            if clicked:
                if member_bet_exists(email, bet_date, "系統預測", "六合彩單式", nums):
                    st.warning("這筆投注已存在：相同日期、來源、種類及號碼不可重複投注。")
                else:
                    add_member_bet(
                        email=email,
                        bet_date=bet_date,
                        bet_source="系統預測",
                        bet_type="六合彩單式",
                        numbers=nums,
                        bet_unit=10,
                        total_bets=1,
                        total_cost=10,
                        notes="由系統下期預測投注加入",
                    )
                    st.success("已加入會員投注紀錄。")


def render_custom_bet_tab(email: str) -> None:
    render_custom_bet_page(email)


def normalize_bet_rows(rows: list[dict]) -> pd.DataFrame:
    """把 SQLite rows 轉成畫面顯示用表格。"""

    display_rows = []
    for row in rows:
        numbers = json.loads(row.get("numbers") or "[]")
        bankers = json.loads(row.get("bankers") or "[]")
        legs = json.loads(row.get("legs") or "[]")
        display_rows.append(
            {
                "建立時間": row.get("created_at", ""),
                "投注日期": row.get("bet_date", ""),
                "來源": row.get("bet_source", ""),
                "投注種類": row.get("bet_type", ""),
                "號碼": "、".join(f"{int(n):02d}" for n in numbers),
                "膽號": "、".join(f"{int(n):02d}" for n in bankers),
                "配腳": "、".join(f"{int(n):02d}" for n in legs),
                "每注": row.get("bet_unit", 10),
                "注數": row.get("total_bets", 1),
                "金額": row.get("total_cost", 10),
                "狀態": row.get("result_status", "pending"),
                "派彩": row.get("payout", 0),
            }
        )

    return pd.DataFrame(display_rows)


def render_profit_summary(rows: list[dict]) -> None:
    """顯示會員投注損益資料；未開獎投注也列入總投注金額。"""

    opened_rows = [row for row in rows if row.get("result_status") == "已開獎"]
    draw_count = len({row.get("bet_date") for row in rows if row.get("bet_date")})
    opened_draw_count = len({row.get("bet_date") for row in opened_rows if row.get("bet_date")})
    total_cost = sum(int(row.get("total_cost") or 0) for row in rows)
    total_payout = sum(int(row.get("payout") or 0) for row in opened_rows)
    profit = total_payout - total_cost
    profit_text = f"+${profit:,}" if profit >= 0 else f"-${abs(profit):,}"

    st.markdown(
        f"""
            <div style="border:1px solid #e5e7eb;border-radius:8px;padding:10px 12px;margin:8px 0 14px 0;background:#fafafa;">
                <div style="font-weight:700;margin-bottom:6px;">會員投注損益資料</div>
            <div>投注期次數：{draw_count} 次｜已開獎：{opened_draw_count} 次</div>
            <div>總投注金額：${total_cost:,}</div>
            <div>總派彩金額：${total_payout:,}</div>
            <div style="font-weight:700;">投注派彩損益：{profit_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def sync_delete_selection(rows: list[dict], key_prefix: str) -> None:
    """根據刪除模式同步每筆投注的勾選狀態。"""

    delete_mode = st.session_state.get(f"{key_prefix}_member_bet_delete_mode", "自定勾選")

    if delete_mode == "全部勾選":
        for row in rows:
            st.session_state[f"{key_prefix}_select_bet_{row['id']}"] = True
    elif delete_mode == "取消":
        for row in rows:
            st.session_state[f"{key_prefix}_select_bet_{row['id']}"] = False


def render_bet_records_tab(email: str, key_prefix: str = "member") -> None:
    st.subheader("C. 會員投注紀錄")
    st.markdown(
        """
        <style>
        .bet-card {
            min-width: 360px;
            margin-top: -4px;
            margin-bottom: -8px;
        }
        .bet-card-title {
            font-weight: 700;
            font-size: 14px;
            line-height: 1.35;
            margin-bottom: 5px;
        }
        .bet-card-date {
            font-weight: 700;
            font-size: 14px;
            line-height: 1.35;
            margin-bottom: 5px;
        }
        .bet-record-meta {
            font-size: 14px;
            font-weight: 700;
            line-height: 1.35;
            margin-top: 5px;
        }
        .bet-record-result {
            font-size: 14px;
            font-weight: 700;
            line-height: 1.35;
            margin-top: 4px;
        }
        .bet-status-unopened {
            color: #dc2626;
            font-weight: 800;
        }
        .bet-record-mood {
            font-size: 14px;
            font-weight: 800;
            line-height: 1.35;
            margin-top: 4px;
            margin-bottom: 0;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.bet-card) {
            padding-top: 4px !important;
            padding-bottom: 0 !important;
            margin-bottom: 6px !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.bet-card) [data-testid="stVerticalBlock"] {
            gap: 0.1rem !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.bet-card) div[data-testid="stMarkdownContainer"] p {
            margin: 0 !important;
        }
        .delete-zone div[data-testid="stHorizontalBlock"] {
            align-items: center;
            gap: 2px;
            flex-wrap: nowrap;
        }
        .delete-zone div[data-testid="column"] {
            min-width: 0 !important;
        }
        .delete-zone div[data-testid="stCheckbox"] {
            min-width: 24px !important;
            width: 24px !important;
        }
        .delete-zone label {
            white-space: nowrap;
            font-size: 13px;
        }
        .delete-zone button {
            width: 52px !important;
            min-width: 52px !important;
            max-width: 52px !important;
            height: 28px !important;
            padding: 2px 4px !important;
            font-size: 11px !important;
            line-height: 1 !important;
            border-radius: 6px !important;
            color: #b91c1c !important;
            border: 1px solid #fecaca !important;
            background: #fff7f7 !important;
            box-shadow: none !important;
            font-weight: 700 !important;
        }
        .delete-zone button:hover:enabled {
            color: #ffffff !important;
            border-color: #dc2626 !important;
            background: #dc2626 !important;
        }
        .delete-zone button:disabled {
            color: #b8b8b8 !important;
            border-color: #eeeeee !important;
            background: #f7f7f7 !important;
        }
        .delete-zone button p {
            white-space: nowrap;
            font-size: 11px !important;
        }
        .delete-actions-row {
            display: flex;
            justify-content: flex-start;
            align-items: center;
            margin-top: -2px;
            margin-bottom: -18px;
            padding: 0;
            line-height: 1;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.bet-card) div[data-testid="stCheckbox"] {
            margin-top: -12px !important;
            margin-bottom: -20px !important;
            padding-top: 0 !important;
            padding-bottom: 0 !important;
            min-height: 20px !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.bet-card) div[data-testid="stCheckbox"] label {
            min-height: 20px !important;
            padding-top: 0 !important;
            padding-bottom: 0 !important;
            font-size: 13px !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    rows = list_member_bets(email)
    if not rows:
        st.info("暫時沒有投注紀錄。")
        return

    rows = enrich_bet_rows_with_results(rows)
    render_profit_summary(rows)
    st.session_state.setdefault(f"{key_prefix}_member_bet_delete_mode", "自定勾選")
    sync_delete_selection(rows, key_prefix)

    selected_ids = [
        int(row["id"])
        for row in rows
        if st.session_state.get(f"{key_prefix}_select_bet_{row['id']}", False)
    ]

    with st.container(border=True):
        st.markdown(
            "<div style='font-size:13px;font-weight:700;color:#991b1b;margin-bottom:4px;'>刪除投注紀錄</div>",
            unsafe_allow_html=True,
        )
        delete_mode = st.radio(
            "刪除模式",
            ["自定勾選", "全部勾選", "取消"],
            horizontal=True,
            key=f"{key_prefix}_member_bet_delete_mode",
            label_visibility="collapsed",
        )
        st.markdown('<div class="delete-zone">', unsafe_allow_html=True)
        delete_cols = st.columns([0.65, 4.8], vertical_alignment="center")
        if delete_cols[0].button(
            "刪除",
            key=f"{key_prefix}_delete_member_bets",
            disabled=(
                delete_mode == "取消"
                or (delete_mode == "自定勾選" and not selected_ids)
            ),
        ):
            if delete_mode == "全部勾選":
                delete_all_member_bets(email)
                st.warning("已刪除全部投注紀錄。")
            else:
                for bet_id in selected_ids:
                    delete_member_bet(email, bet_id)
                st.warning(f"已刪除 {len(selected_ids)} 筆投注紀錄。")
            st.rerun()
        if delete_mode == "自定勾選":
            delete_cols[1].caption(f"已勾選 {len(selected_ids)} 筆")
        elif delete_mode == "全部勾選":
            delete_cols[1].caption("將刪除全部投注紀錄")
        else:
            delete_cols[1].caption("已取消全部勾選")
        st.markdown("</div>", unsafe_allow_html=True)

    lotto_results = load_lotto_results()
    for row in rows:
        numbers = json.loads(row.get("numbers") or "[]")
        bankers = json.loads(row.get("bankers") or "[]")
        legs = json.loads(row.get("legs") or "[]")
        display_numbers = [int(num) for num in (bankers + legs if bankers or legs else numbers)]
        draw_result = lotto_results.get(row.get("bet_date", ""))
        hit_score, prize_name, highlight = calculate_hit_summary(display_numbers, draw_result)

        with st.container(border=True):
            st.markdown('<div class="bet-card">', unsafe_allow_html=True)
            st.markdown(
                f"""
                <div class="bet-card-title">{row.get('bet_type', '')} | {row.get('bet_source', '')}</div>
                <div class="bet-card-date">投注開獎日期：{format_date_with_weekday_short(row.get('bet_date', ''))}</div>
                """,
                unsafe_allow_html=True,
            )

            render_ball_images(display_numbers, highlight=highlight)
            payout = int(row.get("payout") or 0)
            result_status = str(row.get("result_status") or "")
            status_html = (
                f'<span class="bet-status-unopened">{result_status}</span>'
                if result_status == "未開獎"
                else result_status
            )
            payout_text = "0" if result_status == "未開獎" else f"{payout:,}"
            st.markdown(
                f"""
                <div class="bet-record-meta">
                    金額$：{int(row.get('total_cost') or 0):,}｜狀態：{status_html}
                </div>
                <div class="bet-record-result">
                    中：{format_hit_score(hit_score)} 球｜獎項：{prize_name}｜派彩：{payout_text}
                </div>
                <div class="bet-record-mood">{format_result_mood(hit_score)}</div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown('<div class="delete-actions-row delete-zone">', unsafe_allow_html=True)
            st.checkbox(
                "勾選刪除",
                key=f"{key_prefix}_select_bet_{row['id']}",
            )
            st.markdown("</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

    with st.expander("表格檢視"):
        st.dataframe(normalize_bet_rows(rows), hide_index=True, width="stretch")


def render_admin_member_data_tab() -> None:
    """管理員修改或刪除會員資料。"""

    st.subheader("D. 管理員會員資料")
    members = get_all_members()
    current_admin_email = st.session_state.get("login_email_val", "")

    if not members:
        st.info("目前沒有會員資料。")
        return

    for member_id, email, phone, is_admin, created_at in members:
        with st.container(border=True):
            cols = st.columns([2.5, 1.3, 1.1, 0.8, 0.8])
            full_member = get_member(email)
            nickname = ""
            if full_member and len(full_member) > 6:
                nickname = str(full_member[6] or "").strip()
            cols[0].markdown(f"**{nickname or '未填暱稱'}**")
            cols[1].write(phone)
            cols[2].write("管理員" if is_admin else "普通會員")
            cols[3].caption(created_at or "-")

            if email == current_admin_email:
                cols[4].caption("目前帳號")
            elif cols[4].button("刪除", key=f"admin_delete_member_{member_id}"):
                delete_member(member_id)
                st.warning("已刪除會員資料。")
                st.rerun()

            if email != current_admin_email and st.button("修改", key=f"admin_edit_member_{member_id}"):
                st.session_state[f"admin_editing_member_{member_id}"] = True

            if st.session_state.get(f"admin_editing_member_{member_id}"):
                new_phone = st.text_input(
                    "新電話號碼（8 位數字，不用地區號）",
                    value=phone,
                    key=f"admin_phone_{member_id}",
                )
                new_nickname = st.text_input(
                    "會員暱稱（可不填）",
                    value=nickname,
                    key=f"admin_nickname_{member_id}",
                )
                save_cols = st.columns(2)
                if save_cols[0].button("確認修改", key=f"admin_save_member_{member_id}"):
                    new_phone = str(new_phone or "").strip()
                    if not is_valid_local_phone(new_phone):
                        st.error("手機號碼請輸入 8 位數字，不需要地區號。")
                    else:
                        update_member_simple(member_id, new_phone, new_nickname)
                        st.success("會員資料已更新。")
                        st.session_state.pop(f"admin_editing_member_{member_id}", None)
                        st.rerun()
                if save_cols[1].button("取消", key=f"admin_cancel_member_{member_id}"):
                    st.session_state.pop(f"admin_editing_member_{member_id}", None)
                    st.rerun()


def render_admin_member_bets_tab() -> None:
    """管理員查看及刪除指定會員投注紀錄。"""

    st.subheader("E. 管理員會員投注紀錄")
    members = get_all_members()
    member_emails = [email for _, email, _, _, _ in members]

    if not member_emails:
        st.info("目前沒有會員資料。")
        return

    selected_email = st.selectbox(
        "選擇會員",
        member_emails,
        key="admin_selected_member_bet_email",
    )
    if not selected_email:
        st.info("請先選擇會員。")
        return
    selected_email = str(selected_email)
    render_bet_records_tab(selected_email, key_prefix="admin")


def main() -> None:
    st.markdown(white_black_style, unsafe_allow_html=True)
    email = require_login()
    if not email:
        return

    st.header("會員投注中心")
    st.markdown(
        """
        <style>
        div[data-testid="stTabs"] div[role="tablist"] {
            gap: 2px !important;
        }
        div[data-testid="stTabs"] button[role="tab"] {
            background: #dbeafe !important;
            color: #1e3a8a !important;
            border-radius: 8px 8px 0 0 !important;
            border: 1px solid #bfdbfe !important;
            font-weight: 800 !important;
            margin-right: 0 !important;
            padding: 4px 7px !important;
            min-width: auto !important;
        }
        div[data-testid="stTabs"] button[role="tab"] p {
            font-size: 13px !important;
            white-space: nowrap !important;
        }
        div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
            background: #93c5fd !important;
            color: #0f172a !important;
            border-color: #60a5fa !important;
        }
        div[data-testid="stTabs"] button[role="tab"]:hover {
            background: #bfdbfe !important;
            color: #1e3a8a !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    tabs = st.tabs(["自選號碼投注", "投注紀錄"])
    with tabs[0]:
        render_custom_bet_tab(email)
    with tabs[1]:
        render_bet_records_tab(email, key_prefix="member")


if __name__ == "__main__":
    main()
