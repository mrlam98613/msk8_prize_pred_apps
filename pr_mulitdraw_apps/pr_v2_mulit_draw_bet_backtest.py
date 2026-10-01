from pathlib import Path
import csv
import random
from collections import Counter
from collections.abc import Sequence
from typing import TypedDict


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
M6_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"
BET_DATA_DIR = CURRENT_DIR / "bet_data"
BET_WIN_RECORD_CSV = BET_DATA_DIR / "pr_v2_bet_win_recorde.csv"
BET_TICKET_RECORD_CSV = BET_DATA_DIR / "pr_v2_bet_ticket_record.csv"


# MODE 可選："backtest"；本版主力測投注損益。
MODE = "backtest"
BACKTEST_DRAW_COUNT_LIST = [30]
WINDOW_DRAW_COUNT_LIST = [6]

# 查詢號碼範圍。
LOTTO_NUM_MIN = 1
LOTTO_NUM_MAX = 49

# 每期先隨機發 17 個不同號。
RANDOM_PICK_COUNT = 17
RANDOM_SEED = 20260927

# 17 球固定以 4+4+4+3+2 分配。
GROUPS = {
    "A": (1, 9),
    "B": (10, 20),
    "C": (21, 31),
    "D": (32, 40),
    "E": (41, 49),
}
GROUP_TAKE_COUNTS = {
    "A": 5,
    "B": 4,
    "C": 4,
    "D": 2,
    "E": 2,
}

# 投注設定：每期 17 球按指定配號表拆成 23 組 7 號複式。
MULTIPLE_NUM_COUNT = 7
MULTIPLE_SET_COUNT = 23
BET_UNIT = 5
BET_PER_MULTIPLE_7 = 7
PERIOD_BET_COST = 850

# 23 注聰明組合配號表；只使用用戶提供的固定表。
# 01-17 對應當期候選 17 球的入注順序，不按號碼大小重排，也不由程式另行產生組合。
MULTIPLE_INDEX_PATTERNS = [
    (1, 2, 3, 4, 5, 6, 7),
    (1, 2, 3, 8, 9, 10, 11),
    (1, 2, 4, 12, 13, 14, 15),
    (1, 3, 5, 12, 13, 16, 17),
    (1, 4, 6, 8, 9, 16, 17),
    (1, 5, 7, 10, 11, 14, 15),
    (1, 6, 7, 8, 10, 12, 13),
    (2, 3, 6, 10, 11, 16, 17),
    (2, 4, 7, 8, 9, 14, 15),
    (2, 5, 7, 9, 11, 12, 16),
    (2, 5, 6, 13, 14, 15, 17),
    (3, 4, 5, 8, 9, 13, 17),
    (3, 4, 6, 11, 12, 14, 15),
    (3, 7, 9, 10, 13, 15, 16),
    (4, 7, 10, 11, 12, 16, 17),
    (5, 6, 8, 10, 12, 15, 17),
    (5, 6, 9, 11, 13, 14, 16),
    (1, 3, 9, 10, 14, 16, 17),
    (1, 4, 8, 11, 13, 15, 16),
    (2, 3, 7, 8, 12, 14, 17),
    (2, 6, 9, 10, 13, 15, 17),
    (3, 5, 8, 11, 12, 14, 16),
    (4, 6, 7, 9, 10, 12, 13),
]

# 是否打印「每期複式投注明細」。
PRINT_BACKTEST_DETAIL = True

# 預設 $10 注派彩；1-3 獎會在每段回測期用 M6 平均派彩覆蓋。
DEFAULT_TOP_PRIZE_PAYOUTS = {
    "1": 8_000_000.0,
    "2": 1_000_000.0,
    "3": 80_000.0,
}
PRIZE_PAYOUTS = {
    "1": DEFAULT_TOP_PRIZE_PAYOUTS["1"],
    "2": DEFAULT_TOP_PRIZE_PAYOUTS["2"],
    "3": DEFAULT_TOP_PRIZE_PAYOUTS["3"],
    "4": 9_600.0,
    "5": 640.0,
    "6": 320.0,
    "7": 40.0,
}
PRIZE_RULES = [
    {"prize": "1", "req_n": 6, "req_s": 0},
    {"prize": "2", "req_n": 5, "req_s": 1},
    {"prize": "3", "req_n": 5, "req_s": 0},
    {"prize": "4", "req_n": 4, "req_s": 1},
    {"prize": "5", "req_n": 4, "req_s": 0},
    {"prize": "6", "req_n": 3, "req_s": 1},
    {"prize": "7", "req_n": 3, "req_s": 0},
]


