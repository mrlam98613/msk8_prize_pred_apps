import streamlit as st

from new_app_pages.shared_style import apply_new_page_style, page_header, section_title


def main() -> None:
    """Streamlit 1.64 sandbox landing page."""
    apply_new_page_style()
    page_header(
        "New app pages 測試區",
        "這是 Streamlit 1.64.0 新頁面試驗區。舊 app_pages 目錄暫時保留不動。",
    )

    cols = st.columns(3)
    cols[0].metric("Streamlit", st.__version__)
    cols[1].metric("新目錄", "new_app_pages")
    cols[2].metric("狀態", "測試中")

    st.html('<div class="msk-section"></div>')
    section_title("新頁面整理方向")
    st.markdown(
        """
        - 新頁面先放在 `new_app_pages/`
        - 統一字體、顏色、間距和區塊樣式
        - 舊 `app_pages/` 保留，確認新樣式穩定後再逐頁搬入
        - 新頁面優先使用 Streamlit 1.64 原生元件
        """
    )

    st.html('<div class="msk-section"></div>')
    section_title("下一步")
    st.info("可以先把 wheeling / smart bet 頁面搬入這個新目錄，作為新版第一個功能頁。")
