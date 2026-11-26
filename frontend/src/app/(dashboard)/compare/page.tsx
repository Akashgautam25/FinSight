"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Loader2, X } from "lucide-react";
import { stocksApi } from "@/lib/api";
import { CHART_COLORS, cn, formatCurrency, formatLargeNumber, formatNumber, formatPercent, formatRatio } from "@/lib/utils";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { CorrelationHeatmap } from "@/components/charts/CorrelationHeatmap";
import { DemoBadge } from "@/components/common/DemoBadge";
import { PageHeader } from "@/components/common/PageHeader";
import { SymbolSearch } from "@/components/common/SymbolSearch";

export default function ComparePage() {
  const [symbols, setSymbols] = useState(["AAPL", "MSFT", "GOOGL"]);
  const [period, setPeriod] = useState("1y");

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["compare", symbols, period],
    queryFn: () => stocksApi.compare(symbols, period).then((r) => r.data),
    enabled: symbols.length > 0,
  });
  const c = data?.comparison ?? {};
  const anyDemo = symbols.some((s) => c[s]?.detail?.is_demo);

  const rows: [string, (s: string) => string, string?][] = [
    ["Company", (s) => c[s]?.detail?.name ?? "—"],
    ["Sector", (s) => c[s]?.detail?.sector ?? "—"],
    ["Price", (s) => formatCurrency(c[s]?.detail?.current_price, c[s]?.detail?.currency)],
    [`Return (${period})`, (s) => formatPercent(c[s]?.stats?.period_return_pct), "return"],
    ["Volatility (ann.)", (s) => (c[s]?.stats?.volatility_pct != null ? `${c[s].stats.volatility_pct}%` : "—")],
    ["Max drawdown", (s) => (c[s]?.stats?.max_drawdown_pct != null ? `${c[s].stats.max_drawdown_pct}%` : "—")],
    ["Sharpe ratio", (s) => formatNumber(c[s]?.stats?.sharpe_ratio)],
    ["Market cap", (s) => formatLargeNumber(c[s]?.detail?.metrics?.market_cap)],
    ["P/E (trailing)", (s) => formatNumber(c[s]?.detail?.metrics?.pe_ratio)],
    ["Beta", (s) => formatNumber(c[s]?.detail?.metrics?.beta)],
    ["Profit margin", (s) => formatRatio(c[s]?.detail?.metrics?.profit_margin)],
    ["Return on equity", (s) => formatRatio(c[s]?.detail?.metrics?.roe)],
    ["Revenue growth", (s) => formatRatio(c[s]?.detail?.metrics?.revenue_growth)],
    ["Dividend yield", (s) => (c[s]?.detail?.metrics?.dividend_yield ? formatRatio(c[s].detail.metrics.dividend_yield) : "—")],
  ];

  return (
    <div className="space-y-6">
      <PageHeader title="Compare Stocks" description="Benchmark up to 5 companies on performance, risk, valuation and profitability" />
      <div className="flex flex-col gap-3 md:flex-row md:items-center">
        <SymbolSearch onSelect={(s) => !symbols.includes(s) && symbols.length < 5 && setSymbols([...symbols, s])} placeholder={symbols.length >= 5 ? "Maximum of 5 stocks" : "Add a stock to compare"} className="max-w-sm flex-1" />
        <div className="flex flex-wrap gap-2">
          {symbols.map((s, i) => (
            <span key={s} className="inline-flex items-center gap-1.5 rounded-md border border-border/50 bg-card px-2 py-1 font-mono text-xs" style={{ borderColor: CHART_COLORS[i] }}>
              {s}
              <button onClick={() => setSymbols(symbols.filter((x) => x !== s))} aria-label={`Remove ${s}`}><X className="h-3 w-3" /></button>
            </span>
          ))}
        </div>
        <Select value={period} onChange={(e) => setPeriod(e.target.value)} className="w-32 md:ml-auto">
          {["3mo", "6mo", "1y", "2y", "5y"].map((p) => <option key={p} value={p}>{p}</option>)}
        </Select>
        {isFetching && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}
      </div>

      {isLoading ? <div className="h-80 animate-pulse rounded-xl bg-muted/30" /> : data && (
        <>
          <Card>
            <CardHeader title={`Relative performance (${period})`} description="Cumulative return from the start of the period" action={<DemoBadge show={anyDemo} />} />
            <CardContent>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={data.performance}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" strokeOpacity={0.4} />
                  <XAxis dataKey="date" tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} tickLine={false} axisLine={false} minTickGap={50} />
                  <YAxis tickFormatter={(v) => `${v}%`} tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} tickLine={false} axisLine={false} width={45} />
                  <ReferenceLine y={0} stroke="hsl(var(--border))" />
                  <Tooltip contentStyle={{ backgroundColor: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 8, fontSize: 12 }} formatter={(v: number) => `${v.toFixed(2)}%`} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  {symbols.map((s, i) => <Line key={s} dataKey={s} stroke={CHART_COLORS[i]} dot={false} strokeWidth={1.6} />)}
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
          <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
            <Card className="overflow-x-auto xl:col-span-2">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border/30 bg-muted/20">
                    <th className="px-5 py-3 text-left text-xs font-semibold text-muted-foreground">Metric</th>
                    {symbols.map((s, i) => <th key={s} className="px-4 py-3 text-right font-mono text-xs font-bold" style={{ color: CHART_COLORS[i] }}>{s}</th>)}
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/20">
                  {rows.map(([label, fn, kind]) => (
                    <tr key={label} className="hover:bg-muted/10">
                      <td className="px-5 py-2.5 text-muted-foreground">{label}</td>
                      {symbols.map((s) => {
                        const v = fn(s);
                        return <td key={s} className={cn("max-w-[160px] truncate px-4 py-2.5 text-right font-mono", kind === "return" && (v.startsWith("+") ? "text-profit" : v.startsWith("-") ? "text-loss" : ""))}>{v}</td>;
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
            {data.correlation && (
              <Card>
                <CardHeader title="Return correlation" description="Daily returns over the period" />
                <CardContent><CorrelationHeatmap symbols={data.correlation.symbols} matrix={data.correlation.matrix} /></CardContent>
              </Card>
            )}
          </div>
        </>
      )}
    </div>
  );
}
