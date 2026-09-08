# F5_v5 共用分組設定：所有分析模組從此讀取目前分析範圍。
ANALYSIS_GROUPS = {
    "1_9": ("1-9", 1, 9),
    "10_20": ("10-20", 10, 20),
    "21_31": ("21-31", 21, 31),
}
ACTIVE_GROUP_KEY = "1_9"
GROUP_LABEL, BIRTHDAY_NUM_MIN, BIRTHDAY_NUM_MAX = ANALYSIS_GROUPS[ACTIVE_GROUP_KEY]
COLD_REBOUND_JSON_NAME = f"F5_v5_{ACTIVE_GROUP_KEY}_cold_rebound_best.json"
