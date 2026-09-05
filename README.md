# Smart Market Watchlist

A persistent stock watchlist that explains **what changed since your last visit**, why it matters to your Growth, Value or Stability objective, and which changes deserve attention.

Built for **Code, by Groww 2026** using React + TypeScript, FastAPI and PostgreSQL.

## Market data model

The submitted application deliberately separates market-data collection from runtime behavior.

Historical market observations are collected once and committed as reproducible datasets. At runtime, the application replays those saved observations through the same validation, persistence, event-detection and attention pipeline that a live provider could feed.

The runtime application does **not** contact a live market API.

* Prices and volumes are genuine saved historical market observations.
* Replay timestamps are rebased so changes can be demonstrated deterministically.
* Fundamentals are stored as separate snapshots where available.
* Missing values are never fabricated.
* `yfinance` is used only by the optional historical-data collection script.

This design keeps the demo deterministic and independent of third-party API availability or rate limits while preserving a provider-independent ingestion boundary.

The application and startup read committed historical observations for 57 stocks. The default dataset contains 13,922 observations: 248 each for 56 stocks and 34 for TMCV.

Market cap and P/E snapshots are supplied for all 57 stocks. Dividend yield is supplied for 55 and explicitly missing for two.

## Collect historical data once (optional)

The committed historical files already work without downloading anything. You do **not** need to run the collector to start the application.

To refresh the historical dataset:

```bash
cd backend
python3 -m pip install -r requirements-collector.txt
python3 scripts/collect_historical_data.py --start 2025-01-01 --end 2026-01-01
cd ..
./start.sh
```

Use `--snapshots` to also capture available fundamentals at collection time.

These snapshots are explicitly separate from the historical price dates.

Failed downloads retain prior saved history per ticker. Successful downloads record coverage in:

```text
data/scenarios/historical_manifest.json
```

No API credentials are required by the collector, but Yahoo can rate-limit requests.

The UI, watchlists, charts, objective explanations, session behavior and metric cards are retained regardless of whether the optional collector is run.

Historical files determine chart length. `180` is the chart's maximum display window, not a claim that every source supplies exactly 180 points.

## Implemented scope

The submitted runtime intentionally keeps the market-event pipeline narrow and defensible.

Currently wired into ingestion:

* `PRICE_MOVE` events for absolute price moves of **2% or more**
* persistent historical observations
* objective-aware relevance and attention
* since-last-visit filtering
* explanation generation
* data freshness and validation
* persistent watchlists and authentication

Implemented and unit-tested but not wired into the submitted replay worker:

* volume-surge detection
* benchmark-relative detection
* 52-week high/low detection

The broader engineering and product decisions are documented in [`docs/`](docs/). This README and [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) describe the exact submitted runtime behavior.

## What works

* Register, log in and manage persistent watchlists.
* Search the offline stock catalog by ticker or company name.
* Replay rising prices, pullbacks, quiet periods and volume changes into PostgreSQL.
* View price, previous close and volume, plus market cap, P/E and dividend yield wherever the saved source provides them.
* Explore price history with 30/90/180-observation charts and a keyboard-accessible scrubber.
* Detect price moves of **2% or more** and rank them with explanations under three investment objectives.
* Preserve a server-side last-visit boundary, with a stable comparison window during the browser login session.
* Refresh market pages every five seconds while the simulation advances every 30 seconds by default.

Volume, benchmark-relative and 52-week detection functions have unit coverage, but the submitted ingestion worker currently emits **price-move events only**.

A price update below 2% intentionally produces no event.

# Run locally

## Prerequisites

You need:

* Docker Desktop with Docker Compose
* Node.js 20+ with npm
* Git
* Bash and curl
* Python 3.12 only for local backend development or regenerating historical data

Docker Desktop handles PostgreSQL and the backend containers.

Node.js is used for the frontend.

You do **not** need to install PostgreSQL manually.

## 1. Install Docker Desktop

Download and install Docker Desktop:

**macOS / Windows:**
https://www.docker.com/products/docker-desktop/

After installation, open Docker Desktop and wait until the Docker engine is running.

Verify the installation:

```bash
docker --version
docker compose version
```

Both commands should print version information.

## 2. Install Node.js

Install **Node.js 20 or newer**:

