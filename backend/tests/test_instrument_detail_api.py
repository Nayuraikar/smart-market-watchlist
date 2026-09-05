from datetime import datetime, timedelta, timezone
from decimal import Decimal
import uuid

import pytest
from sqlalchemy import delete, select

from app.models import Instrument, MarketEvent, MarketState, Watchlist, WatchlistItem
from app.schemas.change_event import ChangeEvent
from app.services.event_persistence import change_event_to_market_event


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _instrument(db) -> Instrument:
    instrument = Instrument(
        ticker=f"DETAIL{uuid.uuid4().hex[:8].upper()}",
        name="Detail Test Co",
        exchange="TEST",
        instrument_type="EQUITY",
    )
    db.add(instrument)
    await db.flush()
    return instrument


async def _watchlist(db, user, objective="GROWTH") -> Watchlist:
    watchlist = Watchlist(
        user_id=user.id,
        name="Instrument detail test",
        objective=objective,
    )
    db.add(watchlist)
    await db.flush()
    return watchlist


async def _cleanup(db, watchlist_id, instrument_id):
    await db.execute(delete(MarketEvent).where(MarketEvent.instrument_id == instrument_id))
    await db.execute(delete(MarketState).where(MarketState.instrument_id == instrument_id))
    await db.execute(delete(WatchlistItem).where(WatchlistItem.watchlist_id == watchlist_id))
    await db.execute(delete(Watchlist).where(Watchlist.id == watchlist_id))
    await db.execute(delete(Instrument).where(Instrument.id == instrument_id))
    await db.commit()


@pytest.mark.asyncio
async def test_instrument_detail_returns_metadata_events_and_explanation(
    client,
    db,
    make_user,
):
    user, token = await make_user()
    instrument = await _instrument(db)
    watchlist = await _watchlist(db, user)
    item = WatchlistItem(watchlist_id=watchlist.id, instrument_id=instrument.id)
    db.add(item)
    await db.flush()

    event = ChangeEvent(
        instrument_id=str(instrument.id),
        event_type="PRICE_MOVE",
        previous_value=Decimal("100"),
        current_value=Decimal("106"),
        delta=Decimal("6"),
        detected_at=item.added_at + timedelta(minutes=1),
        reason="price_moved_up_6.0pct",
        details={
            "previous_price": "100",
            "current_price": "106",
            "pct_change": "6.0",
            "threshold_pct": "2.0",
        },
    )
    db.add(change_event_to_market_event(event, instrument.ticker, "FRESH", "api_test"))
    await db.commit()

    try:
        response = await client.get(
            f"/watchlists/{watchlist.id}/stocks/{instrument.id}",
            headers=_auth(token),
        )

        assert response.status_code == 200
        body = response.json()
        assert body["ticker"] == instrument.ticker
        assert body["name"] == "Detail Test Co"
        assert body["exchange"] == "TEST"
        assert body["objective"] == "GROWTH"
        assert body["current_data"] is None
        assert len(body["events"]) == 1
        assert body["events"][0]["what_happened"] == "Price moved up 6.0%."
        assert body["events"][0]["data_status"]["state"] == "FRESH"
        assert body["events"][0]["attention_tier"] == "HIGH"
    finally:
        await _cleanup(db, watchlist.id, instrument.id)


@pytest.mark.asyncio
async def test_instrument_detail_objective_override_is_read_only(
    client,
    db,
    make_user,
):
    user, token = await make_user()
    instrument = await _instrument(db)
    watchlist = await _watchlist(db, user, objective="GROWTH")
    db.add(WatchlistItem(watchlist_id=watchlist.id, instrument_id=instrument.id))
    await db.commit()

    try:
        response = await client.get(
            f"/watchlists/{watchlist.id}/stocks/{instrument.id}",
            params={"objective": "STABILITY"},
            headers=_auth(token),
        )
        assert response.status_code == 200
        assert response.json()["objective"] == "STABILITY"

        result = await db.execute(select(Watchlist).where(Watchlist.id == watchlist.id))
        assert result.scalar_one().objective == "GROWTH"
    finally:
        await _cleanup(db, watchlist.id, instrument.id)


@pytest.mark.asyncio
async def test_instrument_detail_does_not_present_unavailable_state_as_current(
    client,
    db,
    make_user,
):
    user, token = await make_user()
    instrument = await _instrument(db)
    watchlist = await _watchlist(db, user)
    db.add(WatchlistItem(watchlist_id=watchlist.id, instrument_id=instrument.id))
    db.add(
        MarketState(
            instrument_id=instrument.id,
            price=Decimal("100"),
            previous_close=Decimal("99"),
            volume=Decimal("1000"),
            observed_at=datetime.now(timezone.utc),
            ingestion_version=1,
            data_quality="UNAVAILABLE",
            source="api_test",
        )
    )
    await db.commit()

    try:
        response = await client.get(
            f"/watchlists/{watchlist.id}/stocks/{instrument.id}",
            headers=_auth(token),
        )
        assert response.status_code == 200
        current_data = response.json()["current_data"]
        assert current_data["data_status"]["state"] == "UNAVAILABLE"
        assert current_data["data_status"]["message"] == "Market data is unavailable."
        assert current_data["price"] is None
        assert current_data["volume"] is None
    finally:
        await _cleanup(db, watchlist.id, instrument.id)


@pytest.mark.asyncio
async def test_instrument_detail_requires_membership_and_ownership(
    client,
    db,
    make_user,
):
    owner, _owner_token = await make_user()
    other, other_token = await make_user()
    instrument = await _instrument(db)
    watchlist = await _watchlist(db, owner)
    db.add(WatchlistItem(watchlist_id=watchlist.id, instrument_id=instrument.id))
    await db.commit()

    try:
        response = await client.get(
            f"/watchlists/{watchlist.id}/stocks/{instrument.id}",
            headers=_auth(other_token),
        )
        assert response.status_code == 404
    finally:
        await _cleanup(db, watchlist.id, instrument.id)


@pytest.mark.asyncio
async def test_instrument_detail_missing_instrument_returns_404(
    client,
    db,
    make_user,
):
    user, token = await make_user()
    watchlist = await _watchlist(db, user)
    await db.commit()
    missing_id = uuid.uuid4()

    try:
        response = await client.get(
            f"/watchlists/{watchlist.id}/stocks/{missing_id}",
            headers=_auth(token),
        )
        assert response.status_code == 404
    finally:
        await db.execute(delete(Watchlist).where(Watchlist.id == watchlist.id))
        await db.commit()
