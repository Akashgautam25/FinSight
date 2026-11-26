"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Area, AreaChart, ResponsiveContainer, Tooltip, YAxis } from "recharts";
import { Briefcase } from "lucide-react";
import { portfolioApi } from "@/lib/api";
import { formatCurrency, formatPercent, getPriceChangeClass } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/common/EmptyState";

export function PortfolioSummary() {
  const { data: portfolios, isLoading } = useQuery({ queryKey: ["portfolios"], queryFn: () => portfolioApi.list().then((r) => r.data) });
  const pid = portfolios?.[0]?.id;
  const { data: a, isLoading: loadingA } = useQuery({
    queryKey: ["portfolio-analytics", pid],
    queryFn: () => portfolioApi.getAnalytics(pid).then((r) => r.data),
    enabled: !!pid,
  });

  return (
    <Card className="h-full">
      <CardHeader title={portfolios?.[0]?.name ?? "Portfolio"} description="Value, return and risk" action={<Link href="/portfolio"><Button variant="ghost" size="sm" className="text-xs">Open</Button></Link>} />
      <CardContent>
        {isLoading || (pid && loadingA) ? (
          <div className="space-y-3"><Skeleton className="h-10 w-40" /><Skeleton className="h-24" /><Skeleton className="h-16" /></div>
        ) : !a || a.holdings.length === 0 ? (
          <EmptyState icon={Briefcase} title="No holdings yet" description="Record your first buy to start tracking performance and risk."
            action={<Link href="/portfolio"><Button size="sm">Add a transaction</Button></Link>} />
        ) : (
          <div className="space-y-4">
            <div>
              <p className="text-xs text-muted-foreground">Current value</p>
              <p className="font-mono text-2xl font-bold">{formatCurrency(a.current_value)}</p>
              <p className={`font-mono text-xs ${getPriceChangeClass(a.absolute_return)}`}>
                {formatCurrency(a.absolute_return)} ({formatPercent(a.return_pct)}) unrealized
              </p>
            </div>
            {a.performance?.length > 0 && (
              <div className="h-20">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={a.performance}>
                    <YAxis hide domain={["auto", "auto"]} />
                    <Tooltip contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 8, fontSize: 11 }}
                      formatter={(v: number, n: string) => [v.toFixed(1), n === "portfolio" ? "Portfolio" : "S&P 500"]} labelFormatter={(l) => l} />
                    <Area dataKey="benchmark" stroke="#64748b" fill="transparent" strokeDasharray="3 3" dot={false} />
                    <Area dataKey="portfolio" stroke="#3b82f6" fill="#3b82f622" dot={false} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}
            <div className="grid grid-cols-2 gap-2 text-xs">
              <Metric label="Sharpe" value={a.sharpe_ratio?.toFixed(2)} />
              <Metric label="Volatility" value={a.portfolio_volatility != null ? `${a.portfolio_volatility.toFixed(1)}%` : undefined} />
              <Metric label="Max drawdown" value={a.max_drawdown != null ? `${a.max_drawdown.toFixed(1)}%` : undefined} className="text-loss" />
              <Metric label="Beta" value={a.beta?.toFixed(2)} />
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function Metric({ label, value, className = "" }: { label: string; value?: string; className?: string }) {
  return (
    <div className="rounded-lg bg-muted/30 p-2.5">
      <p className="text-muted-foreground">{label}</p>
      <p className={`mt-0.5 font-mono font-semibold ${className}`}>{value ?? "—"}</p>
    </div>
  );
}
