// AI Research Reports Page
"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { reportsApi, aiApi } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { FileText, Download, Plus, Loader2, Calendar } from "lucide-react";
import { toast } from "sonner";

export default function ReportsPage() {
  const queryClient = useQueryClient();
  const [symbol, setSymbol] = useState("");
  const [selectedReport, setSelectedReport] = useState<any>(null);

  const { data: reports, isLoading } = useQuery({
    queryKey: ["research-reports"],
    queryFn: () => reportsApi.list().then((r) => r.data),
  });

  const generateMutation = useMutation({
    mutationFn: () => aiApi.generateReport({ symbol: symbol.toUpperCase(), include_predictions: true, include_sentiment: true }),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["research-reports"] });
      toast.success(`Research report for ${symbol.toUpperCase()} generated!`);
      setSelectedReport(res.data);
      setSymbol("");
    },
    onError: () => toast.error("Report generation failed."),
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">AI Financial Research Reports</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Institutional-grade equity research reports synthesized with fundamentals, technicals, sentiment, and PDF export
          </p>
        </div>
      </div>

      {/* Generator Bar */}
      <div className="p-4 rounded-xl border border-border/40 bg-card flex gap-3 max-w-md">
        <Input
          placeholder="Stock Ticker (e.g. AAPL, NVDA)"
          value={symbol}
          onChange={(e) => setSymbol(e.target.value.toUpperCase())}
        />
        <Button
          onClick={() => generateMutation.mutate()}
          disabled={!symbol || generateMutation.isPending}
        >
          {generateMutation.isPending ? (
            <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Synthesizing...</>
          ) : (
            <><Plus className="h-4 w-4 mr-1.5" /> Generate</>
          )}
        </Button>
      </div>

      {/* Reports Archive */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="rounded-xl border border-border/40 bg-card overflow-hidden">
          <div className="px-4 py-3 border-b border-border/30 font-semibold text-sm">
            Saved Reports
          </div>
          <div className="divide-y divide-border/20 max-h-[500px] overflow-y-auto">
            {isLoading ? (
              <div className="p-4 space-y-2 animate-pulse">
                {[1, 2, 3].map((i) => <div key={i} className="h-12 bg-muted rounded" />)}
              </div>
            ) : reports && reports.length > 0 ? (
              reports.map((rep: any) => (
                <div
                  key={rep.id}
                  onClick={() => setSelectedReport(rep)}
                  className={`p-3.5 hover:bg-muted/20 cursor-pointer transition-colors ${selectedReport?.id === rep.id ? "bg-primary/10" : ""}`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-sm font-mono">{rep.symbol}</span>
                    <span className="text-xs text-muted-foreground">{new Date(rep.generated_at).toLocaleDateString()}</span>
                  </div>
                  <p className="text-xs text-muted-foreground truncate mt-0.5">{rep.title}</p>
                </div>
              ))
            ) : (
              <div className="p-6 text-center text-xs text-muted-foreground">
                No reports generated yet. Enter a ticker above to create your first report.
              </div>
            )}
          </div>
        </div>

        {/* Report Preview */}
        <div className="md:col-span-2 rounded-xl border border-border/40 bg-card p-6 min-h-[400px]">
          {selectedReport ? (
            <div className="space-y-4">
              <div className="flex items-start justify-between border-b border-border/30 pb-4">
                <div>
                  <h2 className="text-lg font-bold">{selectedReport.title || `Report: ${selectedReport.symbol}`}</h2>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Synthesized: {new Date(selectedReport.generated_at).toLocaleString()}
                  </p>
                </div>
                {selectedReport.id && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      window.open(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/reports/${selectedReport.id}/export`, "_blank");
                    }}
                  >
                    <Download className="h-3.5 w-3.5 mr-1.5" /> Export PDF
                  </Button>
                )}
              </div>

              <div className="space-y-4 text-sm">
                <div>
                  <h3 className="text-xs font-bold text-muted-foreground uppercase tracking-wider mb-1">Executive Summary</h3>
                  <p className="leading-relaxed bg-muted/20 p-3 rounded-lg border border-border/20">
                    {selectedReport.report_data?.executive_summary || "Summary data loading..."}
                  </p>
                </div>

                <div>
                  <h3 className="text-xs font-bold text-muted-foreground uppercase tracking-wider mb-1">Risk Profile</h3>
                  <p className="leading-relaxed bg-muted/20 p-3 rounded-lg border border-border/20">
                    {selectedReport.report_data?.risk_assessment || "Risk assessment loading..."}
                  </p>
                </div>

                <div className="pt-2 text-xs text-muted-foreground border-t border-border/20">
                  <p><strong>Disclaimer:</strong> {selectedReport.report_data?.disclaimer || "Educational and research purposes only."}</p>
                </div>
              </div>
            </div>
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-center text-muted-foreground py-16">
              <FileText className="h-10 w-10 mb-2 opacity-50" />
              <p className="text-sm">Select a saved report from the list or generate a new one.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
