from __future__ import annotations

import re
from pathlib import Path

from pypdf import PdfReader

from config import OUTPUTS_DIR
from models import ParsedPaper
from pdf_enhanced import (
    detect_language,
    extract_tables_from_text,
    extract_text_with_pymupdf,
    is_text_garbled,
    ocr_pdf_pages,
    reflow_dual_column_text,
    text_quality_score,
    text_signal_length,
)

ABSTRACT_PATTERN = re.compile(
    r"\b(?:abstract|摘要)\b[:\s：]*(.*?)(?=\n\s*(?:1[\.\s]+|introduction\b|引言\b|keywords\b|关键词\b|index terms\b))",
    re.IGNORECASE | re.DOTALL,
)

CHINESE_ABSTRACT_PATTERN = re.compile(
    r"摘要[：:\s]*(.*?)(?=关键词|引言|(?:^|\n)\s*\d+[\.。\s]+|introduction)",
    re.IGNORECASE | re.DOTALL | re.MULTILINE,
)


def normalize_text(text: str) -> str:
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def markdown_to_plain_text(text: str) -> str:
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"^[ \t]{0,3}#{1,6}[ \t]+(.+?)[ \t#]*$", r"\1", text, flags=re.MULTILINE)
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"(\*\*|__)(.*?)\1", r"\2", text)
    text = re.sub(r"(\*|_)(.*?)\1", r"\2", text)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*>\s?", "", text, flags=re.MULTILINE)
    return normalize_text(text)


def extract_text_from_pdf(pdf_path: str, task_id: str = "") -> tuple[str, bool, bool]:
    reader = PdfReader(pdf_path)
    pages: list[str] = []
    dual_column = False
    for page in reader.pages:
        page_text = page.extract_text() or ""
        if page_text.strip():
            reflowed, applied = reflow_dual_column_text(page_text)
            if applied:
                dual_column = True
            pages.append(reflowed if applied else page_text)

    raw = normalize_text("\n\n".join(pages))
    pymupdf_raw = normalize_text(extract_text_with_pymupdf(pdf_path))
    if pymupdf_raw and text_quality_score(pymupdf_raw) > text_quality_score(raw) + 0.08:
        raw = pymupdf_raw
    if len(raw.split()) < 80 or is_text_garbled(raw):
        ocr_text, ocr_applied = ocr_pdf_pages(pdf_path)
        if ocr_applied and (
            text_signal_length(ocr_text) > text_signal_length(raw) or is_text_garbled(raw)
        ):
            raw = normalize_text(ocr_text)
            return raw, ocr_applied, dual_column
    return raw, False, dual_column


def _clean_title_candidate(line: str) -> str:
    line = re.sub(r"\s+", " ", line).strip(" -–—|")
    line = re.sub(r"^(?:title|paper title)\s*[:：]\s*", "", line, flags=re.IGNORECASE)
    return line.strip()


def _is_title_noise(line: str, language: str) -> bool:
    lower = line.lower()
    if not line or len(line) < 6 or len(line) > 190:
        return True
    if re.fullmatch(r"(?:abstract|摘要|keywords?|关键词|introduction|引言)", line, re.IGNORECASE):
        return True
    if re.search(r"(?:doi|arxiv|isbn|issn|http|www\.|@|copyright|©|\bvol\.|\bno\.|\bpp\.)", lower):
        return True
    if re.search(r"\b(?:university|department|institute|laboratory|school of|college|faculty|email|author|affiliation)\b", lower):
        return True
    if re.fullmatch(r"\d+|[ivxlcdm]+", lower):
        return True
    if re.fullmatch(r"(?:may|june|july|august|september|october|november|december|january|february|march|april)\s+\d{1,2},?\s+\d{4}", line, re.IGNORECASE):
        return True
    if re.match(r"^(?:figure|fig\.|table|algorithm)\s*\d+", lower):
        return True
    if line.count(",") >= 3 or line.count(";") >= 2:
        return True
    signal = sum(ch.isalpha() or "\u4e00" <= ch <= "\u9fff" for ch in line)
    if signal < max(4, len(line) * 0.35):
        return True
    if language == "zh" and ("摘要" in line or "关键词" in line):
        return True
    return False


