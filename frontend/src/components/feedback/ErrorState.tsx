import { AlertCircle } from 'lucide-react';

export default function ErrorState({ title = "Error", message, onRetry }: { title?: string; message: string; onRetry?: () => void }) {
  return (
    <div className="bg-rose-50/70 border border-rose-200/80 rounded-2xl p-6 flex flex-col items-center text-center max-w-xl mx-auto shadow-sm">
      <div className="w-10 h-10 rounded-xl bg-rose-100 flex items-center justify-center text-rose-600 mb-3">
        <AlertCircle className="w-5 h-5 stroke-[2]" />
      </div>
      <h3 className="text-base font-bold text-rose-950 mb-1">{title}</h3>
      <p className="text-sm text-rose-700 mb-5 leading-relaxed max-w-md">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-xs font-bold transition-all shadow-sm focus:outline-none focus:ring-2 focus:ring-rose-500 focus:ring-offset-1"
        >
          Try Again
        </button>
      )}
    </div>
  );
}
