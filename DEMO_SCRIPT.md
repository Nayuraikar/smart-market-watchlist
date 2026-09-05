# Submission demo walkthrough

1. Run `SIMULATION_INTERVAL_SECONDS=5 ./start.sh` and open http://localhost:5173.
2. Register/login, create a Growth watchlist, and add RELIANCE, TCS and INFY.
3. Open a stock. Show historical prices, available snapshot fundamentals and the interactive price-history chart. Explain the distinction between source dates and simulation time.
4. Return to the watchlist. Let historical observations advance. A price move of at least 2% creates a ranked event; smaller updates remain visible in the chart. Real source data determines timing—no jumps are manufactured.
5. Switch Growth, Value and Stability. Explain how relevance/ranking changes while the underlying event and comparison boundary remain stable.
6. Log out, allow replay to continue, then log in to demonstrate the persisted visit boundary.

Historical collection is separate: yfinance downloads past data once, stores JSON, and is never used during the running demo. Source gaps and missing fundamentals are explicit. Collection-time fundamentals are not historical daily fundamentals.

Newly added stocks only contribute events after tracking begins. Startup resets market state/history/events and visit boundaries while preserving accounts and watchlists. The periodic worker loops its saved timeline; a worker restart begins at row zero. Fresh refers to simulation timestamps, not live exchange quotes.

See PRODUCT_PITCH.md for the required 100-word pitch and SUBMISSION.md for requirement coverage. README.md contains setup, tests and collection commands.
