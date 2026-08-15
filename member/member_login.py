from pathlib import Path
import sys

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db import (  # noqa: E402
    add_member,
    delete_member,
    ensure_first_admin,
    get_all_members,
    get_member,
    hash_password,
    init_db,
    init_member_bet_db,
    is_valid_email,
    is_valid_local_phone,
    reset_password,
    update_member,
)
from css import white_black_style  # noqa: E402


ADMIN_EMAIL = "mrlam98613@gmail.com"
ADMIN_PHONE = "98687989"
ADMIN_PASSWORD = "98687989"
AUTH_TABS = ["會員登入", "會員註冊", "忘記密碼"]


def init_login_state() -> None:
    """初始化全站登入狀態。"""

    st.session_state.setdefault("login_state", None)
    st.session_state.setdefault("login_email_val", None)
    st.session_state.setdefault("login_member_id", None)


def set_logged_in(member) -> None:
    """登入成功後，把會員資料寫入 session state。"""

    st.session_state["login_member_id"] = member[0]
    st.session_state["login_email_val"] = member[1]
    st.session_state["login_state"] = "admin" if int(member[4]) == 1 else "user"
    init_member_bet_db(member[1])


def switch_to_bet_center() -> None:
    """登入成功後直接前往會員投注中心。"""

    st.session_state["redirect_to_member_bet_center"] = True
    st.rerun()


def switch_auth_tab(tab_name: str) -> None:
    """安排下一次 rerun 切換登入頁分頁。"""

    st.session_state["member_auth_tab"] = tab_name
    st.session_state["member_auth_tab_pending"] = tab_name


def sync_auth_tab_from_widget() -> None:
    """把 radio widget 的選擇同步到登入頁目前分頁。"""

    st.session_state["member_auth_tab"] = st.session_state["member_auth_tab_widget"]


def render_admin_member_manager() -> None:
    """管理員登入後可查看、修改、刪除會員。"""

    st.subheader("會員管理")
    members = get_all_members()

    if not members:
        st.info("目前沒有會員資料。")
        return

    for member_id, email, phone, is_admin, created_at in members:
        cols = st.columns([2.6, 1.4, 1.2, 1, 1])
        cols[0].write(email)
        cols[1].write(phone)
        cols[2].write("管理員" if is_admin else "普通會員")

        if email == ADMIN_EMAIL:
            cols[3].caption("保留")
            cols[4].caption("-")
            continue

        if cols[3].button("修改", key=f"edit_member_{member_id}"):
            st.session_state[f"editing_member_{member_id}"] = True

        if cols[4].button("刪除", key=f"delete_member_{member_id}"):
            delete_member(member_id)
            st.warning("已刪除會員。")
            st.rerun()

        if st.session_state.get(f"editing_member_{member_id}"):
            with st.container(border=True):
                new_email = st.text_input("新信箱", value=email, key=f"email_{member_id}")
                new_phone = st.text_input("新手機號碼", value=phone, key=f"phone_{member_id}")
                if st.button("確認修改", key=f"save_member_{member_id}"):
                    new_email = str(new_email or "").strip().lower()
                    new_phone = str(new_phone or "").strip()
                    if not is_valid_email(new_email):
                        st.error("Email 格式不正確。")
                    elif not is_valid_local_phone(new_phone):
                        st.error("手機號碼請輸入 8 位數字，不需要地區號。")
                    else:
                        update_member(member_id, new_email, new_phone)
                        st.success("會員資料已更新。")
                        st.session_state.pop(f"editing_member_{member_id}", None)
                        st.rerun()


