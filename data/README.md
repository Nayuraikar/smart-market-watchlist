# Market data provenance

## Active dataset: genuine historical prices

`historical_baseline_57.json` and `historical_update_57.json` are the only default runtime inputs. `backend/scripts/collect_historical_data.py` uses yfinance once to download a completed date range and save the result. It never runs during application startup or periodic ingestion.

The collector uses adjusted daily closing prices, observed volume, and the previous adjusted observation as previous close. Dates and prices remain genuine source data in JSON. Runtime substitutes simulation timestamps so historical observations can be played through normal freshness and change detection. The saved update sequence repeats; wraparound can itself produce a replay event.

`historical_manifest.json` records collection time, requested range, coverage per ticker, price basis and any tickers retained from earlier captures after failed downloads. No synthetic observations are inserted to fill gaps.

## Fundamentals

With `--snapshots`, the collector also saves market cap, trailing P/E and dividend yield where the provider supplies them. These are **collection-time snapshots**, not fundamentals from each historical price date. Missing source fields stay null. The UI retains every metric card and identifies absent fields honestly.

Numeric values are stored as strings. Price and market cap are INR; volume is shares; P/E is a multiple; dividend yield is percentage points (0.46 means 0.46%).

## Offline replay and chart

The worker reads saved JSON, advances one observation per stock per tick, and loops at the end. No API or yfinance dependency is required at runtime. The chart reads the newest 180 accepted database observations, chronologically ordered and equally spaced by observation. Available history length depends on each ticker's coverage.

## Preserved alternative fixtures

`demo_*.json`, synthetic financial assumptions in `demo_catalog.json`, and `scripts/generate_demo_data.py` are retained as explicitly synthetic alternatives for reproducible tests. They are not the active feed. The catalog is used only for names/sectors during seeding. Older `yf_*` and `replay_*` files remain local fixtures.
