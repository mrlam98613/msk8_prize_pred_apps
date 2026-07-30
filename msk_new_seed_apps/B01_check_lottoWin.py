import pandas as pd
from pathlib import Path
import os
from typing import Any
# === 設定路徑 ===
# ROOT = Path(__file__).resolve().parent
current_dir = Path(__file__).resolve().parent
BET_FILE = current_dir / "bet_data" / "my_bet_records.csv"
HISTORY_FILE = current_dir.parent / "A_msk_lottery_data_folder" / "M2_last_upgrade_lotto_data.csv"
RESULT_FILE = current_dir / "bet_data" / "my_win_results.csv"

# 獎金對應表（以每注 $20 計）
PRIZE_TABLE: dict[float, int] = {
    6.0: 10000000,
    5.5: 1100000,
    5.0: 300000,
    4.5: 9600,
    4.0: 640,
    3.5: 320,
    3.0: 40,
}



def check_ticket() -> None:
    os.system('clear')
    print("/>---<>--🎯 核對過往投注紀錄與中獎號碼 ---<>---<\\\n")
    if not BET_FILE.exists() or not HISTORY_FILE.exists():
        print("❌ 檔案不存在，請確認 my_bet_records.csv 與 M2_lotto_history.csv 是否正確")
        return

    bets = pd.read_csv(BET_FILE, dtype={"bet_date": str})
    history = pd.read_csv(HISTORY_FILE, dtype={"ndate": str})
    history = history.dropna(subset=["ndate"])

    total_bets = 0
    total_wins = 0
    total_prize = 0
    no_result_dates: set[str] = set()
    results: list[list[Any]] = []

    print("\n🎯 核對投注紀錄：")

    for idx, (_, row) in enumerate(bets.iterrows()):
        total_bets += 1
        bet_date = str(row["bet_date"])
        bet_nums = [int(row[f"N{i}"]) for i in range(1, 7)]

        # 找對應開獎號碼
        match_row = history[history["ndate"] == bet_date]
        if match_row.empty:
            print(f"{idx+1:>3} 注 /> {bet_date}:{bet_nums} ------------------- > 尚未有開獎結果")
            no_result_dates.add(bet_date)
            results.append([bet_date, *["未開獎"] * 6, 0.0, 0])
            continue

        draw = match_row.iloc[0]
        win_nums = [int(draw[f"N{i}"]) for i in range(1, 7)]
        special = int(draw["N7"])

        # 計算中獎數
        hit = sorted([int(x) for x in set(bet_nums) & set(win_nums)])
        special_hit = special in bet_nums
        hit_score = len(hit) + 0.5 if special_hit and len(hit) in [3, 4, 5] else float(len(hit))

        # 計算獎金
        prize = PRIZE_TABLE.get(hit_score, 0)
        if prize > 0:
            total_wins += 1
            total_prize += prize

        # 顯示資訊
        if hit or special_hit:
            hit_display = f"{hit} + [{special}]" if special_hit else f"{hit} + []"
            if hit_score >= 3.0:
                ''' 如果中獎 號>= 3球, 顯示中獎金額'''
                print(f"{idx+1:>3} 注 /> {bet_date} {bet_nums}: {hit_display} = {hit_score}  ------------ 🎉 中獎 ${prize}")
            else:
                print(f"{idx+1:>3} 注 /> {bet_date} {bet_nums}: {hit_display}  = {hit_score}")
        else:
            print(f"{idx+1:>3} 注 /> {bet_date} {bet_nums}: ------------------- > 沒有中獎號碼")

        # 標記中獎號碼
        hit_marks = [n if n in hit else 0 for n in bet_nums]
        results.append([bet_date, *hit_marks, hit_score, prize])

    print("=" * 50)
    if no_result_dates:
        print("-----> 有最後投注彩票 > 但沒有開獎紀錄, 不能核對 !!")

    print("-" * 50)
    lotto_nuit_amount = 10  # 六合彩單式每注投注金額HKD10
    print(f"核對過往投注中獎期數 = [{total_wins}] 期")
    print(f"投注注數:[{total_bets}]注, 投注總金額 = $ {total_bets * lotto_nuit_amount}")
    print(f"中獎注數 =[{'{:>2}'.format(total_wins)}]注, 中獎泒彩獎金 $ {total_prize}")
    print(f"P / L 損益: $ {total_prize - total_bets * lotto_nuit_amount}")
    print("-" * 50)

    
    # 儲存結果（僅保留號碼，不包含 score/prize）
    result_df = pd.DataFrame(results, columns=["bet_date", "N1", "N2", "N3", "N4", "N5", "N6", "score", "prize"])
    result_df.drop(columns=["score", "prize"], inplace=True)
    result_df.to_csv(RESULT_FILE, index=False, encoding="utf-8-sig")
    print(f"\n✅ 已儲存中獎分析至：{RESULT_FILE.name}")

   
if __name__ == "__main__":
    check_ticket()
