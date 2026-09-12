from pathlib import Path
import csv
import html
import sys
from typing import TypedDict

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from css import white_black_style


M6_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"

DEFAULT_RECENT_DRAW_COUNT = 24
DEFAULT_MIN_SELECTED_COUNT = 3
DEFAULT_MATCH_MODE = ">="
DEFAULT_NUM_MIN = 1
DEFAULT_NUM_MAX = 31
DEFAULT_PRIZE_OPTION = 3
DEFAULT_SHOW_PRIZE_COUNT = True


class MatchedDraw(TypedDict):
    index: int
    date: str
    selected_nums: str
    selected_count: float
    prize_count: str
    display_text: str


def get_file_signature(path: Path) -> tuple[int, int]:
    if not path.exists():
        return (0, 0)
    stat = path.stat()
    return (stat.st_mtime_ns, stat.st_size)


@st.cache_data(show_spinner=False)
def read_m6_lotto_history(file_signature: tuple[int, int]) -> list[dict[str, str]]:
    _ = file_signature
    if not M6_CSV.exists():
        return []

    with M6_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames:
            reader.fieldnames = [name.strip().lstrip("\ufeff") for name in reader.fieldnames]
        return [
            {(key or "").strip().lstrip("\ufeff"): (value or "").strip() for key, value in row.items()}
            for row in reader
        ]


def parse_draw_numbers(row: dict[str, str]) -> list[int]:
    nums = []
    for idx in range(1, 7):
        try:
            nums.append(int(row.get(f"N{idx}", "")))
        except ValueError:
            nums.append(0)
    return nums


def parse_special_number(row: dict[str, str]) -> int | None:
    try:
        special = int(row.get("N7", ""))
    except ValueError:
        return None
    return special if 1 <= special <= 49 else None


def format_prize_count(value: str) -> str:
    try:
        return f"{float(value):g}"
    except ValueError:
        return "0"


def validate_params(num_min: int, num_max: int, selected_count: int) -> str:
    if num_min < 1 or num_max > 49:
        return "查詢號碼範圍必須介乎 1 至 49。"
    if num_min > num_max:
        return "查詢範圍最小號碼不可大於最大號碼。"
    if selected_count < 1 or selected_count > 6:
        return "符合號碼數量必須介乎 1 至 6。"
    return ""


def match_selected_count(count: int, target_count: int, match_mode: str) -> bool:
    if match_mode == "==":
        return count == target_count
    return count >= target_count


def should_include_special(match_mode: str, target_count: int, main_count: int) -> bool:
    return match_mode == ">=" and target_count >= 3 and main_count >= target_count


def build_display_text(
    index: int,
    date: str,
    selected_nums: str,
    selected_count: float,
    prize_count: str,
    show_prize_count: bool,
) -> str:
    display_text = (
        f"{index:>3} {date} : "
        f"{selected_nums} /> {selected_count:g} 球"
    )
    if show_prize_count:
        display_text += f" /> {prize_count}"
    return display_text


def build_matched_rows(
    rows: list[dict[str, str]],
    recent_draw_count: int,
    min_selected_count: int,
    match_mode: str,
    num_min: int,
    num_max: int,
    prize_option: int,
    show_prize_count: bool,
) -> list[MatchedDraw]:
    recent_rows = rows[-recent_draw_count:]
    matched_rows: list[MatchedDraw] = []
    prize_key = f"prize{prize_option}"

    for row in recent_rows:
        nums = parse_draw_numbers(row)
        special = parse_special_number(row)
        selected_nums = [num for num in nums if num_min <= num <= num_max]
        if not match_selected_count(len(selected_nums), min_selected_count, match_mode):
            continue

        display_nums = [str(num) for num in selected_nums]
        selected_count = float(len(selected_nums))
        if (
            special is not None
            and num_min <= special <= num_max
            and should_include_special(match_mode, min_selected_count, len(selected_nums))
        ):
            display_nums.append(f"*{special}")
            selected_count += 0.5

        selected_nums_text = ",".join(display_nums)
        prize_count = format_prize_count(row.get(prize_key, ""))
        matched_rows.append(
            {
                "index": len(matched_rows) + 1,
                "date": row.get("nDdate", ""),
                "selected_nums": selected_nums_text,
                "selected_count": selected_count,
                "prize_count": prize_count,
                "display_text": build_display_text(
                    len(matched_rows) + 1,
                    row.get("nDdate", ""),
                    selected_nums_text,
                    selected_count,
                    prize_count,
                    show_prize_count,
                ),
            }
        )

    return matched_rows


