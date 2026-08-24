import type {
  DashboardState,
  Metals,
  Template,
  TemplatesResponse,
} from "./types";

declare global {
  interface Window {
    __API_BASE__?: string;
  }
}

// API base resolution:
//   1. window.__API_BASE__ — set at runtime in index.html (no rebuild needed),
//      used to point the static deploy at the Cloudflare Worker.
//   2. VITE_API_BASE — baked at build time.
//   3. same-origin ("") — the sandbox preview, where FastAPI serves both.
const API_BASE: string =
  window.__API_BASE__ ??
  (import.meta.env.VITE_API_BASE as string | undefined) ??
  "";

function url(path: string): string {
  return `${API_BASE}${path}`;
}

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url(path), init);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(
      (data as { detail?: string }).detail || `Request failed (${res.status})`,
    );
  }
  return data as T;
}

export const api = {
  dashboard: () => json<DashboardState>("/api/dashboard"),

  metals: () => json<Metals>("/api/metals"),

  templates: () => json<TemplatesResponse>("/api/templates"),

  preview: (body: string) =>
    json<{ rendered?: string; unknown_variables?: string[] }>(
      "/api/templates/preview",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: "preview", body, destination: "all" }),
      },
    ),

  saveTemplate: (t: {
    id?: number | null;
    name: string;
    body: string;
    destination: string;
  }) =>
    json<{ template?: Template }>("/api/templates", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(t),
    }),

  deleteTemplate: (id: number) =>
    json<{ ok: boolean }>(`/api/templates/${id}`, { method: "DELETE" }),

  sendTemplate: (t: { name: string; body: string; destination: string }) =>
    json<{ sent: number; queued?: boolean; recipients?: number[] }>(
      "/api/templates/send",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(t),
      },
    ),

  publishBoard: () =>
    json<{ sent: number; queued?: boolean; recipients?: number[] }>(
      "/api/publish/board",
      { method: "POST" },
    ),

  sourceLink: () => json<{ enabled: boolean }>("/api/settings/source_link"),

  setSourceLink: (enabled: boolean) =>
    json<{ enabled: boolean }>("/api/settings/source_link", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled }),
    }),

  toggleSource: (username: string, active: boolean) =>
    json<{ ok: boolean }>(`/api/sources/${encodeURIComponent(username)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ active }),
    }),

  toggleTarget: (chatId: number) =>
    json<{ ok: boolean; enabled?: boolean }>(
      `/api/targets/${chatId}/toggle`,
      { method: "POST" },
    ),

  toggleSubscriber: (chatId: number) =>
    json<{ ok: boolean; subscribed?: boolean }>(
      `/api/subscribers/${chatId}/toggle`,
      { method: "POST" },
    ),
};
