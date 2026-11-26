"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, Check, Cpu, ExternalLink, Loader2, MessageSquarePlus, Send, Sparkles, Square, Trash2, User, Wrench } from "lucide-react";
import { toast } from "sonner";
import { aiApi, apiError } from "@/lib/api";
import { providerLabel, streamSSE, TOOL_LABELS } from "@/lib/sse";
import { cn, timeAgo } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Markdown } from "@/components/common/Markdown";
import { SafeBoundary } from "@/components/common/SafeBoundary";

interface Step {
  id: string;
  name: string;
  args: Record<string, any>;
  status: "running" | "done";
  summary?: string;
  by_model?: boolean;
}

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  steps?: Step[];
  sources?: any[];
  provider?: string;
  suggestions?: string[];
  streaming?: boolean;
  status?: string | null;
}

const STARTERS = [
  "How is NVDA doing today?",
  "Compare AAPL vs MSFT",
  "Analyse the risk of my portfolio",
  "What do the technicals say about TSLA?",
  "How is the market today?",
  "Explain the Sharpe ratio simply",
];

const asText = (v: unknown) => (typeof v === "string" ? v : v == null ? "" : String(v));
const asArray = <T,>(v: unknown): T[] => (Array.isArray(v) ? (v as T[]) : []);

/** Saved chats store tool calls as strings like "get_stock_snapshot(NVDA)". */
function stepsFromSaved(id: string, toolCalls: unknown): Step[] {
  return asArray<unknown>(toolCalls)
    .filter((t): t is string => typeof t === "string")
    .map((t, i) => ({ id: `${id}-${i}`, name: t.split("(")[0], args: {}, status: "done" as const, summary: t.match(/\((.*)\)/)?.[1] || undefined }));
}

function stepLabel(s: Step) {
  const base = TOOL_LABELS[s.name] ?? s.name;
  const target = s.args?.symbol ?? (Array.isArray(s.args?.symbols) ? s.args.symbols.join(", ") : null);
  return target ? `${base} · ${target}` : base;
}