def render_text_result(rows: list[MatchedDraw]) -> None:
    if not rows:
        st.info("沒有符合條件的期數。")
        return

    lines = "<br>".join(html.escape(row["display_text"]) for row in rows)
    st.markdown(
        f"<div class='prize-text-result'>{lines}</div>",
        unsafe_allow_html=True,
    )


def render_result_table(table_rows: list[dict[str, object]]) -> None:
    if not table_rows:
        return

    headers = list(table_rows[0].keys())
    header_html = "".join(f"<th>{html.escape(str(header))}</th>" for header in headers)
    body_rows = []
    for row in table_rows:
        cells = "".join(
            f"<td>{html.escape(str(row.get(header, '')))}</td>"
            for header in headers
        )
        body_rows.append(f"<tr>{cells}</tr>")

    st.markdown(
        f"""
        <div class="prize-table-wrap">
            <table class="prize-result-table">
                <thead><tr>{header_html}</tr></thead>
                <tbody>{''.join(body_rows)}</tbody>
            </table>
        </div>
        """,
        unsafe_allow_html=True,
    )


def reset_query_state() -> None:
    st.session_state["prize_comb_key_has_query"] = False
    st.session_state["prize_comb_key_params"] = {}


def main() -> None:
    st.markdown(white_black_style, unsafe_allow_html=True)
    st.title("獎項組合關鍵分析")

    st.markdown(
        """
        <style>
        .param-title {
            font-size: 1rem;
            font-weight: 900;
            margin: 0.55rem 0 0.2rem;
        }
        .result-title {
            font-size: 1.08rem;
            font-weight: 900;
            margin: 1rem 0 0.45rem;
        }
        .prize-text-result {
            background: #ffffff !important;
            color: #000000 !important;
            border: 1px solid #b8b8b8;
            border-radius: 6px;
            padding: 10px 12px;
            margin: 0.35rem 0 0.85rem;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 0.92rem;
            line-height: 1.55;
            overflow-x: auto;
            white-space: nowrap;
        }
        .prize-table-wrap {
            width: 100%;
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
            border: 1px solid #b8b8b8;
            border-radius: 6px;
            background: #ffffff !important;
            margin-top: 0.6rem;
        }
        .prize-result-table {
            width: 100%;
            min-width: 520px;
            border-collapse: collapse;
            background: #ffffff !important;
            color: #000000 !important;
            font-size: 0.92rem;
        }
        .prize-result-table th,
        .prize-result-table td {
            background: #ffffff !important;
            color: #000000 !important;
            border-bottom: 1px solid #dddddd;
            padding: 7px 8px;
            text-align: left;
            white-space: nowrap;
        }
        .prize-result-table th {
            font-weight: 900;
            background: #f3f5f7 !important;
        }
        @media (max-width: 430px) {
            [data-testid="stNumberInput"],
            [data-testid="stSelectbox"] {
                margin-bottom: 0.35rem;
            }
            [data-testid="stNumberInput"] input {
                min-height: 40px !important;
            }
            .prize-text-result {
                font-size: 0.84rem;
                padding: 9px 10px;
            }
            .prize-result-table {
                min-width: 480px;
                font-size: 0.84rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.session_state.setdefault("prize_comb_key_has_query", False)
    st.session_state.setdefault("prize_comb_key_params", {})

    st.markdown("<div class='param-title'>分析參數</div>", unsafe_allow_html=True)
    with st.form("prize_comb_key_form"):
        recent_draw_count = st.number_input(
            "回測期數",
            min_value=1,
            max_value=2000,
            value=DEFAULT_RECENT_DRAW_COUNT,
            step=1,
        )
        min_selected_count = st.number_input(
            "符合號碼數量",
            min_value=1,
            max_value=6,
            value=DEFAULT_MIN_SELECTED_COUNT,
            step=1,
        )
        match_mode = st.selectbox("數量條件", [">=", "=="], index=0)
        num_min = st.number_input(
            "查詢範圍最小號碼",
            min_value=1,
            max_value=49,
            value=DEFAULT_NUM_MIN,
            step=1,
        )
        num_max = st.number_input(
            "查詢範圍最大號碼",
            min_value=1,
            max_value=49,
            value=DEFAULT_NUM_MAX,
            step=1,
        )
        prize_option = st.selectbox("顯示獎項注數", [1, 2, 3], index=2)

        col_show, col_sort = st.columns(2)
        with col_show:
            show_prize_count = st.checkbox("顯示中獎注數", value=DEFAULT_SHOW_PRIZE_COUNT)
        with col_sort:
            sort_by_prize_count = st.checkbox("依中獎注數排序（大到小）", value=False)

        submitted = st.form_submit_button("查詢", type="primary")
        reset_clicked = st.form_submit_button("Reset", type="secondary")

    if reset_clicked:
        reset_query_state()
        st.rerun()

    if submitted:
        st.session_state["prize_comb_key_has_query"] = True
        st.session_state["prize_comb_key_params"] = {
            "recent_draw_count": int(recent_draw_count),
            "min_selected_count": int(min_selected_count),
            "match_mode": match_mode,
            "num_min": int(num_min),
            "num_max": int(num_max),
            "prize_option": int(prize_option),
            "show_prize_count": bool(show_prize_count),
            "sort_by_prize_count": bool(sort_by_prize_count),
        }

    if not st.session_state["prize_comb_key_has_query"]:
        return

    params = st.session_state["prize_comb_key_params"]
    recent_draw_count = params["recent_draw_count"]
    min_selected_count = params["min_selected_count"]
    match_mode = params["match_mode"]
    num_min = params["num_min"]
    num_max = params["num_max"]
    prize_option = params["prize_option"]
    show_prize_count = params["show_prize_count"]
    sort_by_prize_count = params["sort_by_prize_count"]

    error = validate_params(int(num_min), int(num_max), int(min_selected_count))
    if error:
        st.error(error)
        return

    rows = read_m6_lotto_history(get_file_signature(M6_CSV))
    if not rows:
        st.warning(f"找不到或未能讀取 M6 檔案：{M6_CSV}")
        return

    matched_rows = build_matched_rows(
        rows=rows,
        recent_draw_count=int(recent_draw_count),
        min_selected_count=int(min_selected_count),
        match_mode=match_mode,
        num_min=int(num_min),
        num_max=int(num_max),
        prize_option=int(prize_option),
        show_prize_count=show_prize_count,
    )
    if sort_by_prize_count:
        matched_rows.sort(key=lambda row: float(row["prize_count"]), reverse=True)
        for index, row in enumerate(matched_rows, start=1):
            row["index"] = index
            row["display_text"] = build_display_text(
                index,
                row["date"],
                row["selected_nums"],
                row["selected_count"],
                row["prize_count"],
                show_prize_count,
            )

    include_special_text = (
        "N1-N7"
        if should_include_special(str(match_mode), int(min_selected_count), int(min_selected_count))
        else "N1-N6"
    )
    prize_text = f"顯示 {prize_option} 中獎注數" if show_prize_count else "不顯示中獎注數"
    sort_text = "，依中獎注數由大到小排序" if sort_by_prize_count else ""
    st.markdown(
        f"<div class='result-title'>最近 {int(recent_draw_count)} 期，"
        f"{include_special_text} 包含 {int(num_min)}-{int(num_max)} 號數量 "
        f"{match_mode} {int(min_selected_count)}，{prize_text}{sort_text}</div>",
        unsafe_allow_html=True,
    )

    render_text_result(matched_rows)

    if matched_rows:
        table_rows = [
            {
                "序號": row["index"],
                "日期": row["date"],
                f"{int(num_min)}-{int(num_max)}開獎號": row["selected_nums"],
                "數量": row["selected_count"],
                f"prize{prize_option} 注數": row["prize_count"],
            }
            for row in matched_rows
        ]
        if not show_prize_count:
            for row in table_rows:
                row.pop(f"prize{prize_option} 注數", None)

        render_result_table(table_rows)


if __name__ == "__main__":
    main()
