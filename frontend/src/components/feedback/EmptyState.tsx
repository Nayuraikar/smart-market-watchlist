import React from 'react';
import { LucideIcon } from 'lucide-react';

export default function EmptyState({ title, message, icon: Icon, action }: { title: string, message: string, icon?: LucideIcon, action?: React.ReactNode }) {
  return (
    <div className="bg-white border border-slate-200 border-dashed rounded-lg p-10 flex flex-col items-center text-center max-w-3xl mx-auto">
      {Icon && <Icon className="w-10 h-10 text-slate-400 mb-4" />}
      <h3 className="text-lg font-semibold text-slate-900 mb-2">{title}</h3>
      <p className="text-slate-500 max-w-md mb-6">{message}</p>
      {action}
    </div>
  );
}
