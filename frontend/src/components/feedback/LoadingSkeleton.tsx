export default function LoadingSkeleton() {
  return (
    <div className="animate-pulse space-y-6 w-full max-w-4xl">
      <div className="flex items-center justify-between pb-4 border-b border-slate-200/60">
        <div className="space-y-2">
          <div className="h-8 bg-slate-200/80 rounded-xl w-48"></div>
          <div className="h-4 bg-slate-200/60 rounded-lg w-32"></div>
        </div>
        <div className="h-10 bg-slate-200/80 rounded-xl w-36"></div>
      </div>
      <div className="h-32 bg-slate-200/60 rounded-2xl w-full"></div>
      <div className="space-y-4">
        <div className="h-6 bg-slate-200/70 rounded-lg w-28"></div>
        <div className="h-28 bg-slate-200/50 rounded-2xl w-full"></div>
        <div className="h-28 bg-slate-200/50 rounded-2xl w-full"></div>
      </div>
    </div>
  );
}
