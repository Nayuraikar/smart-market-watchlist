# Relevance & Attention Model — Phase 6.8 Spec (APPROVED)

Status: APPROVED — all 8 decisions (1-7, A, B) resolved and frozen. Ready for Phase 6.8 implementation.
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
| PRICE_MOVE                | MEDIUM | MEDIUM | MEDIUM/HIGH (direction-dependent, see 2d) | A large price move is a volatility fact first (stability), a momentum hint second (growth), and shifts the valuation snapshot a bit (value) - but confirms nothing on its own for growth/value. STABILITY relevance splits by direction; see section 2d. |
| VOLUME_SURGE               | HIGH   | LOW    | MEDIUM    | Unusual volume is a classic momentum/breakout precursor (growth). Largely noise for a value thesis. Can flag event risk (stability). |
| RELATIVE_OUTPERFORMANCE    | HIGH   | LOW    | MEDIUM    | Relative strength vs benchmark is close to the definition of growth momentum. Value investors don't chase relative strength. Large divergence can mean idiosyncratic risk. |
| 52W_HIGH                   | HIGH   | MEDIUM | LOW       | Breaking to a new high is a direct momentum confirmation. Worth a value investor's attention as "getting more expensive." Not a stability signal by itself. |
| 52W_LOW                    | MEDIUM | HIGH   | HIGH      | Breakdown weakens the growth case, but is exactly the "cheap or trap" moment for value, and a new low is unambiguously a risk/stability event. |
| FUNDAMENTAL_CHANGE (+)     | HIGH   | HIGH   | HIGH      | Depends on which metric changed - see 2a. Base row is a placeholder, not usable as-is. |
| EARNINGS                   | HIGH   | MEDIUM | MEDIUM    | Direct input to growth metrics (revenue/EPS growth). Affects the P/E denominator (value). Surprise magnitude is a stability-relevant signal. |
| CORPORATE_ACTION (+)       | LOW    | MEDIUM | MEDIUM    | Depends on sub-type - see 2a. Base row is a placeholder. |


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

### 2b. FUNDAMENTAL_CHANGE details contract (FROZEN - Decision 1, approved)

event_type stays exactly "FUNDAMENTAL_CHANGE" - EVENT_TYPES in change_event.py is NOT modified.
Sub-typing lives entirely in ChangeEvent.details, which for this event_type MUST contain:

  {
      "metric": str,
      "metric_family": "growth" | "value" | "stability",
      "previous": numeric | None,
      "current": numeric | None,
      "delta": numeric | None,
  }

Rules:
1. "metric" is mandatory.
2. "metric_family" is mandatory.
3. "metric_family" must be exactly one of "growth", "value", "stability" - any other
   value is a contract violation.
4. Missing or invalid required fields raise (ValueError, consistent with scoring.py's
   existing _validate_percentile pattern) - never silently defaulted or treated as a
   missing-data / INSUFFICIENT_DATA case.
5. "delta_pct" is NOT required. Delta semantics are metric-specific - a percentage-point
   delta is appropriate for growth-rate metrics (handles zero-crossings correctly, e.g.
   revenue_growth moving from -2% to +3%), while a plain numeric delta suffices for
   ratio-style metrics (pe_ratio, debt_to_equity). The relevance/attention engine reads
   "delta" as already being in whatever unit is correct for that metric; it does not
   reinterpret it.
6. Relevance lookup for this event_type is: event_type -> details["metric_family"] ->
   objective -> relevance, using the metric-family table in section 2a. It is NOT a
   flat event_type -> objective lookup the way the other seven event types are.
7. This contract binds whatever future detector (6.9/6.10 or wherever it lands) produces
   FUNDAMENTAL_CHANGE events - it must populate "metric" and "metric_family" from day one.

### 2c. CORPORATE_ACTION details contract (FROZEN - Decision 2, approved)

event_type stays exactly "CORPORATE_ACTION" - EVENT_TYPES in change_event.py is NOT modified.
Sub-typing lives entirely in ChangeEvent.details, which for this event_type MUST contain:

  {
      "economic_effect": "shareholder_friendly" | "shareholder_dilutive" | "cosmetic" | "structural",
      "action_type": str,
  }

