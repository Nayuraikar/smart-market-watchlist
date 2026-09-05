import React, { useEffect, useState, useCallback } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { authApi } from '../api/auth';

import { AuthContext } from './context';

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const queryClient = useQueryClient();
  const [token, setTokenState] = useState<string | null>(() => localStorage.getItem('access_token'));

  // Only run the query if we have a token
  const { data: user, isLoading: isQueryLoading, isError } = useQuery({
    queryKey: ['auth', 'me'],
    queryFn: authApi.me,
    enabled: !!token,
    retry: false, // Don't retry on 401
  });

  const setToken = useCallback((newToken: string) => {
    localStorage.setItem('access_token', newToken);
    setTokenState(newToken);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('access_token');
    setTokenState(null);
    queryClient.removeQueries({ queryKey: ['auth', 'me'] });
    queryClient.removeQueries({ queryKey: ['watchlists'] }); // Clear all related watchlists queries
    queryClient.removeQueries({ queryKey: ['watchlist'] }); 
  }, [queryClient]);

  // Handle unauthorized events globally broadcasted from Axios
  useEffect(() => {
    const handleUnauthorized = () => {
      logout();
    };
    window.addEventListener('unauthorized', handleUnauthorized);
    return () => window.removeEventListener('unauthorized', handleUnauthorized);
  }, [logout]);

  // Determine the overall loading state
  // If we have a token but haven't resolved the query yet, we are loading.
  const isLoading = !!token && isQueryLoading;

  return (
    <AuthContext.Provider value={{
      user: user || null,
      isAuthenticated: !!user && !isError,
      isLoading,
      setToken,
      logout,
    }}>
      {children}
    </AuthContext.Provider>
  );
};

