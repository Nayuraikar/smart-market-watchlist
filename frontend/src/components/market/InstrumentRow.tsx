import { useRemoveStock } from '../../hooks/useWatchlist';
import { parseApiError } from '../../api/client';
import { Trash2 } from 'lucide-react';
import { StockOut } from '../../types/watchlist';
import { ScoredEventExplanation } from '../../types/market';
import AttentionBadge from './AttentionBadge';
import DataStatusBadge from './DataStatusBadge';
import { Link } from 'react-router-dom';

interface InstrumentRowProps {
  watchlistId: string;
  stock: StockOut;
  topEvent?: ScoredEventExplanation | null;
  objective?: string;
}

export default function InstrumentRow({ watchlistId, stock, topEvent, objective }: InstrumentRowProps) {
  const removeMutation = useRemoveStock();

  const handleRemove = () => {
    if (removeMutation.isPending) return;
    removeMutation.mutate({ watchlistId, instrumentId: stock.instrument_id });
  };

  const removeError = removeMutation.error ? parseApiError(removeMutation.error).message : null;

  return (
    <div className="flex items-start sm:items-center justify-between gap-4 px-5 py-4">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 flex-wrap">
            <Link
              to={`/watchlists/${watchlistId}/stocks/${stock.instrument_id}${objective ? `?objective=${objective}` : ''}`}
              className="text-sm font-bold text-slate-900 font-mono hover:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 rounded"
            >
              {stock.ticker}
            </Link>
          <span className="text-xs text-slate-400 font-medium">{stock.exchange}</span>
          {topEvent && <AttentionBadge tier={topEvent.attention_tier} />}
          {topEvent && <DataStatusBadge dataStatus={topEvent.data_status} showMessage={false} />}
        </div>
        <p className="text-xs text-slate-500 mt-0.5 truncate max-w-sm">{stock.name}</p>
        {topEvent && (
          <p className="text-xs text-slate-600 mt-1 truncate max-w-sm">{topEvent.what_happened}</p>
        )}
        {removeError && (
          <p role="alert" className="text-xs text-red-600 mt-1">
            Could not remove: {removeError}
          </p>
        )}
      </div>

      <button
        type="button"
        onClick={handleRemove}
        disabled={removeMutation.isPending}
        aria-label={`Remove ${stock.ticker} from watchlist`}
        aria-busy={removeMutation.isPending}
        className="
          flex-shrink-0 p-2 rounded-lg text-slate-400
          hover:text-red-600 hover:bg-red-50
          focus:outline-none focus:ring-2 focus:ring-red-400
          disabled:opacity-40 disabled:cursor-not-allowed
          transition-colors
        "
      >
        <Trash2 className="w-4 h-4" aria-hidden="true" />
      </button>
    </div>
  );
}
