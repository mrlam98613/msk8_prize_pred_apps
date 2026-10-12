from __future__ import annotations

import contextlib
import importlib.util
import io
from pathlib import Path
from types import ModuleType

import streamlit as st

from app_pages.shared_style import apply_new_page_style, page_header, section_title


PROJECT_ROOT = Path(__file__).resolve().parents[1]
S1_V2_SCRIPT = PROJECT_ROOT / "S1_ABCD_apps" / "s1_v2_multi_group_analyze.py"

DEFAULT_WINDOW_COUNT = 19
DEFAULT_SELECT_GROUPS = "1,2,3,4"
DEFAULT_COMBINATION_TAKE_COUNT = 3
DEFAULT_COMB_MATCH_MODE = ">="
DEFAULT_LOTTO_LIST = False
DEFAULT_PRIZE_OPTION = 3
DEFAULT_PRIZE_PRINT_SHOW = False


@st.cache_resource(show_spinner=False)
def load_s1_v2_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("s1_v2_multi_group_web", S1_V2_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"未能載入：{S1_V2_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_group_text(raw_text: str) -> tuple[int, ...]:
    cleaned = (
        raw_text.replace("[", " ")
        .replace("]", " ")
        .replace("(", " ")
        .replace(")", " ")
        .replace("，", ",")
    )
    group_ids: list[int] = []
    for item in cleaned.split(","):
        item = item.strip()
        if not item:
            continue
        group_id = int(item)
        if group_id not in (1, 2, 3, 4):
            raise ValueError("SELECT_GROUPS 只可輸入 1,2,3,4")
        if group_id not in group_ids:
            group_ids.append(group_id)
    if not group_ids:
        raise ValueError("SELECT_GROUPS 最少需要輸入一組，例如 1 或 1,2,3,4")
    return tuple(group_ids)


def run_predict_analysis(
    window_count: int,
    select_groups_text: str,
    combination_take_count: int,
    comb_match_mode: str,
    lotto_list: bool,
    prize_option: int,
    prize_print_show: bool,
) -> str:
    module = load_s1_v2_module()
    select_groups = parse_group_text(select_groups_text)

    module.MODE = "predict"
    module.BACKTEST_DRAW_COUNT_LIST = [window_count]
    module.WINDOW_DRAW_COUNT_LIST = [window_count]
    module.SELECT_GROUPS = select_groups
    module.COMBINATION_TAKE_COUNT = combination_take_count
    module.COMB_MATCH_MODE = comb_match_mode
    module.LOTTO_LIST = lotto_list
    module.PRIZE_OPTION = prize_option
    module.PRIZE_PRINT_SHOW = prize_print_show
    module.PRINT_BACKTEST_MODE = "detail"

    draws = module.read_draws()
    next_draw_date = module.read_next_draw_date()

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        module.print_query_setting()
        module.print_predict_window(draws, window_count, next_draw_date)
    return buffer.getvalue()


def init_state() -> None:
    st.session_state.setdefault("s1_v2_window_count", DEFAULT_WINDOW_COUNT)
    st.session_state.setdefault("s1_v2_select_groups", DEFAULT_SELECT_GROUPS)
    st.session_state.setdefault("s1_v2_take_count", DEFAULT_COMBINATION_TAKE_COUNT)
    st.session_state.setdefault("s1_v2_match_mode", DEFAULT_COMB_MATCH_MODE)
    st.session_state.setdefault("s1_v2_lotto_list", DEFAULT_LOTTO_LIST)
    st.session_state.setdefault("s1_v2_prize_option", DEFAULT_PRIZE_OPTION)
    st.session_state.setdefault("s1_v2_prize_print_show", DEFAULT_PRIZE_PRINT_SHOW)


def main() -> None:
    init_state()
    apply_new_page_style()
    page_header("S1 v2 ABCD 分組 predict 分析", "讀取 S1 v2 核心分析邏輯，包含最後一期開獎號。")

    with st.form("s1_v2_params", border=True):
        st.subheader("查詢參數")
        col1, col2, col3 = st.columns(3)
        with col1:
            window_count = st.number_input(
                "預測窗口期",
                min_value=7,
                max_value=80,
                step=1,
                key="s1_v2_window_count",
            )
            combination_take_count = st.number_input(
                "COMBINATION_TAKE_COUNT",
                min_value=0,
                max_value=7,
                step=1,
                key="s1_v2_take_count",
            )
        with col2:
            select_groups_text = st.text_input(
                "SELECT_GROUPS",
                help="不用括號，例如：1 或 1,2,3,4",
                key="s1_v2_select_groups",
            )
            comb_match_mode = st.selectbox(
                "COMB_MATCH_MODE",
                [">=", "==", "<="],
                key="s1_v2_match_mode",
            )
        with col3:
            prize_option = st.number_input(
                "PRIZE_OPTION",
                min_value=1,
                max_value=7,
                step=1,
                key="s1_v2_prize_option",
            )
            lotto_list = st.checkbox("LOTTO_LIST", key="s1_v2_lotto_list")
            prize_print_show = st.checkbox("PRIZE_PRINT_SHOW", key="s1_v2_prize_print_show")

        submitted = st.form_submit_button("執行 predict 分析", icon=":material/play_arrow:")

    if submitted:
        try:
            output = run_predict_analysis(
                int(window_count),
                select_groups_text,
                int(combination_take_count),
                comb_match_mode,
                bool(lotto_list),
                int(prize_option),
                bool(prize_print_show),
            )
        except Exception as exc:  # noqa: BLE001
            st.error(f"分析失敗：{exc}")
        else:
            section_title("S1 v2 predict 分析結果")
            st.code(output, language="text")
    else:
        st.info("設定參數後，按「執行 predict 分析」。預設會讀取 trend_pred.csv 顯示下期系統預測走趨。")


if __name__ == "__main__":
    main()
