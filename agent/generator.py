from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, List, Optional

from llm import BaseLLM, generate_bullets_with_llm, generate_notes_with_llm, generate_script_from_slide_with_llm, llm_generate
from models import ClassifiedPaper, PresentationPlan, SlideContent, SlidePlan
from prompts import SLIDE_NOTES_PROMPT


def _smart_truncate(text: str, limit: int, language: str = "en") -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if len(cleaned) <= limit:
        return cleaned

    if language == "zh":
        cut = cleaned[:limit].rstrip(" ，,；;：:")
        return cut.rstrip("。！？!?") + "。"

    window = cleaned[:limit].rstrip()
    punctuation_matches = list(re.finditer(r"[\.;:!?](?=\s|$)", window))
    if punctuation_matches and punctuation_matches[-1].end() >= max(60, limit - 55):
        cut = window[: punctuation_matches[-1].end()]
    else:
        space_idx = window.rfind(" ")
        cut = window[:space_idx] if space_idx >= max(40, limit - 45) else window
        cut = re.sub(r"\s+(?:and|or|with|for|to|in|of|by|from|as|that|which|the|a|an)$", "", cut, flags=re.IGNORECASE)
        cut = cut.rstrip(" ,;:-")

    # Avoid outputs like "regr..." caused by character-level truncation.
    cut = re.sub(r"\b[A-Za-z]{1,5}\.\.\.$", "", cut).rstrip(" ,;:-")
    cut = re.sub(
        r"\s+(?:in|for|with|of|to|by|from|across|under|through)\s+[^,.;:!?]{1,45}$",
        "",
        cut,
        flags=re.IGNORECASE,
    ).rstrip(" ,;:-")
    return cut.rstrip(".!?") + "."


def split_into_bullets(text: str, max_bullets: int, language: str = "en") -> List[str]:
    if not text.strip():
        return ["已解析文本中未找到该页可用内容。"] if language == "zh" else ["Content not available in the parsed paper text."]

    if language == "zh":
        return _fallback_zh_bullets(text, max_bullets)

    segments = re.split(r"(?<=[\.\!\?])\s+", text.replace("\n", " "))
    bullets: List[str] = []

    for segment in segments:
        cleaned = re.sub(r"\s+", " ", segment).strip(" -")
        if len(cleaned) < 18:
            continue
        cleaned = cleaned.rstrip(".")
        bullets.append(cleaned)
        if len(bullets) >= max_bullets:
            break

    if not bullets:
        compact = re.sub(r"\s+", " ", text).strip()
        bullets = [compact]

    return bullets[:max_bullets]


def _fallback_zh_bullets(text: str, max_bullets: int) -> List[str]:
    if re.search(r"[\u4e00-\u9fff]", text):
        pieces = re.split(r"(?<=[。！？!?])\s*", text.replace("\n", ""))
        cleaned = [re.sub(r"\s+", "", piece).strip(" -") for piece in pieces if len(piece.strip()) >= 12]
        if cleaned:
            return cleaned[:max_bullets]

    templates = [
        "本页概括论文在该部分的核心问题与研究动机。",
        "重点说明该部分涉及的方法设计、实验设置或关键发现。",
        "建议结合原文进一步核对具体数值、公式和实验结论。",
        "该部分内容已保留为中文概述，避免直接混入外文长句。",
    ]
    return templates[:max_bullets]


