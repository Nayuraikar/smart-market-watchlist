# Architecture

## Collection (optional, online)

`backend/scripts/collect_historical_data.py` → yfinance → completed historical date range → committed historical JSON and coverage manifest. Optional fundamentals are collected snapshots, explicitly distinct from historical price dates. Failed downloads preserve prior captured data. Collector dependencies are separate from runtime requirements.

## Runtime (offline)

Saved historical JSON → replay provider → periodic worker → validation and atomic PostgreSQL state/history/event writes. Prices and volume are preserved; only timestamps and source labels are rebased for simulation. Startup initializes historical context and the worker advances/repeats the saved update timeline. No market API is called.

Price moves at or above 2% produce events. Invalid prices, negative volume and non-increasing observation sequences are rejected. Other detector functions exist but are not wired to this worker.

## Reads and persistence

FastAPI authenticates requests and verifies watchlist ownership/membership. Instrument detail returns current metrics, explained events and up to 180 chronological history points. Chart points are sampled observations, not fabricated OHLC candles.

The feed compares events against the later of each stock's tracking start and the persisted visit boundary. GET is read-only; a separate acknowledgement persists the visit. A browser-session boundary preserves the visible feed across refreshes and objective changes. Logout clears it so the next login uses persisted state. The UI refreshes every five seconds.

## Tradeoffs

One ingestion stream serves all users; no per-user provider calls. History is indexed and chart reads are bounded. Full event-feed pagination, persisted replay cursors, distributed worker coordination, and production deployment hardening remain future work. Replay loops can create boundary events. Data freshness describes simulation timestamps; this is not a live exchange quote service.

See data/README.md for provenance, SUBMISSION.md for challenge mapping, and README.md for setup and tests.
