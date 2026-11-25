// Technical indicators display panel
"use client";

import { useQuery } from "@tanstack/react-query";
import { stocksApi } from "@/lib/api";

function IndicatorBadge({ label, value, interpretation }: {
  label: string;
  value: string | null;
  interpretation?: "bullish" | "bearish" | "neutral";
}) {
  const colors = {
    bullish: "text-profit bg-profit/10",
    bearish: "text-loss bg-loss/10",
    neutral: "text-muted-foreground bg-muted/40",
  };
  const colorClass = interpretation ? colors[interpretation] : "bg-muted/40 text-foreground";

  return (
    <div className="p-3 rounded-lg border border-border/30 bg-card">
      <p className="text-xs text-muted-foreground mb-1">{label}</p>
      <p className={`text-sm font-semibold font-mono ${colorClass} px-1.5 py-0.5 rounded inline-block`}>
        {value ?? "—"}
      </p>
    </div>
  );
}

function interpretRsi(rsi: number | null): "bullish" | "bearish" | "neutral" {
  if (!rsi) return "neutral";
  if (rsi < 30) return "bullish"; // Oversold
  if (rsi > 70) return "bearish"; // Overbought
  return "neutral";
}

function interpretMacd(macd: number | null, signal: number | null): "bullish" | "bearish" | "neutral" {
  if (macd == null || signal == null) return "neutral";
  return macd > signal ? "bullish" : "bearish";
}

export function TechnicalIndicatorsPanel({ symbol }: { symbol: string }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["technical", symbol],
    queryFn: () => stocksApi.getTechnical(symbol).then((r) => r.data),
    enabled: !!symbol,
  });

  if (isLoading) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 animate-pulse">
        {Array.from({ length: 12 }).map((_, i) => (
          <div key={i} className="h-16 bg-muted rounded-lg" />
        ))}
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="text-sm text-muted-foreground p-4">
        Technical indicators unavailable — ensure at least 1 year of price history is accessible.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-xs text-muted-foreground">
        As of {data.date} · All indicators computed on historical close prices (no look-ahead).
      </p>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {/* Moving Averages */}
        <IndicatorBadge label="SMA 20" value={data.sma_20?.toFixed(2)} />
        <IndicatorBadge label="SMA 50" value={data.sma_50?.toFixed(2)} />
        <IndicatorBadge label="SMA 200" value={data.sma_200?.toFixed(2)} />
        <IndicatorBadge label="EMA 12" value={data.ema_12?.toFixed(2)} />
        <IndicatorBadge label="EMA 26" value={data.ema_26?.toFixed(2)} />

        {/* RSI */}
        <IndicatorBadge
          label="RSI (14)"
          value={data.rsi_14?.toFixed(2)}
          interpretation={interpretRsi(data.rsi_14)}
        />

        {/* MACD */}
        <IndicatorBadge
          label="MACD"
          value={data.macd?.toFixed(4)}
          interpretation={interpretMacd(data.macd, data.macd_signal)}
        />
        <IndicatorBadge label="MACD Signal" value={data.macd_signal?.toFixed(4)} />
        <IndicatorBadge label="MACD Hist" value={data.macd_hist?.toFixed(4)} />

        {/* Bollinger Bands */}
        <IndicatorBadge label="BB Upper" value={data.bb_upper?.toFixed(2)} />
        <IndicatorBadge label="BB Middle" value={data.bb_middle?.toFixed(2)} />
        <IndicatorBadge label="BB Lower" value={data.bb_lower?.toFixed(2)} />

        {/* ATR */}
        <IndicatorBadge label="ATR (14)" value={data.atr_14?.toFixed(4)} />
      </div>

      <div className="p-3 rounded-lg bg-muted/20 border border-border/30">
        <p className="text-xs text-muted-foreground">
          <strong>RSI interpretation:</strong> {'<'}30 = potentially oversold, {'>'}70 = potentially overbought.
          MACD above signal line = potential bullish momentum. These are indicators, not trading signals.
          Always conduct comprehensive research before making financial decisions.
        </p>
      </div>
    </div>
  );
}
