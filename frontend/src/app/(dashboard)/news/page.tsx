// Financial News & Sentiment Intelligence Page
"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { newsApi } from "@/lib/api";
import { ExternalLink, TrendingUp, TrendingDown, Minus, Filter } from "lucide-react";
import { Button } from "@/components/ui/button";

const SECTORS = ["All", "technology", "finance", "healthcare", "energy"];

export default function NewsPage() {
  const [selectedSector, setSelectedSector] = useState("All");

  const { data, isLoading } = useQuery({
    queryKey: ["financial-news", selectedSector],
    queryFn: () => newsApi.getMarket(30).then((r) => r.data),
  });

  const articles = data?.articles || [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Financial News & Sentiment</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Real-time business news classified by FinBERT transformer model for institutional sentiment scoring
          </p>
        </div>
      </div>

      {/* Sector Filter Bar */}
      <div className="flex gap-1.5 flex-wrap">
        {SECTORS.map((s) => (
          <Button
            key={s}
            variant="ghost"
            size="sm"
            onClick={() => setSelectedSector(s)}
            className={`text-xs capitalize h-7 ${selectedSector === s ? "bg-primary/10 text-primary" : "text-muted-foreground"}`}
          >
            {s}
          </Button>
        ))}
      </div>

      {/* News Cards Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 animate-pulse">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-32 bg-muted/30 rounded-xl" />
          ))}
        </div>
      ) : articles.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {articles.map((item: any) => {
            const isPos = item.sentiment === "positive";
            const isNeg = item.sentiment === "negative";
            return (
              <a
                key={item.id}
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="p-4 rounded-xl border border-border/40 bg-card hover:border-primary/40 hover:bg-muted/10 transition-all flex flex-col justify-between group"
              >
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs text-muted-foreground font-medium">{item.source || "News"}</span>
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full font-medium uppercase tracking-wider ${
                        isPos
                          ? "bg-profit/15 text-profit"
                          : isNeg
                          ? "bg-loss/15 text-loss"
                          : "bg-muted text-muted-foreground"
                      }`}
                    >
                      {item.sentiment}
                    </span>
                  </div>
                  <h3 className="font-semibold text-sm line-clamp-2 group-hover:text-primary transition-colors">
                    {item.title}
                  </h3>
                  {item.summary && (
                    <p className="text-xs text-muted-foreground mt-1.5 line-clamp-2">
                      {item.summary}
                    </p>
                  )}
                </div>
                <div className="flex items-center justify-between pt-3 mt-3 border-t border-border/20 text-xs text-muted-foreground">
                  <span>{item.published_at ? new Date(item.published_at).toLocaleDateString() : ""}</span>
                  <ExternalLink className="h-3 w-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                </div>
              </a>
            );
          })}
        </div>
      ) : (
        <div className="p-8 text-center text-muted-foreground text-sm rounded-xl border border-border/40 bg-card">
          No live news returned. Configure NEWS_API_KEY or FINNHUB_API_KEY in your environment to stream external RSS/APIs.
        </div>
      )}
    </div>
  );
}
