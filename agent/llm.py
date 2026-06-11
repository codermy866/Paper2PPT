from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Optional

from config import load_runtime_settings
from prompts import (
    ACADEMIC_ANALYSIS_ROLE_PROMPT,
    PAPER_ANALYSIS_DIMENSIONS_PROMPT,
    PRESENTATION_WRITING_PROMPT,
    PPT_PAGE_CONTENT_PROMPT,
    SLIDE_SCRIPT_PROMPT,
    SLIDE_BULLETS_PROMPT,
    SLIDE_NOTES_PROMPT,
)


class BaseLLM:
    def generate(self, prompt: str, context: str, max_tokens: int = 300) -> str:
        raise NotImplementedError


class MockLLM(BaseLLM):
    def generate(self, prompt: str, context: str, max_tokens: int = 300) -> str:
        if "中文" in prompt or "不要输出英文" in prompt:
            if "每行一条" in prompt or "bullet" in prompt.lower():
                title_match = re.search(r"页面标题[：:]\s*(.+)", context)
                title = title_match.group(1).strip() if title_match else "本页"
                if "核心研究问题" in title:
                    return "\n".join(["拆解论文试图回答的核心研究问题", "说明作者如何通过方法和实验验证假设", "关注结果是否支撑更广泛的解释"])
                if "创新" in title:
                    return "\n".join(["从问题、方法、数据和应用层面判断创新性", "区分实质性贡献与增量式改进", "结合实验验证评价创新是否充分成立"])
                if "不足" in title or "潜在问题" in title:
                    return "\n".join(["检查方法假设和实验验证是否充分", "关注结论是否存在过度外推风险", "指出可能缺少的对照实验或更强基线"])
                if "追问" in title:
                    return "\n".join(["追问方法选择背后的依据和边界条件", "追问实验设计能否排除其他解释", "追问结论在更复杂场景中的适用性"])
                if "启发" in title:
                    return "\n".join(["提炼方法设计中可借鉴的思路", "总结实验验证和论文写作的可学习之处", "将论文不足转化为后续研究切入点"])
                if "最终评价" in title or "汇报策略" in title:
                    return "\n".join(["综合判断论文贡献、局限和领域位置", "明确汇报中必须展开和可以略讲的内容", "提前准备老师可能追问的关键证据"])
                if "结果" in title or "消融" in title or "鲁棒" in title:
                    return "\n".join(["总结实验中最重要的性能表现", "对比基线方法说明本文方法优势", "结合消融结果解释关键设计的作用"])
                if "背景" in title:
                    return "\n".join(["交代论文关注的研究问题和实际价值", "说明现有方法仍存在的关键不足", "引出本文需要解决的核心挑战"])
                if "方法" in title or "流程" in title:
                    return "\n".join(["概述本文提出的核心方法框架", "说明关键模块如何提升模型表现", "强调方法相对已有工作的改进点"])
                if "实验" in title or "数据" in title or "指标" in title:
                    return "\n".join(["说明实验使用的数据集和评价指标", "概括主要实验配置与对比基线", "为后续结果分析提供评估依据"])
                if "结论" in title or "启示" in title:
                    return "\n".join(["总结论文提出方法的主要贡献", "说明实验验证得到的核心结论", "指出方法的应用价值与后续方向"])
                return "\n".join(
                    [
                        "概括本页对应内容的核心观点",
                        "突出与论文主题直接相关的关键信息",
                        "用适合汇报的方式串联上下文",
                    ]
                )
            return "本页用于讲解论文对应部分的核心内容，重点说明研究动机、方法设计和实验结论。"
        sentences = [part.strip() for part in context.replace("\n", " ").split(".") if part.strip()]
        preview = ". ".join(sentences[:2]).strip()
        if preview and not preview.endswith("."):
            preview += "."
        return preview or "This slide summarizes the paper section in mock mode."


