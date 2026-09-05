import React from 'react';
import { LucideIcon } from 'lucide-react';

export default function EmptyState({ title, message, icon: Icon, action }: { title: string; message: string; icon?: LucideIcon; action?: React.ReactNode }) {
  return (
    <div className="bg-white border border-slate-200/80 rounded-2xl p-10 flex flex-col items-center text-center max-w-xl mx-auto shadow-sm">
      {Icon && (
        <div className="w-12 h-12 rounded-2xl bg-slate-100/80 border border-slate-200/60 flex items-center justify-center text-slate-400 mb-4">
          <Icon className="w-6 h-6 stroke-[1.75]" />
        </div>
      )}
      <h3 className="text-base font-bold text-slate-900 mb-1.5">{title}</h3>
      <p className="text-sm text-slate-500 max-w-md leading-relaxed mb-6">{message}</p>
      {action}
    </div>
  );
}
