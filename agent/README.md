# Paper to PPT Agent

一个面向科研论文汇报场景的 Python Agent 项目。输入论文 PDF，输出一份可编辑的 `.pptx` 学术汇报文件。

当前版本是 MVP，重点是先跑通以下文本驱动流程：

`PDF -> parser -> classifier -> planner -> generator -> ppt_builder -> output.pptx`

## 功能概览

- 读取并解析论文 PDF 文本
- 提取标题、摘要、章节文本
- 识别背景/问题、方法、实验设置、结果、结论
- 自动规划 6 页基础汇报结构
- 为每页生成标题、要点、可选 notes
- 使用 `python-pptx` 导出可编辑 PPT
- 无 API key 时支持 `--sample` 和 `--mock-llm` 演示完整流程

## 项目结构

```text
paper_to_ppt_agent/
├── agent.py
├── app.py
├── classifier.py
├── generator.py
├── llm.py
├── models.py
├── parser.py
├── planner.py
├── ppt_builder.py
├── prompts.py
├── requirements.txt
├── README.md
└── sample_data/
    └── sample_paper.txt
```

## 模块职责

- `app.py`
  - 命令行入口，接收 PDF 路径、输出路径、运行模式等参数。
- `agent.py`
  - 主调度 Agent，串联解析、分类、规划、内容生成与 PPT 构建。
- `parser.py`
  - 负责 PDF 文本抽取与基础元信息解析，也支持从示例文本加载。
- `classifier.py`
  - 负责章节切分、关键内容识别与字段归类。
- `planner.py`
  - 负责将论文内容映射为固定的汇报结构。
- `generator.py`
  - 负责为每页生成 slide title、bullet points 和 speaker notes。
- `ppt_builder.py`
  - 使用固定布局导出 `.pptx` 文件。
- `prompts.py`
  - 预留提示词模板，方便后续接入真实 LLM。
- `llm.py`
  - 统一的 LLM 接口与 mock 实现。
- `models.py`
  - 项目内共享的数据结构定义。
- `sample_data/sample_paper.txt`
  - 无 PDF、无 API key 时的演示输入。

## 安装

建议使用 Python 3.10+

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 运行方式

### 1. 使用真实 PDF

```bash
python app.py --input /absolute/path/to/paper.pdf --output ./output/paper_report.pptx
```

### 2. 使用示例文本演示完整流程

```bash
python app.py --sample --output ./output/sample_report.pptx
```

### 3. 启用 mock LLM 模式

```bash
python app.py --sample --mock-llm --output ./output/sample_report.pptx
```

### 4. 启用前端 Web 界面（Streamlit）
```bash
cd agent
streamlit run web_streamlit.py
```

界面支持：
- 上传论文 PDF
- 可选上传 PPTX 模板（基于 slide_key 自动匹配更合适的模板布局并新建生成页，复用模板版式与配色）
- 选择 notes 生成模式（mock / 非 mock）
- 下载生成的 `.pptx`

## 输出示例

MVP 默认生成 6 页左右的汇报：

1. 标题页
2. 研究背景与问题
3. 方法
4. 实验设置
5. 结果
6. 结论与启发

输出文件是可编辑的 `.pptx`，可直接用 PowerPoint 或 Keynote 打开继续修改。

## 当前实现说明

### PDF 解析

- 使用 `pypdf` 抽取纯文本
- 标题通过首页前几行启发式识别
- 摘要通过 `Abstract` 段落启发式提取

### 章节识别

- 先按常见章节标题切分，如 `Introduction`、`Method`、`Experiments`、`Results`、`Conclusion`
- 若结构不标准，则根据关键词回退匹配
- 目标是先保证“有结果可用”，再逐步提高准确率

### LLM 扩展接口

如果你后续要接入真实大模型，可在 `llm.py` 中替换 `llm_generate()` 的实现，并在：

- `classifier.py` 中做更强的段落级分类
- `planner.py` 中做动态页数规划
- `generator.py` 中做更自然的 bullet 生成与 notes 生成

## 后续扩展建议

### 1. 图表插入

- 在 `parser.py` 中增加图片与图表位置信息抽取
- 在 `ppt_builder.py` 中将关键图插入指定页
- 可增加 `figure_selector.py` 专门挑选最值得展示的图

### 2. 多轮编辑

- 增加 `editor.py`
- 支持命令如“压缩成 5 页”“方法页更详细”“结论更偏应用价值”
- 修改 `SlidePlan` 后重新生成 `.pptx`

### 3. 演讲稿生成

- 在 `generator.py` 中增加更长的 notes 生成模式
- 或单独增加 `speaker_notes.py`
- 支持按每页 30 秒 / 60 秒两种讲稿粒度生成

### 4. 模板风格切换

- 在 `ppt_builder.py` 中加入 Theme 配置
- 支持学术简洁风、答辩风、深色演示风等固定样式

## 常见问题

### 没有 API key 能跑吗？

能。当前默认是规则驱动版本，`--mock-llm` 只是演示未来接入大模型时的接口形态。

### PDF 识别不稳定怎么办？

这是论文 PDF 常见问题。当前版本优先保证鲁棒性：

- 标准结构论文效果最好
- 非标准排版会回退到关键词提取
- 如果抽取文本质量差，建议先转为更干净的 PDF，或后续接入 OCR 模块

## 最小验证

安装依赖后执行：

```bash
python app.py --sample --output ./output/sample_report.pptx
```

若成功，会在 `output/` 下看到生成的可编辑 PPT。
