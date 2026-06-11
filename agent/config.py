from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
RUNTIME_DIR = BASE_DIR / "runtime"
INPUTS_DIR = RUNTIME_DIR / "inputs"
OUTPUTS_DIR = RUNTIME_DIR / "outputs"
TEMPLATES_DIR = RUNTIME_DIR / "templates"
HTML_SKILL_DIR = BASE_DIR.parent / "html-ppt-skill-main"
SAMPLE_TEXT = BASE_DIR / "sample_data" / "sample_paper.txt"
EVAL_FIXTURES_DIR = BASE_DIR / "eval" / "fixtures"
TASK_DB_PATH = RUNTIME_DIR / "tasks.db"
SETTINGS_PATH = RUNTIME_DIR / "settings.json"

TEMPLATE_THEME_MAP: dict[str, str] = {
    "tech-sharing": "minimal-white",
    "weekly-report": "corporate-clean",
    "pitch-deck": "pitch-deck-vc",
    "presenter-mode-reveal": "editorial-serif",
    "product-launch": "magazine-bold",
    "course-module": "academic-paper",
    "xhs-post": "xiaohongshu-white",
    "xhs-white-editorial": "editorial-serif",
    "xhs-pastel-card": "soft-pastel",
    "graphify-dark-graph": "tokyo-night",
    "knowledge-arch-blueprint": "blueprint",
    "hermes-cyber-terminal": "terminal-green",
    "obsidian-claude-gradient": "catppuccin-mocha",
    "testing-safety-alert": "neo-brutalism",
    "dir-key-nav-minimal": "japanese-minimal",
}

STYLE_ACCENT_MAP: dict[str, str] = {
    "blue": "#1677ff",
    "red": "#c42d2b",
    "green": "#2e7d32",
    "purple": "#5d3fd3",
}

BUILTIN_TEMPLATE_PATHS: dict[str, Path] = {
    "学术极简模板": TEMPLATES_DIR / "builtin-academic-minimal.pptx",
    "会议汇报模板": TEMPLATES_DIR / "builtin-conference.pptx",
    "课题组周报模板": TEMPLATES_DIR / "builtin-weekly-report.pptx",
}

PIPELINE_STAGES = ("parse", "classify", "outline_confirm", "generate", "slides_confirm", "layout", "layout_confirm", "build")
TOTAL_STEPS = len(PIPELINE_STAGES)


def ensure_runtime_dirs() -> None:
    for path in (INPUTS_DIR, OUTPUTS_DIR, TEMPLATES_DIR, EVAL_FIXTURES_DIR):
        path.mkdir(parents=True, exist_ok=True)


def load_runtime_settings() -> dict[str, Any]:
    if not SETTINGS_PATH.exists():
        return {}
    try:
        return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_runtime_settings(settings: dict[str, Any]) -> None:
    ensure_runtime_dirs()
    SETTINGS_PATH.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")


def resolve_llm_provider() -> str:
    llm_settings = load_runtime_settings().get("llm") or {}
    if os.getenv("OPENAI_API_KEY", "").strip() or os.getenv("DASHSCOPE_API_KEY", "").strip():
        return "openai"
    if str(llm_settings.get("api_key") or "").strip():
        return "openai"
    if os.getenv("PAPER2PPT_USE_MOCK_LLM", "").lower() in {"1", "true", "yes"}:
        return "mock"
    return "local"


def style_accent(style_id: str) -> str:
    return STYLE_ACCENT_MAP.get(style_id, "#1677ff")
