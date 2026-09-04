# Relevance & Attention Model — Phase 6.8 Spec (DRAFT, unapproved)

Status: DRAFT — not yet approved. Do not implement against this until reviewed.
Supersedes: nothing yet. Depends on: SCORING_MODEL.md (percentile/score contract, frozen), DECISIONS.md.
Scope: change-event x objective relevance, the attention formula, combination rules for
simultaneous events, stale/missing-data handling, and the explanation contract.

---

## 1. Relevance levels

Three tiers, numeric so they can be multiplied directly in the attention formula:

| Level  | Weight |
|--------|--------|
| HIGH   | 1.0    |
| MEDIUM | 0.6    |
| LOW    | 0.3    |

No NONE tier - if an event type truly can't inform an objective, that's a MEDIUM-vs-LOW
judgment call, not a zero. A hard zero would let one irrelevant-looking event silently vanish
from the log even when the user is looking directly at it.

---

## 2. Base relevance matrix

| Event type               | GROWTH | VALUE  | STABILITY | Rationale |
|---------------------------|--------|--------|-----------|-----------|
| PRICE_MOVE                | MEDIUM | MEDIUM | HIGH      | A large price move is a volatility fact first (stability), a momentum hint second (growth), and shifts the valuation snapshot a bit (value) - but confirms nothing on its own for growth/value. |
| VOLUME_SURGE               | HIGH   | LOW    | MEDIUM    | Unusual volume is a classic momentum/breakout precursor (growth). Largely noise for a value thesis. Can flag event risk (stability). |
| RELATIVE_OUTPERFORMANCE    | HIGH   | LOW    | MEDIUM    | Relative strength vs benchmark is close to the definition of growth momentum. Value investors don't chase relative strength. Large divergence can mean idiosyncratic risk. |
| 52W_HIGH                   | HIGH   | MEDIUM | LOW       | Breaking to a new high is a direct momentum confirmation. Worth a value investor's attention as "getting more expensive." Not a stability signal by itself. |
| 52W_LOW                    | MEDIUM | HIGH   | HIGH      | Breakdown weakens the growth case, but is exactly the "cheap or trap" moment for value, and a new low is unambiguously a risk/stability event. |
| FUNDAMENTAL_CHANGE (+)     | HIGH   | HIGH   | HIGH      | Depends on which metric changed - see 2a. Base row is a placeholder, not usable as-is. |
| EARNINGS                   | HIGH   | MEDIUM | MEDIUM    | Direct input to growth metrics (revenue/EPS growth). Affects the P/E denominator (value). Surprise magnitude is a stability-relevant signal. |
| CORPORATE_ACTION (+)       | LOW    | MEDIUM | MEDIUM    | Depends on sub-type - see 2a. Base row is a placeholder. |

(+) = flagged as ambiguous, see section 8.

### 2a. Sub-typing needed for FUNDAMENTAL_CHANGE and CORPORATE_ACTION

Both event types are too coarse for a single relevance row. Proposed resolution (needs your
approval, not yet applied above):

FUNDAMENTAL_CHANGE - relevance should key off *which metric* changed, using the same
metric families already frozen in scoring.py:

| Changed metric family                          | GROWTH | VALUE  | STABILITY |
|---------------------------------------------------|--------|--------|-----------|
| revenue_growth, eps_growth, roce                   | HIGH   | LOW    | LOW       |
| pe_ratio, pb_ratio, fcf_yield                       | LOW    | HIGH   | LOW       |
| debt_to_equity, roe, earnings_volatility            | LOW    | LOW    | HIGH      |

Rule: HIGH for the metric's own objective family, LOW for the other two - a fundamental delta
in a growth metric is direct signal for GROWTH and only incidental noise for VALUE/STABILITY.

CORPORATE_ACTION - relevance should key off action sub-type:

| Sub-type                        | GROWTH | VALUE  | STABILITY |
|-----------------------------------|--------|--------|-----------|
| Buyback announced                  | LOW    | MEDIUM | LOW       |
| Dividend change (up/cut)           | LOW    | MEDIUM | MEDIUM    |
| Share issuance / dilution          | LOW    | MEDIUM | HIGH      |
| Split / bonus (cosmetic only)      | LOW    | LOW    | LOW       |

Both sub-tables need your sign-off before coding - they're my best guess, not something already
implied by your architecture doc.

---

## 3. Attention formula

composite_score = magnitude_normalized x relevance_weight x data_confidence

- magnitude_normalized in [0, 1] - how extreme the event is, on a per-event-type curve (see 3a)
- relevance_weight in {0.3, 0.6, 1.0} - from section 2 / 2a for the currently selected objective
- data_confidence in [0, 1] - from section 6

composite_score is in [0, 1].

### 3a. Magnitude normalization - needs your existing thresholds, not new ones

I don't have change_detection.py's actual firing thresholds in front of me, so I have NOT
invented magnitude curves here. Proposal: reuse whatever threshold already causes each event to
be *detected* in Phase 6.1-6.6 as the magnitude_normalized = 0.5 midpoint, and pick one
multiple of it (e.g. 3x) as the = 1.0 ceiling, clamped. Concretely, for each event type, I need
you to confirm (or paste) the existing detection threshold before I write the normalization
table - otherwise I'll be freezing numbers that silently disagree with code you've already
shipped and tested.

---

## 4. Thresholds and precedence

| Tier   | composite_score range |
|--------|------------------------|
| HIGH   | >= 0.60                 |
| MEDIUM | 0.30 to 0.5999...        |
| LOW    | < 0.30                 |

Precedence rules:
1. Tier is assigned from composite_score only - magnitude, relevance, and confidence never
   independently override the tier once multiplied in.
