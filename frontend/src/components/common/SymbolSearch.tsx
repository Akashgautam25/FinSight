"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Loader2, Search } from "lucide-react";
import { stocksApi } from "@/lib/api";
import { useDebounce } from "@/hooks/useDebounce";
import { cn } from "@/lib/utils";

/** Ticker autocomplete. Pressing Enter with no selection submits the typed text as a ticker. */
export function SymbolSearch({
  onSelect,
  placeholder = "Search stocks (e.g. AAPL, Tesla, RELIANCE.NS)",
  className,
  autoFocus,
  clearOnSelect = true,
}: {
  onSelect: (symbol: string) => void;
  placeholder?: string;
  className?: string;
  autoFocus?: boolean;
  clearOnSelect?: boolean;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const debounced = useDebounce(query.trim(), 300);
  const ref = useRef<HTMLDivElement>(null);

  const { data, isFetching } = useQuery({
    queryKey: ["symbol-search", debounced],
    queryFn: () => stocksApi.search(debounced).then((r) => r.data as any[]),
    enabled: debounced.length >= 1,
    staleTime: 5 * 60 * 1000,
  });
  const results = data ?? [];

  useEffect(() => {
    const close = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  useEffect(() => {
    setActive(0);
  }, [debounced]);

  const choose = (symbol: string) => {
    onSelect(symbol.toUpperCase());
    setOpen(false);
    if (clearOnSelect) setQuery("");
    else setQuery(symbol.toUpperCase());
  };

  return (
    <div ref={ref} className={cn("relative", className)}>
      <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
      <input
        value={query}
        autoFocus={autoFocus}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, results.length - 1)); }
          if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
          if (e.key === "Escape") setOpen(false);
          if (e.key === "Enter" && query.trim()) {
            e.preventDefault();
            choose(open && results[active] ? results[active].symbol : query.trim());
          }
        }}
        placeholder={placeholder}
        className="flex h-9 w-full rounded-md border border-input bg-background/50 pl-9 pr-8 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
      />
      {isFetching && <Loader2 className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-muted-foreground" />}
      {open && debounced && results.length > 0 && (
        <div className="absolute z-50 mt-1 w-full overflow-hidden rounded-lg border border-border bg-popover shadow-xl">
          {results.slice(0, 8).map((r: any, i: number) => (
            <button
              key={r.symbol}
              type="button"
              onMouseEnter={() => setActive(i)}
              onClick={() => choose(r.symbol)}
              className={cn("flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm", i === active ? "bg-accent" : "")}
            >
              <span className="min-w-0">
                <span className="font-mono font-semibold">{r.symbol}</span>
                <span className="ml-2 truncate text-muted-foreground">{r.name}</span>
              </span>
              <span className="shrink-0 text-xs text-muted-foreground">{r.exchange}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