def _score_title_candidate(candidate: str, index: int, language: str) -> float:
    text = _clean_title_candidate(candidate)
    lower = text.lower()
    score = 100 - index * 6
    length = len(text)
    word_count = len(re.findall(r"[A-Za-z]+", text))
    cjk_count = len(re.findall(r"[\u4e00-\u9fff]", text))

    if language == "zh":
        if 10 <= cjk_count <= 70:
            score += 35
        elif cjk_count:
            score += 12
    else:
        if 5 <= word_count <= 24:
            score += 35
        elif 3 <= word_count <= 32:
            score += 12

    if 18 <= length <= 150:
        score += 18
    if ":" in text or "：" in text:
        score += 8
    if text.endswith("."):
        score -= 8
    if re.search(r"\b(?:abstract|keywords?|introduction|references|appendix)\b", lower) or re.search(r"摘要|关键词|引言|参考文献", text):
        score -= 80
    if re.search(r"\d{4}|\[[0-9,\s]+\]|\bet al\.\b", lower):
        score -= 14
    symbol_ratio = sum(not (ch.isalnum() or ch.isspace() or "\u4e00" <= ch <= "\u9fff" or ch in ":：-/()") for ch in text) / max(1, len(text))
    score -= symbol_ratio * 60
    return score


def infer_title(raw_text: str, source_name: str, language: str = "en") -> str:
    lines = [_clean_title_candidate(line) for line in raw_text.splitlines() if line.strip()]
    head_lines: list[tuple[int, str]] = []
    for idx, line in enumerate(lines[:24]):
        if re.fullmatch(r"(?:abstract|摘要)", line, re.IGNORECASE):
            break
        if re.search(r"^(?:abstract|摘要)\s*[:：]", line, re.IGNORECASE):
            break
        if not _is_title_noise(line, language):
            head_lines.append((idx, line))

    candidates: list[tuple[int, str]] = []
    for idx, line in head_lines:
        candidates.append((idx, line))
    for (idx_a, line_a), (idx_b, line_b) in zip(head_lines, head_lines[1:]):
        if idx_b - idx_a <= 2:
            joined = f"{line_a} {line_b}"
            if not _is_title_noise(joined, language):
                candidates.append((idx_a, joined))

    if candidates:
        best_idx, best = max(
            candidates,
            key=lambda item: _score_title_candidate(item[1], item[0], language),
        )
        if _score_title_candidate(best, best_idx, language) > 40:
            return re.sub(r"\s+", " ", best).strip()
    return Path(source_name).stem.replace("_", " ").strip() or "Untitled Paper"


def infer_abstract(raw_text: str, language: str = "en") -> str:
    if language == "zh":
        match = CHINESE_ABSTRACT_PATTERN.search(raw_text)
        if match:
            return match.group(1).strip()

    match = ABSTRACT_PATTERN.search(raw_text)
    if match:
        return match.group(1).strip()

    lines = raw_text.splitlines()
    for idx, line in enumerate(lines):
        if re.fullmatch(r"\s*(?:abstract|摘要)\s*", line, re.IGNORECASE):
            chunk = []
            for follow in lines[idx + 1 : idx + 12]:
                if re.match(
                    r"^\s*(?:1[\.\s]+|introduction\b|引言\b|keywords\b|关键词\b|method\b|methods\b|background\b|related work\b|results?\b|conclusion\b|方法|背景|结果|结论)\s*",
                    follow,
                    re.IGNORECASE,
                ):
                    break
                chunk.append(follow.strip())
            if chunk:
                return " ".join(part for part in chunk if part).strip()
    return ""


def parse_pdf(pdf_path: str, task_id: str = "") -> ParsedPaper:
    raw_text, ocr_applied, dual_column_reflowed = extract_text_from_pdf(pdf_path, task_id=task_id)
    source_name = Path(pdf_path).name
    language = detect_language(raw_text)

    return ParsedPaper(
        source_name=source_name,
        raw_text=raw_text,
        title=infer_title(raw_text, source_name, language=language),
        abstract=infer_abstract(raw_text, language=language),
        language=language,
        figures=[],
        tables=[],
        ocr_applied=ocr_applied,
        dual_column_reflowed=dual_column_reflowed,
    )


def parse_text_file(text_path: str) -> ParsedPaper:
    path = Path(text_path)
    raw_source = path.read_text(encoding="utf-8")
    raw_text = markdown_to_plain_text(raw_source) if path.suffix.lower() in {".md", ".markdown"} else normalize_text(raw_source)
    source_name = Path(text_path).name
    language = detect_language(raw_text)
    return ParsedPaper(
        source_name=source_name,
        raw_text=raw_text,
        title=infer_title(raw_text, source_name, language=language),
        abstract=infer_abstract(raw_text, language=language),
        language=language,
        tables=extract_tables_from_text(raw_text),
    )
