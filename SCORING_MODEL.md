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
| Metric      | Weight | Direction    |
|--------------|--------|--------------|
| P/E ratio     | 40%    | Lower better |
| P/B ratio     | 30%    | Lower better |
| FCF yield     | 30%    | Higher better|

## STABILITY
| Metric               | Weight | Direction     |
|------------------------|--------|---------------|
| Debt/Equity             | 40%    | Lower better  |
| ROE                      | 30%    | Higher better |
| Earnings volatility      | 30%    | Lower better  |

## Missing data handling
- All required metrics present → full weighted score
- Some metrics missing, remaining coverage sufficient (>= 60% of total
  weight, TBD exact threshold — confirm before 6.7) → renormalize
  remaining weights to sum to 100%, compute score on those alone
- Coverage below threshold → return INSUFFICIENT_DATA, never a
  fabricated or partial-looking numeric score

## Percentile normalization
Each metric is percentile-normalized against the seeded instrument
universe before weighting, not used as a raw value — this is what
makes GROWTH/VALUE/STABILITY scores comparable to each other and
stable as new instruments are seeded.