"economic_effect" drives relevance/attention scoring. "action_type" is a free-text label
(e.g. "buyback", "dividend_increase", "stock_split", "merger") retained purely for
deterministic human-facing explanations and UI display - it is NOT used in the relevance
lookup itself, only economic_effect is.

Definitions:
- shareholder_friendly: e.g. buybacks, positive shareholder distributions
- shareholder_dilutive: e.g. new share issuance
- cosmetic: e.g. stock split, bonus/share-count representation changes (no economic change)
- structural: e.g. merger/acquisition

Rules:
1. "economic_effect" is mandatory and must be exactly one of the four values above -
   missing or invalid raises (ValueError), same contract-violation pattern as Decision 1.
2. "action_type" is mandatory - missing also raises. No default/inferred value.
3. Relevance lookup for this event_type is: event_type -> details["economic_effect"] ->
   objective -> relevance, NOT a flat event_type -> objective lookup.

Relevance table for shareholder_friendly / shareholder_dilutive / cosmetic (FROZEN):

| economic_effect        | GROWTH | VALUE  | STABILITY |
|--------------------------|--------|--------|-----------|
| shareholder_friendly      | LOW    | MEDIUM | LOW       |
| shareholder_dilutive      | LOW    | MEDIUM | HIGH      |
| cosmetic                  | LOW    | LOW    | LOW       |

structural (merger/acquisition) - EXPLICITLY NOT FROZEN. Do not assign it a relevance row
or run it through the standard composite_score formula yet. A merger is not mechanically
comparable to a dividend bump or a split, and forcing it through the same magnitude x
relevance x confidence pipeline would produce a number with false precision. Structural
events require dedicated attention handling to be designed once the CORPORATE_ACTION
detector exists and real inputs (deal terms, premium/discount, cash vs stock, etc.) are
available to inform what "relevance" even means for this category. Until that design work
happens, a structural event should be surfaced to the user (e.g. in a raw event log) but
NOT assigned a composite_score or HIGH/MEDIUM/LOW attention_tier through this engine.

### 2d. PRICE_MOVE directionality (FROZEN - Decision 3, approved)

PRICE_MOVE relevance is direction-dependent for STABILITY only. GROWTH and VALUE remain
direction-agnostic per the base table above.

| PRICE_MOVE direction   | GROWTH | VALUE  | STABILITY |
|--------------------------|--------|--------|-----------|
| Upward (delta > 0)        | MEDIUM | MEDIUM | MEDIUM    |
| Downward (delta < 0)      | MEDIUM | MEDIUM | HIGH      |

Rules:
1. GROWTH relevance for PRICE_MOVE is MEDIUM regardless of direction.
2. VALUE relevance for PRICE_MOVE is MEDIUM regardless of direction.
3. STABILITY relevance is HIGH for downward moves, MEDIUM for upward moves.
4. Direction is read from the numeric sign of ChangeEvent.delta - this is the sole
   authoritative source. The relevance/attention engine MUST NOT parse or depend on the
   human-readable "reason" string (e.g. "price_moved_down_3.2pct") to determine direction,
   even though that string happens to encode direction too - reason is for display, delta
   is for logic. These must not silently drift apart.
5. The existing 2.0% firing threshold (PRICE_MOVE_THRESHOLD_PCT) is unchanged. This decision
   affects only the relevance lookup, not detection.
6. No changes to change_detection.py are required - delta's sign is already populated for
   every PRICE_MOVE event.
7. This is the ONLY direction-sensitive relevance rule in the spec. No other event type
   gains direction-dependent relevance without a separate, explicitly approved decision.


---

## 3. Attention formula

composite_score = magnitude_normalized x relevance_weight x data_confidence

- magnitude_normalized in [0, 1] - how extreme the event is, on a per-event-type curve (see 3a)
- relevance_weight in {0.3, 0.6, 1.0} - from section 2 / 2a for the currently selected objective
- data_confidence in [0, 1] - from section 6

composite_score is in [0, 1].

### 3a. Magnitude normalization (CONFIRMED thresholds, proposed curve - needs sign-off)

