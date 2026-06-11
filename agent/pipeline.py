from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from classifier import classify_paper
from config import OUTPUTS_DIR, TOTAL_STEPS, resolve_llm_provider, style_accent
from generator import generate_slide_contents
from html_builder import build_html_deck
from llm import BaseLLM, create_llm
from models import ClassifiedPaper, ParsedFigure, ParsedPaper, PresentationPlan, SlideContent, SlidePlan
from parser import parse_pdf, parse_text_file
from planner import build_presentation_plan
from ppt_builder import build_ppt
from task_store import TaskStore

ALL_LAYOUTS = {
    "arch-diagram",
    "big-quote",
    "bullets",
    "chart-bar",
    "chart-line",
    "chart-pie",
    "chart-radar",
    "code",
    "comparison",
    "cover",
    "cta",
    "diff",
    "flow-diagram",
    "figure-compare",
    "figure-hero",
    "figure-method",
    "figure-results",
    "gantt",
    "image-grid",
    "image-hero",
    "image-left",
    "image-right",
    "evidence-cards",
    "critique-panel",
    "kpi-grid",
    "method-swimlane",
    "mindmap",
    "process-steps",
    "pros-cons",
    "question-matrix",
    "roadmap",
    "section-divider",
    "stat-highlight",
    "statement",
    "table",
    "terminal",
    "thanks",
    "three-column",
    "timeline",
    "toc",
    "todo-checklist",
    "two-column",
}


LAYOUT_LABELS = {
    "arch-diagram": "架构图页",
    "big-quote": "重点引文页",
    "bullets": "要点页",
    "chart-bar": "柱状图页",
    "chart-line": "折线图页",
    "chart-pie": "饼图页",
    "chart-radar": "雷达图页",
    "code": "技术细节页",
    "comparison": "对比页",
    "cover": "封面页",
    "cta": "行动建议页",
    "diff": "差异说明页",
    "flow-diagram": "流程图页",
    "figure-compare": "配图对比页",
    "figure-hero": "配图主视觉页",
    "figure-method": "方法配图页",
    "figure-results": "结果配图页",
    "gantt": "甘特图页",
    "image-grid": "图片网格页",
    "image-hero": "大图页",
    "image-left": "左图右文页",
    "image-right": "左文右图页",
    "evidence-cards": "证据卡片页",
    "critique-panel": "审稿意见页",
    "kpi-grid": "指标卡片页",
    "method-swimlane": "方法泳道页",
    "mindmap": "脑图页",
    "process-steps": "步骤页",
    "pros-cons": "优劣分析页",
    "question-matrix": "研究问题矩阵页",
    "roadmap": "路线图页",
    "section-divider": "章节分隔页",
    "stat-highlight": "数据高亮页",
    "statement": "核心论点页",
    "table": "表格页",
    "terminal": "终端页",
    "thanks": "结束页",
    "three-column": "三栏页",
    "timeline": "时间线页",
    "toc": "目录页",
    "todo-checklist": "清单页",
    "two-column": "双栏页",
}


def _layout_label(layout_name: str) -> str:
    return LAYOUT_LABELS.get(layout_name, layout_name)


def _figure_caption(figure: Any) -> str:
    caption = getattr(figure, "caption", "") or getattr(figure, "figure_id", "")
    match = re.search(r"Figure from page\s+(\d+)", caption, re.IGNORECASE)
    if match:
        return f"第 {match.group(1)} 页图片"
    return caption


def _extract_figure_reference(text: str) -> tuple[str, str]:
    normalized = text or ""
    patterns = [
        (r"\b(?:fig(?:ure)?\.?)\s*([0-9]+[a-zA-Z]?)\b", "figure"),
        (r"\btable\s*([0-9]+[a-zA-Z]?)\b", "table"),
        (r"(?:图|图表)\s*([0-9]+[a-zA-Z]?)", "figure"),
        (r"表\s*([0-9]+[a-zA-Z]?)", "table"),
    ]
    for pattern, ref_type in patterns:
        match = re.search(pattern, normalized, re.IGNORECASE)
        if match:
            return ref_type, match.group(1).lower()
    return "", ""


def _lookup_reference_context(raw_text: str, ref_type: str, ref_no: str) -> str:
    if not raw_text or not ref_type or not ref_no:
        return ""
    escaped_no = re.escape(ref_no)
    if ref_type == "figure":
        marker = rf"(?:fig(?:ure)?\.?\s*{escaped_no}|图\s*{escaped_no}|图表\s*{escaped_no})"
    else:
        marker = rf"(?:table\s*{escaped_no}|表\s*{escaped_no})"
    match = re.search(marker, raw_text, re.IGNORECASE)
    if not match:
        return ""
    start = max(0, match.start() - 260)
    end = min(len(raw_text), match.end() + 420)
    snippet = re.sub(r"\s+", " ", raw_text[start:end]).strip()
    return snippet[:520]


def _title_quality_issue(title: str, source_name: str, language: str) -> str:
    cleaned = re.sub(r"\s+", " ", title or "").strip()
    source_stem = Path(source_name or "").stem.replace("_", " ").strip().lower()
    lower = cleaned.lower()
    if not cleaned:
        return "未识别到标题"
    if source_stem and lower == source_stem:
        return "标题可能只是文件名"
    if len(cleaned) < 8:
        return "标题过短"
    if len(cleaned) > 180:
        return "标题过长，可能混入作者或摘要"
    if re.search(r"\b(?:abstract|keywords?|introduction|department|university|institute|doi|arxiv|@)\b", lower):
        return "标题可能混入摘要、作者单位或 DOI 信息"
    visible = [ch for ch in cleaned if not ch.isspace()]
    odd = sum(1 for ch in visible if not (ch.isalnum() or "\u4e00" <= ch <= "\u9fff" or ch in " :：-/()（）,，."))
    if visible and odd / len(visible) > 0.18:
        return "标题包含较多异常字符"
    if language == "zh" and not re.search(r"[\u4e00-\u9fff]", cleaned):
        return "中文论文标题未识别为中文"
    return ""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _summarize(text: str, limit: int = 420) -> str:
    clean = " ".join(text.split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3].rstrip() + "..."


