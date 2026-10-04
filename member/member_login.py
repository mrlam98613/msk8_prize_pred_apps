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
    get_member_by_phone,
    hash_password,
    init_db,
    init_member_bet_db,
    is_valid_local_phone,
    update_member_simple,
)
from css import white_black_style  # noqa: E402


ADMIN_EMAIL = "98687989"
ADMIN_PHONE = "98687989"
ADMIN_PASSWORD = "7989"
AUTH_TABS = ["會員登入", "會員註冊", "忘記登入"]


def normalize_phone(phone: str | None) -> str:
    """統一整理電話號碼，登入和註冊都只接受 8 位本地號碼。"""

    return str(phone or "").strip()


def auto_password_from_phone(phone: str) -> str:
    """會員預設密碼固定為電話號碼最後 4 位。"""

    return normalize_phone(phone)[-4:]


def find_member_by_phone(phone: str):
    """以電話號碼尋找會員；兼容舊資料 email 欄位仍存電話的情況。"""

    phone = normalize_phone(phone)
    return get_member(phone) or get_member_by_phone(phone)


def member_nickname(member) -> str:
    """安全讀取暱稱欄位；舊資料沒有暱稱時回傳空字串。"""

    if member and len(member) > 6:
        return str(member[6] or "").strip()
    return ""


def init_login_state() -> None:
    """初始化全站登入狀態。"""

    st.session_state.setdefault("login_state", None)
    st.session_state.setdefault("login_email_val", None)
    st.session_state.setdefault("login_member_id", None)


def set_logged_in(member) -> None:
    """登入成功後，把會員資料寫入 session state。"""

    st.session_state["login_member_id"] = member[0]
    st.session_state["login_email_val"] = member[1]
    st.session_state["login_member_phone"] = member[2]
    st.session_state["login_member_nickname"] = member_nickname(member)
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
        full_member = get_member(email)
        nickname = member_nickname(full_member)
        cols[0].write(nickname or "未填暱稱")
        cols[1].write(phone)
        cols[2].write("管理員" if is_admin else "普通會員")

        if email == ADMIN_EMAIL or phone == ADMIN_PHONE:
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
                new_phone = st.text_input(
                    "新電話號碼（8 位數字，不用地區號）",
                    value=phone,
                    key=f"phone_{member_id}",
                )
                new_nickname = st.text_input(
                    "會員暱稱（可不填）",
                    value=nickname,
                    key=f"nickname_{member_id}",
                )
                if st.button("確認修改", key=f"save_member_{member_id}"):
                    new_phone = normalize_phone(new_phone)
                    if not is_valid_local_phone(new_phone):
                        st.error("手機號碼請輸入 8 位數字，不需要地區號。")
                    else:
                        update_member_simple(member_id, new_phone, new_nickname)
                        st.success("會員資料已更新。")
                        st.session_state.pop(f"editing_member_{member_id}", None)
                        st.rerun()


def render_login_tab() -> None:
    st.header("會員登入")
    st.markdown(
        """
        <style>
        input[aria-label="登入密碼（電話號碼後 4 位）"] {
            autocomplete: current-password;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    notice = st.session_state.pop("member_login_notice", None)
    if notice:
        st.success(notice)

    phone = st.text_input("電話號碼（8 位數字，不用地區號）", key="login_phone")
    password = st.text_input("登入密碼（電話號碼後 4 位）", type="password", key="member_login_password")

    if st.button("登入", key="login_btn", type="primary"):
        phone = normalize_phone(phone)
        password = str(password or "")

        if not is_valid_local_phone(phone):
            st.error("電話號碼請輸入 8 位數字，不需要地區號。")
            return

        member = find_member_by_phone(phone)
        if member and member[3] == hash_password(password):
            set_logged_in(member)
            display_name = member_nickname(member) or phone
            st.success(f"登入成功，{display_name}")
            switch_to_bet_center()
        else:
            st.error("電話號碼或密碼錯誤。")

    if st.session_state.get("login_state") == "admin":
        render_admin_member_manager()


def render_register_tab() -> None:
    st.header("會員註冊")

    reg_phone = st.text_input("電話號碼（8 位數字，不用地區號）", key="reg_phone")
    reg_nickname = st.text_input("會員暱稱（可不填）", key="reg_nickname")

    if st.button("註冊", key="reg_btn", type="primary"):
        reg_phone = normalize_phone(reg_phone)
        reg_password = auto_password_from_phone(reg_phone)

        if not is_valid_local_phone(reg_phone):
            st.warning("手機號碼請輸入 8 位數字，不需要地區號。")
        elif find_member_by_phone(reg_phone):
            st.warning("此電話號碼已註冊。")
        else:
            add_member(reg_phone, reg_phone, hash_password(reg_password), 0, reg_nickname)
            init_member_bet_db(reg_phone)
            st.session_state["member_login_notice"] = (
                f"註冊成功，登入密碼是電話號碼後 4 位：{reg_password}"
            )
            switch_auth_tab("會員登入")
            st.rerun()


def render_forgot_password_tab() -> None:
    st.header("忘記登入")

    forgot_phone = st.text_input("電話號碼（8 位數字，不用地區號）", key="forgot_phone")
    forgot_password = st.text_input(
        "登入密碼（電話號碼後 4 位）",
        type="password",
        key="forgot_pwd",
    )

    if st.button("驗證並登入", key="forgot_btn", type="primary"):
        forgot_phone = normalize_phone(forgot_phone)
        forgot_password = str(forgot_password or "")

        if not is_valid_local_phone(forgot_phone):
            st.warning("手機號碼請輸入 8 位數字，不需要地區號。")
        else:
            member = find_member_by_phone(forgot_phone)
            if member and member[3] == hash_password(forgot_password):
                set_logged_in(member)
                st.success("驗證成功，已登入會員網頁。")
                switch_to_bet_center()
            elif forgot_password != auto_password_from_phone(forgot_phone):
                st.error("電話號碼或密碼錯誤。")
            elif member:
                st.error("會員密碼不是目前電話號碼後 4 位，請聯絡管理員。")
            else:
                st.warning("此電話號碼尚未註冊。")


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
