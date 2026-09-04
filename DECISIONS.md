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

### Phase 6.7 correction round (pre-commit review caught these before merge)

- Percentile convention was initially implemented ad hoc (midrank over
  n, max value -> ~83.3 not 100) before being frozen in SCORING_MODEL.md.
  Corrected to an endpoint-anchored rank formula (100 x (avg_rank-1)/(n-1))
  so the observed lowest/highest map to exactly 0/100, matching what a
  "0-100 score" should mean to someone reading the UI. Frozen in
  SCORING_MODEL.md BEFORE the implementation was corrected, not after.
- compute_fcf_yield() initially returned a raw ratio (0.1 for a 10%
  yield). Corrected to return a percentage (x100) to stay consistent
  with every other percentage-style metric in the system
  (revenue_growth, eps_growth, price-move pct_change, etc).
- RELATIVE_OUTPERFORMANCE (event type, frozen since Phase 1/6.4) is
  intentionally bidirectional: a negative delta means underperformance,
  not a data error and not a naming bug. The event type name is frozen
  and is not being split into separate OUTPERFORMANCE/UNDERPERFORMANCE
  types. `reason` already disambiguates direction per-event
  (relative_outperform_Xpp vs relative_underperform_Xpp) and `delta`'s
  sign is the authoritative signal for any caller.
- Score functions now validate that every provided percentile lies in
  [0, 100] and raise ValueError otherwise. An out-of-range percentile
  indicates a caller/data-contract bug upstream (e.g. percentile
  computation itself broken, or a raw value passed in where a
  percentile was expected) — it is not the same class of problem as a
  genuinely missing metric, so it must not be silently treated as
  INSUFFICIENT_DATA.

### Phase 6.8: Relevance/attention spec — Decision 1 (FUNDAMENTAL_CHANGE sub-typing)

FUNDAMENTAL_CHANGE remains a single locked event_type in EVENT_TYPES — not expanded into
per-metric subtypes. Which fundamental metric changed is carried in ChangeEvent.details,
which for this event_type must contain "metric" (str), "metric_family" (one of "growth" /
"value" / "stability"), "previous", "current", "delta" (all numeric | None). "metric" and
"metric_family" are mandatory and a missing or invalid value raises rather than defaulting.
delta_pct is deliberately not required — delta units are metric-specific (percentage-point
for growth-rate metrics, to handle zero-crossings correctly; plain numeric for ratio metrics).
Relevance lookup for this event_type is two-step: event_type -> details["metric_family"] ->
objective, not a flat event_type -> objective lookup like the other event types. Binds any
future FUNDAMENTAL_CHANGE detector to populate these fields from the start. See
RELEVANCE_ATTENTION_SPEC.md section 2b for the full frozen contract.

### Phase 6.8: Relevance/attention spec — Decision 2 (CORPORATE_ACTION sub-typing)

CORPORATE_ACTION remains a single locked event_type in EVENT_TYPES. Sub-typing lives in
ChangeEvent.details via two mandatory fields: "economic_effect" (one of
shareholder_friendly / shareholder_dilutive / cosmetic / structural — drives relevance
scoring) and "action_type" (free-text, e.g. "buyback", "stock_split" — used only for
human-facing explanations/UI, not for scoring). Missing or invalid values in either field
raise rather than defaulting. Relevance lookup is event_type -> details["economic_effect"]
-> objective, mirroring the pattern frozen for FUNDAMENTAL_CHANGE in Decision 1.

structural (merger/acquisition) is deliberately NOT assigned a relevance row or run through
the composite_score formula at this time — a merger isn't mechanically comparable to a
dividend or split, and forcing it through magnitude x relevance x confidence would produce
a number with false precision. It should surface to the user via a raw event log without a
scored attention_tier until dedicated handling is designed against real detector inputs.
See RELEVANCE_ATTENTION_SPEC.md section 2c for the full frozen contract.

### Phase 6.8: Relevance/attention spec — Decision 3 (PRICE_MOVE directionality)

PRICE_MOVE relevance is direction-dependent for STABILITY only: downward moves score HIGH,
upward moves score MEDIUM. GROWTH and VALUE remain direction-agnostic at MEDIUM regardless
of sign. Rationale: downside risk and upside movement are not symmetric for a stability
objective (standard in finance — max drawdown, downside deviation, Sortino ratio all exist
for this reason), whereas extending asymmetry to GROWTH/VALUE would duplicate signal already
carried more precisely by 52W_HIGH/52W_LOW and RELATIVE_OUTPERFORMANCE.

