import { Link } from 'react-router-dom';
import { useAuth } from '../../auth/context';
import { LogOut, LineChart } from 'lucide-react';

export default function Navbar() {
  const { user, logout } = useAuth();
  return (
    <nav className="bg-white border-b border-slate-200 sticky top-0 z-50 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex">
            <Link to="/" className="flex items-center gap-2 text-slate-900 font-bold text-lg hover:text-blue-600 transition-colors">
              <LineChart className="w-6 h-6 text-blue-600" />
              Smart Market Watchlist
            </Link>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-sm text-slate-600 hidden sm:inline-block font-medium">{user?.email}</span>
            <button
              onClick={logout}
              className="text-slate-500 hover:text-red-600 flex items-center gap-1.5 text-sm font-medium transition-colors p-2 rounded-md hover:bg-red-50"
              aria-label="Log out"
            >
              <LogOut className="w-4 h-4" />
              <span className="hidden sm:inline-block">Log out</span>
            </button>
          </div>
        </div>
      </div>
    </nav>
  );
}
