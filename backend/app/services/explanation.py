"""Explanation builder — Phase 7.3. Converts a ScoredEvent (Phase 7.1's
composite_score/attention_tier/relevance) plus its underlying ChangeEvent
(Phase 6/7.2's real, un-rounded detail values) into
RELEVANCE_ATTENTION_SPEC.md section 7's frozen 8-field human-facing
contract.

Scope: only the 5 event types that can actually reach a ScoredEvent today
have templates here — PRICE_MOVE, RELATIVE_OUTPERFORMANCE, VOLUME_SURGE,
52W_HIGH, 52W_LOW. EARNINGS/FUNDAMENTAL_CHANGE/CORPORATE_ACTION all raise
NotScoreable inside intelligence.compute_magnitude() (no magnitude curve
exists yet), so score_event() returns None for them and this function is
never called with one — adding templates for those is deferred to when
their detectors/magnitude curves land, not part of this phase.

No DB, no FastAPI — pure function of ScoredEvent -> ScoredEventExplanation,
same purity discipline as intelligence.py and event_persistence.py.
"""

from decimal import Decimal

from app.schemas.change_event import ChangeEvent
from app.schemas.scored_event import DataStatus, ScoredEventExplanation
from app.services.intelligence import Objective, ScoredEvent

_STALE_MESSAGE = (
    "This event is based on the last known price, which may not reflect "
    "the most recent market activity."
)


class ExplanationNotImplemented(Exception):
    """Raised for an event_type this module has no template for yet.
    Should not occur in practice today — see module docstring — but kept
    explicit rather than silently emitting a generic/wrong sentence."""


def _data_status_from_confidence(data_confidence: Decimal) -> DataStatus:
    if data_confidence == Decimal("1.0"):
        return DataStatus(state="FRESH", message=None)
    if data_confidence == Decimal("0.5"):
        return DataStatus(state="STALE", message=_STALE_MESSAGE)
    # UNAVAILABLE (0.0) means score_event() returned None and this
    # function was never reached — defensive only, not a real path.
    return DataStatus(
        state="UNAVAILABLE",
        message="Data for this event is unavailable.",
    )


# ---- objective_relevance templates -----------------------------------
# Each sentence's tone (highly/moderately/only weakly relevant) is
# written to match intelligence.py's frozen relevance tables exactly —
# _PRICE_MOVE_RELEVANCE and _BASE_RELEVANCE — not invented independently.

_PRICE_MOVE_RELEVANCE_TEXT: dict[str, dict[Objective, str]] = {
    "up": {
        "GROWTH": "A price increase can reflect building momentum, which "
                  "matters for a growth-focused watchlist, though a single "
                  "move isn't a trend on its own.",
        "VALUE": "Price moves alone are only moderately informative for a "
                 "value objective — valuation fundamentals matter more "
                 "than short-term price action.",
        "STABILITY": "An upward move is generally a milder signal for a "
                     "stability-focused watchlist than a downward one.",
    },
    "down": {
        "GROWTH": "A price decline is only moderately relevant for a "
                  "growth objective — it may or may not reflect a change "
                  "in the underlying growth story.",
        "VALUE": "A price decline is moderately relevant for a value "
                 "objective — worth checking against fundamentals, but "
                 "not conclusive on its own.",
        "STABILITY": "A downward price move is highly relevant for a "
                     "stability-focused watchlist, since your objective "
                     "specifically prioritizes low volatility.",
    },
}

_RELATIVE_OUTPERFORMANCE_TEXT: dict[Objective, str] = {
    "GROWTH": "Performance relative to the benchmark is highly relevant "
              "for a growth objective — it's a direct signal of whether "
              "this stock is outpacing the broader market.",
    "VALUE": "Short-term relative performance vs. the benchmark carries "
             "limited weight for a value objective, which is more "
             "concerned with underlying fundamentals.",
    "STABILITY": "Relative performance against the benchmark is "
                 "moderately relevant for a stability-focused watchlist "
                 "— a large divergence, in either direction, hints at "
                 "added volatility.",
}

_VOLUME_SURGE_TEXT: dict[Objective, str] = {
    "GROWTH": "A volume surge is highly relevant for a growth objective "
              "— unusual trading activity often accompanies a meaningful "
              "move in a growth stock.",
    "VALUE": "Volume surges are only weakly relevant for a value "
             "objective — trading activity says little about whether a "
             "stock is fairly priced.",
    "STABILITY": "A volume surge is moderately relevant for a "
                 "stability-focused watchlist, since a spike in activity "
                 "can be an early sign of increased volatility.",
}

_52W_HIGH_TEXT: dict[Objective, str] = {
    "GROWTH": "A new high is highly relevant for a growth objective — "
              "it's a strong signal of sustained upward momentum.",
    "VALUE": "A new high is moderately relevant for a value objective — "
             "worth checking whether the stock still trades at an "
             "attractive valuation.",
    "STABILITY": "A new high is only weakly relevant for a "
                 "stability-focused watchlist, since your objective "
                 "prioritizes low volatility over price appreciation.",
}

