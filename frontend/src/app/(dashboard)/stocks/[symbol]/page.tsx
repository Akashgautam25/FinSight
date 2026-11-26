"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, Bell, BookmarkPlus, Brain, ExternalLink, FileText, Loader2, MessageSquare } from "lucide-react";
import { toast } from "sonner";
import { alertsApi, apiError, newsApi, stocksApi, watchlistApi } from "@/lib/api";
import { formatCurrency, formatLargeNumber, formatNumber, formatRatio, timeAgo } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ChangeText } from "@/components/common/ChangeText";
import { DemoBadge } from "@/components/common/DemoBadge";
import { SentimentBadge } from "@/components/news/SentimentBadge";
import { StockChartPanel } from "@/components/stocks/StockChart";
import { TechnicalIndicatorsPanel } from "@/components/stocks/TechnicalIndicators";
import { AIInsightCard } from "@/components/ai/AIInsightCard";

export default function StockDetailPage() {
  const params = useParams();
  const symbol = decodeURIComponent(params.symbol as string).toUpperCase();
  const qc = useQueryClient();
  const [alertOpen, setAlertOpen] = useState(false);

  const { data: stock, isLoading, error } = useQuery({
    queryKey: ["stock", symbol],
    queryFn: () => stocksApi.getDetail(symbol).then((r) => r.data),
    retry: false,
  });
  const { data: watchlists } = useQuery({ queryKey: ["watchlists"], queryFn: () => watchlistApi.list().then((r) => r.data) });

  const addToWatchlist = useMutation({
    mutationFn: async () => {
      let wl = watchlists?.[0];
      if (!wl) wl = (await watchlistApi.create("My Watchlist")).data;
      return watchlistApi.addSymbol(wl.id, symbol);
    },
    onSuccess: () => {
      toast.success(`${symbol} added to your watchlist`);
      qc.invalidateQueries({ queryKey: ["watchlists"] });
      qc.invalidateQueries({ queryKey: ["watchlist-quotes"] });
    },
    onError: (e) => toast.error(apiError(e)),
  });

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-72" />
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-8">{Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-16" />)}</div>
        <Skeleton className="h-96" />
      </div>
    );
  }

  if (error || !stock) {
    return (
      <div className="flex h-64 flex-col items-center justify-center gap-3 text-muted-foreground">
        <AlertCircle className="h-6 w-6" />
        <p>No market data found for <span className="font-mono font-semibold text-foreground">{symbol}</span>.</p>
        <p className="text-xs">Check the ticker — Indian stocks use a suffix such as <span className="font-mono">RELIANCE.NS</span>.</p>
        <Link href="/market"><Button variant="outline" size="sm">Back to markets</Button></Link>
      </div>
    );
  }

  const inWatchlist = watchlists?.[0]?.symbols?.includes(symbol);
  const m = stock.metrics ?? {};
  const cur = stock.currency;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-bold">{stock.name}</h1>
            <span className="rounded bg-muted px-2 py-0.5 font-mono text-sm text-muted-foreground">{symbol}</span>
            <DemoBadge show={stock.is_demo} />
          </div>
          <p className="mt-1 text-sm text-muted-foreground">{[stock.exchange, stock.sector, stock.industry].filter(Boolean).join(" · ")}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button size="sm" variant="outline" onClick={() => addToWatchlist.mutate()} disabled={inWatchlist || addToWatchlist.isPending}>
              <BookmarkPlus className="mr-1.5 h-3.5 w-3.5" /> {inWatchlist ? "In watchlist" : "Watch"}
            </Button>
            <Button size="sm" variant="outline" onClick={() => setAlertOpen((o) => !o)}><Bell className="mr-1.5 h-3.5 w-3.5" /> Set alert</Button>
            <Link href={`/assistant?q=${encodeURIComponent(`Give me a full analysis of ${symbol}`)}`}><Button size="sm" variant="outline"><MessageSquare className="mr-1.5 h-3.5 w-3.5" /> Ask AI</Button></Link>
            <Link href={`/predictions?symbol=${symbol}`}><Button size="sm" variant="outline"><Brain className="mr-1.5 h-3.5 w-3.5" /> Forecast</Button></Link>
            <Link href={`/reports?symbol=${symbol}`}><Button size="sm" variant="outline"><FileText className="mr-1.5 h-3.5 w-3.5" /> Report</Button></Link>
          </div>
        </div>
        <div className="lg:text-right">
          <p className="font-mono text-3xl font-bold">{formatCurrency(stock.current_price, cur)}</p>
          <div className="mt-1 flex items-center gap-2 lg:justify-end">
            <span className={`font-mono text-sm ${(stock.change ?? 0) >= 0 ? "text-profit" : "text-loss"}`}>{stock.change != null && (stock.change >= 0 ? "+" : "")}{formatNumber(stock.change)}</span>
            <ChangeText value={stock.change_pct} icon className="text-sm" />
          </div>
          <p className="mt-1 text-xs text-muted-foreground">Delayed · updated {timeAgo(stock.last_updated)}</p>
        </div>
      </div>

      {alertOpen && <AlertForm symbol={symbol} price={stock.current_price} onDone={() => setAlertOpen(false)} />}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-8">
        {[
          ["Market cap", formatLargeNumber(m.market_cap)],
          ["P/E ratio", formatNumber(m.pe_ratio)],
          ["EPS", formatNumber(m.eps)],
          ["Beta", formatNumber(m.beta)],
          ["Day range", stock.day_low ? `${formatNumber(stock.day_low)} – ${formatNumber(stock.day_high)}` : "—"],
          ["52W range", m.week_52_low ? `${formatNumber(m.week_52_low, 0)} – ${formatNumber(m.week_52_high, 0)}` : "—"],
          ["Volume", formatLargeNumber(stock.volume)],
          ["Div. yield", m.dividend_yield ? formatRatio(m.dividend_yield) : "—"],
        ].map(([label, value]) => (
          <div key={label} className="rounded-lg border border-border/40 bg-card p-3">
            <p className="text-xs text-muted-foreground">{label}</p>
            <p className="mt-0.5 truncate font-mono text-sm font-semibold">{value}</p>
          </div>
        ))}
      </div>

      <AIInsightCard kind="stock" symbol={symbol} title={`AI analyst note — ${symbol}`} description="Summary, bull case and bear case generated from live fundamentals, technicals and news" />

      <Tabs defaultValue="chart">
        <TabsList className="bg-muted/50">
          <TabsTrigger value="chart">Price chart</TabsTrigger>
          <TabsTrigger value="technical">Technicals</TabsTrigger>
          <TabsTrigger value="fundamentals">Fundamentals</TabsTrigger>
          <TabsTrigger value="news">News & sentiment</TabsTrigger>
          <TabsTrigger value="about">About</TabsTrigger>
        </TabsList>
        <TabsContent value="chart" className="mt-4"><StockChartPanel symbol={symbol} currency={cur} /></TabsContent>
        <TabsContent value="technical" className="mt-4"><TechnicalIndicatorsPanel symbol={symbol} /></TabsContent>
        <TabsContent value="fundamentals" className="mt-4"><FundamentalsPanel metrics={m} currency={cur} isDemo={stock.is_demo} /></TabsContent>
        <TabsContent value="news" className="mt-4"><StockNewsPanel symbol={symbol} /></TabsContent>
        <TabsContent value="about" className="mt-4">
          <div className="rounded-xl border border-border/40 bg-card p-5 text-sm leading-relaxed text-muted-foreground">
            {stock.description || "No company description available."}
            {m.extra_metrics?.website && (
              <a href={m.extra_metrics.website} target="_blank" rel="noreferrer" className="mt-3 flex items-center gap-1 text-primary">
                {m.extra_metrics.website} <ExternalLink className="h-3 w-3" />
              </a>
            )}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function AlertForm({ symbol, price, onDone }: { symbol: string; price?: number; onDone: () => void }) {
  const qc = useQueryClient();
  const [type, setType] = useState("price_above");
  const [value, setValue] = useState(price ? (price * 1.05).toFixed(2) : "");
  const create = useMutation({
    mutationFn: () => alertsApi.create({ symbol, alert_type: type, target_value: parseFloat(value) }),
    onSuccess: () => { toast.success("Alert created — you'll get a notification when it triggers."); qc.invalidateQueries({ queryKey: ["alerts"] }); onDone(); },
    onError: (e) => toast.error(apiError(e)),
  });
  return (
    <div className="flex flex-wrap items-end gap-3 rounded-xl border border-primary/30 bg-card p-4">
      <div className="space-y-1">
        <p className="text-xs text-muted-foreground">Condition</p>
        <Select value={type} onChange={(e) => setType(e.target.value)} className="w-56">
          <option value="price_above">Price rises above</option>
          <option value="price_below">Price falls below</option>
          <option value="pct_change_up">Daily gain of at least (%)</option>
          <option value="pct_change_down">Daily drop of at least (%)</option>
        </Select>
      </div>
      <div className="space-y-1">
        <p className="text-xs text-muted-foreground">{type.startsWith("pct") ? "Percent" : "Price"}</p>
        <Input type="number" step="0.01" value={value} onChange={(e) => setValue(e.target.value)} className="w-36" />
      </div>
      <Button onClick={() => create.mutate()} disabled={!value || create.isPending}>{create.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : "Create alert"}</Button>
      <Button variant="ghost" onClick={onDone}>Cancel</Button>
    </div>
  );
}

