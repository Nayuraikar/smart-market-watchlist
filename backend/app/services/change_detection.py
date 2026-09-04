"""Pure change-detection functions. No DB, no provider, no FastAPI.
Per BUILD_ROADMAP.md Phase 6: 'never mixed with I/O.'"""

from datetime import datetime
from decimal import Decimal

from app.schemas.change_event import ChangeEvent

# Same default as ingestion.py's PRICE_MOVE trigger — see SCORING_MODEL.md
# and DECISIONS.md Phase 5 note. Kept as a separate constant here (not
# imported from ingestion.py) because this module must have zero
# dependency on the ingestion/DB layer.
PRICE_MOVE_THRESHOLD_PCT = Decimal("2.0")


def detect_price_move(
    instrument_id: str,
    previous_price: Decimal | None,
    current_price: Decimal,
    detected_at: datetime,
    baseline_timestamp: datetime | None = None,
    threshold_pct: Decimal = PRICE_MOVE_THRESHOLD_PCT,
) -> ChangeEvent | None:
    """First-ever observation (previous_price is None) never fires an
    event — there's nothing to compare against, per Phase 5's golden
    test 'first-ever observation ⇒ baseline created, no event.'"""
    if previous_price is None or previous_price == 0:
        return None

    pct_change = (current_price - previous_price) / previous_price * 100

    if abs(pct_change) < threshold_pct:
        return None

    return ChangeEvent(
        instrument_id=instrument_id,
        event_type="PRICE_MOVE",
        previous_value=previous_price,
        current_value=current_price,
        delta=pct_change,  # percent, for this event type specifically
        detected_at=detected_at,
        baseline_timestamp=baseline_timestamp,
        reason=f"price_moved_{'up' if pct_change > 0 else 'down'}_{abs(pct_change):.1f}pct",
        details={
            "previous_price": str(previous_price),
            "current_price": str(current_price),
            "pct_change": str(pct_change),
            "threshold_pct": str(threshold_pct),
        },
    )


def detect_change(
    instrument_id: str,
    previous_price: Decimal | None,
    current_price: Decimal,
    detected_at: datetime,
    baseline_timestamp: datetime | None = None,
) -> ChangeEvent | None:
    """Umbrella entry point. Currently only checks PRICE_MOVE — the other
    event types (VOLUME_SURGE, 52W_HIGH/LOW, RELATIVE_OUTPERFORMANCE)
    plug in here once 6.4-6.6 are built. Deliberately NOT stubbed with
    fake logic; each is added only when its real inputs exist."""
    return detect_price_move(
        instrument_id=instrument_id,
        previous_price=previous_price,
        current_price=current_price,
        detected_at=detected_at,
        baseline_timestamp=baseline_timestamp,
    )
