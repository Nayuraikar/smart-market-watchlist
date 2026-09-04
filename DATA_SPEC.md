
---

# 3. DATA_SPEC.md

This one looks scary, but it's basically:

> **"What boxes are we putting into our database?"**

We're going to make this concrete.

Put this into `DATA_SPEC.md`:

```markdown
# Data Spec

This document defines the persistent data model for the Smart Market
Watchlist.

PostgreSQL is the canonical application database.

---

# users

Stores authenticated application users.

| field | type | nullable | constraints | meaning | source |
|---|---|---|---|---|---|
| id | UUID | no | PRIMARY KEY | unique user identifier | generated |
| email | VARCHAR(255) | no | UNIQUE | login identifier | user input |
| password_hash | VARCHAR(255) | no | | securely hashed password | derived |
| created_at | TIMESTAMPTZ | no | | account creation time | generated |
| updated_at | TIMESTAMPTZ | no | | last account update | generated |

---

# watchlists

Stores user-created watchlists.

| field | type | nullable | constraints | meaning | source |
|---|---|---|---|---|---|
| id | UUID | no | PRIMARY KEY | unique watchlist identifier | generated |
| user_id | UUID | no | FK → users.id | owner of watchlist | app |
| name | VARCHAR(100) | no | | display name | user input |
| objective | VARCHAR(20) | no | CHECK | GROWTH, VALUE, or STABILITY | user input |
| last_viewed_at | TIMESTAMPTZ | yes | | previous successful viewing boundary | app |
| created_at | TIMESTAMPTZ | no | | creation time | generated |
| updated_at | TIMESTAMPTZ | no | | last modification time | generated |

Constraints:

- `user_id` must reference an existing user.
- `objective` must be one of GROWTH, VALUE, STABILITY.
- `last_viewed_at` is NULL until the watchlist is viewed successfully.

Indexes:

- `(user_id)`

---

# instruments

Stores securities known to the application.

The instrument table is independent of user watchlists so that the same
instrument can be referenced by many users.

| field | type | nullable | constraints | meaning | source |
|---|---|---|---|---|---|
| id | UUID | no | PRIMARY KEY | internal instrument identifier | generated |
| ticker | VARCHAR(30) | no | UNIQUE | market ticker such as RELIANCE | provider |
| name | VARCHAR(255) | no | | company name | provider |
| exchange | VARCHAR(20) | no | | NSE/BSE | provider |
| instrument_type | VARCHAR(20) | no | | EQUITY initially; future-compatible | provider |
| sector | VARCHAR(100) | yes | | company sector | provider |
| industry | VARCHAR(150) | yes | | company industry | provider |
| isin | VARCHAR(20) | yes | UNIQUE where present | security identifier | provider |
| active | BOOLEAN | no | | whether instrument is currently active | app/provider |
| created_at | TIMESTAMPTZ | no | | record creation | generated |
| updated_at | TIMESTAMPTZ | no | | last metadata update | generated |

The initial product focuses on equities.

The schema remains extensible for other instrument types without requiring
them in the first version.

---

# watchlist_items

Many-to-many relationship between users' watchlists and instruments.

A stock can appear in many users' watchlists.

A watchlist can contain many stocks.

| field | type | nullable | constraints | meaning | source |
|---|---|---|---|---|---|
| watchlist_id | UUID | no | FK → watchlists.id, composite PK | parent watchlist | app |
| instrument_id | UUID | no | FK → instruments.id, composite PK | tracked instrument | app |
| added_at | TIMESTAMPTZ | no | | when tracking began | generated |

Primary key:

    (watchlist_id, instrument_id)

This prevents the same stock from being added to the same watchlist twice.

Indexes:

- `(watchlist_id)`
- `(instrument_id)`

---

# market_state

Stores the latest validated market observation for each instrument.

This table represents the current known state.

| field | type | nullable | constraints | meaning | source |
|---|---|---|---|---|---|
| instrument_id | UUID | no | PRIMARY KEY, FK | instrument | app |
| price | NUMERIC(18,4) | no | CHECK > 0 | latest known price | provider |
| previous_close | NUMERIC(18,4) | yes | CHECK >= 0 | previous market close | provider |
| volume | NUMERIC(24,4) | no | CHECK >= 0 | latest known volume | provider |
| market_cap | NUMERIC(24,4) | yes | | latest known market capitalization | provider |
| pe_ratio | NUMERIC(12,4) | yes | | latest P/E if available | provider |
| dividend_yield | NUMERIC(12,4) | yes | | latest dividend yield if available | provider |
| observed_at | TIMESTAMPTZ | no | | time represented by observation | provider |
| received_at | TIMESTAMPTZ | no | | time application received data | generated |
| sequence | BIGINT | no | | ordering/version for observations | provider/app |
| data_quality | VARCHAR(20) | no | | FRESH/STALE/UNAVAILABLE | app |
| source | VARCHAR(100) | no | | provider identifier | app |

Important rule:

The application must never overwrite a valid market state with an invalid
observation.

---

# market_history

Stores historical market observations used for change detection and
technical calculations.

| field | type | nullable | constraints | meaning | source |
|---|---|---|---|---|---|
| id | BIGSERIAL | no | PRIMARY KEY | history row | generated |
| instrument_id | UUID | no | FK → instruments.id | instrument | app |
| price | NUMERIC(18,4) | no | CHECK > 0 | historical price | provider |
| volume | NUMERIC(24,4) | no | CHECK >= 0 | historical volume | provider |
| timestamp | TIMESTAMPTZ | no | | observation time | provider |

Indexes:

    (instrument_id, timestamp)

This supports historical lookups such as:

- Previous price
- 20-day average volume
- 52-week high
- 52-week low
- Historical returns

---

# fundamental_snapshots

Stores fundamental metrics that change less frequently than market prices.

| field | type | nullable | meaning | source |
|---|---|---|---|---|
| id | BIGSERIAL | no | snapshot identifier | generated |
| instrument_id | UUID | no | related instrument | app |
| period | VARCHAR(30) | no | reporting period | provider |
| revenue | NUMERIC(24,4) | yes | reported revenue | provider |
| revenue_growth | NUMERIC(12,4) | yes | revenue growth | provider/derived |
| eps | NUMERIC(18,6) | yes | earnings per share | provider |
| eps_growth | NUMERIC(12,4) | yes | EPS growth | provider/derived |
| profit | NUMERIC(24,4) | yes | reported profit | provider |
| profit_growth | NUMERIC(12,4) | yes | profit growth | provider/derived |
| roe | NUMERIC(12,4) | yes | return on equity | provider/derived |
| roce | NUMERIC(12,4) | yes | return on capital employed | provider/derived |
| debt_to_equity | NUMERIC(12,4) | yes | leverage ratio | provider/derived |
| interest_coverage | NUMERIC(12,4) | yes | ability to cover interest | provider/derived |
| free_cash_flow | NUMERIC(24,4) | yes | free cash flow | provider/derived |
| snapshot_at | TIMESTAMPTZ | no | snapshot timestamp | provider/app |

Fundamental values may be NULL because not every source provides every
metric for every instrument.

NULL means "unknown/unavailable", not zero.

Indexes:

    (instrument_id, snapshot_at)

---

# valuation_snapshots

Stores valuation metrics used primarily by the VALUE objective.

| field | type | nullable | meaning | source |
|---|---|---|---|---|
| id | BIGSERIAL | no | snapshot identifier | generated |
| instrument_id | UUID | no | related instrument | app |
| pe_ratio | NUMERIC(12,4) | yes | price-to-earnings ratio | provider/derived |
| pb_ratio | NUMERIC(12,4) | yes | price-to-book ratio | provider/derived |
| ev_ebitda | NUMERIC(18,4) | yes | enterprise value / EBITDA | provider/derived |
| price_to_sales | NUMERIC(12,4) | yes | price-to-sales ratio | provider/derived |
| fcf_yield | NUMERIC(12,4) | yes | free-cash-flow yield | provider/derived |
| dividend_yield | NUMERIC(12,4) | yes | dividend yield | provider |
| observed_at | TIMESTAMPTZ | no | valuation observation time | provider/app |

Indexes:

    (instrument_id, observed_at)

---

# corporate_actions

Stores discrete corporate events.

| field | type | nullable | meaning | source |
|---|---|---|---|---|
| id | BIGSERIAL | no | event identifier | generated |
| instrument_id | UUID | no | affected instrument | app |
| action_type | VARCHAR(30) | no | DIVIDEND, BONUS, SPLIT, BUYBACK, RIGHTS, etc. | provider |
| announcement_date | TIMESTAMPTZ | yes | announcement time | provider |
| ex_date | TIMESTAMPTZ | yes | ex-date if applicable | provider |
| record_date | TIMESTAMPTZ | yes | record date if applicable | provider |
| value | NUMERIC(18,6) | yes | action value where applicable | provider |
| source | VARCHAR(100) | no | source identifier | provider |

---

# market_events

Stores discrete market events surfaced by the application.

| field | type | nullable | constraints | meaning | source |
|---|---|---|---|---|---|
| id | BIGSERIAL | no | PRIMARY KEY | event identifier | generated |
| instrument_id | UUID | no | FK → instruments.id | affected instrument | app |
| event_type | VARCHAR(40) | no | CHECK | locked event type | app |
| importance | VARCHAR(10) | no | CHECK | HIGH/MEDIUM/LOW | app |
| timestamp | TIMESTAMPTZ | no | | event detection/event time | app |
| title | VARCHAR(255) | no | | short event title | app |
| details | JSONB | yes | | structured event information | app |
| source | VARCHAR(100) | yes | | originating source | provider/app |

Allowed event types:

- PRICE_MOVE
- VOLUME_SURGE
- 52W_HIGH
- 52W_LOW
- RELATIVE_OUTPERFORMANCE
- FUNDAMENTAL_CHANGE
- CORPORATE_ACTION
- EARNINGS
- OTHER

Allowed importance levels:

- HIGH
- MEDIUM
- LOW

Indexes:

- `(instrument_id, timestamp)`
- `(event_type, timestamp)`

---

# change_events

Stores product-specific changes detected for a watchlist.

This is different from raw market data.

A raw market observation answers:

"What is the market doing?"

A change event answers:

"What changed for this user's watchlist?"

| field | type | nullable | meaning | source |
|---|---|---|---|---|
| id | BIGSERIAL | no | unique change-event identifier | generated |
| watchlist_id | UUID | no | affected watchlist | app |
| instrument_id | UUID | no | affected instrument | app |
| event_type | VARCHAR(40) | no | type of detected change | app |
| detected_at | TIMESTAMPTZ | no | when application detected change | generated |
| previous_value | NUMERIC(24,8) | yes | previous relevant value | derived |
| current_value | NUMERIC(24,8) | yes | current relevant value | derived |
| delta | NUMERIC(24,8) | yes | change magnitude | derived |
| importance | VARCHAR(10) | no | HIGH/MEDIUM/LOW | app |
| attention_level | VARCHAR(10) | no | HIGH/MEDIUM/LOW | app |
| reason | TEXT | no | human-readable explanation | app |
| baseline_timestamp | TIMESTAMPTZ | yes | comparison boundary | app |

Indexes:

- `(watchlist_id, detected_at)`
- `(instrument_id, detected_at)`

---

# Relationships

    users
      │
      │ 1:N
      ▼
    watchlists
      │
      │ 1:N
      ▼
    watchlist_items
      │
      │ N:1
      ▼
    instruments
      │
      ├──────── market_state
      │
      ├──────── market_history
      │
      ├──────── fundamental_snapshots
      │
      ├──────── valuation_snapshots
      │
      ├──────── corporate_actions
      │
      ├──────── market_events
      │
      └──────── change_events

---

# Data Integrity Rules

The database and application must enforce the following rules:

1. A watchlist must belong to an existing user.
2. A watchlist item must reference an existing watchlist.
3. A watchlist item must reference an existing instrument.
4. The same instrument cannot appear twice in one watchlist.
5. Market price must be greater than zero.
6. Volume cannot be negative.
7. Required timestamps must be timezone-aware.
8. Invalid market observations must not replace valid state.
9. Missing fundamental data must remain NULL rather than becoming zero.
10. Users may only access their own watchlists.
11. Event types must come from the locked event list.
12. Attention levels must be HIGH, MEDIUM, or LOW.

---

# Device Independence

User state is stored server-side.

No watchlist, change history, or authentication state required by the product
is stored only on the user's laptop or phone.

Therefore:

    Laptop ─┐
            │
    Phone ──┼──> FastAPI ──> PostgreSQL
            │
    Tablet ─┘

All devices retrieve the same account state from the backend.