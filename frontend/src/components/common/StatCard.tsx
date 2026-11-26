import { cn } from "@/lib/utils";

export function StatCard({ label, value, sub, className, valueClassName, hint }: {
  label: string; value: React.ReactNode; sub?: React.ReactNode; className?: string; valueClassName?: string; hint?: string;
}) {
  return (
    <div className={cn("rounded-xl border border-border/40 bg-card p-4", className)} title={hint}>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={cn("mt-1 text-lg font-bold font-mono truncate", valueClassName)}>{value}</p>
      {sub && <p className="mt-0.5 text-xs text-muted-foreground">{sub}</p>}
    </div>
  );
}
