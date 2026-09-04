"""Pure intelligence-layer functions: relevance, magnitude, confidence,
composite score, attention tier, and top-event tie-break selection.
Per RELEVANCE_ATTENTION_SPEC.md (APPROVED, Decisions 1-7, A, B). No DB,
no provider, no FastAPI — same purity discipline as change_detection.py
and scoring.py (BUILD_ROADMAP.md Phase 6: 'never mixed with I/O.')

Does NOT build the human-facing explanation strings (what_happened /
objective_relevance text) — this module produces the numeric/categorical
outputs the explanation layer consumes. Text templating is Phase 7.3.
"""

from decimal import Decimal
from typing import Literal

from app.schemas.change_event import ChangeEvent

RelevanceLevel = Literal["HIGH", "MEDIUM", "LOW"]
Objective = Literal["GROWTH", "VALUE", "STABILITY"]
DataQualityState = Literal["FRESH", "STALE", "UNAVAILABLE"]
AttentionTier = Literal["HIGH", "MEDIUM", "LOW"]

RELEVANCE_WEIGHT: dict[RelevanceLevel, Decimal] = {
    "HIGH": Decimal("1.0"),
    "MEDIUM": Decimal("0.6"),
    "LOW": Decimal("0.3"),
}

DATA_CONFIDENCE: dict[DataQualityState, Decimal] = {
    "FRESH": Decimal("1.0"),
    "STALE": Decimal("0.5"),
    "UNAVAILABLE": Decimal("0.0"),
}

HIGH_TIER_FLOOR = Decimal("0.60")
MEDIUM_TIER_FLOOR = Decimal("0.30")

# section 5b — a SEPARATE ordering from EVENT_TYPES' declaration order in
# change_event.py. Index 0 = highest priority, wins ties.
EVENT_TYPE_PRIORITY: dict[str, int] = {
    "52W_HIGH": 0,
    "52W_LOW": 1,
    "RELATIVE_OUTPERFORMANCE": 2,
    "EARNINGS": 3,
    "FUNDAMENTAL_CHANGE": 4,
    "CORPORATE_ACTION": 5,
    "VOLUME_SURGE": 6,
    "PRICE_MOVE": 7,
    "OTHER": 8,
}

# section 2 base matrix — event types with a flat event_type -> objective lookup
_BASE_RELEVANCE: dict[str, dict[Objective, RelevanceLevel]] = {
    "VOLUME_SURGE": {"GROWTH": "HIGH", "VALUE": "LOW", "STABILITY": "MEDIUM"},
    "RELATIVE_OUTPERFORMANCE": {"GROWTH": "HIGH", "VALUE": "LOW", "STABILITY": "MEDIUM"},
    "52W_HIGH": {"GROWTH": "HIGH", "VALUE": "MEDIUM", "STABILITY": "LOW"},
    "52W_LOW": {"GROWTH": "MEDIUM", "VALUE": "HIGH", "STABILITY": "HIGH"},
    "EARNINGS": {"GROWTH": "HIGH", "VALUE": "MEDIUM", "STABILITY": "MEDIUM"},
}

# section 2d — PRICE_MOVE, direction-dependent for STABILITY only
_PRICE_MOVE_RELEVANCE: dict[str, dict[Objective, RelevanceLevel]] = {
    "up": {"GROWTH": "MEDIUM", "VALUE": "MEDIUM", "STABILITY": "MEDIUM"},
    "down": {"GROWTH": "MEDIUM", "VALUE": "MEDIUM", "STABILITY": "HIGH"},
}

# section 2a/2b — FUNDAMENTAL_CHANGE, keyed by details["metric_family"]
_FUNDAMENTAL_CHANGE_RELEVANCE: dict[str, dict[Objective, RelevanceLevel]] = {
    "growth": {"GROWTH": "HIGH", "VALUE": "LOW", "STABILITY": "LOW"},
    "value": {"GROWTH": "LOW", "VALUE": "HIGH", "STABILITY": "LOW"},
    "stability": {"GROWTH": "LOW", "VALUE": "LOW", "STABILITY": "HIGH"},
}

# section 2c — CORPORATE_ACTION, keyed by details["economic_effect"].
# "structural" deliberately has no row — see get_relevance().
_CORPORATE_ACTION_RELEVANCE: dict[str, dict[Objective, RelevanceLevel]] = {
    "shareholder_friendly": {"GROWTH": "LOW", "VALUE": "MEDIUM", "STABILITY": "LOW"},
    "shareholder_dilutive": {"GROWTH": "LOW", "VALUE": "MEDIUM", "STABILITY": "HIGH"},
    "cosmetic": {"GROWTH": "LOW", "VALUE": "LOW", "STABILITY": "LOW"},
}

