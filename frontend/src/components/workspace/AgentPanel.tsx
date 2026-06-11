import { useEffect, useRef, useState } from "react";
import { Send } from "lucide-react";
import type { PendingConfirmation, TaskLog, TimelineEntry } from "@/api/pptAgent";

export type ResultCard = {
  id: string;
  title: string;
  body: string;
};

type ChatMsg = { role: "agent" | "user"; text: string };

type AgentPanelProps = {
  messages: ChatMsg[];
  onSend: (text: string) => void;
  resultCards: ResultCard[];
  timeline: TimelineEntry[];
  runtimeLogs: TaskLog[];
  pendingConfirmation: PendingConfirmation | null;
  onApprove: (feedback: string) => void;
  onRevise: (feedback: string) => void;
  layoutOverrides?: Record<string, string>;
  onCycleLayout?: (itemId: string) => void;
  outlineOverrides?: Record<string, string>;
  onOutlineOverrideChange?: (itemId: string, value: string) => void;
  titleOverride?: string;
  onTitleOverrideChange?: (value: string) => void;
  onDisableFigure?: (itemId: string) => void;
  onUploadFigure?: (itemId: string, file: File) => void;
};

function parseLayoutBody(body: string): { layout: string; summary: string } {
  const [layoutPart, ...rest] = body.split("·");
  return {
    layout: (layoutPart || "bullets").trim(),
    summary: rest.join("·").trim(),
  };
}

function layoutLabel(layout: string): string {
  return (
    {
      cover: "封面页",
      bullets: "要点页",
      "arch-diagram": "架构图页",
      "chart-bar": "柱状图页",
      "chart-line": "折线图页",
      "chart-pie": "饼图页",
      "chart-radar": "雷达图页",
      "two-column": "双栏页",
      "three-column": "三栏页",
      table: "表格页",
      code: "技术细节页",
      comparison: "对比页",
      cta: "行动页",
      diff: "差异页",
      "flow-diagram": "流程图页",
      "figure-compare": "配图对比页",
      "figure-hero": "配图主视觉页",
      "figure-method": "方法配图页",
      "figure-results": "结果配图页",
      gantt: "甘特图页",
      "image-grid": "图片网格页",
      "image-hero": "大图主视觉页",
      "image-left": "左图右文页",
      "image-right": "左文右图页",
      "evidence-cards": "证据卡片页",
      "critique-panel": "审稿意见页",
      "kpi-grid": "指标卡片页",
      "method-swimlane": "方法泳道页",
      mindmap: "脑图页",
      "process-steps": "步骤页",
      "pros-cons": "优劣分析页",
      "question-matrix": "研究问题矩阵页",
      roadmap: "路线图页",
      "section-divider": "章节分隔页",
      "stat-highlight": "数据高亮页",
      statement: "核心论点页",
      terminal: "终端页",
      thanks: "结束页",
      timeline: "时间线页",
      toc: "目录页",
      "todo-checklist": "清单页",
    }[layout] || layout
  );
}

function statusLabel(status: string): string {
  return (
    {
      done: "已完成",
      running: "进行中",
      info: "提示",
      error: "错误",
      warning: "警告",
      waiting: "待确认",
    }[status] || status
  );
}

function recommendedLayouts(layout: string, title: string, summary: string): string[] {
  const text = `${title} ${summary}`.toLowerCase();

  if (layout.startsWith("figure-") || text.includes("配图")) {
    return ["figure-hero", "figure-method", "figure-results", "figure-compare", "image-left", "image-right", "image-hero", "image-grid"];
  }

  if (layout === "cover") {
    return ["cover", "section-divider", "image-hero", "big-quote"];
  }

  if (layout === "thanks") {
    return ["thanks", "statement", "big-quote", "stat-highlight", "section-divider"];
  }

  if (layout === "question-matrix" || text.includes("研究问题") || text.includes("research question")) {
    return ["question-matrix", "evidence-cards", "two-column", "table", "bullets"];
  }

  if (layout === "critique-panel" || text.includes("不足") || text.includes("追问") || text.includes("limitation")) {
    return ["critique-panel", "pros-cons", "question-matrix", "two-column", "todo-checklist"];
  }

  if (layout === "evidence-cards" || text.includes("创新") || text.includes("innovation")) {
    return ["evidence-cards", "statement", "kpi-grid", "comparison", "three-column"];
  }

  if (layout === "table" || text.includes("table") || text.includes("表")) {
    return ["table", "comparison", "two-column", "bullets"];
  }

  if (
    layout.startsWith("chart-") ||
    text.includes("result") ||
    text.includes("metric") ||
    text.includes("实验") ||
    text.includes("结果")
  ) {
    return ["figure-results", "evidence-cards", "chart-bar", "chart-line", "kpi-grid", "stat-highlight", "comparison", "table"];
  }

  if (
    layout === "code" ||
    layout === "terminal" ||
    text.includes("method") ||
    text.includes("algorithm") ||
    text.includes("pipeline") ||
    text.includes("方法") ||
    text.includes("算法")
  ) {
    return ["method-swimlane", "figure-method", "code", "flow-diagram", "process-steps", "arch-diagram", "two-column", "terminal"];
  }

  if (
    layout === "timeline" ||
    layout === "roadmap" ||
    text.includes("step") ||
    text.includes("process") ||
    text.includes("阶段") ||
    text.includes("流程")
  ) {
    return ["method-swimlane", "process-steps", "flow-diagram", "timeline", "roadmap", "two-column", "three-column"];
  }

  if (layout === "three-column") {
    return ["three-column", "two-column", "bullets", "comparison", "pros-cons"];
  }

  if (layout === "two-column") {
    return ["two-column", "three-column", "bullets", "comparison", "pros-cons"];
  }

  return ["bullets", "statement", "evidence-cards", "two-column", "three-column", "big-quote", "comparison"];
}

