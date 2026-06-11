import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { Download, Maximize2, X } from "lucide-react";
import { getTaskVersions, restoreTaskVersion, type TaskVersion } from "@/api/pptAgent";

export type SlideThumb = { id: string; title: string; accent: string };

type PreviewPanelProps = {
  slideCount: number;
  wordCount: number;
  durationMin: number;
  completedSteps: number;
  totalSteps: number;
  slides: SlideThumb[];
  htmlPreviewUrl?: string | null;
  htmlDownloadUrl?: string | null;
  taskId?: string | null;
  onDownloadPptx?: () => void;
  onDownloadHtml?: () => void;
  statusText?: string;
};

export function PreviewPanel({
  slideCount,
  wordCount,
  durationMin,
  completedSteps,
  totalSteps,
  slides,
  htmlPreviewUrl = null,
  taskId = null,
  onDownloadPptx,
  onDownloadHtml,
  statusText = "HTML PPT 预览生成中…",
}: PreviewPanelProps) {
  const [rightTab, setRightTab] = useState<"preview" | "history">("preview");
  const [fallbackFullscreenOpen, setFallbackFullscreenOpen] = useState(false);
  const [fsSlideIndex, setFsSlideIndex] = useState(0);
  const [versions, setVersions] = useState<TaskVersion[]>([]);
  const pctDone = totalSteps > 0 ? Math.round((completedSteps / totalSteps) * 100) : 0;
  const pctActive = 100 - pctDone;

  useEffect(() => {
    if (!taskId || rightTab !== "history") return;
    void getTaskVersions(taskId).then(setVersions);
  }, [taskId, rightTab, completedSteps]);

  useEffect(() => {
    if (!fallbackFullscreenOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setFallbackFullscreenOpen(false);
        return;
      }
      if (slides.length === 0) return;
      if (e.key === "ArrowLeft") {
        e.preventDefault();
        setFsSlideIndex((i) => Math.max(0, i - 1));
      }
      if (e.key === "ArrowRight") {
        e.preventDefault();
        setFsSlideIndex((i) => Math.min(slides.length - 1, i + 1));
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [fallbackFullscreenOpen, slides.length]);

  useEffect(() => {
    if (!fallbackFullscreenOpen) return;
    setFsSlideIndex((i) => (slides.length > 0 ? Math.min(i, slides.length - 1) : 0));
  }, [fallbackFullscreenOpen, slides]);

  const fsSlide = slides[fsSlideIndex];
  const fallbackFullscreenModal =
    fallbackFullscreenOpen &&
    createPortal(
      <div className="fixed inset-0 z-[300] flex flex-col bg-slate-950 text-slate-100">
        <header className="flex items-center justify-between border-b border-white/10 px-4 py-3 sm:px-6">
          <div className="min-w-0">
            <h2 className="truncate text-sm font-semibold text-white sm:text-base">PPT 全屏预览</h2>
            <p className="truncate text-[11px] text-slate-400 sm:text-xs">
              {slides.length > 0
                ? `第 ${fsSlideIndex + 1} / ${slides.length} 页 · ← → 切换 · Esc 关闭`
                : `${statusText} · Esc 关闭`}
            </p>
          </div>
          <button
            type="button"
            onClick={() => setFallbackFullscreenOpen(false)}
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-white/20 text-white hover:bg-white/10"
            aria-label="关闭预览"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-hidden p-4 sm:p-6">
          <div className="flex min-h-0 flex-1 items-center justify-center">
            <div className="flex h-full w-full max-h-[min(72vh,720px)] max-w-6xl flex-col overflow-hidden rounded-xl border border-white/10 bg-slate-900 shadow-2xl">
              <div
                className="flex min-h-0 flex-1 flex-col items-center justify-center px-6 py-8 text-center"
                style={
                  fsSlide
                    ? { background: `linear-gradient(145deg, ${fsSlide.accent}33, #0f172a 55%, #1e293b)` }
                    : undefined
                }
              >
                {fsSlide ? (
                  <>
                    <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400">
                      幻灯片 {fsSlideIndex + 1}
                    </p>
                    <h3 className="mt-3 line-clamp-4 text-xl font-semibold leading-snug text-white sm:text-2xl">
                      {fsSlide.title}
                    </h3>
                    <p className="mt-6 max-w-lg text-sm text-slate-400">
                      当前为结构预览；内网/本机环境下会自动回退到这个预览模式。
                    </p>
                  </>
                ) : (
                  <p className="max-w-md text-sm text-slate-400">{statusText}</p>
                )}
              </div>
            </div>
          </div>

          {slides.length > 0 && (
            <div className="shrink-0">
              <p className="mb-2 text-[11px] font-medium text-slate-500">缩略图导航</p>
              <div className="flex gap-2 overflow-x-auto pb-1 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
                {slides.map((s, idx) => (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => setFsSlideIndex(idx)}
                    className={
                      idx === fsSlideIndex
                        ? "w-28 shrink-0 overflow-hidden rounded-lg border-2 border-primary ring-2 ring-primary/30"
                        : "w-28 shrink-0 overflow-hidden rounded-lg border border-white/10 opacity-80 hover:opacity-100"
                    }
                  >
                    <div
                      className="aspect-[16/10] w-full"
                      style={{ background: `linear-gradient(135deg, ${s.accent}44, #1e293b)` }}
                    />
                    <div className="truncate bg-slate-900 px-1.5 py-1 text-left text-[10px] text-slate-300">
                      {s.title}
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>,
      document.body
    );

  return (
    <section className="flex h-full min-h-0 flex-col rounded-card border border-slate-200/80 bg-white shadow-card">
      <div className="flex border-b border-slate-100 px-2">
        {(
          [
            ["preview", "预览"],
            ["history", "版本历史"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            onClick={() => setRightTab(id)}
            className={
              rightTab === id
                ? "border-b-2 border-primary px-4 py-3 text-sm font-semibold text-primary"
                : "border-b-2 border-transparent px-4 py-3 text-sm font-medium text-slate-500 hover:text-slate-800"
            }
          >
            {label}
          </button>
        ))}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        {rightTab === "history" ? (
          versions.length > 0 ? (
            <ul className="space-y-2 text-sm text-slate-600">
              {versions.map((v) => (
                <li key={v.version_no} className="flex items-center justify-between gap-2 rounded-card border border-slate-100 bg-slate-50 px-3 py-2">
                  <span>
                    {v.label} · {new Date(v.created_at).toLocaleString()} · {v.summary}
                  </span>
                  {taskId && (
                    <button
                      type="button"
                      onClick={() => {
                        void restoreTaskVersion(taskId, v.version_no).then(() => {
                          window.location.reload();
                        });
                      }}
                      className="shrink-0 rounded-lg border border-slate-300 bg-white px-2 py-1 text-[11px] font-medium text-slate-700 hover:bg-slate-100"
                    >
                      恢复
                    </button>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-slate-500">暂无版本记录，完成一次生成后将自动保存。</p>
          )
        ) : (
          <>
            {htmlPreviewUrl ? (
              <div className="overflow-hidden rounded-card border border-slate-200 bg-slate-50">
                <iframe
                  src={htmlPreviewUrl}
                  title="HTML PPT 预览"
                  className="aspect-[16/10] w-full bg-white"
                />
              </div>
            ) : (
              <div className="flex aspect-[16/10] items-center justify-center rounded-card border border-dashed border-slate-300 bg-slate-50 text-sm text-slate-500">
                {statusText}
              </div>
            )}
            <div className="mt-3 flex gap-2">
              <button
                type="button"
                onClick={
                  htmlPreviewUrl
                    ? () => window.open(htmlPreviewUrl, "_blank", "noopener,noreferrer")
                    : () => {
                        setFsSlideIndex(0);
                        setFallbackFullscreenOpen(true);
                      }
                }
                title={htmlPreviewUrl ? "在新标签页打开当前 HTML PPT。" : "打开结构化全屏预览。"}
                className="flex flex-1 items-center justify-center gap-2 rounded-card border border-slate-300 bg-white py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                <Maximize2 className="h-4 w-4" />
                全屏预览
              </button>
            </div>
            <div className="mt-2 grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={onDownloadPptx}
                disabled={!onDownloadPptx}
                className="flex items-center justify-center gap-2 rounded-card bg-primary py-2 text-sm font-medium text-white hover:bg-primary-hover disabled:cursor-not-allowed disabled:opacity-60"
              >
                <Download className="h-4 w-4" />
                下载 PPTX
              </button>
              <button
                type="button"
                onClick={onDownloadHtml}
                disabled={!onDownloadHtml}
                className="flex items-center justify-center gap-2 rounded-card border border-slate-300 bg-white py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <Download className="h-4 w-4" />
                下载 HTML
              </button>
            </div>
            <p className="mt-2 text-[11px] leading-snug text-slate-500">
              {htmlPreviewUrl
                ? "当前输出为 HTML PPT，可内嵌预览，也可分别下载 PPTX 与 HTML 压缩包。"
                : "若 HTML 文件尚未返回，点击「全屏预览」会使用应用内结构化预览。"}
            </p>

            <div className="mt-4 grid grid-cols-3 gap-2">
              <StatBox label="字数" value={String(wordCount)} />
              <StatBox label="时长" value={`${durationMin} min`} />
              <StatBox label="页数" value={String(slideCount)} />
            </div>

            <h3 className="mt-5 text-xs font-semibold text-slate-500">幻灯片</h3>
            <div className="mt-2 grid grid-cols-2 gap-2">
              {slides.map((s, idx) => (
                <div
                  key={s.id}
                  className="overflow-hidden rounded-card border border-slate-200 bg-slate-50"
                >
                  {htmlPreviewUrl ? (
                    <div className="aspect-[16/10] w-full overflow-hidden bg-white">
                      <iframe
                        src={`${htmlPreviewUrl}?preview=${idx + 1}`}
                        title={`${s.title} 缩略预览`}
                        className="h-[1080px] w-[1920px] origin-top-left scale-[0.1333] border-0"
                        style={{ transformOrigin: "top left" }}
                      />
                    </div>
                  ) : (
                    <div
                      className="aspect-[16/10] w-full"
                      style={{ background: `linear-gradient(135deg, ${s.accent}22, #fff)` }}
                    />
                  )}
                  <div className="truncate px-2 py-1.5 text-[11px] font-medium text-slate-700">
                    {s.title}
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      <div className="border-t border-slate-100 p-4">
        <div className="flex items-center justify-between text-xs font-medium text-slate-600">
          <span>整体进度</span>
          <span>
            {completedSteps}/{totalSteps}
          </span>
        </div>
        <div className="mt-2 flex h-2 overflow-hidden rounded-full bg-slate-200">
          <div
            className="bg-emerald-500 transition-all"
            style={{ width: `${pctDone}%` }}
          />
          <div
            className="bg-primary transition-all"
            style={{ width: `${pctActive}%` }}
          />
        </div>
        <div className="mt-2 flex gap-4 text-[11px] text-slate-500">
          <span className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-emerald-500" />
            已完成 {completedSteps} 步
          </span>
          <span className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-primary" />
            进行中 {totalSteps - completedSteps} 步
          </span>
        </div>
      </div>
      {fallbackFullscreenModal}
    </section>
  );
}

function StatBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-card border border-slate-100 bg-slate-50 px-2 py-2 text-center">
      <div className="text-lg font-semibold text-slate-900">{value}</div>
      <div className="text-[10px] text-slate-500">{label}</div>
    </div>
  );
}