def _clean_user_figure_description(text: str) -> str:
    clean = re.sub(r"\s+", " ", text or "").strip()
    if not clean:
        return ""
    clean = re.sub(r"\.(?:png|jpe?g|webp|gif|bmp|tiff?)\b", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"[_\-]+", " ", clean)
    clean = re.sub(
        r"^(?:screenshot|screen shot|image|figure|fig|table|图片|截图|图表|表格|图|表)\s*[0-9一二三四五六七八九十A-Za-z]*\s*[-_:：.、]*\s*",
        "",
        clean,
        flags=re.IGNORECASE,
    )
    clean = re.sub(r"\b(?:screenshot|screen shot|image|figure|fig|table|图片|截图)\s*[-_:：]*", "", clean, flags=re.IGNORECASE)
    clean = clean.strip(" .,:;，。；：-_")
    if not clean or re.fullmatch(r"(?:\d+|user figure \d+|figure \d+|fig \d+|图片 \d+|图 \d+)", clean, re.IGNORECASE):
        return ""
    return clean[:36].strip()


def _figure_title_phrase(description: str, filename: str, kind: str, language: str) -> str:
    phrase = _clean_user_figure_description(description) or _clean_user_figure_description(Path(filename or "").stem)
    if not phrase:
        return ""
    phrase = re.split(r"[。；;]|(?:\s+-\s+)", phrase, maxsplit=1)[0].strip()
    comma_split = re.split(r"[，,]", phrase, maxsplit=1)
    if len(comma_split) > 1 and len(comma_split[0].strip()) >= 6:
        phrase = comma_split[0].strip()
    if language == "zh":
        if kind == "method" and "网络" in phrase and "结构" not in phrase:
            return f"{phrase}结构"
        if kind == "method" and not re.search(r"(方法|模型|网络|框架|流程|结构|机制|算法)", phrase):
            return f"{phrase} 方法机制"
        if kind == "setup" and not re.search(r"(实验|数据|指标|设置|样本|基准)", phrase):
            return f"{phrase} 实验设置"
        if kind == "table" and not re.search(r"(表|指标|统计|对比|汇总|数据|基准)", phrase):
            return f"{phrase} 表格对比"
        if kind == "results" and not re.search(r"(结果|性能|对比|消融|恢复率|准确率|指标|趋势)", phrase):
            return f"{phrase} 结果对比"
    else:
        if kind == "method" and not re.search(r"\b(method|model|network|framework|pipeline|architecture|algorithm)\b", phrase, re.IGNORECASE):
            return f"{phrase} Method"
        if kind == "setup" and not re.search(r"\b(experiment|data|dataset|metric|setup|benchmark)\b", phrase, re.IGNORECASE):
            return f"{phrase} Experimental Setup"
        if kind == "table" and not re.search(r"\b(table|metric|summary|comparison|benchmark|data)\b", phrase, re.IGNORECASE):
            return f"{phrase} Table Summary"
        if kind == "results" and not re.search(r"\b(result|performance|comparison|ablation|accuracy|metric|trend)\b", phrase, re.IGNORECASE):
            return f"{phrase} Results"
    return phrase


def _timeline_entry(stage_id: str, title: str, body: str, status: str) -> Dict[str, str]:
    return {
        "id": uuid.uuid4().hex[:12],
        "stage_id": stage_id,
        "title": title,
        "body": body,
        "status": status,
        "created_at": _now_iso(),
    }


def _build_result_cards(classified: ClassifiedPaper, plan: PresentationPlan, slides: Optional[List[SlideContent]] = None) -> List[Dict[str, str]]:
    outline = "\n".join(f"{idx + 1}. {slide.title}" for idx, slide in enumerate(plan.slides))
    if slides:
        cards = [{"id": "outline", "title": "PPT 大纲", "body": outline}]
        for idx, slide in enumerate(slides):
            body_parts = []
            if slide.core_points:
                body_parts.append("每页核心观点：\n" + "\n".join(f"- {point}" for point in slide.core_points[:5]))
            body_parts.append("PPT 页面文字：\n" + "\n".join(f"- {bullet}" for bullet in slide.bullets[:4]))
            if slide.draft_notes:
                body_parts.append(f"备注草稿：{slide.draft_notes}")
            if slide.notes:
                body_parts.append(f"最终讲解备注：{slide.notes}")
            body = "\n\n".join(body_parts)
            cards.append(
                {
                    "id": f"module-{slide.slide_key}-{idx}",
                    "title": f"{idx + 1}. {slide.title}",
                    "body": body,
                }
            )
        return cards
    return [
        {"id": "content", "title": "内容提炼", "body": _summarize(classified.background)},
        {"id": "method", "title": "方法概述", "body": _summarize(classified.method)},
        {"id": "outline", "title": "PPT 大纲", "body": outline},
        {"id": "results", "title": "实验结果", "body": _summarize(classified.results)},
    ]


def _plan_from_task(task: Dict[str, Any], classified: ClassifiedPaper) -> PresentationPlan:
    plan_data = task.get("plan") or {}
    raw_slides = plan_data.get("slides") or []
    if raw_slides:
        return PresentationPlan(
            slides=[
                SlidePlan(
                    slide_key=str(slide.get("slide_key") or f"extra_section_{idx + 1}"),
                    title=str(slide.get("title") or f"Slide {idx + 1}"),
                    goal=str(slide.get("goal") or ""),
                    max_bullets=int(slide.get("max_bullets") or 4),
                )
                for idx, slide in enumerate(raw_slides)
            ]
        )
    return build_presentation_plan(page_count=task["config"]["page_count"], language=classified.language)