class OpenAICompatibleLLM(BaseLLM):
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        saved_llm = (load_runtime_settings().get("llm") or {})
        saved_provider = str(saved_llm.get("provider") or "dashscope").strip().lower()
        saved_api_key = str(saved_llm.get("api_key") or "").strip()
        saved_base_url = str(saved_llm.get("base_url") or "").strip()
        saved_model = str(saved_llm.get("model") or "").strip()
        dashscope_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
        openai_key = os.getenv("OPENAI_API_KEY", "").strip()
        dashscope_base_url = os.getenv("DASHSCOPE_BASE_URL", "").strip()
        openai_base_url = os.getenv("OPENAI_BASE_URL", "").strip()
        dashscope_model = os.getenv("DASHSCOPE_MODEL", "").strip()
        openai_model = os.getenv("OPENAI_MODEL", "").strip()

        preferred_base_url = base_url or dashscope_base_url or saved_base_url or openai_base_url
        using_dashscope = bool(
            dashscope_key
            or dashscope_model
            or saved_provider == "dashscope"
            or (preferred_base_url and "dashscope" in preferred_base_url)
        )
        default_base_url = (
            "https://dashscope.aliyuncs.com/compatible-mode/v1"
            if using_dashscope
            else "https://api.openai.com/v1"
        )
        default_model = "qwen3.7-plus" if using_dashscope else "gpt-4o-mini"
        self.api_key = (api_key or (dashscope_key if using_dashscope else openai_key) or saved_api_key).strip()
        self.base_url = (preferred_base_url or default_base_url).rstrip("/")
        self.model = (model or (dashscope_model if using_dashscope else openai_model) or saved_model or default_model).strip()
        self.using_dashscope = using_dashscope
        saved_thinking = bool(saved_llm.get("enable_thinking", False))
        thinking_default = "true" if saved_thinking else "false"
        self.enable_thinking = os.getenv("DASHSCOPE_ENABLE_THINKING", thinking_default).lower() not in {"0", "false", "no"}
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY or DASHSCOPE_API_KEY is required for OpenAICompatibleLLM")

    def generate(self, prompt: str, context: str, max_tokens: int = 300) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": prompt.strip()},
                {"role": "user", "content": context[:12000]},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.4,
        }
        if self.using_dashscope and self.enable_thinking:
            payload["enable_thinking"] = True
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"LLM request failed ({exc.code}): {detail[:300]}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"LLM request failed: {exc}") from exc

        choices = body.get("choices") or []
        if not choices:
            return ""
        message = choices[0].get("message") or {}
        return str(message.get("content") or "").strip()


def create_llm(provider: str) -> Optional[BaseLLM]:
    if provider == "openai":
        return OpenAICompatibleLLM()
    if provider in {"mock", "local"}:
        return MockLLM()
    return None


def llm_generate(
    prompt: str,
    context: str,
    llm: Optional[BaseLLM] = None,
    max_tokens: int = 300,
) -> str:
    if llm is None:
        return ""
    return llm.generate(prompt=prompt, context=context, max_tokens=max_tokens)


def _clean_generated_line(line: str) -> str:
    cleaned = line.strip()
    cleaned = re.sub(r"^[-*•\s]+", "", cleaned)
    cleaned = re.sub(r"^\d+[\.\)、\)]\s*", "", cleaned)
    cleaned = cleaned.strip(" \t;；")
    return cleaned


def _looks_like_noise(line: str) -> bool:
    lowered = line.lower()
    blocked = ["用户反馈", "用户关注", "focus:", "prompt", "instruction", "请根据", "修改意见"]
    if any(token in lowered for token in blocked):
        return True
    visible = [ch for ch in line if not ch.isspace()]
    if not visible:
        return True
    odd = sum(1 for ch in visible if not (ch.isalnum() or "\u4e00" <= ch <= "\u9fff" or ch in "，。；：、,.:%+-/()（）"))
    return odd / max(len(visible), 1) > 0.28


def _slide_context(text: str, slide_title: str = "", slide_goal: str = "") -> str:
    parts = []
    parts.append("分析任务: 请站在研究生组会文献汇报角度分析论文，不要只做摘要。")
    if slide_title:
        parts.append(f"页面标题: {slide_title}")
    if slide_goal:
        parts.append(f"本页目标: {slide_goal}")
    parts.append("分析维度: 研究问题、方法设计、实验验证、结果解释、创新性、不足、可借鉴之处。")
    parts.append("论文原文片段:")
    parts.append(text)
    return "\n".join(parts)


def generate_bullets_with_llm(
    text: str,
    max_bullets: int,
    llm: Optional[BaseLLM],
    language: str = "en",
    slide_title: str = "",
    slide_goal: str = "",
) -> list[str]:
    if llm is None or not text.strip():
        return []
    language_rule = (
        f"Return up to {max_bullets} concise English bullet lines, one per line, no numbering. "
        "Use complete, presentation-ready English. Do not use Chinese except for source-specific names."
        if language != "zh"
        else (
            f"最多返回 {max_bullets} 行中文要点，每行一条，不要编号。"
            "每条控制在 18 到 34 个汉字左右，必须贴合页面标题和本页目标。"
            "除论文标题、模型名、指标名和专有名词外，不要输出英文。"
        )
    )
    raw = llm_generate(
        prompt=(
            ACADEMIC_ANALYSIS_ROLE_PROMPT
            + "\n"
            + PAPER_ANALYSIS_DIMENSIONS_PROMPT
            + "\n"
            + PRESENTATION_WRITING_PROMPT
            + "\n"
            + PPT_PAGE_CONTENT_PROMPT
            + "\n"
            + SLIDE_BULLETS_PROMPT
            + "\n"
            + language_rule
        ),
        context=_slide_context(text, slide_title=slide_title, slide_goal=slide_goal),
        llm=llm,
        max_tokens=400,
    )
    bullets = [_clean_generated_line(line) for line in raw.splitlines() if line.strip()]
    bullets = [b for b in bullets if len(b) >= 8 and not _looks_like_noise(b)]
    return bullets[:max_bullets]


