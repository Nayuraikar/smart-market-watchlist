export type Objective = "GROWTH" | "VALUE" | "STABILITY";
export type AttentionTier = "HIGH" | "MEDIUM" | "LOW";
export type DataQualityState = "FRESH" | "STALE" | "UNAVAILABLE";

export interface DataStatus {
  state: DataQualityState;
  message: string | null;
}

export interface ScoredEventExplanation {
  instrument_id: string;
  event_type: string;
  detected_at: string;
  what_happened: string;
  magnitude: string;
  benchmark_comparison: string | null;
  objective_relevance: string;
  data_status: DataStatus;
  data_confidence: number;
  attention_tier: AttentionTier;
  composite_score: number;
}

export interface InstrumentSinceLastVisit {
  instrument_id: string;
  ticker: string;
  name: string;
  exchange: string;
  added_at: string;
  top_event: ScoredEventExplanation | null;
}

export interface SinceLastVisit {
  meaningful_change_count: number;
  events: ScoredEventExplanation[];
}

export interface WatchlistSinceLastVisitOut {
  watchlist_id: string;
  objective: Objective;
  last_viewed_at: string | null;
  since_last_visit: SinceLastVisit;
  instruments: InstrumentSinceLastVisit[];
}