2. Hard floor: if data_confidence == 0 (insufficient/unavailable data), the event is
   suppressed from attention scoring entirely - it is not assigned LOW, it does not appear
   in the attention breakdown at all. (It may still appear in a raw, unscored event log if the
   product wants that - separate concern.)
3. Within a tier, sort by exact composite_score descending, not by insertion order - ties are
   broken by relevance_weight, then by magnitude_normalized.
4. No rounding before thresholding - compare the full-precision score to 0.60/0.30.

---

## 5. Combining multiple simultaneous events on one instrument

Per-event scoring stays per-event - never sum composite scores across events, since that would
let an instrument with three MEDIUM events outrank one with a single HIGH event, which inverts
the point of the tiering.

Rule: an instrument's displayed attention tier = the max composite_score among its current
events, for the selected objective. The event that produced that max becomes the "top event
tag" (Phase 8 dashboard requirement). Other concurrent events are retained and shown as
secondary detail on drill-in, not folded into the headline number.

Open question (needs your call, see section 8): should two corroborating events on the same
instrument (e.g. PRICE_MOVE down + VOLUME_SURGE same day) get a small relevance bump for
co-occurrence, on the theory that a price move *with* volume confirmation is more meaningful
than either alone? Proposed default: no bump in v1 - keep it as max-of-independent-scores,
note the idea in DECISIONS.md as a considered-and-deferred enhancement. This keeps the model
explainable, which matters more than a small accuracy gain three days before submission.

---

## 6. Stale / unavailable data -> confidence

| Data state                                                           | data_confidence |
|--------------------------------------------------------------------------|--------------------|
| Fresh (within MARKET_STALE_THRESHOLD_SECONDS)                            | 1.0 |
| Stale but within a grace window (proposal: 5x stale threshold)           | 0.6 |
| Stale beyond grace window, but a last-known value exists                 | 0.3 |
| No usable value at all (INSUFFICIENT_DATA from scoring layer, or missing market state) | 0.0 -> suppressed (rule 2 in section 4) |

This reuses the existing MARKET_STALE_THRESHOLD_SECONDS env var and the scoring layer's own
INSUFFICIENT_DATA sentinel rather than inventing a third staleness concept - one freshness
model end to end, matching the Phase 8 "Updated 2 min ago" / "Data delayed" UI requirement.

---

## 7. Explanation contract

Every scored event, when rendered for a human, must carry exactly these fields:

| Field                     | Content | Example |
|----------------------------|---------|---------|
| what_happened              | One plain-language sentence naming the event type in human terms | "Price broke above its 52-week high" |
| magnitude                  | The raw value + unit + direction, not just the normalized score | "+4.2% today, +18% over 3 sessions" |
| benchmark_comparison       | Nullable - only populated where a benchmark exists (RELATIVE_OUTPERFORMANCE; optionally PRICE_MOVE) | "vs NIFTY 50 +0.6% same period" or null |
| objective_relevance        | Templated per (event_type, objective) pair from section 2/2a - why this matters for the currently selected objective, not a generic blurb | "Under GROWTH: breakout above 52W high confirms upward momentum" |
| data_confidence            | Freshness label + numeric confidence used in scoring | "Fresh - confidence 1.0" or "Stale (47 min) - confidence 0.3" |
| attention_tier             | HIGH / MEDIUM / LOW, the value actually shown in the UI | "HIGH" |
| composite_score            | Internal, full precision - for tests/debugging, not necessarily rendered in the UI | 0.72 |

Explicit non-negotiable: data_confidence must be visible wherever attention_tier is shown,
so a HIGH-attention card never reads as more certain than the underlying data actually is.

---

## 8. Ambiguities / open questions - need your answer before implementation

1. FUNDAMENTAL_CHANGE sub-typing (2a): does the metric-family table match your intent, or
   do you want per-metric granularity instead of per-family?
2. CORPORATE_ACTION sub-typing (2a): are these the sub-types you actually plan to detect?
   The roadmap locks CORPORATE_ACTION as one event type - if the detector doesn't distinguish
   buyback/dividend/dilution/split internally yet, this table can't be applied and
   CORPORATE_ACTION needs a single flat relevance row instead (fallback guess: MEDIUM/MEDIUM/MEDIUM), which is a materially weaker model.
3. Magnitude normalization (3a): I need your actual Phase 6.1-6.6 detection thresholds
   (or the file itself) before I can freeze magnitude_normalized curves - right now that
   section is a placeholder, not a spec.
4. Directional asymmetry: should a downward PRICE_MOVE score higher STABILITY relevance
   than an equal-magnitude upward move? Real risk is usually asymmetric (drawdowns matter more
   than equivalent rallies) but the current matrix treats PRICE_MOVE as direction-agnostic.
   Needs a decision, not an assumption.
5. Co-occurrence bonus (section 5): confirmed default is "no bump in v1" - flag if you disagree.
6. Per-objective vs global attention count: Phase 8's dashboard hero says "N meaningful
   changes since last visit." Is N computed for the currently selected objective (so it
   changes when the user toggles GROWTH/VALUE/STABILITY), or is it a single objective-agnostic
   count with per-objective tiers shown only on drill-in?
7. 0.60 / 0.30 thresholds: these are a proposal, not derived from anything you've specified -
   round numbers chosen so roughly the top ~15-25% of a plausible score distribution lands
   HIGH. Worth a gut-check against a few real numbers once magnitude curves (3a) exist,
   before freezing.

---

## Next step

This file is a draft for review only. Once you resolve section 8 (especially items 1-4, since
they block 2a and 3a from being real numbers rather than placeholders), fold the approved
version into SCORING_MODEL.md (or a new RELEVANCE_MODEL.md if you'd rather keep it separate),
and only then start Phase 6.8 code.