function FundamentalsPanel({ metrics: m, currency, isDemo }: { metrics: any; currency: string; isDemo: boolean }) {
  const x = m.extra_metrics ?? {};
  const rows: [string, string, string][] = [
    ["Market capitalization", formatLargeNumber(m.market_cap), "Share price × shares outstanding"],
    ["Enterprise value", formatLargeNumber(x.enterprise_value), "Market cap + debt − cash"],
    ["P/E ratio (trailing)", formatNumber(m.pe_ratio), "Price ÷ trailing 12-month EPS"],
    ["Forward P/E", formatNumber(x.forward_pe), "Price ÷ expected EPS"],
    ["PEG ratio", formatNumber(x.peg_ratio), "P/E ÷ earnings growth"],
    ["Price / book", formatNumber(x.price_to_book), "Price ÷ book value per share"],
    ["EPS (trailing)", formatCurrency(m.eps, currency), "Net income per share"],
    ["Dividend yield", m.dividend_yield ? formatRatio(m.dividend_yield) : "—", "Annual dividend ÷ price"],
    ["Beta", formatNumber(m.beta), "Volatility relative to the market"],
    ["Return on equity", formatRatio(m.roe), "Net income ÷ shareholder equity"],
    ["Return on assets", formatRatio(m.roa), "Net income ÷ total assets"],
    ["Profit margin", formatRatio(m.profit_margin), "Net income ÷ revenue"],
    ["Revenue growth (YoY)", formatRatio(m.revenue_growth), "Change in revenue vs last year"],
    ["Debt / equity", m.debt_to_equity != null ? `${formatNumber(m.debt_to_equity)}×` : "—", "Total debt ÷ shareholder equity"],
    ["Current ratio", formatNumber(x.current_ratio), "Current assets ÷ current liabilities"],
    ["Free cash flow", formatLargeNumber(m.free_cash_flow), "Operating cash flow − capex"],
  ];
  return (
    <div className="overflow-hidden rounded-xl border border-border/40 bg-card">
      <div className="grid grid-cols-1 divide-y divide-border/30 md:grid-cols-2 md:divide-x md:divide-y-0">
        {[rows.slice(0, 8), rows.slice(8)].map((col, ci) => (
          <div key={ci} className="divide-y divide-border/30">
            {col.map(([label, value, hint]) => (
              <div key={label} className="flex items-center justify-between px-4 py-3" title={hint}>
                <div>
                  <p className="text-sm">{label}</p>
                  <p className="text-[11px] text-muted-foreground">{hint}</p>
                </div>
                <span className="font-mono text-sm font-medium">{value}</span>
              </div>
            ))}
          </div>
        ))}
      </div>
      <div className="flex items-center gap-2 border-t border-border/30 bg-muted/20 px-4 py-3 text-xs text-muted-foreground">
        Source: {isDemo ? "simulated reference values" : "Yahoo Finance (public filings)"} · as of {m.as_of_date ?? "—"} <DemoBadge show={isDemo} />
      </div>
    </div>
  );
}

