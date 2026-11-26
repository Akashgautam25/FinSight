"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Bookmark } from "lucide-react";
import { watchlistApi } from "@/lib/api";
import { formatNumber } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ChangeText } from "@/components/common/ChangeText";
import { EmptyState } from "@/components/common/EmptyState";

export function WatchlistWidget() {
  const { data: lists } = useQuery({ queryKey: ["watchlists"], queryFn: () => watchlistApi.list().then((r) => r.data) });
  const wid = lists?.[0]?.id;
  const { data, isLoading } = useQuery({
    queryKey: ["watchlist-quotes", wid],
    queryFn: () => watchlistApi.quotes(wid).then((r) => r.data),
    enabled: !!wid,
    refetchInterval: 2 * 60 * 1000,
  });
  const items = data?.items ?? [];

  return (
    <Card>
      <CardHeader title={data?.name ?? "Watchlist"} description="Live quotes for stocks you follow"
        action={<Link href="/watchlists"><Button variant="ghost" size="sm" className="text-xs">Manage</Button></Link>} />
      <CardContent>
        {isLoading || (!data && wid) ? (
          <div className="space-y-2">{[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-10" />)}</div>
        ) : items.length === 0 ? (
          <EmptyState icon={Bookmark} title="Your watchlist is empty" action={<Link href="/watchlists"><Button size="sm" variant="outline">Add stocks</Button></Link>} />
        ) : (
          <div className="divide-y divide-border/30">
            {items.slice(0, 7).map((i: any) => (
              <Link key={i.symbol} href={`/stocks/${i.symbol}`} className="flex items-center justify-between py-2.5 text-sm hover:bg-muted/20">
                <div className="min-w-0">
                  <p className="font-mono font-semibold">{i.symbol}</p>
                  <p className="truncate text-xs text-muted-foreground">{i.name}</p>
                </div>
                <div className="text-right">
                  <p className="font-mono">{formatNumber(i.price)}</p>
                  <ChangeText value={i.change_pct} className="text-xs" />
                </div>
              </Link>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
