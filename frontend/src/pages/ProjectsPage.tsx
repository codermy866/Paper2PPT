import { Plus, Presentation } from "lucide-react";
import { AppHeader } from "@/components/AppHeader";

const mockProjects = [
  {
    id: "1",
    name: "扩散模型可解释性 · 组会",
    updated: "今天 14:20",
    slides: 10,
  },
  {
    id: "2",
    name: "CVPR 投稿版本摘要汇报",
    updated: "昨天",
    slides: 8,
  },
  {
    id: "3",
    name: "课题中期答辩草稿",
    updated: "4 月 10 日",
    slides: 12,
  },
];

export function ProjectsPage() {
  return (
    <div className="flex min-h-0 flex-1 flex-col bg-[#f5f6f8]">
      <AppHeader
        title="项目"
        subtitle="管理您的论文转 PPT 任务与历史版本"
        statusLabel="当前状态: 就绪"
      />
      <div className="flex flex-1 flex-col gap-4 overflow-auto p-4 sm:p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-slate-600">共 {mockProjects.length} 个项目</p>
          <button
            type="button"
            className="inline-flex items-center gap-2 rounded-card bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-hover"
          >
            <Plus className="h-4 w-4" />
            新建项目
          </button>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {mockProjects.map((p) => (
            <article
              key={p.id}
              className="flex flex-col rounded-card border border-slate-200/80 bg-white p-4 shadow-card transition hover:border-primary/30"
            >
              <div className="flex items-start gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <Presentation className="h-5 w-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <h2 className="font-semibold text-slate-900">{p.name}</h2>
                  <p className="mt-1 text-xs text-slate-500">更新于 {p.updated}</p>
                </div>
              </div>
              <div className="mt-4 flex items-center justify-between border-t border-slate-100 pt-3 text-xs text-slate-500">
                <span>{p.slides} 页</span>
                <button type="button" className="font-medium text-primary hover:underline">
                  打开
                </button>
              </div>
            </article>
          ))}
        </div>
      </div>
    </div>
  );
}
