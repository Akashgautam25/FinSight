"use client";

import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";
import { isNewBuildAvailable, reloadOnceForStaleBuild, reportClientError } from "@/lib/errors";

/**
 * Reloads the page when the frontend has been rebuilt while this tab was open
 * (checked on navigation and when the tab regains focus, at most every 20 s),
 * and reports uncaught browser errors to the backend log.
 */
export function BuildWatcher() {
  const pathname = usePathname();
  const lastCheck = useRef(0);

  const check = async () => {
    if (Date.now() - lastCheck.current < 20_000) return;
    lastCheck.current = Date.now();
    if (await isNewBuildAvailable()) reloadOnceForStaleBuild();
  };

  useEffect(() => {
    check();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === "visible") check();
    };
    const onError = (e: ErrorEvent) => reportClientError(e.error ?? e.message, "window.onerror");
    const onRejection = (e: PromiseRejectionEvent) => {
      const reason = e.reason as { name?: string } | undefined;
      if (reason?.name !== "AbortError") reportClientError(e.reason, "unhandledrejection");
    };
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("error", onError);
    window.addEventListener("unhandledrejection", onRejection);
    return () => {
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("error", onError);
      window.removeEventListener("unhandledrejection", onRejection);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return null;
}
