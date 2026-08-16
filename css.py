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
    button,
    [role="button"],
    [data-testid="stButton"] button,
    [data-testid="stFormSubmitButton"] button {
        background-color: #ffffff !important;
        color: #000000 !important;
        border: 1px solid #b8b8b8 !important;
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
    [data-testid="stRadio"] *,
    [data-baseweb="radio"],
    [data-baseweb="radio"] *,
    [role="radiogroup"],
    [role="radiogroup"] * {
        background-color: #ffffff !important;
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important;
        color-scheme: light !important;
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
    }
    [data-testid="stRadio"] [aria-checked="true"],
    [data-baseweb="radio"] [aria-checked="true"] {
        border-color: #2563eb !important;
        background-color: #ffffff !important;
    }
    [data-baseweb="input"] svg,
    [data-baseweb="select"] svg,
    [data-baseweb="radio"] svg,
    [data-testid="stNumberInput"] svg,
    [data-testid="stSelectbox"] svg,
    [data-testid="stRadio"] svg,
    [data-baseweb="input"] svg *,
    [data-baseweb="select"] svg * {
        color: #000000 !important;
        fill: #000000 !important;
        stroke: #000000 !important;
        opacity: 1 !important;
    }
    [data-testid="stNumberInput"] button svg *,
    [data-testid="stSelectbox"] svg * {
        fill: #000000 !important;
        stroke: #000000 !important;
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
    [data-testid="stButton"] button *,
    [data-testid="stFormSubmitButton"] button *,
    [data-testid="stNumberInput"] button *,
    [data-testid="stSelectbox"] button *,
    [data-testid="stRadio"] * {
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
            background-color: #ffffff !important;
            color: #000000 !important;
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