class DrawRow(TypedDict):
    date: str
    nums: list[int]
    special: int | None
    prize1_unit: float
    prize2_unit: float
    prize3_unit: float


class BetResult(TypedDict):
    payout: float
    profit: float
    prize_counts: Counter[str]
    hit_ticket_count: int
    main_hits: int
    special_hit: bool


class WinRecord(TypedDict):
    bet_date: str
    N1: int
    N2: int
    N3: int
    N4: int
    N5: int
    N6: int
    N7: int
    hit_counter: float
    unit: int
    prize: str
    amount: float


class TicketRecord(TypedDict):
    draw_index: int
    bet_date: str
    ticket_no: int
    I1: int
    I2: int
    I3: int
    I4: int
    I5: int
    I6: int
    I7: int
    N1: int
    N2: int
    N3: int
    N4: int
    N5: int
    N6: int
    N7: int
    normal_hits: str
    special_hit: str
    hit_counter: float
    prize_counts: str
    amount: float


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    """讀取 CSV 並清理欄位名稱與文字空白。"""
    if not path.exists():
        raise FileNotFoundError(f"找不到 CSV：{path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames:
            reader.fieldnames = [name.strip().lstrip("\ufeff") for name in reader.fieldnames]
        return [
            {(key or "").strip().lstrip("\ufeff"): (value or "").strip() for key, value in row.items()}
            for row in reader
        ]


def to_int(value: object, default: int = 0) -> int:
    """安全轉換數值為 int。"""
    if not isinstance(value, (int, float, str)):
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def to_float(value: object, default: float = 0.0) -> float:
    """安全轉換數值為 float。"""
    if not isinstance(value, (int, float, str)):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_m6_row(row: dict[str, str]) -> DrawRow:
    """將 M6 原始 CSV 一行轉成標準 DrawRow。"""
    special = to_int(row.get("N7"))
    return {
        "date": row.get("nDdate", ""),
        "nums": [to_int(row.get(f"N{index}")) for index in range(1, 7)],
        "special": special if 1 <= special <= 49 else None,
        "prize1_unit": to_float(row.get("prize1_unit")),
        "prize2_unit": to_float(row.get("prize2_unit")),
        "prize3_unit": to_float(row.get("prize3_unit")),
    }


def read_draws() -> list[DrawRow]:
    """讀取所有有效歷史開獎紀錄。"""
    return [row for row in [parse_m6_row(raw) for raw in read_csv_rows(M6_CSV)] if row["date"]]


def format_nums(nums: Sequence[int | str]) -> str:
    """格式化號碼列表。"""
    return "[" + ",".join(str(num) for num in nums) + "]"


def format_money(value: float) -> str:
    """格式化金額。"""
    return f"$ {value:,.2f}"


def payout_for_bet_unit(prize: str) -> float:
    """將 $10 注派彩按本程式 BET_UNIT 折算。"""
    return PRIZE_PAYOUTS[prize] * (BET_UNIT / 10)


def average_positive(values: list[float], default: float) -> float:
    """只用大於 0 的派彩值計平均，沒有資料時回傳預設值。"""
    valid_values = [value for value in values if value > 0]
    if not valid_values:
        return default
    return sum(valid_values) / len(valid_values)


def update_top_prize_payouts(backtest_rows: list[DrawRow]) -> None:
    """用回測期內 M6 過往紀錄的 1、2、3 獎平均獎金更新派彩表。"""
    PRIZE_PAYOUTS["1"] = average_positive([row["prize1_unit"] for row in backtest_rows], DEFAULT_TOP_PRIZE_PAYOUTS["1"])
    PRIZE_PAYOUTS["2"] = average_positive([row["prize2_unit"] for row in backtest_rows], DEFAULT_TOP_PRIZE_PAYOUTS["2"])
    PRIZE_PAYOUTS["3"] = average_positive([row["prize3_unit"] for row in backtest_rows], DEFAULT_TOP_PRIZE_PAYOUTS["3"])


def format_top_prize_payouts() -> str:
    """格式化 1、2、3 獎按本程式 BET_UNIT 折算後的平均派彩顯示。"""
    return (
        f"1獎={format_money(payout_for_bet_unit('1'))}，"
        f"2獎={format_money(payout_for_bet_unit('2'))}，"
        f"3獎={format_money(payout_for_bet_unit('3'))}"
    )


def format_group_ranges() -> str:
    """格式化分組範圍顯示。"""
    return "，".join(f"{name}={start}-{end}" for name, (start, end) in GROUPS.items())


def format_group_take_counts() -> str:
    """格式化各組發球數顯示。"""
    return "，".join(f"{name}={GROUP_TAKE_COUNTS[name]}球" for name in GROUPS.keys())


def group_nums(group_name: str) -> list[int]:
    """取得分組內、且落在手動 min/max 範圍的號碼。"""
    start, end = GROUPS[group_name]
    return [num for num in range(start, end + 1) if LOTTO_NUM_MIN <= num <= LOTTO_NUM_MAX]


def random_predict_nums(check_row: DrawRow, draw_index: int) -> list[int]:
    """按分組分佈，隨機產生 17 個不同預測號，保留入注順序。"""
    rng = random.Random(f"{RANDOM_SEED}-{check_row['date']}-{draw_index}")
    selected: list[int] = []

    for group_name in GROUPS.keys():
        pool = group_nums(group_name)
        take_count = min(GROUP_TAKE_COUNTS[group_name], len(pool))
        selected.extend(rng.sample(pool, take_count))

    if len(selected) < RANDOM_PICK_COUNT:
        remaining_pool = [num for num in range(LOTTO_NUM_MIN, LOTTO_NUM_MAX + 1) if num not in selected]
        selected.extend(rng.sample(remaining_pool, RANDOM_PICK_COUNT - len(selected)))

    return selected


def build_multiple_tickets(predicted_nums: list[int]) -> list[tuple[int, ...]]:
    """用用戶提供的固定 23 注配號表，將 17 個預測號拆成 23 組 7 號複式。"""
    if len(predicted_nums) < RANDOM_PICK_COUNT:
        raise ValueError(f"預測號不足 {RANDOM_PICK_COUNT} 個，不能套用 23 注配號表。")
    tickets: list[tuple[int, ...]] = []
    for pattern in MULTIPLE_INDEX_PATTERNS:
        tickets.append(tuple(predicted_nums[index - 1] for index in pattern))
    return tickets


def ticket_prize_counts(ticket: tuple[int, ...], check_row: DrawRow) -> Counter[str]:
    """計算一組 7 號複式拆成 7 注後，各獎級中獎注數。"""
    main_hit = sum(1 for num in ticket if num in set(check_row["nums"]))
    special_hit = 1 if check_row["special"] in ticket else 0
    miss_count = len(ticket) - main_hit - special_hit
    prize_counts: Counter[str] = Counter()

    for rule in PRIZE_RULES:
        req_n = int(rule["req_n"])
        req_s = int(rule["req_s"])
        req_miss = 6 - req_n - req_s
        if req_n > main_hit or req_s > special_hit or req_miss > miss_count:
            continue
        prize_counts[str(rule["prize"])] += (
            safe_comb(main_hit, req_n)
            * safe_comb(special_hit, req_s)
            * safe_comb(miss_count, req_miss)
        )

    return prize_counts


def ticket_hit_counter(ticket: tuple[int, ...], check_row: DrawRow) -> float:
    """計算單組 7 字複式命中球數；正號 1 球，特號 0.5 球。"""
    main_hit = sum(1 for num in ticket if num in set(check_row["nums"]))
    special_hit = 0.5 if check_row["special"] in ticket else 0.0
    return main_hit + special_hit


def build_win_records(check_row: DrawRow, tickets: list[tuple[int, ...]]) -> list[WinRecord]:
    """只建立有中獎的 7 字複式投注紀錄。"""
    records: list[WinRecord] = []
    for ticket in tickets:
        prize_counts = ticket_prize_counts(ticket, check_row)
        if not prize_counts:
            continue

        hit_counter = ticket_hit_counter(ticket, check_row)
        for prize in ["1", "2", "3", "4", "5", "6", "7"]:
            unit = prize_counts[prize]
            if unit <= 0:
                continue
            records.append(
                {
                    "bet_date": check_row["date"],
                    "N1": ticket[0],
                    "N2": ticket[1],
                    "N3": ticket[2],
                    "N4": ticket[3],
                    "N5": ticket[4],
                    "N6": ticket[5],
                    "N7": ticket[6],
                    "hit_counter": hit_counter,
                    "unit": unit,
                    "prize": prize,
                    "amount": payout_for_bet_unit(prize) * unit,
                }
            )
    return records


def build_ticket_records(
    draw_index: int,
    check_row: DrawRow,
    predicted_nums: list[int],
    tickets: list[tuple[int, ...]],
) -> list[TicketRecord]:
    """建立每一期 23 注完整投注紀錄，方便核對固定配號表是否正確套入。"""
    records: list[TicketRecord] = []

    for ticket_no, (pattern, ticket) in enumerate(zip(MULTIPLE_INDEX_PATTERNS, tickets), start=1):
        prize_counts = ticket_prize_counts(ticket, check_row)
        amount = sum(payout_for_bet_unit(prize) * count for prize, count in prize_counts.items())
        ticket_set = set(ticket)
        normal_hits = [num for num in check_row["nums"] if num in ticket_set]
        special = check_row["special"]
        special_hit = f"*{special}" if special is not None and special in ticket_set else "_"

        record: TicketRecord = {
            "draw_index": draw_index,
            "bet_date": check_row["date"],
            "ticket_no": ticket_no,
            "I1": pattern[0],
            "I2": pattern[1],
            "I3": pattern[2],
            "I4": pattern[3],
            "I5": pattern[4],
            "I6": pattern[5],
            "I7": pattern[6],
            "N1": ticket[0],
            "N2": ticket[1],
            "N3": ticket[2],
            "N4": ticket[3],
            "N5": ticket[4],
            "N6": ticket[5],
            "N7": ticket[6],
            "normal_hits": format_nums(normal_hits),
            "special_hit": special_hit,
            "hit_counter": ticket_hit_counter(ticket, check_row),
            "prize_counts": format_prize_counts(prize_counts),
            "amount": amount,
        }
        records.append(record)

    return records


def write_win_records(records: list[WinRecord]) -> None:
    """將回測中獎複式投注紀錄寫入 CSV。"""
    BET_DATA_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "bet_date",
        "N1",
        "N2",
        "N3",
        "N4",
        "N5",
        "N6",
        "N7",
        "hit_counter",
        "unit",
        "prize",
        "amount",
    ]
    with BET_WIN_RECORD_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def write_ticket_records(records: list[TicketRecord]) -> None:
    """將每期 23 注完整投注紀錄寫入 CSV。"""
    BET_DATA_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "draw_index",
        "bet_date",
        "ticket_no",
        "I1",
        "I2",
        "I3",
        "I4",
        "I5",
        "I6",
        "I7",
        "N1",
        "N2",
        "N3",
        "N4",
        "N5",
        "N6",
        "N7",
        "normal_hits",
        "special_hit",
        "hit_counter",
        "prize_counts",
        "amount",
    ]
    with BET_TICKET_RECORD_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def print_record_csv_paths() -> None:
    """打印投注驗證 CSV 存檔位置。"""
    print(f"完整 23 注投注紀錄：{BET_TICKET_RECORD_CSV}")
    print(f"中獎複式紀錄：{BET_WIN_RECORD_CSV}")