# section 3a — firing thresholds, real values from change_detection.py
MAGNITUDE_THRESHOLDS: dict[str, Decimal] = {
    "PRICE_MOVE": Decimal("2.0"),
    "RELATIVE_OUTPERFORMANCE": Decimal("3.0"),
    "VOLUME_SURGE": Decimal("2.0"),
}


class NotScoreable(Exception):
    """Raised when an event_type/sub-type cannot go through composite_score
    at all: CORPORATE_ACTION structural (Decision 2 — explicitly excluded),
    or an event_type with no detector/magnitude curve yet (EARNINGS,
    FUNDAMENTAL_CHANGE, CORPORATE_ACTION non-structural — section 3a).
    Distinct from a suppressed (data_confidence == 0) event: this means
    'the pipeline doesn't cover this yet', not 'data unavailable'."""


def get_relevance(event: ChangeEvent, objective: Objective) -> RelevanceLevel:
    """event_type -> [sub-key] -> objective -> relevance, per section
    2/2a/2b/2c/2d. Raises ValueError for a malformed details contract on
    FUNDAMENTAL_CHANGE/CORPORATE_ACTION (missing/invalid mandatory
    sub-fields) — never silently defaulted, per those frozen contracts.
    Raises NotScoreable for CORPORATE_ACTION structural, or any event_type
    with no relevance row defined yet."""
    event_type = event.event_type

    if event_type == "PRICE_MOVE":
        direction = "up" if event.delta > 0 else "down"
        return _PRICE_MOVE_RELEVANCE[direction][objective]

    if event_type == "FUNDAMENTAL_CHANGE":
        metric_family = event.details.get("metric_family")
        if metric_family not in ("growth", "value", "stability"):
            raise ValueError(
                f"FUNDAMENTAL_CHANGE details['metric_family'] is {metric_family!r}, "
                "must be 'growth'/'value'/'stability' — contract violation (Decision 1)."
            )
        if not event.details.get("metric"):
            raise ValueError("FUNDAMENTAL_CHANGE details['metric'] is mandatory (Decision 1).")
        return _FUNDAMENTAL_CHANGE_RELEVANCE[metric_family][objective]

    if event_type == "CORPORATE_ACTION":
        economic_effect = event.details.get("economic_effect")
        valid = ("shareholder_friendly", "shareholder_dilutive", "cosmetic", "structural")
        if economic_effect not in valid:
            raise ValueError(
                f"CORPORATE_ACTION details['economic_effect'] is {economic_effect!r}, "
                f"must be one of {valid} — contract violation (Decision 2)."
            )
        if not event.details.get("action_type"):
            raise ValueError("CORPORATE_ACTION details['action_type'] is mandatory (Decision 2).")
        if economic_effect == "structural":
            raise NotScoreable(
                "CORPORATE_ACTION structural is explicitly excluded from composite_score "
                "(Decision 2) — surface via raw event log only, no attention_tier."
            )
        return _CORPORATE_ACTION_RELEVANCE[economic_effect][objective]

    if event_type in _BASE_RELEVANCE:
        return _BASE_RELEVANCE[event_type][objective]

    raise NotScoreable(f"No relevance row defined yet for event_type={event_type!r}.")


def compute_magnitude(event: ChangeEvent) -> Decimal:
    """magnitude_normalized in [0,1], per section 3a. Threshold-gated
    events (PRICE_MOVE, RELATIVE_OUTPERFORMANCE, VOLUME_SURGE) use the
    0.5-floor/3x-ceiling formula. 52W_HIGH/LOW are categorical off
    is_full_window (Decision 4). Raises NotScoreable for event types with
    no magnitude curve yet (EARNINGS, FUNDAMENTAL_CHANGE, CORPORATE_ACTION
    non-structural)."""
    event_type = event.event_type

    if event_type in MAGNITUDE_THRESHOLDS:
        threshold = MAGNITUDE_THRESHOLDS[event_type]
        # VOLUME_SURGE's delta IS the ratio (see change_detection.py); the
        # other two use abs(delta) since they fire on either-direction moves.
        raw = event.delta if event_type == "VOLUME_SURGE" else abs(event.delta)
        normalized = Decimal("0.5") + Decimal("0.5") * (raw - threshold) / (2 * threshold)
        if normalized < Decimal("0.5"):
            return Decimal("0.5")
        if normalized > Decimal("1.0"):
            return Decimal("1.0")
        return normalized

    if event_type in ("52W_HIGH", "52W_LOW"):
        is_full_window = event.details.get("is_full_window")
        if is_full_window is None:
            raise ValueError(
                f"{event_type} details['is_full_window'] is missing — "
                "detector must always populate this (change_detection.py contract)."
            )
        return Decimal("1.0") if is_full_window else Decimal("0.7")

    raise NotScoreable(f"No magnitude curve defined yet for event_type={event_type!r}.")


