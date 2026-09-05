import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { authApi } from '../api/auth';
import { parseApiError } from '../api/client';
import { Activity, Lock, Mail, UserPlus } from 'lucide-react';

export default function Register() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  const registerMutation = useMutation({
    mutationFn: authApi.register,
    onSuccess: () => {
      setSuccessMessage('Registration successful! Redirecting to login...');
      setTimeout(() => {
        navigate('/login');
      }, 1500);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    registerMutation.mutate({ email, password });
  };

  const error = registerMutation.error ? parseApiError(registerMutation.error) : null;

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#f7f8fa] p-4 font-sans">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-card-hover p-7 sm:p-9 w-full max-w-md space-y-7">
        <div className="text-center space-y-2">
          <div className="w-12 h-12 rounded-xl bg-emerald-500 flex items-center justify-center text-white mx-auto shadow-sm shadow-emerald-500/20">
            <Activity className="w-6 h-6" />
          </div>
          <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">Create your account</h1>
          <p className="text-sm text-slate-500">Start monitoring the stocks that matter to you</p>
        </div>

        {error && (
          <div className="p-3.5 bg-rose-50 text-rose-700 rounded-2xl text-xs font-semibold border border-rose-200">
            {error.message}
          </div>
        )}

        {successMessage && (
          <div className="p-3.5 bg-emerald-50 text-emerald-700 rounded-2xl text-xs font-semibold border border-emerald-200">
            {successMessage}
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
                disabled={registerMutation.isPending || !!successMessage}
                placeholder="you@example.com"
                className="w-full pl-10 pr-4 py-3 bg-white border border-slate-300 rounded-lg text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-500 focus:bg-white disabled:opacity-50 transition-all"
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
                minLength={8}
                maxLength={72}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={registerMutation.isPending || !!successMessage}
                placeholder="••••••••"
                className="w-full pl-10 pr-4 py-3 bg-white border border-slate-300 rounded-lg text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-500 focus:bg-white disabled:opacity-50 transition-all"
              />
            </div>
            <p className="mt-1 text-[11px] text-slate-400">Must be between 8 and 72 characters.</p>
          </div>

          <button
            type="submit"
            disabled={registerMutation.isPending || !!successMessage || password.length < 8}
            className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-lg text-sm font-bold text-white bg-emerald-500 hover:bg-emerald-600 active:bg-emerald-700 shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-emerald-500 disabled:opacity-40 disabled:cursor-not-allowed transition-all mt-2"
          >
            <UserPlus className="w-4 h-4" />
            <span>{registerMutation.isPending ? 'Registering...' : 'Create Account'}</span>
          </button>
        </form>

        <div className="text-center text-xs text-slate-500 font-medium pt-2 border-t border-slate-100">
          <span>Already have an account? </span>
          <Link to="/login" className="font-bold text-emerald-600 hover:text-emerald-700 transition-colors">
            Sign in here
          </Link>
        </div>
      </div>
    </div>
  );
}
