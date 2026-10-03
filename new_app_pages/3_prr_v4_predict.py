from __future__ import annotations

import pandas as pd
import streamlit as st

from new_app_pages.prr_v4_web_engine import compute_predict
from new_app_pages.shared_style import apply_new_page_style, page_header, section_title


def nums_text(nums: list[int]) -> str:
    return "[" + ",".join(str(num) for num in nums) + "]"


def render_group_card(group: dict[str, object]) -> None:
    """Render one A-D group prediction block."""
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
    page_header("PRR v4 下期預測", "手機版下期候選、投注分組與 A/B/C/D 屬性分析。")

    with st.form("v4_predict_params"):
        section_title("參數")
        window_count = st.number_input("窗口期", min_value=1, max_value=200, value=18, step=1)
        submitted = st.form_submit_button("產生預測", icon=":material/play_arrow:")

    if not submitted:
        st.info("預設參數：MODE=predict，WINDOW_DRAW_COUNT_LIST=[18]。")
        return

    with st.skeleton(height=220):
        result = compute_predict(int(window_count))

    section_title("下期候選")
    cols = st.columns(3)
    cols[0].metric("最後開獎", result["latest_date"])
    cols[1].metric("下期日期", result["next_draw_date"])
    cols[2].metric("窗口期", result["window_count"])
    st.markdown(f"**最後開獎號碼**：`{result['latest_nums']}`")
    st.markdown(f"**本期配額**：{result['take_counts_text']}")
    st.markdown(f"**ABCD 下期預測候選**：`{nums_text(result['pred_nums'])}`")

    section_title("投注分組")
    for bet_group in result["bet_groups"]:
        with st.container(border=True):
            st.markdown(f"**{bet_group['name']}**")
            st.code(nums_text(bet_group["nums"]), language="text")

    section_title("四種屬性")
    st.write(result["missing_text"])
    for line in result["high_freq_lines"]:
        st.write(line)
    for line in result["weak_lines"]:
        st.write(line)
    with st.expander("窗口條件統計", expanded=False):
        for line in result["condition_lines"]:
            st.caption(line)

    section_title("A/B/C/D 分組")
    for group_code in ["A", "B", "C", "D"]:
        render_group_card(result["groups"][group_code])
