from __future__ import annotations

from models import PresentationPlan, SlidePlan


def build_presentation_plan(page_count: int = 11, language: str = "en") -> PresentationPlan:
    if language == "zh":
        seminar_slides = [
            SlidePlan(slide_key="title", title="论文基本信息与概览", goal="提取题目、作者单位、研究领域、关键词、主要对象和一句话总结", max_bullets=4),
            SlidePlan(slide_key="background", title="研究背景与问题动机", goal="说明问题重要性、已有研究、现有不足和作者研究逻辑", max_bullets=4),
            SlidePlan(slide_key="research_questions", title="核心研究问题", goal="拆解 2 到 4 个具体研究问题、验证思路和解释目标", max_bullets=4),
            SlidePlan(slide_key="method", title="方法框架分析", goal="梳理数据输入、处理流程、核心方法、输出结果、关键假设和方法改进", max_bullets=4),
            SlidePlan(slide_key="experiment_setup", title="实验设计与验证逻辑", goal="分析数据集、对照组、评价指标、验证充分性和变量控制", max_bullets=4),
            SlidePlan(slide_key="results", title="主要结果解读", goal="提取 3 到 5 个关键结果，解释图表趋势、支撑观点、替代解释和可信度", max_bullets=4),
            SlidePlan(slide_key="innovation", title="创新性分析", goal="评价问题、方法、数据、机制和应用创新，并给出综合创新等级", max_bullets=4),
            SlidePlan(slide_key="limitations", title="论文不足与潜在问题", goal="从审稿人角度指出假设、数据、外推、机制、对照、复现和 baseline 问题", max_bullets=4),
            SlidePlan(slide_key="discussion_questions", title="组会可追问问题", goal="提出 5 到 8 个老师或审稿人可能追问的深度问题", max_bullets=4),
            SlidePlan(slide_key="research_inspiration", title="对后续研究的启发", goal="总结方法、实验设计、写作逻辑、研究切入点和改进方案", max_bullets=4),
            SlidePlan(slide_key="conclusion", title="最终评价与汇报策略", goal="综合判断论文价值、领域位置、是否值得深入阅读，以及哪些内容必须讲或可略讲", max_bullets=4),
        ]
        detail_titles = {
            "background": ["研究背景补充", "相关工作与问题动机"],
            "method": ["方法细节一", "训练与推理流程", "方法补充分析", "方法扩展讨论"],
            "experiment_setup": ["数据集与评价指标", "实验实现细节", "实验补充设置", "实验扩展分析"],
            "results": ["消融实验与分析", "错误案例与鲁棒性"],
        }
        detail_goals = {
            "background": "展开研究背景、已有工作与问题动机",
            "method": "解释模型结构、关键模块与实现流程",
            "experiment_setup": "说明数据集、评价指标与复现细节",
            "results": "展开关键结果、消融分析与鲁棒性",
        }
        detail_fallback = {
            "background": "研究背景补充{n}",
            "method": "方法补充分析{n}",
            "experiment_setup": "实验补充分析{n}",
            "results": "结果补充分析{n}",
        }
    else:
        seminar_slides = [
            SlidePlan(slide_key="title", title="Paper Overview and Basics", goal="Extract the title, authors and affiliation, research field, keywords, main subject, and a one-sentence summary", max_bullets=4),
            SlidePlan(slide_key="background", title="Research Background and Motivation", goal="Explain why the problem matters, prior work, existing gaps, and the author's reasoning", max_bullets=4),
            SlidePlan(slide_key="research_questions", title="Core Research Questions", goal="Break down 2 to 4 concrete research questions, their verification approach, and explanatory goals", max_bullets=4),
            SlidePlan(slide_key="method", title="Method Framework Analysis", goal="Lay out data inputs, processing pipeline, core method, outputs, key assumptions, and improvements", max_bullets=4),
            SlidePlan(slide_key="experiment_setup", title="Experimental Design and Validation Logic", goal="Analyze datasets, control groups, metrics, validation sufficiency, and variable control", max_bullets=4),
            SlidePlan(slide_key="results", title="Key Results Interpretation", goal="Extract 3 to 5 key results, explain figure/table trends, supporting claims, alternative explanations, and credibility", max_bullets=4),
            SlidePlan(slide_key="innovation", title="Novelty Analysis", goal="Assess novelty in problem, method, data, mechanism, and application, and give an overall novelty rating", max_bullets=4),
            SlidePlan(slide_key="limitations", title="Limitations and Potential Issues", goal="From a reviewer's view, point out issues in assumptions, data, extrapolation, mechanism, controls, reproducibility, and baselines", max_bullets=4),
            SlidePlan(slide_key="discussion_questions", title="Likely Seminar Questions", goal="Pose 5 to 8 deep questions an advisor or reviewer might raise", max_bullets=4),
            SlidePlan(slide_key="research_inspiration", title="Implications for Future Research", goal="Summarize lessons in method, experimental design, writing logic, research angles, and improvement plans", max_bullets=4),
            SlidePlan(slide_key="conclusion", title="Final Assessment and Presentation Strategy", goal="Judge overall value, position in the field, whether it merits deep reading, and what must be covered versus skimmed", max_bullets=4),
        ]
        detail_titles = {
            "background": ["Background Details", "Related Work and Motivation"],
            "method": ["Method Details I", "Training and Inference Flow", "Further Method Analysis", "Extended Method Discussion"],
            "experiment_setup": ["Dataset and Metrics", "Implementation Notes", "Further Experimental Setup", "Extended Experimental Analysis"],
            "results": ["Ablation and Analysis", "Error Cases and Robustness"],
        }
        detail_goals = {
            "background": "Expand on research background, prior work, and motivation",
            "method": "Explain architecture, key modules, and implementation flow",
            "experiment_setup": "Clarify datasets, metrics, and reproducibility details",
            "results": "Expand on key results, ablations, and robustness",
        }
        detail_fallback = {
            "background": "Background Details {n}",
            "method": "Method Analysis {n}",
            "experiment_setup": "Experimental Analysis {n}",
            "results": "Results Analysis {n}",
        }

    # Order in which analysis pages are added back as the page count grows beyond
    # the five required core pages. "discussion_questions" is intentionally
    # excluded from automatic selection. The canonical seminar order is used for
    # final layout regardless of selection order.
    core_keys = ["background", "research_questions", "method", "experiment_setup", "results"]
    analysis_add_order = ["title", "conclusion", "innovation", "limitations", "research_inspiration"]

    def _detail_split_sequence():
        # Order in which core sections are split into extra detail pages, given
        # as (parent_key, occurrence). A section with N detail pages spans N + 1
        # total pages (the main page plus N details).
        #   - method / experiment first reach 3 pages each (2 details),
        #   - then background / results reach 2 pages each (1 detail),
        #   - then method / experiment reach 4 pages each (3 details),
        #   - then background reaches its cap of 3 pages (2 details),
        #   - finally method / experiment keep alternating without an upper limit.
        # background is capped at 3 pages and results at 2 pages.
        yield ("method", 1)
        yield ("method", 2)
        yield ("experiment_setup", 1)
        yield ("experiment_setup", 2)
        yield ("background", 1)
        yield ("results", 1)
        yield ("method", 3)
        yield ("experiment_setup", 3)
        yield ("background", 2)
        occurrence = 4
        while True:
            yield ("method", occurrence)
            yield ("experiment_setup", occurrence)
            occurrence += 1

    def _build_detail(parent_key: str, occurrence: int) -> SlidePlan:
        titles = detail_titles.get(parent_key, [])
        if occurrence - 1 < len(titles):
            title = titles[occurrence - 1]
        else:
            title = detail_fallback[parent_key].format(n=occurrence)
        return SlidePlan(
            slide_key=f"{parent_key}_detail_{occurrence}",
            title=title,
            goal=detail_goals.get(parent_key, ""),
            max_bullets=4,
        )

    page_count = max(len(core_keys), min(page_count, 20))

    # 1. Start from the required core pages, then add analysis pages by priority.
    selected = list(core_keys)
    for key in analysis_add_order:
        if len(selected) >= page_count:
            break
        selected.append(key)

    # 2. Split core sections into detail pages following the split sequence.
    detail_counts: dict[str, int] = {}
    splits = _detail_split_sequence()
    while len(selected) < page_count:
        parent, occurrence = next(splits)
        detail_counts[parent] = occurrence
        selected.append(f"{parent}_detail_{occurrence}")

    # 3. Emit in canonical seminar order; detail pages follow their parent.
    selected_set = set(selected)
    slides: list[SlidePlan] = []
    for slide in seminar_slides:
        if slide.slide_key not in selected_set:
            continue
        slides.append(slide)
        for occurrence in range(1, detail_counts.get(slide.slide_key, 0) + 1):
            slides.append(_build_detail(slide.slide_key, occurrence))

    return PresentationPlan(slides=slides)
