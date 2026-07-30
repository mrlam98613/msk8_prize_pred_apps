import calendar
import csv
import datetime
import html
from pathlib import Path

import streamlit as st

TIAN_GAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]


def render_lucky_day_table(rows):
    headers = ["日期", "星期", "六合彩狀態", "提示"]
    col_classes = {
        "日期": "date",
        "星期": "weekday",
        "六合彩狀態": "status",
        "提示": "remark",
    }

    table_rows = []
    for row in rows:
        cells = []
        for header in headers:
            value = html.escape(str(row.get(header, "")))
            cells.append(f"<td class='{col_classes[header]}'>{value}</td>")
        table_rows.append("<tr>" + "".join(cells) + "</tr>")

    header_html = "".join(
        f"<th class='{col_classes[header]}'>{html.escape(header)}</th>"
        for header in headers
    )

    st.markdown(
        f"""
        <style>
        .lucky-table-wrap {{
            width: 100%;
            max-width: 420px;
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
            margin-top: 0.65rem;
            border: 1px solid rgba(49, 51, 63, 0.18);
            border-radius: 8px;
        }}
        .lucky-day-table {{
            width: 640px;
            border-collapse: collapse;
            table-layout: fixed;
            font-size: 12px;
            line-height: 1.35;
            background: #ffffff;
        }}
        .lucky-day-table th,
        .lucky-day-table td {{
            padding: 7px 6px;
            border-bottom: 1px solid rgba(49, 51, 63, 0.12);
            border-right: 1px solid rgba(49, 51, 63, 0.08);
            vertical-align: top;
            color: #262730;
            word-break: keep-all;
        }}
        .lucky-day-table th {{
            position: sticky;
            top: 0;
            z-index: 1;
            background: #f4f6f8;
            font-weight: 800;
            text-align: left;
            white-space: nowrap;
        }}
        .lucky-day-table tr:last-child td {{
            border-bottom: 0;
        }}
        .lucky-day-table .date {{ width: 82px; white-space: nowrap; }}
        .lucky-day-table .weekday {{ width: 44px; text-align: center; white-space: nowrap; }}
        .lucky-day-table .status {{ width: 92px; }}
        .lucky-day-table .remark {{
            width: 374px;
            word-break: break-word;
        }}
        @media (max-width: 430px) {{
            .lucky-table-wrap {{
                max-width: calc(100vw - 1.5rem);
            }}
            .lucky-day-table {{
                width: 620px;
                font-size: 11px;
            }}
            .lucky-day-table th,
            .lucky-day-table td {{
                padding: 6px 5px;
            }}
            .lucky-day-table .date {{ width: 78px; }}
            .lucky-day-table .weekday {{ width: 40px; }}
            .lucky-day-table .status {{ width: 88px; }}
            .lucky-day-table .remark {{ width: 354px; }}
        }}
        </style>
        <div class="lucky-table-wrap">
            <table class="lucky-day-table">
                <thead><tr>{header_html}</tr></thead>
                <tbody>{''.join(table_rows)}</tbody>
            </table>
        </div>
        """,
        unsafe_allow_html=True,
    )