https://nodejs.org/

Verify the installation:

```bash
node --version
npm --version
```

## 3. Install Git

Download Git if it is not already installed:

https://git-scm.com/downloads

Verify it:

```bash
git --version
```

## 4. Clone the repository

Open a terminal and run:

```bash
git clone https://github.com/Nayuraikar/smart-market-watchlist.git
cd smart-market-watchlist
```

You should now be inside the project root containing:

```text
backend/
frontend/
data/
demo/
docs/
scripts/
docker-compose.yml
start.sh
README.md
```

---

## macOS / Linux

Make sure Docker Desktop or your Docker engine is running.

From the project root:

```bash
./start.sh
```

If the script is not executable:

```bash
chmod +x start.sh
./start.sh
```

For a faster walkthrough:

```bash
SIMULATION_INTERVAL_SECONDS=5 ./start.sh
```

The normal simulation interval is 30 seconds. The faster setting is useful when evaluating the change feed without waiting between replay observations.

---

## Windows

The project startup script is written in Bash.

The easiest Windows setup is to use **Git Bash**, which is included with Git for Windows.

Install Git for Windows from:

https://git-scm.com/download/win

Then:

1. Open Docker Desktop.
2. Wait until Docker reports that the engine is running.
3. Open the `smart-market-watchlist` folder.
4. Right-click inside the folder.
5. Select **Open Git Bash here**.
6. Run:

```bash
bash start.sh
```

You can also try:

```bash
./start.sh
```

For a faster walkthrough:

```bash
SIMULATION_INTERVAL_SECONDS=5 bash start.sh
```

If `./start.sh` reports a permission or execution issue on Windows, use:

```bash
bash start.sh
```

This executes the script through Bash without requiring Unix executable permissions.

## What startup does

`start.sh` prepares the complete local application.

Startup:

* starts PostgreSQL and the backend with Docker Compose
* applies database migrations
* ensures the instrument catalog exists
* resets demo market state
* loads the saved historical baseline
* loads the saved historical update scenario
* rebases update timestamps to the current time
* starts the repeating market simulation
* installs/uses the frontend dependencies as required
* starts the frontend

The first run can take longer because Docker may need to download images and build the backend container.

Once startup completes, open:

```text
http://localhost:5173
```

Register an account, create a watchlist and add stocks such as:

```text
RELIANCE
TCS
INFY
```

FastAPI's interactive API documentation is available at:

```text
http://localhost:8000/docs
```

The initial update timestamps are rebased to the current time so the saved historical sequence can be demonstrated as a deterministic running simulation.

The frontend opens automatically on macOS when supported.

**Restarting `start.sh` resets demo market state, market history, events and visit boundaries. Users, watchlists and tracked stocks are preserved.**

`Ctrl+C` stops the processes/services started by that invocation. Services that were already running may remain up.

The saved update sequence repeats at the configured pace. A worker restart begins at its first row.

Real historical price moves determine when events occur. No price jumps are manufactured merely to trigger the interface.

A newly added stock only contributes events after tracking begins, so allow subsequent replay ticks before expecting its change feed to fill.

To stop all Compose services manually:

```bash
docker compose down
```

# Saved data and reproducibility

* `data/scenarios/historical_baseline_57.json`: genuine captured historical baseline.
* `data/scenarios/historical_update_57.json`: genuine historical timeline replayed periodically.
* `data/scenarios/historical_manifest.json`: coverage/provenance from the latest successful collection, when present.
* `backend/scripts/collect_historical_data.py`: isolated optional yfinance collector.
* `data/demo_catalog.json`: company names/sectors; its synthetic financial assumptions are not used by historical replay.
* `demo_*.json` and `scripts/generate_demo_data.py`: retained synthetic alternative fixtures, **not the default**.

The collector uses adjusted daily closing prices to reduce artificial jumps caused by splits.

Existing older captures retain their original source basis.

Historical candles do not contain daily historical P/E, market cap or dividend yield. The application labels absent fields rather than substituting fabricated values.

Optional fundamentals snapshots record collection-time values.

See [`data/README.md`](data/README.md) for additional information about the saved datasets.

# Architecture

