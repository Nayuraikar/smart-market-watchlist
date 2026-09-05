import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { ArrowLeft, Activity, Database, Gauge } from 'lucide-react';
import { useWatchlists } from '../hooks/useWatchlists';
import { useInstrumentDetail } from '../hooks/useWatchlist';
import { Objective } from '../types/market';
import ObjectiveSelector from '../components/watchlist/ObjectiveSelector';
import ChangeCard from '../components/market/ChangeCard';
import DataStatusBadge from '../components/market/DataStatusBadge';
import LoadingSkeleton from '../components/feedback/LoadingSkeleton';
import ErrorState from '../components/feedback/ErrorState';
import EmptyState from '../components/feedback/EmptyState';
import { parseApiError } from '../api/client';

function formatValue(value: number | null): string {
  return value === null ? 'Unavailable' : value.toLocaleString(undefined, { maximumFractionDigits: 2 });
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
    <div className="space-y-8 max-w-4xl">
      <header className="flex flex-col md:flex-row md:items-start justify-between gap-6 pb-6 border-b border-slate-200">
        <div className="space-y-3">
          <Link to={`/watchlists/${watchlistId}`} className="inline-flex items-center gap-2 text-sm text-blue-600 hover:text-blue-800 font-medium">
            <ArrowLeft className="w-4 h-4" aria-hidden="true" /> Back to watchlist
          </Link>
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-slate-900">{instrument.ticker}</h1>
            <p className="text-sm text-slate-500 mt-1">{instrument.name} · {instrument.exchange}</p>
          </div>
        </div>
        <div className="flex flex-col items-start md:items-end gap-2">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Viewing objective</p>
          <ObjectiveSelector currentObjective={activeObjective} onChange={handleObjectiveChange} />
          {configuredObjective && activeObjective !== configuredObjective && (
            <p className="text-xs text-amber-600 font-medium">Configured remains {configuredObjective[0] + configuredObjective.slice(1).toLowerCase()}.</p>
          )}
        </div>
      </header>

      <section aria-label="Current market data">
        <h2 className="text-xl font-bold text-slate-900 mb-4">Current data</h2>
        {!current ? (
          <EmptyState title="No market data available" message="No current market state has been recorded for this instrument yet." icon={Database} />
        ) : (
          <div className="bg-white border border-slate-200 rounded-xl p-5 space-y-5">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2"><Activity className="w-5 h-5 text-blue-600" aria-hidden="true" /><span className="text-sm font-semibold text-slate-700">Latest market state</span></div>
              <DataStatusBadge dataStatus={current.data_status} showMessage />
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
              <div><p className="text-xs uppercase tracking-wide text-slate-400">Price</p><p className="text-lg font-bold text-slate-900">{formatValue(current.price)}</p></div>
              <div><p className="text-xs uppercase tracking-wide text-slate-400">Previous close</p><p className="text-lg font-bold text-slate-900">{formatValue(current.previous_close)}</p></div>
              <div><p className="text-xs uppercase tracking-wide text-slate-400">Volume</p><p className="text-lg font-bold text-slate-900">{formatValue(current.volume)}</p></div>
              <div><p className="text-xs uppercase tracking-wide text-slate-400">Market cap</p><p className="text-lg font-bold text-slate-900">{formatValue(current.market_cap)}</p></div>
              <div><p className="text-xs uppercase tracking-wide text-slate-400">P/E ratio</p><p className="text-lg font-bold text-slate-900">{formatValue(current.pe_ratio)}</p></div>
              <div><p className="text-xs uppercase tracking-wide text-slate-400">Dividend yield</p><p className="text-lg font-bold text-slate-900">{formatValue(current.dividend_yield)}</p></div>
            </div>
          </div>
        )}
      </section>

      <section aria-label="Detected changes">
        <div className="flex items-center gap-2 mb-4"><Gauge className="w-5 h-5 text-slate-500" aria-hidden="true" /><h2 className="text-xl font-bold text-slate-900">Detected changes</h2></div>
        {instrument.events.length === 0 ? (
          <EmptyState title="No detected changes" message="There are no scoreable events for this instrument since tracking began." />
        ) : (
          <div className="flex flex-col gap-4">
            {instrument.events.map((event, index) => <ChangeCard key={`${event.event_type}-${event.detected_at}-${index}`} event={event} ticker={instrument.ticker} instrumentName={instrument.name} />)}
          </div>
        )}
      </section>
    </div>
  );
}