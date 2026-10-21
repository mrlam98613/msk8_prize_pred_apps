from __future__ import annotations

import csv
import itertools
import random
import re
import unicodedata
from pathlib import Path
from typing import TypedDict, cast

import streamlit as st

from app_pages.shared_style import apply_new_page_style


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PREDICT_DIR = PROJECT_ROOT / "S3_ABCD_prize3_Banker_leg_app" / "prize3_predict_ball"
BANKER_FILE = PREDICT_DIR / "s3_v3_prize3_banker_leg_balls.csv"
RBG_FILE = PREDICT_DIR / "s3_v3_RBG_balls.csv"
HFB_HFL_FILE = PREDICT_DIR / "s3_v3_HFB_HFL_balls.csv"
M3_FILE = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M3_lotto_prize_results.csv"
MIN_WHEELING_NUMBERS = 8
MAX_WHEELING_NUMBERS = 25
MAX_WHEELING_TICKET_COUNT = 50
FULL_COVERAGE_MAX_WHEELING_NUMBERS = 17


class WheelingSchemeResult(TypedDict):
    no: int
    name: str
    ticket_size: int
    match_if: int
    guarantee: int
    unit_cost: int
    tickets: list[tuple[int, ...]]
    uncovered_count: int
    cost: int
    coverage_verified: bool


@st.cache_data(show_spinner=False)
def read_latest_row(path: Path) -> dict[str, str] | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    return rows[-1] if rows else None


@st.cache_data(show_spinner=False)
def read_m3_next_draw_info(path: Path) -> dict[str, str]:
    info: dict[str, str] = {}
    if not path.exists():
        return info
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        for row in csv.reader(file):
            if len(row) >= 2:
                info[row[0].strip()] = row[1].strip()
    return info


def parse_numbers(value: str) -> list[int]:
    return sorted({int(number) for number in re.findall(r"\*?(\d+)", value or "")})


def format_amount(value: str) -> str:
    digits = re.sub(r"[^0-9]", "", value or "")
    return f"{int(digits):,}" if digits else value or "未有資料"


def parse_wheeling_numbers(raw_value: str) -> list[int]:
    """解析投注候選號碼，去除重複並排序。"""
    normalized = unicodedata.normalize("NFKC", raw_value or "")
    normalized = re.sub(r"[,，、;；]+", " ", normalized)
    return sorted({int(value) for value in normalized.split() if value.strip()})


WHEELING_SCHEMES = [
    {"no": 1, "name": "6字單式", "ticket_size": 6, "match_if": 5, "guarantee": 5, "unit_cost": 10},
    {"no": 2, "name": "6字單式", "ticket_size": 6, "match_if": 4, "guarantee": 4, "unit_cost": 10},
    {"no": 3, "name": "6字單式", "ticket_size": 6, "match_if": 4, "guarantee": 3, "unit_cost": 10},
    {"no": 4, "name": "7字複式", "ticket_size": 7, "match_if": 5, "guarantee": 5, "unit_cost": 35},
    {"no": 5, "name": "7字複式", "ticket_size": 7, "match_if": 4, "guarantee": 4, "unit_cost": 35},
    {"no": 6, "name": "7字複式", "ticket_size": 7, "match_if": 4, "guarantee": 3, "unit_cost": 35},
]


def build_cover_sets(
    tickets: list[tuple[int, ...]],
    subsets: list[tuple[int, ...]],
    guarantee: int,
) -> list[set[tuple[int, ...]]]:
    subset_set = set(subsets)
    all_numbers = sorted({number for subset in subsets for number in subset})
    covered_sets: list[set[tuple[int, ...]]] = []
    for ticket in tickets:
        covered: set[tuple[int, ...]] = set()
        for guaranteed_part in itertools.combinations(ticket, guarantee):
            remaining = len(subsets[0]) - guarantee
            if remaining == 0:
                candidate = tuple(sorted(guaranteed_part))
                if candidate in subset_set:
                    covered.add(candidate)
                continue
            available = [number for number in all_numbers if number not in guaranteed_part]
            for rest in itertools.combinations(available, remaining):
                candidate = tuple(sorted(guaranteed_part + rest))
                if candidate in subset_set:
                    covered.add(candidate)
        covered_sets.append(covered)
    return covered_sets