```mermaid
flowchart LR
    JSON[Saved historical observations] --> Worker[Timed replay worker]
    Worker --> Ingest[Validation and price-change detection]
    Ingest --> DB[(PostgreSQL state / history / events)]
    DB --> API[FastAPI ownership checks and objective scoring]
    API --> UI[React watchlists and price charts]
    UI -->|Acknowledge visit| API
```

The architecture separates market observations from user-specific interpretation.

```mermaid
flowchart TD
    A[Saved Market Observation] --> B[Validation]
    B --> C[Persist Current State + History]
    C --> D{Absolute price move >= 2%?}
    D -->|No| E[No PRICE_MOVE event]
    D -->|Yes| F[Create PRICE_MOVE event]
    F --> G[Objective Relevance]
    G --> H[Attention Ranking]
    H --> I[Since-Last-Visit Filtering]
    I --> J[Explanation]
    J --> K[React UI]
```

The ingestion transaction writes current state, historical observations and resulting events together.

Invalid prices, negative volume and out-of-order observations are rejected.

Historical chart points are accepted observations, not fabricated OHLC candles.

Chart spacing represents observation order, not elapsed wall-clock time.

## Last-visit semantics

A read does not modify `last_viewed_at`.

After a successful visit, the client acknowledges the visit separately.

Within the browser login session, the client preserves the previous comparison boundary in session storage and sends `since` during refreshes and perspective changes.

This means refreshing the page or switching investment objectives does not immediately erase the changes the user is reviewing.

Logging out clears the session comparison window.

The next login uses the persisted server-side boundary.

Each stock is additionally filtered by its own `added_at`, preventing events from before the user began tracking the stock from appearing as new changes.

New events can therefore arrive automatically without erasing the current feed.

### Detailed documentation

* [Architecture](docs/ARCHITECTURE.md)
* [Data specification](docs/DATA_SPEC.md)
* [Engineering decisions](docs/DECISIONS.md)
* [Scoring model](docs/SCORING_MODEL.md)
* [Demo script](docs/DEMO_SCRIPT.md)
* [Product pitch](docs/PRODUCT_PITCH.md)

# Design trade-offs

One ingestion stream serves all users, so tracking the same instrument across many watchlists does not create one market-data stream per user.

Historical observations are shared application state. Watchlists, objectives and visit boundaries remain user-specific state.

History reads are indexed and chart responses are bounded.

The submitted application uses deterministic historical replay rather than a live market-data dependency. This makes the demo reproducible and prevents evaluation from depending on third-party API availability, rate limits or temporary outages.

The ingestion boundary remains provider-independent, so a production market feed can replace the replay provider without changing the watchlist, event, relevance or attention layers.

The current replay worker intentionally emits `PRICE_MOVE` events only. Other detector functions exist and have test coverage but are not wired into the submitted worker.

Full event-feed pagination, persisted replay cursors, distributed worker coordination, multi-provider reconciliation and production deployment hardening remain future work.

Replay loops can create boundary events.

Data freshness describes simulation timestamps and must not be interpreted as a live exchange quote.

# Development and checks

## Frontend

```bash
cd frontend
npm ci
npm run dev
npm run lint
npm run build
```

## Backend

Backend checks should use a dedicated test database.

With the Compose backend and PostgreSQL running, create the test database once:

```bash
docker compose exec postgres createdb -U app watchlist_test
```

Then run migrations and tests:

```bash
docker compose exec \
  -e DATABASE_URL=postgresql+asyncpg://app:app@postgres:5432/watchlist_test \
  backend alembic upgrade head

docker compose exec \
  -e DATABASE_URL=postgresql+asyncpg://app:app@postgres:5432/watchlist_test \
  backend python -m pytest -q
```

Additional checks:

```bash
python3 scripts/generate_demo_data.py --check
bash -n start.sh
docker compose config --quiet
```

For a host Python environment, install:

```text
backend/requirements.txt
```

Then export `DATABASE_URL` using `localhost:5432` and configure a `JWT_SECRET`.

Run Alembic and pytest from `backend` with:

```bash
PYTHONPATH=.
```

The tests create and clean their fixtures.

Do not point the test suite at an important database.

# Configuration and troubleshooting

