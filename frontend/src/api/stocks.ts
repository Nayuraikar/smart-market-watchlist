import { apiClient } from './client';
import { StockAdd, StockOut } from '../types/watchlist';
import { InstrumentDetail } from '../types/instrument';

export const stocksApi = {
  list: async (watchlistId: string): Promise<StockOut[]> => {
    const response = await apiClient.get<StockOut[]>(`/watchlists/${watchlistId}/stocks`);
    return response.data;
  },
  add: async (watchlistId: string, data: StockAdd): Promise<StockOut> => {
    const response = await apiClient.post<StockOut>(`/watchlists/${watchlistId}/stocks`, data);
    return response.data;
  },
  remove: async (watchlistId: string, instrumentId: string): Promise<void> => {
    await apiClient.delete(`/watchlists/${watchlistId}/stocks/${instrumentId}`);
  },
  detail: async (watchlistId: string, instrumentId: string, objective?: string): Promise<InstrumentDetail> => {
    const params = objective ? { objective } : undefined;
    const response = await apiClient.get<InstrumentDetail>(
      `/watchlists/${watchlistId}/stocks/${instrumentId}`,
      { params },
    );
    return response.data;
  },
};
