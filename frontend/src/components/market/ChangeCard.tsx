import { ScoredEventExplanation } from '../../types/market';
import AttentionBadge from './AttentionBadge';
import DataStatusBadge from './DataStatusBadge';
import { GitCompare, Target, TrendingUp, TrendingDown, Activity } from 'lucide-react';

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
  const isNegative = event.magnitude.includes('-') || event.what_happened.toLowerCase().includes('drop') || event.what_happened.toLowerCase().includes('down') || event.what_happened.toLowerCase().includes('fall');

  return (
    <article
      className={`
        bg-white rounded-xl border transition-all duration-200 shadow-card-subtle hover:shadow-card-hover overflow-hidden
        ${isStale ? 'border-amber-200/90' : 'border-slate-200/80'}
      `}
      aria-label={`${ticker}: ${humanEventType(event.event_type)}`}
    >
      {/* Header Bar */}
      <div className={`flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 px-5 sm:px-6 py-4 ${isStale ? 'bg-amber-50/40' : 'bg-slate-50/60'} border-b border-slate-100`}>
        <div className="min-w-0">
          <div className="flex items-center gap-2.5 flex-wrap">
            <span className="text-lg font-extrabold text-slate-900 tracking-tight font-mono">{ticker}</span>
            <AttentionBadge tier={event.attention_tier} />
          </div>
          {instrumentName && (
            <p className="text-xs text-slate-500 mt-0.5 font-medium truncate">{instrumentName}</p>
          )}
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          <DataStatusBadge dataStatus={event.data_status} showMessage={false} />
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider bg-slate-100 px-2 py-0.5 rounded-md">
            {humanEventType(event.event_type)}
          </span>
        </div>
      </div>

      {/* Body Content */}
      <div className="px-5 sm:px-6 py-5 space-y-4">
        {/* Main Event Statement & Magnitude Callout */}
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
          <div className="space-y-1 max-w-xl">
            <p className="text-base font-bold text-slate-900 leading-snug tracking-tight">
              {event.what_happened}
            </p>
          </div>
          {event.magnitude && (
            <div className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl font-bold text-xs shrink-0 tabular-nums border ${
              isNegative
                ? 'bg-rose-50 text-rose-700 border-rose-200/80'
                : 'bg-emerald-50 text-emerald-700 border-emerald-200/80'
            }`}>
              {isNegative ? <TrendingDown className="w-3.5 h-3.5" /> : <TrendingUp className="w-3.5 h-3.5" />}
              <span>{event.magnitude}</span>
            </div>
          )}
        </div>

        {/* Callout boxes for Benchmark & Objective */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
          {event.benchmark_comparison && (
            <div className="flex items-start gap-2.5 bg-slate-50 rounded-lg p-3.5 border border-slate-200">
              <GitCompare className="w-4 h-4 text-emerald-600 shrink-0" aria-hidden="true" />
              <div className="space-y-0.5">
                <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                  Relative to Benchmark
                </p>
                <p className="text-xs font-medium text-slate-700 leading-relaxed">{event.benchmark_comparison}</p>
              </div>
            </div>
          )}

          {event.objective_relevance && (
            <div className={`flex items-start gap-2.5 bg-slate-50 rounded-lg p-3.5 border border-slate-200 ${!event.benchmark_comparison ? 'md:col-span-2' : ''}`}>
              <Target className="w-4 h-4 text-emerald-600 shrink-0" aria-hidden="true" />
              <div className="space-y-0.5">
                <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                  Objective Relevance
                </p>
                <p className="text-xs font-medium text-slate-700 leading-relaxed">{event.objective_relevance}</p>
              </div>
            </div>
          )}
        </div>

        {/* Stale data disclosure */}
        {isStale && event.data_status.message && (
          <div className="flex items-center gap-2 text-xs font-medium text-amber-800 bg-amber-50 border border-amber-200/80 rounded-lg px-3.5 py-2.5 max-w-md">
            <Activity className="w-3.5 h-3.5 text-amber-600 shrink-0" />
            <span>{event.data_status.message}</span>
          </div>
        )}
      </div>
    </article>
  );
}
