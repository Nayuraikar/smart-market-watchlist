# Product Spec — Smart Market Watchlist

## Product Thesis

A watchlist that tells users what changed since their last visit, why it matters,
and what deserves attention now.

This is not intended to be a trading terminal or a buy/sell recommendation system.
The product reduces the noise of raw market data by detecting meaningful changes,
ranking them according to the user's chosen objective, and explaining why each
change matters.

---

## Problem

Investors who check the market occasionally, rather than continuously, have no
fast way to understand what actually changed across the stocks they follow.

A traditional watchlist shows the current price and percentage change, but it
does not answer:

- What changed since I last looked?
- Which changes are actually meaningful?
- Which stocks deserve my attention?
- Did the stock move because of an unusual event or simply move with the market?
- Why should this change matter to me?

Users either scroll through noisy price feeds or manually compare today's market
with what they remember from their previous visit.

---

## User

The primary user is a retail investor who checks the market a few times a week,
rather than monitoring it continuously throughout the trading day.

The user wants:

- A quick summary when they return
- Meaningful changes instead of every small price movement
- Context around why a change matters
- The ability to organize stocks into watchlists
- The ability to choose what matters to them through an objective

The user does not need a full professional trading terminal.

---

## Core Workflow

1. User creates an account.
2. User creates a watchlist.
3. User selects an objective:
   - GROWTH
   - VALUE
   - STABILITY
4. User searches for and adds stocks to the watchlist.
5. The system records the current market state and establishes a baseline.
6. The user leaves the application.
7. Market data changes while the user is away.
8. The backend continuously or periodically updates market state.
9. The system detects meaningful changes.
10. The system determines how relevant each change is to the watchlist's
    selected objective.
11. The system assigns an attention level:
    - HIGH
    - MEDIUM
    - LOW
12. When the user returns, the dashboard shows changes since their previous
    successful visit.
13. The user can open a stock to see the current data, detected changes, and
    explanation.
14. After the watchlist is successfully viewed, the system updates
    `last_viewed_at`.

---

## Definition of "Meaningful Change"

A market change is meaningful when it crosses an explicit threshold or represents
a discrete market event.

The system will detect the following:

### 1. Price Move

A price movement is meaningful when the absolute price change is at least:

**5%**

The percentage change is calculated as:

    ((current_price - baseline_price) / abs(baseline_price)) * 100

Example:

    Baseline price = ₹100
    Current price = ₹106

    Change = +6%

This qualifies as a meaningful price change.

A movement of +1% does not qualify on its own.

---

### 2. Volume Surge

A volume change is meaningful when:

**RVOL >= 2.0x**

RVOL means Relative Volume:

    RVOL = current_volume / average_20_day_volume

Example:

    Current volume = 2,000,000
    Average 20-day volume = 1,000,000

    RVOL = 2.0x

This qualifies as a meaningful volume surge.

---

### 3. 52-Week High or Low

A change is meaningful when the current price establishes a new:

- 52-week high
- 52-week low

This is treated as a discrete event rather than a percentage threshold.

---

### 4. Relative Performance

A stock's movement is meaningful when its performance differs from the selected
benchmark by at least:

**3 percentage points**

The default benchmark is NIFTY 50.

Relative performance is calculated as:

    stock_return - benchmark_return

Example:

    Stock return = +7%
    NIFTY 50 return = +2%

    Relative performance = +5 percentage points

This qualifies as meaningful outperformance.

The same logic applies to meaningful underperformance.

---

### 5. Fundamental Change

A fundamental change is meaningful when an available fundamental metric changes
by at least:

**10% relative to its previous reported value**

Examples include:

- Revenue
- EPS
- Profit
- ROE
- ROCE
- Debt-to-equity

For growth-rate metrics that can cross zero, percentage-point change is used
instead of percentage-of-percentage change.

If the required previous value does not exist, the system does not fabricate a
change.

---

### 6. Corporate and Earnings Events

The following are always treated as meaningful discrete events:

- Earnings
- Dividend
- Stock split
- Bonus issue
- Buyback
- Rights issue
- Other supported corporate actions

These events do not require a percentage threshold.

---

## Definition of Attention

Meaningful changes are ranked into three attention levels.

### HIGH

A change receives HIGH attention when:

- It is a 52-week high or low, OR
- An earnings or corporate-action event occurred, OR
- The stock crosses at least two meaningful-change conditions, OR
- A major meaningful change is strongly relevant to the selected objective.

Examples:

- Price +8% AND RVOL 2.5x
- Price +6% AND new 52-week high
- Earnings event with a significant fundamental change
- Major debt change for a STABILITY watchlist

---

### MEDIUM

