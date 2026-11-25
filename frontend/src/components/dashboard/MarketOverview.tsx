"use client";

import { useQuery } from "@tanstack/react-query";
import { stocksApi } from "@/lib/api";
import { formatPercent } from "@/lib/utils";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

export function MarketOverviewWidget() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["market-overview"],
    queryFn: () => stocksApi.getMarketOverview().then((r) => r.data),
    refetchInterval: 5 * 60 * 1000, // 5 min
  });

  if (isLoading) {
    return (
      <div className="rounded-xl border border-border/50 bg-card p-6">
        <div className="animate-pulse space-y-3">
          <div className="h-5 bg-muted rounded w-32" />
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mt-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-16 bg-muted rounded-lg" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  const indices = data?.indices || [];

  return (
    <div className="rounded-xl border border-border/50 bg-card p-6">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="font-semibold text-sm">Market Overview</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            {data?.as_of ? `Updated: ${new Date(data.as_of).toLocaleTimeString()}` : "Delayed data"}
          </p>
        </div>
        <span className="text-xs px-2 py-1 rounded-full bg-muted text-muted-foreground">
          {data?.market_status || "delayed"}
        </span>
      </div>

      {/* Indices */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
        {indices.length > 0 ? (
          indices.map((index: any) => (
            <IndexCard key={index.symbol} data={index} />
          ))
        ) : (
          <div className="col-span-5 text-center py-8 text-muted-foreground text-sm">
            {error ? "Failed to load market data." : "No index data available."}
          </div>
        )}
      </div>
    </div>
  );
}

function IndexCard({ data }: { data: any }) {
  const isPositive = data.change_pct >= 0;
  const isFlat = data.change_pct === 0;

  return (
    <div className="p-3 rounded-lg bg-muted/30 border border-border/30">
      <p className="text-xs text-muted-foreground truncate">{data.name}</p>
      <p className="text-base font-semibold mt-1 font-mono">
        {data.value?.toLocaleString("en-US", { maximumFractionDigits: 0 })}
      </p>
      <div
        className={`flex items-center gap-1 mt-1 text-xs font-medium ${
          isFlat
            ? "text-muted-foreground"
            : isPositive
            ? "text-profit"
            : "text-loss"
        }`}
      >
        {isFlat ? (
          <Minus className="h-3 w-3" />
        ) : isPositive ? (
          <TrendingUp className="h-3 w-3" />
        ) : (
          <TrendingDown className="h-3 w-3" />
        )}
        {formatPercent(data.change_pct)}
      </div>
    </div>
  );
}