def render_login_tab() -> None:
    st.header("會員登入")
    st.markdown(
        """
        <style>
        input[aria-label="登入密碼"] {
            autocomplete: current-password;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    notice = st.session_state.pop("member_login_notice", None)
    if notice:
        st.success(notice)

    email = st.text_input("信箱", key="login_email")
    password = st.text_input("登入密碼", type="password", key="member_login_password")

    if st.button("登入", key="login_btn", type="primary"):
        email = str(email or "").strip().lower()
        password = str(password or "")

        if not is_valid_email(email):
            st.error("Email 格式不正確。")
            return

        member = get_member(email)
        if member and member[3] == hash_password(password):
            set_logged_in(member)
            st.success(f"登入成功，{email}")
            switch_to_bet_center()
        else:
            st.error("帳號或密碼錯誤。")

    if st.session_state.get("login_state") == "admin":
        render_admin_member_manager()


def render_register_tab() -> None:
    st.header("會員註冊")

    reg_email = st.text_input("註冊信箱", key="reg_email")
    reg_phone = st.text_input("手機號碼（8 位數字，不用地區號）", key="reg_phone")
    reg_password = st.text_input("密碼（6-12 字元）", type="password", key="reg_pwd")

    if st.button("註冊", key="reg_btn", type="primary"):
        reg_email = str(reg_email or "").strip().lower()
        reg_phone = str(reg_phone or "").strip()
        reg_password = str(reg_password or "")

        if not is_valid_email(reg_email):
            st.warning("Email 格式不正確。")
        elif not is_valid_local_phone(reg_phone):
            st.warning("手機號碼請輸入 8 位數字，不需要地區號。")
        elif len(reg_password) < 6 or len(reg_password) > 12:
            st.warning("密碼長度需 6-12 字元。")
        elif get_member(reg_email):
            st.warning("此信箱已註冊。")
        else:
            add_member(reg_email, reg_phone, hash_password(reg_password), 0)
            init_member_bet_db(reg_email)
            st.session_state["member_login_notice"] = "註冊成功，請使用新帳號登入。"
            switch_auth_tab("會員登入")
            st.rerun()


def render_forgot_password_tab() -> None:
    st.header("忘記密碼")

    forgot_email = st.text_input("註冊信箱", key="forgot_email")
    forgot_phone = st.text_input("手機號碼（8 位數字，不用地區號）", key="forgot_phone")
    new_password = st.text_input("新密碼（6-12 字元）", type="password", key="forgot_pwd")

    if st.button("重設密碼", key="forgot_btn", type="primary"):
        forgot_email = str(forgot_email or "").strip().lower()
        forgot_phone = str(forgot_phone or "").strip()
        new_password = str(new_password or "")

        if not is_valid_email(forgot_email):
            st.warning("Email 格式不正確。")
        elif not is_valid_local_phone(forgot_phone):
            st.warning("手機號碼請輸入 8 位數字，不需要地區號。")
        elif len(new_password) < 6 or len(new_password) > 12:
            st.warning("密碼長度需 6-12 字元。")
        elif not get_member(forgot_email):
            st.warning("此信箱尚未註冊。")
        elif reset_password(forgot_email, forgot_phone, hash_password(new_password)):
            st.session_state["member_login_notice"] = "密碼重設成功，請重新登入。"
            switch_auth_tab("會員登入")
            st.rerun()
        else:
            st.error("信箱或手機號碼錯誤，請確認輸入。")


def main() -> None:
    st.markdown(white_black_style, unsafe_allow_html=True)
    init_db()
    ensure_first_admin(ADMIN_EMAIL, ADMIN_PHONE, ADMIN_PASSWORD)
    init_login_state()

    st.session_state.setdefault("member_auth_tab", "會員登入")
    pending_tab = st.session_state.pop("member_auth_tab_pending", None)
    if pending_tab in AUTH_TABS:
        st.session_state["member_auth_tab_widget"] = pending_tab

    current_tab = st.radio(
        "會員功能",
        AUTH_TABS,
        index=AUTH_TABS.index(st.session_state["member_auth_tab"]),
        horizontal=True,
        key="member_auth_tab_widget",
        on_change=sync_auth_tab_from_widget,
        label_visibility="collapsed",
    )

    if current_tab == "會員登入":
        render_login_tab()
    elif current_tab == "會員註冊":
        render_register_tab()
    else:
        render_forgot_password_tab()


if __name__ == "__main__":
    main()
