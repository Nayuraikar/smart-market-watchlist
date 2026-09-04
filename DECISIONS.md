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