def _fallback_zh_bullets_for_slide(slide: SlidePlan, text: str) -> List[str]:
    title = slide.title
    source_hint = _compact_source_hint(text)
    if "概览" in title or slide.slide_key == "title":
        bullets = [
            f"论文围绕{source_hint}展开研究" if source_hint else "论文围绕核心研究问题展开系统分析",
            "重点介绍研究动机、核心方法与实验结论",
            "汇报将按背景、方法、实验和结论逐步展开",
        ]
    elif "核心研究问题" in title:
        bullets = [
            "将论文目标拆解为若干可验证的研究问题",
            "重点关注方法如何回应核心问题与假设",
            "后续实验需要证明结果并非偶然相关",
        ]
    elif "创新" in title:
        bullets = [
            "从问题、方法、数据、机制和应用层面评价创新性",
            "判断贡献属于实质突破还是增量改进",
            "结合对比实验说明创新是否得到充分验证",
        ]
    elif "不足" in title or "潜在问题" in title:
        bullets = [
            "从审稿人角度检查假设、数据和验证是否充分",
            "关注结论是否存在过度外推或机制解释不足",
            "识别缺失对照、复现风险和更强基线需求",
        ]
    elif "追问" in title:
        bullets = [
            "围绕方法选择、实验设计和结论边界提出追问",
            "重点准备老师可能质疑的验证充分性问题",
            "回答时需要回到论文证据和潜在补充实验",
        ]
    elif "最终评价" in title or "汇报策略" in title:
        bullets = [
            "综合判断论文贡献、局限和领域位置",
            "明确汇报中必须展开和可以略讲的内容",
            "提前准备老师可能追问的关键证据",
        ]
    elif "结果" in title or "消融" in title or "鲁棒" in title:
        bullets = [
            "结果部分围绕主要性能、对比实验和消融分析展开",
            "实验结论用于说明本文方法相对基线的优势",
            "进一步分析帮助解释关键模块带来的改进",
        ]
    elif "背景" in title or "问题" in title:
        bullets = [
            f"论文聚焦于{source_hint}这一研究问题" if source_hint else "论文首先交代研究问题与应用价值",
            "现有方法仍存在表达能力或稳定性不足",
            "本页为后续方法设计引出核心挑战",
        ]
    elif "方法" in title or "流程" in title:
        bullets = [
            f"方法部分围绕{source_hint}展开设计" if source_hint else "本文方法围绕核心任务构建整体框架",
            "关键设计用于缓解原有方法的主要不足",
            "整体流程强调可解释性、稳定性与可复现性",
        ]
    elif "实验" in title or "数据" in title or "指标" in title or "实现" in title:
        bullets = [
            "实验部分说明数据集、对比基线与评价指标",
            "设置设计用于验证方法在不同场景下的有效性",
            "该页重点交代后续结果比较的实验依据",
        ]
    elif "结论" in title or "启示" in title or "未来" in title or "局限" in title:
        bullets = [
            "论文总结了方法设计与实验验证得到的主要结论",
            "研究贡献体现在问题建模、方法改进和实验效果上",
            "后续工作可围绕适用范围和实际部署继续扩展",
        ]
    else:
        bullets = _fallback_zh_bullets(text, slide.max_bullets)
    return bullets[: slide.max_bullets]


def _compact_source_hint(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return ""
    if re.search(r"[\u4e00-\u9fff]", cleaned):
        cleaned = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9（）()，,。 ]", "", cleaned)
        return cleaned[:18].strip(" ，,。")
    terms = re.findall(r"\b[A-Za-z]+(?: regression| learning| model| method| constraint| expression)\b|\b[A-Z][A-Za-z0-9-]{2,}\b", cleaned, flags=re.IGNORECASE)
    if terms:
        return terms[0][:36]
    words = re.findall(r"[A-Za-z]{4,}", cleaned)
    return " ".join(words[:3])[:36]


def _is_english_heavy(text: str) -> bool:
    latin_count = sum(1 for ch in text if ch.isascii() and ch.isalpha())
    cjk_count = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    if cjk_count:
        return latin_count > cjk_count * 2 and latin_count > 24
    words = re.findall(r"[A-Za-z]{3,}", text)
    return len(words) >= 5


def _filter_bullets_by_language(bullets: List[str], language: str) -> List[str]:
    if language != "zh":
        return bullets
    return [bullet for bullet in bullets if not _is_english_heavy(bullet)]


def _filter_notes_by_language(notes: str, language: str) -> str:
    if language == "zh" and _is_english_heavy(notes):
        return ""
    return notes


def _is_presentation_ready(line: str, language: str) -> bool:
    if not line or _filter_notes_by_language(line, language) == "":
        return False
    lowered = line.lower()
    generic_markers = [
        "概括该部分",
        "概括本页对应内容",
        "突出与论文主题直接相关",
        "用适合汇报的方式串联",
        "说明论文提出的方法设计和关键机制",
        "总结实验设置、结果表现和主要结论",
        "summarize the paper section",
        "content not available",
    ]
    if any(marker in lowered for marker in generic_markers):
        return False
    if language == "zh":
        cjk_count = sum(1 for ch in line if "\u4e00" <= ch <= "\u9fff")
        return cjk_count >= 8
    return len(re.findall(r"[A-Za-z]{3,}", line)) >= 4