Direction is read exclusively from the numeric sign of ChangeEvent.delta. The relevance/
attention engine must never parse or depend on the human-readable "reason" string for this —
reason is for display only, delta is the sole authoritative source, and the two must not be
allowed to silently drift apart. The existing 2.0% PRICE_MOVE_THRESHOLD_PCT firing threshold
is unchanged; this decision affects only the relevance lookup, not detection, so no changes
to change_detection.py are required.

This is the only direction-sensitive relevance rule in the spec. No other event type gains
direction-dependent relevance without its own separate, explicitly approved decision.
See RELEVANCE_ATTENTION_SPEC.md section 2d for the full frozen contract.

### Phase 6.8: Relevance/attention spec — Decision 4 (52W_HIGH/52W_LOW magnitude)

The earlier proposal to score 52W_HIGH/52W_LOW magnitude via a continuous formula
(magnitude_normalized = clamp(0.4 + 0.6 * pct_beyond_prior_extreme / 5.0, 0.4, 1.0)) is
REJECTED on review as false precision. detect_52w_high/detect_52w_low have no firing
threshold by design — any breakout at all fires — and the formula's "5%" ceiling was an
invented round number with no grounding, producing a five-decimal composite_score that
implied a measurement that was never actually made.

52W_HIGH/52W_LOW magnitude is instead categorical, keyed off the detector's own
is_full_window flag (already present in ChangeEvent.details, already meaningful by the
detector's own design — it reflects how much trailing history backs the "52-week" claim):
is_full_window == True -> magnitude_normalized = 1.0; is_full_window == False -> 0.7. The
0.7 discount is explicitly labeled as a flat, undereived choice, not a computed value.

The real breakout size (prior_max/prior_min, current_price) remains in details and continues
to feed the human-facing explanation text — it is simply excluded from composite_score.
Scoring and explanation are treated as separate consumers of the same event.

See RELEVANCE_ATTENTION_SPEC.md section 3a for the full frozen treatment.

### Phase 6.8: Relevance/attention spec — Decision 5 (multiple simultaneous events)

Multiple events firing on one instrument at the same observation (e.g. PRICE_MOVE + 52W_HIGH,
explicitly possible per detect_change()'s own docstring) combine via max-of-independent-scores,
never summed. This structurally cannot double-count: max() of two numbers is definitionally
not their sum, so no co-occurrence bonus is applied. The event producing the max composite_score
becomes the instrument's "top event tag"; all other concurrent events remain fully retrievable
on drill-in.

Ties in composite_score resolve via a fully deterministic chain: composite_score ->
relevance_weight -> magnitude_normalized -> EVENT_TYPE_PRIORITY. EVENT_TYPE_PRIORITY is a new,
explicitly-frozen ordering (52W_HIGH, 52W_LOW, RELATIVE_OUTPERFORMANCE, EARNINGS,
FUNDAMENTAL_CHANGE, CORPORATE_ACTION, VOLUME_SURGE, PRICE_MOVE, OTHER) — deliberately separate
from EVENT_TYPES' declaration order in change_event.py, which exists only for enum readability
and was never meant to carry tie-break semantics. Rationale: events with built-in historical/
comparative context (52W breakouts, relative-benchmark divergence) rank above single-observation
signals (PRICE_MOVE, VOLUME_SURGE); this is stated as a reasonable default, not a derived fact.

Whether/how to phrase correlated co-fired events as one combined explanation narrative (vs.
separate blocks that could read as "two independent reasons") is explicitly deferred to
Decision 7, since it depends on the explanation contract's actual field structure, not yet
frozen. See RELEVANCE_ATTENTION_SPEC.md section 5/5a/5b/5c for the full frozen contract.

### Phase 6.8: Relevance/attention spec — Decision 6 (stale/unavailable data -> confidence)

The originally-drafted 4-tier confidence scheme (1.0/0.6/0.3/0.0 with a "5x stale threshold"
grace-window boundary) is rejected — the "5x" multiplier was an ungrounded round number, the
same category of false precision already rejected for 52W_HIGH/52W_LOW magnitude in Decision 4.

FRESH / STALE / UNAVAILABLE are now the canonical data-quality states, used by both the
scoring layer and the explanation layer (section 7). data_confidence is a separate, derived
scoring input computed from that state, not the state itself: FRESH -> 1.0, STALE -> 0.5,
UNAVAILABLE -> 0.0 (event suppressed entirely — no composite_score or attention_tier is
computed). The 0.5 value for STALE is explicitly a product-policy discount that halves a
stale event's contribution to scoring — it is not a statistically derived confidence figure
and must never be surfaced to the user as "50% confidence" or similar framing.

Explanation-layer requirement (binding on the not-yet-designed Decision 7 explanation
contract): FRESH events are stated normally; STALE events must explicitly disclose that the
underlying market data is stale/last-known, in plain language, not as a percentage; UNAVAILABLE
data must not generate an attention explanation at all — it should surface a data-status
message instead. See RELEVANCE_ATTENTION_SPEC.md section 6/6a/6b for the full frozen contract.

### Phase 6.8: Relevance/attention spec — Decision 7 (explanation contract, FINAL)

The explanation contract is frozen at 8 fields: what_happened, magnitude,
benchmark_comparison (populated ONLY for RELATIVE_OUTPERFORMANCE - PRICE_MOVE and all
other event types always return null; kept separate from magnitude, not merged), objective_relevance,
data_status, data_confidence, attention_tier, composite_score.

data_status is a structured object { state: FRESH|STALE|UNAVAILABLE, message: string|null },
distinct from data_confidence (the internal-only numeric 1.0/0.5/0.0 from Decision 6).
data_confidence must never be rendered to the user or exposed as a percentage; data_status
carries the entire user-facing trust signal. FRESH allows message: null. STALE requires a
plain-language stale/last-known disclosure. UNAVAILABLE requires a data-status message and
explicitly produces no scored explanation at all — no what_happened, objective_relevance,
attention_tier, or composite_score is generated for a suppressed event.

Co-fired correlated events (PRICE_MOVE + 52W_HIGH, per Decision 5 section 5c) produce one
combined what_happened narrative; the underlying ChangeEvents remain separately stored and
retrievable — only the narrative text is merged, not the underlying data.

This closes the seven designated Decision 1-7 reviews. It does NOT close the spec: two pre-existing section 8 product questions (meaningful-change count scope, and the 0.60/0.30 attention thresholds) remain explicitly open and must be resolved before Phase 6.8 implementation begins. See RELEVANCE_ATTENTION_SPEC.md section 7 for the full explanation contract.

### Phase 6.8: Known open items NOT covered by Decisions 1-7

Two items from the original section 8 ambiguity list were never part of the "Decision 1-7"
review and remain genuinely unresolved:
  - Per-objective vs. global attention count (does the Phase 8 dashboard's "N meaningful
    changes" figure change when the user toggles GROWTH/VALUE/STABILITY, or stay constant
    with only per-objective tiers changing on drill-in?)
  - The 0.60/0.30 composite_score thresholds (section 4) were chosen as round numbers, not
    derived, and were never revisited against real magnitude/relevance/confidence values the
    way the 52W formula and stale-data grace window were in Decisions 4 and 6.
These should be treated as open before Phase 6.8 implementation begins, not silently assumed
resolved by the Decision 1-7 pass.

### Phase 6.8: Relevance/attention spec — Decision A (meaningful-change count "N")

N ("N meaningful changes since last visit") is computed per the currently selected
objective, not globally: N = count of eligible (non-suppressed) events at ANY attention
tier under that objective's relevance rules — LOW and MEDIUM events count too, not just
HIGH. Switching objectives may change N, since eligibility is objective-dependent, mirroring
how attention_tier itself already varies by objective.

N counts events, not instruments: a single instrument co-firing PRICE_MOVE + 52W_HIGH at
one observation contributes 2 to N, even though section 5 collapses those to a single
"top event tag" for display on that instrument's card. This is intentional — N describes
"how much changed," not "how many instruments changed."

UNAVAILABLE (suppressed, data_confidence == 0) events never count toward N under any
objective. See RELEVANCE_ATTENTION_SPEC.md section 9 for the full frozen contract.

### Phase 6.8: Relevance/attention spec — Decision B (0.60/0.30 threshold validation)

The 0.60/0.30 composite_score thresholds were originally an unexamined round-number
proposal, honestly flagged as such in section 8 rather than silently assumed correct — the
same standard applied to the 52W magnitude formula (Decision 4) and the stale-data grace
window (Decision 6). Unlike those two, which were rejected for inventing an ungrounded
curve that implied a measurement never actually made, 0.60/0.30 are not measurements — they
partition the already-defined composite_score space into three tiers, and checking them
against the real frozen formula (magnitude_normalized x relevance_weight x data_confidence)
shows the partition is coherent:

  - LOW-relevance events can never reach HIGH tier (ceiling 0.30 == MEDIUM's floor)
  - STALE-confidence events can never reach HIGH tier (ceiling 0.50 < HIGH's floor 0.60)
  - MEDIUM-relevance events reach HIGH only at near-maximum magnitude
  - HIGH-relevance + FRESH events can cross into HIGH relatively early (magnitude~=0.6,
    raw value ~1.4x the firing threshold) — explicitly accepted as an intended sensitivity
    property (e.g. for STABILITY's downside-risk relevance rule from Decision 3), not an
    overlooked side effect

0.60/0.30 are kept as originally proposed. This closes the final two section 8 items.
See RELEVANCE_ATTENTION_SPEC.md section 4a for the full derivation and DECISIONS.md /
RELEVANCE_ATTENTION_SPEC.md section 9 for Decision A. All eight decisions plus both
originally-open section 8 items are now resolved — Phase 6.8 implementation may begin
once a final consistency pass over both files is done.

## Phase 7 — Last-Visit Engine Decisions

### Decision 9 — First-visit behavior

A first visit with no prior `last_viewed_at` baseline may still surface
currently eligible change events in `since_last_visit`.

Rationale: the absence of a user-specific historical baseline should not
suppress real, currently relevant market events. The first visit should
demonstrate the watchlist's change-awareness rather than appear artificially
empty.

---

### Decision 10 — Newly added stocks

A newly added stock does not generate a new change-event type solely because
it was added to the watchlist.

The stock appears in `instruments[]` with its `added_at` timestamp. It appears
in `since_last_visit` only when it has an independently eligible market-change
event.

Rationale: this preserves the Phase 6 event taxonomy and avoids introducing
a watchlist-management event solely for presentation purposes.

---

### Decision 11 — Invalid objective parameter

An invalid `?objective=` value returns HTTP 400 rather than silently falling
back to the watchlist's default objective.

Rationale: an explicitly requested objective must either be honored or fail
clearly. Silent fallback could cause the API to return relevance, attention,
and `N` values for a different objective than the client requested.

---

### Decision 12 — POST /viewed response loss

`POST /watchlists/{id}/viewed` is the authoritative mutation of
`last_viewed_at`. If the server successfully performs the mutation but the
client does not receive the response, the server-side state remains
authoritative.

The client must not advance its own baseline solely because it sent the
request.

Rationale: this avoids the more dangerous failure mode in which client state
claims that changes have been consumed when the server never recorded the
view. A lost successful response may result in a subsequent request treating
the same baseline as already viewed, which is an accepted tradeoff.

---
### Decision 13 — Per-instrument comparison boundary

comparison_boundary(item) = item.added_at if watchlist.last_viewed_at IS NULL,
else max(watchlist.last_viewed_at, item.added_at). The since-last-visit event
query is per watchlist_item (join against this boundary), never a single
watchlist-level `timestamp > last_viewed_at` filter.

Rationale: Decision 9's "beginning of time" for a first visit must mean
"beginning of that instrument's membership in the watchlist," not literally
unbounded — an event from before a stock was added must never surface as
"since last visit" for it, matching BUILD_ROADMAP.md Phase 7's explicit
TCS check (last viewed 10:00, added 12:00, event at 11:00 excluded / 13:00
included).

---

### Decision 14 — since_last_visit.events attribution

Each entry in since_last_visit.events is the frozen 8-field
RELEVANCE_ATTENTION_SPEC.md section 7 explanation object, flattened with two
additional sibling fields: instrument_id and symbol. The 8-field contract
itself is not modified — Phase 7 owns only the wrapping shape.

Rationale: without an instrument identifier, the frontend cannot attribute
an event in the flat, non-deduplicated events list to a specific stock card.

### Decision 15 — Event-time data-quality snapshot

MarketEvent.data_quality stores the MarketState.data_quality value computed for the
observation that caused the event (FRESH/STALE/UNAVAILABLE), set at event-creation time
inside the same atomic ingestion transaction. Intelligence scoring (score_event) uses this
event-time snapshot, never the instrument's current MarketState.data_quality — an old
event's relevance must not silently change because today's data happens to be stale.

The column is nullable to accommodate pre-existing MarketEvent rows created before this
field existed.

Legacy-NULL handling (closed, not deferred): data_quality IS NULL is treated identically to
"UNAVAILABLE" by get_data_confidence — confidence 0.0, event suppressed from attention
scoring entirely (section 4 rule 2), never silently scored as FRESH or STALE. This is
consistent with BUILD_ROADMAP.md's rule to never silently convert NULL into a zero *value*:
UNAVAILABLE is the existing frozen "no usable value at all" category, not an invented
default — a NULL snapshot honestly has no known freshness, so it belongs there.
