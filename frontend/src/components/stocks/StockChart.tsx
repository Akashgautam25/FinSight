// Stock chart with period selector — uses Recharts
"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { stocksApi } from "@/lib/api";
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend,
} from "recharts";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface Period {
  label: string;
  value: string;
  interval: string;
}

export function StockChartPanel({
  symbol,
  periods,
  currency = "USD",
}: {
  symbol: string;
  periods: Period[];
  currency?: string;
}) {
  const [selected, setSelected] = useState(periods[5] || periods[0]);

  const { data, isLoading } = useQuery({
    queryKey: ["stock-history", symbol, selected.value, selected.interval],
    queryFn: () =>
      stocksApi.getHistory(symbol, selected.value, selected.interval).then((r) => r.data),
    enabled: !!symbol,
  });

  const chartData = data?.data || [];
  const firstClose = chartData[0]?.close;
  const lastClose = chartData[chartData.length - 1]?.close;
  const isPositive = lastClose >= firstClose;

  const color = isPositive ? "#22c55e" : "#ef4444";

  return (
    <div className="rounded-xl border border-border/40 bg-card p-5">
      {/* Period selector */}
      <div className="flex gap-1 mb-5 flex-wrap">
        {periods.map((period) => (
          <Button
            key={period.value}
            size="sm"
            variant="ghost"
            onClick={() => setSelected(period)}
            className={cn(
              "h-7 px-3 text-xs",
              selected.value === period.value
                ? "bg-primary/10 text-primary"
                : "text-muted-foreground"
            )}
          >
            {period.label}
          </Button>
        ))}
      </div>

      {isLoading ? (
        <div className="h-64 bg-muted/30 rounded-lg animate-pulse" />
      ) : chartData.length === 0 ? (
        <div className="h-64 flex items-center justify-center text-muted-foreground text-sm">
          No chart data available for this period.
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={280}>
          <AreaChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id={`gradient-${symbol}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={color} stopOpacity={0.15} />
                <stop offset="95%" stopColor={color} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" strokeOpacity={0.4} />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(val) => {
                const d = new Date(val);
                return selected.interval === "5m" || selected.interval === "1h"
                  ? d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
                  : d.toLocaleDateString([], { month: "short", day: "numeric" });
              }}
            />
            <YAxis
              domain={["auto", "auto"]}
              tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(val) => `${val.toFixed(0)}`}
              width={55}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "hsl(var(--card))",
                border: "1px solid hsl(var(--border))",
                borderRadius: "8px",
                fontSize: "12px",
              }}
              formatter={(value: number) => [
                `${currency} ${value.toFixed(2)}`,
                "Close",
              ]}
            />
            <Area
              type="monotone"
              dataKey="close"
              stroke={color}
              strokeWidth={1.5}
              fill={`url(#gradient-${symbol})`}
              dot={false}
              activeDot={{ r: 4, fill: color }}
            />
          </AreaChart>
        </ResponsiveContainer>
      )}

      <p className="text-xs text-muted-foreground mt-3">
        Data may be delayed by 15–20 minutes. Source: yfinance.
      </p>
    </div>
  );
}
