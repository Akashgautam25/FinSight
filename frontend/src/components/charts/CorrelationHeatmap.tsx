/** Correlation matrix as a colour-scaled grid (red = negative, blue = positive). */
export function CorrelationHeatmap({ symbols, matrix }: { symbols: string[]; matrix: number[][] }) {
  const color = (v: number) => {
    const a = Math.min(Math.abs(v), 1);
    return v >= 0 ? `rgba(59,130,246,${0.15 + a * 0.75})` : `rgba(239,68,68,${0.15 + a * 0.75})`;
  };
  return (
    <div className="overflow-x-auto">
      <table className="mx-auto border-separate border-spacing-1 text-xs">
        <thead>
          <tr>
            <th />
            {symbols.map((s) => <th key={s} className="px-1 font-mono font-medium text-muted-foreground">{s}</th>)}
          </tr>
        </thead>
        <tbody>
          {symbols.map((row, i) => (
            <tr key={row}>
              <th className="pr-2 text-right font-mono font-medium text-muted-foreground">{row}</th>
              {matrix[i].map((v, j) => (
                <td key={j} className="h-10 w-14 rounded text-center font-mono text-white" style={{ background: color(v) }} title={`${row} / ${symbols[j]}: ${v.toFixed(2)}`}>
                  {v.toFixed(2)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
