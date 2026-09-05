import { Outlet } from 'react-router-dom';
import Navbar from './Navbar';

export default function AppShell({ children }: { children?: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-[#f7f8fa] flex flex-col font-sans text-slate-900 selection:bg-emerald-100 selection:text-emerald-900">
      <Navbar />
      <main className="flex-1 w-full max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-7 md:py-9">
        {children || <Outlet />}
      </main>
    </div>
  );
}
