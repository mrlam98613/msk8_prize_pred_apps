from pathlib import Path
import csv
import html
import json
import subprocess
import sys

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent.parent
B1_SCRIPT = PROJECT_ROOT / "n_v2_msk_prize_31_num_backtest_pred" / "B1_v1_birthday_dynamic_predict.py"
B1_DIR = B1_SCRIPT.parent
GROUP_WEIGHT_JSON = B1_DIR / "json_data" / "group_weight_best_modes.json"
M6_CSV = PROJECT_ROOT / "A_msk_lottery_data_folder" / "M6_lotto_history_prize.csv"


def to_int(value: object, default: int = 0) -> int:
    if not isinstance(value, (int, float, str)):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def to_float(value: object, default: float = 0.0) -> float:
    if not isinstance(value, (int, float, str)):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def read_dict_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames:
            reader.fieldnames = [name.strip().lstrip("\ufeff") for name in reader.fieldnames]
        return [
            {(key or "").strip().lstrip("\ufeff"): (value or "").strip() for key, value in row.items()}
            for row in reader
        ]


def read_b0_json_data() -> dict[str, object]:
    if not GROUP_WEIGHT_JSON.exists():
        return {}
    try:
        data = json.loads(GROUP_WEIGHT_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def get_b0_settings() -> dict[str, object]:
    data = read_b0_json_data()
    settings = data.get("__settings__", {})
    return settings if isinstance(settings, dict) else {}


def parse_nums(row: dict[str, str]) -> list[int]:
    nums: list[int] = []
    for idx in range(1, 7):
        try:
            nums.append(int(row.get(f"N{idx}", "0") or 0))
        except ValueError:
            nums.append(0)
    return nums


def parse_special_num(row: dict[str, str]) -> int | None:
    try:
        special_num = int(row.get("N7", "0") or 0)
    except ValueError:
        return None
    return special_num if 1 <= special_num <= 49 else None


def parse_prize_count(row: dict[str, str], prize_option: int) -> float:
    try:
        return float(row.get(f"prize{prize_option}", "0") or 0)
    except ValueError:
        return 0.0


def selected_birthday_nums(nums: list[int]) -> list[int]:
    return sorted(num for num in nums if 1 <= num <= 31)


def is_matched(count: int, match_mode: str, take_count: int) -> bool:
    if match_mode == "==":
        return count == take_count
    return count >= take_count


def format_birthday_draw_slots(nums: list[int], special_num: int | None) -> tuple[str, int]:
    slot_values: list[str] = []
    birthday_count = 0
    for num in nums:
        if 1 <= num <= 31:
            slot_values.append(str(num))
            birthday_count += 1
        else:
            slot_values.append("_")

    if special_num is not None and 1 <= special_num <= 31:
        slot_values.append(str(special_num))
        birthday_count += 1
    else:
        slot_values.append("_")

    return f"[{','.join(slot_values)}]", birthday_count


def format_prize_option_label(prize_option: int) -> str:
    labels = {1: "1 獎中獎注數", 2: "2 獎中獎注數", 3: "3 獎中獎注數"}
    return labels.get(prize_option, f"{prize_option} 獎中獎注數")


def run_b1_text(group_quota_mode: str, display_sort_mode: str) -> str:
    """用子程序執行 B1_v1，避免 Streamlit rerun 時載入 B1 全域狀態。"""

    code = (
        "import importlib.util\n"
        f"spec = importlib.util.spec_from_file_location('b1_runner', {str(B1_SCRIPT)!r})\n"
        "module = importlib.util.module_from_spec(spec)\n"
        "assert spec.loader is not None\n"
        "spec.loader.exec_module(module)\n"
        f"module.GROUP_QUOTA_MODE = {group_quota_mode!r}\n"
        f"module.DISPLAY_SORT_MODE = {display_sort_mode!r}\n"
        "module.main()\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "B1_v1 子程序沒有錯誤輸出").strip())
    return result.stdout.strip()


def build_b0_compare_rows() -> list[dict[str, object]]:
    settings = get_b0_settings()
    optimize_results = settings.get("optimize_results", [])
    if not isinstance(optimize_results, list):
        return []

    rows: list[dict[str, object]] = []
    for rank, item in enumerate(optimize_results, start=1):
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "排名": rank,
                "回測期": to_int(item.get("backtest_draw_count")),
                "窗口期": to_int(item.get("window_draw_count")),
                "5球+": to_int(item.get("hit_5_or_above")),
                "4球+": to_int(item.get("hit_4_or_above")),
                "3球+": to_int(item.get("hit_3_or_above")),
                "0球": to_int(item.get("zero_count")),
                "分數": to_float(item.get("score")),
            }
        )
    return rows