def get_lottery_dates_from_csv(months_ahead=1):
    lottery_dates = set()
    dir_path = Path(__file__).resolve().parent.parent
    csv_path = dir_path / "A_msk_lottery_data_folder" / "M7_lotto_open_days.csv"

    if not csv_path.exists():
        return None, csv_path

    today = datetime.date.today()
    start_date = datetime.date(today.year, today.month, 1)
    if months_ahead < 0:
        months_ahead = 0

    month_index = (today.year * 12 + today.month - 1) + months_ahead
    year = month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    end_date = datetime.date(year, month, last_day)

    with open(csv_path, "r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            date_str = (row.get("開獎日期 (Date)") or "").strip()
            if not date_str:
                continue
            try:
                parsed_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                continue
            if start_date <= parsed_date <= end_date:
                lottery_dates.add(date_str)

    return lottery_dates, csv_path


def get_day_tian_gan(target_date):
    base_date = datetime.date(2026, 1, 1)
    base_tg_idx = 1
    delta_days = (target_date - base_date).days
    tg_idx = (base_tg_idx + delta_days) % 10
    return TIAN_GAN[tg_idx]


def get_fortune_gan(biaz_tg):
    tg_yang = {"甲":True, "丙":True, "戊":True, "庚":True, "壬":True, "乙":False, "丁":False, "己":False, "辛":False, "癸":False}
    tg_wuxing = {"甲":"木", "乙":"木", "丙":"火", "丁":"火", "戊":"土", "己":"土", "庚":"金", "辛":"金", "壬":"水", "癸":"水"}
    ke_relation = {"木":"土", "火":"金", "土":"水", "金":"木", "水":"火"}

    my_wuxing = tg_wuxing[biaz_tg]
    my_yang = tg_yang[biaz_tg]
    target_wuxing = ke_relation[my_wuxing]

    zheng_cai, pian_cai = "", ""
    for tg in TIAN_GAN:
        if tg_wuxing[tg] == target_wuxing:
            if tg_yang[tg] != my_yang:
                zheng_cai = tg
            else:
                pian_cai = tg
    return zheng_cai, pian_cai


def main():
    st.title("六合彩幸運日分析")
    st.markdown(
        """
        本頁將從本地 M7 開獎日 CSV 讀取資料，並依據你的生日推算八字財星，找出正財 / 偏財日與開獎日交集。
        """
    )

    with st.sidebar.expander("說明", expanded=True):
        st.write(
            "建議先執行 A4_mark_six_open_days.py 產生 M7_lotto_open_days.csv，再使用此頁面分析。"
        )
        st.write("目前僅顯示本月與下月的開獎日。")

    lottery_dates, csv_path = get_lottery_dates_from_csv(months_ahead=1)
    if lottery_dates is None:
        st.warning(
            f"找不到 M7 開獎日期檔案：{csv_path}\n請先執行 A4_mark_six_open_days.py 產生檔案。"
        )
        return

    st.success(f"已從 {csv_path.name} 讀取 {len(lottery_dates)} 個開獎日。")

    col1, col2, col3 = st.columns(3)
    with col1:
        birth_year = st.number_input(
            "出生年份 1950",
            min_value=1950,
            max_value=2100,
            value=1950,
            step=1,
            key="lucky_birth_year",
        )
    with col2:
        birth_month = st.number_input(
            "出生月份 1-12",
            min_value=1,
            max_value=12,
            value=1,
            step=1,
            key="lucky_birth_month",
        )
    with col3:
        birth_day = st.number_input(
            "出生日 1-31",
            min_value=1,
            max_value=31,
            value=1,
            step=1,
            key="lucky_birth_day",
        )

    analyse = st.button("開始分析", key="lucky_start_analysis")
    if not analyse:
        return

    try:
        birth_date = datetime.date(birth_year, birth_month, birth_day)
    except ValueError:
        st.error("輸入的日期不正確，請重新檢查年、月、日。")
        return

    user_tg = get_day_tian_gan(birth_date)
    zheng_tg, pian_tg = get_fortune_gan(user_tg)
    st.write(f"**日主天干**：{user_tg}，**正財**：{zheng_tg}，**偏財**：{pian_tg}")

    today = datetime.date.today()
    start_date = datetime.date(today.year, today.month, 1)
    if today.month >= 11:
        end_date = datetime.date(today.year + 1, (today.month + 2) % 12, 1) - datetime.timedelta(days=1)
    else:
        end_date = datetime.date(today.year, today.month + 2, 1) - datetime.timedelta(days=1)

    st.write(f"篩選日期範圍：{start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}")

    rows = []
    current_date = start_date
    while current_date <= end_date:
        tg = get_day_tian_gan(current_date)
        weekday = current_date.isoweekday()
        date_str = current_date.strftime("%Y-%m-%d")

        fortune_type = ""
        if tg == zheng_tg:
            fortune_type = f"正財日 ({zheng_tg})"
        elif tg == pian_tg:
            fortune_type = f"偏財日 ({pian_tg})"

        if fortune_type:
            is_lottery_day = date_str in lottery_dates
            weekday_str = f"週{['一','二','三','四','五','六','日'][weekday-1]}"
            lottery_str = "🎉 馬會開獎日" if is_lottery_day else "無開獎"
            remark = ""
            if fortune_type and is_lottery_day:
                if "偏財" in fortune_type:
                    remark = "🔥 偏財碰上開獎日，偏財運極強！"
                else:
                    remark = "💰 正財碰上開獎日，正財臨門！"
            else:
                remark = "財氣聚集，適合處理常規財務、投資或研究下期號碼"

            rows.append(
                {
                    "日期": date_str,
                    "星期": weekday_str,
                    "日天干": tg,
                    "財星類型": fortune_type,
                    "六合彩狀態": lottery_str,
                    "提示": remark,
                }
            )

        current_date += datetime.timedelta(days=1)

    if rows:
        render_lucky_day_table(rows)
    else:
        st.info("算出來的日期範圍內沒有符合正財或偏財條件的日子。")


if __name__ == "__main__":
    main()