def safe_comb(n: int, r: int) -> int:
    """安全計算組合數。"""
    if r < 0 or r > n:
        return 0
    return math_comb(n, r)


def math_comb(n: int, r: int) -> int:
    """避免全域只為一行匯入 math。"""
    result = 1
    for value in range(1, r + 1):
        result = result * (n - value + 1) // value
    return result


def hit_nums(predicted_nums: list[int], check_row: DrawRow) -> list[str]:
    """取得 17 球命中號碼文字，特號以 * 標示。"""
    predicted_set = set(predicted_nums)
    hits = [str(num) for num in check_row["nums"] if num in predicted_set]
    special = check_row["special"]
    if special is not None and special in predicted_set:
        hits.append(f"*{special}")
    return hits


def normal_hit_nums(predicted_nums: list[int], check_row: DrawRow) -> list[int]:
    """取得正號命中號碼。"""
    predicted_set = set(predicted_nums)
    return [num for num in check_row["nums"] if num in predicted_set]


def special_hit_text(predicted_nums: list[int], check_row: DrawRow) -> str:
    """取得特號命中文字。"""
    special = check_row["special"]
    if special is not None and special in set(predicted_nums):
        return f"*{special}"
    return "_"


def evaluate_period(predicted_nums: list[int], tickets: list[tuple[int, ...]], check_row: DrawRow) -> BetResult:
    """計算單期 23 組複式的中獎注數、派彩與損益。"""
    prize_counts: Counter[str] = Counter()
    hit_ticket_count = 0

    for ticket in tickets:
        ticket_counts = ticket_prize_counts(ticket, check_row)
        if sum(ticket_counts.values()) > 0:
            hit_ticket_count += 1
        prize_counts.update(ticket_counts)

    payout = sum(payout_for_bet_unit(prize) * count for prize, count in prize_counts.items())
    profit = payout - PERIOD_BET_COST
    predicted_set = set(predicted_nums)
    main_hits = sum(1 for num in check_row["nums"] if num in predicted_set)
    special_hit = check_row["special"] in predicted_set if check_row["special"] is not None else False

    return {
        "payout": payout,
        "profit": profit,
        "prize_counts": prize_counts,
        "hit_ticket_count": hit_ticket_count,
        "main_hits": main_hits,
        "special_hit": special_hit,
    }


