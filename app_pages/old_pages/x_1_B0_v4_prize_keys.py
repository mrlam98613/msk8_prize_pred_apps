from pathlib import Path
import csv
import html

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = (
    PROJECT_ROOT
    / "n_v2_msk_prize_31_num_backtest_pred"
    / "bet_data"
    / "backtest_window_check_rows.csv"
)


def read_rows() -> list[dict[str, str]]:
    if not CSV_PATH.exists():
        return []
    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames:
            reader.fieldnames = [name.strip().lstrip("\ufeff") for name in reader.fieldnames]
        return [
            {(key or "").strip().lstrip("\ufeff"): (value or "").strip() for key, value in row.items()}
            for row in reader
        ]


def to_int(value: object, default: int = 0) -> int:
    if not isinstance(value, (int, float, str)):
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def format_group_text(value: str) -> str:
    text = (value or "[]").strip()
    return text if text else "[]"


def build_display_rows(
    source_rows: list[dict[str, str]],
    min_hit_score: int,
    sort_mode: str,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for row in source_rows:
        hit_score = to_int(row.get("hit_score"))
        if hit_score < min_hit_score:
            continue
        rows.append(
            {
                "回測期": to_int(row.get("backtest_draw_count")),
                "窗口期": to_int(row.get("window_draw_count")),
                "日期": row.get("date", ""),
                "1-9": format_group_text(row.get("1-9", "")),
                "10-20": format_group_text(row.get("10-20", "")),
                "21-31": format_group_text(row.get("21-31", "")),
                "命中球數": hit_score,
            }
        )

    if sort_mode == "日期":
        rows = sorted(
            rows,
            key=lambda item: (
                str(item["日期"]),
                to_int(item["回測期"]),
                to_int(item["窗口期"]),
            ),
        )
    elif sort_mode == "窗口期":
        rows = sorted(
            rows,
            key=lambda item: (
                to_int(item["窗口期"]),
                str(item["日期"]),
                -to_int(item["命中球數"]),
                to_int(item["回測期"]),
            ),
        )
    else:
        rows = sorted(
            rows,
            key=lambda item: (
                -to_int(item["命中球數"]),
                str(item["日期"]),
                to_int(item["回測期"]),
                to_int(item["窗口期"]),
            ),
        )

    return rows


def render_table(rows: list[dict[str, object]]) -> None:
    if not rows:
        st.info("沒有符合條件的回測命中紀錄。")
        return

    headers = ["排名", "回測期", "窗口期", "日期", "1-9", "10-20", "21-31", "命中球數"]
    body_rows: list[str] = []
    for idx, row in enumerate(rows, start=1):
        values = [
            idx,
            row["回測期"],
            row["窗口期"],
            row["日期"],
            row["1-9"],
            row["10-20"],
            row["21-31"],
            row["命中球數"],
        ]
        cells = "".join(f"<td>{html.escape(str(value))}</td>" for value in values)
        body_rows.append(f"<tr>{cells}</tr>")

    header_html = "".join(f"<th>{html.escape(header)}</th>" for header in headers)
    st.markdown(
        f"""
        <style>
        .b0-table-wrap {{
            width: 100%;
            overflow-x: auto;
            margin-top: 8px;
        }}
        .b0-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
            line-height: 1.45;
            white-space: nowrap;
        }}
        .b0-table th {{
            background: #f3f4f6;
            color: #111827;
            font-weight: 800;
            border: 1px solid #d1d5db;
            padding: 6px 8px;
            text-align: left;
        }}
        .b0-table td {{
            border: 1px solid #e5e7eb;
            padding: 6px 8px;
            color: #1f2937;
        }}
        .b0-table tr:nth-child(even) td {{
            background: #fafafa;
        }}
        @media (max-width: 430px) {{
            .b0-table {{
                font-size: 12px;
            }}
            .b0-table th,
            .b0-table td {{
                padding: 5px 6px;
            }}
        }}
        </style>
        <div class="b0-table-wrap">
            <table class="b0-table">
                <thead><tr>{header_html}</tr></thead>
                <tbody>{"".join(body_rows)}</tbody>
            </table>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.subheader("B0_v4 回測命中關鍵")
    st.caption("讀取 B0_v4 產生的 backtest_window_check_rows.csv，只顯示符合命中球數條件的分組命中紀錄。")

    source_rows = read_rows()
    if not source_rows:
        st.error(f"找不到或未能讀取 CSV：{CSV_PATH}")
        return

    col1, col2 = st.columns(2)
    min_hit_score = int(col1.selectbox("命中球數 >=", [3, 4, 5], index=0, key="b0_keys_min_hit_score"))
    sort_mode = str(col2.selectbox("排序", ["日期", "窗口期", "命中球數"], index=0, key="b0_keys_sort_mode"))

    rows = build_display_rows(source_rows, min_hit_score, sort_mode)
    st.caption(f"CSV 總行數：{len(source_rows)}｜符合條件：{len(rows)}｜排序：{sort_mode}")
    render_table(rows)


if __name__ == "__main__":
    main()
