from pathlib import Path
from datetime import datetime
import html
import importlib.util
import sys

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent.parent
C1_SCRIPT = PROJECT_ROOT / "n_v3_msk_prize3_sample" / "C1_v1_fortune_key_pred.py"


def load_c1_module():
    spec = importlib.util.spec_from_file_location("c1_v1_fortune_key_pred_web", C1_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"未能載入 C1_v1：{C1_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def to_int(value: object, default: int = 0) -> int:
    if not isinstance(value, (int, float, str)):
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def to_float(value: object, default: float = 0.0) -> float:
    if not isinstance(value, (int, float, str)):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_int_list(text: str, default: list[int]) -> list[int]:
    values: list[int] = []
    for part in text.replace("，", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            value = int(part)
        except ValueError:
            continue
        if value > 0 and value not in values:
            values.append(value)
    return values or default


def format_nums(nums: list[int]) -> str:
    return "[" + ",".join(str(num) for num in nums) + "]"


def render_html_table(rows: list[dict[str, object]]) -> None:
    if not rows:
        st.info("沒有資料")
        return
    headers = list(rows[0].keys())
    head_html = "".join(f"<th>{html.escape(str(header))}</th>" for header in headers)
    body_rows = []
    for row in rows:
        cells = "".join(f"<td>{html.escape(str(row.get(header, '')))}</td>" for header in headers)
        body_rows.append(f"<tr>{cells}</tr>")
    st.markdown(
        """
        <style>
        .c1-table{width:100%;border-collapse:collapse;font-size:14px;margin:6px 0 14px 0;}
        .c1-table th,.c1-table td{border:1px solid #d1d5db;padding:6px 8px;text-align:left;white-space:nowrap;}
        .c1-table th{background:#f3f4f6;font-weight:800;color:#111827;}
        .c1-table td{color:#111827;}
        .c1-scroll{overflow-x:auto;width:100%;}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="c1-scroll"><table class="c1-table"><thead><tr>{head_html}</tr></thead>'
        f"<tbody>{''.join(body_rows)}</tbody></table></div>",
        unsafe_allow_html=True,
    )


def build_setting_rows(
    backtest_counts: list[int],
    window_counts: list[int],
    top_prize_counts: list[int],
    c1,
) -> list[dict[str, object]]:
    return [
        {"項目": "回測期數（預設 12、24）", "設定": ", ".join(str(num) for num in backtest_counts)},
        {"項目": "採樣窗口期（預設 21、36）", "設定": ", ".join(str(num) for num in window_counts)},
        {"項目": "3獎注數最多前期數（預設 7）", "設定": ", ".join(str(num) for num in top_prize_counts)},
        {"項目": "分組", "設定": "1-9 / 10-20 / 21-31"},
        {"項目": "取樣條件", "設定": f"每組生日號 {c1.MATCH_MODE}{c1.MATCH_COUNT} 球，按三獎中獎注數排序"},
        {"項目": "配額列表", "設定": ", ".join(c1.format_quota(quota) for quota in c1.GROUP_QUOTA_LIST)},
    ]


def build_ranking_rows(ranking: list[dict[str, object]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for rank, item in enumerate(ranking, start=1):
        rows.append(
            {
                "排名": rank,
                "回測期": to_int(item.get("backtest_draw_count")),
                "窗口期": to_int(item.get("window_draw_count")),
                "三獎前N期": to_int(item.get("top_prize_draw_count")),
                "配額": str(item.get("group_quota_text", "")),
                "5球+": to_int(item.get("hit_5_or_above")),
                "4球+": to_int(item.get("hit_4_or_above")),
                "3球+": to_int(item.get("hit_3_or_above")),
                "0球": to_int(item.get("zero_count")),
                "0球率": f"{to_float(item.get('zero_rate')) * 100:.1f}%",
                "累積分數": to_float(item.get("score")),
            }
        )
    return rows


def format_bet_date(date_text: str) -> str:
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    try:
        date_value = datetime.strptime(date_text, "%Y-%m-%d")
    except ValueError:
        return date_text
    return f"{date_text}（{weekdays[date_value.weekday()]}）"


def render_prediction(c1, bet_date: str, predictions: dict[str, list[int]], best: dict[str, object]) -> None:
    candidate_pool = sorted({num for nums in predictions.values() for num in nums})
    st.markdown("### 下期預測")
    st.markdown(
        f"已讀入最佳參數：回測期 `{to_int(best.get('backtest_draw_count'))}`，"
        f"窗口期 `{to_int(best.get('window_draw_count'))}`，"
        f"三獎前 `{to_int(best.get('top_prize_draw_count'))}` 期，"
        f"配額 `{best.get('group_quota_text', '')}`，"
        f"分數 `{to_float(best.get('score')):g}`"
    )

    pred_rows = []
    for name in ["1-9", "10-20", "21-31"]:
        nums = predictions.get(name, [])
        pred_rows.append({"分組": name, "預測球": format_nums(nums), "球數": len(nums)})
    render_html_table(pred_rows)

    display_bet_date = html.escape(format_bet_date(bet_date))
    st.markdown(
        f"<div style=\"font-size:1.35rem;font-weight:800;margin:1rem 0 0.75rem;\">"
        f"下期開獎日期：{display_bet_date}</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"預測：{format_nums(predictions.get('1-9', []))},"
        f"{format_nums(predictions.get('10-20', []))},"
        f"{format_nums(predictions.get('21-31', []))}"
    )
    st.markdown(f"候選池：{','.join(str(num) for num in candidate_pool)} /> {len(candidate_pool)} 球")
    for line in c1.format_rbg_lines(candidate_pool):
        st.markdown(line)


def reset_c1_inputs() -> None:
    st.session_state["c1_v1_backtest_draw_count_list"] = "12,24"
    st.session_state["c1_v1_window_draw_count_list"] = "21,36"
    st.session_state["c1_v1_top_prize_draw_count_list"] = "7"
    st.session_state["c1_v1_show_result"] = False


def show_c1_backtest() -> None:
    st.session_state["c1_v1_show_result"] = True


def init_c1_state() -> None:
    st.session_state.setdefault("c1_v1_backtest_draw_count_list", "12,24")
    st.session_state.setdefault("c1_v1_window_draw_count_list", "21,36")
    st.session_state.setdefault("c1_v1_top_prize_draw_count_list", "7")
    st.session_state.setdefault("c1_v1_show_result", False)


def main() -> None:
    # 或更明確地：
    from typing import Any
    c1: Any = load_c1_module()
    
    st.title("財庫鎖匙查詢")
    st.markdown(
        """
        <style>
        [data-testid="stTextInput"] input {
            background-color: #eaf3ff !important;
            border: 2px solid #3b82f6 !important;
            color: #111827 !important;
            font-weight: 700 !important;
        }
        [data-testid="stTextInput"] > div {
            background-color: #eaf3ff !important;
            border-radius: 8px !important;
        }
        [data-testid="stTextInput"] input:focus {
            background-color: #ffffff !important;
            border-color: #1d4ed8 !important;
            box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2) !important;
        }
        [data-testid="stTextInput"] label {
            color: #1d4ed8 !important;
            font-weight: 800 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    # c1 = load_c1_module() # type: ignore[assignment]

    init_c1_state()
    backtest_counts = parse_int_list(
        st.text_input("回測期數", key="c1_v1_backtest_draw_count_list"),
        [12, 24],
    )
    window_counts = parse_int_list(
        st.text_input(
            "採樣窗口期（最少 21 期起）",
            key="c1_v1_window_draw_count_list",
            help="採樣窗口期最少 21 期起，可輸入多個期數，例如：21,36",
        ),
        [21, 36],
    )
    invalid_window_counts = [count for count in window_counts if count < 21]
    if invalid_window_counts:
        st.error(
            f"採樣窗口期最少 21 期起，目前輸入：{', '.join(str(count) for count in invalid_window_counts)}。"
        )
        return

    top_prize_counts = parse_int_list(
        st.text_input("三獎注數最多前期數", key="c1_v1_top_prize_draw_count_list"),
        [7],
    )

    button_cols = st.columns(2)
    button_cols[0].button("顯示回測", type="primary", width="stretch", on_click=show_c1_backtest)
    button_cols[1].button(
        "重設",
        type="secondary",
        width="stretch",
        on_click=reset_c1_inputs,
        disabled=not st.session_state["c1_v1_show_result"],
    )

    if not st.session_state["c1_v1_show_result"]:
        st.info("請設定參數後，按「顯示回測」更新結果。")
        return

    # c1.BACKTEST_DRAW_COUNT_LIST = backtest_counts
    # c1.WINDOW_DRAW_COUNT_LIST = window_counts
    # c1.TOP_PRIZE_DRAW_COUNT_LIST = top_prize_counts
    c1.BACKTEST_DRAW_COUNT_LIST = backtest_counts  # type: ignore[attr-defined]
    c1.WINDOW_DRAW_COUNT_LIST = window_counts  # type: ignore[attr-defined]
    c1.TOP_PRIZE_DRAW_COUNT_LIST = top_prize_counts  # type: ignore[attr-defined]
    draws = c1.read_draws()
    if not draws:
        st.error(f"未能讀取 M6：{c1.M6_CSV}")
        return

    best, ranking, best_rows = c1.run_auto_backtest(draws)
    c1.save_json(best, ranking, best_rows)
    c1.save_backtest_check_csv(best_rows)
    best_params = c1.load_best_params()
    predictions = c1.predict_next(draws, best_params)
    bet_date = c1.read_next_draw_date()
    c1.save_nextdraw_pred_csv(bet_date, predictions)

    st.markdown("### 簡化回測設定")
    render_html_table(build_setting_rows(backtest_counts, window_counts, top_prize_counts, c1))

    st.markdown("### 多期回測參數比較")
    render_html_table(build_ranking_rows(ranking))
    st.success(
        f"最佳組合：回測期 {to_int(best.get('backtest_draw_count'))}，"
        f"窗口期 {to_int(best.get('window_draw_count'))}，"
        f"三獎前 {to_int(best.get('top_prize_draw_count'))} 期，"
        f"配額 {best.get('group_quota_text', '')}，"
        f"5球以上 {to_int(best.get('hit_5_or_above'))} 期，"
        f"4球以上 {to_int(best.get('hit_4_or_above'))} 期，"
        f"3球以上 {to_int(best.get('hit_3_or_above'))} 期，"
        f"分數 {to_float(best.get('score')):g}"
    )

    render_prediction(c1, bet_date, predictions, best)


if __name__ == "__main__":
    main()