def build_wheeling_plan(
    numbers: list[int],
    ticket_size: int,
    match_if: int,
    guarantee: int,
    max_ticket_count: int,
) -> tuple[list[tuple[int, ...]], int]:
    """用貪婪法建立方案，回傳投注組合及未覆蓋子集數量。"""
    tickets = list(itertools.combinations(numbers, ticket_size))
    subsets = list(itertools.combinations(numbers, match_if))
    covered_sets = build_cover_sets(tickets, subsets, guarantee)
    uncovered = set(subsets)
    remaining_indexes = set(range(len(tickets)))
    selected: list[tuple[int, ...]] = []

    while uncovered and remaining_indexes and len(selected) < max_ticket_count:
        best_index = max(
            remaining_indexes,
            key=lambda index: len(covered_sets[index] & uncovered),
        )
        covered_count = len(covered_sets[best_index] & uncovered)
        if covered_count == 0:
            break
        selected.append(tickets[best_index])
        remaining_indexes.remove(best_index)
        uncovered -= covered_sets[best_index]
    return selected, len(uncovered)


def build_fast_wheeling_plan(
    numbers: list[int],
    ticket_size: int,
    max_ticket_count: int,
) -> tuple[list[tuple[int, ...]], int]:
    """18–25 球快速模式，不建立完整覆蓋資料。"""
    tickets = list(
        itertools.islice(
            itertools.combinations(numbers, ticket_size),
            min(max_ticket_count, MAX_WHEELING_TICKET_COUNT),
        )
    )
    return tickets, 0


def find_wheeling_hits(
    tickets: list[tuple[int, ...]],
    draw_numbers: tuple[int, ...],
    guarantee: int,
) -> list[tuple[int, tuple[int, ...], tuple[int, ...]]]:
    draw_set = set(draw_numbers)
    results: list[tuple[int, tuple[int, ...], tuple[int, ...]]] = []
    for index, ticket in enumerate(tickets, start=1):
        hits = tuple(number for number in ticket if number in draw_set)
        if len(hits) >= guarantee:
            results.append((index, ticket, hits))
    return results


def format_wheeling_numbers(numbers: tuple[int, ...] | list[int]) -> str:
    return "[" + ",".join(f"{number:02d}" for number in numbers) + "]"


PRIZE_ROWS = [
    (6.0, "頭獎", None),
    (5.5, "二獎", None),
    (5.0, "三獎", None),
    (4.5, "四獎", 4800),
    (4.0, "五獎", 320),
    (3.5, "六獎", 160),
    (3.0, "七獎", 20),
]


def format_hit_numbers(ticket: tuple[int, ...], regular: tuple[int, ...], special: int) -> str:
    """格式化正號及特別號命中結果。"""
    regular_hits = [number for number in ticket if number in set(regular)]
    hits = [str(number) for number in regular_hits]
    if special in ticket:
        hits.append(f"*{special}")
    return "[" + ",".join(hits) + "]"


def ticket_prize_count(
    ticket: tuple[int, ...], regular: tuple[int, ...], special: int
) -> float:
    return float(len(set(ticket) & set(regular))) + (0.5 if special in ticket else 0.0)


def best_ticket_prize_count(
    ticket: tuple[int, ...], regular: tuple[int, ...], special: int
) -> float:
    """取得單式或複式投注組合中的最高命中球數。"""
    bets = list(itertools.combinations(ticket, 6)) if len(ticket) == 7 else [ticket]
    return max(ticket_prize_count(bet, regular, special) for bet in bets)


