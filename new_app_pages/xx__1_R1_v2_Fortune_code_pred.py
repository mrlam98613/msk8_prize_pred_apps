from pathlib import Path
import base64
from datetime import datetime
import html
import subprocess
import sys

import streamlit as st
'''

1. 讀入 F5 / G1 / H1 的 JSON 預測結果
2. 用 R1_v2 分組配額協調候選球
3. 更新 R1_v2 JSON
4. 更新 nextBetDraw_record.csv
5. 將終端打印結果回傳給網頁顯示

'''


PROJECT_ROOT = Path(__file__).resolve().parent.parent
R1_V2_SCRIPT = PROJECT_ROOT / "nn_v8_msk_route_pred_apps" / "R1_v2_route_with_fgh_pred.py"
BALLS_DIR = PROJECT_ROOT / "A_msk_balls_png"
WEEKDAY_TEXT = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]


def run_r1_v2_text() -> str:
    """執行 R1_v2，取得終端打印內容；避免直接 import 影響 Streamlit rerun。"""

    result = subprocess.run(
        [sys.executable, str(R1_V2_SCRIPT)],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "R1_v2 沒有錯誤輸出").strip())
    return result.stdout.strip()


def extract_prediction_sections(output_text: str) -> str:
    """只保留 R1_v2 下期預測與 F5/G1/H1 協調候選球兩段。"""

    first_marker = "====== R1_v2 下期分組配額預測 ======"
    end_marker = "============== 完結 =============="
    first_index = output_text.find(first_marker)
    if first_index == -1:
        return output_text

    section_text = output_text[first_index:].strip()
    end_index = section_text.find(end_marker)
    if end_index == -1:
        return clean_prediction_text(section_text)
    return clean_prediction_text(section_text[: end_index + len(end_marker)].strip())


def add_weekday_to_next_date(line: str) -> str:
    prefix = "下期日期："
    if not line.startswith(prefix):
        return line
    date_text = line.removeprefix(prefix).strip()
    try:
        draw_date = datetime.strptime(date_text, "%Y-%m-%d")
    except ValueError:
        return line
    return f"{prefix}{date_text}，{WEEKDAY_TEXT[draw_date.weekday()]}"


def parse_integrated_candidate_line(line: str) -> tuple[list[int], str] | None:
    prefix = "整合候選池："
    marker = "/>"
    if not line.startswith(prefix) or marker not in line:
        return None
    nums_text, count_text = line.removeprefix(prefix).split(marker, 1)
    nums: list[int] = []
    for part in nums_text.split(","):
        part = part.strip()
        if part.isdigit():
            nums.append(int(part))
    return nums, count_text.strip()


def clean_prediction_text(text: str) -> str:
    cleaned_lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("提示："):
            continue
        cleaned_lines.append(add_weekday_to_next_date(line))
    return "\n".join(cleaned_lines).strip()


@st.cache_data(show_spinner=False)
def load_ball_image_base64(num: int) -> str:
    img_path = BALLS_DIR / f"{num}.png"
    if not img_path.exists():
        return ""
    return base64.b64encode(img_path.read_bytes()).decode("utf-8")


def build_ball_html(nums: list[int]) -> str:
    parts: list[str] = []
    for num in nums:
        b64 = load_ball_image_base64(num)
        if b64:
            parts.append(
                "<img "
                f"src='data:image/png;base64,{b64}' "
                "class='r1v2-ball-img' "
                f"alt='{num}' "
                "/>"
            )
        else:
            parts.append(f"<span class='r1v2-ball-fallback'>{num}</span>")
    return "".join(parts)


def text_to_html(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        parsed = parse_integrated_candidate_line(line)
        if parsed is None:
            lines.append(html.escape(line))
            continue
        nums, count_text = parsed
        lines.append(
            "<div class='r1v2-candidate-row'>"
            "<div class='r1v2-candidate-label'>整合候選球號：</div>"
            "<div class='r1v2-candidate-balls-line'>"
            f"<span class='r1v2-balls'>{build_ball_html(nums)}</span>"
            f"<span class='r1v2-count'>/> {html.escape(count_text)}</span>"
            "</div>"
            "</div>"
        )
    return "<br/>".join(lines)


def render_text_block(text: str) -> None:
    st.markdown(
        """
        <style>
        .r1v2-text {
            white-space: pre-wrap;
            overflow-x: auto;
            border: 1px solid #d7d7d7;
            border-radius: 6px;
            padding: 0.75rem;
            font-size: 1.02rem;
            line-height: 1.65;
            color: #111;
            background: #fff;
        }
        .r1v2-candidate-row {
            display: flex;
            flex-direction: column;
            align-items: flex-start;
            gap: 0.25rem;
            margin: 0.15rem 0;
        }
        .r1v2-candidate-label {
            font-weight: 800;
        }
        .r1v2-candidate-balls-line {
            display: flex;
            align-items: center;
            gap: 0.45rem;
            flex-wrap: wrap;
        }
        .r1v2-balls {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            flex-wrap: wrap;
        }
        .r1v2-ball-img {
            width: 32px;
            height: 32px;
            object-fit: contain;
        }
        .r1v2-ball-fallback {
            display: inline-flex;
            width: 30px;
            height: 30px;
            align-items: center;
            justify-content: center;
            border-radius: 50%;
            background: #f2f2f2;
            border: 1px solid #999;
            font-weight: 800;
        }
        .r1v2-count {
            font-weight: 800;
        }
        @media (max-width: 430px) {
            .r1v2-text {
                font-size: 0.98rem;
                line-height: 1.55;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(f"<div class='r1v2-text'>{text_to_html(text)}</div>", unsafe_allow_html=True)


def main() -> None:
    st.subheader("R1_v2 Fortune Code 分組配額預測")
    st.caption("讀入 F5 / G1 / H1 候選球，再用 R1_v2 分組配額協調。")

    if not R1_V2_SCRIPT.exists():
        st.error(f"找不到程式：{R1_V2_SCRIPT}")
        return

    if st.button("更新 R1_v2 預測", key="r1_v2_run_button", width="stretch"):
        with st.spinner("正在執行 R1_v2..."):
            try:
                output_text = run_r1_v2_text()
            except RuntimeError as exc:
                st.error(f"執行 R1_v2 失敗：{exc}")
                return
            st.session_state["r1_v2_prediction_text"] = extract_prediction_sections(output_text)

    prediction_text = st.session_state.get("r1_v2_prediction_text")
    if isinstance(prediction_text, str) and prediction_text:
        render_text_block(prediction_text)
    else:
        st.info("按「更新 R1_v2 預測」顯示下期分組配額及候選球。")
