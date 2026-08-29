# MSK Prize Lotto Prediction Apps

本網站用於顯示六合彩開獎資料、下期投注預測、獎金特式分析及歷史投注統計。資料由 crawler 更新至 `A_msk_lottery_data_folder`，再由各個預測程式產生網站讀取用的 CSV。

## 主要功能

### 下期開獎及投注預測

網站會讀取最新一期開獎資料、下期開獎日期、下期頭獎基金，以及已產生的預測投注號碼。一般下期投注預測由 `msk_new_seed_apps/A1_seedBet_main.py` 產生。

### 生日號分組投注預測

`app_pages/1_A1_v2_12_6_3_pred.py` 主要顯示由以下程式產生的生日號分組預測結果：

```text
n_v1_msk_prize_31_num_backtest_pred/A1_v2_brithday_group_quota_pred.py
```

A1_v2 策略會以 1-9、10-20、21-31 三個分組，按 12 / 6 / 2 期近期趨勢、prize3 人氣及特號輔助分產生下期投注參考。

目錄分工：

```text
n_v1_msk_prize_31_num_backtest_pred/
  A1 系列：生日號分組趨勢、回測投注及下期預測
  bet_prize_data/：網站讀取的投注與核對 CSV

n_v2_msk_prize_31_num_backtest_pred/
  A0 系列：組合分析、權重回測及研究記錄
  comb_data/、json_data/：A0 分析輸出資料
```

網站頁面會讀取：

```text
n_v1_msk_prize_31_num_backtest_pred/bet_prize_data/nextBetDraw_record.csv
n_v1_msk_prize_31_num_backtest_pred/bet_prize_data/bet_records.csv
n_v1_msk_prize_31_num_backtest_pred/bet_prize_data/win_results.csv
```

其中 `nextBetDraw_record.csv` 只保留目前最新下期預測投注，`bet_records.csv` 記錄歷史及最新投注，`win_results.csv` 記錄回測核對結果。

### 歷史投注及中獎統計

網站會依歷史投注紀錄，對照已更新的開獎結果，顯示每期投注號碼是否中正號或特別號，並統計投注注數、投注金額、中獎注數、派彩總額及損益。

## 自動更新流程

`crontab.txt` 已設定自動執行：

```text
check_data_then_seed.py
```

當 `check_data_then_seed.py` 發現 M2/M3 有新開獎資料時，會依序執行：

```text
msk_new_seed_apps/A1_seedBet_main.py
n_v1_msk_prize_31_num_backtest_pred/A1_v2_brithday_group_quota_pred.py
```

兩個程式都成功後，才會更新處理狀態。若其中一個失敗，下一次排程會再次嘗試。

## 注意事項

本網站提供的是基於歷史資料、派彩注數、獎金變化、號碼特徵及區間模式的統計分析結果，只作投注參考用途，並不保證中獎。
