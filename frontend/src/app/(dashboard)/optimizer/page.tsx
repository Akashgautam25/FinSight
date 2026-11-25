// Quantitative Portfolio Optimizer page
"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { optimizationApi } from "@/lib/api";
import { formatPercent } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PieChart as PieIcon, LineChart, Loader2, Info } from "lucide-react";
import {
  ResponsiveContainer, ScatterChart, Scatter, XAxis, YAxis,
  CartesianGrid, Tooltip, Cell,
} from "recharts";

export default function OptimizerPage() {
  const [symbolsInput, setSymbolsInput] = useState("AAPL, MSFT, GOOGL, AMZN, NVDA");
  const [period, setPeriod] = useState("2y");
  const [frontierData, setFrontierData] = useState<any>(null);

  const optimizeMutation = useMutation({
    mutationFn: () => {
      const symbols = symbolsInput.split(",").map((s) => s.trim().toUpperCase()).filter(Boolean);
      return optimizationApi.efficientFrontier({
        symbols,
        period,
        risk_free_rate: 0.05,
        min_weight: 0.0,
        max_weight: 1.0,
      });
    },
    onSuccess: (res) => {
      setFrontierData(res.data);
    },
  });

  const frontierPoints = frontierData?.efficient_frontier || [];
  const maxSharpePoint = frontierPoints.find((p: any) => p.label === "Max Sharpe");
  const minVolPoint = frontierPoints.find((p: any) => p.label === "Min Volatility");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Portfolio Optimizer</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Modern Portfolio Theory (Markowitz), Efficient Frontier simulation, and Maximum Sharpe allocation
        </p>
      </div>

      {/* Input Form */}
      <div className="p-5 rounded-xl border border-border/40 bg-card space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="md:col-span-2 space-y-1.5">
            <label className="text-xs font-semibold text-muted-foreground">Asset Tickers (Comma-separated)</label>
            <Input
              value={symbolsInput}
              onChange={(e) => setSymbolsInput(e.target.value)}
              placeholder="e.g. AAPL, MSFT, NVDA, GOOGL"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-muted-foreground">Lookback Period</label>
            <select
              value={period}
              onChange={(e) => setPeriod(e.target.value)}
              className="w-full h-9 rounded-md border border-input bg-background/50 px-3 text-sm"
            >
              <option value="1y">1 Year</option>
              <option value="2y">2 Years</option>
              <option value="5y">5 Years</option>
            </select>
          </div>
        </div>

        <Button
          onClick={() => optimizeMutation.mutate()}
          disabled={optimizeMutation.isPending}
          className="w-full sm:w-auto"
        >
          {optimizeMutation.isPending ? (
            <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Simulating Markowitz Frontier...</>
          ) : (
            "Run Optimization"
          )}
        </Button>
      </div>

      {/* Results Section */}
      {frontierPoints.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Efficient Frontier Chart */}
          <div className="p-5 rounded-xl border border-border/40 bg-card space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-sm">Efficient Frontier (Risk vs Expected Return)</h3>
              <span className="text-xs text-muted-foreground">20 Samples</span>
            </div>
            <ResponsiveContainer width="100%" height={260}>
              <ScatterChart margin={{ top: 10, right: 10, bottom: 10, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" strokeOpacity={0.4} />
                <XAxis
                  type="number"
                  dataKey="volatility"
                  name="Volatility (Risk)"
                  unit="%"
                  tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                  tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                />
                <YAxis
                  type="number"
                  dataKey="expected_return"
                  name="Expected Return"
                  unit="%"
                  tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                  tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                  width={45}
                />
                <Tooltip
                  cursor={{ strokeDasharray: '3 3' }}
                  content={({ payload }) => {
                    if (payload && payload.length) {
                      const data = payload[0].payload;
                      return (
                        <div className="bg-popover p-2 rounded border border-border text-xs space-y-1">
                          {data.label && <p className="font-bold text-primary">{data.label}</p>}
                          <p>Return: {(data.expected_return * 100).toFixed(2)}%</p>
                          <p>Risk (Vol): {(data.volatility * 100).toFixed(2)}%</p>
                          <p>Sharpe: {data.sharpe_ratio.toFixed(2)}</p>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <Scatter name="Portfolios" data={frontierPoints} fill="#3b82f6" />
              </ScatterChart>
            </ResponsiveContainer>
          </div>

          {/* Optimal Weights Snapshot */}
          <div className="p-5 rounded-xl border border-border/40 bg-card space-y-4">
            <h3 className="font-semibold text-sm">Optimal Weight Allocations</h3>

            {maxSharpePoint && (
              <div className="space-y-2">
                <div className="flex justify-between text-xs">
                  <span className="font-bold text-primary">Maximum Sharpe Ratio Allocation</span>
                  <span className="font-mono text-muted-foreground">Sharpe: {maxSharpePoint.sharpe_ratio?.toFixed(2)}</span>
                </div>
                <div className="space-y-1.5">
                  {Object.entries(maxSharpePoint.weights || {}).map(([sym, w]: [string, any]) => (
                    <div key={sym} className="flex items-center justify-between text-xs">
                      <span className="font-mono">{sym}</span>
                      <div className="flex items-center gap-2 w-48">
                        <div className="h-1.5 bg-muted rounded-full flex-1 overflow-hidden">
                          <div className="h-full bg-primary" style={{ width: `${w * 100}%` }} />
                        </div>
                        <span className="font-mono w-10 text-right">{(w * 100).toFixed(1)}%</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {minVolPoint && (
              <div className="space-y-2 pt-3 border-t border-border/30">
                <div className="flex justify-between text-xs">
                  <span className="font-bold text-profit">Minimum Volatility Allocation</span>
                  <span className="font-mono text-muted-foreground">Vol: {(minVolPoint.volatility * 100).toFixed(1)}%</span>
                </div>
                <div className="space-y-1.5">
                  {Object.entries(minVolPoint.weights || {}).map(([sym, w]: [string, any]) => (
                    <div key={sym} className="flex items-center justify-between text-xs">
                      <span className="font-mono">{sym}</span>
                      <div className="flex items-center gap-2 w-48">
                        <div className="h-1.5 bg-muted rounded-full flex-1 overflow-hidden">
                          <div className="h-full bg-profit" style={{ width: `${w * 100}%` }} />
                        </div>
                        <span className="font-mono w-10 text-right">{(w * 100).toFixed(1)}%</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Mathematical assumptions notice */}
      <div className="p-4 rounded-xl border border-border/40 bg-muted/20 flex gap-3 items-start">
        <Info className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5" />
        <p className="text-xs text-muted-foreground leading-relaxed">
          <strong>MPT Assumptions:</strong> Modern Portfolio Theory assumes asset returns are normally distributed and historical covariance predicts future variance.
          Optimized weights maximize expected return per unit of volatility under historical sample mean conditions. Realized market distributions often exhibit fat tails and non-stationary correlation regimes.
        </p>
      </div>
    </div>
  );
}
