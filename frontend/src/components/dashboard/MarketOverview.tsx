"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { stocksApi } from "@/lib/api";
import { formatNumber, timeAgo } from "@/lib/utils";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ChangeText } from "@/components/common/ChangeText";
import { DemoBadge } from "@/components/common/DemoBadge";

export function useMarketOverview() {
  return useQuery({
    queryKey: ["market-overview"],
    queryFn: () => stocksApi.getMarketOverview().then((r) => r.data),
    refetchInterval: 5 * 60 * 1000,
  });
}

export function MarketOverviewWidget() {
  const { data, isLoading, error } = useMarketOverview();

  return (
    <Card>
      <CardHeader
        title="Market Overview"
        description={data?.as_of ? `Updated ${timeAgo(data.as_of)} · US market ${data.market_status}` : "Major indices and today's movers"}
        action={<DemoBadge show={!!data?.is_demo} />}
      />
      <CardContent className="space-y-5">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
          {isLoading
            ? Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-[72px] rounded-lg" />)
            : (data?.indices ?? []).map((idx: any) => (
                <div key={idx.symbol} className="rounded-lg border border-border/30 bg-muted/30 p-3">
                  <p className="truncate text-xs text-muted-foreground">{idx.name}</p>
                  <p className="mt-1 font-mono text-base font-semibold">{formatNumber(idx.value, 0)}</p>
                  <ChangeText value={idx.change_pct} icon className="text-xs" />
                </div>
              ))}
          {error && <p className="col-span-full py-6 text-center text-sm text-muted-foreground">Failed to load market data.</p>}
        </div>
        {!isLoading && data && (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <MoverList title="Top gainers" items={data.top_gainers} />
            <MoverList title="Top losers" items={data.top_losers} />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function MoverList({ title, items }: { title: string; items: any[] }) {
  return (
    <div>
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</p>
      {items?.length ? (
        <div className="divide-y divide-border/30 rounded-lg border border-border/30">
          {items.map((m) => (
            <Link key={m.symbol} href={`/stocks/${m.symbol}`} className="flex items-center justify-between px-3 py-2 text-sm hover:bg-muted/30">
              <span className="font-mono font-semibold">{m.symbol}</span>
              <span className="flex items-center gap-3">
                <span className="font-mono text-muted-foreground">{formatNumber(m.price)}</span>
                <ChangeText value={m.change_pct} className="w-16 text-right text-xs" />
              </span>
            </Link>
          ))}
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">No movers in this direction today.</p>
      )}
    </div>
  );
}
