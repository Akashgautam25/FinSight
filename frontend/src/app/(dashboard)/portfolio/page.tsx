"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid } from "recharts";
import { Briefcase, Loader2, Pencil, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { apiError, portfolioApi, stocksApi } from "@/lib/api";
import { CHART_COLORS, cn, formatCurrency, formatDate, formatPercent, getPriceChangeClass } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DemoBadge } from "@/components/common/DemoBadge";
import { EmptyState } from "@/components/common/EmptyState";
import { PageHeader } from "@/components/common/PageHeader";
import { StatCard } from "@/components/common/StatCard";
import { SymbolSearch } from "@/components/common/SymbolSearch";
import { AIInsightCard } from "@/components/ai/AIInsightCard";

const tooltipStyle = { backgroundColor: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 8, fontSize: 12 };

export default function PortfolioPage() {
  const qc = useQueryClient();
  const [selected, setSelected] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  const { data: portfolios, isLoading } = useQuery({ queryKey: ["portfolios"], queryFn: () => portfolioApi.list().then((r) => r.data) });
  const activeId = selected && portfolios?.some((p: any) => p.id === selected) ? selected : portfolios?.[0]?.id ?? null;
  const active = portfolios?.find((p: any) => p.id === activeId);

  const { data: a, isLoading: loadingA, isFetching } = useQuery({
    queryKey: ["portfolio-analytics", activeId],
    queryFn: () => portfolioApi.getAnalytics(activeId!).then((r) => r.data),
    enabled: !!activeId,
  });
  const { data: txns } = useQuery({
    queryKey: ["portfolio-transactions", activeId],
    queryFn: () => portfolioApi.listTransactions(activeId!).then((r) => r.data),
    enabled: !!activeId,
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["portfolio-analytics", activeId] });
    qc.invalidateQueries({ queryKey: ["portfolio-transactions", activeId] });
  };

  const create = useMutation({
    mutationFn: (name: string) => portfolioApi.create({ name }),
    onSuccess: (res) => { qc.invalidateQueries({ queryKey: ["portfolios"] }); setSelected(res.data.id); toast.success("Portfolio created"); },
    onError: (e) => toast.error(apiError(e)),
  });
  const rename = useMutation({
    mutationFn: (name: string) => portfolioApi.update(activeId!, { name }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["portfolios"] }),
  });
  const remove = useMutation({
    mutationFn: () => portfolioApi.delete(activeId!),
    onSuccess: () => { setSelected(null); qc.invalidateQueries({ queryKey: ["portfolios"] }); toast.success("Portfolio deleted"); },
  });
  const deleteTx = useMutation({
    mutationFn: (txId: string) => portfolioApi.deleteTransaction(activeId!, txId),
    onSuccess: () => { refresh(); toast.success("Transaction removed — holdings recalculated"); },
    onError: (e) => toast.error(apiError(e)),
  });

  if (isLoading) return <Skeleton className="h-96" />;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Portfolio Manager"
        description="Track positions, realised and unrealised P&L, and quantitative risk metrics"
        actions={
          <>
            <Button variant="outline" size="sm" onClick={() => { const n = prompt("New portfolio name"); if (n?.trim()) create.mutate(n.trim()); }}>New portfolio</Button>
            <Button size="sm" onClick={() => setShowForm((s) => !s)} disabled={!activeId}><Plus className="mr-1.5 h-4 w-4" /> Record transaction</Button>
          </>
        }
      />

      {portfolios?.length ? (
        <div className="flex flex-wrap items-center gap-2">
          {portfolios.map((p: any) => (
            <button key={p.id} onClick={() => setSelected(p.id)}
              className={cn("rounded-lg border px-3 py-1.5 text-sm", p.id === activeId ? "border-primary bg-primary/10 text-primary" : "border-border/50 hover:border-primary/40")}>
              {p.name}
            </button>
          ))}
          {active && (
            <div className="ml-auto flex gap-1">
              <Button variant="ghost" size="icon" title="Rename" onClick={() => { const n = prompt("Rename portfolio", active.name); if (n?.trim()) rename.mutate(n.trim()); }}><Pencil className="h-4 w-4" /></Button>
              <Button variant="ghost" size="icon" title="Delete" onClick={() => confirm(`Delete "${active.name}" and all its transactions?`) && remove.mutate()}><Trash2 className="h-4 w-4" /></Button>
            </div>
          )}
        </div>
      ) : (
        <Card><EmptyState icon={Briefcase} title="No portfolios yet" action={<Button size="sm" onClick={() => create.mutate("My Portfolio")}>Create portfolio</Button>} /></Card>
      )}

      {showForm && activeId && <TransactionForm portfolioId={activeId} onDone={() => { setShowForm(false); refresh(); }} />}

      {activeId && (loadingA ? (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-6">{Array.from({ length: 12 }).map((_, i) => <Skeleton key={i} className="h-20" />)}</div>
      ) : a && a.holdings.length === 0 ? (
        <Card>
          <EmptyState icon={Briefcase} title="This portfolio has no holdings"
            description="Record a BUY transaction to start tracking value, returns and risk metrics."
            action={<Button size="sm" onClick={() => setShowForm(true)}><Plus className="mr-1.5 h-4 w-4" /> Record transaction</Button>} />
        </Card>
      ) : a && (
        <>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            {isFetching && <Loader2 className="h-3 w-3 animate-spin" />} Updated {formatDate(a.calculated_at, true)} <DemoBadge show={a.is_demo} />
          </div>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6">
            <StatCard label="Market value" value={formatCurrency(a.current_value)} />
            <StatCard label="Invested (cost basis)" value={formatCurrency(a.total_invested)} />
            <StatCard label="Unrealised P&L" value={formatCurrency(a.absolute_return)} sub={formatPercent(a.return_pct)} valueClassName={getPriceChangeClass(a.absolute_return)} />
            <StatCard label="Realised P&L" value={formatCurrency(a.realized_pnl)} valueClassName={getPriceChangeClass(a.realized_pnl)} hint="Profit locked in by sales (average-cost method)" />
            <StatCard label="Today" value={formatPercent(a.daily_return)} valueClassName={getPriceChangeClass(a.daily_return)} />
            <StatCard label="Annualised return (1y)" value={formatPercent(a.annualized_return)} sub={a.benchmark_return != null ? `S&P 500: ${formatPercent(a.benchmark_return)}` : undefined} valueClassName={getPriceChangeClass(a.annualized_return)} />
            <StatCard label="Volatility (ann.)" value={a.portfolio_volatility != null ? `${a.portfolio_volatility.toFixed(1)}%` : "—"} hint="Standard deviation of daily returns × √252" />
            <StatCard label="Sharpe ratio" value={a.sharpe_ratio?.toFixed(2) ?? "—"} hint="Excess return per unit of volatility (risk-free 5%)" />
            <StatCard label="Sortino ratio" value={a.sortino_ratio?.toFixed(2) ?? "—"} hint="Excess return per unit of downside deviation" />
            <StatCard label="Max drawdown" value={a.max_drawdown != null ? `${a.max_drawdown.toFixed(1)}%` : "—"} valueClassName="text-loss" hint="Largest peak-to-trough fall over the year" />
            <StatCard label="Beta vs S&P 500" value={a.beta?.toFixed(2) ?? "—"} hint="Sensitivity to market moves" />
            <StatCard label="1-day VaR / CVaR (95%)" value={formatCurrency(a.var_95, "USD", 0)} sub={a.cvar_95 != null ? `CVaR ${formatCurrency(a.cvar_95, "USD", 0)}` : undefined} hint="Historical simulation: loss exceeded on 5% of days / average loss on those days" />
          </div>

          <AIInsightCard key={activeId} kind="portfolio" title="AI portfolio review" description="Strengths, risks and ideas to consider — generated from your holdings and risk metrics" />

          <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
            <Card className="xl:col-span-2">
              <CardHeader title="Performance vs S&P 500 (1 year, indexed to 100)" description="Current weights held constant — shows how today's allocation would have performed." />
              <CardContent>
                <ResponsiveContainer width="100%" height={260}>
                  <LineChart data={a.performance}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" strokeOpacity={0.4} />
                    <XAxis dataKey="date" tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} tickLine={false} axisLine={false} minTickGap={50} />
                    <YAxis domain={["auto", "auto"]} tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} tickLine={false} axisLine={false} width={40} />
                    <Tooltip contentStyle={tooltipStyle} />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Line dataKey="portfolio" name="Portfolio" stroke="#3b82f6" strokeWidth={1.8} dot={false} />
                    <Line dataKey="benchmark" name="S&P 500" stroke="#64748b" strokeDasharray="4 3" strokeWidth={1.4} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
            <Card>
              <CardHeader title="Allocation" />
              <CardContent>
                <Tabs defaultValue="holding">
                  <TabsList className="bg-muted/50"><TabsTrigger value="holding">By holding</TabsTrigger><TabsTrigger value="sector">By sector</TabsTrigger></TabsList>
                  {(["holding", "sector"] as const).map((k) => {
                    const src = k === "holding" ? a.asset_allocation : a.sector_allocation;
                    const data = Object.entries(src ?? {}).map(([name, value]) => ({ name, value: Number(value) }));
                    return (
                      <TabsContent key={k} value={k}>
                        <ResponsiveContainer width="100%" height={220}>
                          <PieChart>
                            <Pie data={data} dataKey="value" nameKey="name" innerRadius={50} outerRadius={80} paddingAngle={2}>
                              {data.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
                            </Pie>
                            <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => `${v.toFixed(1)}%`} />
                            <Legend wrapperStyle={{ fontSize: 11 }} />
                          </PieChart>
                        </ResponsiveContainer>
                      </TabsContent>
                    );
                  })}
                </Tabs>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader title="Holdings" description={`${a.holdings.length} positions`} />
            <CardContent className="overflow-x-auto px-0">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-y border-border/30 bg-muted/20 text-xs text-muted-foreground">
                    <th className="px-5 py-2.5 text-left">Asset</th><th className="px-3 text-right">Quantity</th><th className="px-3 text-right">Avg cost</th>
                    <th className="px-3 text-right">Price</th><th className="px-3 text-right">Today</th><th className="px-3 text-right">Market value</th>
                    <th className="px-3 text-right">Unrealised P&L</th><th className="px-5 text-right">Weight</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/20">
                  {a.holdings.map((h: any) => (
                    <tr key={h.id} className="hover:bg-muted/10">
                      <td className="px-5 py-3"><Link href={`/stocks/${h.symbol}`} className="font-mono font-semibold hover:text-primary">{h.symbol}</Link><p className="max-w-[180px] truncate text-xs text-muted-foreground">{h.name}</p></td>
                      <td className="px-3 text-right font-mono">{h.quantity}</td>
                      <td className="px-3 text-right font-mono">{formatCurrency(h.avg_purchase_price)}</td>
                      <td className="px-3 text-right font-mono">{formatCurrency(h.current_price)}</td>
                      <td className={cn("px-3 text-right font-mono text-xs", getPriceChangeClass(h.day_change_pct))}>{formatPercent(h.day_change_pct)}</td>
                      <td className="px-3 text-right font-mono font-medium">{formatCurrency(h.current_value)}</td>
                      <td className={cn("px-3 text-right font-mono", getPriceChangeClass(h.unrealized_pnl))}>{formatCurrency(h.unrealized_pnl)}<span className="block text-xs">{formatPercent(h.unrealized_pnl_pct)}</span></td>
                      <td className="px-5 text-right font-mono text-muted-foreground">{h.weight?.toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </>
      ))}

      {activeId && txns?.length > 0 && (
        <Card>
          <CardHeader title="Transaction history" description="Holdings are rebuilt from this ledger — deleting a transaction recalculates positions." />
          <CardContent className="overflow-x-auto px-0">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-y border-border/30 bg-muted/20 text-xs text-muted-foreground">
                  <th className="px-5 py-2.5 text-left">Date</th><th className="px-3 text-left">Type</th><th className="px-3 text-left">Symbol</th>
                  <th className="px-3 text-right">Quantity</th><th className="px-3 text-right">Price</th><th className="px-3 text-right">Fees</th><th className="px-3 text-right">Total</th><th className="px-5" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border/20">
                {txns.map((t: any) => (
                  <tr key={t.id}>
                    <td className="px-5 py-2.5 text-xs text-muted-foreground">{formatDate(t.transaction_date)}</td>
                    <td className="px-3"><span className={cn("rounded px-1.5 py-0.5 text-[10px] font-bold", t.transaction_type === "BUY" ? "bg-profit/15 text-profit" : "bg-loss/15 text-loss")}>{t.transaction_type}</span></td>
                    <td className="px-3 font-mono font-semibold">{t.symbol}</td>
                    <td className="px-3 text-right font-mono">{t.quantity}</td>
                    <td className="px-3 text-right font-mono">{formatCurrency(t.price)}</td>
                    <td className="px-3 text-right font-mono text-muted-foreground">{formatCurrency(t.fees)}</td>
                    <td className="px-3 text-right font-mono">{formatCurrency(t.quantity * t.price + (t.transaction_type === "BUY" ? t.fees : -t.fees))}</td>
                    <td className="px-5 text-right">
                      <button onClick={() => confirm("Delete this transaction?") && deleteTx.mutate(t.id)} className="text-muted-foreground hover:text-destructive" title="Delete"><Trash2 className="h-3.5 w-3.5" /></button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function TransactionForm({ portfolioId, onDone }: { portfolioId: string; onDone: () => void }) {
  const [symbol, setSymbol] = useState("");
  const [type, setType] = useState<"BUY" | "SELL">("BUY");
  const [quantity, setQuantity] = useState("");
  const [price, setPrice] = useState("");
  const [fees, setFees] = useState("0");
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));

  const { data: quote } = useQuery({
    queryKey: ["quote", symbol],
    queryFn: () => stocksApi.quotes([symbol]).then((r) => r.data[symbol]),
    enabled: !!symbol,
  });
  useEffect(() => {
    if (quote?.price && !price) setPrice(String(quote.price.toFixed(2)));
  }, [quote, price]);

  const save = useMutation({
    mutationFn: () => portfolioApi.addTransaction(portfolioId, {
      symbol, transaction_type: type, quantity: parseFloat(quantity), price: parseFloat(price), fees: parseFloat(fees || "0"),
      transaction_date: new Date(`${date}T15:00:00Z`).toISOString(),
    }),
    onSuccess: () => { toast.success(`${type} ${quantity} ${symbol} recorded`); onDone(); },
    onError: (e) => toast.error(apiError(e, "Failed to record transaction")),
  });

  return (
    <Card className="border-primary/30">
      <CardHeader title="Record a buy or sell" description={symbol && quote ? `${symbol} last price: ${formatCurrency(quote.price)}` : "Search for a symbol — the latest price is filled in automatically"} />
      <CardContent className="grid grid-cols-2 gap-3 md:grid-cols-7">
        <div className="col-span-2">
          {symbol ? (
            <button onClick={() => { setSymbol(""); setPrice(""); }} className="flex h-9 w-full items-center justify-between rounded-md border border-input px-3 font-mono text-sm">
              {symbol} <span className="text-xs text-muted-foreground">change</span>
            </button>
          ) : (
            <SymbolSearch onSelect={setSymbol} placeholder="Symbol" />
          )}
        </div>
        <div className="flex overflow-hidden rounded-md border border-input">
          {(["BUY", "SELL"] as const).map((t) => (
            <button key={t} type="button" onClick={() => setType(t)} className={cn("flex-1 py-2 text-xs font-semibold", type === t ? (t === "BUY" ? "bg-profit text-white" : "bg-loss text-white") : "text-muted-foreground")}>{t}</button>
          ))}
        </div>
        <Input type="number" min="0" step="any" placeholder="Quantity" value={quantity} onChange={(e) => setQuantity(e.target.value)} />
        <Input type="number" min="0" step="any" placeholder="Price" value={price} onChange={(e) => setPrice(e.target.value)} />
        <Input type="date" value={date} max={new Date().toISOString().slice(0, 10)} onChange={(e) => setDate(e.target.value)} />
        <div className="flex gap-2">
          <Input type="number" min="0" step="any" placeholder="Fees" value={fees} onChange={(e) => setFees(e.target.value)} title="Brokerage fees" />
          <Button onClick={() => save.mutate()} disabled={!symbol || !quantity || !price || save.isPending}>{save.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : "Save"}</Button>
        </div>
      </CardContent>
    </Card>
  );
}
