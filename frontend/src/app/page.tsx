// Landing Page — FinSight AI
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  TrendingUp, Brain, Shield, BarChart3, ArrowRight,
  Zap, LineChart, PieChart
} from "lucide-react";

const features = [
  {
    icon: Brain,
    title: "AI Research Assistant",
    description:
      "Ask anything about stocks, portfolios, or markets. Gets verified data before answering.",
  },
  {
    icon: TrendingUp,
    title: "ML Price Predictions",
    description:
      "4 models (Linear Regression, Random Forest, XGBoost, LSTM) with full evaluation metrics.",
  },
  {
    icon: BarChart3,
    title: "Financial Analytics",
    description:
      "Technical indicators, RSI, MACD, Bollinger Bands, fundamental ratios, and risk metrics.",
  },
  {
    icon: PieChart,
    title: "Portfolio Optimizer",
    description:
      "Modern Portfolio Theory, efficient frontier, max Sharpe ratio optimization.",
  },
  {
    icon: LineChart,
    title: "Sentiment Analysis",
    description:
      "FinBERT-powered NLP sentiment analysis on financial news. Real-time classification.",
  },
  {
    icon: Shield,
    title: "Risk Analytics",
    description:
      "VaR, CVaR, Sharpe, Sortino, max drawdown, beta, correlation matrix.",
  },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background">
      {/* Nav */}
      <nav className="border-b border-border/40 backdrop-blur-sm sticky top-0 z-50 bg-background/80">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center">
              <TrendingUp className="h-5 w-5 text-primary" />
            </div>
            <span className="font-semibold text-lg tracking-tight">FinSight AI</span>
          </div>
          <div className="flex items-center gap-3">
            <Link href="/login">
              <Button variant="ghost" size="sm">Sign In</Button>
            </Link>
            <Link href="/register">
              <Button size="sm">Get Started</Button>
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="max-w-7xl mx-auto px-6 pt-24 pb-20 text-center">
        <Badge variant="secondary" className="mb-6 px-4 py-1.5 text-xs font-medium">
          <Zap className="h-3 w-3 mr-1.5 text-primary" />
          B.Tech Final Year Project — AI + FinTech
        </Badge>

        <h1 className="text-5xl md:text-6xl font-bold tracking-tight mb-6 leading-tight">
          Financial Intelligence,{" "}
          <span className="text-primary">Powered by AI</span>
        </h1>

        <p className="text-xl text-muted-foreground max-w-3xl mx-auto mb-10 leading-relaxed">
          Research stocks, predict price movements, optimize portfolios, and get
          AI-powered insights — all in one platform built for serious analysis.
        </p>

        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <Link href="/register">
            <Button size="lg" className="gap-2 px-8">
              Start Researching <ArrowRight className="h-4 w-4" />
            </Button>
          </Link>
          <Link href="/login">
            <Button size="lg" variant="outline" className="gap-2 px-8">
              Sign In
            </Button>
          </Link>
        </div>
      </section>

      {/* Features Grid */}
      <section className="max-w-7xl mx-auto px-6 pb-24">
        <div className="text-center mb-14">
          <h2 className="text-3xl font-bold mb-4">Everything you need for financial research</h2>
          <p className="text-muted-foreground text-lg max-w-2xl mx-auto">
            From raw market data to AI-generated insights — built with real ML models and verified financial data.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feature) => (
            <div
              key={feature.title}
              className="p-6 rounded-xl border border-border/50 bg-card hover:border-primary/30 hover:bg-card/80 transition-all duration-200 group"
            >
              <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center mb-4 group-hover:bg-primary/15 transition-colors">
                <feature.icon className="h-5 w-5 text-primary" />
              </div>
              <h3 className="font-semibold text-base mb-2">{feature.title}</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                {feature.description}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* Disclaimer */}
      <footer className="border-t border-border/40 py-8 text-center">
        <p className="text-xs text-muted-foreground max-w-3xl mx-auto px-6">
          ⚠️ FinSight AI is an educational financial research tool. All predictions are model-generated
          estimates with uncertainty. This platform does not provide personalized investment advice.
          Always consult a qualified financial advisor before making investment decisions.
        </p>
        <p className="text-xs text-muted-foreground mt-3">
          © 2026 FinSight AI — B.Tech CS & AI Final Year Project
        </p>
      </footer>
    </div>
  );
}
