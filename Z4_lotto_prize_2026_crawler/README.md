# Z4 Lotto Prize 2026 Crawler



`Z4_lotto_prize_2026_crawler/A0_main.py` 是獨立的六合彩開獎紀錄下載程式，使用馬會官方資料產生所需 CSV。

資料來源：

- `https://info.cld.hkjc.com/graphql/base/`
- GraphQL query: `lotteryDraws`

輸出：

- `Z4_lotto_prize_2026_crawler/Lotto_Data_Folder/M1_Z4_lotto_data.csv`
- `Z4_lotto_prize_2026_crawler/Lotto_Data_Folder/M2_last_upgrade_lotto_data.csv`
- `Z4_lotto_prize_2026_crawler/Lotto_Data_Folder/M3_lotto_prize_results.csv`
- `Z4_lotto_prize_2026_crawler/Lotto_Data_Folder/M4_lotto_prize_summary.csv`
- `Z4_lotto_prize_2026_crawler/Lotto_Data_Folder/M6_lotto_history_prize.csv`
- `Z4_lotto_prize_2026_crawler/Lotto_Data_Folder/M7_lotto_open_days.csv`

並同步到：

- `A_msk_lottery_data_folder/M1_ZH_lotto_data.csv`
- `A_msk_lottery_data_folder/M2_last_upgrade_lotto_data.csv`
- `A_msk_lottery_data_folder/M3_lotto_prize_results.csv`
- `A_msk_lottery_data_folder/M4_lotto_prize_summary.csv`
- `A_msk_lottery_data_folder/M6_lotto_history_prize.csv`
- `A_msk_lottery_data_folder/M7_lotto_open_days.csv`

注意：

- Z4 使用馬會官方 GraphQL，已可取得 `lotteryPrizes.type / winningUnit / dividend`。
- `M6_lotto_history_prize.csv` 的 `prize1/prize2/prize3` 由 `winningUnit / unitBet` 計算，與原本資料格式一致。
- 下期開獎日期會優先使用馬會資料，找不到才用 Tue/Thu/Sat 規則推算。
