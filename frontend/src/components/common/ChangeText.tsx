import { TrendingDown, TrendingUp } from "lucide-react";
import { cn, formatPercent } from "@/lib/utils";

export function ChangeText({ value, className, icon = false }: { value: number | null | undefined; className?: string; icon?: boolean }) {
  if (value == null) return <span className={cn("text-muted-foreground", className)}>—</span>;
  const up = value >= 0;
  return (
    <span className={cn("inline-flex items-center gap-1 font-mono", up ? "text-profit" : "text-loss", className)}>
      {icon && (up ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />)}
      {formatPercent(value)}
    </span>
  );
}
