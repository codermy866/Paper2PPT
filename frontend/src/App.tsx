import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "@/layouts/AppShell";
import { WorkspacePage } from "@/pages/WorkspacePage";
import { ProjectsPage } from "@/pages/ProjectsPage";
import { SettingsPage } from "@/pages/SettingsPage";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<Navigate to="/workspace" replace />} />
        <Route path="/workspace" element={<WorkspacePage />} />
        <Route path="/projects" element={<ProjectsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/workspace" replace />} />
    </Routes>
  );
}
