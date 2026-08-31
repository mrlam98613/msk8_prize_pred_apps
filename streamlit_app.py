from pathlib import Path
import importlib.util
import sys

import streamlit as st

from css import white_black_style

''' 網頁 / 手機版 由 streamlit coding '''
PROJECT_ROOT = Path(__file__).resolve().parent
CONTENT_DIR = PROJECT_ROOT / "app_pages"

PAGES = [
    
    {
        "label": "六合彩最新資訊",
        "icon": "📌",
        "path": CONTENT_DIR / "0_lotto_info.py",
    },
    {
        "label": "A1_v1 手動趨勢投注",
        "icon": "📈",
        "path": CONTENT_DIR / "1_A1_v1_manuel_pred.py",
    },
    # {
    #     "label": "種子投注法-下期投注預測",
    #     "icon": "🏆",
    #     "path": CONTENT_DIR / "0_predict_nextdraw.py",
    # },
    # {
    #     "label": "A1_v2 12/6/3 分組預測",
    #     "icon": "🎯",
    #     "path": CONTENT_DIR / "1_A1_v2_12_6_3_pred.py",
    # },
    {
        "label": "中獎號碼-組合特色分析",
        "icon": "💰",
        "path": CONTENT_DIR / "2_lotto_prize_results.py",
    },
    {
        "label": "你的生日算出-旺財星日 + 開獎日",
        "icon": "🍀",
        "path": CONTENT_DIR / "3_lotto_lucky_day.py",
    },
    {
        "label": "獎項組合關鍵分析",
        "icon": "🔎",
        "path": CONTENT_DIR / "4_prize_comb_key.py",
    },
    {
            "label": "會員登入投注",
            "icon": "👤",
            "path": PROJECT_ROOT / "member" / "member_login.py",
            "bet_path": PROJECT_ROOT / "member" / "member_bet_center.py",
    },
]


def init_member_state() -> None:
    st.session_state.setdefault("login_state", None)
    st.session_state.setdefault("login_email_val", None)
    st.session_state.setdefault("login_member_id", None)
    st.session_state.setdefault("redirect_to_member_bet_center", False)


def reset_member_custom_bet_state() -> None:
    for key in [
        "custom_seed_numbers",
        "custom_picker_seed_numbers",
        "custom_generated_numbers",
        "custom_generated_signature",
        "custom_banker_numbers",
        "custom_leg_numbers",
        "custom_saved_notice",
        "custom_save_locked",
    ]:
        st.session_state.pop(key, None)
    for key in [
        "custom_seed_reset_token",
        "custom_banker_reset_token",
        "custom_leg_reset_token",
    ]:
        st.session_state[key] = int(st.session_state.get(key, 0)) + 1


def render_member_status() -> None:
    email = st.session_state.get("login_email_val")
    login_state = st.session_state.get("login_state")

    if not email:
        st.caption("會員狀態：尚未登入")
        return

    role = "管理員" if login_state == "admin" else "會員"
    st.caption(f"會員狀態：{email}（{role}）")
    if st.button("登出", key="main_member_logout"):
        reset_member_custom_bet_state()
        st.session_state["login_state"] = None
        st.session_state["login_email_val"] = None
        st.session_state["login_member_id"] = None
        st.session_state["redirect_to_member_bet_center"] = False
        st.rerun()


def apply_styles() -> None:
    """套用簡潔的樣式，避免出現多頁側邊欄。"""
    st.markdown(white_black_style, unsafe_allow_html=True)
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
        h1,
        [data-testid="stHeading"] h1 {
            font-size: 1.75rem !important;
            line-height: 1.25 !important;
        }
        h2,
        [data-testid="stHeading"] h2 {
            font-size: 1.45rem !important;
            line-height: 1.3 !important;
        }
        h3,
        [data-testid="stHeading"] h3 {
            font-size: 1.15rem !important;
            line-height: 1.35 !important;
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
            h1,
            [data-testid="stHeading"] h1 {
                font-size: 1.55rem !important;
            }
            h2,
            [data-testid="stHeading"] h2 {
                font-size: 1.3rem !important;
            }
            h3,
            [data-testid="stHeading"] h3 {
                font-size: 1.05rem !important;
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
        try:
            relative_path = path.relative_to(PROJECT_ROOT)
            module_name = ".".join(relative_path.with_suffix("").parts)
        except ValueError:
            module_name = f"dynamic_pages.{path.stem}"
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


def select_page_path(page: dict) -> Path:
    if (
        page["path"].name == "member_login.py"
        and st.session_state.get("login_state") in ("user", "admin")
        and page.get("bet_path")
    ):
        return page["bet_path"]
    return page["path"]


def main() -> None:
    st.set_page_config(page_title="MSK 8 投注預測", page_icon="🎯", layout="centered")
    
    init_member_state()
    apply_styles()

    st.title("MSK 8 六合彩預測")
    st.caption("以下內容直接顯示在同一頁")
    render_member_status()

    page_labels = [f"{page['icon']} {page['label']}" for page in PAGES]
    if (
        st.session_state.get("redirect_to_member_bet_center")
        and st.session_state.get("login_state") in ("user", "admin")
    ):
        st.session_state["redirect_to_member_bet_center"] = False
        st.session_state["main_page_selector"] = "👤 會員登入投注"

    selected_label = st.selectbox(
        "請拉下選單-選擇網頁功能",
        page_labels,
        index=0,
        key="main_page_selector",
    )

    selected_page = next(
        page for page in PAGES if f"{page['icon']} {page['label']}" == selected_label
    )
    run_page_file(select_page_path(selected_page))


if __name__ == "__main__":
    main()
# streamlit run streamlit_app.py
