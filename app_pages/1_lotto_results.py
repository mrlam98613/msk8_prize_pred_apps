
import streamlit as st
import pandas as pd
from pathlib import Path
import base64
import csv

@st.cache_data(show_spinner=False)
def img_to_base64(path):
    with open(Path(path), "rb") as f:
        return base64.b64encode(f.read()).decode()

next_draw_date = ""  # 確保 next_draw_date 變數在所有 if 判斷前都已正確定義

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PRIZE_RESULTS_PATH = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M3_lotto_prize_results.csv"
LOTTO_RESULTS_PATH = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M2_last_upgrade_lotto_data.csv"
BALLS_DIR = PROJECT_ROOT / "A_msk_balls_png"



def main():
    # 加入自訂 CSS，縮小行距與分隔線間距
    st.markdown("""
        <style>
        .stMarkdown p, .stMarkdown h6, .stMarkdown h7 {
            margin-bottom: 8px !important;
            margin-top: 8px !important;
        }
        hr {
            margin-top: 18px !important;
            margin-bottom: 18px !important;
            border-top: 2.5px solid #e0e0e0 !important;
        }
        .section-title {
            margin-top: 32px !important;
            margin-bottom: 12px !important;
        }
        </style>
    """, unsafe_allow_html=True)
    
    
    # ===== 讀取最新一期開獎與派彩資料 =====
    
    import datetime
    import calendar
    import io
    def get_weekday(date_str):
        # 支援 2026年05月12日 這種格式
        try:
            d = datetime.datetime.strptime(date_str, "%Y年%m月%d日")
            return "一二三四五六日"[d.weekday()]
        except:
            return ""
    
    with open(PRIZE_RESULTS_PATH, encoding="utf-8-sig") as f:
        lines = [line.strip() for line in f if line.strip()]
    
    # 最新一期
    latest_date = ""
    latest_numbers = []
    prize_csv_lines = []
    prize_section = False
    for i, line in enumerate(lines):
        if line.startswith("日期,"):
            latest_date = line.split(",",1)[1]
        if line.startswith("號碼,"):
            latest_numbers = [int(x) for x in line.split(",",1)[1].replace('"','').split(",")]
        if line.startswith("獎項,"):
            prize_section = True
            prize_csv_lines.append(line)
            continue
        if prize_section:
            if line.startswith("🟢"):
                break
            prize_csv_lines.append(line)
    
    
    # 用 csv.reader 解析派彩表格
    prize_rows = []
    if prize_csv_lines:
        reader = csv.reader(io.StringIO("\n".join(prize_csv_lines)))
        header = next(reader, None)
        for row in reader:
            if row and len(row) == 3:
                prize_rows.append(row)
    
    # ===== 顯示最新一期開獎與派彩資訊 =====
    st.markdown('<div style="margin-bottom:2px"><h7 style="font-size:1.2rem; font-weight:bold;display:inline-block;">開獎結果|派彩|下期開獎日期|查詢</h7></div>', unsafe_allow_html=True)
    if latest_date and latest_numbers:
        week = get_weekday(latest_date)
        st.markdown(f"<div class='section-title' style='font-size:1.2rem; font-weight:bold;'>🛎️ A. 最新一期開獎結果</div>", unsafe_allow_html=True)
        st.markdown(f"<div style='margin-bottom:8px'><span style='font-size:1.2rem; font-weight:bold;'>  日期：{latest_date} (星期{week}) </span></div>", unsafe_allow_html=True)
        balls_html = '<div style="display:flex;align-items:center;margin-bottom:2px;">'
        for n in latest_numbers[:6]:
            img_path = BALLS_DIR / f"{int(n)}.png"
            img_b64 = img_to_base64(img_path)
            balls_html += f"<img src='data:image/png;base64,{img_b64}' alt='{int(n)}' style='width:32px;height:32px;margin-right:3px;'/>"
        balls_html += "<span style='font-weight:bold; font-size:1.2em; margin:0 4px;'>+</span>"
        img_path = BALLS_DIR / f"{int(latest_numbers[6])}.png"
        img_b64 = img_to_base64(img_path)
        balls_html += f"<img src='data:image/png;base64,{img_b64}' alt='{int(latest_numbers[6])}' style='width:32px;height:32px;margin-right:3px;'/>"
        balls_html += '</div>'
        st.markdown(balls_html, unsafe_allow_html=True)
        st.markdown("<hr>", unsafe_allow_html=True)
    
    # 讀取下期開獎日期
    for line in lines:
        if line.startswith("開獎日期,"):
            next_draw_date = line.split(",",1)[1]
            break
        
    # 下期開獎日期顯示在最新一期開獎日期下方
    if next_draw_date:
        week = get_weekday(next_draw_date)
        st.markdown(f"<div class='section-title' style='font-size:1.1rem;'> ⏰ B. 下期開獎：</div>", unsafe_allow_html=True)
        st.markdown(f"<div style='margin-bottom:8px'><span style='font-size:1.1rem;'> 🟧 日期：{next_draw_date} </span></div>", unsafe_allow_html=True)
        st.markdown("<hr>", unsafe_allow_html=True)
    
    # 派彩結果表格
    if prize_rows:
        table_rows = []
        for r in prize_rows:
            table_rows.append(f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td></tr>")
        table_html = "\n".join(table_rows)
        st.markdown(f'''
        <div class='section-title' style="font-size:1.1rem;"><b>💰 C. 最新一期派彩結果</b></div>
        <table style="width:100%;font-size:1em;margin-bottom:8px;">
            <tr><th>獎項</th><th>獎金</th><th>中獎注數</th></tr>
            {table_html}
        </table>
        <hr>
        ''', unsafe_allow_html=True)
        
    
    # 開獎, 派彩, 期開獎日期，資訊在，PRIZE_RESULTS_PATH = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M3_lotto_prize_results.csv"
    # 用卡片顯示
    # 1，最新一期開獎，yyyy-mm-dd / 星期幾。
    #    球圖1，球圖2，球圖3，球圖4，球圖5，球圖6 ＋ 球圖7
    # 
    # 2，派彩結果
    # 獎項,獎金,中獎注數
    # 頭獎,"$30,646,080","0.5注中獎, 每注各分 $15,323,040"
    # 二獎,"$2,581,485","1.5注中獎, 每注各分 $1,720,990"
    # 三獎,"$6,883,605","85.5注中獎, 每注各分 $80,510"
    # 四獎,"$1,944,000","202.5注中獎, 每注各分 $9,600"
    # 五獎,"$3,131,200","4,892.5注中獎, 每注各分 $640"
    # 六獎,"$1,830,400","5,720注中獎, 每注各分 $320"
    # 七獎,"$3,785,332","94,633.3注中獎, 每注各分 $40"
    # --------
    # 3，下期開獎日期 yyyy-mm-dd / 星期幾
    
    # 請加入以上功能在頂位置。
    
    
    df = pd.read_csv(LOTTO_RESULTS_PATH, encoding="utf-8-sig")
    # 讓用戶選擇顯示期數（20 或 50 期）
    period_options = [20, 50] if len(df) >= 50 else [20]
    num_periods = st.selectbox(
        "顯示最近幾期",
        period_options,
        index=0,
        format_func=lambda x: f"{x} 期",
        key="lotto_results_num_periods",
    )
    
    df2 = df.iloc[-num_periods:, 0:8].copy()  # 取最後N筆資料的前8欄
    # 重新命名欄位，配合下方卡片顯示
    df2.columns = ["ndate", "N1", "N2", "N3", "N4", "N5", "N6", "N7"]
    df2 = df2[::-1].reset_index(drop=True)  # 由新到舊排序
    df2.insert(0, "期數", range(len(df), len(df)-len(df2), -1))
    
    # 顯示開獎紀錄 球圖顯示
    st.markdown('<div class="section-title" style="font-size:1.2rem; font-weight:bold;display:inline-block;"> ⏰ D. 過往開獎紀錄</div>', unsafe_allow_html=True)
    for i, (index, row_data) in enumerate(df2.iterrows()):
        st.markdown(f"<div style='margin-bottom:8px; margin-top:8px;'><b>[第{row_data['期數']}期] 開獎日期：{row_data['ndate']}</b></div>", unsafe_allow_html=True)
        balls_html = '<div style="display:flex;align-items:center;margin-bottom:2px;">'
        for n in [row_data['N1'], row_data['N2'], row_data['N3'], row_data['N4'], row_data['N5'], row_data['N6']]:
            img_path = BALLS_DIR / f"{int(n)}.png"
            img_b64 = img_to_base64(img_path)
            balls_html += f"<img src='data:image/png;base64,{img_b64}' alt='{int(n)}' style='width:32px;height:32px;margin-right:3px;'/>"
        balls_html += "<span style='font-weight:bold; font-size:1.2em; margin:0 4px;'>+</span>"
        img_path = BALLS_DIR / f"{int(row_data['N7'])}.png"
        img_b64 = img_to_base64(img_path)
        balls_html += f"<img src='data:image/png;base64,{img_b64}' alt='{int(row_data['N7'])}' style='width:32px;height:32px;margin-right:3px;'/>"
        balls_html += '</div>'
        st.markdown(balls_html, unsafe_allow_html=True)
        st.markdown("<hr>", unsafe_allow_html=True)
            
         
    #     # 注意：如果你在 div 內部需要 Streamlit 原生元件（如按鈕），
    #     # 建議改用 st.container(border=True) 搭配 CSS 修改其原本的 class.
    

if __name__ == "__main__":
    main()
