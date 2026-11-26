// Server-Sent Events over POST (EventSource cannot send a body or auth header).
import axios from "axios";
import { API_URL, tokens } from "@/lib/api";

export type StreamEvent =
  | { type: "session"; session_id: string }
  | { type: "status"; message: string }
  | { type: "tool"; id: string; name: string; args: Record<string, any>; status: "running" | "done"; summary?: string; by_model?: boolean }
  | { type: "token"; text: string }
  | { type: "done"; [key: string]: any }
  | { type: "error"; message: string };

async function refreshToken(): Promise<boolean> {
  const refresh = tokens.refresh;
  if (!refresh) return false;
  try {
    const { data } = await axios.post(`${API_URL}/api/v1/auth/refresh`, { refresh_token: refresh });
    tokens.set(data.access_token, data.refresh_token);
    return true;
  } catch {
    return false;
  }
}

/** POST to a streaming endpoint and call `onEvent` for every SSE event. Resolves when the stream ends. */
export async function streamSSE(path: string, body: unknown, onEvent: (e: StreamEvent) => void, signal?: AbortSignal): Promise<void> {
  const send = () =>
    fetch(`${API_URL}/api/v1${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream", Authorization: `Bearer ${tokens.access ?? ""}` },
      body: JSON.stringify(body),
      signal,
    });

  let res = await send();
  if (res.status === 401 && (await refreshToken())) res = await send();
  if (res.status === 401) {
    tokens.clear();
    window.location.href = `/login?next=${encodeURIComponent(window.location.pathname)}`;
    return;
  }
  if (!res.ok || !res.body) {
    let detail = `Request failed (${res.status})`;
    try {
      const j = await res.json();
      if (typeof j.detail === "string") detail = j.detail;
    } catch {
      /* not JSON */
    }
    throw new Error(detail);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buffer.indexOf("\n\n")) >= 0) {
      const raw = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      const line = raw.split("\n").find((l) => l.startsWith("data:"));
      if (!line) continue;
      try {
        onEvent(JSON.parse(line.slice(5)));
      } catch {
        /* ignore malformed event */
      }
    }
  }
}

export const TOOL_LABELS: Record<string, string> = {
  get_stock_snapshot: "Fetching quote & fundamentals",
  get_technical_analysis: "Computing technical indicators",
  get_news_sentiment: "Analysing news sentiment",
  get_ml_forecast: "Loading ML forecasts",
  get_user_portfolio: "Analysing your portfolio",
  get_market_overview: "Checking the market",
  compare_stocks: "Comparing stocks",
  search_financial_knowledge: "Searching the knowledge base",
};

export function providerLabel(p?: string | null): string {
  if (!p || p === "offline") return "Offline analyst";
  const [name, ...rest] = p.split(":");
  const model = rest.join(":");
  const nice: Record<string, string> = { ollama: "Local", gemini: "Gemini", groq: "Groq", openai: "OpenAI" };
  return `${nice[name] ?? name} · ${model}`;
}
