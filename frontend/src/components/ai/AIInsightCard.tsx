"use client";

import { useEffect, useRef, useState } from "react";
import { Loader2, RefreshCw, Sparkles, Square } from "lucide-react";
import { cn, timeAgo } from "@/lib/utils";
import { providerLabel, streamSSE } from "@/lib/sse";
import { Markdown } from "@/components/common/Markdown";

type Kind = "stock" | "portfolio" | "market" | "predictions" | "news";

/** Streaming AI-written insight card used across the app. */
export function AIInsightCard({
  kind,
  symbol,
  title,
  description,
  autoStart = true,
  className,
}: {
  kind: Kind;
  symbol?: string;
  title: string;
  description?: string;
  autoStart?: boolean;
  className?: string;
}) {
  const [text, setText] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [meta, setMeta] = useState<{ provider?: string; cached?: boolean; generated_at?: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const generate = async (refresh = false) => {
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setText("");
    setMeta(null);
    setError(null);
    setRunning(true);
    setStatus("Starting");
    try {
      await streamSSE("/ai/insight/stream", { kind, symbol, refresh }, (e) => {
        if (e.type === "status") setStatus(e.message);
        else if (e.type === "token") { setStatus(null); setText((t) => t + e.text); }
        else if (e.type === "done") setMeta({ provider: e.provider, cached: e.cached, generated_at: e.generated_at });
        else if (e.type === "error") setError(e.message);
      }, ctrl.signal);
    } catch (err: any) {
      if (err?.name !== "AbortError") setError(err?.message ?? "Could not generate the insight");
    } finally {
      setRunning(false);
      setStatus(null);
    }
  };

  useEffect(() => {
    if (autoStart) generate();
    return () => abortRef.current?.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kind, symbol]);

  return (
    <div className={cn("relative overflow-hidden rounded-xl border border-primary/25 bg-gradient-to-br from-primary/[0.07] via-card to-card", className)}>
      <div className="flex items-start justify-between gap-3 px-5 pt-4">
        <div className="min-w-0">
          <h2 className="flex items-center gap-1.5 text-sm font-semibold">
            <Sparkles className="h-4 w-4 text-primary" /> {title}
          </h2>
          {description && <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>}
        </div>
        <div className="flex shrink-0 items-center gap-1">
          {running ? (
            <button onClick={() => abortRef.current?.abort()} className="flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground hover:bg-accent" title="Stop">
              <Square className="h-3 w-3" /> Stop
            </button>
          ) : (
            <button onClick={() => generate(true)} className="flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground hover:bg-accent" title="Regenerate">
              <RefreshCw className="h-3 w-3" /> {text ? "Regenerate" : "Generate"}
            </button>
          )}
        </div>
      </div>
      <div className="px-5 pb-4 pt-2">
        {error ? (
          <p className="text-sm text-destructive">{error}</p>
        ) : !text && running ? (
          <div className="flex items-center gap-2 py-3 text-xs text-muted-foreground">
            <Loader2 className="h-3.5 w-3.5 animate-spin" /> {status ?? "Thinking"}…
          </div>
        ) : text ? (
          <div className={cn(running && "after:ml-0.5 after:inline-block after:h-3.5 after:w-1.5 after:animate-pulse after:bg-primary after:align-middle")}>
            <Markdown>{text}</Markdown>
          </div>
        ) : (
          <p className="py-2 text-xs text-muted-foreground">Click Generate for an AI-written analysis.</p>
        )}
        {meta && (
          <p className="mt-3 text-[11px] text-muted-foreground">
            ✨ {providerLabel(meta.provider)}{meta.cached ? " · cached" : ""}{meta.generated_at ? ` · ${timeAgo(meta.generated_at)}` : ""} · AI-generated from verified data — may contain mistakes, not financial advice.
          </p>
        )}
      </div>
    </div>
  );
}