function StockNewsPanel({ symbol }: { symbol: string }) {
  const { data: summary } = useQuery({ queryKey: ["sentiment", symbol], queryFn: () => newsApi.getSentiment(symbol, 30).then((r) => r.data) });
  const { data: news, isLoading } = useQuery({ queryKey: ["stock-news", symbol], queryFn: () => newsApi.getStock(symbol, 30).then((r) => r.data) });
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <div className="space-y-3 rounded-xl border border-border/40 bg-card p-5">
        <p className="text-sm font-semibold">Sentiment (30 days)</p>
        {summary ? (
          <>
            <SentimentBadge sentiment={summary.overall_sentiment} score={summary.avg_compound_score} />
            <div className="space-y-2">
              {[["Positive", summary.positive_pct, "bg-profit"], ["Neutral", summary.neutral_pct, "bg-muted-foreground"], ["Negative", summary.negative_pct, "bg-loss"]].map(([l, v, c]) => (
                <div key={l as string}>
                  <div className="flex justify-between text-xs"><span>{l}</span><span className="font-mono">{v}%</span></div>
                  <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-muted"><div className={`h-full ${c}`} style={{ width: `${v}%` }} /></div>
                </div>
              ))}
            </div>
            <p className="text-xs text-muted-foreground">{summary.news_count} articles · model: {summary.sentiment_model}</p>
          </>
        ) : <Skeleton className="h-32" />}
      </div>
      <div className="space-y-2 lg:col-span-2">
        {isLoading ? [1, 2, 3].map((i) => <Skeleton key={i} className="h-20" />) : (news?.articles ?? []).map((a: any) => (
          <a key={a.id} href={a.url} target="_blank" rel="noreferrer" className="block rounded-lg border border-border/40 bg-card p-3 hover:border-primary/40">
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs text-muted-foreground">{a.source} · {timeAgo(a.published_at)}</span>
              <SentimentBadge sentiment={a.sentiment} />
            </div>
            <p className="mt-1 text-sm font-medium">{a.title}</p>
            {a.summary && <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{a.summary}</p>}
          </a>
        ))}
        {news && news.articles.length === 0 && <p className="text-sm text-muted-foreground">No recent news found.</p>}
      </div>
    </div>
  );
}
