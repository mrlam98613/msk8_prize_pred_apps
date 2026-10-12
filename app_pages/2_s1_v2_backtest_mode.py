from __future__ import annotations

import contextlib
import importlib.util
import io
import re
from pathlib import Path
from types import ModuleType

import streamlit as st

from app_pages.shared_style import apply_new_page_style, page_header, section_title


PROJECT_ROOT = Path(__file__).resolve().parents[1]
S1_V2_SCRIPT = PROJECT_ROOT / "S1_ABCD_apps" / "s1_v2_multi_group_analyze.py"

DEFAULT_BACKTEST_COUNT = 10
DEFAULT_WINDOW_COUNT = 19
DEFAULT_SELECT_GROUPS = "1,2,3,4"
DEFAULT_COMBINATION_TAKE_COUNT = 3
DEFAULT_COMB_MATCH_MODE = ">="
DEFAULT_LOTTO_LIST = False
DEFAULT_PRIZE_OPTION = 3
DEFAULT_PRIZE_PRINT_SHOW = False

SUMMARY_TITLES = (
    "全部高頻膽號合併，命中核對期",
    "全部高頻配腳號合併，命中核對期",
    "近 1 期比對，HFB 高頻膽號重開提示",
    "維度球轉RBG分析預測",
)

DETAIL_SECTION_TITLE = "HFB  / HFL / RBG 各預測候選球池，核對回測期"
MAX_DETAIL_SECTIONS = 13