def format_prize_counts(prize_counts: Counter[str]) -> str:
    """格式化獎級注數。"""
    parts = [f"{prize}獎={prize_counts[prize]}注" for prize in ["1", "2", "3", "4", "5", "6", "7"] if prize_counts[prize] > 0]
    return "，".join(parts) if parts else "沒有中獎"


def print_query_setting() -> None:
    """打印本次投注回測設定。"""
    print("====== pr_mult_draw 17球拆7號複式投注回測 ======")
    print(f"運作模式：{MODE}")
    print(f"回測期列表：{BACKTEST_DRAW_COUNT_LIST}")
    print(f"窗口期列表：{WINDOW_DRAW_COUNT_LIST}")
    print(f"查詢號碼：{LOTTO_NUM_MIN}-{LOTTO_NUM_MAX}")
    print(f"每期隨機發球：{RANDOM_PICK_COUNT} 個不同號")
    print(f"分組：{format_group_ranges()}")
    print(f"分組發球：{format_group_take_counts()}")
    print(f"每期複式：{MULTIPLE_SET_COUNT} 組固定配號表，每組 {MULTIPLE_NUM_COUNT} 個號碼")
    print(f"每組 7 號複式：{BET_PER_MULTIPLE_7} 注 x {format_money(BET_UNIT)} = {format_money(BET_PER_MULTIPLE_7 * BET_UNIT)}")
    print(f"每期固定投注金額：{format_money(PERIOD_BET_COST)}")
    print(f"派彩：以 $10 注派彩為基準，按本程式每注 {format_money(BET_UNIT)} 折算")
    print("1、2、3獎會用每段回測期 M6 過往紀錄平均值；4-7獎用固定假設")
    print(
        "固定派彩："
        f"4獎={format_money(payout_for_bet_unit('4'))}，"
        f"5獎={format_money(payout_for_bet_unit('5'))}，"
        f"6獎={format_money(payout_for_bet_unit('6'))}，"
        f"7獎={format_money(payout_for_bet_unit('7'))}"
    )
    print()


