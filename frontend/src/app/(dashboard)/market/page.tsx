// Market Explorer page — search and discover stocks
"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { stocksApi } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Search, TrendingUp, ArrowRight } from "lucide-react";
import Link from "next/link";
import { useDebounce } from "@/hooks/useDebounce";

export default function MarketPage() {
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebounce(query, 300);

  const { data: searchResults, isLoading } = useQuery({
    queryKey: ["stock-search", debouncedQuery],
    queryFn: () => stocksApi.search(debouncedQuery).then((r) => r.data),
    enabled: debouncedQuery.length >= 1,
  });

  const { data: overview } = useQuery({
    queryKey: ["market-overview"],
    queryFn: () => stocksApi.getMarketOverview().then((r) => r.data),
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Market Explorer</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Search and research publicly traded companies
        </p>
      </div>

      {/* Search bar */}
      <div className="relative max-w-xl">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search by company name or ticker (e.g. AAPL, Tesla)"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="pl-10 h-11"
        />
      </div>

      {/* Search results */}
      {debouncedQuery && (
        <div className="rounded-xl border border-border/40 bg-card overflow-hidden">
          {isLoading ? (
            <div className="p-4 space-y-3 animate-pulse">
              {[1, 2, 3].map((i) => <div key={i} className="h-12 bg-muted rounded" />)}
            </div>
          ) : searchResults && searchResults.length > 0 ? (
            <div className="divide-y divide-border/30">
              {searchResults.map((stock: any) => (
                <Link
                  key={stock.symbol}
                  href={`/stocks/${stock.symbol}`}
                  className="flex items-center justify-between p-4 hover:bg-muted/30 transition-colors group"
                >
                  <div className="flex items-center gap-4">
                    <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center">
                      <TrendingUp className="h-4 w-4 text-primary" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-sm font-mono">{stock.symbol}</span>
                        <span className="text-xs text-muted-foreground">· {stock.exchange}</span>
                      </div>
                      <p className="text-sm text-muted-foreground">{stock.name}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 text-right">
                    {stock.sector && (
                      <span className="text-xs bg-muted/60 px-2 py-0.5 rounded text-muted-foreground">
                        {stock.sector}
                      </span>
                    )}
                    <ArrowRight className="h-4 w-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <div className="p-6 text-center text-sm text-muted-foreground">
              No results for "{debouncedQuery}". Try a ticker symbol (e.g., AAPL, MSFT, RELIANCE.NS)
            </div>
          )}
        </div>
      )}

      {/* Market overview when not searching */}
      {!debouncedQuery && overview && (
        <div>
          <h2 className="text-sm font-semibold mb-3 text-muted-foreground">MARKET INDICES</h2>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            {(overview.indices || []).map((index: any) => (
              <div key={index.symbol} className="p-4 rounded-xl border border-border/40 bg-card">
                <p className="text-xs text-muted-foreground truncate">{index.name}</p>
                <p className="text-lg font-bold font-mono mt-1">
                  {index.value?.toLocaleString("en-US", { maximumFractionDigits: 0 })}
                </p>
                <p className={`text-xs font-medium ${index.change_pct >= 0 ? "text-profit" : "text-loss"}`}>
                  {index.change_pct >= 0 ? "▲" : "▼"} {Math.abs(index.change_pct).toFixed(2)}%
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Popular stocks */}
      {!debouncedQuery && (
        <div>
          <h2 className="text-sm font-semibold mb-3 text-muted-foreground">QUICK ACCESS</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "TSLA", "META", "JPM"].map((sym) => (
              <Link
                key={sym}
                href={`/stocks/${sym}`}
                className="flex items-center gap-3 p-3 rounded-lg border border-border/40 bg-card hover:border-primary/40 hover:bg-primary/5 transition-all group"
              >
                <div className="w-8 h-8 rounded-md bg-muted flex items-center justify-center text-xs font-bold">
                  {sym[0]}
                </div>
                <span className="text-sm font-mono font-semibold">{sym}</span>
                <ArrowRight className="h-3 w-3 text-muted-foreground ml-auto opacity-0 group-hover:opacity-100 transition-opacity" />
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
