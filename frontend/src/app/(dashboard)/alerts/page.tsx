"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, BellRing, CheckCircle2, Loader2, RefreshCw, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { alertsApi, apiError, stocksApi } from "@/lib/api";
import { cn, formatDate, formatNumber } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { ChangeText } from "@/components/common/ChangeText";
import { EmptyState } from "@/components/common/EmptyState";
import { PageHeader } from "@/components/common/PageHeader";
import { SymbolSearch } from "@/components/common/SymbolSearch";

function AlertsInner() {
  const qc = useQueryClient();
  const initial = useSearchParams().get("symbol");
  const [symbol, setSymbol] = useState(initial?.toUpperCase() ?? "");
  const [type, setType] = useState("price_above");
  const [value, setValue] = useState("");

  const { data: alerts, isLoading } = useQuery({ queryKey: ["alerts"], queryFn: () => alertsApi.list().then((r) => r.data), refetchInterval: 60_000 });
  const { data: quote } = useQuery({ queryKey: ["quote", symbol], queryFn: () => stocksApi.quotes([symbol]).then((r) => r.data[symbol]), enabled: !!symbol });

  useEffect(() => {
    if (quote?.price && !value) setValue(type.startsWith("pct") ? "3" : (quote.price * (type === "price_above" ? 1.05 : 0.95)).toFixed(2));
  }, [quote, type, value]);

  const refresh = () => { qc.invalidateQueries({ queryKey: ["alerts"] }); qc.invalidateQueries({ queryKey: ["notifications"] }); };
  const create = useMutation({
    mutationFn: () => alertsApi.create({ symbol, alert_type: type, target_value: parseFloat(value) }),
    onSuccess: () => { toast.success("Alert created"); setValue(""); refresh(); },
    onError: (e) => toast.error(apiError(e)),
  });
  const remove = useMutation({ mutationFn: (id: string) => alertsApi.delete(id), onSuccess: refresh });
  const check = useMutation({
    mutationFn: () => alertsApi.checkNow().then((r) => r.data),
    onSuccess: (d) => { toast[d.triggered ? "success" : "info"](d.triggered ? `${d.triggered} alert(s) triggered — see notifications` : "No alerts triggered right now"); refresh(); },
  });

  const active = (alerts ?? []).filter((a: any) => a.is_active);
  const triggered = (alerts ?? []).filter((a: any) => a.is_triggered);

  return (
    <div className="space-y-6">
      <PageHeader title="Price Alerts" description="Get notified when a stock crosses a price or moves sharply in a day. Alerts are checked automatically every few minutes."
        actions={<Button variant="outline" size="sm" onClick={() => check.mutate()} disabled={check.isPending}>{check.isPending ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-1.5 h-4 w-4" />} Check now</Button>} />

      <Card>
        <CardHeader title="New alert" description={symbol && quote ? `${symbol} is trading at ${formatNumber(quote.price)} (${quote.change_pct >= 0 ? "+" : ""}${quote.change_pct}% today)` : "Choose a stock"} />
        <CardContent className="flex flex-wrap items-end gap-3">
          <div className="w-56">
            {symbol ? (
              <button onClick={() => { setSymbol(""); setValue(""); }} className="flex h-9 w-full items-center justify-between rounded-md border border-input px-3 font-mono text-sm">{symbol} <span className="text-xs text-muted-foreground">change</span></button>
            ) : <SymbolSearch onSelect={setSymbol} placeholder="Symbol" />}
          </div>
          <Select value={type} onChange={(e) => { setType(e.target.value); setValue(""); }} className="w-60">
            <option value="price_above">Price rises above</option>
            <option value="price_below">Price falls below</option>
            <option value="pct_change_up">Gains at least X% in a day</option>
            <option value="pct_change_down">Drops at least X% in a day</option>
          </Select>
          <Input type="number" step="0.01" min="0" value={value} onChange={(e) => setValue(e.target.value)} placeholder={type.startsWith("pct") ? "%" : "Price"} className="w-32" />
          <Button onClick={() => create.mutate()} disabled={!symbol || !value || create.isPending}>{create.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : "Create alert"}</Button>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <AlertList title={`Active (${active.length})`} alerts={active} loading={isLoading} onDelete={(id) => remove.mutate(id)} icon={Bell} />
        <AlertList title={`Triggered (${triggered.length})`} alerts={triggered} loading={isLoading} onDelete={(id) => remove.mutate(id)} icon={BellRing} />
      </div>
    </div>
  );
}

function AlertList({ title, alerts, loading, onDelete, icon }: { title: string; alerts: any[]; loading: boolean; onDelete: (id: string) => void; icon: any }) {
  return (
    <Card>
      <CardHeader title={title} />
      <CardContent className="space-y-2">
        {loading ? [1, 2].map((i) => <Skeleton key={i} className="h-14" />) : alerts.length === 0 ? (
          <EmptyState icon={icon} title="Nothing here yet" />
        ) : alerts.map((a) => (
          <div key={a.id} className={cn("flex items-center gap-3 rounded-lg border p-3", a.is_triggered ? "border-profit/30 bg-profit/5" : "border-border/40")}>
            {a.is_triggered ? <CheckCircle2 className="h-4 w-4 shrink-0 text-profit" /> : <Bell className="h-4 w-4 shrink-0 text-muted-foreground" />}
            <div className="min-w-0 flex-1">
              <p className="text-sm"><Link href={`/stocks/${a.symbol}`} className="font-mono font-semibold hover:text-primary">{a.symbol}</Link> — {a.description.replace(`${a.symbol} `, "")}</p>
              <p className="text-xs text-muted-foreground">
                Now {formatNumber(a.current_price)} <ChangeText value={a.change_pct} className="text-xs" /> · {a.is_triggered ? `triggered ${formatDate(a.triggered_at, true)}` : `created ${formatDate(a.created_at)}`}
              </p>
            </div>
            <button onClick={() => onDelete(a.id)} className="text-muted-foreground hover:text-destructive" title="Delete"><Trash2 className="h-3.5 w-3.5" /></button>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

export default function AlertsPage() {
  return <Suspense fallback={<Skeleton className="h-96" />}><AlertsInner /></Suspense>;
}
