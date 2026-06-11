import { useCallback, useRef, useState } from "react";
import { Upload } from "lucide-react";

const templateOptions = [
  { id: "tech-sharing", label: "技术分享" },
  { id: "weekly-report", label: "周报汇报" },
  { id: "pitch-deck", label: "商业路演" },
  { id: "presenter-mode-reveal", label: "演讲者模式" },
  { id: "product-launch", label: "产品发布" },
  { id: "course-module", label: "课程模块" },
  { id: "xhs-post", label: "小红书图文" },
  { id: "xhs-white-editorial", label: "白底杂志风" },
  { id: "xhs-pastel-card", label: "马卡龙卡片" },
  { id: "graphify-dark-graph", label: "暗底知识图谱" },
  { id: "knowledge-arch-blueprint", label: "蓝图架构" },
  { id: "hermes-cyber-terminal", label: "暗终端评审" },
  { id: "obsidian-claude-gradient", label: "暗紫渐变" },
  { id: "testing-safety-alert", label: "红琥珀警示" },
  { id: "dir-key-nav-minimal", label: "极简演讲" },
] as const;

const styleOptions = [
  { id: "blue", label: "学术蓝" },
  { id: "red", label: "报告红" },
  { id: "green", label: "自然绿" },
  { id: "purple", label: "创新紫" },
] as const;

const featuredTemplateIds = new Set([
  "tech-sharing",
  "weekly-report",
  "pitch-deck",
  "presenter-mode-reveal",
  "product-launch",
  "xhs-post",
]);

type InputTab = "upload" | "paste" | "example";
const supplementalImageKindHelp = {
  method: "方法：模型结构、算法流程、框架图",
  setup: "实验/数据：数据集、指标、实验设置",
  results: "结果：性能对比、消融、曲线、可视化",
  table: "表格截图：论文表格或统计表",
  other: "其他：不确定或需要手动匹配",
} as const;

function buildPageRecommendation(pageCount: number, images: SupplementalImage[]) {
  const uncategorizedCount = images.filter((image) => image.kind === "other").length;
  const imageCounts = images.reduce(
    (acc, image) => {
      if (image.kind === "method") acc.method += 1;
      if (image.kind === "setup") acc.setup += 1;
      if (image.kind === "results" || image.kind === "table") acc.results += 1;
      return acc;
    },
    { method: 0, setup: 0, results: 0 }
  );
  const gaps = {
    method: Math.max(0, imageCounts.method - 1),
    setup: Math.max(0, imageCounts.setup - 1),
    results: Math.max(0, imageCounts.results - 1),
  };
  let flexiblePages = Math.max(0, pageCount - 5);
  const remainingGaps = { ...gaps };
  for (const key of ["method", "setup", "results"] as const) {
    const covered = Math.min(remainingGaps[key], flexiblePages);
    remainingGaps[key] -= covered;
    flexiblePages -= covered;
  }
  const remainingGapTotal = remainingGaps.method + remainingGaps.setup + remainingGaps.results;
  const recommended = Math.min(20, pageCount + remainingGapTotal);
  const reasons = [
    remainingGaps.method > 0 ? `方法图还缺 ${remainingGaps.method} 页承载` : "",
    remainingGaps.setup > 0 ? `实验/数据图还缺 ${remainingGaps.setup} 页承载` : "",
    remainingGaps.results > 0 ? `结果/表格图还缺 ${remainingGaps.results} 页承载` : "",
  ].filter(Boolean);
  return {
    recommended,
    reasons,
    hasTypedImages: imageCounts.method + imageCounts.setup + imageCounts.results > 0,
    uncategorizedCount,
    canApply: remainingGapTotal > 0 && pageCount < 20,
    atLimit: pageCount + remainingGapTotal > 20,
  };
}

type SupplementalImage = {
  id: string;
  file: File;
  kind: keyof typeof supplementalImageKindHelp;
  description: string;
};

export type GeneratePayload = {
  inputMode: InputTab;
  pastedText?: string;
  file?: File;
  supplementalImages?: SupplementalImage[];
  pageCount: number;
  templateId: (typeof templateOptions)[number]["id"];
  styleId: StyleId;
};

export type StyleId = (typeof styleOptions)[number]["id"];

type InputPanelProps = {
  pageCount: number;
  onPageCountChange: (n: number) => void;
  onGenerate: (payload: GeneratePayload) => void;
  onGenerateTemplateOnly: (payload: GeneratePayload) => void;
  generating: boolean;
};

