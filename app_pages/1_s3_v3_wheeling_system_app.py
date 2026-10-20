from __future__ import annotations

import csv
import itertools
import random
import re
import unicodedata
from pathlib import Path

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


def build_wheeling_tickets(
    numbers: list[int],
    ticket_size: int,
    max_ticket_count: int,
) -> list[tuple[int, ...]]:
    """依候選球池產生固定球數的投注組合，並受注數上限保護。"""
    return list(itertools.islice(itertools.combinations(numbers, ticket_size), max_ticket_count))


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
    candidate_text = st.text_input(
        "候選號碼（逗號或空格分隔）",
        key="wheeling_candidate_numbers",
    )
    ticket_mode = st.selectbox(
        "投注模式",
        ["6字單式", "7字複式"],
        key="wheeling_ticket_mode",
    )
    guarantee = st.selectbox(
        "保證條件",
        [(5, 5), (4, 4), (4, 3)],
        format_func=lambda item: f"中{item[0]}保{item[1]}",
        key="wheeling_guarantee",
    )
    max_ticket_count = st.number_input(
        "最多產生注數",
        min_value=1,
        max_value=5000,
        value=100,
        step=1,
        key="wheeling_max_ticket_count",
    )

    if st.button(
        "產生投注組合",
        key="wheeling_generate",
        icon=":material/confirmation_number:",
        width="stretch",
    ):
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
                ticket_size = 6 if ticket_mode == "6字單式" else 7
                if len(numbers) < ticket_size:
                    st.session_state["wheeling_result"] = None
                    st.error(f"候選號碼不足 {ticket_size} 個，不能產生投注組合。")
                else:
                    tickets = build_wheeling_tickets(
                        numbers, ticket_size, int(max_ticket_count)
                    )
                    st.session_state["wheeling_result"] = {
                        "numbers": numbers,
                        "tickets": tickets,
                        "ticket_mode": ticket_mode,
                        "match_if": guarantee[0],
                        "guarantee": guarantee[1],
                    }

    result = st.session_state.get("wheeling_result")
    if not isinstance(result, dict):
        return

    tickets = result["tickets"]
    match_if = int(result["match_if"])
    guarantee_count = int(result["guarantee"])
    st.write(
        f"方案：{result['ticket_mode']}，中{match_if}保{guarantee_count}，"
        f"候選球池 {len(result['numbers'])} 球，已產生 {len(tickets)} 注。"
    )
    if len(tickets) >= int(max_ticket_count):
        st.info("已達到注數上限；如需更多組合，請提高最多產生注數。")

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
            f"-- 隨機核對驗證：每次隨機開出 {match_if} 球，保中 {guarantee_count} 球"
        ]
        for _ in range(3):
            draw_numbers = tuple(sorted(rng.sample(result["numbers"], match_if)))
            winning_tickets = find_wheeling_hits(tickets, draw_numbers, guarantee_count)
            if not winning_tickets:
                continue
            ticket_index, ticket, hits = winning_tickets[0]
            verification_lines.append(
                f"第 {ticket_index:03d} 組：{format_wheeling_numbers(ticket)}，"
                f"中 {format_wheeling_numbers(hits)}"
            )
        st.code("\n".join(verification_lines), language="text", wrap_lines=False)


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
    """將目前分類的總候選球池帶入下方投注輸入框。"""
    st.session_state["wheeling_candidate_numbers"] = ", ".join(
        str(number) for number in numbers
    )


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
    with st.container(border=True):
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
        if add_col.button("加入候選池", key=f"add_{category_key}", width="stretch"):
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

    if st.button("讀入預測球", icon=":material/download:", width="stretch"):
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

    with st.container(border=True):
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
        st.code(f"{total_pool} /> {len(total_pool)} 球", language="text", wrap_lines=False)
        st.button(
            "將總候選球池加入聰明組合",
            on_click=load_total_pool_into_wheeling,
            args=(total_pool,),
            disabled=not total_pool,
            icon=":material/input:",
            key="load_total_pool_to_wheeling",
            width="stretch",
        )
        st.caption("加入後可在下方修改候選號碼，再產生投注組合。")
    render_wheeling_system(total_pool)