_52W_LOW_TEXT: dict[Objective, str] = {
    "GROWTH": "A new low is moderately relevant for a growth objective "
              "— worth watching, though it doesn't necessarily change "
              "the growth thesis.",
    "VALUE": "A new low is highly relevant for a value objective — it "
             "may present an attractive entry point if the underlying "
             "fundamentals remain sound.",
    "STABILITY": "A new low is highly relevant for a stability-focused "
                 "watchlist, since it directly reflects the kind of "
                 "downside volatility your objective seeks to avoid.",
}


def _price_move_fields(event: ChangeEvent, objective: Objective) -> tuple[str, str, str | None, str]:
    direction = "up" if event.delta > 0 else "down"
    pct = abs(event.delta)
    what_happened = f"Price moved {direction} {pct:.1f}%."
    sign = "+" if event.delta > 0 else "-"
    magnitude = f"{sign}{pct:.1f}% price change"
    objective_relevance = _PRICE_MOVE_RELEVANCE_TEXT[direction][objective]
    return what_happened, magnitude, None, objective_relevance


def _relative_outperformance_fields(event: ChangeEvent, objective: Objective) -> tuple[str, str, str | None, str]:
    relative = event.delta
    direction = "outperformed" if relative > 0 else "underperformed"
    pp = abs(relative)
    what_happened = f"Stock {direction} the benchmark by {pp:.1f} percentage points."
    sign = "+" if relative > 0 else ""
    magnitude = f"{sign}{relative:.1f}pp relative performance"
    stock_return = Decimal(event.details["stock_return_pct"])
    benchmark_return = Decimal(event.details["benchmark_return_pct"])
    benchmark_comparison = (
        f"Stock return {stock_return:.1f}% vs. benchmark return {benchmark_return:.1f}%"
    )
    objective_relevance = _RELATIVE_OUTPERFORMANCE_TEXT[objective]
    return what_happened, magnitude, benchmark_comparison, objective_relevance


def _volume_surge_fields(event: ChangeEvent, objective: Objective) -> tuple[str, str, str | None, str]:
    ratio = event.delta
    window = event.details.get("window", "20")
    what_happened = f"Trading volume surged to {ratio:.1f}x its {window}-day average."
    magnitude = f"{ratio:.1f}x average volume"
    objective_relevance = _VOLUME_SURGE_TEXT[objective]
    return what_happened, magnitude, None, objective_relevance


def _52w_high_fields(event: ChangeEvent, objective: Objective) -> tuple[str, str, str | None, str]:
    is_full_window = bool(event.details.get("is_full_window"))
    window_days_used = event.details.get("window_days_used")
    prior_max = event.details.get("prior_max")
    label = "52-week" if is_full_window else f"{window_days_used}-day"
    what_happened = f"Price broke above its {label} high."
    magnitude = f"+{event.delta} vs. prior high of {prior_max}"
    objective_relevance = _52W_HIGH_TEXT[objective]
    return what_happened, magnitude, None, objective_relevance


def _52w_low_fields(event: ChangeEvent, objective: Objective) -> tuple[str, str, str | None, str]:
    is_full_window = bool(event.details.get("is_full_window"))
    window_days_used = event.details.get("window_days_used")
    prior_min = event.details.get("prior_min")
    label = "52-week" if is_full_window else f"{window_days_used}-day"
    what_happened = f"Price broke below its {label} low."
    magnitude = f"{event.delta} vs. prior low of {prior_min}"
    objective_relevance = _52W_LOW_TEXT[objective]
    return what_happened, magnitude, None, objective_relevance


_FIELD_BUILDERS = {
    "PRICE_MOVE": _price_move_fields,
    "RELATIVE_OUTPERFORMANCE": _relative_outperformance_fields,
    "VOLUME_SURGE": _volume_surge_fields,
    "52W_HIGH": _52w_high_fields,
    "52W_LOW": _52w_low_fields,
}


def build_explanation(scored: ScoredEvent, objective: Objective) -> ScoredEventExplanation:
    """The single, authoritative ScoredEvent -> 8-field explanation
    conversion (RELEVANCE_ATTENTION_SPEC.md section 7). Raises
    ExplanationNotImplemented for an event_type with no template — see
    module docstring for why this should not occur in practice today."""
    builder = _FIELD_BUILDERS.get(scored.event.event_type)
    if builder is None:
        raise ExplanationNotImplemented(
            f"No explanation template for event_type={scored.event.event_type!r}. "
            "This event_type should not have reached score_event() at all "
            "unless a magnitude curve was added for it without a matching "
            "explanation template — see module docstring."
        )

    what_happened, magnitude, benchmark_comparison, objective_relevance = builder(
        scored.event, objective
    )

    return ScoredEventExplanation(
        instrument_id=scored.event.instrument_id,
        event_type=scored.event.event_type,
        detected_at=scored.event.detected_at,
        what_happened=what_happened,
        magnitude=magnitude,
        benchmark_comparison=benchmark_comparison,
        objective_relevance=objective_relevance,
        data_status=_data_status_from_confidence(scored.data_confidence),
        data_confidence=scored.data_confidence,
        attention_tier=scored.attention_tier,
        composite_score=scored.composite_score,
    )
