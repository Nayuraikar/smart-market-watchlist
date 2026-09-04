"""Phase 7.2 end-to-end integration test: ingest_observation() -> real
detect_change() -> change_event_to_market_event() -> (read time)
market_event_to_change_event() -> score_event(). Uses the shared
TESTPHASE7 isolated instrument already manually verified against the
live DB — never touches real ticker data. Cleans up every row it
creates or resets."""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import delete, select

from app.models import Instrument, MarketEvent, MarketHistory, MarketState, User, Watchlist, WatchlistItem
from app.schemas.market import MarketObservation
from app.services.ingestion import IngestResult, ingest_observation
from app.services.last_visit import get_scored_events_since_last_visit

TEST_TICKER = "TESTPHASE7"


async def _get_or_create_test_instrument(db) -> Instrument:
    result = await db.execute(select(Instrument).where(Instrument.ticker == TEST_TICKER))
    instrument = result.scalar_one_or_none()
    if instrument is None:
        instrument = Instrument(
            ticker=TEST_TICKER, name="Phase 7 Integration Test Instrument",
            exchange="TEST", instrument_type="EQUITY",
        )
        db.add(instrument)
        await db.flush()
    return instrument


async def _reset_test_instrument_market_data(db, instrument_id) -> None:
    """Wipes any market data left on TESTPHASE7 by earlier manual runs so
    this test's 'obs1 is the first observation' assumption holds."""
    await db.execute(delete(MarketEvent).where(MarketEvent.instrument_id == instrument_id))
    await db.execute(delete(MarketHistory).where(MarketHistory.instrument_id == instrument_id))
    await db.execute(delete(MarketState).where(MarketState.instrument_id == instrument_id))
    await db.flush()


@pytest.mark.asyncio
async def test_price_move_scores_medium_for_growth_objective(db):
    instrument = await _get_or_create_test_instrument(db)
    await _reset_test_instrument_market_data(db, instrument.id)

    user = User(email=f"phase7-{uuid.uuid4().hex[:8]}@test.local", password_hash="x")
    db.add(user)
    await db.flush()

    watchlist = Watchlist(user_id=user.id, name="Phase 7 test watchlist", objective="GROWTH")
    db.add(watchlist)
    await db.flush()

    db.add(WatchlistItem(watchlist_id=watchlist.id, instrument_id=instrument.id))
    await db.flush()

    now = datetime.now(timezone.utc)

    try:
        obs1 = MarketObservation(
            ticker=TEST_TICKER, price=Decimal("100.00"), volume=Decimal("1000"),
            observed_at=now, source="integration_test",
        )
        outcome1 = await ingest_observation(db, obs1)
        assert outcome1.result == IngestResult.ACCEPTED
        assert outcome1.event_fired is False  # first observation, no baseline

        obs2 = MarketObservation(
            ticker=TEST_TICKER, price=Decimal("106.00"), volume=Decimal("1000"),
            observed_at=now + timedelta(minutes=1), source="integration_test",
        )
        outcome2 = await ingest_observation(db, obs2)
        assert outcome2.result == IngestResult.ACCEPTED
        assert outcome2.event_fired is True

        scored = await get_scored_events_since_last_visit(db, watchlist.id)
        price_move_events = [s for s in scored if s.event.event_type == "PRICE_MOVE"]
        assert len(price_move_events) == 1

        scored_event = price_move_events[0]
        # 6% up-move, GROWTH objective — section 2d: PRICE_MOVE up -> MEDIUM
        assert scored_event.relevance == "MEDIUM"
        # magnitude: 0.5 + 0.5*(6-2)/(2*2) = 1.0 exactly (capped)
        assert scored_event.magnitude_normalized == Decimal("1.0")
        # obs2's observed_at is 1 min in the future relative to real "now"
        # at ingest time -> compute_data_quality's age<0 branch -> STALE,
        # deterministically, regardless of test wall-clock speed
        assert scored_event.data_confidence == Decimal("0.5")
        # composite = 1.0 * 0.6 (MEDIUM) * 0.5 = 0.30 -> MEDIUM tier (>= floor)
        assert scored_event.composite_score == Decimal("0.30")
        assert scored_event.attention_tier == "MEDIUM"

    finally:
        await db.execute(delete(MarketEvent).where(MarketEvent.instrument_id == instrument.id))
        await db.execute(delete(WatchlistItem).where(WatchlistItem.watchlist_id == watchlist.id))
        await db.execute(delete(Watchlist).where(Watchlist.id == watchlist.id))
        await db.execute(delete(MarketHistory).where(MarketHistory.instrument_id == instrument.id))
        await db.execute(delete(MarketState).where(MarketState.instrument_id == instrument.id))
        await db.execute(delete(User).where(User.id == user.id))
        await db.commit()
