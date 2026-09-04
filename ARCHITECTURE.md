# Architecture

## Architecture Overview

The application separates user state, market state, data ingestion, and
intelligence.

The frontend communicates only with the FastAPI backend. The backend is
responsible for authentication, authorization, business logic, change
detection, objective scoring, and serving watchlist data.

PostgreSQL is the canonical server-side source of truth.

External market data is treated as an input to the system rather than as the
application's database.

---

## Diagram

                         ┌──────────────────┐
                         │   React + Vite    │
                         │    Frontend       │
                         └────────┬─────────┘
                                  │ HTTPS / REST
                                  ▼
                         ┌──────────────────┐
                         │  FastAPI Backend  │
                         │                  │
                         │ Auth             │
                         │ Watchlists       │
                         │ Market API       │
                         │ Intelligence     │
                         └───────┬──────────┘
                                 │
                ┌────────────────┼────────────────┐
                │                │                │
                ▼                ▼                ▼
        ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
        │  PostgreSQL  │ │ Intelligence │ │   Provider   │
        │              │ │    Layer     │ │ Abstraction  │
        │ User state   │ │              │ │              │
        │ Market state │ │ Changes      │ │ Real API     │
        │ History      │ │ Scores       │ │ Replay       │
        │ Events       │ │ Attention    │ │              │
        └──────────────┘ └──────────────┘ └──────┬───────┘
                                                │
                                                ▼
                                     Indian Stock Market API
                                                │
                                                ▼
                                         Yahoo Finance

                        Separate ingestion path:

                 Market Data Provider
                          │
                          ▼
                 Ingestion Pipeline
                          │
             ┌────────────┼────────────┐
             ▼            ▼            ▼
        market_state  market_history  market_events