def build_window_sample_rows(display_sort_mode: str) -> list[dict[str, object]]:
    settings = get_b0_settings()
    window_count = to_int(settings.get("window_draw_count"), 12)
    take_count = to_int(settings.get("combination_take_count"), 2)
    match_mode = str(settings.get("birthday_num_match_mode", ">="))
    prize_option = to_int(settings.get("prize_option"), 3)

    table_rows: list[dict[str, object]] = []
    for row in read_dict_rows(M6_CSV)[-window_count:]:
        nums = parse_nums(row)
        selected = selected_birthday_nums(nums)
        if not is_matched(len(selected), match_mode, take_count):
            continue
        draw_text, birthday_count = format_birthday_draw_slots(nums, parse_special_num(row))
        table_rows.append(
            {
                "索引": 0,
                "日期": row.get("nDdate", ""),
                "1-31 開號": draw_text,
                "生日球數": birthday_count,
                "中獎注數": parse_prize_count(row, prize_option),
            }
        )

    if display_sort_mode == "date":
        table_rows = sorted(table_rows, key=lambda item: str(item["日期"]))
    else:
        table_rows = sorted(table_rows, key=lambda item: (-to_float(item["中獎注數"]), str(item["日期"])))

    for idx, item in enumerate(table_rows, start=1):
        item["索引"] = idx
    return table_rows


def get_best_setting_text() -> str:
    settings = get_b0_settings()
    if not settings:
        return ""

    return (
        f"系統選出最佳參數：回測期 {to_int(settings.get('backtest_draw_count'))}，"
        f"窗口期 {to_int(settings.get('window_draw_count'), 12)}，"
        f"取樣條件 {settings.get('birthday_num_match_mode', '>=')}"
        f"{to_int(settings.get('combination_take_count'), 2)}，"
        f"prize{to_int(settings.get('prize_option'), 3)}，"
        f"排序 {settings.get('sample_sort_mode', 'prize')}"
    )


def extract_prediction_text(output_text: str) -> str:
    marker = "====== B1_v1 生日號動態分組預測 ======"
    marker_index = output_text.find(marker)
    if marker_index == -1:
        return output_text
    return output_text[marker_index:].strip()


def render_static_table(rows: list[dict[str, object]]) -> None:
    """用靜態 HTML table 顯示，避免 Streamlit dataframe rerun 時不穩。"""

    if not rows:
        return

    headers = list(rows[0].keys())
    header_html = "".join(f"<th>{html.escape(str(header))}</th>" for header in headers)
    body_rows = []
    for row in rows:
        cells = "".join(
            f"<td>{html.escape(str(row.get(header, '')))}</td>"
            for header in headers
        )
        body_rows.append(f"<tr>{cells}</tr>")

    st.markdown(
        """
        <style>
        .b1-table-wrap {
            overflow-x: auto;
            margin: 0.35rem 0 0.85rem;
            border: 1px solid #d8d8d8;
            border-radius: 6px;
        }
        .b1-table {
            width: 100%;
            min-width: 620px;
            border-collapse: collapse;
            font-size: 0.92rem;
            line-height: 1.35;
        }
        .b1-table th,
        .b1-table td {
            padding: 7px 9px;
            border-bottom: 1px solid #e6e6e6;
            text-align: left;
            white-space: nowrap;
        }
        .b1-table th {
            background: #f3f5f7;
            font-weight: 800;
        }
        .b1-table tr:last-child td {
            border-bottom: 0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div class='b1-table-wrap'><table class='b1-table'>"
        f"<thead><tr>{header_html}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody></table></div>",
        unsafe_allow_html=True,
    )


def main() -> None:
    st.subheader("B1_v1 生日號動態分組預測")
    st.caption("讀取 B0_v4 JSON 最佳參數，顯示多期回測、窗口期樣本及下期膽拖組合。")

    col1, col2 = st.columns(2)
    with col1:
        group_quota_mode = st.selectbox(
            "GROUP_QUOTA_MODE",
            ["dynamic", "fixed"],
            index=0,
            help="dynamic = 動態 2/3/4 配額；fixed = 固定 3/3/3。",
        )
    with col2:
        display_sort_mode = st.selectbox(
            "DISPLAY_SORT_MODE",
            ["prize", "date"],
            index=0,
            help="只影響窗口期列表顯示，不改 B0_v4 JSON 最佳參數。",
        )

    if st.button("執行 B1_v1 預測", type="primary"):
        try:
            output_text = run_b1_text(group_quota_mode, display_sort_mode)
        except Exception as exc:
            st.error(f"B1_v1 執行失敗：{exc}")
            return

        if not output_text:
            st.warning("B1_v1 沒有輸出內容。")
            return

        st.markdown("### B0_v4 多期回測參數比較")
        compare_rows = build_b0_compare_rows()
        if compare_rows:
            render_static_table(compare_rows)
        else:
            st.info("沒有 B0_v4 多期回測參數比較資料。")

        best_setting_text = get_best_setting_text()
        if best_setting_text:
            st.text(best_setting_text)

        settings = get_b0_settings()
        window_count = to_int(settings.get("window_draw_count"), 12)
        prize_option = to_int(settings.get("prize_option"), 3)
        match_mode = str(settings.get("birthday_num_match_mode", ">="))
        take_count = to_int(settings.get("combination_take_count"), 2)
        st.markdown(f"### 最佳窗口期樣本列表：最近 {window_count} 期")
        st.caption(
            f"取樣條件：分組生日號 1-31，{match_mode}{take_count} 球，"
            f"{format_prize_option_label(prize_option)}｜{display_sort_mode}排序"
        )
        window_rows = build_window_sample_rows(display_sort_mode)
        if window_rows:
            render_static_table(window_rows)
        else:
            st.info("沒有最佳窗口期樣本資料。")

        st.markdown("### B1_v1 生日號動態分組預測")
        st.text(extract_prediction_text(output_text))


if __name__ == "__main__":
    main()
