"use client";

import { Bookmark } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";

// Watchlist widget — displays saved stocks with mini price info
// In production: fetched from /api/v1/watchlists and enriched with live prices
export function WatchlistWidget() {
  return (
    <div className="rounded-xl border border-border/50 bg-card p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-semibold text-sm">Watchlist</h2>
        <Link href="/watchlists">
          <Button variant="ghost" size="sm" className="text-xs">Manage</Button>
        </Link>
      </div>

      <div className="flex flex-col items-center justify-center py-8 gap-3 text-center">
        <Bookmark className="h-8 w-8 text-muted-foreground" />
        <p className="text-sm text-muted-foreground">
          Add stocks to your watchlist to monitor them here.
        </p>
        <Link href="/market">
          <Button size="sm" variant="outline">Browse Stocks</Button>
        </Link>
      </div>
    </div>
  );
}
