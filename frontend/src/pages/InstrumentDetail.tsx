import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { ArrowLeft, Activity, Database, Gauge, BarChart3 } from 'lucide-react';
import { useWatchlists } from '../hooks/useWatchlists';
import { useInstrumentDetail } from '../hooks/useWatchlist';
import { Objective } from '../types/market';
import ObjectiveSelector from '../components/watchlist/ObjectiveSelector';
import ChangeCard from '../components/market/ChangeCard';
import DataStatusBadge from '../components/market/DataStatusBadge';
import LoadingSkeleton from '../components/feedback/LoadingSkeleton';
import ErrorState from '../components/feedback/ErrorState';
import EmptyState from '../components/feedback/EmptyState';
import PriceHistoryChart from '../components/market/PriceHistoryChart';
import { parseApiError } from '../api/client';

function formatValue(value: number | null): string {
  return value === null ? 'Not in saved data' : Number(value).toLocaleString('en-IN', { maximumFractionDigits: 2 });
}

function formatMarketCap(value: number | null): string {
  if (value === null) return 'Not in saved data';

  // Convert to trillions, billions, or millions
  const trillions = value / 1_000_000_000_000;
  const billions = value / 1_000_000_000;
  const millions = value / 1_000_000;

  if (trillions >= 1) {
    return `₹${trillions.toFixed(2)}T`;
  } else if (billions >= 1) {
    return `₹${billions.toFixed(2)}B`;
  } else if (millions >= 1) {
    return `₹${millions.toFixed(2)}M`;
  } else {
    return `₹${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
  }
}

export default function InstrumentDetail() {
  const { watchlistId = '', instrumentId = '' } = useParams<{ watchlistId: string; instrumentId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const { data: watchlists } = useWatchlists();
  const configuredObjective = watchlists?.find(w => w.id === watchlistId)?.objective;
  const [viewObjective, setViewObjective] = useState<Objective | null>(
    (searchParams.get('objective') as Objective | null) || null,
  );
  const activeObjective = viewObjective || configuredObjective || 'GROWTH';
  const detail = useInstrumentDetail(watchlistId, instrumentId, activeObjective);
  const navigate = useNavigate();

  useEffect(() => {
    if (detail.data && !viewObjective) setViewObjective(detail.data.objective);
  }, [detail.data, viewObjective]);

  const handleObjectiveChange = (objective: Objective) => {
    setViewObjective(objective);
    setSearchParams({ objective });
  };

  if (detail.isLoading) return <LoadingSkeleton />;
  if (detail.isError) return <ErrorState title="Failed to load instrument" message={parseApiError(detail.error).message} onRetry={() => detail.refetch()} />;
  if (!detail.data) return <ErrorState title="Instrument not found" message="This instrument is not available in the selected watchlist." onRetry={() => navigate(`/watchlists/${watchlistId}`)} />;

  const instrument = detail.data;
  const current = instrument.current_data;

  return (
    <div className="space-y-7 max-w-5xl mx-auto">
      <header className="flex flex-col md:flex-row md:items-end justify-between gap-6 pb-6 border-b border-slate-200">
        <div className="space-y-3">
          <Link
            to={`/watchlists/${watchlistId}`}
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-emerald-600 transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" aria-hidden="true" />
            <span>Back to watchlist</span>
          </Link>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-3xl md:text-4xl font-extrabold tracking-tight text-slate-900 font-mono">{instrument.ticker}</h1>
              <span className="text-xs font-bold text-slate-400 bg-slate-100 px-2 py-0.5 rounded-md uppercase">
                {instrument.exchange}
              </span>
            </div>
            <p className="text-sm font-medium text-slate-500 mt-1">{instrument.name}</p>
          </div>
        </div>
        <div className="flex flex-col items-start md:items-end gap-1.5">
          <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Viewing perspective</p>
          <ObjectiveSelector currentObjective={activeObjective} onChange={handleObjectiveChange} />
          {configuredObjective && activeObjective !== configuredObjective && (
            <p className="text-[11px] text-amber-600 font-semibold mt-1">Configured remains {configuredObjective[0] + configuredObjective.slice(1).toLowerCase()}.</p>
          )}
        </div>
      </header>

      <section aria-label="Current market data" className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-extrabold text-slate-900 tracking-tight flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-emerald-600" aria-hidden="true" />
            <span>Market Metrics</span>
          </h2>
          {current && <DataStatusBadge dataStatus={current.data_status} showMessage />}
        </div>

        {!current ? (
          <EmptyState title="No market data available" message="No current market state has been recorded for this instrument yet." icon={Database} />
        ) : (
          <div className="bg-white border border-slate-200 rounded-xl p-5 sm:p-6 shadow-card-subtle space-y-6">
            <div className="flex items-center justify-between gap-3 border-b border-slate-100 pb-4">
              <div className="flex items-center gap-2">
                <Activity className="w-4 h-4 text-emerald-600" aria-hidden="true" />
                <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Historical Replay Snapshot</span>
              </div>
            </div>

            <p className="text-xs text-slate-500">Prices and volume come from saved historical market data. Available fundamentals are separately collected snapshots, not values measured on each historical price date. Missing source fields are never invented.</p>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-6">
              <div className="bg-slate-50 p-4 rounded-lg border border-slate-100">
                <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Price</p>
                <p className="text-xl font-extrabold text-slate-900 font-mono mt-0.5 tabular-nums">₹{formatValue(current.price)}</p>
              </div>
              <div className="bg-slate-50 p-4 rounded-lg border border-slate-100">
                <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Previous close</p>
                <p className="text-xl font-bold text-slate-800 font-mono mt-0.5 tabular-nums">₹{formatValue(current.previous_close)}</p>
              </div>
              <div className="bg-slate-50 p-4 rounded-lg border border-slate-100">
                <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Volume</p>
                <p className="text-xl font-bold text-slate-800 font-mono mt-0.5 tabular-nums">{formatValue(current.volume)}</p>
              </div>
              <div className="bg-slate-50 p-4 rounded-lg border border-slate-100">
                <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Market cap</p>
                <p className="text-xl font-bold text-slate-800 font-mono mt-0.5 tabular-nums">{formatMarketCap(current.market_cap)}</p>
              </div>
              <div className="bg-slate-50 p-4 rounded-lg border border-slate-100">
                <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">P/E ratio</p>
                <p className="text-xl font-bold text-slate-800 font-mono mt-0.5 tabular-nums">{formatValue(current.pe_ratio)}</p>
              </div>
              <div className="bg-slate-50 p-4 rounded-lg border border-slate-100">
                <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Dividend yield</p>
                <p className="text-xl font-bold text-slate-800 font-mono mt-0.5 tabular-nums">{current.dividend_yield === null ? 'Not in saved data' : `${formatValue(current.dividend_yield)}%`}</p>
              </div>
            </div>
          </div>
        )}
      </section>

      <PriceHistoryChart points={instrument.price_history || []} ticker={instrument.ticker} />

      <section aria-label="Detected changes" className="space-y-4">
        <div className="flex items-center gap-2">
          <Gauge className="w-5 h-5 text-emerald-600" aria-hidden="true" />
          <h2 className="text-lg font-extrabold text-slate-900 tracking-tight">Detected Signals & Events</h2>
        </div>
        {instrument.events.length === 0 ? (
          <EmptyState title="No detected changes" message="There are no scoreable events for this instrument since tracking began." />
        ) : (
          <div className="flex flex-col gap-4">
            {instrument.events.map((event, index) => (
              <ChangeCard
                key={`${event.event_type}-${event.detected_at}-${index}`}
                event={event}
                ticker={instrument.ticker}
                instrumentName={instrument.name}
              />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
