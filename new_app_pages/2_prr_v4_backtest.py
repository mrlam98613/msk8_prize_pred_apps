from __future__ import annotations

import pandas as pd
import streamlit as st

from new_app_pages.prr_v4_web_engine import compute_backtest
from new_app_pages.shared_style import apply_new_page_style, page_header, section_title


def nums_text(nums: list[int]) -> str:
    return "[" + ",".join(str(num) for num in nums) + "]"


def render_group_card(group: dict[str, object]) -> None:
    """Render one A-D group in a compact mobile-friendly block."""
    with st.expander(f"{group['code']}組 {group['name']}，最終 {nums_text(group['final_nums'])}", expanded=False):
        cols = st.columns(2)
        cols[0].metric("配額", group["quota"])
        cols[1].metric("窗口符合", f"{group['matched_count']}/{group['total_count']}", f"{group['matched_percent']:.0f}%")
        st.markdown(f"**權重熱號**：`{nums_text(group['hot_nums'])}`")
        st.markdown(f"**高頻膽號**：`{nums_text(group['dan_nums'])}`")
        st.markdown(f"**高頻配腳號**：`{nums_text(group['partner_nums'])}`")
        st.markdown(f"**弱號**：`{nums_text(group['weak_nums'])}`")
        st.dataframe(pd.DataFrame(group["top_weights"]), hide_index=True)
        with st.expander("窗口明細", expanded=False):
            st.dataframe(pd.DataFrame(group["detail_rows"]), hide_index=True)


def main() -> None:
    apply_new_page_style()
    page_header("PRR v4 回測", "手機版分層檢視：摘要、每期核對、A/B/C/D 分組分析。")

    with st.form("v4_backtest_params"):
        section_title("參數")
        backtest_count = st.number_input("回測期", min_value=1, max_value=500, value=2, step=1)
        window_count = st.number_input("窗口期", min_value=1, max_value=200, value=18, step=1)
        submitted = st.form_submit_button("執行回測", icon=":material/play_arrow:")

    if not submitted:
        st.info("預設參數：MODE=backtest，BACKTEST_DRAW_COUNT_LIST=[2]，WINDOW_DRAW_COUNT_LIST=[18]。")
        return

    with st.skeleton(height=220):
        result = compute_backtest(int(backtest_count), int(window_count))

    section_title("命中統計")
    cols = st.columns(4)
    cols[0].metric("回測期", result["backtest_count"])
    cols[1].metric("窗口期", result["window_count"])
    cols[2].metric("候選球", result["prediction_count"])
    cols[3].metric("基礎配額", result["base_quota_text"])

    st.dataframe(pd.DataFrame(result["hit_summary"]), hide_index=True)
    st.caption("分組比例隨機組合 9 球")
    st.dataframe(pd.DataFrame(result["random_hit_summary"]), hide_index=True)

    section_title("逐期回測")
    for period in result["periods"]:
        label = f"{period['display_index']}. {period['check_date']}｜命中 {period['hit_count']} 球"
        with st.expander(label, expanded=True):
            st.markdown(f"**核對號碼**：`{period['check_nums']}`")
            st.markdown(f"**本期配額**：{period['take_counts_text']}")
            st.markdown(f"**預測候選**：`{nums_text(period['pred_nums'])}`")
            st.caption(period["hit_text"])
            st.markdown(f"**隨機 9 球**：`{nums_text(period['random_nums'])}`")
            st.caption(period["random_hit_text"])

            with st.expander("四種屬性", expanded=False):
                st.write(period["missing_text"])
                for line in period["high_freq_lines"]:
                    st.write(line)
                for line in period["weak_lines"]:
                    st.write(line)
                for line in period["condition_lines"]:
                    st.caption(line)

            for group_code in ["A", "B", "C", "D"]:
                render_group_card(period["groups"][group_code])
