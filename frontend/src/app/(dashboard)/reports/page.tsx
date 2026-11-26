"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, FileText, Loader2, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { aiApi, apiError, reportsApi } from "@/lib/api";
import { cn, formatCurrency, formatDate, formatLargeNumber, formatNumber, formatRatio, MODEL_LABELS } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { DemoBadge } from "@/components/common/DemoBadge";
import { EmptyState } from "@/components/common/EmptyState";
import { PageHeader } from "@/components/common/PageHeader";
import { SymbolSearch } from "@/components/common/SymbolSearch";
import { SentimentBadge } from "@/components/news/SentimentBadge";

function ReportsInner() {
  const qc = useQueryClient();
  const initial = useSearchParams().get("symbol");
  const [symbol, setSymbol] = useState<string>(initial?.toUpperCase() ?? "");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);

  const { data: reports, isLoading } = useQuery({ queryKey: ["reports"], queryFn: () => reportsApi.list().then((r) => r.data) });
  const selected = reports?.find((r: any) => r.id === selectedId) ?? reports?.[0];

  const generate = useMutation({
    mutationFn: () => aiApi.generateReport({ symbol, include_predictions: true, include_sentiment: true }),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["reports"] });
      setSelectedId(res.data.id);
      toast.success(`Report for ${symbol} is ready`);
    },
    onError: (e) => toast.error(apiError(e, "Report generation failed")),
  });
  const remove = useMutation({
    mutationFn: (id: string) => reportsApi.delete(id),
    onSuccess: () => { setSelectedId(null); qc.invalidateQueries({ queryKey: ["reports"] }); },
  });

  useEffect(() => {
    setSymbol(initial?.toUpperCase() ?? "");
  }, [initial]);

  const download = async (r: any) => {
    setDownloading(true);
    try {
      await reportsApi.downloadPdf(r.id, `FinSight_${r.symbol}_${(r.generated_at || "").slice(0, 10)}.pdf`);
    } catch (e) {
      toast.error(apiError(e, "Download failed"));
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Research Reports" description="Equity research reports combining fundamentals, technicals, sentiment, ML forecasts and risk — exportable as PDF" />
      <div className="flex max-w-xl flex-col gap-3 sm:flex-row">
        {symbol ? (
          <button onClick={() => setSymbol("")} className="flex h-9 flex-1 items-center justify-between rounded-md border border-input px-3 font-mono text-sm">{symbol} <span className="text-xs text-muted-foreground">change</span></button>
        ) : (
          <SymbolSearch onSelect={setSymbol} placeholder="Stock for the report (e.g. NVDA)" className="flex-1" clearOnSelect={false} />
        )}
        <Button onClick={() => generate.mutate()} disabled={!symbol || generate.isPending}>
          {generate.isPending ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Generating…</> : <><Plus className="mr-1.5 h-4 w-4" /> Generate report</>}
        </Button>
      </div>
      <p className="-mt-3 text-xs text-muted-foreground">Tip: train models for the stock on the Predictions page first to include ML forecasts.</p>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="overflow-hidden">
          <div className="border-b border-border/30 px-4 py-3 text-sm font-semibold">Saved reports</div>
          <div className="max-h-[600px] divide-y divide-border/20 overflow-y-auto">
            {isLoading ? <div className="space-y-2 p-4">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-12" />)}</div> : reports?.length ? reports.map((r: any) => (
              <button key={r.id} onClick={() => setSelectedId(r.id)} className={cn("w-full p-3.5 text-left hover:bg-muted/20", selected?.id === r.id && "bg-primary/10")}>
                <div className="flex items-center justify-between"><span className="font-mono text-sm font-bold">{r.symbol}</span><span className="text-xs text-muted-foreground">{formatDate(r.generated_at)}</span></div>
                <p className="mt-0.5 truncate text-xs text-muted-foreground">{r.title}</p>
              </button>
            )) : <EmptyState icon={FileText} title="No reports yet" description="Choose a stock above and click Generate." />}
          </div>
        </Card>

        <Card className="min-h-[400px] p-6 lg:col-span-2">
          {!selected ? (
            <EmptyState icon={FileText} title="Select or generate a report" />
          ) : (
            <ReportPreview r={selected} onDownload={() => download(selected)} downloading={downloading} onDelete={() => confirm("Delete this report?") && remove.mutate(selected.id)} />
          )}
        </Card>
      </div>
    </div>
  );
}

