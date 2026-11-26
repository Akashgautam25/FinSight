"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import { stocksApi } from "@/lib/api";
import { formatLargeNumber, formatNumber } from "@/lib/utils";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ChangeText } from "@/components/common/ChangeText";
import { DemoBadge } from "@/components/common/DemoBadge";
import { PageHeader } from "@/components/common/PageHeader";
import { SymbolSearch } from "@/components/common/SymbolSearch";
import { MoverList, useMarketOverview } from "@/components/dashboard/MarketOverview";

const QUICK = {
  "US mega caps": ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "NFLX"],
  "Financials & defensives": ["JPM", "V", "BAC", "JNJ", "KO", "WMT", "XOM", "DIS"],
  "India (NSE)": ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS"],
};

export default function MarketPage() {
  const router = useRouter();
  const { data: overview, isLoading } = useMarketOverview();
  const allQuick = Object.values(QUICK).flat();
  const { data: quotes } = useQuery({ queryKey: ["quotes", allQuick], queryFn: () => stocksApi.quotes(allQuick).then((r) => r.data), refetchInterval: 120_000 });

  return (
    <div className="space-y-6">
      <PageHeader title="Markets" description="Indices, today's movers and quick access to popular stocks" actions={<DemoBadge show={!!overview?.is_demo} />} />
      <SymbolSearch onSelect={(s) => router.push(`/stocks/${encodeURIComponent(s)}`)} className="max-w-xl" autoFocus />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        {isLoading ? Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-20" />) : (overview?.indices ?? []).map((i: any) => (
          <div key={i.symbol} className="rounded-xl border border-border/40 bg-card p-4">
            <p className="truncate text-xs text-muted-foreground">{i.name}</p>
            <p className="mt-1 font-mono text-lg font-bold">{formatNumber(i.value, 0)}</p>
            <ChangeText value={i.change_pct} icon className="text-xs" />
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card><CardHeader title="Top gainers" /><CardContent><MoverList title="" items={overview?.top_gainers ?? []} /></CardContent></Card>
        <Card><CardHeader title="Top losers" /><CardContent><MoverList title="" items={overview?.top_losers ?? []} /></CardContent></Card>
        <Card>
          <CardHeader title="Most active" description="By latest daily volume" />
          <CardContent>
            <div className="divide-y divide-border/30 rounded-lg border border-border/30">
              {(overview?.most_active ?? []).map((m: any) => (
                <Link key={m.symbol} href={`/stocks/${m.symbol}`} className="flex items-center justify-between px-3 py-2 text-sm hover:bg-muted/30">
                  <span className="font-mono font-semibold">{m.symbol}</span>
                  <span className="font-mono text-xs text-muted-foreground">{formatLargeNumber(m.volume)} shares</span>
                </Link>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {Object.entries(QUICK).map(([group, symbols]) => (
        <div key={group}>
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{group}</h2>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            {symbols.map((sym) => {
              const q = quotes?.[sym];
              return (
                <Link key={sym} href={`/stocks/${sym}`} className="group flex items-center justify-between rounded-lg border border-border/40 bg-card p-3 hover:border-primary/40 hover:bg-primary/5">
                  <div>
                    <p className="font-mono text-sm font-semibold">{sym}</p>
                    <p className="font-mono text-xs text-muted-foreground">{q ? formatNumber(q.price) : "…"}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    {q && <ChangeText value={q.change_pct} className="text-xs" />}
                    <ArrowRight className="h-3 w-3 text-muted-foreground opacity-0 group-hover:opacity-100" />
                  </div>
                </Link>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
