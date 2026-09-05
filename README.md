# Smart Market Watchlist

A persistent stock watchlist that explains **what changed since your last visit**, why it matters to your Growth, Value or Stability objective, and which changes deserve attention.

Built for **Code, by Groww 2026**. React + TypeScript, FastAPI and PostgreSQL.

**Historical collection → saved JSON → offline replay.** yfinance is used only by the optional collection script. The application and startup read committed historical observations for 57 stocks and never call a live market API. Prices and volumes are genuine saved market data. Fundamentals are separate snapshots where available; missing values are not fabricated.

## Collect historical data once (optional)

The committed historical files already work without downloading anything: 13,922 actual observations across 57 stocks (248 each for 56 stocks; 34 for TMCV). Market cap and P/E snapshots are supplied for all 57; dividend yield is supplied for 55 and explicitly missing for two. To refresh them:

```bash
cd backend
python3 -m pip install -r requirements-collector.txt
python3 scripts/collect_historical_data.py --start 2025-01-01 --end 2026-01-01
cd ..
./start.sh
```

Use `--snapshots` to also capture available fundamentals at collection time. These are explicitly separate from the historical price dates. Failed downloads retain prior saved history per ticker; successful downloads record coverage in `data/scenarios/historical_manifest.json`. No API credentials are required by this collector, but Yahoo can rate-limit requests.

The UI, watchlists, charts, objective explanations, session behavior and metric cards are retained. Historical files determine chart length; 180 is the chart's maximum display window, not a claim that every source supplies exactly 180 points.

## What works

- Register, log in, and manage persistent watchlists.
- Search the offline stock catalog by ticker or company name.
- Replay rising prices, pullbacks, quiet periods, and volume changes into PostgreSQL.
- View price, previous close and volume, plus market cap, P/E and dividend yield wherever the saved source provides them.
- Explore price history with 30/90/180-observation charts and a keyboard-accessible scrubber.
- Detect price moves of **2% or more** and rank them with explanations under three investment objectives.
- Preserve a server-side last-visit boundary, with a stable comparison window during the browser login session.
- Refresh market pages every five seconds while the simulation advances every 30 seconds.

Volume, benchmark-relative and 52-week detection functions have unit coverage, but the ingestion worker currently emits **price-move events only**. A price update below 2% intentionally produces no event.

## Run locally

Prerequisites: Docker with Compose, Node.js 20+ with npm, Bash and curl. Python 3.12 is needed only for local backend development or regenerating the data.

```bash
git clone https://github.com/Nayuraikar/smart-market-watchlist.git
cd smart-market-watchlist
./start.sh
```

Open **http://localhost:5173**. Register an account, create a watchlist and add stocks such as RELIANCE, TCS and INFY. API documentation is at **http://localhost:8000/docs**.

Startup builds the backend, applies migrations, seeds offline company names, loads the saved historical baseline and update scenario for every stock, then starts the repeating simulation and frontend. The initial update timestamps are rebased to the current time. The frontend opens automatically on macOS.

**Restarting `start.sh` resets demo market state, market history, events and visit boundaries. Users, watchlists and tracked stocks are preserved.** Ctrl+C stops the processes/services this invocation starts; services already running may remain up.

For a faster walkthrough:

```bash
SIMULATION_INTERVAL_SECONDS=5 ./start.sh
```

The saved update sequence repeats at the configured pace. A worker restart begins at its first row. Real historical price moves determine when events occur; no price jumps are manufactured. A newly added stock only contributes events after tracking begins, so allow subsequent ticks before expecting its change feed to fill.

## Saved data and reproducibility

- `data/scenarios/historical_baseline_57.json`: genuine captured historical baseline.
- `data/scenarios/historical_update_57.json`: genuine historical timeline replayed periodically.
- `data/scenarios/historical_manifest.json`: coverage/provenance from the latest successful collection, when present.
- `backend/scripts/collect_historical_data.py`: isolated optional yfinance collector.
- `data/demo_catalog.json`: company names/sectors; its synthetic financial assumptions are not used by historical replay.
- `demo_*.json` and `scripts/generate_demo_data.py`: retained, explicitly synthetic alternative fixtures, **not the default**.

