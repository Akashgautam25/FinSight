"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Area, Bar, BarChart, CartesianGrid, ComposedChart, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { AlertTriangle, Brain, CheckCircle2, Info, Loader2, RefreshCw, Trophy } from "lucide-react";
import { toast } from "sonner";
import { apiError, predictionsApi } from "@/lib/api";
import { CHART_COLORS, cn, formatCurrency, formatDate, formatNumber, MODEL_LABELS } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { DemoBadge } from "@/components/common/DemoBadge";
import { PageHeader } from "@/components/common/PageHeader";
import { SymbolSearch } from "@/components/common/SymbolSearch";
import { AIInsightCard } from "@/components/ai/AIInsightCard";

const ALL_MODELS = ["linear_regression", "random_forest", "xgboost", "lstm"];
const HORIZONS = ["1", "5", "10", "30"];
const tooltipStyle = { backgroundColor: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 8, fontSize: 12 };
const axisTick = { fontSize: 10, fill: "hsl(var(--muted-foreground))" };

function PredictionsInner() {
  const params = useSearchParams();
  const router = useRouter();
  const symbol = (params.get("symbol") || "").toUpperCase();
  const qc = useQueryClient();
  const [models, setModels] = useState<string[]>(ALL_MODELS);
  const [lookback, setLookback] = useState(5);

  const { data: trained } = useQuery({ queryKey: ["trained-models"], queryFn: () => predictionsApi.trained().then((r) => r.data) });

  const { data: status } = useQuery({
    queryKey: ["train-status", symbol],
    queryFn: () => predictionsApi.status(symbol).then((r) => r.data),
    enabled: !!symbol,
    refetchInterval: (q) => (["queued", "running"].includes(q.state.data?.status) ? 1500 : false),
  });
  const isTraining = ["queued", "running"].includes(status?.status);
  const isTrained = status?.status === "completed";

  const { data: preds, isLoading: loadingPreds } = useQuery({
    queryKey: ["predictions", symbol, status?.finished_at],
    queryFn: () => predictionsApi.getPredictions(symbol).then((r) => r.data),
    enabled: !!symbol && isTrained,
    retry: false,
  });
  const { data: evaluation } = useQuery({
    queryKey: ["evaluation", symbol, status?.finished_at],
    queryFn: () => predictionsApi.getEvaluation(symbol).then((r) => r.data),
    enabled: !!symbol && isTrained,
  });

  useEffect(() => {
    if (status?.status === "completed") qc.invalidateQueries({ queryKey: ["trained-models"] });
    if (status?.status === "failed") toast.error(`Training failed: ${status.error}`);
  }, [status?.status, status?.error, qc]);

  const train = useMutation({
    mutationFn: () => predictionsApi.train({ symbol, model_types: models, lookback_years: lookback }),
    onSuccess: () => {
      toast.success(`Training started for ${symbol} — this takes about 10–60 seconds.`);
      qc.invalidateQueries({ queryKey: ["train-status", symbol] });
    },
    onError: (e) => toast.error(apiError(e)),
  });

  const unavailable = Object.entries(trained?.model_availability ?? {}).filter(([, reason]) => reason) as [string, string][];

  return (
    <div className="space-y-6">
      <PageHeader
        title="ML Price Predictions"
        description="Linear Regression, Random Forest, XGBoost and an LSTM network forecast 1, 5, 10 and 30-day returns from 32 technical features."
      />

      <div className="flex items-start gap-3 rounded-xl border border-amber-800/30 bg-amber-950/20 p-4">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />
        <p className="text-xs text-amber-400/90">
          Forecasts are <strong>statistical estimates</strong>. Daily stock returns are close to a random walk, so even the best model only slightly
          beats a naive "price stays the same" forecast — compare the <em>skill vs naive</em> column below before trusting any number.
        </p>
      </div>

      <div className="flex flex-col gap-3 md:flex-row md:items-center">
        <SymbolSearch onSelect={(s) => router.push(`/predictions?symbol=${encodeURIComponent(s)}`)} className="max-w-md flex-1" placeholder="Choose a stock to forecast (e.g. AAPL)" />
        {trained?.symbols?.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-xs text-muted-foreground">Trained:</span>
            {trained.symbols.map((s: any) => (
              <button key={s.symbol} onClick={() => router.push(`/predictions?symbol=${s.symbol}`)}
                className={cn("rounded-md border px-2 py-1 font-mono text-xs", s.symbol === symbol ? "border-primary bg-primary/10 text-primary" : "border-border/50 hover:border-primary/40")}>
                {s.symbol}
              </button>
            ))}
          </div>
        )}
      </div>

      {!symbol ? (
        <Card className="p-10 text-center">
          <Brain className="mx-auto mb-3 h-10 w-10 text-muted-foreground" />
          <p className="font-medium">Pick a stock above to train models and see forecasts</p>
          <p className="mt-1 text-sm text-muted-foreground">Try <button className="text-primary underline" onClick={() => router.push("/predictions?symbol=AAPL")}>AAPL</button> or <button className="text-primary underline" onClick={() => router.push("/predictions?symbol=RELIANCE.NS")}>RELIANCE.NS</button>.</p>
        </Card>
      ) : isTraining ? (
        <Card className="p-8">
          <div className="mx-auto max-w-md space-y-4 text-center">
            <Loader2 className="mx-auto h-8 w-8 animate-spin text-primary" />
            <p className="font-medium">Training models for {symbol}…</p>
            <div className="h-2 overflow-hidden rounded-full bg-muted">
              <div className="h-full bg-primary transition-all duration-500" style={{ width: `${Math.round((status?.progress ?? 0) * 100)}%` }} />
            </div>
            <p className="text-xs text-muted-foreground">{status?.message} · {Math.round((status?.progress ?? 0) * 100)}%</p>
            <p className="text-xs text-muted-foreground">Training runs in a background worker — you can leave this page and you'll get a notification when it finishes.</p>
          </div>
        </Card>
      ) : !isTrained ? (
        <Card className="p-8">
          <div className="mx-auto max-w-lg space-y-5">
            <div className="text-center">
              <Brain className="mx-auto mb-3 h-10 w-10 text-muted-foreground" />
              <p className="font-semibold">No models trained for {symbol} yet</p>
              <p className="mt-1 text-sm text-muted-foreground">Training downloads price history, engineers features and fits every model on a chronological train / validation / test split.</p>
            </div>
            <div className="grid grid-cols-2 gap-2">
              {ALL_MODELS.map((m) => {
                const reason = trained?.model_availability?.[m];
                return (
                  <label key={m} className={cn("flex items-center gap-2 rounded-lg border p-3 text-sm", reason ? "opacity-50" : "cursor-pointer hover:border-primary/40", models.includes(m) && !reason && "border-primary/50 bg-primary/5")} title={reason || undefined}>
                    <input type="checkbox" disabled={!!reason} checked={models.includes(m) && !reason}
                      onChange={(e) => setModels((cur) => (e.target.checked ? [...cur, m] : cur.filter((x) => x !== m)))} />
                    {MODEL_LABELS[m]}
                  </label>
                );
              })}
            </div>
            <div className="flex items-center gap-3">
              <span className="text-sm text-muted-foreground">History:</span>
              <Select value={lookback} onChange={(e) => setLookback(Number(e.target.value))} className="w-36">
                {[2, 3, 5, 10].map((y) => <option key={y} value={y}>{y} years</option>)}
              </Select>
              <Button className="ml-auto" onClick={() => train.mutate()} disabled={train.isPending || models.length === 0}>
                {train.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Brain className="mr-2 h-4 w-4" />} Train models
              </Button>
            </div>
            {status?.status === "failed" && <p className="text-xs text-destructive">Last attempt failed: {status.error}</p>}
            {unavailable.length > 0 && <p className="text-xs text-muted-foreground">{unavailable.map(([m, r]) => `${MODEL_LABELS[m]}: ${r}`).join(" · ")}</p>}
          </div>
        </Card>
      ) : loadingPreds || !preds ? (
        <div className="space-y-4"><Skeleton className="h-80" /><Skeleton className="h-60" /></div>
      ) : (
        <Results preds={preds} evaluation={evaluation} onRetrain={() => train.mutate()} retraining={train.isPending} />
      )}
    </div>
  );
}

