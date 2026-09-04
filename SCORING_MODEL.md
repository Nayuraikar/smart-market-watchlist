# Scoring Model

Authoritative source for GROWTH/VALUE/STABILITY scoring. Code must match
this document, not the other way around — if a weight changes, update
here first, then the implementation, then the tests.

## GROWTH
| Metric           | Weight | Direction     |
|-------------------|--------|---------------|
| Revenue growth     | 40%    | Higher better |
| Earnings growth    | 40%    | Higher better |
| ROCE                | 20%    | Higher better |

## VALUE
| Metric      | Weight | Direction    | Source |
|--------------|--------|--------------|--------|
| P/E ratio     | 40%    | Lower better | MarketObservation.pe_ratio (market-state, not fundamentals) |
| P/B ratio     | 30%    | Lower better | UNAVAILABLE — see note below. Always treated as missing. |
| FCF yield     | 30%    | Higher better| Derived: FundamentalSnapshot.free_cash_flow / MarketObservation.market_cap, computed in the scoring-input prep layer, not stored |

P/B ratio note: computing it would require book equity, which is not
directly stored. FundamentalSnapshot.roe is profit/equity as an
already-computed ratio, not the underlying equity figure, and
back-deriving equity = profit/roe would combine two lossy numbers on
a possibly-inconsistent equity basis (average vs period-end). That is
an invented proxy, not genuinely available data, so P/B is scored as
missing for every instrument rather than approximated. It renormalizes
away under the existing 60% coverage rule like any other missing metric.

## STABILITY
| Metric               | Weight | Direction     | Source |
|------------------------|--------|---------------|--------|
| Debt/Equity             | 40%    | Lower better  | FundamentalSnapshot.debt_to_equity |
| ROE                      | 30%    | Higher better | FundamentalSnapshot.roe |
| Earnings volatility      | 30%    | Lower better  | DEFERRED — no time-series methodology defined yet. Always treated as missing. |

Earnings growth (GROWTH table above) is frozen as FundamentalSnapshot.eps_growth,
not profit_growth — per-share earnings growth, not total profit growth.

## Missing data handling
- All required metrics present → full weighted score
- Some metrics missing, remaining coverage sufficient (>= 60% of total
  weight — CONFIRMED, this is the final threshold) → renormalize
  remaining weights to sum to 100%, compute score on those alone
- Coverage below 60% of total weight → return INSUFFICIENT_DATA, never a
  fabricated or partial-looking numeric score

## Percentile normalization
Each metric is percentile-normalized against the seeded instrument
universe before weighting, not used as a raw value — this is what
makes GROWTH/VALUE/STABILITY scores comparable to each other and
stable as new instruments are seeded.
