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

