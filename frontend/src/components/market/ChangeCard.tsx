import { ScoredEventExplanation } from '../../types/market';
import AttentionBadge from './AttentionBadge';
import DataStatusBadge from './DataStatusBadge';
import { GitCompareArrows, Target } from 'lucide-react';

// Human-readable labels for event_type values.
// Unrecognised types fall through to a cleaned-up version of the raw string.
const EVENT_TYPE_LABELS: Record<string, string> = {
  PRICE_MOVE:              'Price Move',
  VOLUME_SURGE:            'Volume Surge',
  '52W_HIGH':              '52-Week High',
  '52W_LOW':               '52-Week Low',
  RELATIVE_OUTPERFORMANCE: 'Relative Outperformance',
  FUNDAMENTAL_CHANGE:      'Fundamental Change',
  EARNINGS:                'Earnings',
  CORPORATE_ACTION:        'Corporate Action',
};

function humanEventType(raw: string): string {
  return EVENT_TYPE_LABELS[raw] ?? raw.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

interface ChangeCardProps {
  event: ScoredEventExplanation;
  /** ticker + name resolved from InstrumentSinceLastVisit by the parent */
  ticker: string;
  instrumentName: string;
}

export default function ChangeCard({ event, ticker, instrumentName }: ChangeCardProps) {
  const isStale = event.data_status.state === 'STALE';

  return (
    <article
      className={`
        bg-white rounded-xl border shadow-sm overflow-hidden
        ${isStale ? 'border-amber-200' : 'border-slate-200'}
      `}
      aria-label={`${ticker}: ${humanEventType(event.event_type)}`}
    >
      {/* Card header: instrument identity + attention tier */}
      <div className={`flex items-start justify-between gap-3 px-5 pt-5 pb-3 ${isStale ? 'bg-amber-50/40' : ''}`}>
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xl font-bold text-slate-900 tracking-tight">{ticker}</span>
            <AttentionBadge tier={event.attention_tier} />
          </div>
          {instrumentName && (
            <p className="text-sm text-slate-500 mt-0.5 truncate">{instrumentName}</p>
          )}
          <p className="text-xs text-slate-400 mt-1 font-medium uppercase tracking-wider">
            {humanEventType(event.event_type)}
          </p>
        </div>

        {/* Data status badge — top-right */}
        <div className="flex-shrink-0 mt-0.5">
          <DataStatusBadge dataStatus={event.data_status} showMessage={false} />
        </div>
      </div>

      {/* Card body: what happened + magnitude */}
      <div className="px-5 pb-4 space-y-4 border-t border-slate-100">
        {/* What happened — primary */}
        <div className="pt-4">
          <p className="text-base font-semibold text-slate-900 leading-snug">
            {event.what_happened}
          </p>
          <p className="mt-1 text-sm font-medium text-slate-600">
            {event.magnitude}
          </p>
        </div>

        {/* Benchmark comparison — only when backend provides one */}
        {event.benchmark_comparison && (
          <div className="flex items-start gap-2 bg-slate-50 rounded-lg px-3 py-2.5 border border-slate-200">
            <GitCompareArrows className="w-4 h-4 text-slate-400 mt-0.5 flex-shrink-0" aria-hidden="true" />
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-0.5">
                Relative to benchmark
              </p>
              <p className="text-sm text-slate-700">{event.benchmark_comparison}</p>
            </div>
          </div>
        )}

        {/* Objective relevance — contextual */}
        <div className="flex items-start gap-2">
          <Target className="w-4 h-4 text-blue-400 mt-0.5 flex-shrink-0" aria-hidden="true" />
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-0.5">
              Objective relevance
            </p>
            <p className="text-sm text-slate-700">{event.objective_relevance}</p>
          </div>
        </div>

        {/* Stale data disclosure message — shown only when data is stale and message exists */}
        {isStale && event.data_status.message && (
          <div className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-md px-3 py-2">
            {event.data_status.message}
          </div>
        )}
      </div>
    </article>
  );
}
