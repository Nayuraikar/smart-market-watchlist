import { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useWatchlists } from '../hooks/useWatchlists';
import { useWatchlist, useWatchlistStocks, useMarkWatchlistViewed } from '../hooks/useWatchlist';
import { Objective, ScoredEventExplanation } from '../types/market';
import { parseApiError } from '../api/client';
import LoadingSkeleton from '../components/feedback/LoadingSkeleton';
import ErrorState from '../components/feedback/ErrorState';
import ObjectiveSelector from '../components/watchlist/ObjectiveSelector';
import WatchlistSelector from '../components/watchlist/WatchlistSelector';
import AddStockForm from '../components/watchlist/AddStockForm';
import ChangeCard from '../components/market/ChangeCard';
import InstrumentRow from '../components/market/InstrumentRow';
import {
  TrendingUp, FileWarning, Briefcase,
  DollarSign, Shield, CalendarClock,
} from 'lucide-react';

const OBJECTIVE_META: Record<Objective, { label: string; description: string; icon: typeof TrendingUp }> = {
  GROWTH:    { label: 'Growth',    description: 'Revenue, earnings & momentum',           icon: TrendingUp },
  VALUE:     { label: 'Value',     description: 'Fundamentals, multiples & yield',        icon: DollarSign },
  STABILITY: { label: 'Stability', description: 'Low volatility & strong balance sheets', icon: Shield     },
};

