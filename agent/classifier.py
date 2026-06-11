from __future__ import annotations

import re
from typing import Dict, List, Tuple

from models import ClassifiedPaper, ParsedPaper


HEADING_PATTERNS: List[Tuple[str, List[str]]] = [
    ("background", ["introduction", "background", "motivation", "research problem", "引言", "背景", "绪论", "研究背景"]),
    ("method", ["method", "approach", "framework", "model", "proposed method", "methodology", "方法", "模型", "算法", "框架"]),
    ("experiment_setup", ["experiment", "experimental setup", "implementation details", "dataset", "settings", "实验", "实验设置", "数据集", "实现"]),
    ("results", ["results", "evaluation", "analysis", "ablation", "结果", "实验结果", "评估", "分析"]),
    ("conclusion", ["conclusion", "discussion", "future work", "结论", "讨论", "展望", "未来工作"]),
]


KEYWORD_HINTS: Dict[str, List[str]] = {
    "background": ["problem", "challenge", "motivation", "background", "gap", "task", "问题", "挑战", "背景", "动机"],
    "method": ["method", "approach", "framework", "architecture", "algorithm", "module", "方法", "框架", "模型", "算法"],
    "experiment_setup": ["dataset", "benchmark", "implementation", "training", "setting", "metric", "数据集", "实验", "训练", "指标"],
    "results": ["result", "improvement", "outperform", "accuracy", "table", "figure", "结果", "性能", "准确率", "提升"],
    "conclusion": ["conclusion", "summary", "future work", "limitation", "结论", "总结", "展望", "局限"],
}


def split_into_sections(raw_text: str) -> Dict[str, str]:
    lines = [line.strip() for line in raw_text.splitlines()]
    sections: Dict[str, List[str]] = {}
    current_heading = "front_matter"
    sections[current_heading] = []

    heading_names = (
        "introduction|background|related work|method|methods|approach|methodology|framework|"
        "experiment|experiments|experimental setup|implementation details|results|evaluation|"
        "analysis|discussion|conclusion|future work|摘要|引言|背景|相关工作|方法|实验|结果|讨论|结论|展望"
    )
    heading_regex = re.compile(
        rf"^(?:\d+(?:\.\d+)*[\.。\s]+)?(?:{heading_names})\s*$",
        re.IGNORECASE,
    )

    for line in lines:
        if not line:
            continue
        match = heading_regex.match(line)
        if match:
            current_heading = match.group(0).strip().lower()
            current_heading = re.sub(r"^\d+(?:\.\d+)*[\.。\s]+", "", current_heading).strip()
            sections.setdefault(current_heading, [])
            continue
        sections.setdefault(current_heading, []).append(line)

    return {name: "\n".join(content).strip() for name, content in sections.items() if any(content)}


def map_heading_to_bucket(heading: str) -> str | None:
    normalized = heading.lower()
    for bucket, aliases in HEADING_PATTERNS:
        if any(alias in normalized for alias in aliases):
            return bucket
    return None


def first_sentences(text: str, max_sentences: int = 5) -> str:
    if re.search(r"[\u4e00-\u9fff]", text):
        pieces = re.split(r"(?<=[。！？!?])\s*", text.replace("\n", ""))
        cleaned = [piece.strip() for piece in pieces if len(piece.strip()) >= 12]
        return "".join(cleaned[:max_sentences]).strip()
    pieces = re.split(r"(?<=[\.\!\?])\s+", text.replace("\n", " "))
    cleaned = [piece.strip() for piece in pieces if len(piece.strip()) > 20]
    return " ".join(cleaned[:max_sentences]).strip()


def score_bucket(text: str, bucket: str) -> int:
    lowered = text.lower()
    return sum(lowered.count(keyword) for keyword in KEYWORD_HINTS[bucket])


def fallback_extract(raw_text: str, bucket: str) -> str:
    paragraphs = [part.strip() for part in raw_text.split("\n\n") if len(part.strip()) > 60]
    ranked = sorted(paragraphs, key=lambda part: score_bucket(part, bucket), reverse=True)
    ranked = [part for part in ranked if score_bucket(part, bucket) > 0]
    if ranked:
        return first_sentences(ranked[0], max_sentences=4)
    return ""


def classify_paper(parsed: ParsedPaper) -> ClassifiedPaper:
    sections = split_into_sections(parsed.raw_text)
    parsed.sections = sections

    buckets: Dict[str, str] = {
        "background": first_sentences(parsed.abstract, max_sentences=3) if parsed.abstract else "",
        "method": "",
        "experiment_setup": "",
        "results": "",
        "conclusion": "",
    }
    extras: Dict[str, str] = {}

    for heading, text in sections.items():
        bucket = map_heading_to_bucket(heading)
        content = first_sentences(text, max_sentences=5)
        if bucket and not buckets[bucket]:
            buckets[bucket] = content
        else:
            extras[heading] = content

    for bucket_name in list(buckets.keys()):
        if not buckets[bucket_name]:
            buckets[bucket_name] = fallback_extract(parsed.raw_text, bucket_name)

    fallback_text = {
        "zh": {
            "background": "论文围绕一个重要研究问题展开，并说明该问题的研究价值。",
            "method": "论文提出了一种用于解决目标问题的方法或框架。",
            "experiment_setup": "论文基于标准数据集、实验设置和评价指标开展验证。",
            "results": "实验结果表明，所提出方法相比基线方法具有较好的表现。",
            "conclusion": "论文总结了方法的有效性，并指出后续可扩展的方向。",
        },
        "en": {
            "background": "The paper studies an important research problem and motivates why it matters.",
            "method": "The paper proposes a method to address the target problem.",
            "experiment_setup": "Experiments are conducted on benchmark settings with standard evaluation metrics.",
            "results": "The proposed method shows promising performance compared with baselines.",
            "conclusion": "The paper concludes that the proposed approach is effective and suggests future extensions.",
        },
    }
    defaults = fallback_text["zh" if parsed.language == "zh" else "en"]

    return ClassifiedPaper(
        title=parsed.title,
        abstract=parsed.abstract,
        background=buckets["background"] or defaults["background"],
        method=buckets["method"] or defaults["method"],
        experiment_setup=buckets["experiment_setup"] or defaults["experiment_setup"],
        results=buckets["results"] or defaults["results"],
        conclusion=buckets["conclusion"] or defaults["conclusion"],
        language=parsed.language,
        extra_sections=extras,
    )
