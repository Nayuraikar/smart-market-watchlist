import os
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Instrument, MarketState, MarketHistory, MarketEvent
from app.schemas.market import MarketObservation

DEFAULT_STALE_THRESHOLD_SECONDS = int(os.environ.get("MARKET_STALE_THRESHOLD_SECONDS", "120"))
PRICE_MOVE_THRESHOLD_PCT = Decimal("2.0")  # deliberate default — see DECISIONS.md


class IngestResult(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED_INSTRUMENT_UNKNOWN = "REJECTED_INSTRUMENT_UNKNOWN"
    REJECTED_INVALID_PRICE = "REJECTED_INVALID_PRICE"
    REJECTED_INVALID_VOLUME = "REJECTED_INVALID_VOLUME"
    REJECTED_INVALID_TIMESTAMP = "REJECTED_INVALID_TIMESTAMP"
    REJECTED_OUT_OF_SEQUENCE = "REJECTED_OUT_OF_SEQUENCE"


@dataclass
class IngestOutcome:
    result: IngestResult
    event_fired: bool = False
    data_quality: str | None = None


# ---- Pure, DB-free checks. Unit-testable without Docker/DB (Phase 5 golden tests). ----

def check_price_volume(obs: MarketObservation) -> IngestResult | None:
    if obs.price <= 0:
        return IngestResult.REJECTED_INVALID_PRICE
    if obs.volume < 0:
        return IngestResult.REJECTED_INVALID_VOLUME
    return None


def check_timestamp(obs: MarketObservation) -> IngestResult | None:
    if obs.observed_at.tzinfo is None:
        return IngestResult.REJECTED_INVALID_TIMESTAMP
    return None


def compute_sequence(obs: MarketObservation) -> int:
    """No native sequence from yfinance — derive a monotonic integer from
    the observation's own timestamp. Documented deviation; see DECISIONS.md."""
    return int(obs.observed_at.timestamp())


def compute_data_quality(obs: MarketObservation, now: datetime, stale_threshold_seconds: int) -> str:
    age = (now - obs.observed_at).total_seconds()
    if age < 0:
        # Future timestamp / clock skew — treat conservatively, never "extra fresh"
        return "STALE"
    return "STALE" if age > stale_threshold_seconds else "FRESH"


def detect_price_move(previous_price: Decimal | None, new_price: Decimal,
                       threshold_pct: Decimal = PRICE_MOVE_THRESHOLD_PCT) -> bool:
    """Minimal Phase-5 event trigger. Phase 6's detect_change() supersedes
    this with the full event catalog; kept as a pure function so it's
    independently golden-testable now, per the roadmap."""
    if previous_price is None or previous_price == 0:
        return False
    pct_change = abs((new_price - previous_price) / previous_price) * 100
    return pct_change >= threshold_pct


# ---- The actual pipeline. Touches the DB; exact order per BUILD_ROADMAP.md Phase 5. ----

async def ingest_observation(
    db: AsyncSession,
    obs: MarketObservation,
    now: datetime | None = None,
    stale_threshold_seconds: int | None = None,
) -> IngestOutcome:
    now = now or datetime.now(timezone.utc)
    stale_threshold_seconds = stale_threshold_seconds or DEFAULT_STALE_THRESHOLD_SECONDS

    # 1. structural validation already happened at MarketObservation construction

    # 2. instrument resolution
    result = await db.execute(select(Instrument).where(Instrument.ticker == obs.ticker))
    instrument = result.scalar_one_or_none()
    if instrument is None:
        return IngestOutcome(result=IngestResult.REJECTED_INSTRUMENT_UNKNOWN)

    # 3. price>0 / volume>=0
    pv_error = check_price_volume(obs)
    if pv_error is not None:
        return IngestOutcome(result=pv_error)

    # 4. timestamp sanity (tz-aware)
    ts_error = check_timestamp(obs)
    if ts_error is not None:
        return IngestOutcome(result=ts_error)

    # 5. freshness check
    data_quality = compute_data_quality(obs, now, stale_threshold_seconds)

    # 6. sequence check — reject if incoming <= stored, state stays untouched
    incoming_sequence = compute_sequence(obs)
    state_result = await db.execute(select(MarketState).where(MarketState.instrument_id == instrument.id))
    stored_state = state_result.scalar_one_or_none()

    if stored_state is not None and incoming_sequence <= stored_state.ingestion_version:
        return IngestOutcome(result=IngestResult.REJECTED_OUT_OF_SEQUENCE)

    # 7. persist — one atomic transaction: state + history + event (if triggered), or none of it
    previous_price = stored_state.price if stored_state is not None else None
    is_first_observation = stored_state is None
    event_fired = (not is_first_observation) and detect_price_move(previous_price, obs.price)

    if stored_state is None:
        stored_state = MarketState(instrument_id=instrument.id)
        db.add(stored_state)

    stored_state.price = obs.price
    stored_state.previous_close = obs.previous_close
    stored_state.volume = obs.volume
    stored_state.market_cap = obs.market_cap
    stored_state.pe_ratio = obs.pe_ratio
    stored_state.dividend_yield = obs.dividend_yield
    stored_state.observed_at = obs.observed_at
    stored_state.ingestion_version = incoming_sequence
    stored_state.data_quality = data_quality
    stored_state.source = obs.source

    db.add(MarketHistory(
        instrument_id=instrument.id,
        open_price=obs.price,
        high_price=obs.price,
        low_price=obs.price,
        close_price=obs.price,
        volume=obs.volume,
        timestamp=obs.observed_at,
    ))

    if event_fired:
        pct = (obs.price - previous_price) / previous_price * 100
        db.add(MarketEvent(
            instrument_id=instrument.id,
            event_type="PRICE_MOVE",
            importance="MEDIUM",  # placeholder — Phase 6's attention engine supersedes this
            timestamp=obs.observed_at,
            title=f"{obs.ticker} moved {pct:.2f}%",
            details={"previous_price": str(previous_price), "new_price": str(obs.price)},
            source=obs.source,
            data_quality=data_quality,  # Decision 15 — event-time snapshot, same transaction
        ))

    await db.commit()

    return IngestOutcome(result=IngestResult.ACCEPTED, event_fired=event_fired, data_quality=data_quality)
