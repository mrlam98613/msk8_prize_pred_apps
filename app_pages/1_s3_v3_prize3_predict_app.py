from __future__ import annotations

import contextlib
import importlib.util
import io
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import streamlit as st

from app_pages.shared_style import apply_new_page_style


PROJECT_ROOT = Path(__file__).resolve().parents[1]
S3_SCRIPT = PROJECT_ROOT / "S3_ABCD_prize3_Banker_leg_app" / "s3_v3_prize3_predict_app.py"


@st.cache_resource(show_spinner=False)
def load_s3_v3_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("s3_v3_prize3_predict_web", S3_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"未能載入：{S3_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_prediction(
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
    module = cast(Any, load_s3_v3_module())
    module.MODE = "predict"
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

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        module.main()
    return output.getvalue()


def main() -> None:
    st.set_page_config(page_title="S3 v3 下期預測", page_icon="📌", layout="wide")
    apply_new_page_style()
    st.html(
        """
        <style>
        .block-container { max-width: none !important; }
        div[data-testid="stCodeBlock"] { width: 100% !important; }
        div[data-testid="stCodeBlock"] pre {
            white-space: pre !important;
            overflow-x: auto !important;
            overflow-y: hidden !important;
        }
        </style>
        """
    )
    st.write("3獎下期預測候選球池。")
    st.caption("A（1-9）、B（10-20）、C（21-31）、D（32-40），開獎號範圍 1-40。")

    with st.form("s3_v3_prize3_predict_parameters_form_v1", border=True):
        st.subheader("預測參數")
        window_count = st.number_input("窗口期", min_value=7, value=19, step=1)
        select_groups = st.multiselect("ABCD 組別", [1, 2, 3, 4], default=[1, 2, 3, 4])
        match_mode = st.selectbox("查詢條件", [">=", "==", "<="], index=0)
        combination_take_count = st.number_input("條件開號組合", min_value=0, value=5, step=1)
        prize_option = st.number_input("中獎獎項（3 獎）", min_value=1, max_value=3, value=3, step=1)
        prize_print_show = st.checkbox("顯示中獎注數", value=False)
        prize_unit_sort = st.selectbox("中獎注數搜尋條件 >=", [">=", "==", "<="], index=0)
        prize_unit_count = st.number_input("中獎注數", min_value=0, value=80, step=1)
        prize_max_count = st.number_input("中獎注數排序最前 N 期", min_value=1, value=10, step=1)
        prize_date_sort = st.checkbox("中獎注數排序預設日期", value=True)
        submitted = st.form_submit_button("產生下期預測", type="primary", width="stretch")

    if submitted:
        if not select_groups:
            st.error("最少需要選擇一個 ABCD 組別。")
        else:
            st.cache_resource.clear()
            with st.spinner("正在產生下期預測並存檔..."):
                st.session_state["s3_v3_prediction_output"] = run_prediction(
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
            st.success("預測候選球池已產生並存入 prize3_predict_ball/")

    output = st.session_state.get("s3_v3_prediction_output")
    if output:
        st.subheader("下期預測結果")
        st.code(output, language="text", wrap_lines=False)
    else:
        st.info("請先輸入參數，再按「產生下期預測」。")