function formatLastViewed(iso: string | null): string {
  if (!iso) return 'Never visited before';
  const d = new Date(iso);
  const diffMs = Date.now() - d.getTime();
  const diffMins = Math.floor(diffMs / 60_000);
  if (diffMins < 1)  return 'Just now';
  if (diffMins < 60) return `${diffMins} minute${diffMins === 1 ? '' : 's'} ago`;
  const diffHrs = Math.floor(diffMins / 60);
  if (diffHrs < 24)  return `${diffHrs} hour${diffHrs === 1 ? '' : 's'} ago`;
  const diffDays = Math.floor(diffHrs / 24);
  if (diffDays < 30) return `${diffDays} day${diffDays === 1 ? '' : 's'} ago`;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

export default function WatchlistDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  // View-only objective override — null means "use watchlist's configured objective"
  const [viewObjective, setViewObjective] = useState<Objective | null>(null);

  const { data: watchlists } = useWatchlists();

  const {
    data: watchlistData,
    isLoading,
    isError,
    error,
    isSuccess,
    refetch,
  } = useWatchlist(id!, viewObjective || undefined);

  const { data: stocksData, isLoading: isStocksLoading } = useWatchlistStocks(id!);

  // Fire POST /viewed exactly once per viewing session (guard in hook)
  useMarkWatchlistViewed(id, isSuccess);

  // Initialise view objective from the backend value once data arrives
  useEffect(() => {
    if (watchlistData && !viewObjective) {
      setViewObjective(watchlistData.objective);
    }
  }, [watchlistData, viewObjective]);

  // Reset view objective when navigating to a different watchlist
  useEffect(() => {
    setViewObjective(null);
  }, [id]);

  // Build lookup map: instrument_id → { ticker, name } for the change feed
  const instrumentLookup = useMemo(() => {
    const map = new Map<string, { ticker: string; name: string }>();
    watchlistData?.instruments.forEach(inst => {
      map.set(inst.instrument_id, { ticker: inst.ticker, name: inst.name });
    });
    return map;
  }, [watchlistData]);

  // Build lookup map: instrument_id → top_event for the roster
  const topEventLookup = useMemo(() => {
    const map = new Map<string, ScoredEventExplanation | null>();
    watchlistData?.instruments.forEach(inst => {
      map.set(inst.instrument_id, inst.top_event);
    });
    return map;
  }, [watchlistData]);

  const currentWatchlist = watchlists?.find(w => w.id === id);

  if (isLoading) return <LoadingSkeleton />;
  if (isError)   return <ErrorState title="Failed to load watchlist" message={parseApiError(error).message} onRetry={() => refetch()} />;
  if (!watchlistData) return <ErrorState title="Watchlist not found" message="The requested watchlist does not exist or you do not have access." />;

  const activeObjective     = viewObjective || watchlistData.objective;
  const configuredObjective = currentWatchlist?.objective || watchlistData.objective;
  const isViewingAlternate  = activeObjective !== configuredObjective;

  const ObjMeta        = OBJECTIVE_META[activeObjective]     || OBJECTIVE_META.GROWTH;
  const ConfiguredMeta = OBJECTIVE_META[configuredObjective] || OBJECTIVE_META.GROWTH;
  const ConfiguredIcon = ConfiguredMeta.icon;

  const changes     = watchlistData.since_last_visit;
  const events      = changes.events;       // Backend-ordered; must NOT be re-sorted or filtered
  const changeCount = changes.meaningful_change_count; // Authoritative count from backend

  const displayName      = currentWatchlist?.name || 'Watchlist';
  const hasInstruments   = !!stocksData && stocksData.length > 0;

  return (
    <div className="space-y-8 max-w-4xl">

      {/* ── 1. Header ────────────────────────────────────────────────── */}
      <header className="flex flex-col md:flex-row md:items-start justify-between gap-6 pb-6 border-b border-slate-200">
        <div className="space-y-3 min-w-0">
          <WatchlistSelector watchlists={watchlists || []} currentId={id} />
          <h1 className="text-3xl md:text-4xl font-bold tracking-tight text-slate-900 truncate">
            {displayName}
          </h1>
          <div className="flex flex-wrap items-center gap-2">
            <div className="inline-flex items-center gap-1.5 bg-slate-100 text-slate-600 text-xs font-semibold px-2.5 py-1 rounded-full border border-slate-200">
              <ConfiguredIcon className="w-3.5 h-3.5 text-slate-500" aria-hidden="true" />
              Configured: {ConfiguredMeta.label}
            </div>
            <div className="inline-flex items-center gap-1.5 text-xs text-slate-500">
              <CalendarClock className="w-3.5 h-3.5" aria-hidden="true" />
              Last visited: {formatLastViewed(watchlistData.last_viewed_at)}
            </div>
          </div>
        </div>

        <div className="flex flex-col items-start md:items-end gap-2 flex-shrink-0">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Viewing objective
          </p>
          <ObjectiveSelector
            currentObjective={activeObjective}
            onChange={(newObj) => setViewObjective(newObj)}
          />
          {isViewingAlternate && (
            <p className="text-xs text-amber-600 font-medium mt-0.5">
              Viewing as {ObjMeta.label} — configured remains {ConfiguredMeta.label}.
            </p>
          )}
        </div>
      </header>

      {/* ── 2. Change Summary Banner ─────────────────────────────────── */}
      <section aria-label="Meaningful changes since last visit">
        <div className="relative bg-slate-900 text-white rounded-xl p-8 shadow-md overflow-hidden flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="relative z-10">
            <h2 className="text-sm font-semibold uppercase tracking-widest text-blue-300 mb-2">
              Since your last visit
            </h2>
            <p className="text-5xl font-bold tracking-tight leading-none">{changeCount}</p>
            <p className="mt-1 text-slate-400 text-base">
              meaningful {changeCount === 1 ? 'change' : 'changes'}
              {isViewingAlternate && (
                <span className="ml-2 text-amber-400 text-sm font-medium">
                  · scored for {ObjMeta.label}
                </span>
              )}
            </p>
          </div>
          <ObjMeta.icon
            className="absolute -right-6 -bottom-6 w-32 h-32 text-white opacity-5 pointer-events-none hidden sm:block"
            aria-hidden="true"
          />
        </div>
      </section>

      {/* ── 3. Change Feed ───────────────────────────────────────────── */}
      <section aria-label="Change feed">
        <h2 className="text-xl font-bold text-slate-900 mb-4 tracking-tight">Change Feed</h2>
        {events.length === 0 ? (
          hasInstruments ? (
            <div className="bg-white border border-slate-200 border-dashed rounded-xl p-10 flex flex-col items-center text-center">
              <FileWarning className="w-9 h-9 text-slate-400 mb-3" aria-hidden="true" />
              <h3 className="text-base font-semibold text-slate-800 mb-1">No meaningful changes</h3>
              <p className="text-sm text-slate-500 max-w-md">
                No significant events were detected for your instruments under the{' '}
                <strong>{ObjMeta.label}</strong> objective since your last visit.
                Try switching the viewing objective or check back after market data updates.
              </p>
            </div>
          ) : (
            <div className="bg-white border border-slate-200 border-dashed rounded-xl p-10 flex flex-col items-center text-center">
              <Briefcase className="w-9 h-9 text-slate-400 mb-3" aria-hidden="true" />
              <h3 className="text-base font-semibold text-slate-800 mb-1">No instruments yet</h3>
              <p className="text-sm text-slate-500 max-w-md">
                Add instruments using the form below to start monitoring market changes.
              </p>
            </div>
          )
        ) : (
          <ol className="flex flex-col gap-4" aria-label="Change feed events">
            {events.map((event, idx) => {
              const instrument = instrumentLookup.get(event.instrument_id);
              return (
                <li key={`${event.instrument_id}-${event.event_type}-${idx}`}>
                  <ChangeCard
                    event={event}
                    ticker={instrument?.ticker || event.instrument_id}
                    instrumentName={instrument?.name || ''}
                  />
                </li>
              );
            })}
          </ol>
        )}
      </section>

      {/* ── 4. Instrument Roster ─────────────────────────────────────── */}
      <section aria-label="Instrument roster" className="mt-2 pb-8">
        <h2 className="text-xl font-bold text-slate-900 mb-4 tracking-tight">
          Instruments
          {hasInstruments && (
            <span className="ml-2 text-sm font-normal text-slate-500">
              ({stocksData!.length} tracked)
            </span>
          )}
        </h2>

        {/* Add stock form always visible */}
        <div className="mb-4">
          <AddStockForm watchlistId={id!} />
        </div>

        {isStocksLoading ? (
          <div className="animate-pulse h-32 bg-slate-200 rounded-xl w-full" aria-label="Loading instruments" />
        ) : !hasInstruments ? (
          <div className="bg-white border border-slate-200 border-dashed rounded-xl p-8 flex flex-col items-center text-center">
            <Briefcase className="w-8 h-8 text-slate-400 mb-3" aria-hidden="true" />
            <h3 className="text-sm font-semibold text-slate-800 mb-1">No instruments tracked yet</h3>
            <p className="text-sm text-slate-500 max-w-sm">
              Search for a stock above to start monitoring it.
            </p>
          </div>
        ) : (
          <div className="bg-white border border-slate-200 rounded-xl divide-y divide-slate-100" aria-label="Tracked instruments">
            {stocksData!.map((stock) => (
              <InstrumentRow
                key={stock.instrument_id}
                watchlistId={id!}
                stock={stock}
                topEvent={topEventLookup.get(stock.instrument_id)}
                objective={activeObjective}
              />
            ))}
          </div>
        )}
      </section>

      <div className="pb-4">
        <button
          type="button"
          onClick={() => navigate('/')}
          className="text-sm text-blue-600 hover:text-blue-800 font-medium underline-offset-2 hover:underline focus:outline-none focus:ring-2 focus:ring-blue-500 rounded"
        >
          ← Back to all watchlists
        </button>
      </div>
    </div>
  );
}