def _adapt_plan_to_user_figures(plan: PresentationPlan, config: Dict[str, Any], language: str) -> PresentationPlan:
    figure_infos = [item for item in config.get("supplemental_figure_paths") or [] if isinstance(item, dict)]
    if not figure_infos:
        return plan

    requirements: Dict[str, List[str]] = {"method": [], "experiment_setup": [], "results": []}
    for item in figure_infos:
        kind = str(item.get("kind") or "other")
        title_phrase = _figure_title_phrase(
            str(item.get("description") or ""),
            str(item.get("filename") or ""),
            kind,
            language,
        )
        if kind == "method":
            requirements["method"].append(title_phrase)
        elif kind == "setup":
            requirements["experiment_setup"].append(title_phrase)
        elif kind in {"results", "table"}:
            requirements["results"].append(title_phrase)

    if not any(requirements.values()):
        return plan

    slides = list(plan.slides)

    def section_count(base_key: str) -> int:
        return sum(1 for slide in slides if slide.slide_key == base_key or slide.slide_key.startswith(base_key + "_detail_"))

    def next_occurrence(base_key: str) -> int:
        max_seen = 0
        for slide in slides:
            if slide.slide_key.startswith(base_key + "_detail_"):
                suffix = slide.slide_key.rsplit("_", 1)[-1]
                if suffix.isdigit():
                    max_seen = max(max_seen, int(suffix))
        return max_seen + 1

    def insert_after_section(base_key: str, new_slide: SlidePlan) -> None:
        insert_at = None
        for idx, slide in enumerate(slides):
            if slide.slide_key == base_key or slide.slide_key.startswith(base_key + "_detail_"):
                insert_at = idx + 1
        if insert_at is None:
            insert_at = max(0, len(slides) - 1)
        slides.insert(insert_at, new_slide)

    def optional_page_index() -> Optional[int]:
        optional_priority = [
            "research_inspiration",
            "limitations",
            "innovation",
            "discussion_questions",
            "conclusion",
            "title",
        ]
        for optional_key in optional_priority:
            idx = next((idx for idx, slide in enumerate(slides) if slide.slide_key == optional_key), None)
            if idx is not None:
                return idx
        return None

    def replace_optional_page_with_detail(base_key: str, new_slide: SlidePlan) -> bool:
        # Page counts above the five core seminar pages are flexible. Prefer
        # turning those optional analysis pages into figure detail pages instead
        # of silently increasing the deck beyond the user's selected count.
        optional_index = optional_page_index()
        if optional_index is None:
            return False
        slides.pop(optional_index)
        insert_after_section(base_key, new_slide)
        return True

    def title_for(base_key: str, ordinal: int, description: str) -> str:
        desc = _clean_user_figure_description(description)
        if language == "zh":
            if base_key == "method":
                return f"方法设计：{desc}" if desc else f"方法框架解读 {ordinal}"
            if base_key == "experiment_setup":
                return f"实验设置：{desc}" if desc else f"实验与数据说明 {ordinal}"
            return f"结果解读：{desc}" if desc else f"关键结果解读 {ordinal}"
        if base_key == "method":
            return f"Method Design: {desc}" if desc else f"Method Framework Interpretation {ordinal}"
        if base_key == "experiment_setup":
            return f"Experimental Setup: {desc}" if desc else f"Experimental Setup and Data {ordinal}"
        return f"Result Interpretation: {desc}" if desc else f"Key Result Interpretation {ordinal}"

    goals = {
        "method": "结合用户上传的方法图解释模型结构、算法流程或核心模块",
        "experiment_setup": "结合用户上传的实验/数据图说明数据集、指标或实验设置",
        "results": "结合用户上传的结果图解释实验趋势、对比结论和支撑观点",
    }
    goals_en = {
        "method": "Explain the model structure, algorithm flow, or key modules using the user-provided method figure",
        "experiment_setup": "Explain datasets, metrics, or experimental setup using the user-provided setup figure",
        "results": "Interpret trends, comparisons, and claims using the user-provided result figure",
    }

    for base_key, descriptions in requirements.items():
        required_count = len(descriptions)
        existing_indices = [
            idx
            for idx, slide in enumerate(slides)
            if slide.slide_key == base_key or slide.slide_key.startswith(base_key + "_detail_")
        ]
        for ordinal, slide_idx in enumerate(existing_indices[:required_count], start=1):
            desc = descriptions[ordinal - 1] if ordinal - 1 < len(descriptions) else ""
            slide = slides[slide_idx]
            slides[slide_idx] = SlidePlan(
                slide_key=slide.slide_key,
                title=title_for(base_key, ordinal, desc),
                goal=(goals if language == "zh" else goals_en)[base_key],
                max_bullets=slide.max_bullets,
            )
        while section_count(base_key) < required_count and (len(slides) < 20 or optional_page_index() is not None):
            occurrence = next_occurrence(base_key)
            ordinal = section_count(base_key) + 1
            desc = descriptions[ordinal - 1] if ordinal - 1 < len(descriptions) else ""
            new_slide = SlidePlan(
                slide_key=f"{base_key}_detail_{occurrence}",
                title=title_for(base_key, ordinal, desc),
                goal=(goals if language == "zh" else goals_en)[base_key],
                max_bullets=4,
            )
            if not replace_optional_page_with_detail(base_key, new_slide):
                insert_after_section(base_key, new_slide)

    return PresentationPlan(slides=slides)


def _apply_instruction(slides: List[SlideContent], instruction: str, language: str = "en") -> None:
    # Feedback is already stored in task config and passed to regeneration prompts.
    # Do not inject raw user feedback into slide content.
    return


