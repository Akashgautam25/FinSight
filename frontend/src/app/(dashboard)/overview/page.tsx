// Dashboard Overview Page
"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { MarketOverviewWidget } from "@/components/dashboard/MarketOverview";
import { PortfolioSummary } from "@/components/dashboard/PortfolioSummary";
import { WatchlistWidget } from "@/components/dashboard/WatchlistWidget";
import { AIInsightsWidget } from "@/components/dashboard/AIInsightsWidget";

export default function OverviewPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Overview</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Financial intelligence dashboard — market overview and portfolio performance
        </p>
      </div>

      {/* Top row: Market + Portfolio */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className="xl:col-span-2">
          <MarketOverviewWidget />
        </div>
        <div>
          <PortfolioSummary />
        </div>
      </div>

      {/* Bottom row: Watchlist + AI Insights */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <WatchlistWidget />
        <AIInsightsWidget />
      </div>
    </div>
  );
}
