from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from classifier import classify_paper
from generator import generate_slide_contents
from llm import BaseLLM
from models import ClassifiedPaper, ParsedPaper, PresentationPlan
from parser import parse_pdf, parse_text_file
from planner import build_presentation_plan
from ppt_builder import build_ppt


@dataclass
class AgentResult:
    parsed: ParsedPaper
    classified: ClassifiedPaper
    plan: PresentationPlan
    output_path: str


class PaperToPPTAgent:
    def __init__(self, llm: Optional[BaseLLM] = None) -> None:
        self.llm = llm

    def run(
        self,
        output_path: str,
        pdf_path: Optional[str] = None,
        text_path: Optional[str] = None,
        template_path: Optional[str] = None,
    ) -> AgentResult:
        if not pdf_path and not text_path:
            raise ValueError("Either pdf_path or text_path must be provided.")

        if pdf_path:
            parsed = parse_pdf(pdf_path)
        else:
            parsed = parse_text_file(text_path or "")

        classified = classify_paper(parsed)
        plan = build_presentation_plan(language=classified.language)
        slides = generate_slide_contents(classified, plan, llm=self.llm)
        final_output = build_ppt(slides, output_path=output_path, template_path=template_path)

        return AgentResult(
            parsed=parsed,
            classified=classified,
            plan=plan,
            output_path=final_output,
        )
