// Watchlists Page
"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Bookmark, Plus, Trash2, ArrowUpRight, TrendingUp } from "lucide-react";
import Link from "next/link";

interface WatchlistItem {
  symbol: string;
  name: string;
  price: number;
  change: number;
}

const DEFAULT_WATCHLIST: WatchlistItem[] = [
  { symbol: "AAPL", name: "Apple Inc.", price: 228.87, change: 1.42 },
  { symbol: "NVDA", name: "NVIDIA Corp.", price: 141.25, change: 2.15 },
  { symbol: "MSFT", name: "Microsoft Corp.", price: 418.12, change: -0.34 },
  { symbol: "TSLA", name: "Tesla, Inc.", price: 342.10, change: 3.80 },
];

export default function WatchlistsPage() {
  const [items, setItems] = useState<WatchlistItem[]>(DEFAULT_WATCHLIST);
  const [newSymbol, setNewSymbol] = useState("");

  const handleAdd = () => {
    if (!newSymbol.trim()) return;
    const sym = newSymbol.trim().toUpperCase();
    if (items.some((i) => i.symbol === sym)) return;
    setItems((prev) => [
      ...prev,
      { symbol: sym, name: `${sym} Equity`, price: 100.0, change: 0.0 },
    ]);
    setNewSymbol("");
  };

  const handleRemove = (sym: string) => {
    setItems((prev) => prev.filter((i) => i.symbol !== sym));
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Watchlists</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Monitor target securities, trigger price alert thresholds, and track daily volatility
          </p>
        </div>
      </div>

      <div className="flex gap-2 max-w-sm">
        <Input
          placeholder="Add Ticker (e.g. GOOGL)"
          value={newSymbol}
          onChange={(e) => setNewSymbol(e.target.value.toUpperCase())}
          onKeyDown={(e) => e.key === "Enter" && handleAdd()}
        />
        <Button onClick={handleAdd}>
          <Plus className="h-4 w-4 mr-1" /> Add
        </Button>
      </div>

      <div className="rounded-xl border border-border/40 bg-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border/30 bg-muted/20 text-xs text-muted-foreground">
                <th className="text-left px-5 py-3">Asset</th>
                <th className="text-right px-4 py-3">Current Price</th>
                <th className="text-right px-4 py-3">Daily Change</th>
                <th className="text-right px-5 py-3">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/20">
              {items.map((item) => (
                <tr key={item.symbol} className="hover:bg-muted/10 transition-colors">
                  <td className="px-5 py-3.5">
                    <Link href={`/stocks/${item.symbol}`} className="font-semibold font-mono hover:text-primary transition-colors">
                      {item.symbol}
                    </Link>
                    <span className="text-xs text-muted-foreground ml-2">{item.name}</span>
                  </td>
                  <td className="text-right px-4 py-3.5 font-mono font-medium">
                    ${item.price.toFixed(2)}
                  </td>
                  <td className={`text-right px-4 py-3.5 font-mono font-medium ${item.change >= 0 ? "text-profit" : "text-loss"}`}>
                    {item.change >= 0 ? "+" : ""}{item.change.toFixed(2)}%
                  </td>
                  <td className="text-right px-5 py-3.5">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleRemove(item.symbol)}
                      className="text-muted-foreground hover:text-destructive h-7 px-2"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
