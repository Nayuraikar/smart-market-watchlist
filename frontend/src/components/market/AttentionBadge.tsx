import { AttentionTier } from '../../types/market';

const TIER_CONFIG: Record<AttentionTier, { label: string; dot: string; classes: string }> = {
  HIGH:   { label: 'High Attention',   dot: 'bg-rose-500 animate-pulse', classes: 'bg-rose-50 text-rose-700 border-rose-200/80' },
  MEDIUM: { label: 'Medium Attention', dot: 'bg-amber-500',               classes: 'bg-amber-50 text-amber-700 border-amber-200/80' },
  LOW:    { label: 'Low Attention',    dot: 'bg-slate-400',               classes: 'bg-slate-100/80 text-slate-600 border-slate-200/80' },
};

export default function AttentionBadge({ tier }: { tier: AttentionTier }) {
  const config = TIER_CONFIG[tier] ?? TIER_CONFIG.LOW;
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold border ${config.classes}`}
      aria-label={config.label}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${config.dot}`} aria-hidden="true" />
      {config.label}
    </span>
  );
}
