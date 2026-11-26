"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTheme } from "next-themes";
import { CheckCircle2, CircleAlert, Cpu, Loader2, Moon, Sparkles, Sun } from "lucide-react";
import { toast } from "sonner";
import { aiApi, apiError, authApi, systemApi } from "@/lib/api";
import { providerLabel } from "@/lib/sse";
import { passwordRule } from "@/lib/validation";
import { cn, MODEL_LABELS } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { PageHeader } from "@/components/common/PageHeader";
import { useCurrentUser } from "@/hooks/useAuth";

export default function SettingsPage() {
  const qc = useQueryClient();
  const { data: user } = useCurrentUser();
  const { data: prefs } = useQuery({ queryKey: ["preferences"], queryFn: () => authApi.getPreferences().then((r) => r.data) });
  const { data: status } = useQuery({ queryKey: ["system-status"], queryFn: () => systemApi.status().then((r) => r.data) });
  const { theme, setTheme } = useTheme();

  const [profile, setProfile] = useState({ full_name: "", bio: "", default_currency: "USD" });
  const [market, setMarket] = useState("US");
  const [pw, setPw] = useState({ current: "", next: "", confirm: "" });

  useEffect(() => { if (user) setProfile({ full_name: user.full_name ?? "", bio: user.bio ?? "", default_currency: user.default_currency ?? "USD" }); }, [user]);
  useEffect(() => { if (prefs) setMarket(prefs.default_market ?? "US"); }, [prefs]);

  const saveProfile = useMutation({
    mutationFn: async () => {
      await authApi.updateMe(profile);
      await authApi.updatePreferences({ default_market: market, theme: theme === "light" ? "light" : "dark" });
    },
    onSuccess: () => { toast.success("Settings saved"); qc.invalidateQueries({ queryKey: ["me"] }); qc.invalidateQueries({ queryKey: ["preferences"] }); },
    onError: (e) => toast.error(apiError(e)),
  });
  const changePw = useMutation({
    mutationFn: () => authApi.changePassword(pw.current, pw.next),
    onSuccess: () => { toast.success("Password changed"); setPw({ current: "", next: "", confirm: "" }); },
    onError: (e) => toast.error(apiError(e)),
  });
  const submitPw = () => {
    const check = passwordRule.safeParse(pw.next);
    if (!check.success) return toast.error(check.error.issues[0].message);
    if (pw.next !== pw.confirm) return toast.error("New passwords do not match");
    changePw.mutate();
  };

  return (
    <div className="max-w-4xl space-y-6">
      <PageHeader title="Settings" description="Profile, preferences, security and system status" />

      <Card>
        <CardHeader title="Profile" description={user?.email} />
        <CardContent className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div className="space-y-1.5"><Label>Full name</Label><Input value={profile.full_name} onChange={(e) => setProfile({ ...profile, full_name: e.target.value })} /></div>
          <div className="space-y-1.5">
            <Label>Reporting currency</Label>
            <Select value={profile.default_currency} onChange={(e) => setProfile({ ...profile, default_currency: e.target.value })}>
              <option value="USD">USD ($)</option><option value="INR">INR (₹)</option><option value="EUR">EUR (€)</option><option value="GBP">GBP (£)</option>
            </Select>
          </div>
          <div className="space-y-1.5 md:col-span-2"><Label>Bio</Label><Input value={profile.bio} onChange={(e) => setProfile({ ...profile, bio: e.target.value })} placeholder="e.g. Final-year student interested in quantitative finance" /></div>
          <div className="space-y-1.5">
            <Label>Default market</Label>
            <Select value={market} onChange={(e) => setMarket(e.target.value)}><option value="US">US (NYSE / NASDAQ)</option><option value="IN">India (NSE / BSE)</option></Select>
          </div>
          <div className="space-y-1.5">
            <Label>Theme</Label>
            <div className="flex gap-2">
              {[{ v: "dark", icon: Moon }, { v: "light", icon: Sun }].map(({ v, icon: Icon }) => (
                <button key={v} onClick={() => setTheme(v)} className={cn("flex h-9 flex-1 items-center justify-center gap-2 rounded-md border text-sm capitalize", theme === v ? "border-primary bg-primary/10 text-primary" : "border-input")}>
                  <Icon className="h-4 w-4" /> {v}
                </button>
              ))}
            </div>
          </div>
          <div className="md:col-span-2"><Button onClick={() => saveProfile.mutate()} disabled={saveProfile.isPending}>{saveProfile.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />} Save changes</Button></div>
        </CardContent>
      </Card>

      <AISettings />

      <Card>
        <CardHeader title="Change password" />
        <CardContent className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <Input type="password" placeholder="Current password" value={pw.current} onChange={(e) => setPw({ ...pw, current: e.target.value })} />
          <Input type="password" placeholder="New password" value={pw.next} onChange={(e) => setPw({ ...pw, next: e.target.value })} />
          <Input type="password" placeholder="Confirm new password" value={pw.confirm} onChange={(e) => setPw({ ...pw, confirm: e.target.value })} />
          <div><Button variant="outline" onClick={submitPw} disabled={!pw.current || !pw.next || changePw.isPending}>Update password</Button></div>
        </CardContent>
      </Card>

      {status && (
        <Card>
          <CardHeader title="System status" description={`FinSight AI v${status.version} · ${status.environment}`} />
          <CardContent className="grid grid-cols-1 gap-2 text-sm md:grid-cols-2">
            <StatusRow ok label="Database" value={status.database === "sqlite" ? "SQLite (local file)" : "PostgreSQL"} />
            <StatusRow ok label="Cache" value={status.cache === "redis" ? "Redis" : "In-memory"} />
            <StatusRow ok={status.market_data.mode !== "demo" && status.market_data.live_available} label="Market data"
              value={status.market_data.mode === "demo" ? "Simulated (demo mode)" : status.market_data.live_available ? "Live — Yahoo Finance" : "Simulated (live source unreachable)"} />
            <StatusRow ok={status.sentiment.active_model === "ProsusAI/finbert"} label="Sentiment model"
              value={status.sentiment.active_model === "ProsusAI/finbert" ? "FinBERT (transformer)" : `Financial lexicon${status.sentiment.finbert_state === "loading" ? " — FinBERT loading…" : ""}`} />
            <StatusRow ok={status.llm.mode === "llm"} label="AI model (LLM)" value={status.llm.mode === "llm" ? providerLabel(status.llm.active) : "Offline analyst — start Ollama or add GOOGLE_API_KEY"} />
            <StatusRow ok={status.llm.ollama?.embedding_model_installed} label="Semantic search (embeddings)" value={status.llm.ollama?.embedding_model_installed ? `${status.llm.ollama.embedding_model} via Ollama` : "TF-IDF keyword search (pull nomic-embed-text for semantic search)"} />
            {Object.entries(status.ml_models).map(([m, s]: [string, any]) => (
              <StatusRow key={m} ok={s === "available"} label={MODEL_LABELS[m] ?? m} value={s === "available" ? "Available" : s} />
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function StatusRow({ ok, label, value }: { ok: boolean; label: string; value: string }) {
  return (
    <div className="flex items-start gap-2 rounded-lg border border-border/40 p-3">
      {ok ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-profit" /> : <CircleAlert className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />}
      <div className="min-w-0"><p className="text-xs text-muted-foreground">{label}</p><p className="break-words text-sm">{value}</p></div>
    </div>
  );
}

function AISettings() {
  const qc = useQueryClient();
  const { data: ai, isLoading } = useQuery({ queryKey: ["ai-models"], queryFn: () => aiApi.models().then((r) => r.data) });
  const select = useMutation({
    mutationFn: (data: { provider?: string; ollama_model?: string }) => aiApi.selectModel(data).then((r) => r.data),
    onSuccess: () => {
      toast.success("AI settings updated");
      ["ai-models", "ai-status", "system-status"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
    },
    onError: (e) => toast.error(apiError(e)),
  });
  if (isLoading || !ai) return null;
  const ollama = ai.ollama ?? {};
  return (
    <Card>
      <CardHeader title={<span className="flex items-center gap-1.5"><Sparkles className="h-4 w-4 text-primary" /> AI model</span>}
        description="Which large language model powers the assistant, insights and report summaries" />
      <CardContent className="space-y-4">
        <div className={cn("flex items-center gap-3 rounded-lg border p-3", ai.mode === "llm" ? "border-primary/30 bg-primary/5" : "border-amber-500/30 bg-amber-500/5")}>
          <Cpu className={cn("h-5 w-5", ai.mode === "llm" ? "text-primary" : "text-amber-500")} />
          <div className="text-sm">
            <p className="font-medium">{ai.mode === "llm" ? `Active: ${providerLabel(ai.active)}` : "No LLM available — using the offline analyst"}</p>
            <p className="text-xs text-muted-foreground">
              {ai.mode === "llm" ? (ai.is_local ? "Runs entirely on this computer with Ollama — free and works offline." : "Cloud model via API key.") : "Start Ollama (ollama serve) or add GOOGLE_API_KEY to .env."}
            </p>
          </div>
        </div>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div className="space-y-1.5">
            <Label>Provider preference</Label>
            <Select value={ai.preference} onChange={(e) => select.mutate({ provider: e.target.value })}>
              <option value="auto">Auto (cloud key if set, else local)</option>
              <option value="ollama">Local — Ollama</option>
              <option value="gemini" disabled={!ai.cloud_keys?.gemini}>Google Gemini{ai.cloud_keys?.gemini ? "" : " (no key)"}</option>
              <option value="groq" disabled={!ai.cloud_keys?.groq}>Groq{ai.cloud_keys?.groq ? "" : " (no key)"}</option>
              <option value="openai" disabled={!ai.cloud_keys?.openai}>OpenAI{ai.cloud_keys?.openai ? "" : " (no key)"}</option>
              <option value="offline">Offline analyst (no LLM)</option>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>Local model (Ollama)</Label>
            {ollama.reachable ? (
              <Select value={ollama.model} onChange={(e) => select.mutate({ ollama_model: e.target.value })} disabled={select.isPending}>
                {(ollama.installed_models ?? []).map((m: string) => <option key={m} value={m}>{m}</option>)}
                {!ollama.model_installed && <option value={ollama.model}>{ollama.model} (not installed)</option>}
              </Select>
            ) : (
              <p className="rounded-md border border-dashed border-border p-2 text-xs text-muted-foreground">Ollama is not running. Install it and run <code>ollama serve</code>, then <code>ollama pull qwen2.5:3b</code>.</p>
            )}
            <p className="text-[11px] text-muted-foreground">Smaller models (e.g. qwen2.5:1.5b) answer faster on 8 GB machines; larger ones write better analysis.</p>
          </div>
        </div>
        {!ai.cloud_keys?.gemini && (
          <p className="text-xs text-muted-foreground">
            Want a stronger model? Create a free key at <a href="https://aistudio.google.com/app/apikey" target="_blank" rel="noreferrer" className="text-primary underline">Google AI Studio</a>,
            add <code className="rounded bg-muted px-1">GOOGLE_API_KEY=…</code> to <code className="rounded bg-muted px-1">.env</code> and restart the backend — Gemini is then used automatically, with the local model as fallback.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
