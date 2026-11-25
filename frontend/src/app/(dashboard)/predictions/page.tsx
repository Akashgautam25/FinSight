// Predictions page
"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { predictionsApi } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Brain, Loader2, AlertTriangle, TrendingUp, TrendingDown } from "lucide-react";
import { toast } from "sonner";
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend,
} from "recharts";

export default function PredictionsPage() {
  const [symbol, setSymbol] = useState("");
  const [activeSymbol, setActiveSymbol] = useState("");

  const trainMutation = useMutation({
    mutationFn: (sym: string) =>
      predictionsApi.train({ symbol: sym, model_types: ["linear_regression", "random_forest", "xgboost", "lstm"] }),
    onSuccess: () => toast.success(`Training queued for ${activeSymbol}. This runs in the background — check back in a few minutes.`),
    onError: () => toast.error("Failed to queue training."),
  });

  const { data: predictions, isLoading: predLoading, refetch } = useQuery({
    queryKey: ["predictions", activeSymbol],
    queryFn: () => predictionsApi.getPredictions(activeSymbol).then((r) => r.data),
    enabled: !!activeSymbol,
    retry: false,
  });

  const handleSearch = () => {
    if (!symbol.trim()) return;
    setActiveSymbol(symbol.trim().toUpperCase());
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">ML Price Predictions</h1>
        <p className="text-sm text-muted-foreground mt-1">
          4 ML models (Linear Regression, Random Forest, XGBoost, LSTM) trained on historical data
        </p>
      </div>

      <div className="p-4 rounded-xl border border-amber-800/30 bg-amber-950/20 flex items-start gap-3">
        <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0 mt-0.5" />
        <p className="text-xs text-amber-400/90">
          Predictions are <strong>model-generated estimates</strong> with inherent uncertainty.
          They are not guaranteed forecasts and must not be used as the sole basis for investment decisions.
          Past model performance does not guarantee future accuracy.
        </p>
      </div>

      {/* Symbol input */}
      <div className="flex gap-3 max-w-md">
        <Input
          placeholder="Enter ticker symbol (e.g. AAPL)"
          value={symbol}
          onChange={(e) => setSymbol(e.target.value.toUpperCase())}
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
        />
        <Button onClick={handleSearch}>Load</Button>
        <Button
          variant="outline"
          onClick={() => { setActiveSymbol(symbol.toUpperCase()); trainMutation.mutate(symbol.toUpperCase()); }}
          disabled={!symbol || trainMutation.isPending}
        >
          {trainMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Brain className="h-4 w-4 mr-1" />}
          Train
        </Button>
      </div>

      {activeSymbol && (
        predLoading ? (
          <div className="animate-pulse space-y-4">
            <div className="h-72 bg-muted rounded-xl" />
            <div className="grid grid-cols-4 gap-3">
              {[1, 2, 3, 4].map((i) => <div key={i} className="h-24 bg-muted rounded-xl" />)}
            </div>
          </div>
        ) : !predictions ? (
          <div className="rounded-xl border border-border/40 bg-card p-8 text-center">
            <Brain className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
            <h3 className="font-semibold mb-1">No models trained for {activeSymbol}</h3>
            <p className="text-sm text-muted-foreground mb-4">
              Click "Train" to train all 4 ML models. Training runs in the background and takes 1–5 minutes.
            </p>
            <Button onClick={() => trainMutation.mutate(activeSymbol)} disabled={trainMutation.isPending}>
              {trainMutation.isPending ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Brain className="h-4 w-4 mr-2" />}
              Train Models for {activeSymbol}
            </Button>
          </div>
        ) : (
          <PredictionResults data={predictions} />
        )
      )}
    </div>
  );
}

function PredictionResults({ data }: { data: any }) {
  const historicalPrices = data.historical_prices || [];
  const models = data.predictions_by_model || {};
  const modelNames = Object.keys(models);

  // Build chart data: historical + predictions from best model
  const bestModel = data.best_model || modelNames[0];
  const bestPreds = models[bestModel] || {};

  const chartData = historicalPrices.map((p: any) => ({
    date: p.date,
    actual: p.close,
  }));

  // Add prediction points
  Object.entries(bestPreds).forEach(([horizon, pred]: [string, any]) => {
    chartData.push({
      date: pred.target_date,
      predicted: pred.predicted_price,
    });
  });

  return (
    <div className="space-y-5">
      {/* Price chart */}
      <div className="rounded-xl border border-border/40 bg-card p-5">
        <h3 className="font-semibold text-sm mb-4">
          Historical Prices + {bestModel.replace("_", " ").toUpperCase()} Predictions
        </h3>
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" strokeOpacity={0.4} />
            <XAxis dataKey="date" tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} tickLine={false} axisLine={false} />
            <YAxis tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} tickLine={false} axisLine={false} width={55} />
            <Tooltip contentStyle={{ backgroundColor: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: "8px", fontSize: "12px" }} />
            <Legend />
            <Line type="monotone" dataKey="actual" stroke="#6366f1" strokeWidth={1.5} dot={false} name="Historical (Verified)" />
            <Line type="monotone" dataKey="predicted" stroke="#f59e0b" strokeWidth={1.5} strokeDasharray="6 3" dot={{ r: 5, fill: "#f59e0b" }} name="Predicted (Estimate)" />
          </LineChart>
        </ResponsiveContainer>
        <p className="text-xs text-muted-foreground mt-2">
          Dashed line = model estimates. Solid line = verified historical data.
        </p>
      </div>

      {/* Prediction table */}
      <div className="rounded-xl border border-border/40 bg-card overflow-hidden">
        <div className="px-5 py-4 border-b border-border/30">
          <h3 className="font-semibold text-sm">Price Forecasts by Model</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border/30 bg-muted/20">
                <th className="text-left px-5 py-3 text-xs font-medium text-muted-foreground">Model</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-muted-foreground">1 Day</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-muted-foreground">5 Days</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-muted-foreground">10 Days</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-muted-foreground">30 Days</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/20">
              {modelNames.map((model) => (
                <tr key={model} className="hover:bg-muted/20 transition-colors">
                  <td className="px-5 py-3 font-medium capitalize">{model.replace(/_/g, " ")}</td>
                  {["1d", "5d", "10d", "30d"].map((h) => {
                    const pred = models[model]?.[h];
                    const pct = pred?.predicted_change_pct;
                    return (
                      <td key={h} className="text-right px-4 py-3 font-mono">
                        {pred ? (
                          <div>
                            <div>${pred.predicted_price}</div>
                            <div className={`text-xs ${(pct || 0) >= 0 ? "text-profit" : "text-loss"}`}>
                              {(pct || 0) >= 0 ? "▲" : "▼"} {Math.abs(pct || 0).toFixed(2)}%
                            </div>
                          </div>
                        ) : "—"}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="px-5 py-3 bg-muted/10 border-t border-border/30">
          <p className="text-xs text-muted-foreground">
            ⚠️ All values are model estimates with uncertainty. Current prices used: {new Date().toLocaleDateString()}.
            Trained on: {data.historical_prices?.[data.historical_prices.length - 1]?.date}
          </p>
        </div>
      </div>
    </div>
  );
}
