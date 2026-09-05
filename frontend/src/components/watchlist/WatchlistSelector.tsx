import { useNavigate } from 'react-router-dom';
import { ChevronDown } from 'lucide-react';
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
      <div className="relative">
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
            appearance-none bg-slate-100 border border-slate-300 text-slate-800 
            text-sm font-semibold rounded-lg 
            pl-3 pr-9 py-2
            cursor-pointer
            hover:bg-slate-200 hover:border-slate-400
            focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500
            transition-colors
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
          className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500"
          aria-hidden="true"
        />
      </div>
    </div>
  );
}
