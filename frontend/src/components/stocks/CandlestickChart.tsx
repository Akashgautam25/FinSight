"use client";

import { useEffect, useRef } from "react";
import { useTheme } from "next-themes";

type Point = { date: string; open: number; high: number; low: number; close: number; volume?: number; sma_20?: number; sma_50?: number };

/** TradingView lightweight-charts candlestick view with volume and SMA overlays. */
export default function CandlestickChart({ data, intraday, showSma }: { data: Point[]; intraday: boolean; showSma: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const { resolvedTheme } = useTheme();

  useEffect(() => {
    if (!ref.current || !data.length) return;
    let disposed = false;
    let cleanup = () => {};
    import("lightweight-charts").then(({ createChart, CrosshairMode }) => {
      if (disposed || !ref.current) return;
      const dark = resolvedTheme !== "light";
      const chart = createChart(ref.current, {
        height: 360,
        layout: { background: { color: "transparent" }, textColor: dark ? "#94a3b8" : "#475569", fontSize: 11 },
        grid: { vertLines: { color: dark ? "#1e293b" : "#e2e8f0" }, horzLines: { color: dark ? "#1e293b" : "#e2e8f0" } },
        rightPriceScale: { borderVisible: false },
        timeScale: { borderVisible: false, timeVisible: intraday, secondsVisible: false },
        crosshair: { mode: CrosshairMode.Normal },
        autoSize: true,
      });
      const time = (d: string) => (intraday ? (Math.floor(Date.parse(d + (d.endsWith("Z") ? "" : "Z")) / 1000) as any) : (d.slice(0, 10) as any));
      const candles = chart.addCandlestickSeries({
        upColor: "#22c55e", downColor: "#ef4444", borderVisible: false, wickUpColor: "#22c55e", wickDownColor: "#ef4444",
      });
      candles.setData(data.filter((p) => p.open != null).map((p) => ({ time: time(p.date), open: p.open, high: p.high, low: p.low, close: p.close })));
      const volume = chart.addHistogramSeries({ priceFormat: { type: "volume" }, priceScaleId: "" });
      volume.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
      volume.setData(data.map((p) => ({ time: time(p.date), value: p.volume ?? 0, color: p.close >= p.open ? "#22c55e55" : "#ef444455" })));
      if (showSma) {
        for (const [key, color] of [["sma_20", "#f59e0b"], ["sma_50", "#a855f7"]] as const) {
          const series = chart.addLineSeries({ color, lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
          series.setData(data.filter((p) => p[key] != null).map((p) => ({ time: time(p.date), value: p[key] as number })));
        }
      }
      chart.timeScale().fitContent();
      cleanup = () => chart.remove();
    });
    return () => {
      disposed = true;
      cleanup();
    };
  }, [data, intraday, showSma, resolvedTheme]);

  return <div ref={ref} className="h-[360px] w-full" />;
}