Real thresholds pulled directly from change_detection.py on 2026-09-05:
  PRICE_MOVE_THRESHOLD_PCT = 2.0
  RELATIVE_OUTPERFORMANCE_THRESHOLD_PCT = 3.0
  RVOL_THRESHOLD = 2.0
  52W_HIGH / 52W_LOW: no magnitude threshold - any breakout fires (see caveat below)

General formula for threshold-gated events (PRICE_MOVE, RELATIVE_OUTPERFORMANCE, VOLUME_SURGE):
the value that just barely fires the detector maps to magnitude_normalized = 0.5 (an event
that didn't clear its own bar never reaches this code path at all, so 0.5 is the true floor,
not an arbitrary starting point). 3x the firing threshold maps to 1.0, clamped above that.

  magnitude_normalized = clamp(0.5 + 0.5 * (raw - threshold) / (2 * threshold), 0.5, 1.0)

Concretely:
  PRICE_MOVE:              raw = abs(pct_change).      threshold=2.0,  ceiling=6.0
  RELATIVE_OUTPERFORMANCE: raw = abs(relative_pp).      threshold=3.0,  ceiling=9.0
  VOLUME_SURGE:             raw = ratio (current/avg).   threshold=2.0,  ceiling=6.0 (i.e. 6x avg)

52W_HIGH / 52W_LOW (FROZEN - Decision 4, approved) - NOT scored via a continuous magnitude
formula. detect_52w_high/detect_52w_low have no firing threshold by design (any breakout at
all fires) - the earlier proposal to derive magnitude_normalized from "pct beyond the prior
extreme" via a 0.4-floor/5%-ceiling curve is REJECTED as false precision: it implied a
derived, measured number where none exists, and it ignored is_full_window, the one qualifier
the detector's own design actually treats as meaningful (how much history backs the claim,
not how far past the old extreme price closed).

Instead, 52W_HIGH/52W_LOW magnitude is categorical, keyed off details["is_full_window"]:

  is_full_window == True   -> magnitude_normalized = 1.0
  is_full_window == False  -> magnitude_normalized = 0.7

0.7 is a flat, explicitly-labeled discount for reduced historical backing - it is NOT derived
from any measurement, and is not dressed up as one. This is a deliberately simpler, more
honest number than a formula that looks precise but isn't.

The actual breakout size (prior_max/prior_min, current_price, the real delta) remains in
ChangeEvent.details exactly as already populated by detect_52w_high/detect_52w_low, and
continues to feed the human-facing explanation contract (section 7) - "magnitude" in the
explanation still shows the real price delta. That value is simply not used to compute
composite_score. Scoring and explanation are two different consumers of the same event and
must not be conflated.

EARNINGS / FUNDAMENTAL_CHANGE / CORPORATE_ACTION (non-structural) - no detector function
exists yet in change_detection.py, so no magnitude curve can be written for these until
6.9/6.10 (or wherever they land) implement the actual detection logic and its own threshold.
CORPORATE_ACTION structural (mergers) is excluded from scoring entirely per Decision 2 and
has no magnitude concept to define here.

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

### 4a. Threshold rationale (FROZEN - Decision B, approved)

