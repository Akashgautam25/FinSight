"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeftRight, Bell, Bookmark, Brain, Briefcase, ChevronLeft, ChevronRight, FileText, LayoutDashboard,
  LineChart, Loader2, LogOut, Menu, MessageSquare, Newspaper, PieChart, Settings, Sparkles, TrendingUp, X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { systemApi, tokens } from "@/lib/api";
import { DisclaimerBanner } from "@/components/common/DisclaimerBanner";
import { SymbolSearch } from "@/components/common/SymbolSearch";
import { NotificationBell } from "@/components/layout/NotificationBell";
import { useCurrentUser, useLogout } from "@/hooks/useAuth";

const NAV_ITEMS = [
  { href: "/overview", label: "Overview", icon: LayoutDashboard },
  { href: "/market", label: "Markets", icon: LineChart, match: ["/market", "/stocks"] },
  { href: "/assistant", label: "AI Assistant", icon: MessageSquare },
  { href: "/predictions", label: "Predictions", icon: Brain },
  { href: "/portfolio", label: "Portfolio", icon: Briefcase },
  { href: "/optimizer", label: "Optimizer", icon: PieChart },
  { href: "/compare", label: "Compare", icon: ArrowLeftRight },
  { href: "/news", label: "News & Sentiment", icon: Newspaper },
  { href: "/reports", label: "Research Reports", icon: FileText },
  { href: "/watchlists", label: "Watchlists", icon: Bookmark },
  { href: "/alerts", label: "Price Alerts", icon: Bell },
  { href: "/settings", label: "Settings", icon: Settings },
];

function DataSourcePill() {
  const { data } = useQuery({ queryKey: ["system-status"], queryFn: () => systemApi.status().then((r) => r.data), refetchInterval: 60_000 });
  if (!data) return null;
  const live = data.market_data.mode !== "demo" && data.market_data.live_available;
  return (
    <Link
      href="/settings"
      title={live ? "Live market data from Yahoo Finance (15–20 min delayed)" : "Live data unavailable — showing simulated data"}
      className={cn(
        "hidden md:inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium",
        live ? "border-profit/30 text-profit" : "border-amber-500/30 text-amber-500"
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", live ? "bg-profit animate-pulse" : "bg-amber-500")} />
      {live ? "Live data" : "Simulated data"}
    </Link>
  );
}

function AIPill() {
  const { data } = useQuery({ queryKey: ["system-status"], queryFn: () => systemApi.status().then((r) => r.data), refetchInterval: 60_000 });
  const ai = data?.llm;
  if (!ai) return null;
  const on = ai.mode === "llm";
  return (
    <Link
      href="/settings"
      title={on ? `AI model: ${ai.active}` : "No LLM available — start Ollama or add GOOGLE_API_KEY"}
      className={cn("hidden md:inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium", on ? "border-primary/40 text-primary" : "border-border text-muted-foreground")}
    >
      <Sparkles className="h-3 w-3" />
      {on ? `AI · ${ai.active.split(":").slice(1).join(":")}${ai.is_local ? " (local)" : ""}` : "AI offline"}
    </Link>
  );
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [ready, setReady] = useState(false);
  const pathname = usePathname();
  const router = useRouter();
  const logout = useLogout();

  useEffect(() => {
    if (!tokens.access && !tokens.refresh) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    } else {
      setReady(true);
    }
  }, [pathname, router]);

  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  const { data: user } = useCurrentUser(ready);

  if (!ready) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const isActive = (item: (typeof NAV_ITEMS)[number]) => (item.match ?? [item.href]).some((p) => pathname.startsWith(p));
  const initials = (user?.full_name || user?.email || "?").split(/[\s@]/).filter(Boolean).slice(0, 2).map((s: string) => s[0]?.toUpperCase()).join("");

  const nav = (compact: boolean) => (
    <nav className="flex-1 space-y-0.5 overflow-y-auto px-2 py-3">
      {NAV_ITEMS.map((item) => {
        const active = isActive(item);
        return (
          <Link key={item.href} href={item.href} title={compact ? item.label : undefined}>
            <div
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                active ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-accent hover:text-foreground"
              )}
            >
              <item.icon className="h-4 w-4 shrink-0" />
              {!compact && <span className="truncate">{item.label}</span>}
            </div>
          </Link>
        );
      })}
    </nav>
  );

  const logo = (compact: boolean) => (
    <Link href="/overview" className="flex items-center gap-3 border-b border-border/40 px-4 py-4">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/15">
        <TrendingUp className="h-4 w-4 text-primary" />
      </div>
      {!compact && <span className="text-sm font-semibold tracking-tight">FinSight AI</span>}
    </Link>
  );

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Desktop sidebar */}
      <aside className={cn("relative hidden shrink-0 flex-col border-r border-border/50 bg-card transition-[width] duration-200 lg:flex", collapsed ? "w-16" : "w-60")}>
        {logo(collapsed)}
        {nav(collapsed)}
        <button
          onClick={() => setCollapsed((c) => !c)}
          className="absolute -right-3 top-16 flex h-6 w-6 items-center justify-center rounded-full border border-border bg-background shadow-sm hover:bg-accent"
          aria-label="Toggle sidebar"
        >
          {collapsed ? <ChevronRight className="h-3 w-3" /> : <ChevronLeft className="h-3 w-3" />}
        </button>
      </aside>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-black/60" onClick={() => setMobileOpen(false)} />
          <aside className="relative flex h-full w-64 flex-col border-r border-border bg-card">
            <button onClick={() => setMobileOpen(false)} className="absolute right-3 top-4 text-muted-foreground" aria-label="Close menu">
              <X className="h-4 w-4" />
            </button>
            {logo(false)}
            {nav(false)}
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <header className="flex h-14 shrink-0 items-center gap-3 border-b border-border/50 bg-card/50 px-4 backdrop-blur">
          <button onClick={() => setMobileOpen(true)} className="lg:hidden" aria-label="Open menu">
            <Menu className="h-5 w-5" />
          </button>
          <SymbolSearch onSelect={(s) => router.push(`/stocks/${encodeURIComponent(s)}`)} className="w-full max-w-md" placeholder="Search any stock… (press Enter)" />
          <div className="ml-auto flex items-center gap-2">
            <AIPill />
            <DataSourcePill />
            <NotificationBell />
            <Link href="/settings" className="flex items-center gap-2 rounded-md px-1.5 py-1 hover:bg-accent" title={user?.email}>
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/15 text-xs font-semibold text-primary">{initials}</span>
              <span className="hidden max-w-[140px] truncate text-sm xl:block">{user?.full_name || user?.email}</span>
            </Link>
            <button onClick={logout} className="flex h-9 w-9 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground" title="Sign out" aria-label="Sign out">
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </header>
        <DisclaimerBanner />
        <main className="flex-1 overflow-y-auto p-4 md:p-6">{children}</main>
      </div>
    </div>
  );
}
