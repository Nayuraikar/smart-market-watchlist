"""Conversion boundary between Phase 6's ChangeEvent (pure, in-memory)
and Phase 7's persisted MarketEvent row. Per DECISIONS.md Decision 16
(Option A): scoring is read-time only, never baked in here. This module
only translates shape and handles JSONB-safe serialization — it must
never call score_event() or anything from intelligence.py's relevance/
objective-aware functions.
"""

from datetime import datetime, timezone
from decimal import Decimal

from app.models import MarketEvent
from app.schemas.change_event import ChangeEvent
from app.services.intelligence import compute_magnitude, NotScoreable

# Coarse, objective-agnostic severity buckets from magnitude_normalized
# alone. Deliberately NOT the same thing as intelligence.get_attention_tier(),
# which additionally weighs relevance and data_confidence. See Decision 16.
_SEVERITY_HIGH_FLOOR = Decimal("0.8")

# Canonical fields change_event_to_market_event() adds on top of
# event.details (winning on collision). Stripped back out in the reverse
# direction so ChangeEvent.details matches its original shape exactly.
_CANONICAL_DETAIL_KEYS = ("previous_value", "current_value", "delta", "reason", "baseline_timestamp")


class LegacyEventNotConvertible(Exception):
    """Raised by market_event_to_change_event() for a MarketEvent row that
    predates Decision 16's canonical details contract — a Phase 5
    placeholder row (fired by ingestion.py's old detect_price_move()
    inline check) whose details lack current_value/delta. Per Decision 16
    consequence 5, these rows are permanently excluded from scoring, not
    silently misinterpreted as if they carried the full contract."""


def derive_event_severity(event: ChangeEvent) -> str:
    """HIGH/MEDIUM/LOW from magnitude alone. NotScoreable (event type has
    no magnitude curve yet) defaults to LOW — an under-estimate is safe,
    a fabricated HIGH is not."""
    try:
        magnitude = compute_magnitude(event)
    except NotScoreable:
        return "LOW"
    return "HIGH" if magnitude >= _SEVERITY_HIGH_FLOOR else "MEDIUM"


def _serialize_value(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def _serialize_timestamp(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _deserialize_decimal(value: str | None) -> Decimal | None:
    return Decimal(value) if value is not None else None


def _deserialize_timestamp(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value is not None else None


def change_event_to_market_event(
    event: ChangeEvent,
    ticker: str,
    data_quality: str,
    source: str,
) -> MarketEvent:
    """The single, authoritative ChangeEvent -> MarketEvent conversion.
    Per Decision 16: no guessing, no key reconstruction. Canonical fields
    win over any same-named key already in event.details."""

    details = dict(event.details)  # event-specific fields first
    details.update({
        "previous_value": _serialize_value(event.previous_value),
        "current_value": _serialize_value(event.current_value),
        "delta": _serialize_value(event.delta),
        "reason": event.reason,
        "baseline_timestamp": _serialize_timestamp(event.baseline_timestamp),
    })

    return MarketEvent(
        instrument_id=event.instrument_id,
        event_type=event.event_type,
        importance=derive_event_severity(event),
        timestamp=event.detected_at,
        title=f"{ticker}: {event.reason}",
        details=details,
        source=source,
        data_quality=data_quality,
    )


def market_event_to_change_event(row: MarketEvent) -> ChangeEvent:
    """Reverse of change_event_to_market_event(), for read-time scoring
    via intelligence.score_event(). Strips the five canonical keys back
    out of details, restoring ChangeEvent.details to its original
    event-specific-only shape.

    ChangeEvent.importance is intentionally left at its default (LOW) —
    it is never reconstructed from row.importance, since that column
    holds derive_event_severity()'s derived bucket, not the original
    (always-meaningless) ChangeEvent.importance value. See Decision 16.

    Raises LegacyEventNotConvertible for a Phase 5 placeholder row
    (missing current_value/delta) — callers must catch this and skip
    the row, per Decision 16 consequence 5, rather than fabricate a
    ChangeEvent from an incomplete contract.
    """
    details = dict(row.details or {})

    previous_value = _deserialize_decimal(details.pop("previous_value", None))
    current_value_raw = details.pop("current_value", None)
    delta_raw = details.pop("delta", None)
    reason = details.pop("reason", None)
    baseline_timestamp = _deserialize_timestamp(details.pop("baseline_timestamp", None))

    if current_value_raw is None or delta_raw is None or reason is None:
        raise LegacyEventNotConvertible(
            f"MarketEvent id={row.id} (event_type={row.event_type!r}) lacks the "
            "canonical current_value/delta/reason keys — predates Decision 16, "
            "excluded from scoring per that decision's consequence 5."
        )

    return ChangeEvent(
        instrument_id=str(row.instrument_id),
        event_type=row.event_type,
        previous_value=previous_value,
        current_value=Decimal(current_value_raw),
        delta=Decimal(delta_raw),
        detected_at=row.timestamp,
        baseline_timestamp=baseline_timestamp,
        reason=reason,
        details=details,
    )