def build_simulated_draw(
    candidate_numbers: list[int],
    candidate_hit_count: int,
    rng: random.Random,
) -> tuple[tuple[int, ...], int]:
    """建立指定候選球命中數，其餘正號及特別號來自候選池以外。"""
    outside_numbers = [number for number in range(1, 50) if number not in candidate_numbers]
    candidate_hits = rng.sample(candidate_numbers, candidate_hit_count)
    outside_draw = rng.sample(outside_numbers, 7 - candidate_hit_count)
    regular_numbers = tuple(sorted(candidate_hits + outside_draw[: 6 - candidate_hit_count]))
    special_number = outside_draw[-1]
    return regular_numbers, special_number


def render_prize_verification(
    ticket: tuple[int, ...],
    regular: tuple[int, ...],
    special: int,
    ticket_index: int = 1,
) -> None:
    """顯示單式或複式的獎項、注數及派彩核對。"""
    is_system = len(ticket) == 7
    bet_type = "複式" if is_system else "單式"
    bet_unit = 5 if is_system else 10
    bets = list(itertools.combinations(ticket, 6)) if is_system else [ticket]
    counts: dict[float, int] = {row[0]: 0 for row in PRIZE_ROWS}
    for bet in bets:
        hits = ticket_prize_count(bet, regular, special)
        if hits in counts:
            counts[hits] += 1

    highest_result = next(
        (row for row in PRIZE_ROWS if counts[row[0]] > 0),
        (0.0, "未達獎", 0),
    )
    highest_hits = format_hit_numbers(ticket, regular, special)
    st.markdown(
        f"**第 {ticket_index} 注，{bet_type}，中獎結果 {highest_hits} ｜ "
        f"{highest_result[1]} ｜ {len(bets)} 注 ｜**"
    )
    rows = []
    for hit_count, prize_name, prize_amount in PRIZE_ROWS:
        count = counts[hit_count]
        if prize_amount is None:
            amount_text = "等待馬會公佈"
            total_text = "待公佈"
        else:
            amount_text = f"$ {prize_amount:,}"
            total_text = f"$ {count * prize_amount:,}"
        rows.append(
            {
                "命中球數": f"{hit_count:g}",
                "獎項": prize_name,
                "注數": count,
                "每注派彩": amount_text,
                "合計": total_text,
            }
        )
    st.table(rows)


