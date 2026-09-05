import { useState } from 'react';
import { useAddStock } from '../../hooks/useWatchlist';
import { parseApiError } from '../../api/client';
import { PlusCircle, Search } from 'lucide-react';

interface AddStockFormProps {
  watchlistId: string;
}

export default function AddStockForm({ watchlistId }: AddStockFormProps) {
  const [ticker, setTicker] = useState('');
  const addMutation = useAddStock();

  // Derive the error message from the backend response.
  // 409 ALREADY_IN_WATCHLIST → friendly message
  // 404 INSTRUMENT_NOT_FOUND → friendly message
  // anything else → use backend message
  const getErrorMessage = (): string | null => {
    if (!addMutation.error) return null;
    const err = parseApiError(addMutation.error);
    if (err.status === 409) return 'This instrument is already in your watchlist.';
    if (err.status === 404) return `No instrument found for "${ticker.trim().toUpperCase()}". Use the NSE ticker format, e.g. TCS.NS or RELIANCE.NS.`;
    return err.message;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = ticker.trim().toUpperCase();
    if (!trimmed || addMutation.isPending) return;
    addMutation.mutate(
      { watchlistId, data: { ticker: trimmed } },
      {
        onSuccess: () => {
          setTicker('');
          addMutation.reset();
        },
      }
    );
  };

  const errorMessage = getErrorMessage();

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-5">
      <h3 className="text-sm font-bold text-slate-900 mb-1 flex items-center gap-2">
        <Search className="w-4 h-4 text-slate-500" aria-hidden="true" />
        Add Instrument
      </h3>
      <p className="text-xs text-slate-500 mb-4">
        Enter the NSE ticker symbol with the <code className="bg-slate-100 px-1 rounded">.NS</code> suffix
        (e.g.{' '}
        <code className="bg-slate-100 px-1 rounded">TCS.NS</code>,{' '}
        <code className="bg-slate-100 px-1 rounded">RELIANCE.NS</code>,{' '}
        <code className="bg-slate-100 px-1 rounded">INFY.NS</code>).
        The instrument must already exist in the catalog.
      </p>

      <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-2" noValidate>
        <div className="flex-1">
          <label htmlFor={`add-ticker-${watchlistId}`} className="sr-only">
            Ticker symbol
          </label>
          <input
            id={`add-ticker-${watchlistId}`}
            type="text"
            value={ticker}
            onChange={(e) => {
              setTicker(e.target.value);
              if (addMutation.isError) addMutation.reset();
            }}
            placeholder="e.g. TCS.NS"
            disabled={addMutation.isPending}
            autoComplete="off"
            aria-label="Ticker symbol to add"
            aria-invalid={addMutation.isError}
            aria-describedby={addMutation.isError ? `add-ticker-error-${watchlistId}` : undefined}
            className={`
              w-full px-4 py-2.5 text-sm border rounded-lg
              font-mono tracking-wide placeholder-slate-400 text-slate-900 uppercase
              focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500
              disabled:opacity-50 disabled:bg-slate-50
              transition-colors
              ${addMutation.isError ? 'border-red-400 bg-red-50' : 'border-slate-300'}
            `}
          />
        </div>

        <button
          type="submit"
          disabled={addMutation.isPending || !ticker.trim()}
          aria-disabled={addMutation.isPending || !ticker.trim()}
          aria-label={addMutation.isPending ? 'Adding instrument…' : 'Add instrument to watchlist'}
          className="
            inline-flex items-center justify-center gap-2
            px-5 py-2.5 rounded-lg text-sm font-semibold text-white
            bg-blue-600 hover:bg-blue-700 active:bg-blue-800
            focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500
            disabled:opacity-50 disabled:cursor-not-allowed
            transition-colors flex-shrink-0
          "
        >
          <PlusCircle className="w-4 h-4" aria-hidden="true" />
          {addMutation.isPending ? 'Adding…' : 'Add'}
        </button>
      </form>

      {/* Error feedback — rendered below the form, associated by aria-describedby */}
      {errorMessage && (
        <p
          id={`add-ticker-error-${watchlistId}`}
          role="alert"
          className={`mt-2 text-sm font-medium ${
            addMutation.error && parseApiError(addMutation.error).status === 409
              ? 'text-amber-700'
              : 'text-red-700'
          }`}
        >
          {errorMessage}
        </p>
      )}
    </div>
  );
}
