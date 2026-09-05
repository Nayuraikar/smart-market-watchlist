import { apiClient } from './client';
import { WatchlistCreate, WatchlistUpdate, WatchlistOut } from '../types/watchlist';
import { WatchlistSinceLastVisitOut } from '../types/market';
import { Objective } from '../types/market';

const FIRST_VISIT_BOUNDARY = '1970-01-01T00:00:00Z';

export const watchlistsApi = {
  create: async (data: WatchlistCreate): Promise<WatchlistOut> => {
    const response = await apiClient.post<WatchlistOut>('/watchlists', data);
    return response.data;
  },
  list: async (): Promise<WatchlistOut[]> => {
    const response = await apiClient.get<WatchlistOut[]>('/watchlists');
    return response.data;
  },
  get: async (id: string, objective?: Objective): Promise<WatchlistSinceLastVisitOut> => {
    const key = `watchlist-boundary:${id}`;
    const since = sessionStorage.getItem(key);
    const params = { objective, ...(since ? { since } : {}) };
    const response = await apiClient.get<WatchlistSinceLastVisitOut>(`/watchlists/${id}`, { params });
    if (!since) {
      sessionStorage.setItem(key, response.data.last_viewed_at || FIRST_VISIT_BOUNDARY);
    }
    // The epoch is a query sentinel, never a real user visit date.
    return { ...response.data, last_viewed_at: since === FIRST_VISIT_BOUNDARY ? null : response.data.last_viewed_at };
  },
  update: async (id: string, data: WatchlistUpdate): Promise<WatchlistOut> => {
    const response = await apiClient.patch<WatchlistOut>(`/watchlists/${id}`, data);
    return response.data;
  },
  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/watchlists/${id}`);
  },
  markViewed: async (id: string): Promise<WatchlistOut> => {
    const response = await apiClient.post<WatchlistOut>(`/watchlists/${id}/viewed`);
    return response.data;
  },
};
