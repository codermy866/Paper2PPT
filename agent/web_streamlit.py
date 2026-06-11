from __future__ import annotations

import io
import sys
import tempfile
from pathlib import Path
from typing import Optional

import streamlit as st


# Ensure local imports work when launched from repo root.
THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))

from agent import PaperToPPTAgent  # noqa: E402
from config import resolve_llm_provider  # noqa: E402
from llm import MockLLM, create_llm  # noqa: E402


def _save_uploaded_file(uploaded_file, target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with target_path.open("wb") as f:
        f.write(uploaded_file.getbuffer())


def main() -> None:
    st.set_page_config(page_title="Paper to PPT Agent", layout="centered")
    st.title("论文到可编辑 PPT（Paper to PPT Agent）")

    st.markdown(
        "上传论文 PDF（必填），可选上传 PPTX 模板（用于复用模板版式与配色）。"
    )

    pdf_file = st.file_uploader("上传论文 PDF", type=["pdf"])
    template_file = st.file_uploader("上传 PPTX 模板（可选）", type=["pptx"])

    mock_llm = st.checkbox("生成演讲 notes 使用 mock 模式（无 API key 时推荐）", value=True)
    use_real_llm = st.checkbox("使用 OpenAI（需配置 OPENAI_API_KEY）", value=False)

    output_name = st.text_input("输出文件名", value="paper_report.pptx")

    generate_clicked = st.button("开始生成 PPTX", type="primary", disabled=pdf_file is None)

    if generate_clicked and pdf_file is not None:
        if mock_llm:
            llm = MockLLM()
        elif use_real_llm:
            llm = create_llm("openai")
        else:
            provider = resolve_llm_provider()
            llm = create_llm(provider) if provider in {"openai", "mock"} else None
        agent = PaperToPPTAgent(llm=llm)

        with st.spinner("正在解析论文并生成 PPT，请稍等..."):
            with tempfile.TemporaryDirectory() as tmpdir:
                tmpdir_path = Path(tmpdir)
                pdf_path = tmpdir_path / pdf_file.name
                _save_uploaded_file(pdf_file, pdf_path)

                template_path: Optional[str] = None
                if template_file is not None:
                    tmp_template_path = tmpdir_path / template_file.name
                    _save_uploaded_file(template_file, tmp_template_path)
                    template_path = str(tmp_template_path)

                output_path = tmpdir_path / output_name
                result = agent.run(
                    output_path=str(output_path),
                    pdf_path=str(pdf_path),
                    text_path=None,
                    template_path=template_path,
                )

                ppt_bytes = output_path.read_bytes()

                st.success("生成完成")
                st.write(f"论文标题：{result.classified.title}")
                st.write(f"生成页数：{len(result.plan.slides)}")

                st.download_button(
                    label="下载生成的 PPTX",
                    data=ppt_bytes,
                    file_name=output_name,
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                )


if __name__ == "__main__":
    main()

