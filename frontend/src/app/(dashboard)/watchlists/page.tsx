"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, Bookmark, Pencil, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { apiError, watchlistApi } from "@/lib/api";
import { cn, formatCurrency, formatLargeNumber, formatNumber } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ChangeText } from "@/components/common/ChangeText";
import { DemoBadge } from "@/components/common/DemoBadge";
import { EmptyState } from "@/components/common/EmptyState";
import { PageHeader } from "@/components/common/PageHeader";
import { SymbolSearch } from "@/components/common/SymbolSearch";

export default function WatchlistsPage() {
  const qc = useQueryClient();
  const [selected, setSelected] = useState<string | null>(null);
  const { data: lists, isLoading } = useQuery({ queryKey: ["watchlists"], queryFn: () => watchlistApi.list().then((r) => r.data) });
  const activeId = selected && lists?.some((l: any) => l.id === selected) ? selected : lists?.[0]?.id;
  const active = lists?.find((l: any) => l.id === activeId);

  const { data: quotes, isLoading: loadingQuotes } = useQuery({
    queryKey: ["watchlist-quotes", activeId],
    queryFn: () => watchlistApi.quotes(activeId).then((r) => r.data),
    enabled: !!activeId,
    refetchInterval: 120_000,
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["watchlists"] });
    qc.invalidateQueries({ queryKey: ["watchlist-quotes"] });
  };
  const add = useMutation({ mutationFn: (s: string) => watchlistApi.addSymbol(activeId, s), onSuccess: (_, s) => { toast.success(`${s} added`); invalidate(); }, onError: (e) => toast.error(apiError(e)) });
  const remove = useMutation({ mutationFn: (s: string) => watchlistApi.removeSymbol(activeId, s), onSuccess: invalidate });
  const create = useMutation({ mutationFn: (n: string) => watchlistApi.create(n), onSuccess: (res) => { setSelected(res.data.id); invalidate(); } });
  const rename = useMutation({ mutationFn: (n: string) => watchlistApi.rename(activeId, n), onSuccess: invalidate });
  const del = useMutation({ mutationFn: () => watchlistApi.delete(activeId), onSuccess: () => { setSelected(null); invalidate(); } });

  if (isLoading) return <Skeleton className="h-96" />;
  const items = quotes?.items ?? [];

  return (
    <div className="space-y-6">
      <PageHeader title="Watchlists" description="Follow stocks with live quotes; set price alerts in one click"
        actions={<Button variant="outline" size="sm" onClick={() => { const n = prompt("Watchlist name"); if (n?.trim()) create.mutate(n.trim()); }}><Plus className="mr-1.5 h-4 w-4" /> New list</Button>} />

      <div className="flex flex-wrap items-center gap-2">
        {lists?.map((l: any) => (
          <button key={l.id} onClick={() => setSelected(l.id)} className={cn("rounded-lg border px-3 py-1.5 text-sm", l.id === activeId ? "border-primary bg-primary/10 text-primary" : "border-border/50 hover:border-primary/40")}>
            {l.name} <span className="ml-1 text-xs opacity-60">{l.symbols.length}</span>
          </button>
        ))}
        {active && (
          <div className="ml-auto flex gap-1">
            <Button variant="ghost" size="icon" title="Rename" onClick={() => { const n = prompt("Rename watchlist", active.name); if (n?.trim()) rename.mutate(n.trim()); }}><Pencil className="h-4 w-4" /></Button>
            <Button variant="ghost" size="icon" title="Delete list" onClick={() => confirm(`Delete "${active.name}"?`) && del.mutate()}><Trash2 className="h-4 w-4" /></Button>
          </div>
        )}
      </div>

      {!active ? (
        <Card><EmptyState icon={Bookmark} title="No watchlists" action={<Button size="sm" onClick={() => create.mutate("My Watchlist")}>Create a watchlist</Button>} /></Card>
      ) : (
        <>
          <div className="flex items-center gap-3">
            <SymbolSearch onSelect={(s) => add.mutate(s)} placeholder={`Add a stock to "${active.name}"`} className="max-w-sm flex-1" />
            <DemoBadge show={items.some((i: any) => i.is_demo)} />
          </div>
          <Card className="overflow-x-auto">
            {loadingQuotes ? <div className="space-y-2 p-4">{[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-12" />)}</div> : items.length === 0 ? (
              <EmptyState icon={Bookmark} title="This watchlist is empty" description="Search for a stock above to add it." />
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border/30 bg-muted/20 text-xs text-muted-foreground">
                    <th className="px-5 py-3 text-left">Stock</th><th className="px-4 text-right">Price</th><th className="px-4 text-right">Change</th>
                    <th className="px-4 text-right">Change %</th><th className="px-4 text-right">Volume</th><th className="px-5 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/20">
                  {items.map((i: any) => (
                    <tr key={i.symbol} className="hover:bg-muted/10">
                      <td className="px-5 py-3">
                        <Link href={`/stocks/${i.symbol}`} className="font-mono font-semibold hover:text-primary">{i.symbol}</Link>
                        <p className="max-w-[220px] truncate text-xs text-muted-foreground">{i.name}{i.sector ? ` · ${i.sector}` : ""}</p>
                      </td>
                      <td className="px-4 text-right font-mono font-medium">{formatCurrency(i.price, i.currency)}</td>
                      <td className={cn("px-4 text-right font-mono", (i.change ?? 0) >= 0 ? "text-profit" : "text-loss")}>{i.change != null && (i.change >= 0 ? "+" : "")}{formatNumber(i.change)}</td>
                      <td className="px-4 text-right"><ChangeText value={i.change_pct} /></td>
                      <td className="px-4 text-right font-mono text-muted-foreground">{formatLargeNumber(i.volume)}</td>
                      <td className="px-5 text-right">
                        <div className="flex justify-end gap-1">
                          <Link href={`/alerts?symbol=${i.symbol}`}><Button variant="ghost" size="sm" className="h-7 px-2" title="Create alert"><Bell className="h-3.5 w-3.5" /></Button></Link>
                          <Button variant="ghost" size="sm" className="h-7 px-2 text-muted-foreground hover:text-destructive" onClick={() => remove.mutate(i.symbol)} title="Remove"><Trash2 className="h-3.5 w-3.5" /></Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