A change receives MEDIUM attention when:

- Exactly one clear meaningful threshold is crossed, or
- A meaningful change is relevant to the objective but does not meet HIGH
  attention criteria.

Example:

    Reliance
    +5.8% price movement

This is meaningful, but by itself does not necessarily require HIGH attention.

---

### LOW

A change receives LOW attention when:

- The value is close to a meaningful threshold but has not crossed it, or
- The change is meaningful but has relatively low relevance to the selected
  objective.

LOW changes may be displayed as secondary information rather than being placed
at the top of the dashboard.

---

## Objective System

Each watchlist has exactly one objective.

The available objectives are:

### GROWTH

Prioritizes:

- Revenue growth
- Earnings/EPS growth
- Profit growth
- ROCE
- FCF growth

### VALUE

Prioritizes:

- P/E
- P/B
- EV/EBITDA
- Free-cash-flow yield
- Dividend yield

### STABILITY

Prioritizes:

- Debt-to-equity
- Interest coverage
- ROE
- ROCE
- Earnings consistency
- Free-cash-flow consistency

The objective changes the ranking and explanation of detected changes.

It does not generate buy/sell recommendations.

---

## Non-Goals

The first version will NOT include:

- Trading or order execution
- Buy/sell advice
- Personalized investment recommendations
- Portfolio management
- Positions
- P&L tracking
- Cost basis
- Social features
- Comments
- Following other users
- A full technical-analysis suite
- Candlestick charting
- A large indicator library
- Options trading
- Futures trading
- Intraday trading tools
- Complex multi-source market-data consensus
- AI-generated investment advice

---

## Locked Objective Set

The objective set is locked to:

- GROWTH
- VALUE
- STABILITY

A fourth objective will not be introduced during the initial build.

---

## Locked Event Types

The system supports:

- PRICE_MOVE
- VOLUME_SURGE
- 52W_HIGH
- 52W_LOW
- RELATIVE_OUTPERFORMANCE
- FUNDAMENTAL_CHANGE
- CORPORATE_ACTION
- EARNINGS
- OTHER

---

## Last-Visit Behavior

The system tracks `last_viewed_at` for each watchlist.

`last_viewed_at` represents the beginning of the user's previous successful
watchlist viewing session.

When the user opens a watchlist:

1. The backend retrieves changes detected after `last_viewed_at`.
2. The backend returns the ranked meaningful changes.
3. The frontend renders the watchlist successfully.
4. The frontend confirms the viewing session.
5. The backend updates `last_viewed_at`.

The last-visit state belongs to the user's account/watchlist and is therefore
device-independent.

A user can view the same watchlist on a laptop and later on a mobile device.

---

## First Visit

If `last_viewed_at` is NULL, the user has no previous viewing baseline.

The system displays:

"Baseline established today. Future meaningful changes will appear here."

The first observation is not treated as a change.

---

## Newly Added Stocks

When a stock is newly added to a watchlist, it is marked as:

"Tracking started today."

The system does not pretend that the user was tracking that stock before it
was added.

---

## Data Freshness

Every market observation contains an observation timestamp.

Market data is classified as:

- FRESH
- STALE
- UNAVAILABLE

Stale data must be clearly indicated to the user.

If the external market-data provider becomes unavailable, the system preserves
the last verified market state rather than replacing it with invalid or empty
data.

---

## Invalid Market Data

The system must reject invalid market observations.

Examples:

- Price <= 0
- Negative volume
- Unknown instrument
- Invalid timestamp
- Out-of-order observation
- Missing required fields

Invalid observations must never overwrite the last valid market state.

---

## Missing Data

Missing fundamental or valuation data is not treated as zero.

If insufficient data exists to calculate an objective score, the system reports:

`INSUFFICIENT_DATA`

rather than producing a misleading score.

The UI may show data coverage such as:

- Market data: Available
- Fundamentals: Partial
- Valuation: Available
- Corporate events: Unavailable

---

## Explainability

Every high- or medium-attention change should explain why it was surfaced.

Example:

"Reliance moved +8.1%, traded at 2.4x its normal volume, and reached a new
52-week high."

The system explains observed market behavior.

It does not tell the user what action to take.

---

## Scalability Principle

Market data is shared application state, while watchlists are user-specific state.

The system should fetch and validate market data centrally rather than making
one external API request per user.

One validated market observation should be reusable across many users and
watchlists.

---

## Product Success Criteria

The product succeeds if a returning user can answer these questions quickly:

1. What changed since I last looked?
2. Which changes matter most?
3. Why do they matter?
4. Is the underlying market data fresh?
5. What happened to each stock I care about?

The product should provide this information without requiring the user to
manually compare historical values.