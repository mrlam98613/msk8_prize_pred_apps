2026-08-11 星期二
目前這輪主要已整理好：
Zeabur Streamlit cache 更新問題：0_lotto_info.py、2_lotto_prize_results.py
Z4 log 改為只保留最新一次
移除 M0 依賴，改用 M2 作歷史底表
M1 只作 Z4 內部暫存，不再同步到網站資料夾
Z4_README.md 已重寫說明 M1/M2/M3/M4/M6/M7 用途與輸出位置
C4_brithday_num_pred.py 已完成回測/預測模式分離及三注單式策略


n_ 開頭目錄，代表已上線 預測功能 

n_msk_lotto_prize123_backtest_pred # 1，2，3 中獎注數最多作預測。

o_ 開頭代表回測練習，預測中。