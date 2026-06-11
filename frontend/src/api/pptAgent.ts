import type { GeneratePayload } from "@/components/workspace/InputPanel";

export type TaskResult = {
  title: string;
  abstract: string;
  slides: { id: string; title: string; accent: string }[];
  slide_count: number;
  word_count: number;
  duration_min: number;
  result_cards: { id: string; title: string; body: string }[];
  download_url: string;
  html_preview_url: string;
  html_download_url: string;
  applied_config?: {
    input_mode: string;
    page_count: number;
    template_id: string;
    style_id?: string;
    instruction: string;
    llm_provider?: string;
  };
};

export type TaskLog = {
  level: string;
  message: string;
  created_at: string;
};

export type LlmSettings = {
  provider: "dashscope" | "openai";
  base_url: string;
  model: string;
  enable_thinking: boolean;
  api_key?: string;
  api_key_set?: boolean;
  api_key_mask?: string;
  settings_path?: string;
};

export type TimelineEntry = {
  id: string;
  stage_id: string;
  title: string;
  body: string;
  status: string;
  created_at: string;
};

export type PendingConfirmation = {
  stage_id: string;
  title: string;
  body: string;
  items: {
    id: string;
    title: string;
    body: string;
    figure_url?: string;
    figure_caption?: string;
  }[];
};

export type TaskStatus = {
  task_id: string;
  status: "queued" | "running" | "waiting_confirmation" | "succeeded" | "failed";
  message: string;
  error?: string | null;
  completed_steps: number;
  total_steps: number;
  result?: TaskResult | null;
  timeline?: TimelineEntry[];
  pending_confirmation?: PendingConfirmation | null;
  current_stage?: string | null;
};

export async function createTask(payload: GeneratePayload, instruction: string): Promise<string> {
  const formData = new FormData();
  formData.append("input_mode", payload.inputMode);
  formData.append("page_count", String(payload.pageCount));
  formData.append("template_id", payload.templateId);
  formData.append("style_id", payload.styleId);
  formData.append("instruction", instruction);
  if (payload.pastedText) {
    formData.append("pasted_text", payload.pastedText);
  }
  if (payload.file) {
    formData.append("file", payload.file);
  }
  payload.supplementalImages?.forEach((image) => {
    formData.append("supplemental_figures", image.file);
  });
  if (payload.supplementalImages?.length) {
    formData.append(
      "supplemental_figure_meta",
      JSON.stringify(
        payload.supplementalImages.map((image) => ({
          kind: image.kind,
          description: image.description,
          filename: image.file.name,
        }))
      )
    );
  }

  const resp = await fetch("/api/tasks", {
    method: "POST",
    body: formData,
  });
  if (!resp.ok) {
    if (resp.status === 413) {
      throw new Error("上传文件过大（超过 50MB），请压缩模板后重试");
    }
    if (resp.status === 502 || resp.status === 503) {
      throw new Error(
        "无法连接后端 API（502/503）。请确认后端已运行在 127.0.0.1:8001，并在 frontend 目录重启 Docker 前端。"
      );
    }
    if (resp.status >= 500) {
      throw new Error("后端处理出错，请查看 8001 端口的 uvicorn 运行日志，或重启后端后重试。");
    }
    const text = await resp.text();
    try {
      const parsed = JSON.parse(text) as { detail?: string };
      throw new Error(parsed.detail || "创建任务失败");
    } catch {
      throw new Error(text || "创建任务失败");
    }
  }
  const data = (await resp.json()) as { task_id: string };
  return data.task_id;
}

export async function getTaskStatus(taskId: string): Promise<TaskStatus> {
  const resp = await fetch(`/api/tasks/${taskId}`);
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(text || "获取任务状态失败");
  }
  return (await resp.json()) as TaskStatus;
}

export async function getLlmSettings(): Promise<LlmSettings> {
  const resp = await fetch("/api/settings/llm");
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(text || "读取 API 设置失败");
  }
  return (await resp.json()) as LlmSettings;
}

export async function saveLlmSettings(settings: LlmSettings): Promise<LlmSettings> {
  const resp = await fetch("/api/settings/llm", {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(settings),
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(text || "保存 API 设置失败");
  }
  return (await resp.json()) as LlmSettings;
}

export type TaskVersion = {
  version_no: number;
  label: string;
  summary: string;
  created_at: string;
};

export async function getTaskVersions(taskId: string): Promise<TaskVersion[]> {
  const resp = await fetch(`/api/tasks/${taskId}/versions`);
  if (!resp.ok) {
    return [];
  }
  const data = (await resp.json()) as { versions: TaskVersion[] };
  return data.versions ?? [];
}

export async function getTaskLogs(taskId: string): Promise<TaskLog[]> {
  const resp = await fetch(`/api/tasks/${taskId}/logs`);
  if (!resp.ok) {
    return [];
  }
  const data = (await resp.json()) as { logs: TaskLog[] };
  return data.logs ?? [];
}

export async function restoreTaskVersion(taskId: string, versionNo: number): Promise<TaskResult> {
  const resp = await fetch(`/api/tasks/${taskId}/versions/${versionNo}/restore`, {
    method: "POST",
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(text || "恢复版本失败");
  }
  const data = (await resp.json()) as { result: TaskResult };
  return data.result;
}

export async function confirmTaskStage(
  taskId: string,
  action: "approve" | "revise",
  feedback: string,
  layoutOverrides: Record<string, string> = {},
  outlineOverrides: Record<string, string> = {},
  titleOverride = ""
): Promise<void> {
  const resp = await fetch(`/api/tasks/${taskId}/confirm`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      action,
      feedback,
      layout_overrides: layoutOverrides,
      outline_overrides: outlineOverrides,
      title_override: titleOverride,
    }),
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(text || "阶段确认失败");
  }
}

export async function uploadTaskFigure(taskId: string, itemId: string, file: File): Promise<void> {
  const formData = new FormData();
  formData.append("file", file);
  const resp = await fetch(`/api/tasks/${taskId}/figures/${itemId}/upload`, {
    method: "POST",
    body: formData,
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(text || "上传替换图片失败");
  }
}
