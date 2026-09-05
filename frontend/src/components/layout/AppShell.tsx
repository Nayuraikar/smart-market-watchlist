import { Outlet } from 'react-router-dom';
import Navbar from './Navbar';

export default function AppShell({ children }: { children?: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
      <Navbar />
      <main className="flex-1 w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 md:py-10">
        {children || <Outlet />}
      </main>
    </div>
  );
}
