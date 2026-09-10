uv add tree 安裝 tree, 輸入 tree -d，可以打印目錄 

不打印某目錄 
tree -d -I "__pycache__|A_msk_balls_png"

# 存檔整個系統 csv 開獎號 
├── A_msk_lottery_data_folder # 
# streamlit 網頁版 目錄 
├── app_pages
# 網頁版 components 
├── custom_components
│   └── number_picker_frontend
# 網頁版- 會員功能 
├── member
│   └── member_bet_dbs
# -- RBG convertion function
├── msk_marksix_function_app 

# n_v1, n_v3 都是用 3 獎注數作主要分析，排序預測。暫不用 3 獎注數作預測 
├── n_v1_msk_prize_31_num_backtest_pred
│   ├── bet_prize_data
│   └── json_data
├── n_v3_msk_prize3_test_sample
│   ├── bet_data
│   ├── data
│   └── json_data
# nn_v5, nn_v6, nn_v7, nn_v8 , 是正式用 1-31, 分組預測。
# F = 1-9，G = 10-20, H= 21-31
├── nn_v5_msk_1_9_num_apps
│   └── json_data
├── nn_v6_msk_10_20_num_apps
│   └── json_data
├── nn_v7_msk_21_31_num_apps
│   └── json_data
├── nn_v8_msk_route_pred_apps
│   ├── bet_data
│   └── json_data
# ================================================| 
# -- xx_ 目錄已決定網頁版 全碼用 不用 1-31 生日號 apps , 用 3 獎注作重點分析。
# =================================================|
# 種子投注法。
├── xx_msk_new_seed_apps
│   └── bet_data

├── x_nn_v4_msk_birthday_31_num_apps
│   ├── bet_data
│   ├── comb_data
│   └── json_data
├── xx_n_v2_msk_prize_31_num_backtest_pred
│   ├── bet_data
│   ├── comb_data
│   ├── json_data
│   └── old_py
# 下載馬會開獎號及中獎資訊
└── Z4_lotto_prize_2026_crawler
    ├── log
    └── Lotto_Data_Folder

38 directories