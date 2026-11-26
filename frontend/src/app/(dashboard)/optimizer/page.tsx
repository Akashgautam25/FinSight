"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { CartesianGrid, Legend, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from "recharts";
import { Info, Loader2, PieChart as PieIcon } from "lucide-react";
import { toast } from "sonner";
import { apiError, optimizationApi } from "@/lib/api";
import { CHART_COLORS, formatCurrency } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { CorrelationHeatmap } from "@/components/charts/CorrelationHeatmap";
import { DemoBadge } from "@/components/common/DemoBadge";
import { EmptyState } from "@/components/common/EmptyState";
import { PageHeader } from "@/components/common/PageHeader";

const PRESETS: Record<string, string> = {
  "US tech": "AAPL, MSFT, NVDA, GOOGL, AMZN",
  "Diversified US": "AAPL, JPM, JNJ, XOM, KO, WMT",
  "India large caps": "RELIANCE.NS, TCS.NS, INFY.NS, HDFCBANK.NS",
};
const pct = (v: number) => `${(v * 100).toFixed(1)}%`;

export default function OptimizerPage() {
  const [symbols, setSymbols] = useState(PRESETS["Diversified US"]);
  const [period, setPeriod] = useState("2y");
  const [maxWeight, setMaxWeight] = useState("60");
  const [rf, setRf] = useState("5");
  const [amount, setAmount] = useState("10000");
  const [data, setData] = useState<any>(null);

  const run = useMutation({
    mutationFn: () => optimizationApi.efficientFrontier({
      symbols: symbols.split(/[,\s]+/).map((s) => s.trim().toUpperCase()).filter(Boolean),
      period, risk_free_rate: Number(rf) / 100, min_weight: 0, max_weight: Number(maxWeight) / 100,
      investment_amount: amount ? Number(amount) : undefined,
    }),
    onSuccess: (res) => {
      setData(res.data);
      if (res.data.excluded_symbols?.length) toast.warning(`No data for: ${res.data.excluded_symbols.join(", ")}`);
    },
    onError: (e) => toast.error(apiError(e, "Optimization failed")),
  });

  return (
    <div className="space-y-6">
      <PageHeader title="Portfolio Optimizer" description="Modern Portfolio Theory (Markowitz): efficient frontier, maximum Sharpe ratio and minimum volatility allocations" />

      <Card>
        <CardContent className="space-y-4 pt-5">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-6">
            <div className="space-y-1.5 md:col-span-3">
              <label className="text-xs font-semibold text-muted-foreground">Tickers (2–15, comma separated)</label>
              <Input value={symbols} onChange={(e) => setSymbols(e.target.value)} placeholder="AAPL, MSFT, JPM…" />
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(PRESETS).map(([k, v]) => (
                  <button key={k} onClick={() => setSymbols(v)} className="rounded-md border border-border/50 px-2 py-0.5 text-[11px] text-muted-foreground hover:border-primary/40 hover:text-foreground">{k}</button>
                ))}
              </div>
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-muted-foreground">History</label>
              <Select value={period} onChange={(e) => setPeriod(e.target.value)}>
                <option value="1y">1 year</option><option value="2y">2 years</option><option value="5y">5 years</option>
              </Select>
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-muted-foreground">Max weight per asset (%)</label>
              <Input type="number" min="10" max="100" value={maxWeight} onChange={(e) => setMaxWeight(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-muted-foreground">Risk-free rate (%)</label>
              <Input type="number" step="0.1" min="0" max="25" value={rf} onChange={(e) => setRf(e.target.value)} />
            </div>
          </div>
          <div className="flex flex-wrap items-end gap-4">
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-muted-foreground">Amount to invest (optional)</label>
              <Input type="number" min="0" value={amount} onChange={(e) => setAmount(e.target.value)} className="w-44" />
            </div>
            <Button onClick={() => run.mutate()} disabled={run.isPending}>
              {run.isPending ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Optimizing…</> : "Run optimization"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {!data ? (
        <Card><EmptyState icon={PieIcon} title="Choose a set of stocks and run the optimizer" description="FinSight estimates expected returns and a shrunk covariance matrix from historical prices, then solves for the optimal weights." /></Card>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            {data.observations} trading days · {data.methodology} <DemoBadge show={data.is_demo} />
          </div>
          <div className="grid grid-cols-1 gap-6 xl:grid-cols-5">
            <Card className="xl:col-span-3">
              <CardHeader title="Efficient frontier" description="Grey: 1,500 random portfolios · blue: efficient frontier · coloured dots: individual stocks · stars: optimal portfolios" />
              <CardContent>
                <ResponsiveContainer width="100%" height={340}>
                  <ScatterChart margin={{ top: 10, right: 10, bottom: 10, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" strokeOpacity={0.4} />
                    <XAxis type="number" dataKey="volatility" name="Volatility" tickFormatter={pct} tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} label={{ value: "Volatility (risk)", position: "insideBottom", offset: -5, fontSize: 11, fill: "hsl(var(--muted-foreground))" }} domain={["auto", "auto"]} />
                    <YAxis type="number" dataKey="expected_return" name="Return" tickFormatter={pct} tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} width={50} domain={["auto", "auto"]} />
                    <ZAxis range={[20, 20]} />
                    <Tooltip
                      cursor={{ strokeDasharray: "3 3" }}
                      content={({ payload }) => {
                        const p: any = payload?.[0]?.payload;
                        if (!p) return null;
                        return (
                          <div className="space-y-0.5 rounded border border-border bg-popover p-2 text-xs">
                            {(p.label || p.symbol) && <p className="font-bold text-primary">{p.label || p.symbol}</p>}
                            <p>Return: {pct(p.expected_return)}</p>
                            <p>Volatility: {pct(p.volatility)}</p>
                            {p.sharpe_ratio != null && <p>Sharpe: {p.sharpe_ratio.toFixed(2)}</p>}
                          </div>
                        );
                      }}
                    />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Scatter name="Random portfolios" data={data.random_portfolios} fill="#64748b" fillOpacity={0.25} shape="circle" />
                    <Scatter name="Efficient frontier" data={data.frontier} fill="#3b82f6" line={{ stroke: "#3b82f6", strokeWidth: 2 }} shape="circle" />
                    <Scatter name="Stocks" data={data.assets} fill="#f59e0b" shape="diamond" />
                    <Scatter name="Max Sharpe" data={[data.max_sharpe]} fill="#22c55e" shape="star" legendType="star" />
                    <Scatter name="Min volatility" data={[data.min_volatility]} fill="#a855f7" shape="star" legendType="star" />
                  </ScatterChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
            <div className="space-y-6 xl:col-span-2">
              {[{ p: data.max_sharpe, color: "#22c55e", title: "Maximum Sharpe ratio" }, { p: data.min_volatility, color: "#a855f7", title: "Minimum volatility" }].map(({ p, color, title }) => (
                <Card key={title}>
                  <CardHeader title={title} description={`Return ${pct(p.expected_return)} · Volatility ${pct(p.volatility)} · Sharpe ${p.sharpe_ratio.toFixed(2)}`} />
                  <CardContent className="space-y-2">
                    {Object.entries(p.weights).sort((a: any, b: any) => b[1] - a[1]).map(([sym, w]: [string, any]) => (
                      <div key={sym} className="flex items-center gap-3 text-xs">
                        <span className="w-24 font-mono">{sym}</span>
                        <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted"><div className="h-full" style={{ width: `${w * 100}%`, background: color }} /></div>
                        <span className="w-12 text-right font-mono">{(w * 100).toFixed(1)}%</span>
                        {p.allocation?.shares?.[sym] != null && <span className="w-16 text-right font-mono text-muted-foreground">{p.allocation.shares[sym]} sh</span>}
                      </div>
                    ))}
                    {p.allocation && (
                      <p className="pt-1 text-[11px] text-muted-foreground">
                        Whole-share allocation of {formatCurrency(Number(amount))}: invested {formatCurrency(p.allocation.invested)}, leftover cash {formatCurrency(p.allocation.leftover_cash)}.
                      </p>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
            <Card>
              <CardHeader title="Correlation of daily returns" description="Lower correlations → more diversification benefit" />
              <CardContent><CorrelationHeatmap symbols={data.correlation_matrix.symbols} matrix={data.correlation_matrix.matrix} /></CardContent>
            </Card>
            <Card>
              <CardHeader title="Individual assets" description="Historical annualised return (CAGR) and volatility" />
              <CardContent>
                <table className="w-full text-sm">
                  <thead><tr className="border-b border-border/30 text-xs text-muted-foreground"><th className="py-2 text-left">Stock</th><th className="text-right">Return</th><th className="text-right">Volatility</th><th className="text-right">Sharpe</th></tr></thead>
                  <tbody className="divide-y divide-border/20">
                    {data.assets.map((a: any, i: number) => (
                      <tr key={a.symbol}>
                        <td className="py-2 font-mono font-semibold" style={{ color: CHART_COLORS[i % CHART_COLORS.length] }}>{a.symbol}</td>
                        <td className="text-right font-mono">{pct(a.expected_return)}</td>
                        <td className="text-right font-mono">{pct(a.volatility)}</td>
                        <td className="text-right font-mono">{a.sharpe_ratio?.toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </CardContent>
            </Card>
          </div>
        </>
      )}

      <div className="flex items-start gap-3 rounded-xl border border-border/40 bg-muted/20 p-4">
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
        <p className="text-xs leading-relaxed text-muted-foreground">
          <strong>Assumptions:</strong> expected returns are historical CAGRs and risk is the Ledoit-Wolf shrunk covariance — both are noisy estimates, so optimal weights
          can change a lot with the time window. MPT assumes roughly normal returns and stable correlations; real markets have fat tails and correlations rise in crises.
          No transaction costs or taxes are modelled. Educational use only.
        </p>
      </div>
    </div>
  );
}
