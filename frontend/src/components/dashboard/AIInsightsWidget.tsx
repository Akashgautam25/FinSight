"use client";

import { useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import { newsApi } from "@/lib/api";
import { timeAgo } from "@/lib/utils";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { DemoBadge } from "@/components/common/DemoBadge";
import { SentimentBadge } from "@/components/news/SentimentBadge";

export function AIInsightsWidget() {
  const { data, isLoading } = useQuery({
    queryKey: ["market-news", "overview"],
    queryFn: () => newsApi.getMarket(6).then((r) => r.data),
    refetchInterval: 10 * 60 * 1000,
  });

  return (
    <Card>
      <CardHeader title="Market Intelligence" description={`Latest headlines scored by ${data?.sentiment_model === "ProsusAI/finbert" ? "FinBERT" : "the financial sentiment model"}`}
        action={<DemoBadge show={!!data?.is_demo} />} />
      <CardContent>
        {isLoading ? (
          <div className="space-y-2">{[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-14" />)}</div>
        ) : (
          <div className="space-y-2">
            {(data?.articles ?? []).map((a: any) => (
              <a key={a.id} href={a.url} target="_blank" rel="noopener noreferrer" className="group flex items-start gap-3 rounded-lg bg-muted/20 p-3 hover:bg-muted/40">
                <SentimentBadge sentiment={a.sentiment} compact />
                <div className="min-w-0 flex-1">
                  <p className="line-clamp-2 text-xs font-medium group-hover:text-primary">{a.title}</p>
                  <p className="mt-0.5 text-[11px] text-muted-foreground">{a.source} · {timeAgo(a.published_at)}</p>
                </div>
                <ExternalLink className="mt-0.5 h-3 w-3 shrink-0 text-muted-foreground opacity-0 group-hover:opacity-100" />
              </a>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
