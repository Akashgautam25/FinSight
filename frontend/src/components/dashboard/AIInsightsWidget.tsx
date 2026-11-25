"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { newsApi } from "@/lib/api";
import { ExternalLink, TrendingUp, TrendingDown, Minus } from "lucide-react";

function SentimentIcon({ sentiment }: { sentiment: string }) {
  if (sentiment === "positive") return <TrendingUp className="h-3 w-3 text-profit" />;
  if (sentiment === "negative") return <TrendingDown className="h-3 w-3 text-loss" />;
  return <Minus className="h-3 w-3 text-muted-foreground" />;
}

export function AIInsightsWidget() {
  const { data, isLoading } = useQuery({
    queryKey: ["market-news-overview"],
    queryFn: () => newsApi.getMarket(5).then((r) => r.data),
    refetchInterval: 10 * 60 * 1000,
  });

  const articles = data?.articles || [];

  return (
    <div className="rounded-xl border border-border/50 bg-card p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="font-semibold text-sm">Market Intelligence</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Latest financial news with FinBERT sentiment
          </p>
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-3 animate-pulse">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-14 bg-muted rounded-lg" />
          ))}
        </div>
      ) : articles.length === 0 ? (
        <div className="py-8 text-center text-sm text-muted-foreground">
          Configure NEWS_API_KEY or FINNHUB_API_KEY to load news.
        </div>
      ) : (
        <div className="space-y-3">
          {articles.map((article: any) => (
            <a
              key={article.id}
              href={article.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-start gap-3 p-3 rounded-lg bg-muted/20 hover:bg-muted/40 transition-colors group"
            >
              <SentimentIcon sentiment={article.sentiment} />
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium line-clamp-2 group-hover:text-primary transition-colors">
                  {article.title}
                </p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {article.source} · {article.published_at ? new Date(article.published_at).toLocaleDateString() : ""}
                </p>
              </div>
              <ExternalLink className="h-3 w-3 text-muted-foreground shrink-0 mt-0.5 opacity-0 group-hover:opacity-100 transition-opacity" />
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
