from __future__ import annotations

import contextlib
import importlib.util
import io
from pathlib import Path
from types import ModuleType

import streamlit as st

from app_pages.shared_style import apply_new_page_style, page_header, section_title


PROJECT_ROOT = Path(__file__).resolve().parents[1]
S1_V2_COMBO_SCRIPT = PROJECT_ROOT / "S1_ABCD_apps" / "s1_v2_combo_trend_analyze.py"
TREND_PRED_CSV = PROJECT_ROOT / "S1_ABCD_apps" / "backtest_pred_data" / "trend_pred.csv"

DEFAULT_WINDOW_COUNT = 19
DEFAULT_SELECT_GROUPS = "1,2,3,4"
DEFAULT_COMBINATION_TAKE_COUNT = 3
DEFAULT_COMB_MATCH_MODE = ">="
DEFAULT_LOTTO_LIST = False


@st.cache_resource(show_spinner=False)
def load_combo_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("s1_v2_combo_trend_web", S1_V2_COMBO_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"未能載入：{S1_V2_COMBO_SCRIPT}")
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


def run_predict_combo_trend(
    window_count: int,
    select_groups_text: str,
    combination_take_count: int,
    comb_match_mode: str,
    lotto_list: bool,
) -> tuple[str, dict[str, object]]:
    module = load_combo_module()
    select_groups = parse_group_text(select_groups_text)

    module.MODE = "predict"
    module.BACKTEST_DRAW_COUNT_LIST = [window_count]
    module.WINDOW_DRAW_COUNT_LIST = [window_count]
    module.SELECT_GROUPS = select_groups
    module.COMBINATION_TAKE_COUNT = combination_take_count
    module.COMB_MATCH_MODE = comb_match_mode
    module.LOTTO_LIST = lotto_list

    draws = module.read_draws()
    next_draw_infos = module.read_next_draw_infos()
    record = module.build_predict_trend_record(draws, window_count, next_draw_infos)

    module.write_csv_rows(TREND_PRED_CSV, [record])
    module.write_csv_rows(module.TREND_PRED_CSV, [record])

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        module.print_query_setting()
        module.print_predict_window(draws, window_count, next_draw_infos)
        print()
        print(f"predict CSV 已寫入：{TREND_PRED_CSV}")
    return buffer.getvalue(), record


def init_state() -> None:
    st.session_state.setdefault("s1_v2_combo_window_count", DEFAULT_WINDOW_COUNT)
    st.session_state.setdefault("s1_v2_combo_select_groups", DEFAULT_SELECT_GROUPS)
    st.session_state.setdefault("s1_v2_combo_take_count", DEFAULT_COMBINATION_TAKE_COUNT)
    st.session_state.setdefault("s1_v2_combo_match_mode", DEFAULT_COMB_MATCH_MODE)
    st.session_state.setdefault("s1_v2_combo_lotto_list", DEFAULT_LOTTO_LIST)


def main() -> None:
    init_state()
    apply_new_page_style()
    page_header("S1 v2 組合走趨 predict 分析", "包含最後一期開獎號，執行後寫入 trend_pred.csv。")

    with st.form("s1_v2_combo_params", border=True):
        st.subheader("查詢參數")
        col1, col2 = st.columns(2)
        with col1:
            window_count = st.number_input(
                "回測期 / 窗口期",
                min_value=7,
                max_value=80,
                step=1,
                key="s1_v2_combo_window_count",
            )
            select_groups_text = st.text_input(
                "SELECT_GROUPS",
                help="不用括號，例如：1 或 1,2,3,4",
                key="s1_v2_combo_select_groups",
            )
        with col2:
            combination_take_count = st.number_input(
                "COMBINATION_TAKE_COUNT",
                min_value=0,
                max_value=7,
                step=1,
                key="s1_v2_combo_take_count",
            )
            comb_match_mode = st.selectbox(
                "COMB_MATCH_MODE",
                [">=", "==", "<="],
                key="s1_v2_combo_match_mode",
            )
            lotto_list = st.checkbox("LOTTO_LIST", key="s1_v2_combo_lotto_list")

        submitted = st.form_submit_button("執行 combo trend predict", icon=":material/play_arrow:")

    if submitted:
        try:
            output, record = run_predict_combo_trend(
                int(window_count),
                select_groups_text,
                int(combination_take_count),
                comb_match_mode,
                bool(lotto_list),
            )
        except Exception as exc:  # noqa: BLE001
            st.error(f"分析失敗：{exc}")
        else:
            section_title("trend_pred.csv 下期預測")
            st.table([record])
            section_title("S1 v2 combo trend predict 分析結果")
            st.code(output, language="text")
    else:
        st.info("設定參數後，按「執行 combo trend predict」。結果會覆蓋寫入 trend_pred.csv。")


if __name__ == "__main__":
    main()
