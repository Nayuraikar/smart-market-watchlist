import { DataStatus, DataQualityState } from '../../types/market';
import { CheckCircle2, Clock, AlertTriangle } from 'lucide-react';

const STATE_CONFIG: Record<DataQualityState, {
  label: string;
  icon: typeof CheckCircle2;
  classes: string;
}> = {
  FRESH:       { label: 'Fresh',       icon: CheckCircle2,  classes: 'text-emerald-700 bg-emerald-50/80 border-emerald-200/80' },
  STALE:       { label: 'Stale',       icon: Clock,         classes: 'text-amber-700 bg-amber-50/80 border-amber-200/80' },
  UNAVAILABLE: { label: 'Unavailable', icon: AlertTriangle, classes: 'text-slate-600 bg-slate-100/80 border-slate-200/80' },
};

interface DataStatusBadgeProps {
  dataStatus: DataStatus;
  /** When true, also shows the detail message from the backend if present */
  showMessage?: boolean;
}
export default function DataStatusBadge({ dataStatus, showMessage = false }: DataStatusBadgeProps) {
  const config = STATE_CONFIG[dataStatus.state] ?? STATE_CONFIG.UNAVAILABLE;
  const Icon = config.icon;

  return (
    <div className="flex flex-col items-center justify-center text-center gap-1">
      <span
        className={`inline-flex items-center justify-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold border ${config.classes}`}
        aria-label={`Data quality: ${config.label}`}
      >
        <Icon className="w-3 h-3 flex-shrink-0" aria-hidden="true" />
        {config.label}
      </span>
      {showMessage && dataStatus.message && (
        <p className="text-xs text-slate-500 italic mt-0.5">{dataStatus.message}</p>
      )}
    </div>
  );
}
