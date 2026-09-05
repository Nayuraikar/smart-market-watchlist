import { useState } from 'react';
import { useAddStock } from '../../hooks/useWatchlist';
import { parseApiError } from '../../api/client';
import { Plus, Search } from 'lucide-react';

interface AddStockFormProps {
  watchlistId: string;
}

const STOCK_OPTIONS = [
  { ticker: 'RELIANCE.NS', name: 'Reliance Industries' },
  { ticker: 'TCS.NS', name: 'Tata Consultancy Services' },
  { ticker: 'HDFCBANK.NS', name: 'HDFC Bank' },
  { ticker: 'INFY.NS', name: 'Infosys' },
  { ticker: 'ICICIBANK.NS', name: 'ICICI Bank' },
  { ticker: 'ITC.NS', name: 'ITC' },
  { ticker: 'TMCV.NS', name: 'Tata Motors' },
  { ticker: 'BHARTIARTL.NS', name: 'Bharti Airtel' },
  { ticker: 'SBIN.NS', name: 'State Bank of India' },
  { ticker: 'SUNPHARMA.NS', name: 'Sun Pharma' },
  { ticker: 'TITAN.NS', name: 'Titan Company' },
  { ticker: 'WIPRO.NS', name: 'Wipro' },
];

export default function AddStockForm({ watchlistId }: AddStockFormProps) {
  const [ticker, setTicker] = useState('');
  const [isFocused, setIsFocused] = useState(false);
  const addMutation = useAddStock();

  const query = ticker.trim().toUpperCase();
  const suggestions = STOCK_OPTIONS.filter((stock) =>
    !query || `${stock.ticker} ${stock.name}`.toUpperCase().includes(query),
  ).slice(0, 6);

  // Derive the error message from the backend response.
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

  // Popular stock pills ONLY populate the existing search input state
  const chooseStock = (selectedTicker: string) => {
    setTicker(selectedTicker);
    if (addMutation.isError) addMutation.reset();
  };

  const errorMessage = getErrorMessage();

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-5 sm:p-6 shadow-card-subtle">
      <div className="flex items-start justify-between gap-4 mb-4">
        <div>
          <h3 className="text-sm font-bold text-slate-900">Add instruments</h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Search NSE stocks by company name or ticker.
          </p>
        </div>
        <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest bg-slate-100 px-2 py-1 rounded-md">
          NSE MARKET
        </span>
      </div>

      <form onSubmit={handleSubmit} className="space-y-3" noValidate>
        <div className="relative">
          <label htmlFor={`add-ticker-${watchlistId}`} className="sr-only">
            Search stocks
          </label>
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" aria-hidden="true" />
          <input
            id={`add-ticker-${watchlistId}`}
            type="text"
            value={ticker}
            onFocus={() => setIsFocused(true)}
            onBlur={() => window.setTimeout(() => setIsFocused(false), 120)}
            onChange={(e) => {
              setTicker(e.target.value);
              if (addMutation.isError) addMutation.reset();
            }}
            placeholder="Search by company or ticker e.g. TCS.NS, RELIANCE.NS"
            disabled={addMutation.isPending}
            autoComplete="off"
            aria-label="Search stocks to add"
            aria-invalid={addMutation.isError}
            aria-describedby={addMutation.isError ? `add-ticker-error-${watchlistId}` : undefined}
            className={`w-full pl-10 pr-24 py-3 text-sm border rounded-lg text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-500 disabled:opacity-50 disabled:bg-slate-50 transition-all ${addMutation.isError ? 'border-rose-300 bg-rose-50/50' : 'border-slate-300 bg-white'}`}
          />
          <button
            type="submit"
            disabled={addMutation.isPending || !ticker.trim()}
            className="absolute right-1.5 top-1.5 bottom-1.5 inline-flex items-center gap-1.5 px-3.5 rounded-md text-xs font-bold text-white bg-emerald-500 hover:bg-emerald-600 disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
            aria-label={addMutation.isPending ? 'Adding stock' : 'Add stock'}
          >
            <Plus className="w-3.5 h-3.5" aria-hidden="true" />
            {addMutation.isPending ? 'Adding...' : 'Add'}
          </button>
        </div>

        {(isFocused || query) && suggestions.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1" aria-label="Stock suggestions">
            {suggestions.map((stock) => (
              <button
                key={stock.ticker}
                type="button"
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => chooseStock(stock.ticker)}
                className="flex items-center gap-3 rounded-lg border border-slate-200 px-3.5 py-2 text-left hover:border-emerald-300 hover:bg-emerald-50/50 focus:outline-none focus:ring-2 focus:ring-emerald-500 transition-colors"
              >
                <span className="min-w-0">
                  <span className="block text-xs font-bold text-slate-900 font-mono truncate">{stock.ticker}</span>
                  <span className="block text-[11px] text-slate-500 truncate">{stock.name}</span>
                </span>
                <Plus className="w-3.5 h-3.5 text-emerald-600 shrink-0" aria-hidden="true" />
              </button>
            ))}
          </div>
        )}
      </form>

      <div className="mt-3 flex flex-wrap items-center justify-center gap-1.5" aria-label="Popular stocks">
        <span className="text-[11px] font-semibold text-slate-400 mr-1">Popular:</span>
        {STOCK_OPTIONS.slice(0, 6).map((stock) => (
          <button
            key={stock.ticker}
            type="button"
            onClick={() => chooseStock(stock.ticker)}
            className="rounded-full border border-slate-200 px-3 py-1 text-[11px] font-semibold text-slate-600 hover:border-emerald-400 hover:text-emerald-700 hover:bg-emerald-50/50 transition-colors"
          >
            {stock.ticker.replace('.NS', '')}
          </button>
        ))}
      </div>

      {errorMessage && (
        <p
          id={`add-ticker-error-${watchlistId}`}
          role="alert"
          className={`mt-3 text-xs font-semibold ${
            addMutation.error && parseApiError(addMutation.error).status === 409
              ? 'text-amber-700 bg-amber-50 border border-amber-200/80 rounded-xl px-3 py-2'
              : 'text-rose-700 bg-rose-50 border border-rose-200/80 rounded-xl px-3 py-2'
          }`}
        >
          {errorMessage}
        </p>
      )}
    </div>
  );
}
