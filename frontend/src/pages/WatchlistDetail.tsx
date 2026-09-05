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
  DollarSign, Shield, CalendarClock, ArrowLeft, Activity,
} from 'lucide-react';

const OBJECTIVE_META: Record<Objective, { label: string; description: string; icon: typeof TrendingUp }> = {
  GROWTH:    { label: 'Growth',    description: 'The change feed prioritizes events relevant to a growth-oriented investor.', icon: TrendingUp },
  VALUE:     { label: 'Value',     description: 'The same underlying events are evaluated through the value lens.',           icon: DollarSign },
  STABILITY: { label: 'Stability', description: 'The same underlying events are evaluated through the stability lens.',       icon: Shield     },
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
    isFetchedAfterMount,
    refetch,
  } = useWatchlist(id!, viewObjective || undefined);

  const { data: stocksData, isLoading: isStocksLoading } = useWatchlistStocks(id!);

  // Wait for the objective-specific query so its response is not replaced by
  // a second GET after last_viewed_at advances.
  useMarkWatchlistViewed(id, isSuccess && isFetchedAfterMount && viewObjective !== null);

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
    <div className="space-y-7 max-w-5xl mx-auto">

      {/* ── 1. Header ────────────────────────────────────────────────── */}
      <header className="bg-white border border-slate-200 rounded-xl p-5 sm:p-7 shadow-card-subtle space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-5 pb-5 border-b border-slate-100">
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <button
                onClick={() => navigate('/')}
                className="inline-flex items-center justify-center gap-1 text-xs font-bold text-slate-500 hover:text-emerald-600 transition-colors"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>Watchlists</span>
              </button>
              <span className="text-slate-300">/</span>
              <WatchlistSelector watchlists={watchlists || []} currentId={id} />
            </div>

            <h1 className="text-3xl md:text-4xl font-extrabold tracking-tight text-slate-900 capitalize">
              {displayName}
            </h1>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div className="inline-flex items-center justify-center gap-1.5 bg-slate-100/90 text-slate-700 text-xs font-bold px-3 py-1.5 rounded-full border border-slate-200/80">
              <ConfiguredIcon className="w-3.5 h-3.5 text-emerald-600" aria-hidden="true" />
              <span>Default: {ConfiguredMeta.label}</span>
            </div>
            <div className="inline-flex items-center justify-center gap-1.5 text-xs font-medium text-slate-400">
              <CalendarClock className="w-3.5 h-3.5 text-slate-400" aria-hidden="true" />
              <span>Last visited: {formatLastViewed(watchlistData.last_viewed_at)}</span>
            </div>
          </div>
        </div>

        {/* Viewing Lens Section */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pt-1">
          <div>
          <p className="text-[11px] font-extrabold uppercase tracking-widest text-slate-400 mb-2">
            Viewing Perspective
          </p>
          <ObjectiveSelector
            currentObjective={activeObjective}
            onChange={(newObj) => setViewObjective(newObj)}
          />
          </div>
          <div className="space-y-1 sm:text-right">
            <p className="text-xs font-semibold text-slate-700">
              <strong className="text-emerald-600 font-extrabold">Viewing as {ObjMeta.label}</strong> — {ObjMeta.description}
            </p>
            {isViewingAlternate && (
              <p className="text-[11px] font-semibold text-amber-700 bg-amber-50 inline-block px-3 py-0.5 rounded-full border border-amber-200/80 mt-2">
                Watchlist default objective is configured as <strong>{ConfiguredMeta.label}</strong>
              </p>
            )}
          </div>
        </div>
      </header>

      {/* ── 2. Change Summary Banner (Centered, High-Contrast Groww Style) ───── */}
      <section aria-label="Meaningful changes since last visit">
        <div className="bg-emerald-500 rounded-xl p-6 sm:p-7 shadow-sm flex flex-col sm:flex-row sm:items-center sm:justify-between gap-5 text-white">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-emerald-100">Since your last visit</p>
            <h2 className="text-xl font-extrabold tracking-tight mt-1">
              {changeCount === 0 ? 'No meaningful changes detected' : `${changeCount} meaningful ${changeCount === 1 ? 'change' : 'changes'} detected`}
            </h2>
            <p className="text-sm text-emerald-50 mt-1.5">
              Here&apos;s what changed while you were away.
              {isViewingAlternate && ` Evaluated through the ${ObjMeta.label} lens.`}
            </p>
          </div>
          <div className="bg-white/15 border border-white/20 rounded-lg px-5 py-3 text-center shrink-0">
            <span className="text-4xl font-extrabold tracking-tight font-mono block leading-none">
              {changeCount}
            </span>
            <span className="text-[10px] uppercase tracking-widest font-bold text-emerald-100">Events</span>
          </div>
        </div>
      </section>

      {/* ── 3. Change Feed ───────────────────────────────────────────── */}
      <section aria-label="Change feed" className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-lg font-extrabold text-slate-900 tracking-tight flex items-center gap-2">
            <Activity className="w-5 h-5 text-emerald-600" />
            <span>Change Feed</span>
          </h2>
          {events.length > 0 && (
            <span className="text-xs font-bold text-slate-500 bg-slate-100 px-3 py-1 rounded-full border border-slate-200/60 inline-flex items-center justify-center">
              {events.length} event{events.length === 1 ? '' : 's'}
            </span>
          )}
        </div>

        {events.length === 0 ? (
          hasInstruments ? (
            <div className="bg-white border border-slate-200/80 rounded-3xl p-10 flex flex-col items-center text-center shadow-card-subtle">
              <div className="w-12 h-12 rounded-xl bg-slate-100 flex items-center justify-center text-slate-400 mb-3">
                <FileWarning className="w-6 h-6 stroke-[1.75]" aria-hidden="true" />
              </div>
              <h3 className="text-base font-bold text-slate-900 mb-1">No meaningful changes</h3>
              <p className="text-xs text-slate-500 max-w-md leading-relaxed">
                You&apos;re all caught up! No significant market events were detected for your instruments under the{' '}
                <strong className="text-slate-700">{ObjMeta.label}</strong> objective since your last visit.
              </p>
            </div>
          ) : (
            <div className="bg-white border border-slate-200/80 rounded-3xl p-10 flex flex-col items-center text-center shadow-card-subtle">
              <div className="w-12 h-12 rounded-xl bg-emerald-50 flex items-center justify-center text-emerald-600 mb-3">
                <Briefcase className="w-6 h-6 stroke-[1.75]" aria-hidden="true" />
              </div>
              <h3 className="text-base font-bold text-slate-900 mb-1">No instruments in watchlist</h3>
              <p className="text-xs text-slate-500 max-w-md leading-relaxed">
                Add NSE stocks using the search form below to start monitoring simulated historical changes.
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
      <section aria-label="Instrument roster" className="mt-6 space-y-4">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-lg font-extrabold text-slate-900 tracking-tight flex items-center">
            <span>Tracked Instruments</span>
            {hasInstruments && (
              <span className="ml-2 text-xs font-bold text-slate-400">
                ({stocksData!.length})
              </span>
            )}
          </h2>
        </div>

        {/* Add stock form */}
        <div>
          <AddStockForm watchlistId={id!} />
        </div>

        {isStocksLoading ? (
          <div className="animate-pulse h-32 bg-slate-200/60 rounded-3xl w-full" aria-label="Loading instruments" />
        ) : !hasInstruments ? (
          <div className="bg-white border border-slate-200/80 rounded-3xl p-8 flex flex-col items-center text-center shadow-card-subtle">
            <Briefcase className="w-8 h-8 text-slate-300 mb-2" aria-hidden="true" />
            <h3 className="text-sm font-bold text-slate-800 mb-1">No instruments tracked yet</h3>
            <p className="text-xs text-slate-500 max-w-sm">
              Search for a stock above to start tracking performance.
            </p>
          </div>
        ) : (
          <div className="bg-white border border-slate-200 rounded-xl divide-y divide-slate-100 shadow-card-subtle overflow-hidden" aria-label="Tracked instruments">
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

      <div className="pt-2 pb-4 text-center">
        <button
          type="button"
          onClick={() => navigate('/')}
          className="inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-emerald-600 font-bold transition-colors focus:outline-none focus:ring-2 focus:ring-emerald-500 rounded-lg px-3 py-1.5 bg-white border border-slate-200/80 shadow-sm"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to all watchlists</span>
        </button>
      </div>
    </div>
  );
}