function Results({ preds, evaluation, onRetrain, retraining }: { preds: any; evaluation: any; onRetrain: () => void; retraining: boolean }) {
  const [horizon, setHorizon] = useState("1");
  const cur = preds.symbol.endsWith(".NS") || preds.symbol.endsWith(".BO") ? "INR" : "USD";

  const chartData = useMemo(() => {
    const hist = preds.historical_prices.map((p: any) => ({ date: p.date, actual: p.close }));
    if (hist.length) {
      const last = hist[hist.length - 1];
      last.predicted = last.actual;
      last.band = [last.actual, last.actual];
    }
    const future = preds.forecast_path.map((p: any) => ({ date: p.date, predicted: p.predicted, band: [p.lower, p.upper], horizon: p.horizon, model: p.model }));
    return [...hist, ...future];
  }, [preds]);

  const metricsFor = (evaluation?.metrics ?? []).filter((m: any) => String(m.horizon_days) === horizon && !m.error);
  const naive = evaluation?.naive_baseline?.[horizon];
  const backtestKey = evaluation?.backtest?.[horizon] ? horizon : evaluation?.backtest ? Object.keys(evaluation.backtest)[0] : null;
  const backtest = backtestKey ? evaluation.backtest[backtestKey] : null;
  const backtestData = backtest
    ? backtest.dates.map((d: string, i: number) => ({ date: d, actual: backtest.actual[i], ...Object.fromEntries(Object.entries(backtest.predictions).map(([m, arr]: any) => [m, arr[i]])) }))
    : [];
  const fiModel = evaluation?.feature_importance?.random_forest ? "random_forest" : evaluation?.feature_importance?.xgboost ? "xgboost" : null;
  const fiData = fiModel ? Object.entries(evaluation.feature_importance[fiModel]).map(([k, v]) => ({ feature: k, importance: Number(v) })).slice(0, 10).reverse() : [];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
        <span>Trained {formatDate(preds.trained_at, true)}</span>
        <span>·</span>
        <span>Data: {evaluation?.data_range ? `${evaluation.data_range.start} → ${evaluation.data_range.end} (${evaluation.data_range.rows} days)` : preds.data_source}</span>
        {evaluation?.training_seconds && <><span>·</span><span>Training time {evaluation.training_seconds}s</span></>}
        <DemoBadge show={preds.is_demo} />
        <Button size="sm" variant="outline" className="ml-auto h-7 text-xs" onClick={onRetrain} disabled={retraining}>
          <RefreshCw className="mr-1.5 h-3 w-3" /> Retrain
        </Button>
      </div>

      <Card>
        <CardHeader title={`${preds.symbol} — history and forecast`} description="Solid: verified closing prices. Dashed: best model per horizon, shaded band = 95% prediction interval." />
        <CardContent>
          <ResponsiveContainer width="100%" height={300}>
            <ComposedChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" strokeOpacity={0.4} />
              <XAxis dataKey="date" tick={axisTick} tickLine={false} axisLine={false} minTickGap={40} tickFormatter={(d) => new Date(d).toLocaleDateString([], { month: "short", day: "numeric" })} />
              <YAxis domain={["auto", "auto"]} tick={axisTick} tickLine={false} axisLine={false} width={60} />
              <Tooltip contentStyle={tooltipStyle} formatter={(v: any, n: string) => [Array.isArray(v) ? `${formatNumber(v[0])} – ${formatNumber(v[1])}` : formatNumber(v), n]} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Area dataKey="band" stroke="none" fill="#f59e0b" fillOpacity={0.15} name="95% interval" />
              <Line dataKey="actual" stroke="#3b82f6" strokeWidth={1.6} dot={false} name="Historical close" />
              <Line dataKey="predicted" stroke="#f59e0b" strokeWidth={1.8} strokeDasharray="6 3" dot={{ r: 4, fill: "#f59e0b" }} name="Forecast (best model)" />
            </ComposedChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <AIInsightCard key={preds.trained_at} kind="predictions" symbol={preds.symbol} title="Explain these results (AI)" description="Plain-language explanation of the forecasts and how reliable the models are" autoStart={false} />

      <Card>
        <CardHeader title="Price forecasts by model" description={`From the latest close of ${formatCurrency(preds.current_price, cur)} on ${preds.as_of}. 🏆 = lowest validation error for that horizon.`} />
        <CardContent className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border/30 text-xs text-muted-foreground">
                <th className="py-2 text-left font-medium">Model</th>
                {HORIZONS.map((h) => <th key={h} className="px-3 py-2 text-right font-medium">{h} day{h !== "1" && "s"}</th>)}
              </tr>
            </thead>
            <tbody className="divide-y divide-border/20">
              {preds.available_models.map((m: string) => (
                <tr key={m}>
                  <td className="py-3 font-medium">{MODEL_LABELS[m] ?? m}</td>
                  {HORIZONS.map((h) => {
                    const p = preds.predictions_by_model[m]?.[`${h}d`];
                    return (
                      <td key={h} className={cn("px-3 py-3 text-right font-mono", p?.is_best && "bg-primary/5")}>
                        {p ? (
                          <div>
                            <div>{p.is_best && "🏆 "}{formatNumber(p.predicted_price)}</div>
                            <div className={cn("text-xs", p.predicted_change_pct >= 0 ? "text-profit" : "text-loss")}>{p.predicted_change_pct >= 0 ? "▲" : "▼"} {Math.abs(p.predicted_change_pct).toFixed(2)}%</div>
                            <div className="text-[10px] text-muted-foreground">{formatNumber(p.lower_bound)} – {formatNumber(p.upper_bound)}</div>
                          </div>
                        ) : "—"}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>

      {evaluation?.trained && (
        <Card>
          <CardHeader
            title="Model evaluation on the unseen test set"
            description="Metrics on the most recent 15% of data, which no model saw during training or model selection."
            action={
              <div className="flex rounded-md border border-border/50">
                {HORIZONS.map((h) => (
                  <button key={h} onClick={() => setHorizon(h)} className={cn("px-3 py-1 text-xs", horizon === h ? "bg-primary/10 text-primary" : "text-muted-foreground")}>{h}d</button>
                ))}
              </div>
            }
          />
          <CardContent className="space-y-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/30 text-xs text-muted-foreground">
                  <th className="py-2 text-left font-medium">Model</th>
                  <th className="px-3 py-2 text-right font-medium" title="Root mean squared error of the forecast price">RMSE</th>
                  <th className="px-3 py-2 text-right font-medium" title="Mean absolute percentage error">MAPE</th>
                  <th className="px-3 py-2 text-right font-medium" title="Share of correct up/down calls">Direction acc.</th>
                  <th className="px-3 py-2 text-right font-medium" title="1 − RMSE / RMSE(naive). Positive = better than assuming no change">Skill vs naive</th>
                  <th className="px-3 py-2 text-right font-medium" title="Variance of returns explained">R² (returns)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/20">
                {metricsFor.map((row: any) => (
                  <tr key={row.model} className={row.is_best ? "bg-primary/5" : ""}>
                    <td className="py-2.5 font-medium">{row.is_best && <Trophy className="mr-1 inline h-3 w-3 text-amber-500" />}{MODEL_LABELS[row.model] ?? row.model}</td>
                    <td className="px-3 py-2.5 text-right font-mono">{formatNumber(row.test.rmse)}</td>
                    <td className="px-3 py-2.5 text-right font-mono">{formatNumber(row.test.mape)}%</td>
                    <td className="px-3 py-2.5 text-right font-mono">{row.test.directional_accuracy != null ? `${(row.test.directional_accuracy * 100).toFixed(1)}%` : "—"}</td>
                    <td className={cn("px-3 py-2.5 text-right font-mono", (row.test.skill_vs_naive ?? 0) > 0 ? "text-profit" : "text-loss")}>{row.test.skill_vs_naive != null ? `${(row.test.skill_vs_naive * 100).toFixed(1)}%` : "—"}</td>
                    <td className="px-3 py-2.5 text-right font-mono">{formatNumber(row.test.r_squared_returns, 3)}</td>
                  </tr>
                ))}
                {naive && (
                  <tr className="text-muted-foreground">
                    <td className="py-2.5 italic">Naive baseline (no change)</td>
                    <td className="px-3 py-2.5 text-right font-mono">{formatNumber(naive.rmse)}</td>
                    <td className="px-3 py-2.5 text-right font-mono">{formatNumber(naive.mape)}%</td>
                    <td className="px-3 py-2.5 text-right font-mono">—</td>
                    <td className="px-3 py-2.5 text-right font-mono">0.0%</td>
                    <td className="px-3 py-2.5 text-right font-mono">—</td>
                  </tr>
                )}
              </tbody>
            </table>
            {evaluation.splits?.[horizon] && (
              <div className="grid grid-cols-1 gap-2 text-xs md:grid-cols-3">
                {(["train", "validation", "test"] as const).map((k) => {
                  const s = evaluation.splits[horizon][k];
                  return (
                    <div key={k} className="rounded-lg border border-border/30 bg-muted/20 p-2.5">
                      <p className="font-semibold capitalize">{k}</p>
                      <p className="text-muted-foreground">{s.start} → {s.end} · {s.rows} rows</p>
                    </div>
                  );
                })}
              </div>
            )}
            {Object.keys(evaluation.models_skipped ?? {}).length > 0 && (
              <p className="text-xs text-muted-foreground">Skipped: {Object.entries(evaluation.models_skipped).map(([m, r]) => `${MODEL_LABELS[m]} (${r})`).join(", ")}</p>
            )}
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        {backtest && (
          <Card>
            <CardHeader title={`Backtest — ${backtestKey}-day forecasts vs reality`} description="Out-of-sample test period: what each model predicted against what actually happened." />
            <CardContent>
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={backtestData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" strokeOpacity={0.4} />
                  <XAxis dataKey="date" tick={axisTick} tickLine={false} axisLine={false} minTickGap={40} />
                  <YAxis domain={["auto", "auto"]} tick={axisTick} tickLine={false} axisLine={false} width={55} />
                  <Tooltip contentStyle={tooltipStyle} formatter={(v: number, n: string) => [formatNumber(v), MODEL_LABELS[n] ?? n]} />
                  <Legend wrapperStyle={{ fontSize: 11 }} formatter={(v) => MODEL_LABELS[v] ?? (v === "actual" ? "Actual" : v)} />
                  <Line dataKey="actual" stroke="hsl(var(--foreground))" strokeWidth={1.8} dot={false} />
                  {Object.keys(backtest.predictions).map((m, i) => <Line key={m} dataKey={m} stroke={CHART_COLORS[i]} strokeWidth={1} dot={false} strokeOpacity={0.85} />)}
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        )}
        {fiData.length > 0 && (
          <Card>
            <CardHeader title={`Feature importance — ${MODEL_LABELS[fiModel!]}`} description="Which engineered features drive the 1-day forecast." />
            <CardContent>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={fiData} layout="vertical" margin={{ left: 30 }}>
                  <XAxis type="number" tick={axisTick} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
                  <YAxis type="category" dataKey="feature" tick={axisTick} width={110} />
                  <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => [`${(v * 100).toFixed(2)}%`, "Importance"]} />
                  <Bar dataKey="importance" fill="#3b82f6" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        )}
      </div>

      <Card className="p-5">
        <div className="flex gap-3">
          <Info className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
          <div className="space-y-1.5 text-xs leading-relaxed text-muted-foreground">
            <p><strong className="text-foreground">Methodology.</strong> Target: forward h-day return (converted back to a price). Features: {evaluation?.feature_columns?.length ?? 32} scale-invariant indicators (returns, MA ratios, RSI, MACD, Bollinger %B, ATR, volatility, momentum, volume, lags) computed only from past data.</p>
            <p><strong className="text-foreground">Leakage prevention.</strong> Chronological 70/15/15 split with an h-row purge gap at each boundary; scalers fitted on training data only; best model chosen on validation RMSE, reported on test data.</p>
            <p><strong className="text-foreground">Intervals.</strong> 95% bands use ±1.96 × the standard deviation of validation residuals. <CheckCircle2 className="inline h-3 w-3" /> <Link href="/assistant?q=Explain%20directional%20accuracy%20and%20skill%20vs%20naive" className="text-primary underline">Ask the assistant</Link> to explain any metric.</p>
          </div>
        </div>
      </Card>
    </div>
  );
}

export default function PredictionsPage() {
  return (
    <Suspense fallback={<Skeleton className="h-96" />}>
      <PredictionsInner />
    </Suspense>
  );
}
