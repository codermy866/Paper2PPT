import { Outlet } from "react-router-dom";
import { Sidebar } from "@/components/Sidebar";

export function AppShell() {
  return (
    <div className="flex min-h-[100dvh] flex-1 flex-col md:min-h-0 md:h-screen md:flex-row">
      <Sidebar />
      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <Outlet />
      </div>
    </div>
  );
}
