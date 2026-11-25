// Settings & Profile Management Page
"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";

export default function SettingsPage() {
  const [currency, setCurrency] = useState("USD");
  const [market, setMarket] = useState("US");
  const [alphaVantageKey, setAlphaVantageKey] = useState("");
  const [geminiKey, setGeminiKey] = useState("");

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    toast.success("Preferences saved successfully!");
  };

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">System Settings & Preferences</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Manage currency display, default exchange markets, and user authentication preferences
        </p>
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        <div className="p-5 rounded-xl border border-border/40 bg-card space-y-4">
          <h2 className="text-sm font-semibold">Localization & Markets</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label>Base Reporting Currency</Label>
              <select
                value={currency}
                onChange={(e) => setCurrency(e.target.value)}
                className="w-full h-9 rounded-md border border-input bg-background/50 px-3 text-sm"
              >
                <option value="USD">USD ($)</option>
                <option value="INR">INR (₹)</option>
                <option value="EUR">EUR (€)</option>
                <option value="GBP">GBP (£)</option>
              </select>
            </div>
            <div className="space-y-1.5">
              <Label>Default Market Universe</Label>
              <select
                value={market}
                onChange={(e) => setMarket(e.target.value)}
                className="w-full h-9 rounded-md border border-input bg-background/50 px-3 text-sm"
              >
                <option value="US">US Markets (NYSE / NASDAQ)</option>
                <option value="IN">Indian Markets (NSE / BSE)</option>
              </select>
            </div>
          </div>
        </div>

        <div className="p-5 rounded-xl border border-border/40 bg-card space-y-4">
          <h2 className="text-sm font-semibold">User API Key Overrides (Optional)</h2>
          <p className="text-xs text-muted-foreground">
            Provide personal API keys if you wish to bypass standard shared rate limits.
          </p>
          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label>Alpha Vantage API Key</Label>
              <Input
                type="password"
                placeholder="Leave blank to use server environment default"
                value={alphaVantageKey}
                onChange={(e) => setAlphaVantageKey(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Google Gemini API Key</Label>
              <Input
                type="password"
                placeholder="Leave blank to use server environment default"
                value={geminiKey}
                onChange={(e) => setGeminiKey(e.target.value)}
              />
            </div>
          </div>
        </div>

        <Button type="submit">Save Preferences</Button>
      </form>
    </div>
  );
}
