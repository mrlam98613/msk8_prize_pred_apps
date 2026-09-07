F5_v6_main.py


F5-v2.py 是 分析沒有 開號 1-9 號。
F5\_v5\_cold.py, 才是冷門號分析。

1. 先判斷 1-9 是否發球
2. 再決定少發球 / 正常發球 / 強發球
3. 讀入 F5_v5_cold_rebound_best.json 的最佳冷號門檻
4. 最後才選雙球 pair，合併成候選球

配額判斷：少發球，目標 2 球
原因：上一期只開 1 球，先減少 1-9 發球
預測雙球：(1,7)
合併候選球：[1,7]

nn_v5_msk_1_31_num_apps/json_data/F5_v6_best_params.json