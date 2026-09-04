"""Pure change-detection functions. No DB, no provider, no FastAPI.
Per BUILD_ROADMAP.md Phase 6: 'never mixed with I/O.'

Architecturally separate from the placeholder price-move check inside
app/services/ingestion.py (Phase 5), which fires a minimal DB-transaction
-scoped MarketEvent row directly. That placeholder is superseded by this
module once Phase 7 wires the intelligence layer into the actual
ingestion pipeline — until then the two coexist deliberately.
"""

from datetime import datetime
from decimal import Decimal

from app.schemas.change_event import ChangeEvent

PRICE_MOVE_THRESHOLD_PCT = Decimal("2.0")
# Percentage points, not percent-of-percent. See SCORING_MODEL.md.
RELATIVE_OUTPERFORMANCE_THRESHOLD_PCT = Decimal("3.0")
# Multiple of the trailing 20-day average volume, not a percentage.
RVOL_WINDOW = 20
RVOL_THRESHOLD = Decimal("2.0")


def compute_return(previous: Decimal | None, current: Decimal) -> Decimal | None:
    """Percent return. None if there's no baseline or baseline is zero."""
    if previous is None or previous == 0:
        return None
    return (current - previous) / previous * 100


def detect_price_move(
    instrument_id: str,
    previous_price: Decimal | None,
    current_price: Decimal,
    detected_at: datetime,
    baseline_timestamp: datetime | None = None,
    threshold_pct: Decimal = PRICE_MOVE_THRESHOLD_PCT,
) -> ChangeEvent | None:
    pct_change = compute_return(previous_price, current_price)
    if pct_change is None or abs(pct_change) < threshold_pct:
        return None
    return ChangeEvent(
        instrument_id=instrument_id,
        event_type="PRICE_MOVE",
        previous_value=previous_price,
        current_value=current_price,
        delta=pct_change,
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


def compute_relative_performance(
    stock_previous: Decimal | None,
    stock_current: Decimal,
    benchmark_previous: Decimal | None,
    benchmark_current: Decimal,
) -> Decimal | None:
    """Stock return minus benchmark return, in percentage points.
    None if either leg lacks a baseline."""
    stock_return = compute_return(stock_previous, stock_current)
    benchmark_return = compute_return(benchmark_previous, benchmark_current)
    if stock_return is None or benchmark_return is None:
        return None
    return stock_return - benchmark_return


def detect_relative_outperformance(
    instrument_id: str,
    stock_previous: Decimal | None,
    stock_current: Decimal,
    benchmark_previous: Decimal | None,
    benchmark_current: Decimal,
    detected_at: datetime,
    baseline_timestamp: datetime | None = None,
    threshold_pct: Decimal = RELATIVE_OUTPERFORMANCE_THRESHOLD_PCT,
) -> ChangeEvent | None:
    """Fires when the stock's return diverges from NIFTY 50's return by
    >= threshold_pct percentage points, in EITHER direction. A negative
    delta means underperformance — the event type name follows the
    roadmap's locked list but covers both directions, same as PRICE_MOVE
    firing on drops as well as rises."""
    relative = compute_relative_performance(stock_previous, stock_current, benchmark_previous, benchmark_current)
    if relative is None or abs(relative) < threshold_pct:
        return None

    stock_return = compute_return(stock_previous, stock_current)
    benchmark_return = compute_return(benchmark_previous, benchmark_current)

    return ChangeEvent(
        instrument_id=instrument_id,
        event_type="RELATIVE_OUTPERFORMANCE",
        previous_value=stock_previous,
        current_value=stock_current,
        delta=relative,
        detected_at=detected_at,
        baseline_timestamp=baseline_timestamp,
        reason=f"relative_{'outperform' if relative > 0 else 'underperform'}_{abs(relative):.1f}pp",
        details={
            "stock_return_pct": str(stock_return),
            "benchmark_return_pct": str(benchmark_return),
            "relative_performance_pp": str(relative),
            "threshold_pct": str(threshold_pct),
        },
    )


def compute_average(values: list[Decimal]) -> Decimal | None:
    """Simple average. None for an empty list — never divide by zero,
    never silently return 0 for 'no data'."""
    if not values:
        return None
    return sum(values, Decimal("0")) / len(values)


def detect_volume_surge(
    instrument_id: str,
    current_volume: Decimal,
    trailing_volumes: list[Decimal],
    detected_at: datetime,
    baseline_timestamp: datetime | None = None,
    window: int = RVOL_WINDOW,
    threshold: Decimal = RVOL_THRESHOLD,
) -> ChangeEvent | None:
    """Fires when current_volume >= threshold * (average of the trailing
    `window` observations, NOT including current_volume itself).

    trailing_volumes must contain at least `window` entries or this
    returns None — a partial window is not a fabricated baseline, same
    rule as detect_price_move's previous_price is None case. Only the
    most recent `window` entries of trailing_volumes are used, so
    callers may pass a longer history without it silently diluting the
    average (the off-by-one bug this guards against: accidentally
    averaging 21 days instead of 20, or including today in its own
    baseline).
    """
    if len(trailing_volumes) < window:
        return None

    windowed = trailing_volumes[-window:]
    avg_volume = compute_average(windowed)
    if avg_volume is None or avg_volume == 0:
        return None

    ratio = current_volume / avg_volume
    if ratio < threshold:
        return None

    pct_above_average = (ratio - 1) * 100

    return ChangeEvent(
        instrument_id=instrument_id,
        event_type="VOLUME_SURGE",
        previous_value=avg_volume,
        current_value=current_volume,
        delta=ratio,  # a multiple (e.g. 2.5), not a percentage — see module docstring
        detected_at=detected_at,
        baseline_timestamp=baseline_timestamp,
        reason=f"volume_surge_{ratio:.1f}x_average",
        details={
            "current_volume": str(current_volume),
            "avg_volume_20d": str(avg_volume),
            "ratio": str(ratio),
            "pct_above_average": str(pct_above_average),
            "window": str(window),
            "threshold": str(threshold),
        },
    )


def detect_change(
    instrument_id: str,
    previous_price: Decimal | None,
    current_price: Decimal,
    detected_at: datetime,
    baseline_timestamp: datetime | None = None,
    benchmark_previous: Decimal | None = None,
    benchmark_current: Decimal | None = None,
    current_volume: Decimal | None = None,
    trailing_volumes: list[Decimal] | None = None,
) -> list[ChangeEvent]:
    """Umbrella orchestrator. Runs every available detector and returns
    ALL triggered events — a single observation can legitimately fire
    more than one event type at once (e.g. PRICE_MOVE and
    RELATIVE_OUTPERFORMANCE together). Returns [] when nothing fires.

    Benchmark checks only run when benchmark_current is provided.
    Volume checks only run when BOTH current_volume and trailing_volumes
    are provided, so the function stays usable without silently
    fabricating a comparison when volume history isn't on hand.

    52W_HIGH/LOW plug in here once 6.6 is built.
    """
    events: list[ChangeEvent] = []

    price_move = detect_price_move(
        instrument_id=instrument_id,
        previous_price=previous_price,
        current_price=current_price,
        detected_at=detected_at,
        baseline_timestamp=baseline_timestamp,
    )
    if price_move is not None:
        events.append(price_move)

    if benchmark_current is not None:
        outperformance = detect_relative_outperformance(
            instrument_id=instrument_id,
            stock_previous=previous_price,
            stock_current=current_price,
            benchmark_previous=benchmark_previous,
            benchmark_current=benchmark_current,
            detected_at=detected_at,
            baseline_timestamp=baseline_timestamp,
        )
        if outperformance is not None:
            events.append(outperformance)

    if current_volume is not None and trailing_volumes is not None:
        volume_surge = detect_volume_surge(
            instrument_id=instrument_id,
            current_volume=current_volume,
            trailing_volumes=trailing_volumes,
            detected_at=detected_at,
            baseline_timestamp=baseline_timestamp,
        )
        if volume_surge is not None:
            events.append(volume_surge)

    return events
