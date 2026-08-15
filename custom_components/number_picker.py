from pathlib import Path

import streamlit.components.v1 as components


FRONTEND_DIR = Path(__file__).resolve().parent / "number_picker_frontend"

_number_picker = components.declare_component(
    "number_picker",
    path=str(FRONTEND_DIR),
)


def number_picker(selected=None, max_select=3, reset_token=0, key=None):
    """顯示 1-49 緊湊選號盤，回傳已選號碼 list[int]。"""

    selected = selected or []
    value = _number_picker(
        selected=selected,
        max_select=max_select,
        reset_token=reset_token,
        default=selected,
        key=key,
    )
    return value or selected