function AgentSteps({ steps, active }: { steps: Step[]; active: boolean }) {
  const [open, setOpen] = useState(true);
  useEffect(() => { if (!active) setOpen(false); }, [active]);
  if (!steps.length) return null;
  const done = steps.filter((s) => s.status === "done").length;
  return (
    <div className="mb-3 rounded-lg border border-border/40 bg-background/40 text-xs">
      <button onClick={() => setOpen((o) => !o)} className="flex w-full items-center gap-2 px-3 py-2 text-muted-foreground">
        <Wrench className="h-3 w-3" />
        <span>{active ? "Working" : "Used"} {steps.length} tool{steps.length > 1 && "s"}{active && ` · ${done}/${steps.length} done`}</span>
        <span className="ml-auto text-[10px]">{open ? "hide" : "show"}</span>
      </button>
      {open && (
        <ol className="space-y-1 border-t border-border/30 px-3 py-2">
          {steps.map((s) => (
            <li key={s.id} className="flex items-start gap-2">
              {s.status === "running" ? <Loader2 className="mt-0.5 h-3 w-3 shrink-0 animate-spin text-primary" /> : <Check className="mt-0.5 h-3 w-3 shrink-0 text-profit" />}
              <span className="min-w-0">
                <span className="text-foreground">{stepLabel(s)}</span>
                {s.by_model && <span className="ml-1.5 rounded bg-primary/15 px-1 py-px text-[10px] text-primary">model&apos;s choice</span>}
                {s.summary && <span className="ml-1.5 text-muted-foreground">→ {s.summary}</span>}
              </span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

function AssistantInner() {
  const qc = useQueryClient();
  const params = useSearchParams();
  const [messages, setMessages] = useState<Message[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const autoSent = useRef(false);

  const { data: sessions } = useQuery({ queryKey: ["chat-sessions"], queryFn: () => aiApi.getSessions().then((r) => r.data) });
  const { data: ai } = useQuery({ queryKey: ["ai-status"], queryFn: () => aiApi.status().then((r) => r.data), refetchInterval: 30_000 });

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  const patchLast = (fn: (m: Message) => Message) =>
    setMessages((ms) => (ms.length ? [...ms.slice(0, -1), fn(ms[ms.length - 1])] : ms));

  const send = async (text: string) => {
    const message = text.trim();
    if (!message || busy) return;
    setInput("");
    setBusy(true);
    setMessages((ms) => [
      ...ms,
      { id: `u-${Date.now()}`, role: "user", content: message },
      { id: `a-${Date.now()}`, role: "assistant", content: "", steps: [], streaming: true, status: "Starting" },
    ]);
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    try {
      await streamSSE("/ai/chat/stream", { message, session_id: sessionId || undefined }, (e) => {
        switch (e.type) {
          case "session":
            setSessionId(e.session_id);
            break;
          case "status":
            patchLast((m) => ({ ...m, status: e.message }));
            break;
          case "tool":
            patchLast((m) => {
              const steps = [...(m.steps ?? [])];
              const i = steps.findIndex((s) => s.id === e.id);
              const step: Step = { id: asText(e.id), name: asText(e.name), args: e.args && typeof e.args === "object" ? e.args : {}, status: e.status === "done" ? "done" : "running", summary: e.summary ? asText(e.summary) : undefined, by_model: !!e.by_model };
              if (i >= 0) steps[i] = step; else steps.push(step);
              return { ...m, steps };
            });
            break;
          case "token":
            patchLast((m) => ({ ...m, content: m.content + asText(e.text), status: null }));
            break;
          case "done":
            patchLast((m) => ({
              ...m,
              id: asText(e.message_id) || m.id,
              content: asText(e.content) || m.content,
              sources: asArray(e.sources),
              provider: asText(e.llm_provider),
              suggestions: asArray<string>(e.suggestions).filter((x) => typeof x === "string"),
              streaming: false,
              status: null,
            }));
            qc.invalidateQueries({ queryKey: ["chat-sessions"] });
            break;
          case "error":
            toast.error(asText(e.message) || "The assistant hit an error");
            break;
        }
      }, ctrl.signal);
    } catch (err: any) {
      if (err?.name === "AbortError") patchLast((m) => ({ ...m, content: m.content + (m.content ? "\n\n_(stopped)_" : "_Stopped._") }));
      else toast.error(err?.message ?? "The assistant could not answer");
    } finally {
      patchLast((m) => ({ ...m, streaming: false, status: null }));
      setBusy(false);
    }
  };

  useEffect(() => {
    const q = params.get("q");
    if (q && !autoSent.current) {
      autoSent.current = true;
      send(q);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params]);

  const openSession = async (id: string) => {
    if (busy) return;
    try {
      const { data } = await aiApi.getSession(id);
      setSessionId(id);
      setMessages(asArray<any>(data).map((m, i) => ({
        id: asText(m?.id) || `saved-${i}`,
        role: m?.role === "user" ? "user" : "assistant",
        content: asText(m?.content),
        sources: asArray(m?.sources),
        steps: stepsFromSaved(asText(m?.id) || `saved-${i}`, m?.tool_calls),
      })));
    } catch (e) {
      toast.error(apiError(e));
    }
  };

  const deleteSession = async (id: string) => {
    await aiApi.deleteSession(id);
    if (id === sessionId) newChat();
    qc.invalidateQueries({ queryKey: ["chat-sessions"] });
  };

  const newChat = () => {
    abortRef.current?.abort();
    setSessionId(null);
    setMessages([]);
  };

  return (
    <div className="flex h-[calc(100vh-8.5rem)] gap-4">
      <aside className="hidden w-60 shrink-0 flex-col rounded-xl border border-border/40 bg-card lg:flex">
        <div className="p-3">
          <Button onClick={newChat} variant="outline" size="sm" className="w-full"><MessageSquarePlus className="mr-1.5 h-4 w-4" /> New chat</Button>
        </div>
        <div className="flex-1 space-y-0.5 overflow-y-auto px-2 pb-2">
          {(sessions ?? []).map((s: any) => (
            <div key={s.id} className={cn("group flex items-center gap-1 rounded-md px-2 py-2 text-xs hover:bg-accent", s.id === sessionId && "bg-accent")}>
              <button onClick={() => openSession(s.id)} className="min-w-0 flex-1 text-left">
                <p className="truncate">{asText(s.title) || "Untitled chat"}</p>
                <p className="text-[10px] text-muted-foreground">{timeAgo(s.updated_at)}</p>
              </button>
              <button onClick={() => deleteSession(s.id)} className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive" aria-label="Delete chat"><Trash2 className="h-3 w-3" /></button>
            </div>
          ))}
          {sessions?.length === 0 && <p className="px-2 py-4 text-center text-xs text-muted-foreground">No conversations yet</p>}
        </div>
        {ai && (
          <div className="border-t border-border/40 p-3 text-[11px] text-muted-foreground">
            <p className="flex items-center gap-1.5 font-medium text-foreground"><Cpu className="h-3 w-3" /> {providerLabel(ai.active)}</p>
            <p className="mt-0.5">{ai.mode === "llm" ? (ai.is_local ? "Running locally via Ollama" : "Cloud LLM") : "No LLM available"}</p>
            <Link href="/settings" className="mt-1 inline-block text-primary hover:underline">AI settings</Link>
          </div>
        )}
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div>
            <h1 className="flex items-center gap-2 text-xl font-bold tracking-tight"><Sparkles className="h-5 w-5 text-primary" /> AI Research Assistant</h1>
            <p className="text-xs text-muted-foreground">A tool-using AI agent: it fetches verified market data, news sentiment, forecasts and your portfolio, then reasons over them.</p>
          </div>
          {ai && (
            <span className={cn("shrink-0 rounded-full border px-2.5 py-1 text-[11px]", ai.mode === "llm" ? "border-primary/40 text-primary" : "border-border text-muted-foreground")}>
              {providerLabel(ai.active)}
            </span>
          )}
        </div>

        <div className="min-h-0 flex-1 space-y-5 overflow-y-auto rounded-xl border border-border/40 bg-card p-4">
          {messages.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center gap-6">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10"><Bot className="h-7 w-7 text-primary" /></div>
              <div className="max-w-md text-center">
                <h3 className="mb-1 font-semibold">Ask about stocks, markets, your portfolio or financial concepts</h3>
                <p className="text-sm text-muted-foreground">Watch the agent call its tools live. Every number in the answer comes from those tools — never from the model&apos;s memory.</p>
              </div>
              <div className="grid w-full max-w-xl grid-cols-1 gap-2 md:grid-cols-2">
                {STARTERS.map((q) => (
                  <button key={q} onClick={() => send(q)} className="rounded-lg border border-border/40 p-3 text-left text-xs text-muted-foreground hover:border-primary/40 hover:bg-primary/5 hover:text-foreground">{q}</button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((msg, idx) => (
              <SafeBoundary key={msg.id} fallback={<pre className="whitespace-pre-wrap rounded-lg bg-muted/40 p-3 text-xs">{asText(msg.content) || "This message could not be displayed."}</pre>}>
              <div className={cn("flex gap-3", msg.role === "user" ? "justify-end" : "justify-start")}>
                {msg.role === "assistant" && <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-primary/10"><Bot className="h-4 w-4 text-primary" /></div>}
                <div className={cn("max-w-[85%] rounded-xl px-4 py-3", msg.role === "user" ? "bg-primary text-sm text-primary-foreground" : "min-w-[260px] bg-muted/40")}>
                  {msg.role === "user" ? (
                    <p className="whitespace-pre-wrap text-sm">{msg.content}</p>
                  ) : (
                    <>
                      <AgentSteps steps={msg.steps ?? []} active={!!msg.streaming} />
                      {msg.content ? (
                        <div className={cn(msg.streaming && "after:ml-0.5 after:inline-block after:h-3.5 after:w-1.5 after:animate-pulse after:bg-primary after:align-middle")}>
                          <Markdown>{msg.content}</Markdown>
                        </div>
                      ) : msg.streaming ? (
                        <p className="flex items-center gap-2 text-xs text-muted-foreground"><Loader2 className="h-3.5 w-3.5 animate-spin" /> {msg.status ?? "Thinking"}…</p>
                      ) : null}
                      {!msg.streaming && msg.provider && <p className="mt-2 text-[10px] text-muted-foreground">✨ {providerLabel(msg.provider)}</p>}
                      {asArray(msg.sources).length > 0 && (
                        <div className="mt-3 space-y-1 border-t border-border/30 pt-2">
                          <p className="text-[11px] font-medium text-muted-foreground">Sources</p>
                          {asArray<any>(msg.sources).filter((s) => s && typeof s === "object").map((s: any, i: number) => (
                            <div key={i} className="flex items-center gap-1.5 text-xs text-muted-foreground">
                              <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-profit" />
                              {typeof s.url === "string" && s.url ? (
                                s.url.startsWith("/") ? <Link href={s.url} className="truncate hover:text-primary">{s.title}</Link>
                                  : <a href={s.url} target="_blank" rel="noreferrer" className="flex items-center gap-1 truncate hover:text-primary">{s.title} <ExternalLink className="h-3 w-3 shrink-0" /></a>
                              ) : <span className="truncate">{s.title}</span>}
                            </div>
                          ))}
                        </div>
                      )}
                      {msg.suggestions && idx === messages.length - 1 && !busy && (
                        <div className="mt-3 flex flex-wrap gap-1.5">
                          {msg.suggestions.map((s) => (
                            <button key={s} onClick={() => send(s)} className="rounded-full border border-border/50 px-2.5 py-1 text-[11px] text-muted-foreground hover:border-primary/40 hover:text-foreground">{s}</button>
                          ))}
                        </div>
                      )}
                    </>
                  )}
                </div>
                {msg.role === "user" && <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-muted"><User className="h-4 w-4 text-muted-foreground" /></div>}
              </div>
              </SafeBoundary>
            ))
          )}
          <div ref={endRef} />
        </div>

        <form onSubmit={(e) => { e.preventDefault(); send(input); }} className="mt-3 flex gap-2">
          <input value={input} onChange={(e) => setInput(e.target.value)} disabled={busy} placeholder="Ask about a stock, the market, your portfolio or a concept…"
            className="flex h-10 flex-1 rounded-md border border-input bg-background/50 px-3 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring" />
          {busy ? (
            <Button type="button" size="icon" variant="outline" className="h-10 w-10" onClick={() => abortRef.current?.abort()} title="Stop generating"><Square className="h-4 w-4" /></Button>
          ) : (
            <Button type="submit" size="icon" className="h-10 w-10" disabled={!input.trim()}><Send className="h-4 w-4" /></Button>
          )}
        </form>
        <p className="mt-1.5 text-[11px] text-muted-foreground">AI answers can be wrong. Verify important information independently — this is not financial advice.</p>
      </div>
    </div>
  );
}

export default function AssistantPage() {
  return <Suspense><AssistantInner /></Suspense>;
}
