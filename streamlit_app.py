from pathlib import Path
import importlib.util
import sys

import streamlit as st



PROJECT_ROOT = Path(__file__).resolve().parent
CONTENT_DIR = PROJECT_ROOT / "app_pages"

PAGES = [
    {
        "label": "六合彩最新資訊",
        "icon": "📌",
        "path": CONTENT_DIR / "0_lotto_info.py",
    },
    {
        "label": "種子投注法-下期投注預測",
        "icon": "🏆",
        "path": CONTENT_DIR / "0_predict_nextdraw.py",
    },
    {
        "label": "天機借運-下期投注預測",
        "icon": "🎯",
        "path": CONTENT_DIR / "1_nextdraw_prize123_pred_bet.py",
    },
    {
        "label": "中獎號碼-組合特色分析",
        "icon": "💰",
        "path": CONTENT_DIR / "2_lotto_prize_results.py",
    },
    {
        "label": "你的財日分析",
        "icon": "🍀",
        "path": CONTENT_DIR / "3_lotto_lucky_day.py",
    },
]


def apply_styles() -> None:
    """套用簡潔的樣式，避免出現多頁側邊欄。"""
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"],
        [data-testid="collapsedControl"],
        #MainMenu,
        header,
        footer {
            display: none !important;
            visibility: hidden !important;
        }
        .block-container {
            padding-top: 0.75rem;
        }
        div[data-testid="stTabs"] [role="tablist"] {
            gap: 0.35rem;
            margin-bottom: 0.75rem;
        }
        div[data-testid="stTabs"] [role="tab"] {
            min-height: 36px;
            padding: 4px 14px;
            border-radius: 8px 8px 0 0;
            font-size: 14px;
            font-weight: 800;
        }
        div[data-testid="stTabs"] [role="tab"] p {
            font-size: 14px;
            font-weight: 800;
            white-space: nowrap;
        }
        @media (max-width: 430px) {
            .block-container {
                padding-left: 0.75rem;
                padding-right: 0.75rem;
            }
            div[data-testid="stTabs"] [role="tab"] {
                padding-left: 8px;
                padding-right: 8px;
            }
            div[data-testid="stTabs"] [role="tab"] p {
                font-size: 13px;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def run_page_file(path: Path) -> None:
    """在主頁內依序載入各個內容區塊。"""
    if not path.exists():
        st.error(f"內容檔案不存在：{path}")
        st.stop()

    try:
        module_name = f"app_pages.{path.stem}"
        module = sys.modules.get(module_name)
        if module is None:
            spec = importlib.util.spec_from_file_location(module_name, path)
            if spec is None or spec.loader is None:
                raise RuntimeError(f"無法載入內容檔案：{path}")
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

        page_main = getattr(module, "main", None) or getattr(module, "render_home_page", None)
        if callable(page_main):
            page_main()
        else:
            raise RuntimeError(f"內容檔案沒有可執行入口：{path.name}")
    except Exception as exc:  # pragma: no cover - 實際執行時的例外處理
        st.error(f"載入內容時發生錯誤：{exc}")
        st.stop()


def main() -> None:
    st.set_page_config(page_title="MSK 8 下期預測", page_icon="🎯", layout="centered")
    
    apply_styles()

    st.title("六合彩預測與分析")
    st.caption("以下內容直接顯示在同一頁")

    page_labels = [f"{page['icon']} {page['label']}" for page in PAGES]
    selected_label = st.selectbox(
        "請選擇內容",
        page_labels,
        index=0,
        key="main_page_selector",
    )

    selected_page = next(
        page for page in PAGES if f"{page['icon']} {page['label']}" == selected_label
    )
    run_page_file(selected_page["path"])


if __name__ == "__main__":
    main()
# streamlit run streamlit_app.py
