import { API_URL } from "@/lib/api";

const CLIENT_BUILD = process.env.NEXT_PUBLIC_BUILD_ID ?? "dev";
const RELOAD_KEY = "finsight:stale-build-reload";

/** True when an error comes from a JS chunk that no longer exists — typically an open tab after the app was rebuilt. */
export function isStaleBuildError(error: unknown): boolean {
  const e = error as { name?: string; message?: string } | undefined;
  const text = `${e?.name ?? ""} ${e?.message ?? ""}`;
  return /ChunkLoadError|Loading chunk|Loading CSS chunk|Failed to fetch dynamically imported module|Importing a module script failed/i.test(text);
}

const SEEN_KEY = "finsight:reloaded-for-build";

/**
 * Has the server been rebuilt since this tab loaded its JavaScript?
 * Loop-proof: if we already reloaded once for this exact server build and the
 * mismatch persists, the ids are inconsistent and we never reload for it again.
 */
export async function isNewBuildAvailable(): Promise<boolean> {
  if (CLIENT_BUILD === "dev" || typeof window === "undefined") return false;
  try {
    const res = await fetch("/api/build-id", { cache: "no-store" });
    if (!res.ok) return false;
    const { buildId } = await res.json();
    if (!buildId || buildId === CLIENT_BUILD) return false;
    if (sessionStorage.getItem(SEEN_KEY) === buildId) return false;
    sessionStorage.setItem(SEEN_KEY, buildId);
    return true;
  } catch {
    return false;
  }
}

/** Reload once to pick up the new build (guarded so it can never loop). */
export function reloadOnceForStaleBuild(): boolean {
  if (typeof window === "undefined") return false;
  const last = Number(sessionStorage.getItem(RELOAD_KEY) || 0);
  if (Date.now() - last < 30_000) return false;
  sessionStorage.setItem(RELOAD_KEY, String(Date.now()));
  window.location.reload();
  return true;
}

/** Send a UI error to the backend log so it can be diagnosed (best effort, never throws). */
export function reportClientError(error: unknown, context: string, extra?: string) {
  try {
    const e = error as { name?: string; message?: string; stack?: string; digest?: string } | undefined;
    const body = JSON.stringify({
      context,
      message: `${e?.name ?? "Error"}: ${e?.message ?? String(error)}`.slice(0, 1000),
      stack: `${e?.stack ?? ""}${extra ? `\n--- component stack ---${extra}` : ""}`.slice(0, 8000),
      url: typeof window !== "undefined" ? window.location.href : "",
      build: CLIENT_BUILD,
      user_agent: typeof navigator !== "undefined" ? navigator.userAgent : "",
    });
    fetch(`${API_URL}/api/v1/system/client-errors`, { method: "POST", headers: { "Content-Type": "application/json" }, body, keepalive: true }).catch(() => {});
  } catch {
    /* ignore */
  }
}
