"use client";

import { useQuery } from "@tanstack/react-query";
import { portfolioApi } from "@/lib/api";
import { formatCurrency, formatPercent, getPriceChangeClass } from "@/lib/utils";
import { Briefcase, TrendingUp } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";

export function PortfolioSummary() {
  const { data: portfolios, isLoading } = useQuery({
    queryKey: ["portfolios"],
    queryFn: () => portfolioApi.list().then((r) => r.data),
  });

  const defaultPortfolio = portfolios?.[0];

  const { data: analytics } = useQuery({
    queryKey: ["portfolio-analytics", defaultPortfolio?.id],
    queryFn: () =>
      portfolioApi.getAnalytics(defaultPortfolio!.id).then((r) => r.data),
    enabled: !!defaultPortfolio?.id,
  });

  if (isLoading) {
    return (
      <div className="rounded-xl border border-border/50 bg-card p-6 h-full">
        <div className="animate-pulse space-y-4">
          <div className="h-5 bg-muted rounded w-24" />
          <div className="h-10 bg-muted rounded w-40" />
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-4 bg-muted rounded" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (!defaultPortfolio) {
    return (
      <div className="rounded-xl border border-border/50 bg-card p-6 flex flex-col items-center justify-center h-full gap-3">
        <Briefcase className="h-8 w-8 text-muted-foreground" />
        <p className="text-sm text-muted-foreground text-center">
          No portfolio yet. Create one to track your investments.
        </p>
        <Link href="/portfolio">
          <Button size="sm">Create Portfolio</Button>
        </Link>
      </div>
    );
  }

  const returnClass = getPriceChangeClass(analytics?.return_pct);

  return (
    <div className="rounded-xl border border-border/50 bg-card p-6 h-full">
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-semibold text-sm">Portfolio</h2>
        <Link href="/portfolio">
          <Button variant="ghost" size="sm" className="text-xs">View All</Button>
        </Link>
      </div>

      {analytics ? (
        <div className="space-y-4">
          <div>
            <p className="text-xs text-muted-foreground">Current Value</p>
            <p className="text-2xl font-bold font-mono mt-0.5">
              {formatCurrency(analytics.current_value)}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Metric label="Invested" value={formatCurrency(analytics.total_invested)} />
            <Metric label="P&L" value={formatCurrency(analytics.absolute_return)} className={returnClass} />
            <Metric label="Return" value={formatPercent(analytics.return_pct)} className={returnClass} />
            <Metric label="Sharpe" value={analytics.sharpe_ratio?.toFixed(2) || "—"} />
          </div>

          {analytics.portfolio_volatility && (
            <div className="pt-3 border-t border-border/40">
              <p className="text-xs text-muted-foreground">
                Volatility (annualized): <span className="text-foreground font-mono">{analytics.portfolio_volatility.toFixed(1)}%</span>
              </p>
              {analytics.max_drawdown && (
                <p className="text-xs text-muted-foreground mt-1">
                  Max Drawdown: <span className="text-loss font-mono">{analytics.max_drawdown.toFixed(1)}%</span>
                </p>
              )}
            </div>
          )}
        </div>
      ) : (
        <div className="text-sm text-muted-foreground">
          Add holdings to see analytics.
        </div>
      )}
    </div>
  );
}

function Metric({ label, value, className = "" }: { label: string; value: string; className?: string }) {
  return (
    <div className="p-3 rounded-lg bg-muted/30">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={`text-sm font-semibold font-mono mt-0.5 ${className}`}>{value}</p>
    </div>
  );
}