def render_wheeling_system(candidate_pool: list[int]) -> None:
    """顯示獨立智能組合投注區。"""
    st.divider()
    st.subheader("聰明組合投注")
    st.caption(
        f"候選球號限制：最少 {MIN_WHEELING_NUMBERS} 個，最多 {MAX_WHEELING_NUMBERS} 個。"
        "所有投注組合只會使用候選球池內的號碼。"
    )

    if "wheeling_candidate_numbers" not in st.session_state:
        st.session_state["wheeling_candidate_numbers"] = ", ".join(
            str(number) for number in candidate_pool
        )
    candidate_text = st.session_state.get("wheeling_candidate_numbers", "")
    st.markdown("**總候選球池**")
    with st.container(key="wheeling_candidate_display"):
        st.code(candidate_text or "[]", language="text", wrap_lines=True)
    try:
        entered_numbers = parse_wheeling_numbers(candidate_text)
        st.caption(f"目前候選號碼：{len(entered_numbers)} 球")
    except ValueError:
        st.caption("目前候選號碼：格式待修正")

    preview_col, reset_col = st.columns(2)
    preview_clicked = preview_col.button(
        "聰明投注組合預覽",
        key="wheeling_generate",
        icon=":material/preview:",
        type="primary",
        width="stretch",
    )
    reset_col.button(
        "重設",
        key="wheeling_reset",
        icon=":material/refresh:",
        on_click=reset_wheeling_system,
        width="stretch",
    )

    if preview_clicked:
        try:
            numbers = parse_wheeling_numbers(candidate_text)
        except ValueError:
            st.session_state["wheeling_result"] = None
            st.error("候選號碼格式不正確，請輸入整數號碼。")
        else:
            invalid_numbers = [number for number in numbers if not 1 <= number <= 49]
            if invalid_numbers:
                st.session_state["wheeling_result"] = None
                st.error(f"號碼必須介乎 1 至 49：{invalid_numbers}")
            elif not MIN_WHEELING_NUMBERS <= len(numbers) <= MAX_WHEELING_NUMBERS:
                st.session_state["wheeling_result"] = None
                st.error(
                    f"候選號碼數量必須是 {MIN_WHEELING_NUMBERS}-{MAX_WHEELING_NUMBERS} 個，"
                    f"目前是 {len(numbers)} 個。"
                )
            else:
                with st.spinner("正在計算 6 個投注方案，請稍候..."):
                    schemes: list[WheelingSchemeResult] = []
                    for scheme in WHEELING_SCHEMES:
                        coverage_verified = len(numbers) <= FULL_COVERAGE_MAX_WHEELING_NUMBERS
                        if coverage_verified:
                            tickets, uncovered_count = build_wheeling_plan(
                                numbers,
                                int(scheme["ticket_size"]),
                                int(scheme["match_if"]),
                                int(scheme["guarantee"]),
                                MAX_WHEELING_TICKET_COUNT,
                            )
                        else:
                            tickets, uncovered_count = build_fast_wheeling_plan(
                                numbers,
                                int(scheme["ticket_size"]),
                                MAX_WHEELING_TICKET_COUNT,
                            )
                        scheme_result: WheelingSchemeResult = {
                            "no": int(scheme["no"]),
                            "name": str(scheme["name"]),
                            "ticket_size": int(scheme["ticket_size"]),
                            "match_if": int(scheme["match_if"]),
                            "guarantee": int(scheme["guarantee"]),
                            "unit_cost": int(scheme["unit_cost"]),
                            "tickets": tickets,
                            "uncovered_count": uncovered_count,
                            "cost": len(tickets) * int(scheme["unit_cost"]),
                            "coverage_verified": coverage_verified,
                        }
                        schemes.append(scheme_result)
                st.session_state["wheeling_result"] = {"numbers": numbers, "schemes": schemes}
                st.session_state["wheeling_show_selected"] = False

    result = st.session_state.get("wheeling_result")
    if not isinstance(result, dict):
        return

    schemes = cast(list[WheelingSchemeResult], result["schemes"])
    st.markdown("### 方案摘要")
    summary_lines: list[str] = []
    for scheme in schemes:
        if not scheme["coverage_verified"]:
            status = f"快速模式，最多 {MAX_WHEELING_TICKET_COUNT} 注，未作完整覆蓋驗證"
        else:
            status = "完全覆蓋" if scheme["uncovered_count"] == 0 else f"未覆蓋 {scheme['uncovered_count']} 組"
        summary_lines.append(
            f"{scheme['no']}. {scheme['name']}，中{scheme['match_if']}保{scheme['guarantee']} = "
            f"{len(scheme['tickets'])} 組，${scheme['unit_cost']} x {len(scheme['tickets'])} "
            f"= ${scheme['cost']:,}，{status}"
        )
    st.code("\n".join(summary_lines), language="text", wrap_lines=False)

    selected_no = st.selectbox(
        "選擇投注方案預覽",
        [int(scheme["no"]) for scheme in schemes],
        format_func=lambda value: next(
            f"方案 {scheme['no']}：{scheme['name']}，中{scheme['match_if']}保{scheme['guarantee']}"
            for scheme in schemes if scheme["no"] == value
        ),
        key="wheeling_selected_scheme",
    )
    selected_scheme = next(scheme for scheme in schemes if scheme["no"] == selected_no)
    match_if = int(selected_scheme["match_if"])
    guarantee_count = int(selected_scheme["guarantee"])
    st.write(
        f"方案 {selected_no} 明細：{selected_scheme['name']}，中{match_if}保{guarantee_count}，"
        f"預計投注組數 {len(selected_scheme['tickets'])}，總成本 ${selected_scheme['cost']:,}。"
    )

    if st.button(
        "產生已選方案投注組合",
        key="wheeling_create_selected",
        icon=":material/confirmation_number:",
        type="primary",
        width="stretch",
    ):
        st.session_state["wheeling_show_selected"] = True

    if not st.session_state.get("wheeling_show_selected", False):
        st.info("請先選擇方案，再按「產生已選方案投注組合」。")
        return

    tickets = selected_scheme["tickets"]

    ticket_lines = [
        f"第 {index:03d} 組：[" + ",".join(f"{number:02d}" for number in ticket) + "]"
        for index, ticket in enumerate(tickets, start=1)
    ]
    st.code("\n".join(ticket_lines), language="text", wrap_lines=False)

    if st.button(
        "隨機核對驗證",
        key="wheeling_random_test",
        icon=":material/fact_check:",
        width="stretch",
    ):
        rng = random.Random()
        verification_lines = [
            f"-- 隨機核對驗證：候選球命中 {match_if} 個，其餘正號及特別號為非候選球"
        ]
        best_verification: tuple[float, int, tuple[int, ...], tuple[int, ...], int] | None = None
        for _ in range(3):
            regular_numbers, special_number = build_simulated_draw(
                result["numbers"], match_if, rng
            )
            selected_ticket = max(
                enumerate(tickets, start=1),
                key=lambda item: best_ticket_prize_count(
                    item[1], regular_numbers, special_number
                ),
                default=None,
            )
            if selected_ticket is None:
                continue
            ticket_index, ticket = selected_ticket
            hit_count = best_ticket_prize_count(ticket, regular_numbers, special_number)
            verification_lines.append(
                f"開獎號：{format_wheeling_numbers(regular_numbers)} + *{special_number}；"
                f"第 {ticket_index} 注：{format_wheeling_numbers(ticket)}，"
                f"中 {format_hit_numbers(ticket, regular_numbers, special_number)}"
            )
            current_result = (hit_count, ticket_index, ticket, regular_numbers, special_number)
            if best_verification is None or current_result[0] > best_verification[0]:
                best_verification = current_result
        st.code("\n".join(verification_lines), language="text", wrap_lines=False)
        if best_verification is not None:
            render_prize_verification(
                best_verification[2],
                best_verification[3],
                best_verification[4],
                best_verification[1],
            )


