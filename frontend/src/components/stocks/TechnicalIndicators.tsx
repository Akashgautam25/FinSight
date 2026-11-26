"use client";

import { useQuery } from "@tanstack/react-query";
import { stocksApi } from "@/lib/api";
import { cn, formatNumber } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";

const SIGNAL_STYLE: Record<string, string> = {
  bullish: "text-profit bg-profit/10 border-profit/20",
  bearish: "text-loss bg-loss/10 border-loss/20",
  neutral: "text-muted-foreground bg-muted/40 border-border/40",
};

export function TechnicalIndicatorsPanel({ symbol }: { symbol: string }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["technical", symbol],
    queryFn: () => stocksApi.getTechnical(symbol).then((r) => r.data),
  });

  if (isLoading) return <div className="grid grid-cols-2 gap-3 md:grid-cols-4">{Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-16" />)}</div>;
  if (error || !data) return <p className="p-4 text-sm text-muted-foreground">Technical indicators are unavailable — at least 35 trading days of history are required.</p>;

  const values: [string, number | null, number?][] = [
    ["Close", data.close], ["SMA 20", data.sma_20], ["SMA 50", data.sma_50], ["SMA 200", data.sma_200],
    ["EMA 12", data.ema_12], ["EMA 26", data.ema_26], ["RSI (14)", data.rsi_14, 1], ["ATR (14)", data.atr_14],
    ["MACD", data.macd, 3], ["MACD signal", data.macd_signal, 3], ["MACD histogram", data.macd_hist, 3], ["30-day volatility", data.volatility_30d, 1],
    ["Bollinger upper", data.bb_upper], ["Bollinger middle", data.bb_middle], ["Bollinger lower", data.bb_lower],
  ];

  return (
    <div className="space-y-4">
      <div className={cn("flex flex-wrap items-center justify-between gap-3 rounded-xl border p-4", SIGNAL_STYLE[data.overall_signal])}>
        <div>
          <p className="text-xs uppercase tracking-wide opacity-80">Overall technical picture · {data.date}</p>
          <p className="text-xl font-bold capitalize">{data.overall_signal}</p>
        </div>
        <p className="max-w-md text-xs opacity-80">
          {data.signals.filter((s: any) => s.signal === "bullish").length} bullish · {data.signals.filter((s: any) => s.signal === "bearish").length} bearish ·{" "}
          {data.signals.filter((s: any) => s.signal === "neutral").length} neutral signals. A summary of indicators — not a trading recommendation.
        </p>
      </div>
      <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
        {data.signals.map((s: any) => (
          <div key={s.indicator} className="flex items-start gap-3 rounded-lg border border-border/40 bg-card p-3">
            <span className={cn("rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase", SIGNAL_STYLE[s.signal])}>{s.signal}</span>
            <div>
              <p className="text-sm font-medium">{s.indicator}</p>
              <p className="text-xs text-muted-foreground">{s.detail}</p>
            </div>
          </div>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-2 md:grid-cols-3 lg:grid-cols-5">
        {values.map(([label, v, digits]) => (
          <div key={label} className="rounded-lg border border-border/30 bg-card p-3">
            <p className="text-xs text-muted-foreground">{label}</p>
            <p className="mt-0.5 font-mono text-sm font-semibold">{formatNumber(v, digits ?? 2)}{label.includes("volatility") && v != null ? "%" : ""}</p>
          </div>
        ))}
      </div>
      <p className="rounded-lg border border-border/30 bg-muted/20 p-3 text-xs text-muted-foreground">
        RSI uses Wilder's smoothing: below 30 suggests oversold, above 70 overbought. MACD above its signal line indicates positive momentum.
        Price above the 200-day average is generally read as a long-term uptrend. All indicators are computed only from past prices.
      </p>
    </div>
  );
}
