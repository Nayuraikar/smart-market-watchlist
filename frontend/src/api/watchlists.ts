import { apiClient } from './client';
import { WatchlistCreate, WatchlistUpdate, WatchlistOut } from '../types/watchlist';
import { WatchlistSinceLastVisitOut } from '../types/market';
import { Objective } from '../types/market';

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
    const params = objective ? { objective } : undefined;
    const response = await apiClient.get<WatchlistSinceLastVisitOut>(`/watchlists/${id}`, { params });
    return response.data;
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
