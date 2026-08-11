# Z4 六合彩資料下載說明

`A0_main.py` 是本專案的六合彩資料下載主程式，負責從香港賽馬會官方資料來源抓取最新開獎、派彩、下期開獎資料，建立網站及預測程式使用的 CSV。

## 資料來源

- 馬會六合彩首頁：
  `https://bet.hkjc.com/ch/marksix/home`
- 馬會六合彩結果頁：
  `https://bet.hkjc.com/ch/marksix/results`
- 官方 GraphQL API：
  `https://info.cld.hkjc.com/graphql/base/`
- 主要 GraphQL query：
  `lotteryDraws`

## 執行方式

在專案根目錄執行：

```bash
python3 Z4_lotto_prize_2026_crawler/A0_main.py
```

Zeabur / Docker 會由 `crontab.txt` 定時執行同一支程式。

## 下載及建立流程

`A0_main.py` 會依序完成：

1. 下載馬會開獎日資料，建立 `M7_lotto_open_days.csv`
2. 下載馬會最新開獎及派彩資料
3. 建立 `M1_Z4_lotto_data.csv`
4. 合併現有 M2 歷史資料，建立最新 `M2_last_upgrade_lotto_data.csv`
5. 建立網站首頁使用的 `M3_lotto_prize_results.csv`
6. 建立下期獎金摘要 `M4_lotto_prize_summary.csv`
7. 建立派彩歷史 `M6_lotto_history_prize.csv`
8. 同步 M2/M3/M4/M6/M7 到 `A_msk_lottery_data_folder`

## CSV 功能說明

### M1_Z4_lotto_data.csv

位置：

```text
Z4_lotto_prize_2026_crawler/Lotto_Data_Folder/M1_Z4_lotto_data.csv
```

用途：

- 馬會 GraphQL 最新批次開獎資料暫存檔
- 不是完整歷史資料
- 用來和現有 M2 合併，更新完整歷史開獎檔

欄位：

```text
ndate,N1,N2,N3,N4,N5,N6,N7
```

### M2_last_upgrade_lotto_data.csv

位置：

```text
Z4_lotto_prize_2026_crawler/Lotto_Data_Folder/M2_last_upgrade_lotto_data.csv
```

用途：

- 完整開獎歷史主檔
- 由現有 M2 歷史資料 + M1 最新批次合併而成
- 多數預測程式會讀取這個檔案

欄位：

```text
ndate,N1,N2,N3,N4,N5,N6,N7
```

### M3_lotto_prize_results.csv

位置：

```text
Z4_lotto_prize_2026_crawler/Lotto_Data_Folder/M3_lotto_prize_results.csv
```

用途：

- 網站首頁顯示最新一期開獎資料
- 顯示最新一期獎項、獎金、中獎注數
- 顯示下一期開獎日期、多寶 / 金多寶、估計頭獎基金

網站頁面：

```text
app_pages/0_lotto_info.py
```

### M4_lotto_prize_summary.csv

位置：

```text
Z4_lotto_prize_2026_crawler/Lotto_Data_Folder/M4_lotto_prize_summary.csv
```

用途：

- 下期開獎摘要
- 儲存最新開獎日期、下一期日期、星期、估計頭獎基金
- 預測及投注程式會讀取這個檔案

### M6_lotto_history_prize.csv

位置：

```text
Z4_lotto_prize_2026_crawler/Lotto_Data_Folder/M6_lotto_history_prize.csv
```

用途：

- 派彩歷史紀錄
- 儲存每期 N1-N6、N7、1/2/3 獎注數、每注獎金
- 派彩特色分析及網站派彩紀錄頁會讀取這個檔案

網站頁面：

```text
app_pages/2_lotto_prize_results.py
```

欄位：

```text
nDdate,N1,N2,N3,N4,N5,N6,N7,prize1,prize2,prize3,prize1_unit,prize2_unit,prize3_unit
```

### M7_lotto_open_days.csv

位置：

```text
Z4_lotto_prize_2026_crawler/Lotto_Data_Folder/M7_lotto_open_days.csv
```

用途：

- 馬會公布的開獎日
- 一般為星期二、四、六
- 若有特別開獎日，以馬會公布日期為準

## 輸出位置

Z4 內部輸出：

```text
Z4_lotto_prize_2026_crawler/Lotto_Data_Folder/
```

網站讀取位置：

```text
A_msk_lottery_data_folder/
```

成功執行後會同步：

```text
A_msk_lottery_data_folder/M2_last_upgrade_lotto_data.csv
A_msk_lottery_data_folder/M3_lotto_prize_results.csv
A_msk_lottery_data_folder/M4_lotto_prize_summary.csv
A_msk_lottery_data_folder/M6_lotto_history_prize.csv
A_msk_lottery_data_folder/M7_lotto_open_days.csv
```

## 成功 Log 範例

```text
✅ 2026-08-12 04:21:15 Z4 下載完成。
/> 最新一期：2026-08-11
/> 下期開獎日期：2026-08-13
/> 下期期號：26/088
/> 已同步 M2/M3/M4/M6/M7 到 A_msk_lottery_data_folder。
```

意思：

- 最新一期開獎資料已更新到 `2026-08-11`
- 下一期開獎日期為 `2026-08-13`
- 下一期期號為 `26/088`
- 所有網站需要的 CSV 已同步到 `A_msk_lottery_data_folder`

## Log 位置

```text
Z4_lotto_prize_2026_crawler/log/lotto_download_log.txt
```

目前 log 只保留最新一次下載紀錄，不追加舊紀錄。

## 注意事項

- `M1_Z4_lotto_data.csv` 只是最新批次暫存，不是完整歷史。
- `M1_Z4_lotto_data.csv` 只保留在 Z4 內部資料夾，不同步到網站資料夾。
- `M2_last_upgrade_lotto_data.csv` 是完整開獎歷史主檔。
- `M3_lotto_prize_results.csv` 影響網站首頁最新開獎顯示。
- `M6_lotto_history_prize.csv` 影響網站派彩特色紀錄頁。
- Streamlit 網站頁面有 cache，讀取 M3/M6 時需使用檔案修改時間作 cache key，避免 Zeabur 長駐服務顯示舊資料。
