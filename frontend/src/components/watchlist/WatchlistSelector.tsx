import { useNavigate } from 'react-router-dom';
import { ChevronDown, Bookmark } from 'lucide-react';
import { WatchlistOut } from '../../types/watchlist';

interface WatchlistSelectorProps {
  watchlists: WatchlistOut[];
  currentId?: string;
}

export default function WatchlistSelector({ watchlists, currentId }: WatchlistSelectorProps) {
  const navigate = useNavigate();

  if (!watchlists || watchlists.length === 0) return null;

  const current = watchlists.find(w => w.id === currentId);

  return (
    <div className="relative inline-block">
      <label htmlFor="watchlist-select" className="sr-only">
        Switch active watchlist
      </label>
      <div className="relative flex items-center">
        <Bookmark className="pointer-events-none absolute left-3 w-3.5 h-3.5 text-emerald-600 z-10" aria-hidden="true" />
        <select
          id="watchlist-select"
          value={currentId || ''}
          onChange={(e) => {
            const val = e.target.value;
            if (val && val !== currentId) {
              navigate(`/watchlists/${val}`);
            }
          }}
          className="
            appearance-none bg-white border border-slate-200 text-slate-900
            text-xs font-bold rounded-xl
            pl-8 pr-8 py-2
            cursor-pointer shadow-sm
            hover:border-emerald-300 hover:bg-slate-50/50
            focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500
            transition-all
          "
          aria-label={`Active watchlist: ${current?.name || 'Select a watchlist'}`}
        >
          {!currentId && (
            <option value="" disabled>Select a watchlist...</option>
          )}
          {watchlists.map(w => (
            <option key={w.id} value={w.id}>{w.name}</option>
          ))}
        </select>
        <ChevronDown
          className="pointer-events-none absolute right-2.5 w-3.5 h-3.5 text-slate-400"
          aria-hidden="true"
        />
      </div>
    </div>
  );
}
