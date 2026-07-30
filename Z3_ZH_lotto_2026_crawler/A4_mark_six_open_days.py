import csv
import datetime as dt
import json
import shutil
from pathlib import Path
from urllib import error, request

PROJECT_DIR = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_DIR.parent
DATA_DIR = PROJECT_DIR / "Lotto_Data_Folder"
M7_CSV = DATA_DIR / "M7_lotto_open_days.csv"

# 馬會官方六合彩攪珠頁面
URL = "https://bet.hkjc.com/ch/marksix/fixtures"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-HK,zh-TW;q=0.9,en-US;q=0.8,en;q=0.7",
}

CSV_FILE_NAME = M7_CSV
# 常規六合彩開獎日：週二、週四、週六、週日
DRAW_WEEKDAYS = {2, 4, 6, 7}


def _next_month(year: int, month: int) -> tuple[int, int]:
    if month == 12:
        return year + 1, 1
    return year, month + 1


def _read_existing_dates_from_csv() -> set[str]:
    if not M7_CSV.exists():
        return set()

    existing_dates: set[str] = set()
    with open(M7_CSV, mode="r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            date_value = (row.get("開獎日期 (Date)") or "").strip()
            if date_value:
                existing_dates.add(date_value)
    return existing_dates


def _has_current_and_next_month_dates(existing_dates: set[str]) -> bool:
    today = dt.date.today()
    months_to_cover = [(today.year, today.month), _next_month(today.year, today.month)]

    for year, month in months_to_cover:
        month_prefix = f"{year}-{month:02d}-"
        if not any(date_value.startswith(month_prefix) for date_value in existing_dates):
            return False
    return True


def _copy_m7_to_webapp_folder() -> None:
    webapp_dir = PROJECT_DIR.parent / "A_msk_lottery_data_folder"
    webapp_dir.mkdir(parents=True, exist_ok=True)

    if not M7_CSV.exists():
        print(f"⚠️ 找不到 {M7_CSV}，無法同步到網站資料夾。")
        return

    destination = webapp_dir / M7_CSV.name
    shutil.copy2(M7_CSV, destination)
    print(f"📦 已將 {M7_CSV.name} 同步到網站資料夾：{destination}")


def _collect_draw_dates_for_target_months() -> list[dict[str, str]]:
    today = dt.date.today()
    months_to_cover = [(today.year, today.month), _next_month(today.year, today.month)]
    rows: list[dict[str, str]] = []

    for year, month in months_to_cover:
        if month == 13:
            year += 1
            month = 1
        last_day = dt.date(year, month + 1, 1) - dt.timedelta(days=1) if month < 12 else dt.date(year + 1, 1, 1) - dt.timedelta(days=1)

        for current_day in range(1, last_day.day + 1):
            draw_date = dt.date(year, month, current_day)
            if draw_date.isoweekday() in DRAW_WEEKDAYS:
                rows.append({"開獎日期 (Date)": draw_date.strftime("%Y-%m-%d")})

    return rows


def _try_fetch_official_fixtures() -> list[dict[str, str]] | None:
    print("🌐 正在連線至香港賽馬會官方網站下載開獎數據...")
    try:
        req = request.Request(URL, headers=HEADERS)
        with request.urlopen(req, timeout=12) as response:
            status_code = response.getcode()
            if status_code != 200:
                print(f"⚠️ 馬會網站回應 {status_code}，改用內建後備排程。")
                return None

            text = response.read().decode("utf-8", errors="ignore")
            if "fixtures" not in text.lower():
                print("⚠️ 馬會網站沒有提供可解析的排期資料，改用內建後備排程。")
                return None

            # 這個入口目前不穩定，若回傳非 JSON 或沒有可用欄位，就退回後備排程。
            try:
                payload = json.loads(text)
            except ValueError:
                print("⚠️ 馬會網站回傳格式非 JSON，改用內建後備排程。")
                return None

            fixtures = payload.get("fixtures") or []
        if not fixtures:
            print("⚠️ 未能在馬會數據中找到任何開獎排期日程，改用內建後備排程。")
            return None

        converted: list[dict[str, str]] = []
        for fixture in fixtures:
            raw_date = fixture.get("drawDate", "")
            draw_date = raw_date.replace("/", "-") if raw_date else "N/A"
            if draw_date != "N/A":
                converted.append({"開獎日期 (Date)": draw_date})
        return converted
    except error.URLError as exc:
        print(f"⚠️ 網路連線異常: {exc}，改用內建後備排程。")
        return None
    except Exception as exc:  # pragma: no cover - defensive
        print(f"⚠️ 解析失敗: {exc}，改用內建後備排程。")
        return None


def download_fixtures_to_csv() -> None:
    existing_dates = _read_existing_dates_from_csv()
    if M7_CSV.exists() and _has_current_and_next_month_dates(existing_dates):
        print(f"ℹ️ 已檢查到 {M7_CSV} 中已有本月與下月開獎日，跳過下載。")
        _copy_m7_to_webapp_folder()
        return

    fixtures = _try_fetch_official_fixtures()
    if fixtures is None:
        fixtures = _collect_draw_dates_for_target_months()
        print("🧱 已切換為內建後備排程。")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(CSV_FILE_NAME, mode="w", encoding="utf-8-sig", newline="") as csv_file:
        fieldnames = ["開獎日期 (Date)"]
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()

        for fixture in fixtures:
            writer.writerow(fixture)

    _copy_m7_to_webapp_folder()
    print(f"\n🎉 處理完成！")
    print(f"✅ 已將 {len(fixtures)} 個開獎日程寫入至檔案：【{CSV_FILE_NAME}】")


if __name__ == "__main__":
    download_fixtures_to_csv()
