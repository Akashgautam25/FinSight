"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, RefreshCw, RotateCcw } from "lucide-react";
import { isNewBuildAvailable, isStaleBuildError, reloadOnceForStaleBuild, reportClientError } from "@/lib/errors";

/** Friendly replacement for Next.js's "Application error" screen. */
export function ErrorFallback({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  const [stale, setStale] = useState(isStaleBuildError(error));
  const [reloading, setReloading] = useState(false);
  const [details, setDetails] = useState(false);

  useEffect(() => {
    console.error("FinSight UI error:", error);
    let cancelled = false;
    (async () => {
      // Errors right after a rebuild usually come from mixing two builds' JavaScript.
      const outdated = isStaleBuildError(error) || (await isNewBuildAvailable());
      if (cancelled) return;
      if (outdated) {
        setStale(true);
        if (reloadOnceForStaleBuild()) setReloading(true);
      } else {
        reportClientError(error, "error-boundary");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [error]);

  return (
    <div className="flex min-h-[60vh] items-center justify-center p-6">
      <div className="max-w-lg rounded-xl border border-border/50 bg-card p-6 text-center">
        <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-xl bg-amber-500/10">
          <AlertTriangle className="h-5 w-5 text-amber-500" />
        </div>
        <h2 className="font-semibold">{stale ? "FinSight was updated" : "Something went wrong on this page"}</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {reloading
            ? "Loading the latest version…"
            : stale
              ? "This tab is running an older version of the app. Reload to get the latest one."
              : "The rest of the app still works. You can retry this page or reload. The error has been logged for diagnosis."}
        </p>
        {!stale && error?.message && (
          <p className="mt-3 break-words rounded-md bg-muted/40 p-2 text-left font-mono text-[11px] text-muted-foreground">{error.message}</p>
        )}
        {!stale && error?.stack && (
          <div className="mt-2 text-left">
            <button onClick={() => setDetails((d) => !d)} className="text-[11px] text-primary hover:underline">{details ? "Hide" : "Show"} technical details</button>
            {details && <pre className="mt-1 max-h-48 overflow-auto rounded-md bg-muted/40 p-2 text-[10px] text-muted-foreground">{error.stack}</pre>}
          </div>
        )}
        <div className="mt-4 flex justify-center gap-2">
          {!stale && (
            <button onClick={reset} className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm hover:bg-accent">
              <RotateCcw className="h-3.5 w-3.5" /> Try again
            </button>
          )}
          <button onClick={() => window.location.reload()} className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground hover:bg-primary/90">
            <RefreshCw className="h-3.5 w-3.5" /> Reload
          </button>
        </div>
      </div>
    </div>
  );
}