def select_category(category_key: str) -> None:
    st.session_state["wheel_pending_category"] = category_key


def apply_pending_category() -> None:
    category_key = st.session_state.pop("wheel_pending_category", None)
    if category_key is None:
        return
    category_pools = st.session_state["wheel_category_pools"]
    for other_key in category_pools:
        if other_key == category_key:
            continue
        category_pools[other_key].clear()
        for row_key in st.session_state["wheel_row_keys"].get(other_key, []):
            st.session_state[row_key] = False
    st.session_state["wheel_active_category"] = category_key


def reset_category(category_key: str) -> None:
    st.session_state["wheel_pending_reset"] = category_key


def load_total_pool_into_wheeling(numbers: list[int]) -> None:
    """將目前分類的總候選球池帶入聰明組合區。"""
    st.session_state["wheeling_candidate_numbers"] = ", ".join(
        str(number) for number in numbers
    )


def reset_wheeling_system() -> None:
    """清除候選號碼及已產生的方案預覽。"""
    st.session_state["wheeling_candidate_numbers"] = ""
    st.session_state.pop("wheeling_result", None)
    st.session_state.pop("wheeling_show_selected", None)
    st.session_state.pop("wheeling_selected_scheme", None)


def reset_total_group_selection() -> None:
    """清除總候選球池的 ABCD 選擇及聰明組合內容。"""
    for group in "ABCD":
        st.session_state[f"total_group_{group}"] = False
    reset_wheeling_system()


