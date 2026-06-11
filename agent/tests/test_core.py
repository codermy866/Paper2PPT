from __future__ import annotations

from pathlib import Path

import pytest

from classifier import classify_paper
from eval_runner import run_batch_evaluation
from parser import parse_text_file
from pdf_enhanced import detect_language, extract_tables_from_text, is_text_garbled, reflow_dual_column_text
from planner import build_presentation_plan


FIXTURES = Path(__file__).resolve().parent.parent / "eval" / "fixtures"


def test_detect_language_chinese():
    assert detect_language("这是一段中文论文摘要，包含方法、实验和结论。") == "zh"


def test_detect_language_english():
    assert detect_language("This paper proposes a Transformer architecture for NLP.") == "en"


def test_garbled_text_detection():
    assert is_text_garbled("����ÃÂâ€œ\x00\x01" * 8) is True
    assert is_text_garbled("这是一段正常的中文论文摘要，包含方法、实验、结果和结论。") is False


def test_dual_column_reflow():
    left = [f"Left sentence {i} with enough length." for i in range(6)]
    right = [f"Right sentence {i} with enough length." for i in range(6)]
    page = "\n".join(left + right)
    reflowed, applied = reflow_dual_column_text(page)
    assert applied is True
    assert "Left sentence 0" in reflowed
    assert reflowed.index("Left sentence 0") < reflowed.index("Right sentence 0")


def test_parse_and_classify_english_fixture():
    parsed = parse_text_file(str(FIXTURES / "sample_en.txt"))
    classified = classify_paper(parsed)
    assert "Attention" in parsed.title
    assert classified.background
    assert classified.method
    assert classified.results


def test_parse_chinese_fixture():
    parsed = parse_text_file(str(FIXTURES / "sample_zh.txt"))
    assert parsed.language == "zh"
    assert "Transformer" in parsed.title or "Transformer" in parsed.raw_text


def test_table_extraction_from_markdown_block():
    text = "Header\n\n| Col A | Col B |\n| --- | --- |\n| 1 | 2 |\n| 3 | 4 |"
    tables = extract_tables_from_text(text)
    assert len(tables) >= 1
    assert tables[0].row_count >= 2


def test_presentation_plan_page_count():
    # The minimum plan is the five required core-analysis pages, kept in
    # canonical seminar order.
    minimal = build_presentation_plan(page_count=5)
    assert [s.slide_key for s in minimal.slides] == [
        "background",
        "research_questions",
        "method",
        "experiment_setup",
        "results",
    ]

    # Requests below the minimum are clamped up to five pages.
    assert len(build_presentation_plan(page_count=3).slides) == 5

    # Analysis pages are added back by priority; discussion_questions is excluded.
    for pc in range(5, 11):
        plan = build_presentation_plan(page_count=pc)
        assert len(plan.slides) == pc
        assert all(s.slide_key != "discussion_questions" for s in plan.slides)

    # Beyond the analysis pages, core sections split into detail pages that
    # follow their parent, with the final assessment last.
    plan12 = build_presentation_plan(page_count=12)
    assert len(plan12.slides) == 12
    assert plan12.slides[-1].slide_key == "conclusion"
    keys12 = [s.slide_key for s in plan12.slides]
    assert keys12.index("method_detail_1") == keys12.index("method") + 1

    # Every page count in range produces exactly that many slides.
    for pc in range(5, 21):
        assert len(build_presentation_plan(page_count=pc).slides) == pc

    def section_pages(plan, base):
        return sum(
            1
            for s in plan.slides
            if s.slide_key == base or s.slide_key.startswith(base + "_detail_")
        )

    # Method and experiment split before background and results.
    p12 = build_presentation_plan(page_count=12)
    assert section_pages(p12, "method") == 3
    assert section_pages(p12, "experiment_setup") == 1
    assert section_pages(p12, "background") == 1
    assert section_pages(p12, "results") == 1

    # Background is capped at 3 pages and results at 2 pages; method and
    # experiment keep growing past those caps.
    for pc in range(5, 21):
        plan = build_presentation_plan(page_count=pc)
        assert section_pages(plan, "background") <= 3
        assert section_pages(plan, "results") <= 2
    p20 = build_presentation_plan(page_count=20)
    assert section_pages(p20, "background") == 3
    assert section_pages(p20, "results") == 2
    assert section_pages(p20, "method") >= 4
    assert section_pages(p20, "experiment_setup") >= 4


def test_batch_evaluation_report():
    report = run_batch_evaluation()
    assert report["case_count"] >= 3
    assert "overall_score" in report
    assert report["overall_score"] >= 0.75
    assert report.get("passed") is True


def test_eval_gate():
    from eval_runner import assert_eval_gate

    assert_eval_gate(run_batch_evaluation())


def test_chinese_abstract_and_sections():
    parsed = parse_text_file(str(FIXTURES / "sample_zh.txt"))
    assert len(parsed.abstract) >= 20
    classified = classify_paper(parsed)
    assert classified.method
    assert classified.results


def test_task_store_roundtrip(tmp_path, monkeypatch):
    from task_store import TaskStore

    db = tmp_path / "tasks.db"
    monkeypatch.setenv("TASK_DB", str(db))
    store = TaskStore(db_path=db)
    store.save_task("abc", {"task_id": "abc", "status": "queued"})
    loaded = store.get_task("abc")
    assert loaded is not None
    assert loaded["task_id"] == "abc"
    store.add_version("abc", "v1", "initial", {"slide_count": 3})
    versions = store.list_versions("abc")
    assert len(versions) == 1
