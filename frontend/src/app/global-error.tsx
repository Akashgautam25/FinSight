"use client";

import { useEffect } from "react";
import { isNewBuildAvailable, isStaleBuildError, reloadOnceForStaleBuild, reportClientError } from "@/lib/errors";

// Last-resort boundary (replaces the root layout, so it cannot use the app's providers or CSS).
export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    (async () => {
      if (isStaleBuildError(error) || (await isNewBuildAvailable())) reloadOnceForStaleBuild();
      else reportClientError(error, "global-error");
    })();
  }, [error]);
  return (
    <html lang="en">
      <body style={{ background: "#0f1115", color: "#e5e7eb", fontFamily: "system-ui, sans-serif", display: "grid", placeItems: "center", minHeight: "100vh", margin: 0 }}>
        <div style={{ textAlign: "center", maxWidth: 420, padding: 24 }}>
          <h2 style={{ margin: "0 0 8px" }}>FinSight AI hit an unexpected error</h2>
          <p style={{ color: "#9ca3af", fontSize: 14 }}>Please reload the page. If this keeps happening, restart the frontend (npm run dev).</p>
          <div style={{ display: "flex", gap: 8, justifyContent: "center", marginTop: 16 }}>
            <button onClick={reset} style={{ padding: "6px 14px", borderRadius: 6, border: "1px solid #374151", background: "transparent", color: "inherit", cursor: "pointer" }}>Try again</button>
            <button onClick={() => window.location.reload()} style={{ padding: "6px 14px", borderRadius: 6, border: 0, background: "#3b82f6", color: "white", cursor: "pointer" }}>Reload</button>
          </div>
        </div>
      </body>
    </html>
  );
}