@st.cache_resource(show_spinner=False)
def load_s1_v2_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("s1_v2_multi_group_backtest_web", S1_V2_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"未能載入：{S1_V2_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_int_list_text(raw_text: str, allowed_values: tuple[int, ...] | None = None) -> list[int]:
    cleaned = (
        raw_text.replace("[", " ")
        .replace("]", " ")
        .replace("(", " ")
        .replace(")", " ")
        .replace("，", ",")
    )
    values: list[int] = []
    for item in cleaned.split(","):
        item = item.strip()
        if not item:
            continue
        value = int(item)
        if allowed_values is not None and value not in allowed_values:
            allowed_text = ",".join(str(allowed) for allowed in allowed_values)
            raise ValueError(f"只可輸入：{allowed_text}")
        if value not in values:
            values.append(value)
    if not values:
        raise ValueError("最少需要輸入一個數值")
    return values


def extract_summary_sections(output: str) -> str:
    lines = output.splitlines()
    selected_lines: list[str] = []
    keep = False

    for line in lines:
        if line.startswith("----- 回測期"):
            keep = any(title in line for title in SUMMARY_TITLES)
            if keep:
                if selected_lines:
                    selected_lines.append("")
                selected_lines.append(line)
            continue
        if keep:
            if line.startswith("----- ") or line.startswith("======"):
                keep = False
                continue
            if line.strip():
                selected_lines.append(format_summary_line(line))

    return "\n".join(selected_lines).strip()


def format_summary_line(line: str) -> str:
    match = re.match(r"各回測期候選球池 \[[^\]]*\]，平均期 (.+)", line)
    if match:
        return f"回測期候選球池，平均期 {match.group(1)}"
    return line


def extract_backtest_detail_sections(output: str) -> str:
    lines = output.splitlines()
    sections: list[list[str]] = []
    index = 0

    while index < len(lines):
        line = lines[index]
        if line.startswith("---- HFB") and DETAIL_SECTION_TITLE in line:
            section = [line]
            index += 1
            while index < len(lines):
                next_line = lines[index]
                if next_line.startswith("---- ") or next_line.startswith("======") or next_line.startswith("----- 回測期"):
                    break
                if next_line.strip():
                    section.append(next_line)
                index += 1
            sections.append(section)
            continue
        index += 1

    latest_sections = sections[-MAX_DETAIL_SECTIONS:]
    return "\n\n".join("\n".join(section) for section in latest_sections).strip()


def run_backtest_analysis(
    backtest_count_text: str,
    window_count_text: str,
    select_groups_text: str,
    combination_take_count: int,
    comb_match_mode: str,
) -> tuple[str, str]:
    module = load_s1_v2_module()
    backtest_counts = parse_int_list_text(backtest_count_text)
    window_counts = parse_int_list_text(window_count_text)
    select_groups = tuple(parse_int_list_text(select_groups_text, allowed_values=(1, 2, 3, 4)))

    module.MODE = "backtest"
    module.BACKTEST_DRAW_COUNT_LIST = backtest_counts
    module.WINDOW_DRAW_COUNT_LIST = window_counts
    module.SELECT_GROUPS = select_groups
    module.COMBINATION_TAKE_COUNT = combination_take_count
    module.COMB_MATCH_MODE = comb_match_mode
    module.LOTTO_LIST = DEFAULT_LOTTO_LIST
    module.PRIZE_OPTION = DEFAULT_PRIZE_OPTION
    module.PRIZE_PRINT_SHOW = DEFAULT_PRIZE_PRINT_SHOW
    module.PRINT_BACKTEST_MODE = "detail"

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        module.main()

    output = buffer.getvalue()
    details = extract_backtest_detail_sections(output)
    summary = extract_summary_sections(output)
    return (
        details or "沒有可顯示的回測期命中明細。",
        summary or "沒有可顯示的 4 大項統計。",
    )


def init_state() -> None:
    st.session_state.setdefault("s1_v2_backtest_count_text", str(DEFAULT_BACKTEST_COUNT))
    st.session_state.setdefault("s1_v2_backtest_window_text", str(DEFAULT_WINDOW_COUNT))
    st.session_state.setdefault("s1_v2_backtest_groups_text", DEFAULT_SELECT_GROUPS)
    st.session_state.setdefault("s1_v2_backtest_take_count", DEFAULT_COMBINATION_TAKE_COUNT)
    st.session_state.setdefault("s1_v2_backtest_match_mode", DEFAULT_COMB_MATCH_MODE)


def main() -> None:
    init_state()
    apply_new_page_style()
    page_header("S1 v2 backtest mode", "固定 MODE = backtest，只顯示 4 大項回測統計。")

    with st.form("s1_v2_backtest_params", border=True):
        st.subheader("回測參數")
        col1, col2, col3 = st.columns(3)
        with col1:
            backtest_count_text = st.text_input(
                "BACKTEST_DRAW_COUNT_LIST",
                help="不用括號，例如：10 或 3,10",
                key="s1_v2_backtest_count_text",
            )
            window_count_text = st.text_input(
                "WINDOW_DRAW_COUNT_LIST",
                help="不用括號，例如：19 或 13,19",
                key="s1_v2_backtest_window_text",
            )
        with col2:
            select_groups_text = st.text_input(
                "SELECT_GROUPS",
                help="不用括號，例如：1 或 1,2,3,4",
                key="s1_v2_backtest_groups_text",
            )
            combination_take_count = st.number_input(
                "COMBINATION_TAKE_COUNT",
                min_value=0,
                max_value=7,
                step=1,
                key="s1_v2_backtest_take_count",
            )
        with col3:
            comb_match_mode = st.selectbox(
                "COMB_MATCH_MODE",
                [">=", "==", "<="],
                key="s1_v2_backtest_match_mode",
            )

        submitted = st.form_submit_button("執行 backtest 分析", icon=":material/play_arrow:")

    if submitted:
        try:
            detail_output, summary_output = run_backtest_analysis(
                backtest_count_text,
                window_count_text,
                select_groups_text,
                int(combination_take_count),
                comb_match_mode,
            )
        except Exception as exc:  # noqa: BLE001
            st.error(f"回測失敗：{exc}")
        else:
            section_title("回測期 HFB / HFL / RBG 命中球統計")
            st.code(detail_output, language="text")
            section_title("4 大項回測統計")
            st.code(summary_output, language="text")
    else:
        st.info("設定參數後，按「執行 backtest 分析」。MODE 固定為 backtest。")


if __name__ == "__main__":
    main()
