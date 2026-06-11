from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ParsedFigure:
    page_index: int
    figure_id: str
    caption: str = ""
    image_path: str = ""


@dataclass
class ParsedTable:
    page_index: int
    table_id: str
    markdown: str
    row_count: int = 0
    col_count: int = 0
    image_path: str = ""


@dataclass
class ParsedPaper:
    source_name: str
    raw_text: str
    title: str = ""
    abstract: str = ""
    language: str = "en"
    sections: Dict[str, str] = field(default_factory=dict)
    figures: List[ParsedFigure] = field(default_factory=list)
    tables: List[ParsedTable] = field(default_factory=list)
    ocr_applied: bool = False
    dual_column_reflowed: bool = False


@dataclass
class ClassifiedPaper:
    title: str
    abstract: str
    background: str
    method: str
    experiment_setup: str
    results: str
    conclusion: str
    language: str = "en"
    extra_sections: Dict[str, str] = field(default_factory=dict)


@dataclass
class SlidePlan:
    slide_key: str
    title: str
    goal: str
    max_bullets: int = 4


@dataclass
class SlideContent:
    slide_key: str
    title: str
    bullets: List[str]
    notes: Optional[str] = None
    core_points: List[str] = field(default_factory=list)
    draft_notes: Optional[str] = None


@dataclass
class PresentationPlan:
    slides: List[SlidePlan]