def print_profit_summary(total_cost: float, total_payout: float, total_profit: float, hit_period_count: int, total_period: int, prize_totals: Counter[str]) -> None:
    """打印總投注損益表。"""
    print("----- 投注損益總結 -----")
    print(f"回測期數：{total_period} 期")
    print(f"命中期數：{hit_period_count} 期")
    print(f"總投注金額：{format_money(total_cost)}")
    print(f"總派彩金額：{format_money(total_payout)}")
    print(f"總損益：{format_money(total_profit)}")
    roi = (total_profit / total_cost * 100) if total_cost else 0.0
    print(f"回報率 ROI：{roi:.2f}%")
    print(f"總中獎注數：{format_prize_counts(prize_totals)}")


def run_backtest(draws: list[DrawRow]) -> None:
    """執行投注回測。"""
    latest_index = len(draws) - 1
    for backtest_count in BACKTEST_DRAW_COUNT_LIST:
        for window_count in WINDOW_DRAW_COUNT_LIST:
            first_check_index = max(window_count, latest_index - backtest_count + 1)
            check_indices = list(range(first_check_index, latest_index + 1))

            total_cost = 0.0
            total_payout = 0.0
            total_profit = 0.0
            hit_period_count = 0
            prize_totals: Counter[str] = Counter()
            detail_rows: list[str] = []
            win_records: list[WinRecord] = []
            ticket_records: list[TicketRecord] = []
            backtest_rows = [draws[index] for index in check_indices]
            update_top_prize_payouts(backtest_rows)

            print(f"====== 回測期={backtest_count}，窗口期={window_count} ======")
            print(f"回測期 1-3 獎平均派彩（{format_money(BET_UNIT)}注）：{format_top_prize_payouts()}")

            for draw_order, check_index in enumerate(check_indices, start=1):
                check_row = draws[check_index]
                predicted_nums = random_predict_nums(check_row, draw_order - 1)
                tickets = build_multiple_tickets(predicted_nums)
                result = evaluate_period(predicted_nums, tickets, check_row)
                win_records.extend(build_win_records(check_row, tickets))
                ticket_records.extend(build_ticket_records(draw_order, check_row, predicted_nums, tickets))

                total_cost += PERIOD_BET_COST
                total_payout += result["payout"]
                total_profit += result["profit"]
                prize_totals.update(result["prize_counts"])
                if result["payout"] > 0:
                    hit_period_count += 1

                if PRINT_BACKTEST_DETAIL:
                    score = result["main_hits"] + (0.5 if result["special_hit"] else 0.0)
                    detail_rows.append(
                        f"{draw_order} /> 核對日期：{check_row['date']}，"
                        "預測17球，"
                        f"正號命中 {format_nums(normal_hit_nums(predicted_nums, check_row))}，"
                        f"特號命中 {special_hit_text(predicted_nums, check_row)} /> {score:g} 球，"
                        f"中獎複式 {result['hit_ticket_count']}組，"
                        f"{format_prize_counts(result['prize_counts'])}，"
                        f"派彩 {format_money(result['payout'])}，"
                        f"損益 {format_money(result['profit'])}"
                    )

            if PRINT_BACKTEST_DETAIL:
                print()
                print("----- 每期複式投注明細 -----")
                for detail in detail_rows:
                    print(detail)

            write_win_records(win_records)
            write_ticket_records(ticket_records)

            print()
            print_profit_summary(
                total_cost=total_cost,
                total_payout=total_payout,
                total_profit=total_profit,
                hit_period_count=hit_period_count,
                total_period=len(check_indices),
                prize_totals=prize_totals,
            )
            print_record_csv_paths()
            print()


def main() -> None:
    """主流程。"""
    draws = read_draws()
    if not draws:
        raise FileNotFoundError(f"找不到或未能讀取 M6：{M6_CSV}")

    print_query_setting()
    if MODE == "backtest":
        run_backtest(draws)
    else:
        raise ValueError('MODE 目前只支援 "backtest"')


if __name__ == "__main__":
    main()
