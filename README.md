# MSK Prize Lotto Prediction Apps

本網站用於顯示六合彩開獎資料、下期投注預測、獎金特式分析及歷史投注統計。資料由 crawler 更新至 `A_msk_lottery_data_folder`，再由各個預測程式產生網站讀取用的 CSV。

## 主要功能

### 下期開獎及投注預測

網站會讀取最新一期開獎資料、下期開獎日期、下期頭獎基金，以及已產生的預測投注號碼。一般下期投注預測由 `msk_new_seed_apps/A1_seedBet_main.py` 產生。

### 1、2、3 獎特式投注預測

`app_pages/3_nextdraw_prize123_pred_bet.py` 主要顯示由以下程式產生的特式預測結果：

```text
n_msk_lotto_prize123_backtest_pred/C6_lotto_prize_123_pred_bet.py
```

C6 策略會分析最近約 50 期開獎及派彩資料，並在最近 24 期內，根據頭獎、二獎、三獎的中獎注數及中獎獎金變化，取出具參考價值的特式組合投注。

系統會分別針對以下三種獎金特式產生預測：

- 三獎特式預測：分析三獎派彩及中獎注數走勢，產生 1 注參考投注。
- 二獎特式預測：分析二獎派彩及中獎注數走勢，產生 1 注參考投注。
- 頭獎特式預測：分析頭獎派彩、無人中獎及獎金累積情況，產生 1 注參考投注。

預設模式會同時產生 3 注投注號碼，分別對應三獎、二獎及頭獎特式。用戶亦可按自己的投注偏好，選擇指定的獎金特式作預測投注參考。

網站頁面會讀取：

```text
n_msk_lotto_prize123_backtest_pred/bet_prize_data/prize123_nextDraw_bet.csv
n_msk_lotto_prize123_backtest_pred/bet_prize_data/prize123_bet.csv
```

其中 `prize123_nextDraw_bet.csv` 只保留目前最新下期的 1、2、3 獎特式預測投注，方便網站直接顯示。

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
n_msk_lotto_prize123_backtest_pred/C6_lotto_prize_123_pred_bet.py predict all
```

兩個程式都成功後，才會更新處理狀態。若其中一個失敗，下一次排程會再次嘗試。

## 注意事項

本網站提供的是基於歷史資料、派彩注數、獎金變化、號碼特徵及區間模式的統計分析結果，只作投注參考用途，並不保證中獎。