def apply_pending_reset() -> None:
    category_key = st.session_state.pop("wheel_pending_reset", None)
    if category_key is None:
        return
    st.session_state["wheel_category_pools"][category_key].clear()
    for row_key in st.session_state["wheel_row_keys"].get(category_key, []):
        st.session_state[row_key] = False
    if st.session_state.get("wheel_active_category") == category_key:
        st.session_state["wheel_active_category"] = None


def render_category_pool(title: str, pools: list[tuple[str, str]], category_key: str) -> set[int]:
    with st.container(border=True, key=f"category_pool_{category_key}"):
        st.subheader(title)
        row_keys = st.session_state["wheel_row_keys"].setdefault(category_key, [])
        selected_rows: list[set[int]] = []
        for label, value in pools:
            numbers = parse_numbers(value)
            row_key = f"check_{category_key}_{label}"
            if row_key not in row_keys:
                row_keys.append(row_key)
            checked = st.checkbox(
                f"{label}  {value or '[]'}",
                key=row_key,
                on_change=select_category,
                args=(category_key,),
            )
            if checked:
                selected_rows.append(set(numbers))
        selected_numbers = set().union(*selected_rows) if selected_rows else set()
        add_col, reset_col = st.columns(2)
        if add_col.button(
            "加入候選池",
            key=f"add_{category_key}",
            type="primary",
            width="stretch",
        ):
            select_category(category_key)
            st.session_state["wheel_category_pools"][category_key].update(selected_numbers)
            st.session_state["wheel_active_category"] = category_key
        reset_col.button(
            "重設",
            key=f"reset_{category_key}",
            on_click=reset_category,
            args=(category_key,),
            width="stretch",
        )
        category_pool = sorted(st.session_state["wheel_category_pools"][category_key])
        st.caption(
            f"{title.split('：', 1)[0]} 投注總候選球池 "
            f"{category_pool} /> {len(category_pool)} 球"
        )
    return set(st.session_state["wheel_category_pools"][category_key])


