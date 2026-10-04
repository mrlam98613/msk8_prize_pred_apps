# css.py

white_black_style = """
<style>
    :root,
    html,
    body {
        color-scheme: light !important;
        background-color: #ffffff !important;
    }
    .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stHeader"],
    [data-testid="stToolbar"],
    [data-testid="stSidebar"],
    [data-testid="stMain"],
    [data-testid="stMainBlockContainer"],
    [data-testid="stVerticalBlock"],
    [data-testid="stHorizontalBlock"] {
        background-color: #ffffff !important;
    }
    .stApp,
    .stApp *,
    [data-testid="stSidebar"],
    [data-testid="stSidebar"] * {
        color: #000000 !important;
    }
    input,
    textarea,
    select,
    option,
    label,
    [data-baseweb="select"] > div,
    [data-baseweb="input"] > div,
    [data-baseweb="textarea"] > div,
    [data-baseweb="radio"] {
        background-color: #ffffff !important;
        color: #000000 !important;
        border-color: #b8b8b8 !important;
        -webkit-text-fill-color: #000000 !important;
        color-scheme: light !important;
    }
    [data-testid="stButton"] button[kind="secondary"],
    [data-testid="stFormSubmitButton"] button[kind="secondary"] {
        background-color: #ffffff !important;
        color: #000000 !important;
        border: 1px solid #b8b8b8 !important;
        opacity: 1 !important;
    }
    [data-testid="stButton"] button[kind="primary"],
    [data-testid="stFormSubmitButton"] button[kind="primary"] {
        background-color: #ff4b4b !important;
        color: #ffffff !important;
        border: 1px solid #ff4b4b !important;
        opacity: 1 !important;
        color-scheme: light !important;
    }
    [data-testid="stButton"] button[kind="primary"] *,
    [data-testid="stFormSubmitButton"] button[kind="primary"] * {
        color: #ffffff !important;
        fill: #ffffff !important;
        stroke: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
    }
    [data-testid="stButton"] button[kind="primary"]:hover,
    [data-testid="stFormSubmitButton"] button[kind="primary"]:hover {
        background-color: #e63b3b !important;
        border-color: #e63b3b !important;
        color: #ffffff !important;
    }
    [data-testid="stButton"] button[kind="primary"]:active,
    [data-testid="stFormSubmitButton"] button[kind="primary"]:active {
        background-color: #c92f2f !important;
        border-color: #c92f2f !important;
        color: #ffffff !important;
    }
    [data-testid="stButton"] button:disabled,
    [data-testid="stFormSubmitButton"] button:disabled,
    [data-testid="stButton"] button[disabled],
    [data-testid="stFormSubmitButton"] button[disabled] {
        background-color: #f3f4f6 !important;
        color: #9ca3af !important;
        border-color: #d1d5db !important;
        opacity: 1 !important;
    }
    [data-baseweb="input"] button,
    [data-baseweb="select"] button,
    [data-baseweb="radio"] [role="radio"],
    [data-testid="stRadio"] [role="radio"],
    [data-testid="stNumberInput"] button,
    [data-testid="stSelectbox"] button,
    [data-baseweb="input"] [role="button"],
    [data-baseweb="select"] [role="button"] {
        background-color: #ffffff !important;
        color: #000000 !important;
        border-color: #b8b8b8 !important;
        opacity: 1 !important;
        color-scheme: light !important;
    }
    [data-testid="stRadio"],
    [data-baseweb="radio"],
    [role="radiogroup"] {
        background-color: #ffffff !important;
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important;
        color-scheme: light !important;
    }
    [data-testid="stRadio"] label,
    [data-testid="stRadio"] p,
    [data-baseweb="radio"] label,
    [data-baseweb="radio"] p,
    [role="radiogroup"] label,
    [role="radiogroup"] p {
        background-color: transparent !important;
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important;
    }
    [data-testid="stRadio"] [role="radio"],
    [data-baseweb="radio"] [role="radio"] {
        width: 18px !important;
        height: 18px !important;
        min-width: 18px !important;
        min-height: 18px !important;
        border: 2px solid #4b5563 !important;
        border-radius: 999px !important;
        background-color: #ffffff !important;
        box-shadow: none !important;
        accent-color: #ff4b4b !important;
    }
    [data-testid="stRadio"] [aria-checked="true"],
    [data-baseweb="radio"] [aria-checked="true"] {
        border-color: #ff4b4b !important;
        background: radial-gradient(circle, #ff4b4b 0 42%, #ffffff 46% 100%) !important;
    }
    [data-testid="stRadio"] [aria-checked="true"] svg,
    [data-baseweb="radio"] [aria-checked="true"] svg,
    [data-testid="stRadio"] [aria-checked="true"] svg *,
    [data-baseweb="radio"] [aria-checked="true"] svg * {
        color: #ff4b4b !important;
        fill: #ff4b4b !important;
        stroke: #ff4b4b !important;
        opacity: 1 !important;
    }
    [data-baseweb="input"] svg,
    [data-baseweb="radio"] svg,
    [data-testid="stNumberInput"] svg,
    [data-testid="stRadio"] svg,
    [data-baseweb="input"] svg * {
        color: #000000 !important;
        fill: #000000 !important;
        stroke: #000000 !important;
        opacity: 1 !important;
    }
    [data-testid="stNumberInput"] button svg * {
        fill: #000000 !important;
        stroke: #000000 !important;
    }
    [data-testid="stSelectbox"] [data-baseweb="select"] > div > div:last-child,
    [data-testid="stSelectbox"] [data-baseweb="select"] svg,
    [data-baseweb="select"] > div > div:last-child,
    [data-baseweb="select"] svg {
        background: transparent !important;
        background-color: transparent !important;
        box-shadow: none !important;
    }
    [data-testid="stSelectbox"] [data-baseweb="select"] svg rect,
    [data-testid="stSelectbox"] [data-baseweb="select"] svg mask,
    [data-baseweb="select"] svg rect,
    [data-baseweb="select"] svg mask {
        fill: transparent !important;
        stroke: transparent !important;
    }
    [data-testid="stSelectbox"] [data-baseweb="select"] svg path,
    [data-baseweb="select"] svg path {
        fill: #000000 !important;
        stroke: #000000 !important;
    }
    [data-testid="stSelectbox"] [data-baseweb="select"] > div > div:last-child,
    [data-baseweb="select"] > div > div:last-child {
        position: relative !important;
        width: 38px !important;
        min-width: 38px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        background: #ffffff !important;
        background-color: #ffffff !important;
    }
    [data-testid="stSelectbox"] [data-baseweb="select"] > div > div:last-child svg,
    [data-baseweb="select"] > div > div:last-child svg {
        display: none !important;
        visibility: hidden !important;
    }
    [data-testid="stSelectbox"] [data-baseweb="select"] > div > div:last-child::after,
    [data-baseweb="select"] > div > div:last-child::after {
        content: "" !important;
        width: 8px !important;
        height: 8px !important;
        border-right: 2px solid #000000 !important;
        border-bottom: 2px solid #000000 !important;
        transform: rotate(45deg) translateY(-2px) !important;
        background: transparent !important;
        display: block !important;
    }
    [data-testid="stSelectbox"] [data-baseweb="select"] [data-baseweb="icon"],
    [data-baseweb="select"] [data-baseweb="icon"] {
        background: transparent !important;
        color: #000000 !important;
        fill: #000000 !important;
    }
    [data-testid="stSelectbox"] [data-baseweb="select"] [data-baseweb="icon"] svg,
    [data-baseweb="select"] [data-baseweb="icon"] svg {
        background: transparent !important;
        fill: #000000 !important;
        stroke: none !important;
    }
    [data-testid="stSelectbox"] [data-baseweb="select"],
    [data-baseweb="select"] {
        position: relative !important;
        background-color: #ffffff !important;
    }
    [data-testid="stSelectbox"] [data-baseweb="select"] svg,
    [data-testid="stSelectbox"] [data-baseweb="select"] svg *,
    [data-baseweb="select"] svg,
    [data-baseweb="select"] svg * {
        display: none !important;
        visibility: hidden !important;
        opacity: 0 !important;
        width: 0 !important;
        height: 0 !important;
        fill: transparent !important;
        stroke: transparent !important;
        background: transparent !important;
        background-color: transparent !important;
    }
    [data-testid="stSelectbox"] [data-baseweb="select"] *:has(> svg),
    [data-baseweb="select"] *:has(> svg) {
        display: none !important;
        visibility: hidden !important;
        opacity: 0 !important;
        background: transparent !important;
        background-color: transparent !important;
        box-shadow: none !important;
    }
    [data-testid="stSelectbox"] [data-baseweb="select"]::after,
    [data-baseweb="select"]::after {
        content: "" !important;
        position: absolute !important;
        right: 16px !important;
        top: 50% !important;
        width: 8px !important;
        height: 8px !important;
        margin-top: -6px !important;
        border-right: 2px solid #000000 !important;
        border-bottom: 2px solid #000000 !important;
        transform: rotate(45deg) !important;
        pointer-events: none !important;
        background: transparent !important;
        z-index: 5 !important;
    }
    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
        position: relative !important;
        padding-right: 42px !important;
        background-color: #ffffff !important;
    }
    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div > div:nth-child(n+2),
    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div > span:nth-child(n+2),
    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div > button,
    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div > i {
        display: none !important;
        visibility: hidden !important;
        opacity: 0 !important;
        width: 0 !important;
        min-width: 0 !important;
        max-width: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
        background: transparent !important;
        background-color: transparent !important;
        border: 0 !important;
        box-shadow: none !important;
    }
    div[data-testid="stSelectbox"] div[data-baseweb="select"] [aria-hidden="true"],
    div[data-testid="stSelectbox"] div[data-baseweb="select"] [class*="icon"],
    div[data-testid="stSelectbox"] div[data-baseweb="select"] [class*="Icon"],
    div[data-testid="stSelectbox"] div[data-baseweb="select"] [class*="material"],
    div[data-testid="stSelectbox"] div[data-baseweb="select"] [class*="Material"] {
        display: none !important;
        visibility: hidden !important;
        opacity: 0 !important;
        width: 0 !important;
        min-width: 0 !important;
        max-width: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
        overflow: hidden !important;
        background: transparent !important;
        background-color: transparent !important;
        border: 0 !important;
        box-shadow: none !important;
        color: transparent !important;
        -webkit-text-fill-color: transparent !important;
    }
    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div::after {
        content: "" !important;
        position: absolute !important;
        right: 16px !important;
        top: 50% !important;
        width: 8px !important;
        height: 8px !important;
        margin-top: -6px !important;
        border-right: 2px solid #111111 !important;
        border-bottom: 2px solid #111111 !important;
        transform: rotate(45deg) !important;
        pointer-events: none !important;
        background: transparent !important;
        z-index: 10 !important;
    }
    [data-testid="stNumberInput"] > div,
    [data-testid="stSelectbox"] > div {
        background-color: #ffffff !important;
    }
    [data-testid="stNumberInput"] input {
        background-color: #ffffff !important;
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important;
    }
    [data-testid="stButton"] button[kind="secondary"] *,
    [data-testid="stFormSubmitButton"] button[kind="secondary"] *,
    [data-testid="stNumberInput"] button *,
    [data-testid="stSelectbox"] button * {
        color: #000000 !important;
        fill: #000000 !important;
        stroke: #000000 !important;
    }
    input[type="number"]::-webkit-inner-spin-button,
    input[type="number"]::-webkit-outer-spin-button {
        opacity: 1 !important;
        filter: none !important;
    }
    @media (max-width: 430px) {
        [data-baseweb="select"] > div,
        [data-baseweb="input"] > div,
        [data-baseweb="textarea"] > div {
            min-height: 42px !important;
        }
        [data-baseweb="input"] button,
        [data-baseweb="select"] button,
        [data-testid="stNumberInput"] button,
        [data-testid="stSelectbox"] button,
        [data-baseweb="input"] [role="button"],
        [data-baseweb="select"] [role="button"] {
            min-width: 38px !important;
            min-height: 38px !important;
            background-color: #ffffff !important;
            color: #000000 !important;
        }
        [data-testid="stNumberInput"] {
            min-width: 0 !important;
        }
        [data-testid="stNumberInput"] button {
            border-left: 1px solid #b8b8b8 !important;
        }
        [data-testid="stButton"] button,
        [data-testid="stFormSubmitButton"] button {
            width: 100% !important;
            min-height: 42px !important;
        }
        [data-testid="stButton"] button[kind="secondary"],
        [data-testid="stFormSubmitButton"] button[kind="secondary"] {
            background-color: #ffffff !important;
            color: #000000 !important;
        }
        [data-testid="stButton"] button[kind="primary"],
        [data-testid="stFormSubmitButton"] button[kind="primary"] {
            background-color: #ff4b4b !important;
            color: #ffffff !important;
        }
    }
</style>
"""

