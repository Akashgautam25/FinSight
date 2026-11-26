"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import { useQuery } from "@tanstack/react-query";
import {
  Area, Bar, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { BarChart3, CandlestickChart as CandleIcon, LineChart as LineIcon } from "lucide-react";
import { stocksApi } from "@/lib/api";
import { cn, formatCurrency, formatPercent } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { DemoBadge } from "@/components/common/DemoBadge";

const CandlestickChart = dynamic(() => import("./CandlestickChart"), { ssr: false, loading: () => <Skeleton className="h-[360px]" /> });

export const PERIODS = [
  { label: "1D", value: "1d", interval: "5m" },
  { label: "5D", value: "5d", interval: "30m" },
  { label: "1M", value: "1mo", interval: "1d" },
  { label: "6M", value: "6mo", interval: "1d" },
  { label: "YTD", value: "ytd", interval: "1d" },
  { label: "1Y", value: "1y", interval: "1d" },
  { label: "5Y", value: "5y", interval: "1wk" },
];

const tooltipStyle = { backgroundColor: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 8, fontSize: 12 };
const axisTick = { fontSize: 11, fill: "hsl(var(--muted-foreground))" };

export function StockChartPanel({ symbol, currency = "USD" }: { symbol: string; currency?: string }) {
  const [period, setPeriod] = useState(PERIODS[5]);
  const [mode, setMode] = useState<"line" | "candles">("line");
  const [overlays, setOverlays] = useState({ sma: true, bb: false, volume: true, rsi: true, macd: false });
  const intraday = period.interval.endsWith("m") || period.interval.endsWith("h");
  const wantIndicators = !intraday;

  const { data, isLoading } = useQuery({
    queryKey: ["stock-history", symbol, period.value, period.interval, wantIndicators],
    queryFn: () => stocksApi.getHistory(symbol, period.value, period.interval, wantIndicators).then((r) => r.data),
  });
  const points: any[] = data?.data ?? [];
  const first = points[0]?.close;
  const last = points[points.length - 1]?.close;
  const up = last >= first;
  const color = up ? "#22c55e" : "#ef4444";

  const fmtDate = (v: string) => {
    const d = new Date(intraday && !v.endsWith("Z") ? v + "Z" : v);
    return intraday
      ? d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", timeZone: "UTC" })
      : d.toLocaleDateString([], { month: "short", day: "numeric", ...(period.value === "5y" ? { year: "2-digit" } : {}) });
  };

  const toggle = (k: keyof typeof overlays) => setOverlays((o) => ({ ...o, [k]: !o[k] }));

  return (
    <div className="rounded-xl border border-border/40 bg-card p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-1">
          {PERIODS.map((p) => (
            <Button key={p.label} size="sm" variant="ghost" onClick={() => setPeriod(p)}
              className={cn("h-7 px-2.5 text-xs", period.label === p.label ? "bg-primary/10 text-primary" : "text-muted-foreground")}>
              {p.label}
            </Button>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-1">
          {wantIndicators && (["sma", "bb", "volume", "rsi", "macd"] as const).map((k) => (
            <button key={k} onClick={() => toggle(k)}
              className={cn("rounded-md border px-2 py-1 text-[11px] font-medium uppercase", overlays[k] ? "border-primary/40 bg-primary/10 text-primary" : "border-border/50 text-muted-foreground")}>
              {k === "bb" ? "Bollinger" : k}
            </button>
          ))}
          <div className="ml-2 flex rounded-md border border-border/50">
            <button onClick={() => setMode("line")} className={cn("p-1.5", mode === "line" && "bg-accent")} title="Area chart"><LineIcon className="h-3.5 w-3.5" /></button>
            <button onClick={() => setMode("candles")} className={cn("p-1.5", mode === "candles" && "bg-accent")} title="Candlestick chart"><CandleIcon className="h-3.5 w-3.5" /></button>
          </div>
        </div>
      </div>

      {data && points.length > 1 && (
        <div className="mb-3 flex items-center gap-3 text-xs text-muted-foreground">
          <span>Period return: <span className={up ? "text-profit" : "text-loss"}>{formatPercent(data.period_return_pct)}</span></span>
          <DemoBadge show={data.is_demo} />
        </div>
      )}

      {isLoading ? (
        <Skeleton className="h-[360px]" />
      ) : points.length === 0 ? (
        <div className="flex h-64 flex-col items-center justify-center gap-2 text-sm text-muted-foreground">
          <BarChart3 className="h-6 w-6" /> No chart data available for this period.
        </div>
      ) : mode === "candles" ? (
        <CandlestickChart data={points} intraday={intraday} showSma={overlays.sma && wantIndicators} />
      ) : (
        <ResponsiveContainer width="100%" height={340}>
          <ComposedChart data={points} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id={`grad-${symbol}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={color} stopOpacity={0.18} />
                <stop offset="95%" stopColor={color} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" strokeOpacity={0.4} />
            <XAxis dataKey="date" tick={axisTick} tickLine={false} axisLine={false} tickFormatter={fmtDate} minTickGap={40} />
            <YAxis yAxisId="price" domain={["auto", "auto"]} tick={axisTick} tickLine={false} axisLine={false} width={60} tickFormatter={(v) => v.toFixed(0)} />
            {overlays.volume && <YAxis yAxisId="vol" hide domain={[0, (max: number) => max * 5]} />}
            <Tooltip contentStyle={tooltipStyle} labelFormatter={(l) => fmtDate(String(l))}
              formatter={(v: number, name: string) => [name === "volume" ? v.toLocaleString() : formatCurrency(v, currency), name.replace("_", " ").toUpperCase()]} />
            {overlays.volume && <Bar yAxisId="vol" dataKey="volume" fill="hsl(var(--muted-foreground))" opacity={0.25} />}
            {overlays.bb && wantIndicators && <Line yAxisId="price" dataKey="bb_upper" stroke="#64748b" strokeDasharray="4 3" dot={false} strokeWidth={1} />}
            {overlays.bb && wantIndicators && <Line yAxisId="price" dataKey="bb_lower" stroke="#64748b" strokeDasharray="4 3" dot={false} strokeWidth={1} />}
            <Area yAxisId="price" type="monotone" dataKey="close" stroke={color} strokeWidth={1.6} fill={`url(#grad-${symbol})`} dot={false} />
            {overlays.sma && wantIndicators && <Line yAxisId="price" dataKey="sma_20" stroke="#f59e0b" dot={false} strokeWidth={1} />}
            {overlays.sma && wantIndicators && <Line yAxisId="price" dataKey="sma_50" stroke="#a855f7" dot={false} strokeWidth={1} />}
            {overlays.sma && wantIndicators && <Line yAxisId="price" dataKey="sma_200" stroke="#06b6d4" dot={false} strokeWidth={1} />}
          </ComposedChart>
        </ResponsiveContainer>
      )}

      {wantIndicators && points.length > 0 && overlays.rsi && (
        <div className="mt-4">
          <p className="mb-1 text-xs font-medium text-muted-foreground">RSI (14)</p>
          <ResponsiveContainer width="100%" height={100}>
            <ComposedChart data={points} margin={{ top: 0, right: 8, left: 0, bottom: 0 }}>
              <XAxis dataKey="date" hide />
              <YAxis domain={[0, 100]} ticks={[30, 70]} tick={axisTick} tickLine={false} axisLine={false} width={60} />
              <ReferenceLine y={70} stroke="#ef4444" strokeDasharray="3 3" strokeOpacity={0.6} />
              <ReferenceLine y={30} stroke="#22c55e" strokeDasharray="3 3" strokeOpacity={0.6} />
              <Tooltip contentStyle={tooltipStyle} labelFormatter={(l) => fmtDate(String(l))} formatter={(v: number) => [v.toFixed(1), "RSI"]} />
              <Line dataKey="rsi_14" stroke="#3b82f6" dot={false} strokeWidth={1.2} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}
      {wantIndicators && points.length > 0 && overlays.macd && (
        <div className="mt-4">
          <p className="mb-1 text-xs font-medium text-muted-foreground">MACD (12, 26, 9)</p>
          <ResponsiveContainer width="100%" height={110}>
            <ComposedChart data={points} margin={{ top: 0, right: 8, left: 0, bottom: 0 }}>
              <XAxis dataKey="date" hide />
              <YAxis tick={axisTick} tickLine={false} axisLine={false} width={60} tickFormatter={(v) => v.toFixed(1)} />
              <ReferenceLine y={0} stroke="hsl(var(--border))" />
              <Tooltip contentStyle={tooltipStyle} labelFormatter={(l) => fmtDate(String(l))} formatter={(v: number, n: string) => [v.toFixed(3), n]} />
              <Bar dataKey="macd_hist" fill="#64748b" opacity={0.5} />
              <Line dataKey="macd" stroke="#3b82f6" dot={false} strokeWidth={1.2} />
              <Line dataKey="macd_signal" stroke="#f59e0b" dot={false} strokeWidth={1.2} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}
      <p className="mt-3 text-xs text-muted-foreground">
        {wantIndicators && overlays.sma && <><span className="text-amber-500">━</span> SMA 20 · <span className="text-purple-500">━</span> SMA 50 · <span className="text-cyan-500">━</span> SMA 200 · </>}
        Source: {data?.is_demo ? "simulated data" : "Yahoo Finance"} (may be delayed 15–20 minutes).
      </p>
    </div>
  );
}
