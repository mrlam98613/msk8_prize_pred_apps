import pandas as pd 
from pathlib import Path
import res_predict_N1_N6_interval_BackTest


# 取得目前檔案所在目錄
current_dir = Path(__file__).resolve().parent

# 讀取歷史開獎資料，包含日期和號碼。
def load_data_func():
    df_ = pd.read_csv(
        current_dir.parent / "A_msk_lottery_data_folder" / "M2_last_upgrade_lotto_data.csv"
    )
    df = df_.iloc[:, [0, 1, 2, 3, 4, 5, 6, 7]]  # ndate, N1..N6 + N7
    df_all = pd.DataFrame(df)
    return df_all


def main():

    df_all = load_data_func()
    
    # # 找最後一開獎期-日期
    anchor_date = df_all.iloc[-1]["ndate"]
    
    if anchor_date is None:
        anchor_exists = (df_all["ndate"] == anchor_date).any()
        if not anchor_exists:
            print(f"找不到 anchor_date={anchor_date}，無法預測。")
            return None
    
    
    # '[0,x,x,x,x,4]/[x,x,x,x,x,4],[x,x,x,x,x,x] 依馬可夫隨機預測, 區間模式')
    fixed_interval_mode = "none"  # "head_tail" / "tail_only" / "none"
    window_list = [6]
    interval_pred = res_predict_N1_N6_interval_BackTest.predict_next_draw_intervals(
        window_list=window_list,
        alpha=1.0,
        anchor_date=str(anchor_date),
        fixed_interval_mode = fixed_interval_mode
    )

    # 安全提取預測結果（可能為 None）
    pred_interval = []
    if interval_pred is not None:
        pred_interval = interval_pred.get("pred_interval", [])
        print(f'/> 下期預測開號區間: {pred_interval}')
        
if __name__ == "__main__":
    main()