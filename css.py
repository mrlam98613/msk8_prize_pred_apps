# css.py

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
