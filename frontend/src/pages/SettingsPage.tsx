import { useEffect, useState } from "react";
import { AppHeader } from "@/components/AppHeader";
import { getLlmSettings, saveLlmSettings, type LlmSettings } from "@/api/pptAgent";

const DEFAULT_SETTINGS: LlmSettings = {
  provider: "dashscope",
  base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1",
  model: "qwen3.7-max",
  enable_thinking: false,
  api_key: "",
};

export function SettingsPage() {
  const [settings, setSettings] = useState<LlmSettings>(DEFAULT_SETTINGS);
  const [apiKey, setApiKey] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    getLlmSettings()
      .then((data) => {
        if (!active) return;
        setSettings({ ...DEFAULT_SETTINGS, ...data, api_key: "" });
      })
      .catch((err: Error) => {
        if (!active) return;
        setError(err.message || "读取设置失败");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const update = <K extends keyof LlmSettings>(key: K, value: LlmSettings[K]) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
  };

  const handleProviderChange = (provider: "dashscope" | "openai") => {
    setSettings((prev) => ({
      ...prev,
      provider,
      base_url:
        provider === "dashscope"
          ? "https://dashscope.aliyuncs.com/compatible-mode/v1"
          : "https://api.openai.com/v1",
      model: provider === "dashscope" ? "qwen3.7-max" : "gpt-4o-mini",
      enable_thinking: provider === "dashscope" ? prev.enable_thinking : false,
    }));
  };

  const handleSave = async () => {
    setSaving(true);
    setMessage("");
    setError("");
    try {
      const saved = await saveLlmSettings({ ...settings, api_key: apiKey.trim() });
      setSettings({ ...DEFAULT_SETTINGS, ...saved, api_key: "" });
      setApiKey("");
      setMessage("设置已保存，后续新任务会使用这套 API 配置。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-[#f5f6f8]">
      <AppHeader
        title="设置"
        subtitle="配置论文分析与页面文案生成使用的 LLM API"
        statusLabel={settings.api_key_set ? "当前状态: API 已配置" : "当前状态: 未配置 API Key"}
      />
      <div className="mx-auto w-full max-w-2xl flex-1 space-y-6 overflow-auto p-4 sm:p-6">
        <section className="rounded-card border border-slate-200/80 bg-white p-5 shadow-card">
          <h2 className="text-sm font-semibold text-slate-900">模型与 API</h2>
          <p className="mt-1 text-xs text-slate-500">
            保存后后端会从本地运行时配置读取，不需要每次在终端 export。
          </p>

          <label className="mt-4 block text-xs font-medium text-slate-600">服务商</label>
          <select
            value={settings.provider}
            onChange={(event) => handleProviderChange(event.target.value as "dashscope" | "openai")}
            className="mt-1.5 w-full rounded-card border border-slate-200 px-3 py-2 text-sm outline-none focus:border-primary focus:ring-1 focus:ring-primary"
          >
            <option value="dashscope">阿里云百炼 / DashScope</option>
            <option value="openai">OpenAI Compatible</option>
          </select>

          <label className="mt-4 block text-xs font-medium text-slate-600">API Base URL</label>
          <input
            type="url"
            value={settings.base_url}
            onChange={(event) => update("base_url", event.target.value)}
            placeholder="https://dashscope.aliyuncs.com/compatible-mode/v1"
            className="mt-1.5 w-full rounded-card border border-slate-200 px-3 py-2 text-sm outline-none focus:border-primary focus:ring-1 focus:ring-primary"
          />

          <label className="mt-4 block text-xs font-medium text-slate-600">模型</label>
          <input
            value={settings.model}
            onChange={(event) => update("model", event.target.value)}
            placeholder="qwen3.7-max"
            className="mt-1.5 w-full rounded-card border border-slate-200 px-3 py-2 text-sm outline-none focus:border-primary focus:ring-1 focus:ring-primary"
          />

          <label className="mt-4 block text-xs font-medium text-slate-600">API Key</label>
          <input
            type="password"
            value={apiKey}
            onChange={(event) => setApiKey(event.target.value)}
            placeholder={settings.api_key_set ? `已保存 ${settings.api_key_mask || "****"}，留空则不修改` : "请输入 API Key"}
            className="mt-1.5 w-full rounded-card border border-slate-200 px-3 py-2 text-sm outline-none focus:border-primary focus:ring-1 focus:ring-primary"
          />
          <p className="mt-2 text-xs text-slate-500">
            为了安全，页面不会回显完整 API Key。留空保存会继续使用已保存的 Key。
          </p>

          {settings.provider === "dashscope" ? (
            <label className="mt-4 flex items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={settings.enable_thinking}
                onChange={(event) => update("enable_thinking", event.target.checked)}
                className="rounded border-slate-300 text-primary"
              />
              开启 Qwen thinking 模式，质量可能更高但会更慢
            </label>
          ) : null}
        </section>

        <section className="rounded-card border border-slate-200/80 bg-white p-5 shadow-card">
          <h2 className="text-sm font-semibold text-slate-900">默认导出</h2>
          <div className="mt-4 space-y-3">
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input type="checkbox" defaultChecked className="rounded border-slate-300 text-primary" />
              生成演讲者备注
            </label>
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input type="checkbox" className="rounded border-slate-300 text-primary" />
              嵌入可编辑图表占位符
            </label>
          </div>
        </section>

        {error ? <div className="rounded-card border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div> : null}
        {message ? <div className="rounded-card border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{message}</div> : null}

        <button
          type="button"
          disabled={loading || saving}
          onClick={handleSave}
          className="w-full rounded-card bg-primary py-2.5 text-sm font-semibold text-white hover:bg-primary-hover disabled:cursor-not-allowed disabled:opacity-60"
        >
          {saving ? "保存中..." : "保存设置"}
        </button>
      </div>
    </div>
  );
}
