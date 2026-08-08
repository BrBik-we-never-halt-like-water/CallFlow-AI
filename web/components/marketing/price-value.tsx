import { cn } from "@/lib/cn";
import { formatCurrency, formatNumber, formatRate, type Currency } from "@/lib/format";

/**
 * Renders a commercial number, or a visible `TODO` chip when it has not been set.
 *
 * Deliberately loud about the gap. Every price in `lib/pricing.ts` starts unset,
 * and an obviously missing number is far safer to ship than a plausible invented
 * one   nobody signs a contract off a placeholder, but they will quote one back
 * at you.
 */
export function PriceValue({
  amount,
  currency,
  suffix,
  className,
}: {
  amount: number | null;
  currency: Currency;
  suffix?: string;
  className?: string;
}) {
  if (amount === null) return <TodoChip className={className} />;

  return (
    <span className={cn("inline-flex items-baseline gap-1.5", className)}>
      <span className="font-display text-[2.5rem] leading-none tabular-nums text-text">
        {amount === 0 ? formatCurrency(0, currency) : formatCurrency(amount, currency)}
      </span>
      {suffix ? <span className="text-small text-text-mute">{suffix}</span> : null}
    </span>
  );
}

export function RateValue({
  amount,
  currency,
  suffix = "per call",
}: {
  amount: number | null;
  currency: Currency;
  suffix?: string;
}) {
  if (amount === null) return <TodoChip />;

  return (
    <span className="font-mono text-data tabular-nums text-text-dim">
      {formatRate(amount, currency)} {suffix}
    </span>
  );
}

export function VolumeValue({ calls }: { calls: number | null }) {
  if (calls === null) return <TodoChip />;
  return (
    <span className="font-mono text-data tabular-nums text-text">
      {formatNumber(calls)} calls included
    </span>
  );
}

export function TodoChip({ className }: { className?: string }) {
  return (
    <span
      title="This number has not been set yet. It lives in lib/pricing.ts."
      className={cn(
        "inline-flex items-center rounded-xs border border-dashed border-rule-strong bg-surface-sunken px-1.5 py-0.5",
        "font-mono text-label uppercase tracking-[0.14em] text-text-mute",
        className,
      )}
    >
      TODO
    </span>
  );
}
