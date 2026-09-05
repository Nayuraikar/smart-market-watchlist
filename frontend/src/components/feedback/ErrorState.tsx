import { AlertCircle } from 'lucide-react';

export default function ErrorState({ title = "Error", message, onRetry }: { title?: string, message: string, onRetry?: () => void }) {
  return (
    <div className="bg-red-50 border border-red-200 rounded-lg p-6 flex flex-col items-center text-center max-w-2xl mx-auto">
      <AlertCircle className="w-8 h-8 text-red-500 mb-3" />
      <h3 className="text-lg font-medium text-red-800 mb-1">{title}</h3>
      <p className="text-red-600 mb-4">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="px-4 py-2 bg-red-100 hover:bg-red-200 text-red-700 rounded-md text-sm font-medium transition-colors"
        >
          Try Again
        </button>
      )}
    </div>
  );
}
