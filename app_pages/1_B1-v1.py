from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import importlib.util
import sys

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent.parent
B1_SCRIPT = PROJECT_ROOT / "n_v2_msk_prize_31_num_backtest_pred" / "B1_v1_birthday_dynamic_predict.py"


def load_b1_module():
    """載入 B1_v1 程式，讓網頁版直接使用原本預測邏輯。"""

    module_name = "n_v2_msk_prize_31_num_backtest_pred.B1_v1_birthday_dynamic_predict_web"
    module = sys.modules.get(module_name)
    if module is not None:
        return module

    spec = importlib.util.spec_from_file_location(module_name, B1_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"無法載入 B1_v1：{B1_SCRIPT}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def run_b1_text(group_quota_mode: str, display_sort_mode: str) -> str:
    """執行 B1_v1 並捕捉 console 文字輸出。"""

    b1 = load_b1_module()
    b1.GROUP_QUOTA_MODE = group_quota_mode
    b1.DISPLAY_SORT_MODE = display_sort_mode

    output = StringIO()
    with redirect_stdout(output):
        b1.main()
    return output.getvalue().strip()


def main() -> None:
    st.subheader("B1_v1 生日號動態分組預測")
    st.caption("讀取 B0_v4 JSON 最佳參數，顯示多期回測、窗口期樣本及下期膽拖組合。")

    col1, col2 = st.columns(2)
    with col1:
        group_quota_mode = st.selectbox(
            "GROUP_QUOTA_MODE",
            ["dynamic", "fixed"],
            index=0,
            help="dynamic = 動態 2/3/4 配額；fixed = 固定 3/3/3。",
        )
    with col2:
        display_sort_mode = st.selectbox(
            "DISPLAY_SORT_MODE",
            ["prize", "date"],
            index=0,
            help="只影響窗口期列表顯示，不改 B0_v4 JSON 最佳參數。",
        )

    if st.button("執行 B1_v1 預測", type="primary"):
        try:
            output_text = run_b1_text(group_quota_mode, display_sort_mode)
        except Exception as exc:
            st.error(f"B1_v1 執行失敗：{exc}")
            return

        if not output_text:
            st.warning("B1_v1 沒有輸出內容。")
            return

        st.text(output_text)


if __name__ == "__main__":
    main()
