export default function LoadingSkeleton() {
  return (
    <div className="animate-pulse flex flex-col gap-6 w-full max-w-4xl">
      <div className="h-10 bg-slate-200 rounded-md w-1/3"></div>
      <div className="h-24 bg-slate-200 rounded-lg w-full"></div>
      <div className="h-40 bg-slate-200 rounded-lg w-full"></div>
    </div>
  );
}
