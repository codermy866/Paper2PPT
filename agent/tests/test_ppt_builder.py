from __future__ import annotations

from pathlib import Path

from models import ParsedTable, SlideContent
from ppt_builder import build_ppt


def test_ppt_builder_with_table_slide(tmp_path):
    table = ParsedTable(
        page_index=1,
        table_id="t1",
        markdown="| A | B |\n| --- | --- |\n| 1 | 2 |",
        row_count=2,
        col_count=2,
    )
    slides = [
        SlideContent(slide_key="title", title="Demo", bullets=["Point A"]),
    ]
    out = tmp_path / "demo.pptx"
    build_ppt(
        slides=slides,
        output_path=str(out),
        style_key="blue",
        tables=[table],
    )
    assert out.exists()
    assert out.stat().st_size > 1000
