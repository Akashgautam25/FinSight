// Disclaimer banner — always shown, never dismissable
export function DisclaimerBanner() {
  return (
    <div className="bg-amber-950/40 border-b border-amber-800/30 px-4 py-1.5 text-center">
      <p className="text-xs text-amber-400/80">
        ⚠️ FinSight AI is an educational research tool. All predictions are
        estimates with uncertainty. This is <strong>not</strong> financial
        advice. Data may be delayed 15–20 minutes.
      </p>
    </div>
  );
}
