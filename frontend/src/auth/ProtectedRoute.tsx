import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from './context';

export const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="text-slate-500 animate-pulse font-medium">Restoring session...</div>
      </div>
    );
  }

  // Prevent redirect loops if an authenticated user lands on /login or /register
  const isAuthRoute = location.pathname === '/login' || location.pathname === '/register';
  
  if (isAuthenticated && isAuthRoute) {
    return <Navigate to="/" replace />;
  }

  if (!isAuthenticated && !isAuthRoute) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
};
