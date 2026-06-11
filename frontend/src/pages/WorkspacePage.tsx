import { useEffect, useMemo, useState } from "react";
import { AppHeader } from "@/components/AppHeader";
import { InputPanel, type GeneratePayload } from "@/components/workspace/InputPanel";
import { AgentPanel, type ResultCard } from "@/components/workspace/AgentPanel";
import { PreviewPanel, type SlideThumb } from "@/components/workspace/PreviewPanel";
import {
  confirmTaskStage,
  createTask,
  getTaskLogs,
  getTaskStatus,
  uploadTaskFigure,
  type PendingConfirmation,
  type TaskLog,
  type TaskResult,
  type TimelineEntry,
} from "@/api/pptAgent";

type ChatRole = "agent" | "user";

const initialMessages: { role: ChatRole; text: string }[] = [
  {
    role: "agent",
    text: "您好，我是 Paper2PPT 智能体。上传论文或粘贴摘要后，我可以帮您提炼要点并生成学术汇报 PPT。您也可以直接说：「生成 8 页、突出实验结果」。",
  },
];

export function WorkspacePage() {
  const [pageCount, setPageCount] = useState(8);
  const [messages, setMessages] = useState<{ role: ChatRole; text: string }[]>(initialMessages);
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [completedSteps, setCompletedSteps] = useState(0);
  const [totalSteps, setTotalSteps] = useState(6);
  const [result, setResult] = useState<TaskResult | null>(null);
  const [statusText, setStatusText] = useState("请先上传论文并点击开始生成");
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [htmlDownloadUrl, setHtmlDownloadUrl] = useState<string | null>(null);
  const [htmlPreviewUrl, setHtmlPreviewUrl] = useState<string | null>(null);
  const [runtimeLogs, setRuntimeLogs] = useState<TaskLog[]>([]);
  const [instruction, setInstruction] = useState("");
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [pendingConfirmation, setPendingConfirmation] = useState<PendingConfirmation | null>(null);
  const [layoutOverrides, setLayoutOverrides] = useState<Record<string, string>>({});
  const [outlineOverrides, setOutlineOverrides] = useState<Record<string, string>>({});
  const [titleOverride, setTitleOverride] = useState("");
  const parseLayoutName = (body: string) => {
    const [layoutPart] = body.split("·");
    return (layoutPart || "bullets").trim();
  };

  const recommendedLayouts = (layout: string, title: string, summary: string) => {
    const text = `${title} ${summary}`.toLowerCase();

    if (layout.startsWith("figure-") || text.includes("配图")) {
      return ["figure-hero", "figure-method", "figure-results", "figure-compare", "image-left", "image-right", "image-hero", "image-grid"];
    }
    if (layout === "cover") return ["cover", "section-divider", "image-hero", "big-quote", "statement"];
    if (layout === "thanks") return ["thanks", "statement", "big-quote", "stat-highlight", "section-divider"];
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
    if (layout === "three-column") return ["three-column", "two-column", "bullets", "comparison", "pros-cons"];
    if (layout === "two-column") return ["two-column", "three-column", "bullets", "comparison", "pros-cons"];
    return ["bullets", "statement", "evidence-cards", "two-column", "three-column", "big-quote", "comparison"];
  };

  const resultCards = useMemo<ResultCard[]>(
    () => (result ? result.result_cards : []),
    [result]
  );
  const slides = useMemo<SlideThumb[]>(() => (result ? result.slides : []), [result]);

  useEffect(() => {
    if (!activeTaskId) return;
    let cancelled = false;

    const timer = setInterval(async () => {
      try {
        const status = await getTaskStatus(activeTaskId);
        if (cancelled) return;
        setCompletedSteps(status.completed_steps);
        setTotalSteps(status.total_steps);
        setStatusText(status.message);
        setTimeline(status.timeline ?? []);
        const confirmation = status.pending_confirmation ?? null;
        setPendingConfirmation(confirmation);
        if (confirmation?.stage_id === "outline_confirm") {
          const titleItem = confirmation.items.find((item) => item.id === "paper-title");
          if (titleItem && !titleOverride) {
            const match = titleItem.body.match(/当前识别标题：(.+?)(?:\n|$)/);
            setTitleOverride(match?.[1]?.trim() || "");
          }
          setOutlineOverrides((prev) => {
            if (Object.keys(prev).length > 0) return prev;
            return Object.fromEntries(
              confirmation.items
                .filter((item) => item.id.startsWith("outline-"))
                .map((item) => [item.id, item.body])
            );
          });
        }
        if (confirmation?.stage_id !== "layout_confirm") {
          setLayoutOverrides({});
        }
        if (confirmation?.stage_id !== "outline_confirm") {
          setOutlineOverrides({});
        }
        void getTaskLogs(activeTaskId).then(setRuntimeLogs);

        if (status.status === "succeeded" && status.result) {
          setGenerating(false);
          setResult(status.result);
          setDownloadUrl(status.result.download_url);
          setHtmlDownloadUrl(status.result.html_download_url);
          setHtmlPreviewUrl(status.result.html_preview_url);
          setPageCount(status.result.slide_count);
          const applied = status.result.applied_config;
          setMessages((prev) => [
            ...prev,
            {
              role: "agent",
              text: applied
                ? `HTML PPT 已生成完成（页数 ${applied.page_count}，模板 ${applied.template_id}，风格 ${applied.style_id ?? "blue"}，内容生成 ${applied.llm_provider === "openai" ? "OpenAI" : "本地模式"}）。你可以在右侧预览或下载 PPTX / HTML 压缩包。`
                : "HTML PPT 已生成完成，你可以在右侧直接下载。",
            },
          ]);
          clearInterval(timer);
        } else if (status.status === "failed") {
          setGenerating(false);
          setMessages((prev) => [
            ...prev,
            { role: "agent", text: status.error ?? "任务失败，请检查文件格式后重试。" },
          ]);
          clearInterval(timer);
        } else if (status.status === "waiting_confirmation") {
          setGenerating(false);
        }
      } catch (error) {
        setGenerating(false);
        setMessages((prev) => [
          ...prev,
          { role: "agent", text: `状态查询失败：${String(error)}` },
        ]);
        clearInterval(timer);
      }
    }, 1500);

    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [activeTaskId]);

  const handleGenerate = async (payload: GeneratePayload) => {
    let finalPayload = payload;
    if (payload.inputMode === "upload" && !payload.file) {
      setMessages((prev) => [...prev, { role: "agent", text: "请先选择一个 PDF、Markdown 或 TXT 文件再生成。" }]);
      return;
    }
    if (finalPayload.inputMode === "paste" && !finalPayload.pastedText?.trim()) {
      setMessages((prev) => [...prev, { role: "agent", text: "请先粘贴论文文本后再生成。" }]);
      return;
    }

    try {
      setGenerating(true);
      setCompletedSteps(0);
      setResult(null);
      setDownloadUrl(null);
      setHtmlDownloadUrl(null);
      setHtmlPreviewUrl(null);
      setRuntimeLogs([]);
      setTimeline([]);
      setPendingConfirmation(null);
      setLayoutOverrides({});
      setOutlineOverrides({});
      setTitleOverride("");
      setStatusText("任务创建中…");
      setMessages((prev) => [
        ...prev,
        { role: "agent", text: "已收到生成请求，开始创建任务并进入后端处理。" },
      ]);
      const taskId = await createTask(finalPayload, instruction);
      setActiveTaskId(taskId);
    } catch (error) {
      setGenerating(false);
      setMessages((prev) => [
        ...prev,
        { role: "agent", text: `任务创建失败：${String(error)}` },
      ]);
    }
  };

  const handleGenerateTemplateOnly = async (payload: GeneratePayload) => {
    await handleGenerate({
      ...payload,
      inputMode: "example",
      file: undefined,
      pastedText: "",
    });
  };

  const handleSend = (text: string) => {
    if (pendingConfirmation) {
      const normalized = text.trim().toLowerCase();
      setMessages((prev) => [...prev, { role: "user", text }]);
      if (["确认", "ok", "okay", "yes", "继续", "通过"].includes(normalized)) {
        void handleStageAction("approve", "");
        return;
      }
      void handleStageAction("revise", text);
      return;
    }

    setInstruction(text);
    setMessages((prev) => [...prev, { role: "user", text }]);
    setMessages((prev) => [
      ...prev,
      {
        role: "agent",
        text: "收到。该要求会作为“补充指令”应用到下一次生成任务中。你可以重新点击“开始生成 HTML PPT”。",
      },
    ]);
  };

  const handleStageAction = async (action: "approve" | "revise", feedback: string) => {
    if (!activeTaskId || !pendingConfirmation) return;
    if (action === "revise" && !feedback.trim()) {
      setMessages((prev) => [
        ...prev,
        { role: "agent", text: "请先写清楚修改意见，再点击“按意见重做本步”。" },
      ]);
      return;
    }
    try {
      setGenerating(true);
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        const nextMessage = {
          role: "agent" as const,
          text:
            action === "approve"
              ? `已确认 ${pendingConfirmation.title}，继续下一步。`
              : `已收到对 ${pendingConfirmation.title} 的修改意见，正在重做本步。`,
        };
        if (last?.role === "agent" && last.text === nextMessage.text) {
          return prev;
        }
        return [...prev, nextMessage];
      });
      await confirmTaskStage(
        activeTaskId,
        action,
        feedback,
        pendingConfirmation.stage_id === "layout_confirm" ? layoutOverrides : {},
        pendingConfirmation.stage_id === "outline_confirm" ? outlineOverrides : {},
        pendingConfirmation.stage_id === "outline_confirm" ? titleOverride : ""
      );
      setPendingConfirmation(null);
      setLayoutOverrides({});
      setOutlineOverrides({});
      setStatusText(action === "approve" ? "已确认，正在进入下一步…" : "正在根据意见重做当前步骤…");
    } catch (error) {
      setGenerating(false);
      setMessages((prev) => [
        ...prev,
        { role: "agent", text: `阶段处理失败：${String(error)}` },
      ]);
    }
  };

  const handleCycleLayout = (itemId: string) => {
    if (pendingConfirmation?.stage_id !== "layout_confirm") return;
    const currentItem = pendingConfirmation.items.find((item) => item.id === itemId);
    if (!currentItem) return;
    const baseLayout = layoutOverrides[itemId] || parseLayoutName(currentItem.body);
    const [, ...rest] = currentItem.body.split("·");
    const choices = recommendedLayouts(baseLayout, currentItem.title, rest.join("·").trim());
    const currentIndex = Math.max(0, choices.indexOf(baseLayout));
    const nextLayout = choices[(currentIndex + 1) % choices.length];
    setLayoutOverrides((prev) => ({ ...prev, [itemId]: nextLayout }));
  };

  const handleDisableFigure = (itemId: string) => {
    if (pendingConfirmation?.stage_id !== "layout_confirm") return;
    setLayoutOverrides((prev) => ({ ...prev, [itemId]: "bullets" }));
  };

  const handleUploadFigure = async (itemId: string, file: File) => {
    if (!activeTaskId) return;
    try {
      await uploadTaskFigure(activeTaskId, itemId, file);
      setLayoutOverrides((prev) => ({ ...prev, [itemId]: "figure-hero" }));
      setMessages((prev) => [...prev, { role: "agent", text: "替换图片已上传，并绑定到当前页面。" }]);
      const status = await getTaskStatus(activeTaskId);
      setPendingConfirmation(status.pending_confirmation ?? pendingConfirmation);
      setTimeline(status.timeline ?? []);
    } catch (error) {
      setMessages((prev) => [...prev, { role: "agent", text: `图片上传失败：${String(error)}` }]);
    }
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-[#f5f6f8]">
      <AppHeader
        title="Paper2PPT Agent"
        subtitle="支持模板与风格控制的科研论文演示文稿智能生成"
        statusLabel="当前状态: 数据分析"
        onSaveDraft={() => {}}
        onExport={() => {}}
      />
      <main className="grid min-h-0 flex-1 grid-cols-1 gap-3 overflow-y-auto overflow-x-hidden p-3 sm:gap-4 sm:p-4 md:grid-cols-2 xl:h-full xl:grid-cols-[minmax(260px,330px)_minmax(0,1fr)_minmax(280px,360px)] xl:items-stretch xl:overflow-hidden">
        <div className="min-h-[min(420px,55vh)] min-w-0 xl:h-full xl:min-h-0">
          <InputPanel
            pageCount={pageCount}
            onPageCountChange={setPageCount}
            onGenerate={handleGenerate}
            onGenerateTemplateOnly={handleGenerateTemplateOnly}
            generating={generating}
          />
        </div>
        <div className="flex min-h-[min(480px,60vh)] min-w-0 flex-col xl:h-full xl:min-h-0">
          <AgentPanel
            messages={messages}
            onSend={handleSend}
            resultCards={resultCards}
            timeline={timeline}
            runtimeLogs={runtimeLogs}
            pendingConfirmation={pendingConfirmation}
            onApprove={(feedback) => handleStageAction("approve", feedback)}
            onRevise={(feedback) => handleStageAction("revise", feedback)}
            layoutOverrides={layoutOverrides}
            onCycleLayout={handleCycleLayout}
            outlineOverrides={outlineOverrides}
            onOutlineOverrideChange={(itemId, value) =>
              setOutlineOverrides((prev) => ({ ...prev, [itemId]: value }))
            }
            titleOverride={titleOverride}
            onTitleOverrideChange={setTitleOverride}
            onDisableFigure={handleDisableFigure}
            onUploadFigure={handleUploadFigure}
          />
        </div>
        <div className="min-h-[min(420px,55vh)] min-w-0 md:col-span-2 xl:col-span-1 xl:h-full xl:min-h-0">
          <PreviewPanel
            slideCount={result?.slide_count ?? pageCount}
            wordCount={result?.word_count ?? 0}
            durationMin={result?.duration_min ?? 0}
            completedSteps={completedSteps}
            totalSteps={totalSteps}
            slides={slides}
            statusText={statusText}
            htmlPreviewUrl={htmlPreviewUrl}
            htmlDownloadUrl={htmlDownloadUrl}
            taskId={activeTaskId}
            onDownloadPptx={
              downloadUrl
                ? () => {
                    window.open(downloadUrl, "_blank");
                  }
                : undefined
            }
            onDownloadHtml={
              htmlDownloadUrl
                ? () => {
                    window.open(htmlDownloadUrl, "_blank");
                  }
                : undefined
            }
          />
        </div>
      </main>
    </div>
  );
}