def _propose_layout_names(slides: List[SlideContent]) -> List[str]:
    layouts: List[str] = []
    for idx, slide in enumerate(slides):
        if idx == 0 or slide.slide_key == "title":
            layouts.append("cover")
            continue
        if idx == len(slides) - 1 or slide.slide_key.startswith("conclusion"):
            layouts.append("thanks")
            continue

        bullet_count = len(slide.bullets)
        joined = " ".join(slide.bullets).lower()
        title_key = slide.title.lower()
        if slide.slide_key == "research_questions" or any(token in title_key for token in ("研究问题", "research question")):
            layouts.append("question-matrix")
        elif slide.slide_key in {"limitations", "discussion_questions"} or any(token in title_key for token in ("不足", "追问", "limitation", "question")):
            layouts.append("critique-panel")
        elif slide.slide_key == "innovation" or any(token in title_key for token in ("创新", "innovation")):
            layouts.append("evidence-cards")
        elif slide.slide_key == "research_inspiration" or any(token in title_key for token in ("启发", "inspiration")):
            layouts.append("statement")
        elif any(token in title_key for token in ("方法框架", "method framework")):
            layouts.append("method-swimlane")
        elif any(token in joined for token in ("table", "表", "|")):
            layouts.append("table")
        elif any(token in joined for token in ("code", "算法", "伪代码", "python", "loss", "train")):
            layouts.append("code")
        elif bullet_count >= 6:
            layouts.append("three-column")
        elif bullet_count >= 4:
            layouts.append("two-column")
        else:
            layouts.append("bullets")
    return layouts


def _bind_figures_to_slides(slides: List[SlideContent], figures: List[Any]) -> Dict[int, int]:
    if not slides or not figures:
        return {}

    bindings: Dict[int, int] = {}
    used_figures: set[int] = set()

    groups = {
        "method": {"method", "methods", "framework", "architecture", "pipeline", "network", "gradient", "constraint", "zero-point", "model", "algorithm", "flow", "流程", "方法", "框架", "模型", "网络", "梯度", "约束", "算法"},
        "results": {"result", "results", "experiment", "performance", "metric", "ablation", "accuracy", "mse", "rmse", "mae", "comparison", "结果", "实验", "指标", "消融", "性能", "对比"},
        "setup": {"setup", "dataset", "benchmark", "setting", "implementation", "data", "sample", "数据集", "设置", "样本", "评价", "指标"},
        "table": {"table", "tabular", "statistics", "表格", "表", "统计"},
    }

    def categories(text: str) -> set[str]:
        lowered = text.lower()
        return {name for name, tokens in groups.items() if any(token in lowered for token in tokens)}

    def tokens(text: str) -> set[str]:
        return set(re.findall(r"[\u4e00-\u9fff]{2,}|[a-zA-Z][a-zA-Z0-9-]{2,}", text.lower()))

    def desired_categories(slide: SlideContent) -> set[str]:
        key = slide.slide_key
        if key == "method" or key.startswith("method_detail_"):
            return {"method"}
        if key == "experiment_setup" or key.startswith("experiment_detail_"):
            return {"setup"}
        if key == "results" or key.startswith("results_detail_"):
            return {"results"}
        return set()

    def figure_kind(figure: Any) -> str:
        caption = str(getattr(figure, "caption", "")).lower()
        match = re.search(r"(?:类型|type)\s*[:：]\s*([a-zA-Z_-]+|[\u4e00-\u9fff]+)", caption)
        if not match:
            return ""
        raw = match.group(1).strip().lower()
        mapping = {
            "method": "method",
            "setup": "setup",
            "results": "results",
            "result": "results",
            "table": "table",
            "方法图": "method",
            "实验图": "setup",
            "数据图": "setup",
            "结果图": "results",
            "表格截图": "table",
        }
        return mapping.get(raw, raw)

    def is_kind_compatible(kind: str, wanted: set[str]) -> bool:
        if not kind or kind == "other":
            return True
        if kind == "table":
            return bool(wanted & {"setup", "results"})
        return kind in wanted

    candidates: List[tuple[int, int, int, str]] = []
    for slide_idx, slide in enumerate(slides):
        if slide.slide_key == "title" or slide.slide_key.startswith("conclusion"):
            continue
        wanted = desired_categories(slide)
        slide_text = f"{slide.slide_key} {slide.title} {' '.join(slide.bullets[:4])}"
        slide_categories = categories(slide_text) | wanted
        slide_tokens = tokens(slide_text)
        for figure_idx, figure in enumerate(figures):
            caption = f"{getattr(figure, 'caption', '')} {getattr(figure, 'figure_id', '')}"
            kind = figure_kind(figure)
            is_user_supplied = str(getattr(figure, "figure_id", "")).startswith("User supplied figure")
            if is_user_supplied and not is_kind_compatible(kind, wanted):
                continue
            figure_categories = categories(caption) | ({kind} if kind else set())
            if not figure_categories and not tokens(caption):
                continue
            if wanted == {"setup"} and "results" in figure_categories:
                continue
            overlap = len(slide_tokens & tokens(caption))
            category_score = len(wanted & figure_categories) * 18 if wanted else len(slide_categories & figure_categories) * 8
            kind_bonus = 10 if kind and wanted and kind in wanted else 0
            user_bonus = 4 if is_user_supplied else 0
            table_bonus = 10 if kind == "table" and ("setup" in wanted or "results" in wanted) else 0
            score = category_score + kind_bonus + table_bonus + user_bonus + min(overlap * 2, 12)
            if wanted == {"results"} and "results" in figure_categories:
                score += 4
            if score >= 10:
                reason = f"类型/说明与页面匹配，得分 {score}"
                candidates.append((score, slide_idx, figure_idx, reason))

    for score, slide_idx, figure_idx, _reason in sorted(candidates, reverse=True):
        if slide_idx in bindings or figure_idx in used_figures:
            continue
        bindings[slide_idx] = figure_idx
        used_figures.add(figure_idx)
    return bindings


def _bind_tables_to_slides(slides: List[SlideContent], tables: List[Any]) -> Dict[int, int]:
    if not slides or not tables:
        return {}

    candidates: List[int] = []
    for idx, slide in enumerate(slides):
        if slide.slide_key in {"results", "experiment_setup"} or slide.slide_key.startswith("results_detail_"):
            candidates.append(idx)

    bindings: Dict[int, int] = {}
    for table_idx, slide_idx in enumerate(candidates[: len(tables)]):
        bindings[slide_idx] = table_idx
    return bindings