export function InputPanel({
  pageCount,
  onPageCountChange,
  onGenerate,
  onGenerateTemplateOnly,
  generating,
}: InputPanelProps) {
  const [tab, setTab] = useState<InputTab>("upload");
  const [templateId, setTemplateId] = useState<(typeof templateOptions)[number]["id"]>("tech-sharing");
  const [styleId, setStyleId] = useState<StyleId>("blue");
  const [showAllTemplates, setShowAllTemplates] = useState(false);
  const [pasteText, setPasteText] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | undefined>();
  const [supplementalImages, setSupplementalImages] = useState<SupplementalImage[]>([]);
  const [fileError, setFileError] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const selectFile = useCallback((file?: File) => {
    if (!file) return;

    const fileName = file.name.toLowerCase();
    const supported =
      fileName.endsWith(".pdf") ||
      fileName.endsWith(".md") ||
      fileName.endsWith(".markdown") ||
      fileName.endsWith(".txt") ||
      file.type === "application/pdf" ||
      file.type === "text/markdown" ||
      file.type === "text/plain";
    if (!supported) {
      setSelectedFile(undefined);
      setFileError("只支持上传 PDF、Markdown 或 TXT 文件。");
      return;
    }

    if (file.size > 50 * 1024 * 1024) {
      setSelectedFile(undefined);
      setFileError("文件超过 50MB，请压缩后再上传。");
      return;
    }

    setSelectedFile(file);
    setFileError("");
    setTab("upload");
  }, []);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    const dropped = e.dataTransfer.files?.[0];
    selectFile(dropped);
  }, [selectFile]);

  const addSupplementalImages = useCallback((files: FileList | null) => {
    if (!files?.length) return;
    const supported = Array.from(files).filter((file) => {
      const name = file.name.toLowerCase();
      return (
        name.endsWith(".png") ||
        name.endsWith(".jpg") ||
        name.endsWith(".jpeg") ||
        name.endsWith(".webp") ||
        ["image/png", "image/jpeg", "image/webp"].includes(file.type)
      );
    });
    setSupplementalImages((prev) =>
      [
        ...prev,
        ...supported.map((file) => ({
          id: `${file.name}-${file.size}-${file.lastModified}-${crypto.randomUUID()}`,
          file,
          kind: "other" as const,
          description: "",
        })),
      ].slice(0, 12)
    );
  }, []);

  const generate = () => {
    onGenerate({
      inputMode: tab,
      pastedText: pasteText.trim(),
      file: selectedFile,
      supplementalImages,
      pageCount,
      templateId,
      styleId,
    });
  };

  const generateTemplateOnly = () => {
    onGenerateTemplateOnly({
      inputMode: "example",
      pastedText: "",
      file: undefined,
      supplementalImages,
      pageCount,
      templateId,
      styleId,
    });
  };

  const featuredTemplates = templateOptions.filter((template) => featuredTemplateIds.has(template.id));
  const moreTemplates = templateOptions.filter((template) => !featuredTemplateIds.has(template.id));
  const pageRecommendation = buildPageRecommendation(pageCount, supplementalImages);
  const recommendedPageCount = pageRecommendation.recommended;

  return (
    <section className="flex h-full min-h-0 flex-col rounded-card border border-slate-200/80 bg-white p-4 shadow-card">
      <h2 className="shrink-0 text-sm font-semibold text-slate-900">输入与配置</h2>

      <div className="min-h-0 flex-1 overflow-y-auto pr-1">
      <div className="mt-4 flex rounded-lg bg-slate-100 p-0.5 text-xs font-medium">
        {(
          [
            ["upload", "上传文件"],
            ["paste", "粘贴文本"],
            ["example", "使用示例"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            className={
              tab === id
                ? "flex-1 rounded-md bg-white py-2 text-primary shadow-sm"
                : "flex-1 rounded-md py-2 text-slate-600 transition hover:text-slate-900"
            }
          >
            {label}
          </button>
        ))}
      </div>

      <div className="mt-4 min-h-[140px] flex-1">
        {tab === "upload" && (
          <div
            role="button"
            tabIndex={0}
            onClick={() => fileInputRef.current?.click()}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                fileInputRef.current?.click();
              }
            }}
            onDragOver={(e) => {
              e.preventDefault();
              e.dataTransfer.dropEffect = "copy";
            }}
            onDrop={onDrop}
            className="flex h-full min-h-[140px] cursor-pointer flex-col items-center justify-center rounded-card border-2 border-dashed border-slate-300 bg-slate-50/80 px-4 py-8 text-center transition hover:border-primary/50 hover:bg-slate-50"
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="application/pdf,text/markdown,text/plain,.pdf,.md,.markdown,.txt"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                selectFile(file);
                e.currentTarget.value = "";
              }}
            />
            <Upload className="h-8 w-8 text-slate-400" />
            <span className="mt-2 text-sm font-medium text-slate-700">
              拖拽文件到此处或点击上传
            </span>
            <p className="mt-1 text-xs text-slate-500">支持 PDF / Markdown / TXT，最大 50MB</p>
            <p className="mt-1 text-[11px] text-slate-400">PDF 仅解析文字；需要图表请在下方上传图片素材</p>
            {fileError && (
              <p className="mt-2 rounded bg-rose-50 px-2 py-1 text-xs text-rose-600">
                {fileError}
              </p>
            )}
            {selectedFile && (
              <p className="mt-2 rounded bg-white px-2 py-1 text-xs text-primary">
                已选择：{selectedFile.name}
              </p>
            )}
          </div>
        )}
        {tab === "paste" && (
          <textarea
            value={pasteText}
            onChange={(e) => setPasteText(e.target.value)}
            placeholder="粘贴论文摘要或全文片段…"
            className="h-full min-h-[140px] w-full resize-none rounded-card border border-slate-200 bg-white p-3 text-sm outline-none ring-primary/20 focus:ring-2"
          />
        )}
        {tab === "example" && (
          <div className="rounded-card border border-slate-200 bg-slate-50 p-3 text-xs leading-relaxed text-slate-600">
            将加载内置示例论文片段，用于快速体验不同 html-ppt 模板。点击底部按钮即可。
          </div>
        )}
      </div>

      <div className="mt-4 rounded-card border border-slate-200 bg-slate-50/70 p-3">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="text-xs font-semibold text-slate-700">补充图片素材</div>
            <p className="mt-0.5 text-[11px] text-slate-500">PDF 图表请截图上传；Markdown 表格可直接解析</p>
          </div>
          <label className="cursor-pointer rounded-lg border border-primary/30 bg-white px-2.5 py-1.5 text-[11px] font-medium text-primary hover:bg-primary/5">
            上传图片
            <input
              type="file"
              multiple
              accept="image/png,image/jpeg,image/webp,.png,.jpg,.jpeg,.webp"
              className="hidden"
              onChange={(event) => {
                addSupplementalImages(event.target.files);
                event.currentTarget.value = "";
              }}
            />
          </label>
        </div>
        {supplementalImages.length > 0 ? (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {supplementalImages.map((image, idx) => (
              <div
                key={image.id}
                className="w-full rounded-lg border border-slate-100 bg-white p-2 text-[10px] text-slate-600"
              >
                <div className="flex items-center gap-2">
                  <span className="min-w-0 flex-1 truncate font-medium">{image.file.name}</span>
                  <select
                    value={image.kind}
                    onChange={(event) =>
                      setSupplementalImages((prev) =>
                        prev.map((item) =>
                          item.id === image.id ? { ...item, kind: event.target.value as SupplementalImage["kind"] } : item
                        )
                      )
                    }
                    className="rounded-md border border-slate-200 bg-white px-1.5 py-1 text-[10px] outline-none"
                  >
                    <option value="method">方法图</option>
                    <option value="setup">实验/数据图</option>
                    <option value="results">结果图</option>
                    <option value="table">表格截图</option>
                    <option value="other">其他</option>
                  </select>
                </div>
                <p className="mt-1 text-[10px] leading-relaxed text-slate-400">
                  {supplementalImageKindHelp[image.kind]}
                </p>
                <div className="mt-1 flex items-center gap-1">
                  <input
                    value={image.description}
                    onChange={(event) =>
                      setSupplementalImages((prev) =>
                        prev.map((item) =>
                          item.id === image.id ? { ...item, description: event.target.value } : item
                        )
                      )
                    }
                    placeholder="说明图片内容，如：Figure 2 消融实验、Table 1 数据集统计"
                    className="min-w-0 flex-1 rounded-md border border-slate-200 px-2 py-1 text-[10px] outline-none focus:border-primary"
                  />
                <button
                  type="button"
                  onClick={() => setSupplementalImages((prev) => prev.filter((_, imageIdx) => imageIdx !== idx))}
                  className="font-semibold text-slate-400 hover:text-rose-500"
                  aria-label={`移除图片 ${image.file.name}`}
                >
                  x
                </button>
                </div>
              </div>
            ))}
          </div>
        ) : null}
        {supplementalImages.length > 0 && pageRecommendation.canApply ? (
          <div className="mt-2 rounded-lg border border-blue-100 bg-blue-50 px-2 py-2 text-[11px] leading-relaxed text-blue-700">
            已上传 {supplementalImages.length} 张图片。{pageRecommendation.reasons.join("，")}，建议改为{" "}
            <button
              type="button"
              onClick={() => onPageCountChange(recommendedPageCount)}
              className="font-semibold underline decoration-blue-300 underline-offset-2 hover:text-blue-900"
            >
              {recommendedPageCount} 页
            </button>
            。
          </div>
        ) : null}
        {supplementalImages.length > 0 && !pageRecommendation.canApply && !pageRecommendation.atLimit ? (
          <div className="mt-2 rounded-lg border border-slate-100 bg-white px-2 py-2 text-[11px] leading-relaxed text-slate-600">
            {pageRecommendation.hasTypedImages
              ? `已上传 ${supplementalImages.length} 张图片。当前 ${pageCount} 页预计可以承载已分类图片。`
              : `已上传 ${supplementalImages.length} 张图片，请先为图片选择“方法/实验/结果/表格”等类型，系统再推荐是否需要增加页数。`}
            {pageRecommendation.uncategorizedCount > 0 && pageRecommendation.hasTypedImages
              ? ` 还有 ${pageRecommendation.uncategorizedCount} 张图片为“其他”，不会参与页数推荐。`
              : ""}
          </div>
        ) : null}
        {supplementalImages.length > 0 && pageRecommendation.atLimit ? (
          <div className="mt-2 rounded-lg border border-amber-100 bg-amber-50 px-2 py-2 text-[11px] leading-relaxed text-amber-700">
            已上传 {supplementalImages.length} 张图片，但 20 页上限内仍可能无法做到一图一页。建议减少图片数量、合并同类图片，或在布局确认阶段手动取舍。
          </div>
        ) : null}
      </div>

      <div className="mt-6 space-y-4 border-t border-slate-100 pt-4">
        <div>
          <div className="flex items-center justify-between gap-3">
            <span className="text-xs font-medium text-slate-600">模板选择</span>
            <button
              type="button"
              onClick={() => setShowAllTemplates((value) => !value)}
              className="text-xs font-medium text-primary transition hover:text-primary-hover"
            >
              {showAllTemplates ? "收起更多模板" : "更多模板"}
            </button>
          </div>
          <div className="mt-2 grid grid-cols-2 gap-2">
            {featuredTemplates.map((template) => (
              <button
                key={template.id}
                type="button"
                onClick={() => setTemplateId(template.id)}
                className={
                  templateId === template.id
                    ? "rounded-card border-2 border-primary bg-primary/10 px-3 py-2 text-sm font-medium text-primary"
                    : "rounded-card border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-600 transition hover:border-slate-300"
                }
              >
                {template.label}
              </button>
            ))}
          </div>
          {showAllTemplates && (
            <div className="mt-3 grid grid-cols-2 gap-2 border-t border-slate-100 pt-3">
              {moreTemplates.map((template) => (
                <button
                  key={template.id}
                  type="button"
                  onClick={() => setTemplateId(template.id)}
                  className={
                    templateId === template.id
                      ? "rounded-card border-2 border-primary bg-primary/10 px-3 py-2 text-sm font-medium text-primary"
                      : "rounded-card border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-600 transition hover:border-slate-300"
                  }
                >
                  {template.label}
                </button>
              ))}
            </div>
          )}
        </div>

        <div>
          <span className="text-xs font-medium text-slate-600">风格配色</span>
          <div className="mt-2 grid grid-cols-2 gap-2">
            {styleOptions.map((style) => (
              <button
                key={style.id}
                type="button"
                onClick={() => setStyleId(style.id)}
                className={
                  styleId === style.id
                    ? "rounded-card border-2 border-primary bg-primary/10 px-3 py-2 text-sm font-medium text-primary"
                    : "rounded-card border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-600 transition hover:border-slate-300"
                }
              >
                {style.label}
              </button>
            ))}
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between text-xs font-medium text-slate-600">
            <span>页数设置</span>
            <span className="text-slate-900">{pageCount} 页</span>
          </div>
          <input
            type="range"
            min={5}
            max={20}
            value={pageCount}
            onChange={(e) => onPageCountChange(Number(e.target.value))}
            className="slider-primary mt-2 w-full"
          />
        </div>
      </div>

      <button
        type="button"
        onClick={generate}
        disabled={generating}
        className="mt-6 w-full rounded-card bg-primary py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-primary-hover disabled:cursor-not-allowed disabled:opacity-60"
      >
        {generating ? "生成中..." : "开始生成 HTML PPT"}
      </button>
      <button
        type="button"
        onClick={generateTemplateOnly}
        disabled={generating}
        className="mt-2 w-full rounded-card border border-slate-300 bg-white py-2.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
      >
        仅用示例生成
      </button>
      <p className="mt-1 text-center text-[11px] text-slate-500">
        当前版本以模板为主，模板会自带默认主题与版式气质
      </p>
      </div>
    </section>
  );
}
