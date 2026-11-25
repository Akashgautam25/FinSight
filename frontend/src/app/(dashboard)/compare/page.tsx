// Stock Comparison Page (Up to 5 stocks)
"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { stocksApi } from "@/lib/api";
import { formatCurrency, formatPercent } from "@/lib/utils";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { ArrowLeftRight, Check, Loader2 } from "lucide-react";

export default function ComparePage() {
  const [symbolsInput, setSymbolsInput] = useState("AAPL, MSFT, GOOGL");
  const [activeSymbols, setActiveSymbols] = useState(["AAPL", "MSFT", "GOOGL"]);

  const { data, isLoading } = useQuery({
    queryKey: ["compare-stocks", activeSymbols],
    queryFn: () => stocksApi.compare(activeSymbols).then((r) => r.data),
    enabled: activeSymbols.length > 0,
  });

  const handleRun = () => {
    const list = symbolsInput.split(",").map((s) => s.trim().toUpperCase()).filter(Boolean).slice(0, 5);
    setActiveSymbols(list);
  };

  const comparison = data?.comparison || {};

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Stock Comparison Engine</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Simultaneously benchmark up to 5 companies across valuation, growth, volatility, and financial ratios
        </p>
      </div>

      <div className="flex gap-2 max-w-xl">
        <Input
          value={symbolsInput}
          onChange={(e) => setSymbolsInput(e.target.value)}
          placeholder="e.g. AAPL, NVDA, TSLA, AMD (max 5)"
        />
        <Button onClick={handleRun}>Compare</Button>
      </div>

      {isLoading ? (
        <div className="h-64 rounded-xl bg-muted/30 animate-pulse flex items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : Object.keys(comparison).length > 0 ? (
        <div className="rounded-xl border border-border/40 bg-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/30 bg-muted/20">
                  <th className="text-left px-5 py-3 text-xs font-semibold text-muted-foreground">Metric</th>
                  {activeSymbols.map((s) => (
                    <th key={s} className="text-right px-4 py-3 text-xs font-bold font-mono text-primary">
                      {s}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border/20">
                <ComparisonRow
                  label="Company Name"
                  symbols={activeSymbols}
                  comparison={comparison}
                  accessor={(d) => d?.detail?.name || "—"}
                />
                <ComparisonRow
                  label="Sector"
                  symbols={activeSymbols}
                  comparison={comparison}
                  accessor={(d) => d?.detail?.sector || "—"}
                />
                <ComparisonRow
                  label="Current Price"
                  symbols={activeSymbols}
                  comparison={comparison}
                  accessor={(d) => formatCurrency(d?.detail?.current_price)}
                />
                <ComparisonRow
                  label="Trailing P/E"
                  symbols={activeSymbols}
                  comparison={comparison}
                  accessor={(d) => d?.detail?.metrics?.pe_ratio?.toFixed(2) || "—"}
                />
                <ComparisonRow
                  label="Beta (5Y Monthly)"
                  symbols={activeSymbols}
                  comparison={comparison}
                  accessor={(d) => d?.detail?.metrics?.beta?.toFixed(2) || "—"}
                />
                <ComparisonRow
                  label="Return on Equity (ROE)"
                  symbols={activeSymbols}
                  comparison={comparison}
                  accessor={(d) => d?.detail?.metrics?.roe ? `${(d.detail.metrics.roe * 100).toFixed(1)}%` : "—"}
                />
                <ComparisonRow
                  label="Profit Margin"
                  symbols={activeSymbols}
                  comparison={comparison}
                  accessor={(d) => d?.detail?.metrics?.profit_margin ? `${(d.detail.metrics.profit_margin * 100).toFixed(1)}%` : "—"}
                />
                <ComparisonRow
                  label="Debt to Equity"
                  symbols={activeSymbols}
                  comparison={comparison}
                  accessor={(d) => d?.detail?.metrics?.debt_to_equity?.toFixed(2) || "—"}
                />
                <ComparisonRow
                  label="Dividend Yield"
                  symbols={activeSymbols}
                  comparison={comparison}
                  accessor={(d) => d?.detail?.metrics?.dividend_yield ? `${(d.detail.metrics.dividend_yield * 100).toFixed(2)}%` : "—"}
                />
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function ComparisonRow({ label, symbols, comparison, accessor }: {
  label: string;
  symbols: string[];
  comparison: any;
  accessor: (item: any) => string;
}) {
  return (
    <tr className="hover:bg-muted/10 transition-colors">
      <td className="px-5 py-3 font-medium text-muted-foreground">{label}</td>
      {symbols.map((sym) => (
        <td key={sym} className="text-right px-4 py-3 font-mono">
          {accessor(comparison[sym])}
        </td>
      ))}
    </tr>
  );
}