def main() -> None:
    st.set_page_config(page_title="S3 v3 智能組合球池", page_icon="🎯", layout="wide")
    apply_new_page_style()
    st.html(
        """
        <style>
        .block-container { max-width: none !important; }
        .s3-next-line { line-height: 1.9; }
        .s3-next-date { color: #0057b8 !important; font-weight: 700; }
        .s3-next-money { color: #d40000 !important; font-weight: 700; }
        button[kind="primary"],
        button[data-testid="stBaseButton-primary"] {
            background: #dcefff !important;
            border-color: #8fc8ef !important;
            color: #14527a !important;
        }
        button[kind="primary"]:hover,
        button[data-testid="stBaseButton-primary"]:hover {
            background: #c7e6fb !important;
            border-color: #6fb5e6 !important;
        }
        .st-key-load_predict_container button {
            background: #ddf5df !important;
            border-color: #91d39a !important;
            color: #256b2e !important;
        }
        .st-key-load_predict_container button:hover {
            background: #c9edcc !important;
            border-color: #6fbd7b !important;
        }
        .st-key-category_pool_banker_leg button[kind="primary"],
        .st-key-category_pool_rbg button[kind="primary"],
        .st-key-category_pool_hfb_hfl button[kind="primary"],
        .st-key-category_pool_banker_leg button[data-testid="stBaseButton-primary"],
        .st-key-category_pool_rbg button[data-testid="stBaseButton-primary"],
        .st-key-category_pool_hfb_hfl button[data-testid="stBaseButton-primary"] {
            background: #dcefff !important;
            border-color: #8fc8ef !important;
            color: #111111 !important;
        }
        .st-key-category_pool_banker_leg button[kind="secondary"],
        .st-key-category_pool_rbg button[kind="secondary"],
        .st-key-category_pool_hfb_hfl button[kind="secondary"],
        .st-key-category_pool_banker_leg button[data-testid="stBaseButton-secondary"],
        .st-key-category_pool_rbg button[data-testid="stBaseButton-secondary"],
        .st-key-category_pool_hfb_hfl button[data-testid="stBaseButton-secondary"] {
            background: #ffe1e1 !important;
            border-color: #efa0a0 !important;
            color: #111111 !important;
        }
        .st-key-category_pool_banker_leg button,
        .st-key-category_pool_banker_leg button *,
        .st-key-category_pool_rbg button,
        .st-key-category_pool_rbg button *,
        .st-key-category_pool_hfb_hfl button,
        .st-key-category_pool_hfb_hfl button * {
            color: #111111 !important;
        }
        .st-key-load_total_pool_container button {
            background: #fff1b8 !important;
            border-color: #e5c84f !important;
            color: #111111 !important;
        }
        .st-key-load_total_pool_container button:hover {
            background: #ffe88a !important;
            border-color: #d4b52f !important;
        }
        .st-key-reset_total_group_container button {
            background: #ffe1e1 !important;
            border-color: #efa0a0 !important;
            color: #111111 !important;
        }
        .st-key-reset_total_group_container button:hover {
            background: #ffd0d0 !important;
            border-color: #df7f7f !important;
        }
        .st-key-total_candidate_pool pre {
            font-size: 0.82rem !important;
            letter-spacing: -0.01em !important;
            line-height: 1.45 !important;
            white-space: pre-wrap !important;
            overflow-wrap: anywhere !important;
        }
        .st-key-wheeling_candidate_display pre {
            font-size: 0.82rem !important;
            letter-spacing: -0.01em !important;
            line-height: 1.45 !important;
            white-space: pre-wrap !important;
            overflow-wrap: anywhere !important;
        }
        div[data-testid="stHorizontalBlock"]:has(button[kind="primary"]) div[data-testid="stColumn"]:nth-child(2) button,
        div[data-testid="stHorizontalBlock"]:has(button[data-testid="stBaseButton-primary"]) div[data-testid="stColumn"]:nth-child(2) button {
            background: #ffe1e1 !important;
            border-color: #efa0a0 !important;
            color: #8f2f2f !important;
        }
        div[data-testid="stHorizontalBlock"]:has(button[kind="primary"]) div[data-testid="stColumn"]:nth-child(2) button:hover,
        div[data-testid="stHorizontalBlock"]:has(button[data-testid="stBaseButton-primary"]) div[data-testid="stColumn"]:nth-child(2) button:hover {
            background: #ffd0d0 !important;
            border-color: #df7f7f !important;
        }
        div[data-testid="stCodeBlock"] { width: 100% !important; }
        div[data-testid="stCodeBlock"] pre {
            white-space: pre !important;
            overflow-x: auto !important;
        }
        </style>
        """
    )
    m3_info = read_m3_next_draw_info(M3_FILE)
    st.write("3 v3 智能組合預測球池。")
    st.markdown("<div class='s3-next-line'>預測下期：開獎日期</div>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='s3-next-line s3-next-date'>{m3_info.get('開獎日期', '未有資料')}</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div class='s3-next-line'>多寶／金多寶：<span class='s3-next-money'>{format_amount(m3_info.get('多寶 / 金多寶', ''))}</span></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div class='s3-next-line'>估計頭獎基金：<span class='s3-next-money'>{format_amount(m3_info.get('估計頭獎基金', ''))}</span></div>",
        unsafe_allow_html=True,
    )

    with st.container(key="load_predict_container"):
        load_predict_clicked = st.button(
            "讀入預測球",
            icon=":material/download:",
            type="secondary",
            width="stretch",
        )
    if load_predict_clicked:
        st.cache_data.clear()
        st.rerun()

    banker = read_latest_row(BANKER_FILE)
    rbg = read_latest_row(RBG_FILE)
    hfb_hfl = read_latest_row(HFB_HFL_FILE)

    if not banker and not rbg and not hfb_hfl:
        st.info("尚未找到 S3 v3 預測球池，請先執行下期預測。")

    st.session_state.setdefault(
        "wheel_category_pools",
        {"banker_leg": set(), "rbg": set(), "hfb_hfl": set()},
    )
    st.session_state.setdefault("wheel_row_keys", {})
    st.session_state.setdefault("wheel_active_category", None)
    st.session_state.setdefault("wheel_pending_category", None)
    st.session_state.setdefault("wheel_pending_reset", None)
    apply_pending_reset()
    apply_pending_category()

    if banker:
        render_category_pool(
            "分類 1：主力／配腳球池",
            [
                ("主力 1", banker.get("banker1", "")),
                ("主力 2", banker.get("banker2", "")),
                ("配腳 1", banker.get("leg1", "")),
                ("配腳 2", banker.get("leg2", "")),
            ],
            "banker_leg",
        )
    else:
        st.info("沒有主力／配腳球池資料。")

    if rbg:
        render_category_pool(
            "分類 2：RBG 三色球池",
            [
                ("R 球", rbg.get("R ball", "")),
                ("B 球", rbg.get("B ball", "")),
                ("G 球", rbg.get("G ball", "")),
            ],
            "rbg",
        )
    else:
        st.info("沒有 RBG 球池資料。")

    if hfb_hfl:
        render_category_pool(
            "分類 3：HFB／HFL 球池",
            [
                ("HFB 高頻膽號", hfb_hfl.get("HFB_list", "")),
                ("HFL 高頻腳號", hfb_hfl.get("HFL_list", "")),
            ],
            "hfb_hfl",
        )
    else:
        st.info("沒有 HFB／HFL 球池資料。")

    with st.container(border=True, key="total_candidate_groups"):
        st.subheader("總候選球池")
        raw_category_key = st.session_state.get("wheel_active_category")
        category_key = raw_category_key if isinstance(raw_category_key, str) else None
        category_pools = st.session_state["wheel_category_pools"]
        total_pool = sorted(category_pools.get(category_key, set())) if category_key else []
        category_names = {
            "banker_leg": "主力／配腳",
            "rbg": "RBG",
            "hfb_hfl": "HFB／HFL",
        }
        if category_key is None:
            active_name = "尚未選擇"
        else:
            active_name = category_names.get(category_key, "尚未選擇")
        st.caption(f"目前使用分類：{active_name}")
        with st.container(key="total_candidate_pool"):
            st.code(
                f"{total_pool} /> {len(total_pool)} 球",
                language="text",
                wrap_lines=True,
            )
        group_pools = {
            "A": [number for number in total_pool if 1 <= number <= 9],
            "B": [number for number in total_pool if 10 <= number <= 20],
            "C": [number for number in total_pool if 21 <= number <= 31],
            "D": [number for number in total_pool if 32 <= number <= 40],
        }
        selected_groups: list[str] = []
        group_cols = st.columns(4)
        for group, group_numbers in group_pools.items():
            with group_cols[ord(group) - ord("A")]:
                checked = st.checkbox(
                    f"{group} {group_numbers or '[]'}",
                    key=f"total_group_{group}",
                    disabled=not group_numbers,
                )
            if checked:
                selected_groups.append(group)
        selected_group_numbers = sorted(
            number
            for group in selected_groups
            for number in group_pools[group]
        )
        with st.container(key="load_total_pool_container"):
            st.button(
                "將所選組別加入聰明組合",
                on_click=load_total_pool_into_wheeling,
                args=(selected_group_numbers,),
                disabled=not selected_group_numbers,
                icon=":material/input:",
                key="load_total_pool_to_wheeling",
                width="stretch",
            )
        with st.container(key="reset_total_group_container"):
            st.button(
                "重設",
                on_click=reset_total_group_selection,
                key="reset_total_group_selection",
                icon=":material/refresh:",
                width="stretch",
            )
        st.caption("勾選 A、B、C、D 任意一組或多組，再加入聰明組合。")
    render_wheeling_system(total_pool)