def _filter_bullets_for_quality(bullets: List[str], language: str) -> List[str]:
    return [bullet for bullet in bullets if _is_presentation_ready(bullet, language)]


def build_notes(text: str, llm: Optional[BaseLLM] = None, language: str = "en") -> str:
    prompt = (
        SLIDE_NOTES_PROMPT + "\n请用中文输出，除论文标题、模型名、指标名和专有名词外不要使用英文。"
        if language == "zh"
        else SLIDE_NOTES_PROMPT + "\nWrite in English. Do not use Chinese except for source-specific names."
    )
    generated = llm_generate(prompt=prompt, context=text, llm=llm, max_tokens=120)
    generated = _filter_notes_by_language(generated, language)
    if generated:
        return generated
    if language == "zh":
        return "本页用于讲解论文对应部分的核心内容，请结合页面要点进行说明。"
    condensed = re.sub(r"\s+", " ", text).strip()
    return condensed


def _ensure_sentence(text: str, language: str) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip(" -;；")
    if not cleaned:
        return ""
    if language == "zh":
        return cleaned if cleaned.endswith(("。", "！", "？")) else f"{cleaned}。"
    return cleaned if cleaned.endswith((".", "!", "?")) else f"{cleaned}."


def _strip_meta_phrases(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    cleaned = re.sub(r"这一页的讲解草稿围绕“[^”]+”展开，? ?", "", cleaned)
    cleaned = re.sub(r"重点服务于“[^”]+”。?", "", cleaned)
    cleaned = re.sub(r"讲解时可以先交代问题，再说明证据，最后指出其对论文主线的意义。?", "", cleaned)
    cleaned = re.sub(r"The draft speaker notes for this slide focus on [^.]+\. ?", "", cleaned)
    cleaned = re.sub(r"Present this by connecting the problem, evidence, and implication for the paper's main argument\. ?", "", cleaned)
    return cleaned.strip()


def _remove_repeated_sentence(text: str, repeated: str) -> str:
    normalized = text.strip()
    target = repeated.strip().rstrip("。.!?")
    if not target:
        return normalized
    normalized = normalized.replace(repeated.strip(), "")
    normalized = normalized.replace(target, "")
    return re.sub(r"\s+", " ", normalized).strip(" ，,。.;；")


def _speaker_sentence_from_bullet(
    bullet: str,
    core_points: List[str],
    draft_notes: str,
    idx: int,
    language: str,
) -> str:
    clean = bullet.strip().rstrip("。.!?")
    context_pool = " ".join(core_points + [_strip_meta_phrases(draft_notes)])
    context_pool = _remove_repeated_sentence(context_pool, clean)
    support_sentences = _sentences(context_pool)
    support = ""
    if support_sentences:
        support = support_sentences[min(idx, len(support_sentences) - 1)].strip().rstrip("。.!?")
        if clean and (support == clean or clean in support or support in clean):
            support = ""

    if language == "zh":
        connectors = ["首先可以说明", "接着需要强调", "进一步来看", "最后可以补充"]
        connector = connectors[min(idx, len(connectors) - 1)]
        if support:
            return _ensure_sentence(f"{connector}，{clean}；这一点可以结合原文中关于{support}的分析展开", language)
        return _ensure_sentence(f"{connector}，{clean}，这里重点把页面上的结论解释清楚，而不是继续堆叠原文细节", language)

    connectors = ["First, explain that", "Next, emphasize that", "Then, point out that", "Finally, add that"]
    connector = connectors[min(idx, len(connectors) - 1)]
    if support:
        return _ensure_sentence(f"{connector} {clean}; this can be supported by the paper's discussion of {support}", language)
    return _ensure_sentence(f"{connector} {clean}, keeping the explanation tied to the on-slide point rather than adding unrelated details", language)


def _build_notes_from_final_bullets(
    title: str,
    goal: str,
    bullets: List[str],
    source_text: str,
    language: str,
    core_points: Optional[List[str]] = None,
    draft_notes: str = "",
) -> str:
    clean_bullets = [_ensure_sentence(bullet, language) for bullet in bullets if bullet.strip()]
    clean_bullets = [bullet for bullet in clean_bullets if bullet]
    if clean_bullets:
        core_points = core_points or []
        sentences = [
            _speaker_sentence_from_bullet(bullet, core_points, draft_notes, idx, language)
            for idx, bullet in enumerate(clean_bullets)
        ]
        return " ".join(sentence for sentence in sentences if sentence)

    fallback = build_notes(source_text, llm=None, language=language)
    return _ensure_sentence(fallback, language)


def _build_draft_notes_from_core_points(
    title: str,
    goal: str,
    core_points: List[str],
    source_text: str,
    language: str,
) -> str:
    clean_points = [_ensure_sentence(point, language) for point in core_points if point.strip()]
    clean_points = [point for point in clean_points if point]
    if language == "zh":
        lead = f"这一页的讲解草稿围绕“{title}”展开。"
        if goal:
            lead = f"这一页的讲解草稿围绕“{title}”展开，重点服务于“{goal}”。"
        if clean_points:
            return " ".join([lead, " ".join(clean_points), "讲解时可以先交代问题，再说明证据，最后指出其对论文主线的意义。"])
    else:
        lead = f"The draft speaker notes for this slide focus on {title}."
        if goal:
            lead = f"The draft speaker notes for this slide focus on {title}, with the goal of {goal[0].lower() + goal[1:] if goal else goal}."
        if clean_points:
            return " ".join([lead, " ".join(clean_points), "Present this by connecting the problem, evidence, and implication for the paper's main argument."])
    return build_notes(source_text, llm=None, language=language)


def _select_slide_bullets_from_core_points(
    core_points: List[str],
    max_bullets: int,
    language: str,
) -> List[str]:
    selected: List[str] = []
    seen: set[str] = set()
    for point in core_points:
        cleaned = _trim_for_slide(point, language)
        if not cleaned or not _is_presentation_ready(cleaned, language):
            continue
        key = _dedupe_key(cleaned)
        if key in seen:
            continue
        seen.add(key)
        selected.append(cleaned)
        if len(selected) >= max_bullets:
            break
    return selected


def _sentences(text: str) -> List[str]:
    if re.search(r"[\u4e00-\u9fff]", text):
        return [
            seg.strip()
            for seg in re.split(r"(?<=[。！？!?])\s*", text.replace("\n", ""))
            if len(seg.strip()) > 12
        ]
    return [
        seg.strip()
        for seg in re.split(r"(?<=[\.\!\?])\s+", text.replace("\n", " "))
        if len(seg.strip()) > 20
    ]


def _slice_variant(text: str, variant_index: int, window_size: int = 4) -> str:
    sents = _sentences(text)
    if not sents:
        return text
    start = variant_index * window_size
    if start >= len(sents):
        start = max(0, len(sents) - window_size)
    end = min(len(sents), start + window_size)
    return " ".join(sents[start:end]).strip()


def _resolve_source_text(paper: ClassifiedPaper, slide_key: str) -> str:
    direct_keys = {"background", "method", "experiment_setup", "results", "conclusion"}
    if slide_key in direct_keys:
        return getattr(paper, slide_key)

    if slide_key == "research_questions":
        return " ".join([paper.abstract, paper.background, paper.method]).strip()

    if slide_key == "innovation":
        return " ".join([paper.abstract, paper.method, paper.results, paper.conclusion]).strip()

    if slide_key == "limitations":
        return " ".join([paper.experiment_setup, paper.results, paper.conclusion]).strip()

    if slide_key == "discussion_questions":
        return " ".join([paper.background, paper.method, paper.experiment_setup, paper.results, paper.conclusion]).strip()

    if slide_key == "research_inspiration":
        return " ".join([paper.method, paper.experiment_setup, paper.results, paper.conclusion]).strip()

    for prefix, bucket in (
        ("background_detail_", "background"),
        ("method_detail_", "method"),
        ("experiment_setup_detail_", "experiment_setup"),
        ("experiment_detail_", "experiment_setup"),
        ("results_detail_", "results"),
        ("conclusion_detail_", "conclusion"),
    ):
        if slide_key.startswith(prefix):
            idx_str = slide_key.split(prefix, 1)[1]
            idx = int(idx_str) - 1 if idx_str.isdigit() else 0
            return _slice_variant(getattr(paper, bucket), idx)

    if slide_key.startswith("extra_section_"):
        idx_str = slide_key.split("extra_section_", 1)[1]
        idx = int(idx_str) - 1 if idx_str.isdigit() else 0
        extra_values = list(paper.extra_sections.values())
        if extra_values:
            return _slice_variant(extra_values[idx % len(extra_values)], 0)
        merged = " ".join([paper.method, paper.experiment_setup, paper.results, paper.conclusion])
        return _slice_variant(merged, idx)

    merged_default = " ".join([paper.background, paper.method, paper.results, paper.conclusion])
    return _slice_variant(merged_default, 0)


def _generate_single_slide(
    paper: ClassifiedPaper,
    slide: SlidePlan,
    llm: Optional[BaseLLM],
) -> SlideContent:
    language = paper.language

    if slide.slide_key == "title":
        cover_text = paper.abstract or paper.background
        bullets = generate_bullets_with_llm(
            cover_text,
            slide.max_bullets,
            llm,
            language=language,
            slide_title=paper.title,
            slide_goal=slide.goal,
        )
        bullets = _filter_bullets_by_language(bullets, language)
        bullets = _filter_bullets_for_quality(bullets, language)
        if not bullets:
            bullets = _fallback_zh_bullets_for_slide(slide, cover_text) if language == "zh" else split_into_bullets(cover_text, slide.max_bullets, language=language)
        core_points = bullets[: max(slide.max_bullets, 4)]
        ppt_bullets = _select_slide_bullets_from_core_points(core_points, 2, language) or core_points[:2]
        return SlideContent(
            slide_key=slide.slide_key,
            title=paper.title,
            bullets=ppt_bullets,
            notes="",
            core_points=core_points,
            draft_notes=_build_draft_notes_from_core_points(paper.title, slide.goal, core_points, cover_text, language),
        )

    source_text = _resolve_source_text(paper, slide.slide_key)
    bullets = generate_bullets_with_llm(
        source_text,
        slide.max_bullets,
        llm,
        language=language,
        slide_title=slide.title,
        slide_goal=slide.goal,
    )
    bullets = _filter_bullets_by_language(bullets, language)
    bullets = _filter_bullets_for_quality(bullets, language)
    if not bullets:
        bullets = _fallback_zh_bullets_for_slide(slide, source_text) if language == "zh" else split_into_bullets(source_text, slide.max_bullets, language=language)
    core_points = bullets[: max(slide.max_bullets, 4)]
    ppt_bullets = _select_slide_bullets_from_core_points(core_points, slide.max_bullets, language) or core_points[: slide.max_bullets]
    return SlideContent(
        slide_key=slide.slide_key,
        title=slide.title,
        bullets=ppt_bullets,
        notes="",
        core_points=core_points,
        draft_notes=_build_draft_notes_from_core_points(slide.title, slide.goal, core_points, source_text, language),
    )


def _generate_single_slide_with_fallback(
    paper: ClassifiedPaper,
    slide: SlidePlan,
    llm: Optional[BaseLLM],
    on_warning: Optional[Callable[[str], None]] = None,
) -> SlideContent:
    try:
        return _generate_single_slide(paper, slide, llm)
    except Exception as exc:
        if on_warning is not None:
            on_warning(f"LLM 生成第「{slide.title}」页失败，已回退本地规则生成：{exc}")
        return _generate_single_slide(paper, slide, None)


def _parallel_worker_count(slide_count: int, llm: Optional[BaseLLM]) -> int:
    if llm is None or slide_count <= 1:
        return 1
    return min(4, slide_count)


def _normalize_generated_bullet(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    cleaned = re.sub(r"^[-*•\s]+", "", cleaned)
    cleaned = re.sub(r"^\d+[\.\)、\)]\s*", "", cleaned)
    cleaned = re.sub(r"\b[A-Za-z]{1,5}\.\.\.$", "", cleaned).rstrip()
    cleaned = cleaned.strip(" ;；")
    return cleaned


def _dedupe_key(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", text.lower())


def _trim_for_slide(text: str, language: str) -> str:
    return _normalize_generated_bullet(text)


def _trim_notes(notes: str, language: str) -> str:
    return re.sub(r"\s+", " ", notes or "").strip()


def _organize_generated_deck(
    paper: ClassifiedPaper,
    plan: PresentationPlan,
    slides: List[SlideContent],
    llm: Optional[BaseLLM] = None,
) -> List[SlideContent]:
    """Final pass after parallel generation: preserve order, normalize quality."""
    language = paper.language
    organized: List[SlideContent] = []
    seen: set[str] = set()

    final_titles = [paper.title if slide.slide_key == "title" else slide.title for slide in slides]

    for idx, slide in enumerate(slides):
        slide_plan = plan.slides[idx] if idx < len(plan.slides) else None
        max_bullets = 2 if slide.slide_key == "title" else (slide_plan.max_bullets if slide_plan else 4)
        source_text = paper.abstract or paper.background if slide.slide_key == "title" else _resolve_source_text(paper, slide.slide_key)

        cleaned_bullets: List[str] = []
        for bullet in slide.bullets:
            cleaned = _trim_for_slide(bullet, language)
            if not cleaned or not _is_presentation_ready(cleaned, language):
                continue
            key = _dedupe_key(cleaned)
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            cleaned_bullets.append(cleaned)
            if len(cleaned_bullets) >= max_bullets:
                break

        if len(cleaned_bullets) < max_bullets:
            fallback_source = _fallback_zh_bullets_for_slide(slide_plan, source_text) if language == "zh" and slide_plan else split_into_bullets(source_text, max_bullets, language=language)
            for fallback in fallback_source:
                cleaned = _trim_for_slide(fallback, language)
                key = _dedupe_key(cleaned)
                if cleaned and key not in seen:
                    seen.add(key)
                    cleaned_bullets.append(cleaned)
                if len(cleaned_bullets) >= max_bullets:
                    break

        if not cleaned_bullets:
            fallback_source = _fallback_zh_bullets_for_slide(slide_plan, source_text) if language == "zh" and slide_plan else split_into_bullets(source_text, 1, language=language)
            cleaned_bullets = [_trim_for_slide(fallback_source[0], language)] if fallback_source else [
                "本页内容需要结合原文进一步核对。" if language == "zh" else "This page should be verified against the source paper."
            ]

        final_title = paper.title if slide.slide_key == "title" else slide.title
        fallback_notes = _trim_notes(
            _build_notes_from_final_bullets(
                final_title,
                slide_plan.goal if slide_plan else "",
                cleaned_bullets[:max_bullets],
                source_text,
                language,
                core_points=slide.core_points,
                draft_notes=slide.draft_notes or "",
            ),
            language,
        )
        llm_notes = ""
        try:
            llm_notes = _filter_notes_by_language(
                generate_script_from_slide_with_llm(
                    title=final_title,
                    bullets=cleaned_bullets[:max_bullets],
                    core_points=slide.core_points or cleaned_bullets[:max_bullets],
                    draft_notes=slide.draft_notes or "",
                    prev_title=final_titles[idx - 1] if idx > 0 else "",
                    next_title=final_titles[idx + 1] if idx + 1 < len(final_titles) else "",
                    llm=llm,
                    language=language,
                ),
                language,
            )
        except Exception:
            llm_notes = ""

        organized.append(
            SlideContent(
                slide_key=slide.slide_key,
                title=final_title,
                bullets=cleaned_bullets[:max_bullets],
                notes=_trim_notes(llm_notes, language) or fallback_notes,
                core_points=slide.core_points or cleaned_bullets[:max_bullets],
                draft_notes=slide.draft_notes
                or _build_draft_notes_from_core_points(
                    paper.title if slide.slide_key == "title" else slide.title,
                    slide_plan.goal if slide_plan else "",
                    slide.core_points or cleaned_bullets[:max_bullets],
                    source_text,
                    language,
                ),
            )
        )

    return organized


def generate_slide_contents(
    paper: ClassifiedPaper,
    plan: PresentationPlan,
    llm: Optional[BaseLLM] = None,
    on_warning: Optional[Callable[[str], None]] = None,
) -> List[SlideContent]:
    worker_count = _parallel_worker_count(len(plan.slides), llm)
    if worker_count == 1:
        slides = [_generate_single_slide_with_fallback(paper, slide, llm, on_warning) for slide in plan.slides]
        return _organize_generated_deck(paper, plan, slides, llm=llm)

    ordered: list[Optional[SlideContent]] = [None] * len(plan.slides)
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_to_index = {
            executor.submit(_generate_single_slide_with_fallback, paper, slide, llm, on_warning): idx
            for idx, slide in enumerate(plan.slides)
        }
        for future in as_completed(future_to_index):
            idx = future_to_index[future]
            ordered[idx] = future.result()

    slides = [slide for slide in ordered if slide is not None]
    return _organize_generated_deck(paper, plan, slides, llm=llm)