function ReportPreview({ r, onDownload, downloading, onDelete }: { r: any; onDownload: () => void; downloading: boolean; onDelete: () => void }) {
  const d = r.report_data ?? {};
  const s = d.stock_detail ?? {};
  const m = s.metrics ?? {};
  const t = d.technicals;
  const risk = d.risk_metrics ?? {};
  const cur = s.currency ?? "USD";
  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 border-b border-border/30 pb-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-lg font-bold">{r.title}</h2>
          <p className="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">Generated {formatDate(r.generated_at, true)} · summary: {d.summary_provider} <DemoBadge show={d.is_demo} /></p>
        </div>
        <div className="flex gap-2">
          <Button size="sm" onClick={onDownload} disabled={!r.pdf_available || downloading}>{downloading ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <Download className="mr-1.5 h-3.5 w-3.5" />} PDF</Button>
          <Button size="sm" variant="ghost" onClick={onDelete} title="Delete"><Trash2 className="h-4 w-4" /></Button>
        </div>
      </div>
      <Section title="Executive summary"><p className="leading-relaxed">{d.executive_summary}</p></Section>
      <Section title="Valuation & fundamentals">
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          {[["Price", formatCurrency(s.current_price, cur)], ["Market cap", formatLargeNumber(m.market_cap)], ["P/E", formatNumber(m.pe_ratio)], ["Beta", formatNumber(m.beta)],
            ["Profit margin", formatRatio(m.profit_margin)], ["ROE", formatRatio(m.roe)], ["52W high", formatNumber(m.week_52_high)], ["52W low", formatNumber(m.week_52_low)]].map(([l, v]) => (
            <div key={l} className="rounded-lg bg-muted/30 p-2.5"><p className="text-xs text-muted-foreground">{l}</p><p className="font-mono text-sm font-semibold">{v}</p></div>
          ))}
        </div>
      </Section>
      {t && (
        <Section title={`Technical analysis — ${t.overall_signal}`}>
          <ul className="list-disc space-y-1 pl-5 text-xs">{t.signals.map((x: any) => <li key={x.indicator}><strong>{x.indicator}:</strong> {x.detail}</li>)}</ul>
        </Section>
      )}
      {d.sentiment && (
        <Section title="News sentiment">
          <div className="mb-2 flex items-center gap-2 text-xs"><SentimentBadge sentiment={d.sentiment.overall_sentiment} /> {d.sentiment.positive_pct}% positive · {d.sentiment.negative_pct}% negative · {d.sentiment.news_count} articles</div>
          <ul className="space-y-1 text-xs">{(d.recent_news ?? []).slice(0, 4).map((a: any) => <li key={a.title} className="flex gap-2"><SentimentBadge sentiment={a.sentiment} compact /> <a href={a.url} target="_blank" rel="noreferrer" className="hover:text-primary">{a.title}</a></li>)}</ul>
        </Section>
      )}
      {d.predictions?.forecast_path?.length > 0 && (
        <Section title="ML forecasts (best model per horizon)">
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            {d.predictions.forecast_path.map((p: any) => (
              <div key={p.horizon} className="rounded-lg bg-muted/30 p-2.5 text-xs">
                <p className="text-muted-foreground">{p.horizon} · {MODEL_LABELS[p.model] ?? p.model}</p>
                <p className="font-mono text-sm font-semibold">{formatNumber(p.predicted)}</p>
                <p className="text-muted-foreground">{formatNumber(p.lower)} – {formatNumber(p.upper)}</p>
              </div>
            ))}
          </div>
        </Section>
      )}
      <Section title="Risk assessment">
        {Object.keys(risk).length > 0 && (
          <div className="mb-2 grid grid-cols-2 gap-2 md:grid-cols-5">
            {[["1y return", `${risk.return_1y_pct}%`], ["Volatility", `${risk.volatility_pct}%`], ["Max drawdown", `${risk.max_drawdown_pct}%`], ["1-day VaR", `${risk.var_95_pct}%`], ["Beta (1y)", risk.beta_1y ?? "—"]].map(([l, v]) => (
              <div key={l} className="rounded-lg bg-muted/30 p-2 text-xs"><p className="text-muted-foreground">{l}</p><p className="font-mono font-semibold">{v}</p></div>
            ))}
          </div>
        )}
        <p className="leading-relaxed">{d.risk_assessment}</p>
      </Section>
      <p className="border-t border-border/20 pt-3 text-xs text-muted-foreground"><strong>Disclaimer:</strong> {d.disclaimer}</p>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="text-sm">
      <h3 className="mb-1.5 text-xs font-bold uppercase tracking-wider text-muted-foreground">{title}</h3>
      {children}
    </div>
  );
}

export default function ReportsPage() {
  return <Suspense fallback={<Skeleton className="h-96" />}><ReportsInner /></Suspense>;
}
