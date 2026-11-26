import { Minus, TrendingDown, TrendingUp } from "lucide-react";
import { cn } from "@/lib/utils";

export function SentimentBadge({ sentiment, compact = false, score }: { sentiment?: string; compact?: boolean; score?: number }) {
  const s = sentiment ?? "neutral";
  const styles = s === "positive" ? "bg-profit/15 text-profit" : s === "negative" ? "bg-loss/15 text-loss" : "bg-muted text-muted-foreground";
  const Icon = s === "positive" ? TrendingUp : s === "negative" ? TrendingDown : Minus;
  if (compact) {
    return (
      <span className={cn("mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full", styles)} title={`${s} sentiment`}>
        <Icon className="h-3 w-3" />
      </span>
    );
  }
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider", styles)}>
      <Icon className="h-3 w-3" /> {s}{score != null && ` ${score > 0 ? "+" : ""}${score.toFixed(2)}`}
    </span>
  );
}
