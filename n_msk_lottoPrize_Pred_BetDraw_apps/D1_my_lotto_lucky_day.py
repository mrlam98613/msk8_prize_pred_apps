import calendar
import csv
import datetime
from pathlib import Path

TIAN_GAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]


def get_lottery_dates_from_csv(months_ahead=1):
    """讀取 M7 CSV 中、指定月份區間內的開獎日期。"""
    lottery_dates = set()
    dir_path = Path(__file__).resolve().parent
    csv_path = dir_path.parent / "A_msk_lottery_data_folder" / "M7_lotto_open_days.csv"

    print(f"📄 正在讀取開獎日期檔案：{csv_path}")

    if not csv_path.exists():
        print("⚠️ 找不到 M7 CSV，請先執行 A4_mark_six_open_days.py 產生檔案。")
        return lottery_dates

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

    print(f"✅ 已從 M7 CSV 讀取 {len(lottery_dates)} 個開獎日（{start_date.strftime('%Y-%m')} 至 {end_date.strftime('%Y-%m')}）。")
    return lottery_dates

def get_day_tian_gan(target_date):
    """計算任意公曆日期的日天干 (以 2026-01-01 乙卯日為基準)"""
    base_date = datetime.date(2026, 1, 1)
    base_tg_idx = 1  # 乙
    delta_days = (target_date - base_date).days
    tg_idx = (base_tg_idx + delta_days) % 10
    return TIAN_GAN[tg_idx]

def get_fortune_gan(biaz_tg):
    """根據生日天干，自動推算正財、偏財天干"""
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
    print("=" * 80)
    print(" 🔮 本地 CSV 版：香港六合彩開獎日 × 個人八字財星【強烈提示器】 🔮")
    print("=" * 80)
    
    # 1. 從 M7 CSV 讀取「本月至 N 月」的開獎日期
    live_lottery_dates = get_lottery_dates_from_csv(months_ahead=1)
    
    # 2. 輸入生日
    try:
        birth_year = int(input("\n請輸入出生年份 (如 1952): "))
        birth_month = int(input("請輸入出生月份 (如 2): "))
        birth_day = int(input("請輸入出生日期 (如 21): "))
        birth_date = datetime.date(birth_year, birth_month, birth_day)
    except ValueError:
        print("❌ 輸入錯誤，請務必輸入數字。")
        return

    user_tg = get_day_tian_gan(birth_date)
    zheng_tg, pian_tg = get_fortune_gan(user_tg)
    
    print(f"\n[分析結果] 您的日主天干為:【{user_tg}】 | 正財:【{zheng_tg}】 | 偏財:【{pian_tg}】")
    
    # 3. 設定查詢範圍 (自動抓取電腦目前的「這個月」和「下個月」)
    today = datetime.date.today()
    start_date = datetime.date(today.year, today.month, 1)
    if today.month >= 11:
        end_date = datetime.date(today.year + 1, (today.month + 2) % 12, 1) - datetime.timedelta(days=1)
    else:
        end_date = datetime.date(today.year, today.month + 2, 1) - datetime.timedelta(days=1)

    print(f"📊 正在篩選 {start_date.strftime('%Y-%m')} 至 {end_date.strftime('%Y-%m')} 的財運交集日...")
    print("-" * 110)
    print(f"{'日期':<12} | {'星期':<5} | {'日天干':<4} | {'財星類型':<12} | {'六合彩狀態':<10}")
    print("-" * 110)

    current_date = start_date
    while current_date <= end_date:
        tg = get_day_tian_gan(current_date)
        weekday = current_date.isoweekday()
        date_str = current_date.strftime("%Y-%m-%d")
        
        # 判斷是否為財日
        fortune_type = ""
        if tg == zheng_tg:
            fortune_type = f"正財日 ({zheng_tg})"
        elif tg == pian_tg:
            fortune_type = f"偏財日 ({pian_tg})"
            
        # 判斷是否為六合彩開獎日
        if live_lottery_dates:
            is_lottery_day = date_str in live_lottery_dates
        else:
            is_lottery_day = False
        
        #建立提示訊息
        hint_msg = ""
        if fortune_type and is_lottery_day:
            if "偏財" in fortune_type:
                hint_msg = "🔥【偏財碰上開獎日】偏財運極強！極其適合小試身手 🚀🚀🚀"
            else:
                hint_msg = "💰【正財碰上開獎日】正財臨門！適合合資或以理性穩健方式購買 🧧"
        elif fortune_type:
            hint_msg = "財氣聚集，適合處理常規財務、投資或研究下期號碼"

        # 輸出結果
        if fortune_type:
            weekday_str = f"週{['一','二','三','四','五','六','日'][weekday-1]}"
            lottery_str = "🎉 馬會開獎日" if is_lottery_day else "無開獎"
            print(f"{date_str} | {weekday_str:<5} | {tg:<5} | {fortune_type:<14} | {lottery_str:<12}")
            
        current_date += datetime.timedelta(days=1)
    print("=" * 110)

if __name__ == "__main__":
    main()



