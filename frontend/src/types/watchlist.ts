import { Objective } from './market';

export interface WatchlistCreate {
  name: string;
  objective: Objective;
}

export interface WatchlistUpdate {
  name?: string;
  objective?: Objective;
}

export interface WatchlistOut {
  id: string;
  name: string;
  objective: Objective;
  last_viewed_at: string | null;
  created_at: string;
}

export interface StockAdd {
  ticker: string;
}

export interface StockOut {
  instrument_id: string;
  ticker: string;
  name: string;
  exchange: string;
  added_at: string;
}