def get_data_confidence(data_quality: DataQualityState) -> Decimal:
    """FRESH/STALE/UNAVAILABLE -> data_confidence, per section 6b."""
    return DATA_CONFIDENCE[data_quality]


def compute_composite_score(
    magnitude_normalized: Decimal, relevance: RelevanceLevel, data_confidence: Decimal,
) -> Decimal:
    """composite_score = magnitude_normalized x relevance_weight x
    data_confidence, per section 3. Callers must check data_confidence == 0
    (UNAVAILABLE) BEFORE calling this and suppress the event entirely
    (section 4 rule 2) — this function does not special-case zero."""
    return magnitude_normalized * RELEVANCE_WEIGHT[relevance] * data_confidence


def get_attention_tier(composite_score: Decimal) -> AttentionTier:
    """Tier from full-precision composite_score, per section 4. Assumes
    the caller already excluded a suppressed (confidence==0) event."""
    if composite_score >= HIGH_TIER_FLOOR:
        return "HIGH"
    if composite_score >= MEDIUM_TIER_FLOOR:
        return "MEDIUM"
    return "LOW"


class ScoredEvent:
    """Carries a ChangeEvent plus its computed scoring outputs between
    intelligence.py and the Phase 7 endpoint layer. Not a Pydantic model —
    the endpoint layer builds the actual response schema from this."""

    __slots__ = (
        "event", "relevance", "magnitude_normalized",
        "data_confidence", "composite_score", "attention_tier",
    )

    def __init__(
        self,
        event: ChangeEvent,
        relevance: RelevanceLevel,
        magnitude_normalized: Decimal,
        data_confidence: Decimal,
        composite_score: Decimal,
        attention_tier: AttentionTier,
    ) -> None:
        self.event = event
        self.relevance = relevance
        self.magnitude_normalized = magnitude_normalized
        self.data_confidence = data_confidence
        self.composite_score = composite_score
        self.attention_tier = attention_tier


def score_event(
    event: ChangeEvent, objective: Objective, data_quality: DataQualityState,
) -> ScoredEvent | None:
    """Full per-event pipeline: confidence -> relevance -> magnitude ->
    composite_score -> tier. Returns None for a suppressed event
    (data_confidence == 0 — section 4 rule 2) or an event_type/sub-type
    not yet scoreable (NotScoreable). Propagates ValueError for a
    malformed details contract — that's a data bug, not a missing-data
    case, and must not be swallowed."""
    data_confidence = get_data_confidence(data_quality)
    if data_confidence == 0:
        return None

    try:
        relevance = get_relevance(event, objective)
        magnitude_normalized = compute_magnitude(event)
    except NotScoreable:
        return None

    composite_score = compute_composite_score(magnitude_normalized, relevance, data_confidence)
    attention_tier = get_attention_tier(composite_score)

    return ScoredEvent(
        event=event,
        relevance=relevance,
        magnitude_normalized=magnitude_normalized,
        data_confidence=data_confidence,
        composite_score=composite_score,
        attention_tier=attention_tier,
    )


def _tie_break_key(scored: ScoredEvent) -> tuple:
    """Section 5a's chain: higher composite_score, then higher
    relevance_weight, then higher magnitude_normalized, then lower
    EVENT_TYPE_PRIORITY index wins. Priority index is negated so that
    'wins' still means 'larger' for use with max()."""
    priority_index = EVENT_TYPE_PRIORITY.get(scored.event.event_type, EVENT_TYPE_PRIORITY["OTHER"])
    return (
        scored.composite_score,
        RELEVANCE_WEIGHT[scored.relevance],
        scored.magnitude_normalized,
        -priority_index,
    )


def select_top_event(scored_events: list[ScoredEvent]) -> ScoredEvent | None:
    """max-of-independent-scores + deterministic tie-break, per section
    5/5a/5b. Never sums scores. Returns None for an empty list — zero
    eligible events on an instrument is a valid state."""
    if not scored_events:
        return None
    return max(scored_events, key=_tie_break_key)
