import { DataStatus, Objective, ScoredEventExplanation } from './market';

export interface CurrentMarketData {
  price: number | null;
  previous_close: number | null;
  volume: number | null;
  market_cap: number | null;
  pe_ratio: number | null;
  dividend_yield: number | null;
  observed_at: string | null;
  data_status: DataStatus;
}

export interface InstrumentDetail {
  instrument_id: string;
  ticker: string;
  name: string;
  exchange: string;
  objective: Objective;
  current_data: CurrentMarketData | null;
  events: ScoredEventExplanation[];
}