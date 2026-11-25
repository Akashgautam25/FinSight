// Portfolio Manager page
"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { portfolioApi } from "@/lib/api";
import { formatCurrency, formatPercent, getPriceChangeClass } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Plus, Trash2, ArrowUpRight, ArrowDownRight, Briefcase, Loader2 } from "lucide-react";
import { toast } from "sonner";

export default function PortfolioPage() {
  const queryClient = useQueryClient();
  const [showAddModal, setShowAddModal] = useState(false);
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string | null>(null);

  // Form states for transaction
  const [symbol, setSymbol] = useState("");
  const [quantity, setQuantity] = useState("");
  const [price, setPrice] = useState("");
  const [type, setType] = useState<"BUY" | "SELL">("BUY");

  const { data: portfolios, isLoading: loadingPortfolios } = useQuery({
    queryKey: ["portfolios"],
    queryFn: () => portfolioApi.list().then((r) => r.data),
  });

  const activeId = selectedPortfolioId || (portfolios?.[0]?.id ?? null);

  const { data: analytics, isLoading: loadingAnalytics } = useQuery({
    queryKey: ["portfolio-analytics", activeId],
    queryFn: () => portfolioApi.getAnalytics(activeId!).then((r) => r.data),
    enabled: !!activeId,
  });

  const createPortfolioMutation = useMutation({
    mutationFn: (name: string) => portfolioApi.create({ name, currency: "USD" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["portfolios"] });
      toast.success("Portfolio created successfully");
    },
  });

  const addTxnMutation = useMutation({
    mutationFn: () =>
      portfolioApi.addTransaction(activeId!, {
        symbol: symbol.toUpperCase(),
        transaction_type: type,
        quantity: parseFloat(quantity),
        price: parseFloat(price),
        fees: 0,
        transaction_date: new Date().toISOString(),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["portfolio-analytics", activeId] });
      toast.success("Transaction recorded");
      setShowAddModal(false);
      setSymbol("");
      setQuantity("");
      setPrice("");
    },
    onError: () => toast.error("Failed to add transaction"),
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Portfolio Manager</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Real-time portfolio tracking, positions, transaction history, and quantitative risk metrics
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              const name = prompt("Enter new portfolio name:");
              if (name) createPortfolioMutation.mutate(name);
            }}
          >
            New Portfolio
          </Button>
          <Button size="sm" onClick={() => setShowAddModal(!showAddModal)} disabled={!activeId}>
            <Plus className="h-4 w-4 mr-1.5" /> Record Transaction
          </Button>
        </div>
      </div>

      {/* Add Transaction Bar */}
      {showAddModal && (
        <div className="p-4 rounded-xl border border-primary/30 bg-card/90 space-y-3">
          <h3 className="text-sm font-semibold">Record Buy / Sell Order</h3>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <Input placeholder="Symbol (e.g. AAPL)" value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} />
            <div className="flex rounded-md border border-input overflow-hidden">
              <button
                type="button"
                className={`flex-1 text-xs font-semibold py-2 ${type === "BUY" ? "bg-profit text-white" : "bg-card text-muted-foreground"}`}
                onClick={() => setType("BUY")}
              >
                BUY
              </button>
              <button
                type="button"
                className={`flex-1 text-xs font-semibold py-2 ${type === "SELL" ? "bg-loss text-white" : "bg-card text-muted-foreground"}`}
                onClick={() => setType("SELL")}
              >
                SELL
              </button>
            </div>
            <Input type="number" placeholder="Quantity" value={quantity} onChange={(e) => setQuantity(e.target.value)} />
            <Input type="number" placeholder="Execution Price ($)" value={price} onChange={(e) => setPrice(e.target.value)} />
            <Button
              onClick={() => addTxnMutation.mutate()}
              disabled={!symbol || !quantity || !price || addTxnMutation.isPending}
            >
              {addTxnMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : "Save"}
            </Button>
          </div>
        </div>
      )}

      {/* Analytics KPI Ribbon */}
      {analytics && (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
          <div className="p-4 rounded-xl border border-border/40 bg-card">
            <p className="text-xs text-muted-foreground">Portfolio Value</p>
            <p className="text-xl font-bold font-mono mt-1">{formatCurrency(analytics.current_value)}</p>
          </div>
          <div className="p-4 rounded-xl border border-border/40 bg-card">
            <p className="text-xs text-muted-foreground">Invested Capital</p>
            <p className="text-xl font-bold font-mono mt-1">{formatCurrency(analytics.total_invested)}</p>
          </div>
          <div className="p-4 rounded-xl border border-border/40 bg-card">
            <p className="text-xs text-muted-foreground">Unrealized P&L</p>
            <p className={`text-xl font-bold font-mono mt-1 ${getPriceChangeClass(analytics.absolute_return)}`}>
              {formatCurrency(analytics.absolute_return)} ({formatPercent(analytics.return_pct)})
            </p>
          </div>
          <div className="p-4 rounded-xl border border-border/40 bg-card">
            <p className="text-xs text-muted-foreground">Sharpe Ratio</p>
            <p className="text-xl font-bold font-mono mt-1">{analytics.sharpe_ratio ? analytics.sharpe_ratio.toFixed(2) : "—"}</p>
          </div>
          <div className="p-4 rounded-xl border border-border/40 bg-card">
            <p className="text-xs text-muted-foreground">Ann. Volatility</p>
            <p className="text-xl font-bold font-mono mt-1">{analytics.portfolio_volatility ? `${analytics.portfolio_volatility.toFixed(1)}%` : "—"}</p>
          </div>
          <div className="p-4 rounded-xl border border-border/40 bg-card">
            <p className="text-xs text-muted-foreground">Max Drawdown</p>
            <p className="text-xl font-bold font-mono mt-1 text-loss">{analytics.max_drawdown ? `${analytics.max_drawdown.toFixed(1)}%` : "—"}</p>
          </div>
        </div>
      )}

      {/* Holdings Table */}
      <div className="rounded-xl border border-border/40 bg-card overflow-hidden">
        <div className="px-5 py-4 border-b border-border/30 flex items-center justify-between">
          <h3 className="font-semibold text-sm">Active Holdings</h3>
          <span className="text-xs text-muted-foreground">{analytics?.holdings?.length || 0} Assets</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border/30 bg-muted/20 text-xs text-muted-foreground">
                <th className="text-left px-5 py-3">Asset</th>
                <th className="text-right px-4 py-3">Quantity</th>
                <th className="text-right px-4 py-3">Avg Cost</th>
                <th className="text-right px-4 py-3">Current Price</th>
                <th className="text-right px-4 py-3">Market Value</th>
                <th className="text-right px-4 py-3">Unrealized P&L</th>
                <th className="text-right px-4 py-3">Weight</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/20">
              {analytics?.holdings && analytics.holdings.length > 0 ? (
                analytics.holdings.map((h: any) => (
                  <tr key={h.id} className="hover:bg-muted/10 transition-colors">
                    <td className="px-5 py-3 font-semibold font-mono">{h.symbol}</td>
                    <td className="text-right px-4 py-3 font-mono">{h.quantity}</td>
                    <td className="text-right px-4 py-3 font-mono">{formatCurrency(h.avg_purchase_price)}</td>
                    <td className="text-right px-4 py-3 font-mono">{formatCurrency(h.current_price)}</td>
                    <td className="text-right px-4 py-3 font-mono font-medium">{formatCurrency(h.current_value)}</td>
                    <td className={`text-right px-4 py-3 font-mono font-medium ${getPriceChangeClass(h.unrealized_pnl)}`}>
                      {formatCurrency(h.unrealized_pnl)} ({formatPercent(h.unrealized_pnl_pct)})
                    </td>
                    <td className="text-right px-4 py-3 font-mono text-muted-foreground">{h.weight ? `${h.weight.toFixed(1)}%` : "—"}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={7} className="px-5 py-8 text-center text-muted-foreground">
                    No holdings in this portfolio. Click "Record Transaction" to add your first position.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
