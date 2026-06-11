from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from classifier import classify_paper
from config import EVAL_FIXTURES_DIR, OUTPUTS_DIR, resolve_llm_provider
from generator import generate_slide_contents
from llm import create_llm
from parser import parse_text_file
from planner import build_presentation_plan
from text_utils import content_length, is_substantial


DEFAULT_MIN_OVERALL = 0.75


def _score_title(parsed_title: str, expected: str) -> float:
    if not expected:
        return 1.0
    return 1.0 if expected.lower() in parsed_title.lower() else 0.0


def _score_section_coverage(classified: Any, required: List[str], language: str) -> float:
    if not required:
        return 1.0
    hits = 0
    for key in required:
        value = getattr(classified, key, "")
        if value and is_substantial(value, language=language):
            hits += 1
    return hits / len(required)


def _score_abstract(parsed_abstract: str, language: str) -> float:
    if language == "zh":
        return 1.0 if content_length(parsed_abstract, language) >= 20 else 0.0
    return 1.0 if content_length(parsed_abstract, language) >= 5 else 0.0


def _evaluate_fixture(path: Path, spec: Dict[str, Any], llm_provider: Optional[str] = None) -> Dict[str, Any]:
    parsed = parse_text_file(str(path))
    classified = classify_paper(parsed)
    language = spec.get("language", parsed.language)
    plan = build_presentation_plan(page_count=spec.get("page_count", 8), language=language)
    provider = llm_provider or resolve_llm_provider()
    llm = create_llm(provider) if provider in {"openai", "mock"} else None
    slides = generate_slide_contents(classified, plan, llm=llm)

    metrics = {
        "title_match": _score_title(parsed.title, spec.get("expected_title", "")),
        "abstract_nonempty": _score_abstract(parsed.abstract, language),
        "section_coverage": _score_section_coverage(
            classified, spec.get("required_sections", []), language
        ),
        "slide_count_ok": 1.0 if len(slides) == spec.get("page_count", 8) else 0.0,
        "language_match": 1.0 if parsed.language == language else 0.0,
    }
    metrics["overall"] = round(sum(metrics.values()) / len(metrics), 4)
    return {
        "fixture": path.name,
        "title": parsed.title,
        "language": parsed.language,
        "slide_count": len(slides),
        "llm_provider": provider if llm else "local",
        "metrics": metrics,
    }


def run_batch_evaluation(
    min_overall: Optional[float] = None,
    llm_provider: Optional[str] = None,
) -> Dict[str, Any]:
    EVAL_FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = EVAL_FIXTURES_DIR / "manifest.json"
    if not manifest_path.exists():
        manifest = {"min_overall_score": DEFAULT_MIN_OVERALL, "cases": []}
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    threshold = min_overall if min_overall is not None else float(
        manifest.get("min_overall_score", DEFAULT_MIN_OVERALL)
    )
    results: List[Dict[str, Any]] = []
    cases = manifest.get("cases", [])
    for case in cases:
        fixture = EVAL_FIXTURES_DIR / case["file"]
        if not fixture.exists():
            results.append(
                {
                    "fixture": case["file"],
                    "error": "missing fixture",
                    "metrics": {"overall": 0.0},
                }
            )
            continue
        results.append(_evaluate_fixture(fixture, case, llm_provider=llm_provider))

    overall = round(
        sum(item.get("metrics", {}).get("overall", 0.0) for item in results) / max(len(results), 1),
        4,
    )
    passed = overall >= threshold
    for item, case in zip(results, cases):
        if "error" in item:
            passed = False
            continue
        case_min = float(case.get("min_score", 0.0))
        if item.get("metrics", {}).get("overall", 0.0) < case_min:
            passed = False

    report = {
        "overall_score": overall,
        "min_overall_score": threshold,
        "passed": passed,
        "case_count": len(results),
        "results": results,
    }
    out_path = Path(OUTPUTS_DIR) / "eval_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def assert_eval_gate(report: Optional[Dict[str, Any]] = None) -> None:
    report = report or run_batch_evaluation()
    if not report.get("passed"):
        failures = [
            f"{item['fixture']}: {item.get('metrics', {}).get('overall', 0)}"
            for item in report.get("results", [])
            if item.get("metrics", {}).get("overall", 1.0) < float(
                next(
                    (c.get("min_score", DEFAULT_MIN_OVERALL) for c in []),
                    DEFAULT_MIN_OVERALL,
                )
            )
        ]
        raise AssertionError(
            f"Eval gate failed: overall={report.get('overall_score')} "
            f"min={report.get('min_overall_score')}; failures={failures or report.get('results')}"
        )