def generate_notes_with_llm(
    text: str,
    llm: Optional[BaseLLM],
    language: str = "en",
    slide_title: str = "",
    slide_goal: str = "",
) -> str:
    language_rule = (
        "Write short, fluent speaker notes in English. Do not use Chinese except for source-specific names."
        if language != "zh"
        else "请用中文写 1 到 2 句简短演讲备注，语句自然，适合现场汇报。除论文标题、模型名、指标名和专有名词外，不要输出英文。"
    )
    generated = llm_generate(
        prompt=(
            ACADEMIC_ANALYSIS_ROLE_PROMPT
            + "\n"
            + PRESENTATION_WRITING_PROMPT
            + "\n"
            + SLIDE_SCRIPT_PROMPT
            + "\n"
            + SLIDE_NOTES_PROMPT
            + "\n"
            + language_rule
        ),
        context=_slide_context(text, slide_title=slide_title, slide_goal=slide_goal),
        llm=llm,
        max_tokens=180,
    )
    return generated.strip()


def generate_script_from_slide_with_llm(
    *,
    title: str,
    bullets: list[str],
    core_points: list[str],
    draft_notes: str,
    visual_context: str = "",
    prev_title: str = "",
    next_title: str = "",
    llm: Optional[BaseLLM],
    language: str = "zh",
) -> str:
    if llm is None:
        return ""
    language_rule = (
        (
            "Write a natural, fluent, colloquial English speaker script suitable for reading aloud directly. "
            "Explain and expand on the page's core content; do not mechanically repeat the bullets. "
            "Open by introducing the page topic, explain the key points in the middle, and close with a natural transition to the next page. "
            "For pages with a figure or table, state only the conclusion it supports; do not describe its internal details such as axes, legends, data points, or method-name labels. "
            "Keep each page around 20 to 40 seconds; key pages can run slightly longer, while agenda and transition pages stay short. "
            "Ensure logical coherence with the surrounding pages and avoid vague, empty, or repetitive phrasing. "
            "When transitioning, reference the actual next-page topic and vary the wording; do not reuse a fixed transition sentence or repeat sentences already used on adjacent pages. "
            "Do not fabricate data, experimental results, or conclusions absent from the source. "
            "Do not output user feedback, file names, figure indices, prompt text, or implementation metadata."
        )
        if language != "zh"
        else (
            "请用自然、流畅、口语化的中文生成逐字稿，语言要适合直接朗读。"
            "解释和扩展页面核心内容，不要机械复述 PPT 页面上的文字。"
            "开头自然引入本页主题，中间讲解关键观点，结尾自然过渡到下一页。"
            "遇到配图或表格的页面，只说明图表得出的结论及其意义，不要逐一描述坐标轴、图例、数据点或方法名等图内细节。"
            "每页控制在 20 到 40 秒朗读量，重点页可略长，目录页或过渡页保持简短。"
            "保证与前后页逻辑连贯，避免空泛、重复或前后脱节的表达。"
            "过渡时要结合下一页的实际主题，并变换措辞，不要套用固定的过渡句，也不要重复相邻页已经用过的句子。"
            "不要编造原文没有的数据、实验结果或结论。"
            "不要输出用户反馈、文件名、图片编号、prompt 或实现元数据。"
        )
    )
    context = "\n".join(
        [
            f"上一页标题: {prev_title or '无（这是第一页）'}",
            f"页面标题: {title}",
            f"下一页标题: {next_title or '无（这是最后一页）'}",
            "PPT页面文字:",
            *[f"- {item}" for item in bullets],
            "每页核心观点:",
            *[f"- {item}" for item in core_points],
            f"备注草稿: {draft_notes}",
            f"图表/视觉信息: {visual_context or '无'}",
        ]
    )
    generated = llm_generate(
        prompt=(
            ACADEMIC_ANALYSIS_ROLE_PROMPT
            + "\n"
            + PRESENTATION_WRITING_PROMPT
            + "\n"
            + SLIDE_SCRIPT_PROMPT
            + "\n"
            + language_rule
        ),
        context=context,
        llm=llm,
        max_tokens=320,
    )
    return generated.strip()
