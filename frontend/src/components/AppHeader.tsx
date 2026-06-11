type AppHeaderProps = {
  title: string;
  subtitle: string;
  statusLabel?: string;
  onSaveDraft?: () => void;
  onExport?: () => void;
};

export function AppHeader({
  title,
  subtitle,
  statusLabel = "当前状态: 数据分析",
  onSaveDraft,
  onExport,
}: AppHeaderProps) {
  return (
    <header className="flex shrink-0 flex-col gap-3 border-b border-slate-200/80 bg-white px-4 py-3 shadow-sm sm:flex-row sm:flex-wrap sm:items-start sm:justify-between sm:gap-4 sm:px-6 sm:py-4">
      <div className="min-w-0 flex-1">
        <h1 className="text-base font-semibold text-slate-900 sm:text-lg">{title}</h1>
        <p className="mt-0.5 line-clamp-2 text-xs text-slate-500 sm:line-clamp-none sm:text-sm">
          {subtitle}
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-2 sm:gap-3">
        <span className="max-w-full truncate rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] text-slate-600 sm:max-w-none sm:px-3 sm:text-xs">
          {statusLabel}
        </span>
        <button
          type="button"
          onClick={onSaveDraft}
          className="rounded-card border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-sm transition hover:border-slate-400 hover:bg-slate-50 sm:px-4 sm:py-2 sm:text-sm"
        >
          保存草稿
        </button>
        <button
          type="button"
          onClick={onExport}
          className="rounded-card bg-primary px-3 py-1.5 text-xs font-medium text-white shadow-sm transition hover:bg-primary-hover sm:px-4 sm:py-2 sm:text-sm"
        >
          导出 PPT
        </button>
      </div>
    </header>
  );
}
