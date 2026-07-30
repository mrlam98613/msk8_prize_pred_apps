

def get_rbg_sub_group_dict():
    """回傳 R/B/G 的子分組字典。"""
    return {
        1: {
            "R1": [1, 2, 7, 8],
            "R2": [12, 13, 18, 19, 23, 24, 29, 30, 34, 35],
            "R3": [40, 45, 46],
        },
        2: {
            "B1": [3, 4, 9, 10],
            "B2": [14, 15, 20, 25, 26, 31, 36, 37],
            "B3": [41, 42, 47, 48],
        },
        3: {
            "G1": [5, 6, 11],
            "G2": [16, 17, 21, 22, 27, 28, 32, 33, 38],
            "G3": [39, 43, 44, 49],
        },
    }


def group_candidates_by_rbg_sub_group(candidate_dict):
    """將 {1:[...], 2:[...], 3:[...]} 候選號分成 R1/R2/R3 等子組。"""
    sub_group_dict = get_rbg_sub_group_dict()
    grouped_dict = {}

    for color_key, sub_groups in sub_group_dict.items():
        candidate_set = set(candidate_dict.get(color_key, []))
        grouped_dict[color_key] = {}
        for group_name, group_nums in sub_groups.items():
            grouped_dict[color_key][group_name] = sorted(candidate_set & set(group_nums))

    return grouped_dict