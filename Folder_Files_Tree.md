不打印某目錄 , 自打印目錄 
tree -d -I "__pycache__|__init__ |A_msk_balls_png"
打印目錄 ＋ 檔案 
tree -I "__pycache__|__init__|A_msk_balls_png"

├── A_msk_lottery_data_folder
│   ├── M2_last_upgrade_lotto_data.csv
│   ├── M3_lotto_prize_results.csv
│   ├── M4_lotto_prize_summary.csv
│   ├── M6_lotto_history_prize.csv
│   └── M7_lotto_open_days.csv
├── app_pages
│   ├── 0_lotto_info.py
│   ├── 1_A1_v1_manuel_pred.py
│   ├── 1_R1_v2_Fortune_code_pred.py
│   ├── 2_lotto_prize_results.py
│   ├── 3_lotto_lucky_day.py
│   ├── 4_prize_comb_key.py
│   ├── old_pages
│   │   ├── x_0_predict_nextdraw.py
│   │   ├── x_1_A1_v2_12_6_3_pred.py
│   │   ├── x_1_B0_v4_prize_keys.py
│   │   ├── x_1_B1_v1.py
│   │   └── x_1_C1_v1_fortune_key.py
│   ├── x1_multiple_bet.py
│   └── x2_banker_leg_bet.py
├── check_data_then_seed.py
├── crontab.txt
├── css.py
├── custom_components
│   ├── number_picker_frontend
│   │   └── index.html
│   └── number_picker.py
├── db.py
├── Dockerfile
├── fix_vol.md
├── Folder_Files_Tree.md
├── Folder_說明.md
├── member
│   ├── member_bet_center.py
│   ├── member_bet_dbs
│   │   ├── mrlam9861_gmail_com_bets.db
│   │   └── mrlam98613_gmail_com_bets.db
│   ├── member_custom_bet.py
│   ├── member_login.py
│   └── members.db
├── msk_marksix_function_app
│   ├── app4_multiple_bet.py
│   ├── app5_banker_legs_bet.py
│   └── res_func_num_convert_RBG_Dict.py
├── n_v1_msk_prize_31_num_backtest_pred
│   ├── A1_v1_brithday_keys_analysis.py
│   └── bet_prize_data
│       └── admin_bet.csv
├── n_v3_msk_prize3_test_sample
│   ├── bet_data
│   │   ├── bet_records.csv
│   │   ├── nextdraw_pred.csv
│   │   └── win_results.csv
│   ├── C1_v1_fortune_key_pred.py
│   ├── c2_v2_step2_collect.py
│   ├── c2_v2-fortune_key_step1.py
│   ├── C2_v3_collect_pred.py
│   ├── C2_v4_with_json_pred.py
│   ├── C2_v5_backtest_predict.py
│   ├── data
│   │   ├── C1_v1_backtest_check_rows.csv
│   │   ├── C1_v1_nextdraw_pred.csv
│   │   ├── C2_v4_nextdraw_pred.csv
│   │   └── D1_v1_nextdraw_pred.csv
│   ├── json_data
│   │   ├── C1_v1_simple_best_params.json
│   │   ├── C1_v1_web_best_params.json
│   │   ├── C2_v4_best_params.json
│   │   └── D1_v1_best_params.json
│   ├── res_func_num_convert_RBG_Dict.py
│   ├── x_D1_v1_dynamic_quota_pred.py
│   ├── z_C2_v1_fortune_key第一步.md
│   └── z_C2_v2.md
├── nn_v5_msk_1_9_num_apps
│   ├── F5_v5_cold_rebound.py
│   ├── F5_v5_main.py
│   ├── f5_v5_settings.py
│   ├── F5_v6_main.py
│   ├── json_data
│   │   └── F5_v6_best_params.json
│   └── z_F5_v6.md
├── nn_v6_msk_10_20_num_apps
│   ├── G1_v1_cold_rebound.py
│   ├── G1_v1_main.py
│   └── json_data
│       ├── G1_v1_best_params.json
│       └── G1_v1_cold_rebound_best.json
├── nn_v7_msk_21_31_num_apps
│   ├── H1_v1_cold_rebound.py
│   ├── H1_v1_main.py
│   └── json_data
│       ├── H1_v1_best_params.json
│       └── H1_v1_cold_rebound_best.json
├── nn_v8_msk_route_pred_apps
│   ├── bet_data
│   │   └── nextBetDraw_record.csv
│   ├── json_data
│   │   ├── R1_v1_route_best_params.json
│   │   └── R1_v2_route_with_fgh_pred.json
│   ├── R1_v1_route_backtest_pred.py
│   └── R1_v2_route_with_fgh_pred.py
├── pyproject.toml
├── requirements.txt
├── streamlit_app.py
├── uv.lock
├── xx__msk_new_seed_apps
│   ├── A1_seedBet_main.py
│   ├── B01_check_lottoWin.py
│   ├── bet_data
│   │   ├── check_data_log.txt
│   │   ├── check_data_state.json
│   │   ├── my_bet_records.csv
│   │   ├── my_win_results.csv
│   │   ├── nextBetDraw_record.csv
│   │   └── nextBetDraw_summary.csv
│   ├── func2_RBG_collect_5Balls_DrawWindows.py
│   ├── res_func_marksix_next_BetDate.py
│   ├── res_func_num_convert_RBG_Dict.py
│   ├── res_predict_N1_N6_interval_BackTest.py
│   └── seed_lotto_strategy.py
├── xx__nn_v4_msk_birthday_31_num_apps
│   ├── bet_data
│   ├── comb_data
│   │   ├── E1_num_1_9_comb.csv
│   │   ├── E2_num_1_9.csv
│   │   ├── E2_num_10_20.csv
│   │   ├── E2_num_21_31.csv
│   │   ├── E4_num_1_9_comb.csv
│   │   ├── E4_v3_num_1_9_comb.csv
│   │   └── F5_v1.csv
│   ├── E1_v1_1_9_basic_query.py
│   ├── E2_v1_1_31_comb_csv_builder.py
│   ├── E4_v3_backtest_pred_pass.py
│   ├── F5_v1_backtest_detail.py
│   ├── F5_v2_main.py
│   ├── F5_v2_none_transition.py
│   ├── F5_v3_upgrade.py
│   ├── F5_v4_cold_rebound_backtest.py
│   ├── json_data
│   │   ├── E4_v1_19_pred_mode_params.json
│   │   ├── E4_v2.json
│   │   ├── E4_v3.json
│   │   ├── F5_v2_best_params.json
│   │   ├── F5_v2_none_transition.json
│   │   ├── F5_v3_auto_best_params.json
│   │   └── F5_v4_cold_rebound_best.json
│   ├── NN_E3_v1.md
│   ├── NN_v4_num31.md
│   ├── x_E3_v1_19_backtest.py
│   ├── x_E4_v1_19_pred_mode.py
│   └── x_E4_v2_backtest_pred.py
├── xx_n_v2_msk_prize_31_num_backtest_pred
│   ├── A0_v1_comb_unit_analysis.py
│   ├── A0_v3.py
│   ├── B0_v4_backtest_with_json.py
│   ├── B1_v1_birthday_dynamic_predict.py
│   ├── bet_data
│   │   ├── backtest_window_check_rows.csv
│   │   ├── bet_records.csv
│   │   ├── nextdraw_pred.csv
│   │   └── win_results.csv
│   ├── comb_data
│   │   ├── backtest_match_unit_3.csv
│   │   ├── comb_unit_3.csv
│   │   ├── hit_count_unit_3.csv
│   │   └── pair_focus_groups_3.json
│   ├── json_data
│   │   └── group_weight_best_modes.json
│   ├── old_py
│   │   ├── A0_v1_comb_unit_analysis.py
│   │   ├── A0_v2_comb31_group_backtest_pred.py
│   │   ├── A0_v3_comb31_group_backtest_pred.py
│   │   ├── A0_v3.py
│   │   ├── r_A0_v3_中獎注數回測及下期預測.md
│   │   └── x_comb_4_test.py
│   ├── res_func_num_convert_RBG_Dict.py
│   └── 權重.md
└── Z4_lotto_prize_2026_crawler
    ├── A0_main.py
    ├── A1_mingpao_fallback_append.py
    ├── log
    │   └── lotto_download_log.txt
    ├── Lotto_Data_Folder
    │   ├── M0_2008_2025_history_prize.csv
    │   ├── M1_Z4_lotto_data.csv
    │   ├── M2_last_upgrade_lotto_data.csv
    │   ├── M3_lotto_prize_results.csv
    │   ├── M4_lotto_prize_summary.csv
    │   ├── M6_lotto_history_prize.csv
    │   └── M7_lotto_open_days.csv
    └── Z4_README.md

38 directories, 156 files