import { HelpCircle, LayoutDashboard, FolderKanban, Settings } from "lucide-react";
import { NavLink } from "react-router-dom";

const nav = [
  { to: "/workspace", label: "工作台", icon: LayoutDashboard },
  { to: "/projects", label: "项目", icon: FolderKanban },
  { to: "/settings", label: "设置", icon: Settings },
] as const;

export function Sidebar() {
  return (
    <aside className="z-30 flex w-full shrink-0 flex-col border-b border-white/10 bg-sidebar-bg text-white md:sticky md:top-0 md:h-screen md:w-[220px] md:shrink-0 md:border-b-0 md:border-r md:border-white/10">
      <div className="flex items-center gap-2 border-b border-white/10 px-3 py-3 md:px-4 md:py-5">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-card bg-primary text-sm font-bold">
          P2
        </div>
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold leading-tight">Paper2PPT</div>
          <div className="hidden text-xs text-sidebar-muted sm:block">智能生成</div>
        </div>
      </div>

      <nav className="flex gap-1 overflow-x-auto px-2 py-2 [-ms-overflow-style:none] [scrollbar-width:none] md:flex-1 md:flex-col md:gap-1 md:overflow-y-auto md:overflow-x-hidden md:p-3 md:py-3 [&::-webkit-scrollbar]:hidden md:[&::-webkit-scrollbar]:block">
        {nav.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              [
                "flex shrink-0 items-center gap-2 rounded-card px-3 py-2.5 text-sm font-medium whitespace-nowrap transition-colors md:gap-3 md:whitespace-normal",
                isActive
                  ? "bg-sidebar-active text-white shadow-card"
                  : "text-sidebar-muted hover:bg-white/10 hover:text-white",
              ].join(" ")
            }
          >
            <Icon className="h-4 w-4 shrink-0" strokeWidth={1.75} />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="hidden border-t border-white/10 p-3 md:block">
        <a
          href="#help"
          className="flex items-center gap-2 px-3 py-2 text-xs text-sidebar-muted transition-colors hover:text-white"
        >
          <HelpCircle className="h-4 w-4 shrink-0" />
          帮助中心
        </a>
        <div className="mt-3 rounded-card bg-white/5 p-3">
          <div className="text-xs font-medium text-white">研究员</div>
          <div className="mt-0.5 truncate text-[11px] text-sidebar-muted">
            researcher@example.edu
          </div>
        </div>
      </div>
    </aside>
  );
}
