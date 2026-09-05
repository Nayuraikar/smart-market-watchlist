import { DataStatus, DataQualityState } from '../../types/market';
import { CheckCircle2, Clock, AlertTriangle } from 'lucide-react';

const STATE_CONFIG: Record<DataQualityState, {
  label: string;
  icon: typeof CheckCircle2;
  classes: string;
}> = {
  FRESH:       { label: 'Fresh',       icon: CheckCircle2,  classes: 'text-emerald-700 bg-emerald-50 border-emerald-200' },
  STALE:       { label: 'Stale',       icon: Clock,         classes: 'text-amber-700 bg-amber-50 border-amber-200' },
  UNAVAILABLE: { label: 'Unavailable', icon: AlertTriangle, classes: 'text-slate-600 bg-slate-100 border-slate-200' },
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
    <div className="flex flex-col gap-1">
      <span
        className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-semibold border ${config.classes}`}
        aria-label={`Data quality: ${config.label}`}
      >
        <Icon className="w-3 h-3 flex-shrink-0" aria-hidden="true" />
        {config.label}
      </span>
      {showMessage && dataStatus.message && (
        <p className="text-xs text-slate-500 italic">{dataStatus.message}</p>
      )}
    </div>
  );
}