card_style = """
<style>
    .my-card {
        background-color: #ffffff; /* 白色背景 */
        border: 1px solid #e0e0e0; /* 淺灰色邊框 */
        border-radius: 10px; /* 圓角 */
        padding: 12px; /* 內距 */
        margin: 10px auto; /* 上下外距，左右自動置中 */
        max-width: 400px; /* 控制卡片寬度 */
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        text-align: left; /* 內容置左 */
    }
    
    .my-card h3 {
        color: #1f77b4;
        margin-bottom: 10px;
    }
    .my-card h5 {
        text-align: left;
        margin-left: 0;
        margin-bottom: 12px;
        font-weight: bold;
    }
    /* 球圖橫向排列，手機 400px 內不換行 */
    .balls-row {
        display: flex;
        flex-direction: row;
        align-items: center;
        gap: 4px;
        flex-wrap: nowrap;
        overflow-x: auto;
        max-width: 100%;
    }
    .balls-row img {
        width: 38px;
        height: 38px;
        min-width: 38px;
        min-height: 38px;
        object-fit: contain;
    }
    @media (max-width: 420px) {
        .my-card {
            max-width: 98vw;
            padding: 10px;
        }
        .balls-row {
            gap: 2px;
        }
    }
</style>
"""

# 置中 Streamlit navigation bar
navigation_center_style = """
<style>
    /* 嘗試置中 navigation bar，class 需根據實際 DOM 結構調整 */
    .stNavigation, [data-testid="stNavigationBar"] {
        justify-content: center !important;
        display: flex !important;
    }
</style>
"""
# css.py 針對 Streamlit 容器樣式
container_style = """
<style>
    [data-testid="stVerticalBlockBorderWrapper"] {
        max-width: 400px;
        margin: 0 auto;
        border-color: #ff4b4b !important;
    }
    
</style>
"""