function LayoutPreview({ layout }: { layout: string }) {
  if (layout === "cover") {
    return (
      <div className="rounded-lg border border-slate-200 bg-slate-50 p-2">
        <div className="h-2.5 w-16 rounded bg-slate-300" />
        <div className="mt-3 h-5 w-4/5 rounded bg-slate-800/80" />
        <div className="mt-2 h-2 w-3/5 rounded bg-slate-300" />
        <div className="mt-4 grid grid-cols-2 gap-2">
          <div className="h-12 rounded bg-white shadow-sm" />
          <div className="h-12 rounded bg-white shadow-sm" />
        </div>
      </div>
    );
  }

  if (layout === "question-matrix") {
    return (
      <div className="rounded-lg border border-slate-200 bg-slate-50 p-2">
        <div className="h-2.5 w-20 rounded bg-slate-300" />
        <div className="mt-3 rounded bg-white shadow-sm">
          {Array.from({ length: 3 }).map((_, idx) => (
            <div key={idx} className="grid grid-cols-[28px_1fr_42px] gap-2 border-b border-slate-100 p-2 last:border-b-0">
              <div className="h-3 rounded bg-blue-300" />
              <div className="h-3 rounded bg-slate-200" />
              <div className="h-3 rounded bg-slate-100" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (layout === "method-swimlane") {
    return (
      <div className="rounded-lg border border-slate-200 bg-slate-50 p-2">
        <div className="h-2.5 w-20 rounded bg-slate-300" />
        <div className="mt-3 grid grid-cols-5 gap-1">
          {Array.from({ length: 5 }).map((_, idx) => (
            <div key={idx} className="h-16 rounded bg-white shadow-sm">
              <div className="m-1 h-2 rounded bg-blue-200" />
              <div className="mx-1 mt-2 h-2 rounded bg-slate-200" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (layout === "statement" || layout === "evidence-cards" || layout === "critique-panel") {
    return (
      <div className="rounded-lg border border-slate-200 bg-slate-50 p-2">
        <div className="h-2.5 w-20 rounded bg-slate-300" />
        <div className="mt-3 h-10 rounded bg-white shadow-sm" />
        <div className="mt-2 grid grid-cols-2 gap-2">
          <div className="h-12 rounded bg-white shadow-sm" />
          <div className="h-12 rounded bg-white shadow-sm" />
        </div>
      </div>
    );
  }

  if (layout === "two-column" || layout === "three-column") {
    const cols = layout === "two-column" ? 2 : 3;
    return (
      <div className="rounded-lg border border-slate-200 bg-slate-50 p-2">
        <div className="h-2.5 w-14 rounded bg-slate-300" />
        <div className={`mt-3 grid gap-2 ${cols === 2 ? "grid-cols-2" : "grid-cols-3"}`}>
          {Array.from({ length: cols }).map((_, idx) => (
            <div key={idx} className="rounded bg-white p-2 shadow-sm">
              <div className="h-2 w-3/4 rounded bg-slate-300" />
              <div className="mt-2 h-2 w-full rounded bg-slate-200" />
              <div className="mt-1 h-2 w-5/6 rounded bg-slate-200" />
              <div className="mt-1 h-2 w-2/3 rounded bg-slate-200" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (layout === "table" || layout.startsWith("chart-") || layout === "gantt") {
    return (
      <div className="rounded-lg border border-slate-200 bg-slate-50 p-2">
        <div className="h-2.5 w-14 rounded bg-slate-300" />
        <div className="mt-3 rounded bg-white shadow-sm">
          {Array.from({ length: 4 }).map((_, idx) => (
            <div key={idx} className="border-b border-slate-100 px-2 py-2 last:border-b-0">
              <div className="h-2 w-full rounded bg-slate-200" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (layout === "code" || layout === "terminal") {
    return (
      <div className="rounded-lg border border-slate-200 bg-slate-900 p-2">
        <div className="h-2.5 w-16 rounded bg-emerald-400/70" />
        <div className="mt-3 space-y-1.5 rounded bg-slate-800 p-2">
          <div className="h-2 w-5/6 rounded bg-slate-500" />
          <div className="h-2 w-full rounded bg-slate-600" />
          <div className="h-2 w-4/6 rounded bg-slate-500" />
          <div className="h-2 w-3/4 rounded bg-slate-600" />
        </div>
      </div>
    );
  }

  if (layout === "thanks" || layout === "section-divider" || layout === "cta") {
    return (
      <div className="rounded-lg border border-slate-200 bg-slate-50 p-2">
        <div className="mt-3 flex h-20 items-center justify-center rounded bg-white shadow-sm">
          <div className="h-5 w-24 rounded bg-slate-800/80" />
        </div>
      </div>
    );
  }

  if (layout === "image-grid" || layout === "image-hero" || layout === "image-left" || layout === "image-right" || layout === "kpi-grid" || layout.startsWith("figure-")) {
    return (
      <div className="rounded-lg border border-slate-200 bg-slate-50 p-2">
        <div className="h-2.5 w-14 rounded bg-slate-300" />
        <div className="mt-3 grid grid-cols-3 gap-2">
          <div className="h-10 rounded bg-white shadow-sm" />
          <div className="h-10 rounded bg-white shadow-sm" />
          <div className="h-10 rounded bg-white shadow-sm" />
          <div className="h-10 rounded bg-white shadow-sm" />
          <div className="h-10 rounded bg-white shadow-sm" />
          <div className="h-10 rounded bg-white shadow-sm" />
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-2">
      <div className="h-2.5 w-14 rounded bg-slate-300" />
      <div className="mt-3 space-y-2 rounded bg-white p-2 shadow-sm">
        <div className="h-3 rounded bg-slate-200" />
        <div className="h-3 rounded bg-slate-200" />
        <div className="h-3 w-5/6 rounded bg-slate-200" />
      </div>
    </div>
  );
}

export function AgentPanel({
  messages,
  onSend,
  resultCards,
  timeline,
  runtimeLogs,
  pendingConfirmation,
  onApprove,
  onRevise,
  layoutOverrides = {},
  onCycleLayout,
  outlineOverrides = {},
  onOutlineOverrideChange,
  titleOverride = "",
  onTitleOverrideChange,
  onDisableFigure,
  onUploadFigure,
}: AgentPanelProps) {
  const [input, setInput] = useState("");
  const chatScrollRef = useRef<HTMLDivElement>(null);
  const shouldStickToBottomRef = useRef(true);

  const isNearBottom = () => {
    const el = chatScrollRef.current;
    if (!el) return true;
    return el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  };

  useEffect(() => {
    const el = chatScrollRef.current;
    if (!el) return;
    if (shouldStickToBottomRef.current || isNearBottom()) {
      el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    }
  }, [messages.length, pendingConfirmation?.stage_id, resultCards.length]);

  const submit = () => {
    const t = input.trim();
    if (!t) return;
    onSend(t);
    setInput("");
  };

  const approve = () => {
    onApprove(input.trim());
    setInput("");
  };

  const revise = () => {
    const feedback = input.trim();
    if (!feedback) return;
    onRevise(feedback);
    setInput("");
  };

  return (
    <section className="flex h-full min-h-0 flex-col rounded-card border border-slate-200/80 bg-white shadow-card">
      <div className="shrink-0 border-b border-slate-100 px-4 py-3">
        <h2 className="text-sm font-semibold text-slate-900">智能体对话</h2>
        <p className="mt-0.5 text-[11px] text-slate-500">对话与生成结果分区展示，均可独立滚动</p>
      </div>

      <div
        ref={chatScrollRef}
        onScroll={() => {
          shouldStickToBottomRef.current = isNearBottom();
        }}
        className="min-h-0 flex-1 basis-0 space-y-3 overflow-y-auto overscroll-contain px-4 py-3"
      >
        {messages.map((m, i) => (
          <div
            key={i}
            className={
              m.role === "agent"
                ? "rounded-card border border-slate-100 bg-slate-50/80 p-3 text-sm text-slate-700"
                : "ml-4 rounded-card bg-primary/10 p-3 text-sm text-slate-800 sm:ml-8"
            }
          >
            {m.text}
          </div>
        ))}

        {timeline.map((entry) => (
          <article key={entry.id} className="rounded-card border border-slate-200 bg-white p-3 shadow-sm">
            <div className="flex items-center justify-between gap-3">
              <h4 className="text-xs font-semibold text-slate-900">{entry.title}</h4>
              <span className="text-[10px] tracking-wide text-slate-400">{statusLabel(entry.status)}</span>
            </div>
            <p className="mt-2 whitespace-pre-wrap text-xs leading-relaxed text-slate-600">{entry.body}</p>
          </article>
        ))}

        {pendingConfirmation && (
          <article className="rounded-card border border-amber-200 bg-amber-50 p-3 shadow-sm">
            <h4 className="text-sm font-semibold text-slate-900">{pendingConfirmation.title}</h4>
            <p className="mt-2 whitespace-pre-wrap text-xs leading-relaxed text-slate-700">
              {pendingConfirmation.body}
            </p>
            {pendingConfirmation.stage_id !== "outline_confirm" && (
              <div className="mt-3 grid gap-2">
                {pendingConfirmation.items.map((item) => (
                  <div key={item.id} className="rounded-xl border border-amber-100 bg-white/80 p-2">
                    {pendingConfirmation.stage_id === "layout_confirm" ? (
                      (() => {
                        const parsed = parseLayoutBody(item.body);
                        const layout = layoutOverrides[item.id] || parsed.layout;
                        const choices = recommendedLayouts(layout, item.title, parsed.summary);
                        const hasFigure = parsed.summary.includes("配图") || layout.startsWith("figure-") || layout === "image-left" || layout === "image-right";
                        return (
                          <>
                            <div className="flex items-center justify-between gap-2">
                              <div className="text-xs font-semibold text-slate-900">{item.title}</div>
                              <div className="flex items-center gap-2">
                                <span className="rounded-full bg-slate-900 px-2 py-0.5 text-[10px] font-semibold text-white">
                                  {layoutLabel(layout)}
                                </span>
                                <button
                                  type="button"
                                  onClick={() => onCycleLayout?.(item.id)}
                                  className="rounded-md border border-slate-300 bg-white px-2 py-0.5 text-[10px] font-medium text-slate-700 hover:bg-slate-50"
                                >
                                  切换布局
                                </button>
                              </div>
                            </div>
                            <div className="mt-2">
                              {item.figure_url ? (
                                <div className="overflow-hidden rounded-lg border border-slate-200 bg-slate-950/5">
                                  <img
                                    src={item.figure_url}
                                    alt={item.figure_caption || item.title}
                                    className="max-h-56 w-full object-contain"
                                  />
                                </div>
                              ) : (
                                <LayoutPreview layout={layout} />
                              )}
                            </div>
                            <div className="mt-2 text-xs leading-relaxed text-slate-600">
                              {item.figure_url ? (
                                <div className="mb-1 rounded-md bg-blue-50 px-2 py-1 text-[11px] text-blue-700">
                                  当前配图：{item.figure_caption || "未识别标题的论文图片"}
                                </div>
                              ) : null}
                              {parsed.summary || "该页面将按上述布局渲染。"}
                              <div className="mt-1 text-[10px] text-slate-500">
                                候选布局：{choices.map((name) => layoutLabel(name)).join(" / ")}
                              </div>
                            </div>
                            <div className="mt-2 flex flex-wrap gap-2">
                              {hasFigure ? (
                                <button
                                  type="button"
                                  onClick={() => onDisableFigure?.(item.id)}
                                  className="rounded-md border border-amber-300 bg-amber-50 px-2 py-1 text-[10px] font-medium text-amber-800 hover:bg-amber-100"
                                >
                                  不使用图片
                                </button>
                              ) : null}
                              <label className="cursor-pointer rounded-md border border-blue-200 bg-blue-50 px-2 py-1 text-[10px] font-medium text-blue-700 hover:bg-blue-100">
                                {hasFigure ? "上传替换图" : "上传图片"}
                                <input
                                  type="file"
                                  accept="image/png,image/jpeg,image/webp"
                                  className="hidden"
                                  onChange={(event) => {
                                    const file = event.target.files?.[0];
                                    if (file) onUploadFigure?.(item.id, file);
                                    event.currentTarget.value = "";
                                  }}
                                />
                              </label>
                            </div>
                          </>
                        );
                      })()
                    ) : (
                      <>
                        <div className="text-xs font-semibold text-slate-900">{item.title}</div>
                        <div className="mt-1 whitespace-pre-wrap text-xs leading-relaxed text-slate-600">
                          {item.body}
                        </div>
                      </>
                    )}
                  </div>
                ))}
              </div>
            )}
            {pendingConfirmation.stage_id === "outline_confirm" ? (
              <div className="mt-3 rounded-xl border border-amber-100 bg-white/80 p-2">
                {pendingConfirmation.items.map((item) => (
                  <div key={item.id} className="mb-3 last:mb-0">
                    <div className="text-xs font-semibold text-slate-900">{item.title}</div>
                    {item.id.startsWith("outline-") ? (
                      <input
                        value={outlineOverrides[item.id] ?? item.body}
                        onChange={(event) => onOutlineOverrideChange?.(item.id, event.target.value)}
                        className="mt-1 w-full rounded-lg border border-amber-200 bg-white px-2 py-1.5 text-xs outline-none focus:border-primary focus:ring-1 focus:ring-primary"
                      />
                    ) : (
                      <div className="mt-1 whitespace-pre-wrap text-xs leading-relaxed text-slate-600">{item.body}</div>
                    )}
                    {item.id === "paper-title" ? (
                      <>
                        <label className="mt-2 block text-[11px] font-medium text-slate-600">手动修正标题</label>
                        <input
                          value={titleOverride}
                          onChange={(event) => onTitleOverrideChange?.(event.target.value)}
                          placeholder="如果标题识别不准确，请在这里输入正确论文标题"
                          className="mt-1 w-full rounded-lg border border-amber-200 bg-white px-2 py-1.5 text-xs outline-none focus:border-primary focus:ring-1 focus:ring-primary"
                        />
                      </>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : null}
            <div className="mt-3 flex gap-2">
              <button
                type="button"
                onClick={approve}
                className="rounded-lg bg-primary px-3 py-2 text-xs font-medium text-white transition hover:bg-primary-hover"
              >
                确认并继续
              </button>
              <button
                type="button"
                onClick={revise}
                disabled={!input.trim()}
                className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                按意见重做本步
              </button>
            </div>
            <p className="mt-2 text-[11px] text-amber-700">重做本步前，请先在下方输入具体修改意见。</p>
          </article>
        )}

        {runtimeLogs.length > 0 && (
          <article className="rounded-card border border-slate-200 bg-slate-50 p-3">
            <h4 className="text-xs font-semibold text-slate-900">运行日志</h4>
            <ul className="mt-2 max-h-32 space-y-1 overflow-y-auto text-[11px] text-slate-600">
              {runtimeLogs.slice(-8).map((log, idx) => (
                <li key={`${log.created_at}-${idx}`}>
                  [{log.level}] {log.message}
                </li>
              ))}
            </ul>
          </article>
        )}
      </div>

      {resultCards.length > 0 && (
        <div className="max-h-[min(38vh,340px)] shrink-0 overflow-y-auto overscroll-contain border-t border-slate-100 px-4 py-3 sm:max-h-[min(42vh,400px)]">
          <h3 className="sticky top-0 z-10 mb-2 border-b border-slate-100 bg-white pb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
            生成结果
          </h3>
          <div className="grid gap-3 sm:grid-cols-2">
            {resultCards.map((c) => (
              <article
                key={c.id}
                className="rounded-card border border-slate-200 bg-white p-3 shadow-sm"
              >
                <h4 className="text-xs font-semibold text-slate-900">{c.title}</h4>
                <p className="mt-2 whitespace-pre-wrap text-xs leading-relaxed text-slate-600">
                  {c.body}
                </p>
              </article>
            ))}
          </div>
        </div>
      )}

      <div className="shrink-0 border-t border-slate-100 p-3">
        <div className="flex gap-2 rounded-card border border-slate-200 bg-slate-50 p-1">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            placeholder={
              pendingConfirmation
                ? "回复“确认”进入下一步，或直接输入修改意见重做当前步骤…"
                : "输入补充说明，例如：突出方法创新点…"
            }
            className="min-w-0 flex-1 bg-transparent px-2 py-2 text-sm outline-none"
          />
          <button
            type="button"
            onClick={submit}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary text-white transition hover:bg-primary-hover"
            aria-label="发送"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
        <p className="mt-1.5 text-center text-[11px] text-slate-400">Enter 发送 · Shift+Enter 换行</p>
      </div>
    </section>
  );
}