def _apply_figure_layouts(slides: List[SlideContent], layout_names: List[str], figure_bindings: Dict[int, int]) -> List[str]:
    updated = list(layout_names)
    for slide_idx in figure_bindings:
        if slide_idx >= len(slides):
            continue
        slide = slides[slide_idx]
        text = f"{slide.slide_key} {slide.title} {' '.join(slide.bullets[:3])}".lower()
        if any(token in text for token in ("result", "metric", "实验", "结果", "ablation", "accuracy")):
            updated[slide_idx] = "figure-results"
        elif any(token in text for token in ("method", "framework", "architecture", "pipeline", "方法", "算法")):
            updated[slide_idx] = "figure-method"
        elif any(token in text for token in ("compare", "vs", "对比", "comparison")):
            updated[slide_idx] = "figure-compare"
        else:
            updated[slide_idx] = "figure-hero"
    return updated


def _apply_table_layouts(layout_names: List[str], table_bindings: Dict[int, int]) -> List[str]:
    updated = list(layout_names)
    for slide_idx in table_bindings:
        if slide_idx < len(updated):
            updated[slide_idx] = "table"
    return updated


class TaskPipeline:
    def __init__(self, store: TaskStore, on_update: Callable[[str, Dict[str, Any]], None]) -> None:
        self.store = store
        self.on_update = on_update

    def _log(self, task_id: str, message: str, level: str = "info") -> None:
        self.store.append_log(task_id, message, level=level)

    def _patch(self, task_id: str, **updates: Any) -> None:
        self.on_update(task_id, updates)

    def run_until_pause_or_done(self, task_id: str) -> None:
        while True:
            task = self.store.get_task(task_id)
            if not task:
                return
            status = task.get("status")
            if status in {"succeeded", "failed", "waiting_confirmation"}:
                return

            try:
                llm_provider = task.get("config", {}).get("llm_provider") or resolve_llm_provider()
                llm: Optional[BaseLLM] = create_llm(llm_provider)
                stage = task.get("current_stage", "parse")
                if stage == "parse":
                    self._stage_parse(task_id, task)
                elif stage == "classify":
                    self._stage_classify(task_id, task)
                elif stage == "outline_confirm":
                    self._stage_outline_confirm(task_id, task)
                    return
                elif stage == "generate":
                    self._stage_generate(task_id, task, llm)
                elif stage == "slides_confirm":
                    self._stage_slides_confirm(task_id, task)
                    return
                elif stage == "layout":
                    self._stage_layout(task_id, task)
                elif stage == "layout_confirm":
                    self._stage_layout_confirm(task_id, task)
                    return
                elif stage == "build":
                    self._stage_build(task_id, task)
                    return
                else:
                    return
            except Exception as exc:
                self._log(task_id, f"任务失败: {exc}", level="error")
                self._patch(
                    task_id,
                    status="failed",
                    message=f"任务失败: {exc}",
                    error=str(exc),
                )
                return

    def continue_after_confirm(
        self,
        task_id: str,
        action: str,
        feedback: str,
        layout_overrides: Optional[Dict[str, str]] = None,
        outline_overrides: Optional[Dict[str, str]] = None,
        title_override: str = "",
    ) -> None:
        task = self.store.get_task(task_id)
        if not task:
            return
        stage = task.get("current_stage", "")
        timeline = list(task.get("timeline") or [])
        layout_overrides = layout_overrides or {}
        outline_overrides = outline_overrides or {}
        title_override = title_override.strip()
        if stage == "outline_confirm" and title_override:
            classified_data = dict(task.get("classified") or {})
            parsed_data = dict(task.get("parsed") or {})
            classified_data["title"] = title_override
            parsed_data["title"] = title_override
            timeline = [
                {
                    **entry,
                    "body": f"标题: {title_override[:80]}",
                }
                if entry.get("stage_id") == "classify"
                else entry
                for entry in timeline
            ]
            self._patch(task_id, classified=classified_data, parsed=parsed_data, timeline=timeline)
            task = self.store.get_task(task_id) or task
            self._log(task_id, "User corrected paper title")
        if stage == "outline_confirm" and outline_overrides:
            plan_data = dict(task.get("plan") or {})
            slides_data = list(plan_data.get("slides") or [])
            for item_id, title in outline_overrides.items():
                title = str(title).strip()
                if not title or not item_id.startswith("outline-"):
                    continue
                try:
                    idx = int(item_id.split("-", 1)[1])
                except ValueError:
                    continue
                if 0 <= idx < len(slides_data):
                    slide_data = dict(slides_data[idx])
                    slide_data["title"] = title
                    slides_data[idx] = slide_data
            plan_data["slides"] = slides_data
            self._patch(task_id, plan=plan_data)
            task = self.store.get_task(task_id) or task
            self._log(task_id, "User edited outline titles")
        if stage == "layout_confirm" and layout_overrides:
            current_layouts = list(task.get("layout_names") or [])
            slides = _deserialize_slides(task.get("slides") or [])
            slide_index = {f"layout-{idx}": idx for idx, _ in enumerate(slides)}
            for item_id, layout_name in layout_overrides.items():
                idx = slide_index.get(item_id)
                if idx is None or layout_name not in ALL_LAYOUTS:
                    continue
                while idx >= len(current_layouts):
                    current_layouts.append("bullets")
                current_layouts[idx] = layout_name
            self._patch(task_id, layout_names=current_layouts)
        if action == "revise" and feedback.strip():
            config = dict(task.get("config") or {})
            config["instruction"] = (config.get("instruction", "") + "\n" + feedback.strip()).strip()
            snapshot = {
                "stage": stage,
                "feedback": feedback.strip(),
                "classified": task.get("classified"),
                "slides": task.get("slides"),
                "plan": task.get("plan"),
            }
            self.store.add_version(task_id, label="revise", summary=f"重做 {stage}", snapshot=snapshot)
            self._log(task_id, f"User requested revise at {stage}")
            self._patch(task_id, config=config, pending_confirmation=None)
            if stage == "outline_confirm":
                self._patch(task_id, current_stage="classify", status="running", message="按反馈重新分类…")
            elif stage == "slides_confirm":
                self._patch(task_id, current_stage="generate", status="running", message="按反馈重新生成内容…")
            elif stage == "layout_confirm":
                self._patch(task_id, current_stage="layout", status="running", message="按反馈重新生成布局方案…")
        else:
            timeline.append(_timeline_entry(stage, "用户确认", "已确认并继续", "done"))
            self._patch(task_id, pending_confirmation=None, timeline=timeline)
            if stage == "outline_confirm":
                self._patch(
                    task_id,
                    current_stage="generate",
                    status="running",
                    message="正在生成幻灯片内容…",
                    completed_steps=4,
                )
            elif stage == "slides_confirm":
                self._patch(
                    task_id,
                    current_stage="layout",
                    status="running",
                    message="正在匹配页面布局…",
                    completed_steps=5,
                )
            elif stage == "layout_confirm":
                self._patch(
                    task_id,
                    current_stage="build",
                    status="running",
                    message="正在构建输出文件…",
                    completed_steps=7,
                )
        self.run_until_pause_or_done(task_id)

    def _stage_parse(self, task_id: str, task: Dict[str, Any]) -> None:
        self._patch(task_id, status="running", message="正在解析论文文本…", completed_steps=1)
        config = task["config"]
        input_mode = config["input_mode"]
        source_path = config["source_path"]
        source_kind = config.get("source_kind")
        if not source_kind:
            source_kind = "pdf" if Path(source_path).suffix.lower() == ".pdf" else "text"
        if input_mode == "upload" and source_kind == "pdf":
            parsed = parse_pdf(source_path, task_id=task_id)
        else:
            parsed = parse_text_file(source_path)
        for idx, figure_info in enumerate(config.get("supplemental_figure_paths") or [], start=1):
            if isinstance(figure_info, dict):
                image_path = str(figure_info.get("path") or "")
                kind = str(figure_info.get("kind") or "other")
                description = str(figure_info.get("description") or "").strip()
                filename = str(figure_info.get("filename") or f"图片 {idx}")
            else:
                image_path = str(figure_info)
                kind = "other"
                description = ""
                filename = f"图片 {idx}"
            caption_parts = [f"用户上传图片 {idx}", f"类型: {kind}"]
            if description:
                caption_parts.append(f"说明: {description}")
            else:
                caption_parts.append(f"文件: {filename}")
            ref_type, ref_no = _extract_figure_reference(f"{description} {filename}")
            reference_context = _lookup_reference_context(parsed.raw_text, ref_type, ref_no)
            if reference_context:
                caption_parts.append(f"原文描述: {reference_context}")
            parsed.figures.append(
                ParsedFigure(
                    page_index=0,
                    figure_id=f"User supplied figure {idx}",
                    caption="；".join(caption_parts),
                    image_path=image_path,
                )
            )
        timeline = list(task.get("timeline") or [])
        timeline.append(
            _timeline_entry(
                "parse",
                "解析完成",
                f"识别语言: {parsed.language}；用户图片 {len(parsed.figures)}；文本表格 {len(parsed.tables)}",
                "done",
            )
        )
        self._log(task_id, f"Parsed {parsed.source_name}, language={parsed.language}")
        self._patch(
            task_id,
            parsed=_serialize_parsed(parsed),
            current_stage="classify",
            timeline=timeline,
            message="正在抽取结构化章节…",
            completed_steps=2,
        )

    def _stage_classify(self, task_id: str, task: Dict[str, Any]) -> None:
        parsed = _deserialize_parsed(task["parsed"])
        classified = classify_paper(parsed)
        plan = _adapt_plan_to_user_figures(_plan_from_task(task, classified), task["config"], classified.language)
        timeline = list(task.get("timeline") or [])
        timeline.append(
            _timeline_entry(
                "classify",
                "章节分类完成",
                f"标题: {classified.title[:80]}",
                "done",
            )
        )
        self._log(task_id, "Classification complete")
        self._patch(
            task_id,
            classified=_serialize_classified(classified),
            plan={
                "slides": [
                    {
                        "slide_key": s.slide_key,
                        "title": s.title,
                        "goal": s.goal,
                        "max_bullets": s.max_bullets,
                    }
                    for s in plan.slides
                ]
            },
            current_stage="outline_confirm",
            timeline=timeline,
            message="等待确认大纲…",
            completed_steps=3,
        )

    def _stage_outline_confirm(self, task_id: str, task: Dict[str, Any]) -> None:
        classified = _deserialize_classified(task["classified"])
        parsed = _deserialize_parsed(task["parsed"])
        plan_data = task.get("plan") or {}
        title_issue = _title_quality_issue(classified.title, parsed.source_name, classified.language)
        title_body = f"当前识别标题：{classified.title}"
        if title_issue:
            title_body += f"\n系统提示：{title_issue}，建议手动核对标题。"
        items: List[Dict[str, str]] = [
            {"id": "paper-title", "title": "论文标题", "body": title_body}
        ]
        for idx, slide in enumerate(plan_data.get("slides", [])):
            items.append(
                {
                    "id": f"outline-{idx}",
                    "title": f"第 {idx + 1} 页",
                    "body": str(slide.get("title") or ""),
                }
            )
        outline = "\n".join(
            f"{idx + 1}. {slide['title']}" for idx, slide in enumerate(plan_data.get("slides", []))
        )
        self._log(task_id, "Waiting for outline confirmation")
        self._patch(
            task_id,
            status="waiting_confirmation",
            current_stage="outline_confirm",
            message="请确认论文大纲与章节划分",
            pending_confirmation={
                "stage_id": "outline_confirm",
                "title": "确认论文大纲",
                "body": outline or classified.title,
                "items": items,
            },
        )

    def _stage_generate(self, task_id: str, task: Dict[str, Any], llm: Optional[BaseLLM]) -> None:
        classified = _deserialize_classified(task["classified"])
        parsed = _deserialize_parsed(task["parsed"])
        plan = _plan_from_task(task, classified)
        worker_count = min(4, len(plan.slides)) if llm is not None and len(plan.slides) > 1 else 1
        self._log(task_id, f"Generating slide content with {worker_count} worker(s)")
        llm_warnings: List[str] = []

        def record_llm_warning(message: str) -> None:
            llm_warnings.append(message)
            self._log(task_id, message)

        try:
            slides = generate_slide_contents(classified, plan, llm=llm, on_warning=record_llm_warning)
        except Exception as exc:
            self._log(task_id, f"LLM generation failed, retrying with local fallback: {exc}")
            llm_warnings.append(str(exc))
            slides = generate_slide_contents(classified, plan, llm=None)
        self._log(task_id, "Reorganized generated deck")
        _apply_instruction(slides, task["config"].get("instruction", ""), language=classified.language)
        timeline = list(task.get("timeline") or [])
        if llm_warnings:
            timeline.append(
                _timeline_entry(
                    "generate",
                    "LLM 生成部分回退",
                    f"{len(llm_warnings)} 页因模型请求失败改用本地规则生成",
                    "warning",
                )
            )
        timeline.append(
            _timeline_entry("generate", "内容生成完成", f"共 {len(slides)} 页幻灯片", "done")
        )
        self._log(task_id, f"Generated {len(slides)} slides")
        self._patch(
            task_id,
            slides=_serialize_slides(slides),
            current_stage="slides_confirm",
            timeline=timeline,
            message="等待确认幻灯片内容…",
            completed_steps=4,
            parsed=_serialize_parsed(parsed),
        )

    def _stage_slides_confirm(self, task_id: str, task: Dict[str, Any]) -> None:
        slides = _deserialize_slides(task.get("slides") or [])
        preview = "\n".join(f"- {s.title}: {'; '.join(s.bullets[:2])}" for s in slides)
        items = [
            {
                "id": s.slide_key,
                "title": s.title,
                "body": "\n".join(
                    [
                        "每页核心观点：",
                        *[f"- {point}" for point in (s.core_points or s.bullets)],
                        "",
                        "页面文字：",
                        *[f"- {bullet}" for bullet in s.bullets],
                        "",
                        "备注草稿：",
                        s.draft_notes or "本页暂无备注草稿。",
                        "",
                        "讲解备注：",
                        s.notes or "本页暂无备注。",
                    ]
                ),
            }
            for s in slides
        ]
        self._log(task_id, "Waiting for slides confirmation")
        self._patch(
            task_id,
            status="waiting_confirmation",
            current_stage="slides_confirm",
            message="请确认幻灯片要点",
            pending_confirmation={
                "stage_id": "slides_confirm",
                "title": "确认幻灯片内容",
                "body": preview,
                "items": items,
            },
        )

    def _stage_layout(self, task_id: str, task: Dict[str, Any]) -> None:
        slides = _deserialize_slides(task.get("slides") or [])
        parsed = _deserialize_parsed(task["parsed"])
        figure_bindings = _bind_figures_to_slides(slides, parsed.figures)
        table_bindings = _bind_tables_to_slides(slides, parsed.tables)
        layout_names = _apply_table_layouts(
            _apply_figure_layouts(slides, _propose_layout_names(slides), figure_bindings),
            table_bindings,
        )
        timeline = list(task.get("timeline") or [])
        timeline.append(
            _timeline_entry("layout", "布局匹配完成", f"共生成 {len(layout_names)} 页布局方案", "done")
        )
        self._log(task_id, f"Prepared {len(layout_names)} layout suggestions")
        self._patch(
            task_id,
            layout_names=layout_names,
            figure_bindings={str(k): v for k, v in figure_bindings.items()},
            table_bindings={str(k): v for k, v in table_bindings.items()},
            current_stage="layout_confirm",
            timeline=timeline,
            message="等待确认页面布局…",
            completed_steps=6,
        )

    def _stage_layout_confirm(self, task_id: str, task: Dict[str, Any]) -> None:
        slides = _deserialize_slides(task.get("slides") or [])
        parsed = _deserialize_parsed(task["parsed"])
        layout_names = list(task.get("layout_names") or [])
        figure_bindings = {int(k): v for k, v in dict(task.get("figure_bindings") or {}).items()}
        table_bindings = {int(k): v for k, v in dict(task.get("table_bindings") or {}).items()}
        items = []
        for idx, slide in enumerate(slides):
            layout_name = layout_names[idx] if idx < len(layout_names) else "bullets"
            figure_note = ""
            if idx in figure_bindings and figure_bindings[idx] < len(parsed.figures):
                figure = parsed.figures[figure_bindings[idx]]
                figure_note = f" · 配图：{_figure_caption(figure)}"
            table_note = ""
            if idx in table_bindings and table_bindings[idx] < len(parsed.tables):
                table = parsed.tables[table_bindings[idx]]
                table_note = f" · 配表：{table.table_id}"
            item = {
                "id": f"layout-{idx}",
                "title": slide.title,
                "body": f"{layout_name} · {'; '.join(slide.bullets[:2])}{figure_note}{table_note}",
            }
            if idx in figure_bindings and figure_bindings[idx] < len(parsed.figures):
                figure_idx = figure_bindings[idx]
                figure = parsed.figures[figure_idx]
                item["figure_url"] = f"/api/tasks/{task_id}/figures/{figure_idx}/preview"
                item["figure_caption"] = _figure_caption(figure)
            items.append(item)
        preview = "\n".join(
            f"- {slide.title}：{_layout_label(layout_names[idx] if idx < len(layout_names) else 'bullets')}"
            for idx, slide in enumerate(slides)
        )
        self._log(task_id, "Waiting for layout confirmation")
        self._patch(
            task_id,
            status="waiting_confirmation",
            current_stage="layout_confirm",
            message="请确认页面布局方案",
            pending_confirmation={
                "stage_id": "layout_confirm",
                "title": "确认页面布局",
                "body": preview,
                "items": items,
            },
        )

    def _stage_build(self, task_id: str, task: Dict[str, Any]) -> None:
        config = task["config"]
        classified = _deserialize_classified(task["classified"])
        parsed = _deserialize_parsed(task["parsed"])
        slides = _deserialize_slides(task.get("slides") or [])
        plan = _plan_from_task(task, classified)
        layout_names = list(task.get("layout_names") or [])
        figure_bindings = {int(k): v for k, v in dict(task.get("figure_bindings") or {}).items()}
        table_bindings = {int(k): v for k, v in dict(task.get("table_bindings") or {}).items()}
        accent = style_accent(config.get("style_id", "blue"))
        template_id = config.get("template_id", "tech-sharing")

        pptx_path = Path(OUTPUTS_DIR) / f"{task_id}.pptx"
        build_ppt(
            slides=slides,
            output_path=str(pptx_path),
            template_path=config.get("template_path"),
            style_key=config.get("style_id", "blue"),
            figures=parsed.figures,
            tables=parsed.tables,
            layout_names=layout_names,
            figure_bindings=figure_bindings,
        )
        html_path = build_html_deck(
            task_id=task_id,
            slides=slides,
            template_id=template_id,
            accent=accent,
            figures=parsed.figures,
            tables=parsed.tables,
            layout_names=layout_names,
            figure_bindings=figure_bindings,
            table_bindings=table_bindings,
            language=classified.language,
        )

        result = {
            "title": classified.title,
            "abstract": classified.abstract,
            "slides": [
                {"id": f"{s.slide_key}-{idx}", "title": s.title, "accent": accent}
                for idx, s in enumerate(slides)
            ],
            "slide_count": len(slides),
            "word_count": len(parsed.raw_text.split()),
            "duration_min": max(8, len(slides) * 2),
            "result_cards": _build_result_cards(classified, plan, slides),
            "download_url": f"/api/tasks/{task_id}/download",
            "html_preview_url": f"/api/tasks/{task_id}/html/index.html",
            "html_download_url": f"/api/tasks/{task_id}/html/download",
            "layout_names": layout_names,
            "figure_bindings": figure_bindings,
            "applied_config": {
                "input_mode": config["input_mode"],
                "page_count": len(slides),
                "template_id": template_id,
                "style_id": config.get("style_id", "blue"),
                "instruction": config.get("instruction", ""),
                "llm_provider": config.get("llm_provider", "local"),
            },
        }

        timeline = list(task.get("timeline") or [])
        timeline.append(_timeline_entry("build", "构建完成", "PPTX 与 HTML 已生成", "done"))
        version = self.store.add_version(
            task_id,
            label="final",
            summary="生成完成",
            snapshot={"result": result, "slide_count": len(slides)},
        )
        self._log(task_id, f"Build complete, version v{version['version_no']}")
        self._patch(
            task_id,
            status="succeeded",
            message="生成完成，可预览或下载",
            completed_steps=TOTAL_STEPS,
            total_steps=TOTAL_STEPS,
            current_stage="done",
            output_path=str(pptx_path),
            html_path=html_path,
            result=result,
            timeline=timeline,
            pending_confirmation=None,
        )


