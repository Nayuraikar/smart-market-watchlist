import { useEffect, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { watchlistsApi } from '../api/watchlists';
import { stocksApi } from '../api/stocks';
import { WatchlistUpdate, StockAdd, WatchlistOut } from '../types/watchlist';
import { Objective } from '../types/market';
import { InstrumentDetail } from '../types/instrument';

export const useWatchlist = (watchlistId: string, objective?: Objective) => {
  return useQuery({
    queryKey: ['watchlist', watchlistId, 'since-last-visit', { objective }],
    queryFn: () => watchlistsApi.get(watchlistId, objective),
    enabled: !!watchlistId,
    refetchInterval: 5000,
  });
};

export const useWatchlistStocks = (watchlistId: string) => {
  return useQuery({
    queryKey: ['watchlist', watchlistId, 'stocks'],
    queryFn: () => stocksApi.list(watchlistId),
    enabled: !!watchlistId,
    refetchInterval: 5000,
  });
};

export const useInstrumentDetail = (watchlistId: string, instrumentId: string, objective?: Objective) => {
  return useQuery<InstrumentDetail>({
    queryKey: ['watchlist', watchlistId, 'stock', instrumentId, { objective }],
    queryFn: () => stocksApi.detail(watchlistId, instrumentId, objective),
    enabled: !!watchlistId && !!instrumentId,
    refetchInterval: 5000,
  });
};

export const useUpdateWatchlist = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: WatchlistUpdate }) => watchlistsApi.update(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['watchlists', 'list'] });
      queryClient.invalidateQueries({ queryKey: ['watchlist', variables.id] });
    },
  });
};

export const useDeleteWatchlist = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (id: string) => watchlistsApi.delete(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: ['watchlists', 'list'] });
      queryClient.removeQueries({ queryKey: ['watchlist', id] });
    },
  });
};

export const useAddStock = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ watchlistId, data }: { watchlistId: string; data: StockAdd }) => stocksApi.add(watchlistId, data),
    onSuccess: (_, variables) => {
      // Invalidate both the detail dashboard and the specific stocks list
      queryClient.invalidateQueries({ queryKey: ['watchlist', variables.watchlistId] });
    },
  });
};

export const useRemoveStock = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ watchlistId, instrumentId }: { watchlistId: string; instrumentId: string }) => stocksApi.remove(watchlistId, instrumentId),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['watchlist', variables.watchlistId] });
    },
  });
};

/**
 * Custom hook to safely trigger POST /viewed exactly once per viewing session.
 * 
 * @param watchlistId The active watchlist ID
 * @param isSuccess The isSuccess boolean from the useWatchlist TanStack query
 */
export const useMarkWatchlistViewed = (watchlistId: string | undefined, isSuccess: boolean) => {
  const queryClient = useQueryClient();
  
  // Guard to prevent double execution via React StrictMode or re-renders
  const hasViewed = useRef<boolean>(false);
  
  // Track previous ID to reset the session if the user switches watchlists without unmounting
  const previousId = useRef<string | undefined>(watchlistId);

  const { mutate } = useMutation({
    mutationFn: (id: string) => watchlistsApi.markViewed(id),
    onSuccess: (updatedWatchlist: WatchlistOut, id: string) => {
      // Do NOT invalidate broad queries to prevent unnecessary refetches.
      // Instead, manually update the watchlist list cache if it exists so sidebars update accurately.
      queryClient.setQueryData<WatchlistOut[]>(['watchlists', 'list'], (oldList) => {
        if (!Array.isArray(oldList)) return oldList;
        return oldList.map((w) => 
          w.id === id ? { ...w, last_viewed_at: updatedWatchlist.last_viewed_at } : w
        );
      });
    },
  });

  useEffect(() => {
    if (!watchlistId) return;

    // Reset session state if the watchlist ID changes
    if (previousId.current !== watchlistId) {
      hasViewed.current = false;
      previousId.current = watchlistId;
    }

    // Only fire the mutation if the GET fetch succeeded AND we haven't fired it yet this session
    if (isSuccess && !hasViewed.current) {
      hasViewed.current = true;
      mutate(watchlistId);
    }
  }, [watchlistId, isSuccess, mutate]);
};
