import { AttentionTier } from '../../types/market';

const TIER_CONFIG: Record<AttentionTier, { label: string; classes: string }> = {
  HIGH:   { label: 'High Attention',   classes: 'bg-rose-100 text-rose-800 border-rose-200' },
  MEDIUM: { label: 'Medium Attention', classes: 'bg-amber-100 text-amber-800 border-amber-200' },
  LOW:    { label: 'Low Attention',    classes: 'bg-slate-100 text-slate-600 border-slate-200' },
};

export default function AttentionBadge({ tier }: { tier: AttentionTier }) {
  const config = TIER_CONFIG[tier] ?? TIER_CONFIG.LOW;
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-bold uppercase tracking-wide border ${config.classes}`}
      aria-label={config.label}
    >
      {config.label}
    </span>
  );
}