def _serialize_parsed(parsed: ParsedPaper) -> Dict[str, Any]:
    return {
        "source_name": parsed.source_name,
        "raw_text": parsed.raw_text,
        "title": parsed.title,
        "abstract": parsed.abstract,
        "language": parsed.language,
        "sections": parsed.sections,
        "figures": [
            {
                "page_index": f.page_index,
                "figure_id": f.figure_id,
                "caption": f.caption,
                "image_path": f.image_path,
            }
            for f in parsed.figures
        ],
        "tables": [
            {
                "page_index": t.page_index,
                "table_id": t.table_id,
                "markdown": t.markdown,
                "row_count": t.row_count,
                "col_count": t.col_count,
                "image_path": t.image_path,
            }
            for t in parsed.tables
        ],
        "ocr_applied": parsed.ocr_applied,
        "dual_column_reflowed": parsed.dual_column_reflowed,
    }


def _deserialize_parsed(data: Dict[str, Any]) -> ParsedPaper:
    from models import ParsedFigure, ParsedTable

    return ParsedPaper(
        source_name=data.get("source_name", ""),
        raw_text=data.get("raw_text", ""),
        title=data.get("title", ""),
        abstract=data.get("abstract", ""),
        language=data.get("language", "en"),
        sections=data.get("sections") or {},
        figures=[ParsedFigure(**f) for f in data.get("figures") or []],
        tables=[ParsedTable(**t) for t in data.get("tables") or []],
        ocr_applied=bool(data.get("ocr_applied")),
        dual_column_reflowed=bool(data.get("dual_column_reflowed")),
    )


def _serialize_classified(classified: ClassifiedPaper) -> Dict[str, Any]:
    return {
        "title": classified.title,
        "abstract": classified.abstract,
        "background": classified.background,
        "method": classified.method,
        "experiment_setup": classified.experiment_setup,
        "results": classified.results,
        "conclusion": classified.conclusion,
        "language": classified.language,
        "extra_sections": classified.extra_sections,
    }


def _deserialize_classified(data: Dict[str, Any]) -> ClassifiedPaper:
    return ClassifiedPaper(**data)


def _serialize_slides(slides: List[SlideContent]) -> List[Dict[str, Any]]:
    return [
        {
            "slide_key": s.slide_key,
            "title": s.title,
            "bullets": s.bullets,
            "notes": s.notes,
            "core_points": s.core_points,
            "draft_notes": s.draft_notes,
        }
        for s in slides
    ]


def _deserialize_slides(data: List[Dict[str, Any]]) -> List[SlideContent]:
    return [SlideContent(**item) for item in data]
