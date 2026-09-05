import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useWatchlists, useCreateWatchlist } from '../hooks/useWatchlists';
import { Objective } from '../types/market';
import { parseApiError } from '../api/client';
import LoadingSkeleton from '../components/feedback/LoadingSkeleton';
import ErrorState from '../components/feedback/ErrorState';
import { PlusCircle, List, ArrowRight, TrendingUp, DollarSign, Shield } from 'lucide-react';

const OBJECTIVE_LABELS: Record<Objective, { label: string; description: string; icon: typeof TrendingUp }> = {
  GROWTH: { label: 'Growth', description: 'Revenue, earnings & capital efficiency', icon: TrendingUp },
  VALUE: { label: 'Value', description: 'Valuation & free cash flow yield', icon: DollarSign },
  STABILITY: { label: 'Stability', description: 'Financial resilience & balance sheet strength', icon: Shield },
};

export default function Dashboard() {
  const navigate = useNavigate();
  const { data: watchlists, isLoading, isError, error, refetch } = useWatchlists();

  const [name, setName] = useState('');
  const [objective, setObjective] = useState<Objective>('GROWTH');

  const createMutation = useCreateWatchlist();

  if (isLoading) return <LoadingSkeleton />;
  if (isError) return <ErrorState title="Failed to load watchlists" message={parseApiError(error).message} onRetry={() => refetch()} />;

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmedName = name.trim();
    if (!trimmedName || createMutation.isPending) return;
    createMutation.mutate({ name: trimmedName, objective }, {
      onSuccess: (newWatchlist) => {
        navigate(`/watchlists/${newWatchlist.id}`);
      },
    });
  };

  const createFormError = createMutation.error ? parseApiError(createMutation.error).message : null;
  const isSubmitDisabled = createMutation.isPending || !name.trim();

  return (
    <div className="space-y-10 max-w-5xl">

      {/* Page heading */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-slate-900 mb-1">Watchlists</h1>
        <p className="text-slate-500">Monitor what changed since your last visit.</p>
      </div>

      {/* Existing watchlists */}
      {watchlists && watchlists.length > 0 && (
        <section aria-label="Your watchlists">
          <h2 className="text-lg font-semibold text-slate-800 mb-4">Your Watchlists</h2>
          <ul className="flex flex-col gap-3">
            {watchlists.map((w) => {
              const ObjIcon = OBJECTIVE_LABELS[w.objective as Objective]?.icon;
              const objLabel = OBJECTIVE_LABELS[w.objective as Objective]?.label || w.objective;
              return (
                <li key={w.id}>
                  <Link
                    to={`/watchlists/${w.id}`}
                    className="
                      group flex items-center justify-between 
                      bg-white border border-slate-200 rounded-xl px-5 py-4 
                      hover:border-blue-300 hover:shadow-md 
                      focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-300
                      transition-all
                    "
                    aria-label={`Open watchlist: ${w.name}, objective: ${objLabel}`}
                  >
                    <div className="flex items-center gap-4 min-w-0">
                      {ObjIcon && (
                        <div className="flex-shrink-0 w-9 h-9 bg-blue-50 rounded-lg flex items-center justify-center group-hover:bg-blue-100 transition-colors">
                          <ObjIcon className="w-5 h-5 text-blue-600" aria-hidden="true" />
                        </div>
                      )}
                      <div className="min-w-0">
                        <p className="font-semibold text-slate-900 truncate">{w.name}</p>
                        <p className="text-xs text-slate-500 mt-0.5">{objLabel} objective</p>
                      </div>
                    </div>
                    <ArrowRight className="flex-shrink-0 w-5 h-5 text-slate-300 group-hover:text-blue-500 transition-colors ml-4" aria-hidden="true" />
                  </Link>
                </li>
              );
            })}
          </ul>
        </section>
      )}

      {/* Empty state — no watchlists */}
      {watchlists && watchlists.length === 0 && (
        <div className="bg-white border border-slate-200 border-dashed rounded-xl p-12 flex flex-col items-center text-center">
          <List className="w-10 h-10 text-slate-400 mb-4" aria-hidden="true" />
          <h2 className="text-lg font-semibold text-slate-900 mb-2">No watchlists yet</h2>
          <p className="text-slate-500 max-w-sm">
            Create your first watchlist below. Choose a name and an investment objective — the backend will use it to score and prioritize market changes for you.
          </p>
        </div>
      )}

      {/* Create watchlist form */}
      <section aria-label="Create a new watchlist" className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden max-w-xl">
        <div className="px-6 py-5 border-b border-slate-100 flex items-center gap-3">
          <PlusCircle className="w-5 h-5 text-blue-600 flex-shrink-0" aria-hidden="true" />
          <h2 className="text-lg font-bold text-slate-900">Create New Watchlist</h2>
        </div>

        <div className="p-6 space-y-5">
          {createFormError && (
            <div role="alert" className="p-3.5 bg-red-50 text-red-700 rounded-lg text-sm border border-red-100">
              {createFormError}
            </div>
          )}

          <form onSubmit={handleCreate} className="space-y-5">
            <div>
              <label htmlFor="wl-name" className="block text-sm font-semibold text-slate-700 mb-1.5">
                Watchlist Name <span className="text-red-500" aria-hidden="true">*</span>
              </label>
              <input
                id="wl-name"
                type="text"
                required
                autoComplete="off"
                placeholder="e.g. Tech Giants"
                value={name}
                onChange={(e) => setName(e.target.value)}
                disabled={createMutation.isPending}
                aria-required="true"
                aria-describedby="wl-name-hint"
                className="
                  w-full px-4 py-2.5 
                  border border-slate-300 rounded-lg shadow-sm 
                  text-slate-900 placeholder-slate-400 text-sm
                  focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 
                  disabled:opacity-50 disabled:bg-slate-50
                  transition-shadow
                "
              />
              <p id="wl-name-hint" className="mt-1 text-xs text-slate-400">Give your watchlist a descriptive name.</p>
            </div>

            <div>
              <label htmlFor="wl-objective" className="block text-sm font-semibold text-slate-700 mb-1.5">
                Primary Objective
              </label>
              <p className="text-xs text-slate-500 mb-2">
                This determines how the backend scores market events for your instruments.
                You can switch your viewing perspective at any time without changing this setting.
              </p>
              <select
                id="wl-objective"
                value={objective}
                onChange={(e) => setObjective(e.target.value as Objective)}
                disabled={createMutation.isPending}
                className="
                  w-full px-4 py-2.5 
                  border border-slate-300 rounded-lg shadow-sm 
                  text-slate-900 text-sm bg-white
                  focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 
                  disabled:opacity-50 disabled:bg-slate-50
                  transition-shadow
                "
              >
                <option value="GROWTH">Growth — revenue, earnings &amp; capital efficiency</option>
                <option value="VALUE">Value — valuation &amp; free cash flow yield</option>
                <option value="STABILITY">Stability — financial resilience &amp; balance sheet strength</option>
              </select>
            </div>

            <div className="pt-1">
              <button
                type="submit"
                disabled={isSubmitDisabled}
                aria-disabled={isSubmitDisabled}
                className="
                  inline-flex items-center gap-2 
                  px-6 py-2.5 rounded-lg text-sm font-semibold text-white 
                  bg-blue-600 hover:bg-blue-700 active:bg-blue-800
                  shadow-sm transition-colors 
                  focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500
                  disabled:opacity-50 disabled:cursor-not-allowed
                "
              >
                <PlusCircle className="w-4 h-4" aria-hidden="true" />
                {createMutation.isPending ? 'Creating…' : 'Create Watchlist'}
              </button>
            </div>
          </form>
        </div>
      </section>
    </div>
  );
}
