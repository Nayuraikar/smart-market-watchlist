import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { watchlistsApi } from '../api/watchlists';
import { WatchlistCreate } from '../types/watchlist';

export const useWatchlists = () => {
  return useQuery({
    queryKey: ['watchlists', 'list'],
    queryFn: watchlistsApi.list,
  });
};

export const useCreateWatchlist = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (data: WatchlistCreate) => watchlistsApi.create(data),
    onSuccess: () => {
      // Invalidate the list to show the newly created watchlist
      queryClient.invalidateQueries({ queryKey: ['watchlists', 'list'] });
    },
  });
};
