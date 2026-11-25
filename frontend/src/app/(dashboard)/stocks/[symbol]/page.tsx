// Stock detail page — /stocks/[symbol]
"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { stocksApi } from "@/lib/api";
import { formatCurrency, formatLargeNumber, formatPercent, getPriceChangeClass } from "@/lib/utils";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { StockChartPanel } from "@/components/stocks/StockChart";
import { TechnicalIndicatorsPanel } from "@/components/stocks/TechnicalIndicators";
import { TrendingUp, TrendingDown, AlertCircle } from "lucide-react";

const PERIODS = [
  { label: "1D", value: "1d", interval: "5m" },
  { label: "1W", value: "5d", interval: "1h" },
  { label: "1M", value: "1mo", interval: "1d" },
  { label: "3M", value: "3mo", interval: "1d" },
  { label: "6M", value: "6mo", interval: "1d" },
  { label: "1Y", value: "1y", interval: "1d" },
  { label: "5Y", value: "5y", interval: "1wk" },
];

export default function StockDetailPage() {
  const params = useParams();
  const symbol = (params.symbol as string)?.toUpperCase();

  const { data: stock, isLoading, error } = useQuery({
    queryKey: ["stock", symbol],
    queryFn: () => stocksApi.getDetail(symbol).then((r) => r.data),
    enabled: !!symbol,
  });

  if (isLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-8 bg-muted rounded w-48" />
        <div className="grid grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => <div key={i} className="h-24 bg-muted rounded-xl" />)}
        </div>
        <div className="h-80 bg-muted rounded-xl" />
      </div>
    );
  }

  if (error || !stock) {
    return (
      <div className="flex items-center justify-center h-64 gap-3 text-muted-foreground">
        <AlertCircle className="h-5 w-5" />
        <span>Stock {symbol} not found or data unavailable.</span>
      </div>
    );
  }

  const priceChange = stock.current_price && stock.previous_close
    ? stock.current_price - stock.previous_close
    : null;
  const priceChangePct = priceChange && stock.previous_close
    ? (priceChange / stock.previous_close) * 100
    : null;
  const isPositive = (priceChangePct || 0) >= 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold">{stock.name}</h1>
            <span className="text-sm font-mono bg-muted px-2 py-0.5 rounded text-muted-foreground">
              {symbol}
            </span>
            {stock.exchange && (
              <span className="text-xs text-muted-foreground">· {stock.exchange}</span>
            )}
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            {stock.sector && <span>{stock.sector}</span>}
            {stock.sector && stock.industry && <span> · </span>}
            {stock.industry && <span>{stock.industry}</span>}
          </p>
        </div>
        <div className="text-right">
          <p className="text-3xl font-bold font-mono">
            {formatCurrency(stock.current_price, stock.currency)}
          </p>
          {priceChangePct != null && (
            <div className={`flex items-center justify-end gap-1.5 mt-1 ${getPriceChangeClass(priceChangePct)}`}>
              {isPositive ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />}
              <span className="text-sm font-medium font-mono">
                {priceChange != null && (priceChange >= 0 ? "+" : "")}{priceChange?.toFixed(2)} ({formatPercent(priceChangePct)})
              </span>
            </div>
          )}
          <p className="text-xs text-muted-foreground mt-1">Delayed data · Last: {new Date(stock.last_updated || "").toLocaleTimeString()}</p>
        </div>
      </div>

      {/* Key metrics strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
        {[
          { label: "Market Cap", value: formatLargeNumber(stock.metrics?.market_cap) },
          { label: "P/E Ratio", value: stock.metrics?.pe_ratio?.toFixed(2) || "—" },
          { label: "EPS", value: stock.metrics?.eps?.toFixed(2) || "—" },
          { label: "Beta", value: stock.metrics?.beta?.toFixed(2) || "—" },
          { label: "52W High", value: formatCurrency(stock.metrics?.week_52_high, stock.currency) },
          { label: "52W Low", value: formatCurrency(stock.metrics?.week_52_low, stock.currency) },
          { label: "Volume", value: formatLargeNumber(stock.volume) },
          { label: "Div Yield", value: stock.metrics?.dividend_yield ? `${(stock.metrics.dividend_yield * 100).toFixed(2)}%` : "—" },
        ].map((metric) => (
          <div key={metric.label} className="p-3 rounded-lg border border-border/40 bg-card">
            <p className="text-xs text-muted-foreground">{metric.label}</p>
            <p className="text-sm font-semibold font-mono mt-0.5 truncate">{metric.value}</p>
          </div>
        ))}
      </div>

      {/* Chart + Analysis tabs */}
      <Tabs defaultValue="chart">
        <TabsList className="bg-muted/50">
          <TabsTrigger value="chart">Price Chart</TabsTrigger>
          <TabsTrigger value="technical">Technical Analysis</TabsTrigger>
          <TabsTrigger value="fundamentals">Fundamentals</TabsTrigger>
        </TabsList>

        <TabsContent value="chart" className="mt-4">
          <StockChartPanel symbol={symbol} periods={PERIODS} currency={stock.currency} />
        </TabsContent>

        <TabsContent value="technical" className="mt-4">
          <TechnicalIndicatorsPanel symbol={symbol} />
        </TabsContent>

        <TabsContent value="fundamentals" className="mt-4">
          <FundamentalsPanel metrics={stock.metrics} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function FundamentalsPanel({ metrics }: { metrics: any }) {
  if (!metrics) return <div className="text-muted-foreground text-sm">No fundamental data available.</div>;

  const rows = [
    ["Market Capitalization", formatLargeNumber(metrics.market_cap)],
    ["P/E Ratio (Trailing)", metrics.pe_ratio?.toFixed(2) || "—"],
    ["EPS", metrics.eps?.toFixed(4) || "—"],
    ["Dividend Yield", metrics.dividend_yield ? `${(metrics.dividend_yield * 100).toFixed(2)}%` : "—"],
    ["Beta", metrics.beta?.toFixed(4) || "—"],
    ["Return on Equity", metrics.roe ? `${(metrics.roe * 100).toFixed(2)}%` : "—"],
    ["Return on Assets", metrics.roa ? `${(metrics.roa * 100).toFixed(2)}%` : "—"],
    ["Debt to Equity", metrics.debt_to_equity?.toFixed(2) || "—"],
    ["Profit Margin", metrics.profit_margin ? `${(metrics.profit_margin * 100).toFixed(2)}%` : "—"],
    ["Revenue Growth", metrics.revenue_growth ? `${(metrics.revenue_growth * 100).toFixed(2)}%` : "—"],
    ["Free Cash Flow", formatLargeNumber(metrics.free_cash_flow)],
    ["52-Week High", metrics.week_52_high?.toFixed(2) || "—"],
    ["52-Week Low", metrics.week_52_low?.toFixed(2) || "—"],
  ];

  return (
    <div className="rounded-xl border border-border/40 bg-card overflow-hidden">
      <div className="divide-y divide-border/30">
        {rows.map(([label, value]) => (
          <div key={label} className="flex items-center justify-between px-4 py-3">
            <span className="text-sm text-muted-foreground">{label}</span>
            <span className="text-sm font-mono font-medium">{value}</span>
          </div>
        ))}
      </div>
      <div className="px-4 py-3 bg-muted/20 border-t border-border/30">
        <p className="text-xs text-muted-foreground">
          Source: yfinance · As of: {metrics.as_of_date || "unknown"} · Data sourced from public financial filings.
        </p>
      </div>
    </div>
  );
}

// Needed formatter
function formatLargeNumber(value: number | null | undefined): string {
  if (value == null) return "—";
  if (Math.abs(value) >= 1e12) return `$${(value / 1e12).toFixed(2)}T`;
  if (Math.abs(value) >= 1e9) return `$${(value / 1e9).toFixed(2)}B`;
  if (Math.abs(value) >= 1e6) return `$${(value / 1e6).toFixed(2)}M`;
  return value.toFixed(2);
}
