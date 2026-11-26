"use client";

import Link from "next/link";
import { Brain, MessageSquare, PieChart, FileText } from "lucide-react";
import { MarketOverviewWidget } from "@/components/dashboard/MarketOverview";
import { PortfolioSummary } from "@/components/dashboard/PortfolioSummary";
import { WatchlistWidget } from "@/components/dashboard/WatchlistWidget";
import { AIInsightsWidget } from "@/components/dashboard/AIInsightsWidget";
import { useCurrentUser } from "@/hooks/useAuth";
import { AIInsightCard } from "@/components/ai/AIInsightCard";

const ACTIONS = [
  { href: "/assistant", label: "Ask the AI assistant", icon: MessageSquare },
  { href: "/predictions", label: "Train a forecast model", icon: Brain },
  { href: "/optimizer", label: "Optimize a portfolio", icon: PieChart },
  { href: "/reports", label: "Generate a PDF report", icon: FileText },
];

export default function OverviewPage() {
  const { data: user } = useCurrentUser();
  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{greeting}{user?.full_name ? `, ${user.full_name.split(" ")[0]}` : ""} 👋</h1>
          <p className="mt-1 text-sm text-muted-foreground">Here is your market and portfolio snapshot.</p>
        </div>
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          {ACTIONS.map((a) => (
            <Link key={a.href} href={a.href} className="flex items-center gap-2 rounded-lg border border-border/40 bg-card px-3 py-2 text-xs font-medium hover:border-primary/40 hover:bg-primary/5">
              <a.icon className="h-4 w-4 text-primary" /> {a.label}
            </Link>
          ))}
        </div>
      </div>
      <AIInsightCard kind="market" title="AI market briefing" description="Written by the AI from today's indices, movers and headlines" />
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <div className="xl:col-span-2"><MarketOverviewWidget /></div>
        <PortfolioSummary />
      </div>
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <WatchlistWidget />
        <AIInsightsWidget />
      </div>
    </div>
  );
}