0.60/0.30 were originally chosen as round numbers with no derivation - flagged honestly in
section 8 rather than silently assumed correct, per the same standard applied to the 52W
formula (Decision 4) and the stale-data grace window (Decision 6). Unlike those two, which
were REJECTED because they invented an ungrounded curve that implied a measurement never
made, 0.60/0.30 are not measurements at all - they are a partition of the already-defined
[0,1] composite_score space (section 3) into three tiers. Checking them against the actual
frozen formula shows the partition is coherent, not arbitrary:

  relevance_weight in {0.3 (LOW), 0.6 (MEDIUM), 1.0 (HIGH)}
  data_confidence in {1.0 (FRESH), 0.5 (STALE)} (UNAVAILABLE=0.0 is suppressed, never reaches
  this thresholding at all, per rule 2 above)
  magnitude_normalized in [0.5, 1.0] for threshold-gated events; {0.7, 1.0} for 52W events

  | relevance | confidence | score range (min-max) | resulting tier(s) |
  |-----------|------------|------------------------|---------------------|
  | LOW       | FRESH      | 0.15 - 0.30            | LOW only (0.30 is MEDIUM's floor, never above) |
  | LOW       | STALE      | 0.075 - 0.15           | LOW only |
  | MEDIUM    | FRESH      | 0.30 - 0.60            | MEDIUM only (0.60 is HIGH's floor, reached only at max magnitude) |
  | MEDIUM    | STALE      | 0.15 - 0.30            | LOW only |
  | HIGH      | FRESH      | 0.50 - 1.00            | MEDIUM, crossing into HIGH around magnitude~=0.6 |
  | HIGH      | STALE      | 0.25 - 0.50            | LOW to MEDIUM - NEVER reaches HIGH |

Accepted properties of this partition (checked, not assumed):
1. A LOW-relevance event can never reach HIGH tier regardless of magnitude - its ceiling
   (0.30) exactly equals MEDIUM's floor, never crosses it.
2. A STALE event can never reach HIGH tier regardless of relevance or magnitude - its
   ceiling (0.50) sits below HIGH's floor (0.60). This is a useful emergent consistency
   with Decision 6's confidence discount, not a separately-coded rule.
3. A MEDIUM-relevance event reaches HIGH only at the extreme end of the magnitude range
   (raw value at or near 3x the detector's firing threshold) - in practice MEDIUM-relevance
   events live almost entirely inside the MEDIUM tier.
4. A HIGH-relevance, FRESH-data event can cross into HIGH tier relatively early - around
   magnitude_normalized~=0.6, i.e. a raw value only ~1.4x the firing threshold (e.g. a 2.8%
   price move against a 2.0% PRICE_MOVE_THRESHOLD_PCT). This is EXPLICITLY ACCEPTED as a
   deliberate sensitivity property, not an overlooked side effect: for objectives where
   HIGH relevance is assigned to downside risk (e.g. STABILITY's downward PRICE_MOVE per
   Decision 3), reacting early to a modest move is the intended behavior, not a bug to be
   tuned away speculatively. If a specific real scenario later shows this firing too
   eagerly in practice, that is grounds for revisiting the threshold against real data -
   not a reason to guess a different number now.

0.60/0.30 are therefore kept as originally proposed, verified against the real formula
rather than left as an unexamined guess.

---

## 5. Combining multiple simultaneous events on one instrument (FROZEN - Decision 5, approved)

Per-event scoring stays per-event - composite scores are never summed across events. Summing
would let an instrument with three MEDIUM events outrank one with a single HIGH event, which
inverts the point of the tiering. Max-of-independent-scores cannot double-count by
construction: taking the maximum of two numbers is definitionally not adding them, so a
PRICE_MOVE + 52W_HIGH co-firing (the case explicitly flagged for review) still produces
exactly one attention tier - whichever event scored higher - never a boosted or combined
value. No co-occurrence bonus is applied, deliberately, to keep the model explainable.

Rule: an instrument's displayed attention tier = the max composite_score among its current
events, for the selected objective. The event that produced that max becomes the "top event
tag" (Phase 8 dashboard requirement). Other concurrent events are retained in full and remain
retrievable on drill-in - never discarded once a max is chosen.

### 5a. Deterministic tie-break chain (FROZEN - Decision 5, approved)

When two or more events on the same instrument produce an exactly equal composite_score,
resolve which becomes the "top event tag" via, in order:

  1. Higher composite_score (the normal case - this is the primary sort key)
  2. Higher relevance_weight
  3. Higher magnitude_normalized
  4. EVENT_TYPE_PRIORITY order (see 5b) - lower index wins

This chain must be fully deterministic and must never rely on Python dict iteration order,
list append order, or any other incidental ordering. The same set of co-fired events must
resolve to the same "top event tag" on every run, not just typically.

### 5b. EVENT_TYPE_PRIORITY - frozen tie-break order (FROZEN - Decision 5, approved)

This is a SEPARATE, explicitly-defined ordering from EVENT_TYPES' declaration order in
change_event.py, which exists purely for enum readability and carries no tie-break meaning.
Reusing it incidentally for tie-breaking would silently couple two unrelated concerns.

EVENT_TYPE_PRIORITY (index 0 = highest priority, wins ties):

  0. 52W_HIGH
  1. 52W_LOW
  2. RELATIVE_OUTPERFORMANCE
  3. EARNINGS
  4. FUNDAMENTAL_CHANGE
  5. CORPORATE_ACTION
  6. VOLUME_SURGE
  7. PRICE_MOVE
  8. OTHER

Rationale (a judgment call, stated plainly rather than hidden): 52-week breakouts and
relative-benchmark divergence are the most information-dense signals available (they already
encode a comparison against real history/context, not just today's raw reading), so they win
ties over PRICE_MOVE and VOLUME_SURGE, which are single-observation signals with no such
context. EARNINGS and FUNDAMENTAL_CHANGE outrank CORPORATE_ACTION because they speak directly
to the metrics the three objectives are built from (SCORING_MODEL.md), whereas most
CORPORATE_ACTION sub-types (Decision 2) are one step more indirect. PRICE_MOVE sits lowest
among the "real" event types since it is the least specific signal - almost every other event
type implies some price movement anyway. This ordering is a reasonable default, not a derived
fact - flag if a different priority makes more sense once real data is available.

### 5c. Explanation-layer correlation phrasing - EXPLICITLY DEFERRED (not decided in Decision 5)

The scoring risk of PRICE_MOVE + 52W_HIGH co-firing is fully resolved by 5/5a above (max
cannot double-count). A separate, narrower concern remains at the EXPLANATION layer: showing
two full, seemingly-independent explanation blocks for what is really one underlying price
move could read as "two reasons this matters" to a user, even though the score was never
doubled. Whether/how to phrase correlated co-fired events as a single combined narrative
(e.g. "Price broke above its 52-week high on a 4.1% move" instead of two separate blocks) is
deferred to Decision 7 (explanation contract), where it will be designed against the actual
frozen explanation field structure rather than guessed at here before that contract exists.

---

## 6. Stale / unavailable data -> confidence (FROZEN - Decision 6, approved)

The earlier 4-tier scheme (1.0/0.6/0.3/0.0, with a "5x stale threshold" grace-window
boundary) is REJECTED on the same grounds as the 0.4/5.0 formula rejected in Decision 4: the
"5x" multiplier was an ungrounded round number producing a boundary that looked derived but
wasn't. Rather than invent a justification for it, the grace-window tier is removed entirely.

### 6a. Canonical data-quality states (FROZEN)

FRESH / STALE / UNAVAILABLE are the three canonical data-quality states used throughout the
system - by the explanation layer for phrasing (section 7) as much as by the scoring layer.
These are a product/data-status classification, not a numeric confidence score.

  FRESH        - within MARKET_STALE_THRESHOLD_SECONDS
  STALE        - beyond MARKET_STALE_THRESHOLD_SECONDS, but a last-known value exists
  UNAVAILABLE  - no usable value at all (no last-known value, or the scoring layer's own
                 INSUFFICIENT_DATA sentinel)

### 6b. data_confidence mapping (FROZEN - product-policy values, not statistical confidence)

data_confidence is a SEPARATE, DERIVED scoring input computed from the state in 6a - it is
not itself the state, and the two must not be conflated in code or in explanations.

  FRESH        -> data_confidence = 1.0
  STALE        -> data_confidence = 0.5
  UNAVAILABLE  -> data_confidence = 0.0 -> event suppressed (rule 2, section 4) - no
                  composite_score or attention_tier is computed for it at all

0.5 for STALE is an explicit PRODUCT-POLICY DISCOUNT, not a statistically derived confidence
value. It exists to halve a stale event's contribution to composite_score, nothing more. It
must never be exposed to the user as "50% confidence" or any framing that implies it was
measured - see section 7 for the exact required phrasing.

Only two data-quality states carry a nonzero confidence (FRESH, STALE); UNAVAILABLE always
suppresses. This intentionally simpler 3-state model replaces any grace-window boundary,
removing the false-precision risk a middle "how stale is too stale" cutoff would introduce.

---

## 7. Explanation contract (FROZEN - Decision 7, approved)

Every scored event, when rendered for a human, must carry exactly these 8 fields:

| Field                 | Content | Rule |
|-------------------------|---------|------|
| what_happened            | Plain-language event description | For co-fired correlated events (e.g. PRICE_MOVE + 52W_HIGH on the same instrument/observation, per section 5c), produces ONE combined sentence, not separate blocks - e.g. "Price broke above its 52-week high on a 4.1% move." The underlying ChangeEvents remain separately stored/retrievable (section 5) - only the narrative is combined, not the data. |
| magnitude                | Raw value + unit + direction | Always the real figure. For 52W_HIGH/52W_LOW this is the actual price delta even though scoring uses the categorical 1.0/0.7 value (section 3a, Decision 4) - explanation and scoring are separate consumers of the same event and must not be conflated. |
| benchmark_comparison     | Nullable | Populated ONLY for RELATIVE_OUTPERFORMANCE. PRICE_MOVE and every other event_type: always null - not "optionally," not implementation-dependent. Kept as a distinct field from magnitude - NOT merged. If per-instrument benchmarking for PRICE_MOVE is wanted later, that is a new decision, not an inferred extension of this one. |
| objective_relevance      | Why this matters for the selected objective | Templated per (event_type, [sub-key]) from section 2/2a/2b/2c/2d - must reflect the correct sub-lookup (metric_family, economic_effect, or PRICE_MOVE direction) per the relevant frozen decision, never a generic blurb. |
| data_status               | Structured object: { "state": "FRESH" \| "STALE" \| "UNAVAILABLE", "message": string \| null } | FRESH: message may be null: no disclosure beyond normal phrasing. STALE: message MUST contain plain-language disclosure that the underlying data is stale/last-known - in words, never as a percentage or numeric confidence figure. UNAVAILABLE: message MUST contain a data-status explanation, and this event MUST NOT produce a scored attention explanation at all - no what_happened/objective_relevance/attention_tier/composite_score are generated for it. |
| data_confidence           | Internal numeric value (1.0 / 0.5 / 0.0, per section 6b) | Tests/debugging only. MUST NOT be rendered to the user directly, and MUST NOT be exposed as a percentage anywhere in user-facing text - this is the numeric counterpart to data_status.state, not a substitute for it. |
| attention_tier            | HIGH / MEDIUM / LOW | Absent entirely (not "N/A", not null-but-present) for UNAVAILABLE events, since suppression (section 4, rule 2) means no scoring ran at all. |
| composite_score           | Full-precision internal value | Tests/debugging only. |

Non-negotiable: data_status must be visible wherever attention_tier is shown, so a
HIGH-attention card never reads as more certain than the underlying data actually is. This
supersedes the earlier single data_confidence-only requirement - data_status.state carries
the user-facing trust signal, data_confidence is internal-only.

---

## 8. Ambiguities / open questions - need your answer before implementation

1. [RESOLVED - Decision 1, approved] FUNDAMENTAL_CHANGE sub-typing: event_type stays a single
   locked "FUNDAMENTAL_CHANGE" value; per-metric detail lives in ChangeEvent.details and is
   mapped to relevance via details["metric_family"]. Full frozen contract in section 2b.
2. [RESOLVED - Decision 2, approved] CORPORATE_ACTION sub-typing: event_type stays a single
   locked "CORPORATE_ACTION" value; sub-typing lives in ChangeEvent.details via a mandatory
   "economic_effect" field (shareholder_friendly / shareholder_dilutive / cosmetic / structural)
   used for relevance lookup, plus a mandatory "action_type" free-text field used only for
   explanations/UI. "structural" (mergers) is explicitly NOT scored through the standard
   composite_score pipeline - deferred pending detector implementation and real inputs.
   Full frozen contract in section 2c.
3. [RESOLVED - Decision 4, approved] Magnitude normalization: threshold-gated events
   (PRICE_MOVE, RELATIVE_OUTPERFORMANCE, VOLUME_SURGE) use the 0.5-floor/3x-ceiling formula
   in section 3a, anchored to their real detection thresholds. 52W_HIGH/52W_LOW are scored
   categorically (1.0 full-window / 0.7 partial-window), NOT via a continuous formula - the
   earlier 0.4/5.0 proposal was reviewed and rejected as false precision. EARNINGS/
   FUNDAMENTAL_CHANGE/CORPORATE_ACTION(non-structural) remain blocked on their detectors not
   existing yet.
4. [RESOLVED - Decision 3, approved] PRICE_MOVE directionality: STABILITY relevance is
   direction-dependent (downward = HIGH, upward = MEDIUM), read from ChangeEvent.delta's sign,
   never from the "reason" string. GROWTH and VALUE remain direction-agnostic. No other event
   type gains direction-sensitivity without a separate approved decision. Full frozen contract
   in section 2d.
5. [RESOLVED - Decision 5, approved] Multiple simultaneous events: max-of-independent-scores,
   no co-occurrence bonus - frozen with a fully deterministic tie-break chain (composite_score
   -> relevance_weight -> magnitude_normalized -> EVENT_TYPE_PRIORITY, a new explicit ordering
   separate from EVENT_TYPES' declaration order). Secondary events remain fully retrievable.
   Correlated-event explanation phrasing is explicitly deferred to Decision 7. Full frozen
   contract in section 5/5a/5b/5c.
6. [RESOLVED - Decision 6, approved] Stale/unavailable data -> confidence: FRESH/STALE/
   UNAVAILABLE are the canonical data-quality states (used by both scoring and explanation
   layers). data_confidence is a separate derived value: FRESH=1.0, STALE=0.5 (explicit
   product-policy discount, not statistical confidence), UNAVAILABLE=0.0 -> suppressed. The
   earlier 4-tier scheme with a "5x threshold" grace window is rejected as ungrounded, same
   category of error as the 52W magnitude formula rejected in Decision 4. Full frozen
   contract in section 6/6a/6b.
7. [RESOLVED - Decision A, approved] Per-objective vs global attention count: N is
   computed per the CURRENTLY SELECTED objective, counting any eligible (non-suppressed)
   event at any tier - not just HIGH. N counts events, not instruments: a co-fired
   PRICE_MOVE + 52W_HIGH on one instrument contributes 2 to N. Switching objectives may
   change N since eligibility is objective-dependent. Full frozen contract in section 9.
8. [RESOLVED - Decision B, approved] 0.60 / 0.30 composite_score thresholds: KEPT as
   originally proposed, but no longer "unrevisited round numbers" - checked against the
   actual frozen formula (section 3/3a, magnitude_normalized x relevance_weight x
   data_confidence) and found to produce coherent, load-bearing partition properties rather
   than arbitrary ones. Full derivation and accepted properties in section 4a.

---

## 9. Meaningful-change count "N" (FROZEN - Decision A, approved)

Phase 8's dashboard hero ("N meaningful changes since last visit") is computed PER-OBJECTIVE,
not globally:

  N = count of events eligible for attention under the CURRENTLY SELECTED objective,
      across ANY attention tier (HIGH, MEDIUM, and LOW all count - not just HIGH),
      using that objective's relevance rules (section 2/2a/2b/2c/2d).

Switching the selected objective (GROWTH/VALUE/STABILITY) may therefore change N, since
relevance - and hence eligibility - is objective-dependent by design (this mirrors how
attention_tier itself already varies by objective; a headline count that didn't vary with it
would be inconsistent with the tiers it's summarizing).

Rules:
1. N counts EVENTS, not instruments. If one instrument co-fires multiple events at the same
   observation (e.g. PRICE_MOVE + 52W_HIGH, per section 5's docstring-documented case), each
   event that independently clears eligibility counts separately toward N. This is intentional
   and explicit - N is not deduplicated per-instrument. An instrument showing 2 eligible events
   contributes 2 to N, not 1, even though section 5 collapses them to a single displayed
   "top event tag" for that instrument's card.
2. "Eligible" means the event was not suppressed (data_confidence != 0, i.e. not UNAVAILABLE
   per section 6b) and produced a real composite_score and attention_tier under the selected
   objective's relevance lookup - it does NOT mean "tier == HIGH". A LOW-tier event is still
   part of the "what changed" story and must be counted, not silently dropped from N just
   because it will render as low-priority on the card itself.
3. UNAVAILABLE (suppressed) events are never counted in N under any objective, consistent
   with section 4 rule 2 - they never reach a composite_score/attention_tier at all.

---

## Next step

All section 8 items (1-8, corresponding to Decisions 1-7 plus A and B) are resolved and
frozen as of this version. This spec is ready to fold into SCORING_MODEL.md (or a standalone
RELEVANCE_MODEL.md, if kept separate) and to begin Phase 6.8 implementation against.
