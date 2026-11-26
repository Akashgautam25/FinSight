"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { ExternalLink, FlaskConical, Loader2, X } from "lucide-react";
import { toast } from "sonner";
import { apiError, newsApi } from "@/lib/api";
import { cn, timeAgo } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { DemoBadge } from "@/components/common/DemoBadge";
import { PageHeader } from "@/components/common/PageHeader";
import { SymbolSearch } from "@/components/common/SymbolSearch";
import { SentimentBadge } from "@/components/news/SentimentBadge";
import { AIInsightCard } from "@/components/ai/AIInsightCard";

const CATEGORIES = ["all", "technology", "finance", "healthcare", "energy", "consumer", "india"];

export default function NewsPage() {
  const [category, setCategory] = useState("all");
  const [symbol, setSymbol] = useState<string | null>(null);

  const market = useQuery({
    queryKey: ["market-news", category],
    queryFn: () => newsApi.getMarket(30, category).then((r) => r.data),
    enabled: !symbol,
  });
  const stockNews = useQuery({ queryKey: ["stock-news", symbol], queryFn: () => newsApi.getStock(symbol!, 30, 30).then((r) => r.data), enabled: !!symbol });
  const summary = useQuery({ queryKey: ["sentiment", symbol], queryFn: () => newsApi.getSentiment(symbol!, 30).then((r) => r.data), enabled: !!symbol });

  const feed = symbol ? stockNews : market;
  const articles = feed.data?.articles ?? [];
  const counts = { positive: 0, neutral: 0, negative: 0 } as Record<string, number>;
  articles.forEach((a: any) => (counts[a.sentiment] = (counts[a.sentiment] ?? 0) + 1));
  const pie = [
    { name: "Positive", value: counts.positive, color: "#22c55e" },
    { name: "Neutral", value: counts.neutral, color: "#64748b" },
    { name: "Negative", value: counts.negative, color: "#ef4444" },
  ];

  return (
    <div className="space-y-6">
      <PageHeader title="News & Sentiment" description={`Financial headlines classified by ${feed.data?.sentiment_model === "ProsusAI/finbert" ? "FinBERT (transformer)" : "a finance-specific sentiment model"}`} />

      <div className="flex flex-col gap-3 md:flex-row md:items-center">
        <SymbolSearch onSelect={setSymbol} placeholder="Company news & sentiment (e.g. TSLA)" className="max-w-sm flex-1" />
        {symbol ? (
          <button onClick={() => setSymbol(null)} className="inline-flex items-center gap-1.5 rounded-md border border-primary/40 bg-primary/10 px-2.5 py-1 font-mono text-xs text-primary">
            {symbol} <X className="h-3 w-3" />
          </button>
        ) : (
          <div className="flex flex-wrap gap-1">
            {CATEGORIES.map((c) => (
              <Button key={c} variant="ghost" size="sm" onClick={() => setCategory(c)} className={cn("h-7 text-xs capitalize", category === c ? "bg-primary/10 text-primary" : "text-muted-foreground")}>{c}</Button>
            ))}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <div className="space-y-6">
          <Card>
            <CardHeader title={symbol ? `${symbol} sentiment` : "Feed sentiment"} description={`${articles.length} articles`} action={<DemoBadge show={!!feed.data?.is_demo} />} />
            <CardContent>
              {feed.isLoading ? <Skeleton className="h-40" /> : (
                <div className="flex items-center gap-4">
                  <ResponsiveContainer width={140} height={140}>
                    <PieChart>
                      <Pie data={pie} dataKey="value" innerRadius={40} outerRadius={65} paddingAngle={2}>{pie.map((p) => <Cell key={p.name} fill={p.color} />)}</Pie>
                      <Tooltip contentStyle={{ backgroundColor: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 8, fontSize: 12 }} />
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="space-y-1.5 text-sm">
                    {pie.map((p) => <p key={p.name} className="flex items-center gap-2"><span className="h-2 w-2 rounded-full" style={{ background: p.color }} />{p.name}: <span className="font-mono">{p.value}</span></p>)}
                    {symbol && summary.data && <div className="pt-2"><SentimentBadge sentiment={summary.data.overall_sentiment} score={summary.data.avg_compound_score} /></div>}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
          <AIInsightCard key={symbol ?? "market"} kind="news" symbol={symbol ?? undefined} title={symbol ? `AI news digest — ${symbol}` : "AI news digest"} description="Key themes and sentiment, summarised by the AI" autoStart={false} />
          <SentimentPlayground />
        </div>

        <div className="space-y-3 xl:col-span-2">
          {feed.isLoading ? Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-24" />) : articles.length === 0 ? (
            <Card className="p-8 text-center text-sm text-muted-foreground">No articles found.</Card>
          ) : articles.map((a: any) => (
            <a key={a.id} href={a.url} target="_blank" rel="noopener noreferrer" className="group block rounded-xl border border-border/40 bg-card p-4 hover:border-primary/40">
              <div className="mb-1.5 flex items-center justify-between gap-2">
                <span className="text-xs text-muted-foreground">{a.source} · {timeAgo(a.published_at)}</span>
                <SentimentBadge sentiment={a.sentiment} score={a.compound_score} />
              </div>
              <h3 className="text-sm font-semibold group-hover:text-primary">{a.title} <ExternalLink className="ml-1 inline h-3 w-3 opacity-0 group-hover:opacity-60" /></h3>
              {a.summary && <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{a.summary}</p>}
            </a>
          ))}
        </div>
      </div>
    </div>
  );
}

function SentimentPlayground() {
  const [text, setText] = useState("Shares surge after the company beats expectations and raises full-year guidance");
  const analyze = useMutation({ mutationFn: () => newsApi.analyze(text).then((r) => r.data), onError: (e) => toast.error(apiError(e)) });
  const r = analyze.data;
  return (
    <Card>
      <CardHeader title={<span className="flex items-center gap-1.5"><FlaskConical className="h-4 w-4 text-primary" /> Try the sentiment model</span>} description="Type any financial headline to see how it is classified" />
      <CardContent className="space-y-3">
        <textarea value={text} onChange={(e) => setText(e.target.value)} rows={3} className="w-full rounded-md border border-input bg-background/50 p-2 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring" />
        <Button size="sm" onClick={() => analyze.mutate()} disabled={!text.trim() || analyze.isPending}>{analyze.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : "Analyze"}</Button>
        {r && (
          <div className="space-y-2 rounded-lg border border-border/40 p-3 text-xs">
            <div className="flex items-center justify-between"><SentimentBadge sentiment={r.sentiment} score={r.compound_score} /><span className="text-muted-foreground">{r.model_used}</span></div>
            {[["Positive", r.positive_score, "bg-profit"], ["Neutral", r.neutral_score, "bg-muted-foreground"], ["Negative", r.negative_score, "bg-loss"]].map(([l, v, c]) => (
              <div key={l as string} className="flex items-center gap-2">
                <span className="w-16">{l}</span>
                <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted"><div className={`h-full ${c}`} style={{ width: `${(v as number) * 100}%` }} /></div>
                <span className="w-10 text-right font-mono">{((v as number) * 100).toFixed(0)}%</span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
