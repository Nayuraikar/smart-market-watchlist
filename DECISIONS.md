## Market Data Provider

Originally planned: 0xramm/Indian-Stock-Market-API (http://65.0.104.9/).
Verified unreachable during Phase 2 (connection timeout on both a default
curl and a 5s/10s connect/max-time curl — not a transient blip, the host
did not respond).

Switched to yfinance (direct Python library) as the primary provider.
yfinance pulls from Yahoo Finance under the hood — same underlying data
source the original API was proxying, minus the extra hop.

Trade-off accepted: yfinance is an unofficial, scraping-based library with
no SLA — it can break or get rate-limited without warning. This is exactly
why the ReplayProvider (Phase 5) is not optional polish — it's the
resilience backbone that carries the live demo if yfinance misbehaves
on demo day.

## Fundamentals granularity

Using yfinance quarterly statements (quarterly_income_stmt, etc.) rather than
annual. Annual data only updates once a year, which would make
FUNDAMENTAL_CHANGE detection nearly untestable within the project timeline.
Quarterly gives 4x the data points and is what most retail-facing products
use for "did anything change" comparisons anyway.

## Fundamental snapshot cadence (period_type)

fundamental_snapshots holds both QUARTERLY and ANNUAL rows, distinguished
by period_type, rather than a separate table per cadence. Reasoning:
yfinance's quarterly cash flow coverage is confirmed ticker-dependent, not
universal — RELIANCE.NS and HDFCBANK.NS return an empty quarterly_cashflow
DataFrame; TCS.NS and INFY.NS return real data. A single table with a
cadence flag adapts per-instrument without a schema change; a hardcoded
"FCF is always annual" design would have been wrong for 2 of our 4 sample
tickers.

## Growth calculated YoY, not sequential QoQ

Tested directly on RELIANCE.NS: sequential quarter-over-quarter revenue
growth swung +5.24% / +11.01% / +8.73% / -6.79% across four consecutive
quarters — mostly seasonality, not signal. Same-quarter year-over-year
comparison gave a stable +18.39%. revenue_growth, eps_growth, and
profit_growth are all defined as YoY for this reason.

## ROE / ROCE / interest_coverage use TTM, not single-quarter

Single-quarter ROE (2.32%) is roughly 1/4 the annualized figure (8.93%)
and isn't comparable to the other TTM-scale metrics in the same table
(pe_ratio, ev_ebitda). All three ratios sum the trailing 4 quarters for
the income-statement component before dividing by the period-end balance
sheet figure.

## fcf_yield_basis added

Since FCF cadence differs by instrument, fcf_yield alone can't tell you
whether its numerator is a TTM-quarterly sum or a single annual figure.
fcf_yield_basis (TTM_QUARTERLY / ANNUAL) makes this explicit so
cross-instrument ranking doesn't silently mix definitions.


## Instrument universe remains intentionally scoped

The initial instrument universe is scoped to the NIFTY 50 plus a small
number of additional representative NSE equities rather than the full
NSE/BSE listing.

Broader coverage would require a verified, current, and appropriately
licensed instrument-universe source. No such source was established within
the build window, and universe size is not a product requirement.

Decision: Phase 3.6 seeds the initial 53 instruments only. The architecture
does not assume this is the permanent universe: instruments are stored
independently by canonical provider ticker, so broader coverage can be
added later without a schema change.

Sector and industry metadata are best-effort enrichment and do not block
instrument seeding. yfinance Ticker.info is currently rate-limited by
Yahoo quoteSummary, while market history remains available through the
history endpoint. Metadata failures therefore leave sector/industry NULL
rather than preventing the core instrument universe from being created.

### Phase 5: Ingestion decisions

- PRICE_MOVE events trigger at an absolute price change of >= 2%.
  This threshold is intentionally explicit and is covered by boundary tests.

- ingestion_version is application-derived from observed_at because
  yfinance does not expose a provider-side monotonic sequence number.
  Production providers should use a native provider sequence/event ID
  when available.

- The live yfinance provider returned HTTP 429 during development.
  The system therefore treats yfinance as a best-effort external source,
  preserves the last validated market state on provider failure, and
  does not claim exchange-grade feed reliability.

### Phase 6.6: 52W_HIGH / 52W_LOW window honesty

- "52-week" high/low is measured in trading observations, not calendar
  time. The target window is 252 prior observations, but during this
  build window the system will never accumulate 252 real trading days,
  so a strict 252-observation requirement would make this event type
  permanently dead code — untestable against real behavior and never
  demonstrable live.
- Instead the window is adaptive: window_days_used = min(available prior
  observations, 252), with a floor of 5 prior observations before the
  detector is allowed to fire at all. Every emitted 52W_HIGH/52W_LOW
  event carries details.window_days_used, details.window_target_days
  (always 252), and details.is_full_window (bool) so a partial-history
  "high" is never presented as equivalent to a genuine 52-week high.
- This follows the same disclosure principle as the freshness badges in
  Phase 8 (surface the limitation, don't hide it) applied to window
  size instead of data recency.
- Breakout events are state transitions, not equality checks: a value is
  compared with strict > (HIGH) or < (LOW) against the max/min of the
  prior window, excluding today's own observation. Because today's
  record price enters tomorrow's window, a flat plateau at the new
  high/low never re-fires on its own — no separate "already notified"
  tracking is needed.

### Phase 6.7: scoring metric sourcing decisions

- "Earnings growth" in GROWTH is frozen as FundamentalSnapshot.eps_growth
  (per-share), not profit_growth (total profit) — the two are different
  metrics and the model name was ambiguous until now.
- P/E ratio (VALUE) is sourced from MarketObservation.pe_ratio, a
  cross-table read at the scoring-input-preparation layer. The three
  score functions themselves remain agnostic to source tables — they
  consume only a dict of already-computed percentiles.
- FCF yield (VALUE) is not a stored column anywhere. It is derived as
  free_cash_flow / market_cap in the scoring-input-prep layer, joining
  FundamentalSnapshot and MarketObservation, before being fed into the
  percentile step alongside every other metric.
- P/B ratio (VALUE) is permanently unavailable, not approximated. Book
  equity is not directly stored; FundamentalSnapshot.roe is an
  already-computed profit/equity ratio, and back-deriving equity from
  it would combine two lossy numbers on a possibly-inconsistent equity
  basis. Rather than invent that proxy, P/B is treated as a missing
  metric for every instrument, every time, and renormalizes away under
  the existing >=60% coverage rule exactly like any other missing value.
- Earnings volatility (STABILITY) is deferred. It is not a snapshot
  column but a statistic (e.g. rolling stddev of eps or profit_growth
  across historical FundamentalSnapshot rows for one instrument), and
  no such time-series methodology has been defined or built yet. It is
  always treated as missing for now. STABILITY therefore always scores
  off Debt/Equity + ROE alone (40+30 = 70% of total weight, renormalized
  to 100%), which stays above the 60% floor without changing the frozen
  weights.
- No migration was added solely to colocate scoring metrics onto one
  table. Cross-table joins happen once, at the scoring-input-prep step,
  which already has to touch both tables per instrument to compute
  percentiles anyway.
