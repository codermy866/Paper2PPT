from __future__ import annotations

import re


def content_length(text: str, language: str = "en") -> int:
    text = text.strip()
    if not text:
        return 0
    if language == "zh" or re.search(r"[\u4e00-\u9fff]", text):
        return len(re.sub(r"\s+", "", text))
    return len(text.split())


def is_substantial(text: str, language: str = "en", min_words: int = 8, min_chars: int = 24) -> bool:
    if language == "zh" or re.search(r"[\u4e00-\u9fff]", text):
        return content_length(text, language) >= min_chars
    return content_length(text, language) >= min_words


def looks_like_figure_legend_noise(text: str) -> bool:
    """Detect figure legend / axis-tick fragments leaked from a figure into its caption.

    These look like short token soup of method-name abbreviations and tick values
    (e.g. "SBPGP EQL GP-GOMEA Noise Level 0 0.01 0.1 DSR FFX"), which slip past the
    odd-character noise check because every token is alphanumeric.
    """
    compact = re.sub(r"\s+", " ", text or "").strip()
    if not compact:
        return True
    if re.search(r"[\u4e00-\u9fff]", compact):
        return False
    tokens = compact.split()
    if len(tokens) < 4:
        return False
    numeric_tokens = sum(1 for tok in tokens if re.fullmatch(r"[-+]?\d*\.?\d+%?", tok))
    short_caps = sum(1 for tok in tokens if re.fullmatch(r"[A-Za-z][A-Za-z0-9-]{0,5}", tok) and tok[:1].isupper())
    sentence_words = sum(1 for tok in tokens if re.fullmatch(r"[a-z]{3,}", tok))
    fragment_ratio = (numeric_tokens + short_caps) / max(len(tokens), 1)
    # Real prose has connective lowercase words; legend soup almost none.
    if fragment_ratio >= 0.6 and sentence_words <= 1:
        return True
    if numeric_tokens >= 3 and sentence_words <= 2:
        return True
    return False