The collector uses adjusted daily closing prices to reduce artificial jumps caused by splits. The existing older captures retain their original source basis. Historical candles do not contain daily historical P/E, market cap or dividend yield; the app labels absent fields rather than substituting fake numbers. Optional fundamentals snapshots record collection-time values. See [data/README.md](data/README.md).

## Architecture

```mermaid
flowchart LR
  JSON[Saved scenario JSON] --> Worker[Timed replay worker]
  Worker --> Ingest[Validation and price-change detection]
  Ingest --> DB[(PostgreSQL state / history / events)]
  DB --> API[FastAPI ownership checks and objective scoring]
  API --> UI[React watchlists and price charts]
  UI -->|Acknowledge visit| API
```

The ingestion transaction writes current state, history and events together. Invalid prices, negative volume and out-of-order observations are rejected. Historical chart points are accepted observations, not fabricated OHLC candles. Chart spacing represents observation order, not elapsed wall-clock time.

A read does not modify `last_viewed_at`. After a successful visit the client acknowledges it separately. Within the browser login session, it preserves the previous boundary in session storage and sends `since` on refreshes and perspective changes. Logging out clears that window; the next login uses the persisted boundary. Each stock is still filtered by its own `added_at`. New events arrive automatically without erasing the current feed.

More detail: [ARCHITECTURE.md](ARCHITECTURE.md), [SCORING_MODEL.md](SCORING_MODEL.md), [DEMO_SCRIPT.md](DEMO_SCRIPT.md).

## Development and checks

Frontend:

```bash
cd frontend
npm ci
npm run dev
npm run lint
npm run build
```

Backend checks should use a dedicated test database. With the Compose backend and PostgreSQL running, create it once:

```bash
docker compose exec postgres createdb -U app watchlist_test
```

Then run migrations and tests (repeatable):

```bash
docker compose exec -e DATABASE_URL=postgresql+asyncpg://app:app@postgres:5432/watchlist_test backend alembic upgrade head
docker compose exec -e DATABASE_URL=postgresql+asyncpg://app:app@postgres:5432/watchlist_test backend python -m pytest -q
python3 scripts/generate_demo_data.py --check
bash -n start.sh
docker compose config --quiet
```

For a host Python environment, install `backend/requirements.txt`, export `DATABASE_URL` using `localhost:5432` and a `JWT_SECRET`, then run Alembic and pytest from `backend` with `PYTHONPATH=.`. The tests create and clean their fixtures; do not point the suite at an important database.

GitHub Actions runs dataset reproducibility, migrations, all backend tests against a fresh PostgreSQL service, frontend lint/build, and startup/Compose syntax checks. Dependencies require internet during installation; **market-data ingestion does not**.

## Configuration and troubleshooting

| Setting | Default / behavior |
|---|---|
| `SIMULATION_INTERVAL_SECONDS` | 30; positive integer, exported to Compose by startup |
| `REPLAY_SCENARIO` | `data/scenarios/historical_update_57.json` in the worker service |
| `DATABASE_URL` | Local demo PostgreSQL; set explicitly for host development/tests |
| `JWT_SECRET` | Compose has a local-development placeholder; configure a private value for deployment |
| `VITE_API_BASE_URL` | See `frontend/src/api/client.ts`; frontend defaults to localhost API |

- **No events yet:** confirm tracked stocks, wait for a ≥2% tick, and check `docker compose logs --tail 20 market-ingestion`. Small changes should not become signals.
- **Old values after data edits:** restart the worker with `docker compose restart market-ingestion`. To replace the entire history, rerun `start.sh` (market reset described above).
- **Ports in use:** the demo uses 5173, 8000 and 5432. Adminer is optional on 8080.
- **Data badges:** “Fresh” describes the simulated observation timestamp, not a live quote. Event badges capture quality at event time.

## Repository contents

```text
backend/app/             API, schemas, models, ingestion, scoring and replay
backend/alembic/         Database migrations
backend/tests/           Unit and database/API regression tests
frontend/src/            Watchlists, metrics, charts and session behavior
data/                    Saved demo catalog, scenarios and provenance
scripts/                 Offline reproducible dataset generator
.github/workflows/       Automated GitHub checks
start.sh                 Complete local demo startup
```

This repository is a local demo, not a production deployment. The development credentials and ports in Compose are intentional local defaults. `.env`, caches, build output and editor histories are excluded from Git. Older design documents retain historical decisions and future detector plans; the README and data guide describe the current demo behavior.
