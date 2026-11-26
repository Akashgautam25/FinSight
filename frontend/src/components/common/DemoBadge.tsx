import { FlaskConical } from "lucide-react";
import { cn } from "@/lib/utils";

/** Shown wherever data comes from the offline simulator instead of live markets. */
export function DemoBadge({ show = true, className }: { show?: boolean; className?: string }) {
  if (!show) return null;
  return (
    <span
      title="Live market data was unavailable, so FinSight is showing deterministic simulated data."
      className={cn(
        "inline-flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-500",
        className
      )}
    >
      <FlaskConical className="h-3 w-3" /> Simulated data
    </span>
  );
}
