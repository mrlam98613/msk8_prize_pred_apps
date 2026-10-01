from itertools import combinations


# table40 id = 0..9
# 0 = 40,10,20,30
# 1 = 1,11,21,31
# ...
# 9 = 9,19,29,39
TABLE_IDS = tuple(range(10))
BASE_IDS = tuple(range(1, 10))

# 是否每組固定加入 0。
INCLUDE_ZERO = False

# True 時同時比較「不加 0」與「固定加 0」的組數。
COMPARE_ZERO_MODE = True

# 查詢 0..9 每組取幾個 id 的完整組合。
RUN_FULL_PICK_COMB = True
PICK_COUNT_LIST = [3]

# 是否顯示所有組合明細。
PRINT_DETAIL = False


def normalize_group(group: tuple[int, ...], include_zero: bool = INCLUDE_ZERO) -> tuple[int, ...]:
    """整理組合；需要時固定加入 0，並去重排序。"""
    ids = set(group)
    if include_zero:
        ids.add(0)
    return tuple(sorted(ids))


def sliding_seq3_groups() -> list[tuple[int, ...]]:
    """連續 3 個 id，例如 1,2,3 / 2,3,4。"""
    return [tuple(range(start_id, start_id + 3)) for start_id in range(1, 8)]


def step3_groups() -> list[tuple[int, ...]]:
    """直線間隔 3，例如 1,4,7 / 2,5,8 / 3,6,9。"""
    return [(1, 4, 7), (2, 5, 8), (3, 6, 9)]


def edge_89_groups() -> list[tuple[int, ...]]:
    """合併到 8,9 的直覺組，例如 1,8,9。"""
    return [(start_id, 8, 9) for start_id in range(1, 8)]


def all_pick3_groups() -> list[tuple[int, ...]]:
    """1..9 任選 3 個 id，作全組合參考。"""
    return list(combinations(BASE_IDS, 3))


def full_pick_groups(pick_count: int) -> list[tuple[int, ...]]:
    """0..9 任選 pick_count 個 id 的完整組合。"""
    return list(combinations(TABLE_IDS, pick_count))


def print_full_pick_report() -> None:
    """打印 0..9 每組取 N 個 id 的完整組合統計。"""
    print("====== 0..9 完整組合查詢 ======")
    for pick_count in PICK_COUNT_LIST:
        groups = full_pick_groups(pick_count)
        print(f"每組 {pick_count} 個 id：{len(groups)} 組")
        if PRINT_DETAIL:
            for index, group in enumerate(groups, start=1):
                print(f"{index:>3}. {group}")
        print()


def build_pattern_groups(include_zero: bool = INCLUDE_ZERO) -> dict[str, list[tuple[int, ...]]]:
    """建立各類 table40 id 組合。"""
    raw_groups = {
        "連續3": sliding_seq3_groups(),
        "間隔3": step3_groups(),
        "合併8_9": edge_89_groups(),
        "全組合C9_3": all_pick3_groups(),
    }
    return {
        name: [normalize_group(group, include_zero) for group in groups]
        for name, groups in raw_groups.items()
    }


def unique_groups(groups: list[tuple[int, ...]]) -> list[tuple[int, ...]]:
    """去重後按組合排序。"""
    return sorted(set(groups))


def print_group_report(groups_by_name: dict[str, list[tuple[int, ...]]]) -> int:
    """打印各類組合與總數，並回傳合併去重總數。"""
    all_groups: list[tuple[int, ...]] = []
    for name, groups in groups_by_name.items():
        unique_list = unique_groups(groups)
        all_groups.extend(unique_list)
        print(f"{name}：{len(unique_list)} 組")
        if PRINT_DETAIL:
            for index, group in enumerate(unique_list, start=1):
                print(f"{index:>2}. {group}")
        print()

    all_unique_groups = unique_groups(all_groups)
    print(f"合併去重總數：{len(all_unique_groups)} 組")
    if PRINT_DETAIL:
        for index, group in enumerate(all_unique_groups, start=1):
            print(f"{index:>2}. {group}")
    return len(all_unique_groups)


def main() -> None:
    """主程式：建立並打印 table40 id 組合統計。"""
    print("====== table40 id 組合查詢 ======")
    print(f"TABLE_IDS：{TABLE_IDS}")
    print(f"PRINT_DETAIL：{PRINT_DETAIL}")
    print()
    if RUN_FULL_PICK_COMB:
        print_full_pick_report()
        return

    if COMPARE_ZERO_MODE:
        print("====== 不固定加入 0 ======")
        total_without_zero = print_group_report(build_pattern_groups(False))
        print()
        print("====== 固定加入 0 ======")
        total_with_zero = print_group_report(build_pattern_groups(True))
        print()
        print(f"總結：不加 0 = {total_without_zero} 組，固定加 0 = {total_with_zero} 組")
        return

    print(f"INCLUDE_ZERO：{INCLUDE_ZERO}")
    print_group_report(build_pattern_groups(INCLUDE_ZERO))


if __name__ == "__main__":
    main()
