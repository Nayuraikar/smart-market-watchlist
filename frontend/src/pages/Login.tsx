import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { authApi } from '../api/auth';
import { useAuth } from '../auth/context';
import { parseApiError } from '../api/client';
import { Activity, Lock, Mail, ArrowRight } from 'lucide-react';

export default function Login() {
  const navigate = useNavigate();
  const { setToken } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const loginMutation = useMutation({
    mutationFn: authApi.login,
    onSuccess: (data) => {
      setToken(data.access_token);
      navigate('/');
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    loginMutation.mutate({ email, password });
  };

  const error = loginMutation.error ? parseApiError(loginMutation.error) : null;

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#f7f8fa] p-4 font-sans">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-card-hover p-7 sm:p-9 w-full max-w-md space-y-7">
        <div className="text-center space-y-2">
          <div className="w-12 h-12 rounded-xl bg-emerald-500 flex items-center justify-center text-white mx-auto shadow-sm shadow-emerald-500/20">
            <Activity className="w-6 h-6" />
          </div>
          <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">Welcome back</h1>
          <p className="text-sm text-slate-500">Sign in to view your market watchlists</p>
        </div>

        {error && (
          <div className="p-3.5 bg-rose-50 text-rose-700 rounded-2xl text-xs font-semibold border border-rose-200">
            {error.message}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="email" className="block text-xs font-bold text-slate-700 mb-1.5">
              Email address
            </label>
            <div className="relative w-full">
              <Mail className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={loginMutation.isPending}
                placeholder="you@example.com"
                className="w-full pl-10 pr-4 py-3 bg-white border border-slate-300 rounded-lg text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-500 disabled:opacity-50 transition-all"
              />
            </div>
          </div>

          <div>
            <label htmlFor="password" className="block text-xs font-bold text-slate-700 mb-1.5">
              Password
            </label>
            <div className="relative w-full">
              <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                id="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={loginMutation.isPending}
                placeholder="••••••••"
                className="w-full pl-10 pr-4 py-3 bg-white border border-slate-300 rounded-lg text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-500 disabled:opacity-50 transition-all"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loginMutation.isPending}
            className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-lg text-sm font-bold text-white bg-emerald-500 hover:bg-emerald-600 active:bg-emerald-700 shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-emerald-500 disabled:opacity-40 disabled:cursor-not-allowed transition-all mt-2"
          >
            <span>{loginMutation.isPending ? 'Signing in...' : 'Sign In'}</span>
            {!loginMutation.isPending && <ArrowRight className="w-4 h-4" />}
          </button>
        </form>

        <div className="text-center text-xs text-slate-500 font-medium pt-2 border-t border-slate-100">
          <span>Don&apos;t have an account? </span>
          <Link to="/register" className="font-bold text-emerald-600 hover:text-emerald-700 transition-colors">
            Register here
          </Link>
        </div>
      </div>
    </div>
  );
}
