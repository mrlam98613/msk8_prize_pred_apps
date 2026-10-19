from __future__ import annotations

import contextlib
import importlib.util
import io
import re
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import streamlit as st

from app_pages.shared_style import apply_new_page_style, page_header


PROJECT_ROOT = Path(__file__).resolve().parents[1]
S3_SCRIPT = PROJECT_ROOT / "S3_ABCD_prize3_Banker_leg_app" / "s3_v2_ABCD_search_prize3_app.py"

DEFAULT_BACKTEST_COUNT = 1
DEFAULT_WINDOW_COUNT = 25
DEFAULT_SELECT_GROUPS = (1, 2, 3, 4)
DEFAULT_MATCH_MODE = ">="
DEFAULT_TAKE_COUNT = 5
DEFAULT_PRIZE_COUNT = 80
DEFAULT_PRIZE_MAX_COUNT = 10
DEFAULT_PRIZE_DATE_SORT = True


@st.cache_resource(show_spinner=False)
def load_s3_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("s3_v2_prize3_backtest_web", S3_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"未能載入：{S3_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_analysis(
    backtest_count: int,
    window_count: int,
    select_groups: tuple[int, ...],
    match_mode: str,
    combination_take_count: int,
    prize_option: int,
    prize_print_show: bool,
    prize_unit_sort: str,
    prize_unit_count: int,
    prize_max_count: int,
    prize_date_sort: bool,
) -> str:
    module = cast(Any, load_s3_module())
    module.MODE = "backtest"
    module.BACKTEST_DRAW_COUNT_LIST = [backtest_count]
    module.WINDOW_DRAW_COUNT_LIST = [window_count]
    module.SELECT_GROUPS = select_groups
    module.COMB_MATCH_MODE = match_mode
    module.COMBINATION_TAKE_COUNT = combination_take_count
    module.PRIZE_OPTION = prize_option
    module.PRIZE_PRINT_SHOW = prize_print_show
    module.prize3_sort_mode = True
    module.prize3_unit_sort = prize_unit_sort
    module.prize3_unit_count = prize_unit_count
    module.prize3_max_count = prize_max_count
    module.prize3_date_sort = prize_date_sort
    module.PRINT_PRIZE3_PROPERTY_ANALYSIS = True

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        module.main()
    return compact_separators(output.getvalue())


def compact_separators(output: str) -> str:
    output = re.sub(r"-{3,}", "--", output)
    output = re.sub(r"={3,}", "==", output)
    return output


def last_backtest_block(output: str) -> str:
    lines = output.splitlines()
    starts = [index for index, line in enumerate(lines) if line.startswith("======[回測")]
    if not starts:
        return output.strip()
    start = starts[-1]
    return "\n".join(lines[start:]).strip()


def split_summary(output: str) -> tuple[str, str]:
    lines = output.splitlines()
    summary_start = next(
        (index for index, line in enumerate(lines) if line.startswith("----- 回測期")),
        len(lines),
    )
    detail = "\n".join(lines[:summary_start]).strip()
    summary = "\n".join(lines[summary_start:]).strip()
    return detail, summary


def main() -> None:
    st.set_page_config(page_title="S3 v2 3 獎回測", page_icon="📊", layout="centered")
    apply_new_page_style()
    page_header("S3 v2 3 獎回測", "只顯示最後一期回測明細及各組統計。")

    with st.form("s3_v2_prize3_count_backtest_parameters_form_v1", border=True):
        st.subheader("回測參數")
        backtest_count = st.number_input("回測期", min_value=1, value=DEFAULT_BACKTEST_COUNT, step=1)
        window_count = st.number_input("窗口期", min_value=7, value=DEFAULT_WINDOW_COUNT, step=1)
        select_groups = st.multiselect("SELECT_GROUPS", [1, 2, 3, 4], default=list(DEFAULT_SELECT_GROUPS))
        match_mode = st.selectbox("COMB_MATCH_MODE", [">=", "==", "<="], index=0)
        combination_take_count = st.number_input(
            "COMBINATION_TAKE_COUNT", min_value=0, value=DEFAULT_TAKE_COUNT, step=1
        )
        prize_option = st.number_input("PRIZE_OPTION", min_value=1, max_value=3, value=3, step=1)
        prize_print_show = st.checkbox("PRIZE_PRINT_SHOW", value=False)
        prize_unit_sort = st.selectbox("prize3_unit_sort", [">=", "==", "<="], index=0)
        prize_unit_count = st.number_input("prize3_unit_count", min_value=0, value=DEFAULT_PRIZE_COUNT, step=1)
        prize_max_count = st.number_input("prize3_max_count", min_value=1, value=DEFAULT_PRIZE_MAX_COUNT, step=1)
        prize_date_sort = st.checkbox("prize3_date_sort", value=DEFAULT_PRIZE_DATE_SORT)
        submitted = st.form_submit_button("開始回測", type="primary", width="stretch")

    if not submitted and "s3_v2_output" not in st.session_state:
        st.info("請先確認參數，再按「開始回測」。")
        return
    if submitted:
        st.cache_resource.clear()
        with st.spinner("正在分析..."):
            st.session_state["s3_v2_output"] = run_analysis(
                int(backtest_count),
                int(window_count),
                tuple(select_groups),
                match_mode,
                int(combination_take_count),
                int(prize_option),
                prize_print_show,
                prize_unit_sort,
                int(prize_unit_count),
                int(prize_max_count),
                prize_date_sort,
            )

    output = st.session_state["s3_v2_output"]
    detail, summary = split_summary(last_backtest_block(output))

    st.subheader("最後一期回測")
    st.code(detail, language="text", wrap_lines=True)

    st.subheader("回測統計")
    st.code(summary or "沒有符合條件的統計結果。", language="text", wrap_lines=True)