| Setting                       | Default / behavior                                                                         |
| ----------------------------- | ------------------------------------------------------------------------------------------ |
| `SIMULATION_INTERVAL_SECONDS` | `30`; positive integer exported to Compose by startup                                      |
| `REPLAY_SCENARIO`             | `data/scenarios/historical_update_57.json` in the worker service                           |
| `DATABASE_URL`                | Local demo PostgreSQL; set explicitly for host development/tests                           |
| `JWT_SECRET`                  | Compose contains a local-development placeholder; configure a private value for deployment |
| `VITE_API_BASE_URL`           | See `frontend/src/api/client.ts`; frontend defaults to the localhost API                   |

## Docker is not running

Open Docker Desktop and wait until the Docker engine starts before running the startup script.

Verify:

```bash
docker compose version
```

## Docker command not found

Install Docker Desktop and reopen your terminal after installation.

## Windows `./start.sh` does not run

Use Git Bash:

```bash
bash start.sh
```

## No events yet

Confirm that stocks have been added to your watchlist and allow the simulation to advance.

`PRICE_MOVE` events require an absolute movement of at least **2%** between consecutive accepted observations.

Inspect the ingestion worker:

```bash
docker compose logs --tail 20 market-ingestion
```

Small price changes intentionally do not become signals.

For a faster demonstration:

### macOS / Linux

```bash
SIMULATION_INTERVAL_SECONDS=5 ./start.sh
```

### Windows Git Bash

```bash
SIMULATION_INTERVAL_SECONDS=5 bash start.sh
```

## Old values after data edits

Restart the ingestion worker:

```bash
docker compose restart market-ingestion
```

To replace the entire demo history, rerun:

### macOS / Linux

```bash
./start.sh
```

### Windows

```bash
bash start.sh
```

## Ports already in use

The local demo uses:

| Service               |   Port |
| --------------------- | -----: |
| Frontend              | `5173` |
| FastAPI backend       | `8000` |
| PostgreSQL            | `5432` |
| Adminer, when enabled | `8080` |

## Data badges

“Fresh” describes the simulated observation timestamp.

It does **not** mean the value is a live exchange quote.

Event badges capture data quality at event time.

# Repository contents

```text
smart-market-watchlist/
├── backend/
│   ├── app/                API, models, ingestion, scoring and replay
│   ├── alembic/            Database migrations
│   ├── scripts/            Historical-data collection
│   └── tests/              Unit and database/API regression tests
│
├── frontend/
│   └── src/                Watchlists, metrics, charts and session behavior
│
├── data/
│   └── scenarios/          Saved historical observations and provenance
│
├── demo/
│   └── index.html          Standalone interactive walkthrough
│
├── docs/
│   ├── ARCHITECTURE.md     Detailed system architecture
│   ├── DATA_SPEC.md        Market-data and provenance specification
│   ├── DECISIONS.md        Engineering decisions and trade-offs
│   ├── DEMO_SCRIPT.md      Guided demonstration flow
│   ├── PRODUCT_PITCH.md    100-word product pitch
│   └── SCORING_MODEL.md    Objective scoring methodology
│
├── scripts/                Offline reproducible dataset utilities
│
├── .env.example
├── .gitignore
├── docker-compose.yml
├── start.sh
└── README.md
```

This repository is a local demonstration, not a production deployment.

Development credentials and ports in Compose are intentional local defaults.

`.env`, virtual environments, caches, build output and editor-specific files are excluded from Git.

For the exact submitted runtime behavior, **this README and [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) are authoritative**.

# Interactive Demo

A standalone interactive walkthrough is included in the repository.

It provides a quick way to explore the product concept and engineering architecture without installing Docker, PostgreSQL, Node.js or backend dependencies.

Open:

[`demo/index.html`](demo/index.html)

directly in your browser.

## macOS

From the repository root:

```bash
open demo/index.html
```

## Windows

Open the `demo` folder and double-click:

```text
index.html
```

Alternatively, right-click `index.html` and open it with Chrome, Edge or another browser.

## Important

The interactive demo uses **illustrative data** and is intended only as a guided product walkthrough.

It does **not** replace the actual running application.

The real application uses the committed historical market observations and the complete FastAPI/PostgreSQL/React architecture described above.

To run the actual application:

### macOS / Linux

```bash
./start.sh
```

### Windows using Git Bash

```bash
bash start.sh
```
