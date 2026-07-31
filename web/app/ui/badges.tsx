import type { Disposition, Sentiment } from "@/lib/api";

const DISPOSITION: Record<Disposition, { label: string; cls: string; dot: string }> = {
  escalated: {
    label: "Needs human",
    cls: "bg-red-50 text-red-700 ring-red-200",
    dot: "bg-red-500",
  },
  auto_closed: {
    label: "Auto-closed",
    cls: "bg-emerald-50 text-emerald-700 ring-emerald-200",
    dot: "bg-emerald-500",
  },
  retry: {
    label: "Retry later",
    cls: "bg-amber-50 text-amber-700 ring-amber-200",
    dot: "bg-amber-500",
  },
  unreachable: {
    label: "Unreachable",
    cls: "bg-slate-100 text-slate-600 ring-slate-200",
    dot: "bg-slate-400",
  },
  skipped: {
    label: "Skipped",
    cls: "bg-slate-50 text-slate-500 ring-slate-200",
    dot: "bg-slate-300",
  },
};

export function DispositionBadge({ value }: { value: Disposition }) {
  const d = DISPOSITION[value];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${d.cls}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${d.dot}`} />
      {d.label}
    </span>
  );
}

const SENTIMENT: Record<Sentiment, { cls: string; icon: string }> = {
  positive: { cls: "text-emerald-700", icon: "▲" },
  neutral: { cls: "text-slate-500", icon: "■" },
  negative: { cls: "text-red-700", icon: "▼" },
  unknown: { cls: "text-slate-400", icon: "·" },
};

export function SentimentBadge({ value }: { value: Sentiment }) {
  const s = SENTIMENT[value];
  return (
    <span className={`inline-flex items-center gap-1 text-xs font-medium ${s.cls}`}>
      <span aria-hidden="true" className="text-[10px]">
        {s.icon}
      </span>
      <span className="capitalize">{value}</span>
    </span>
  );
}
