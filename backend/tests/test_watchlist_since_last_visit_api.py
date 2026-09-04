"""Phase 7.4 API tests: GET /watchlists/{id}. Hits the real FastAPI app
through httpx.ASGITransport — real routers, real deps, real Postgres.
No isolated test DB (project convention): every test commits its own
setup data (required for the app's separate request-scoped DB session
to see it) and deletes everything it created in a finally block.
"""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import delete, select

from app.models import Instrument, MarketEvent, MarketHistory, MarketState, User, Watchlist, WatchlistItem
from app.schemas.change_event import ChangeEvent
from app.schemas.market import MarketObservation
from app.services.event_persistence import change_event_to_market_event
from app.services.ingestion import ingest_observation


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _mk_instrument(db, ticker: str) -> Instrument:
    instrument = Instrument(ticker=ticker, name=f"{ticker} Test Co", exchange="TEST", instrument_type="EQUITY")
    db.add(instrument)
    await db.flush()
    return instrument


async def _mk_watchlist(db, user: User, objective: str = "GROWTH") -> Watchlist:
    watchlist = Watchlist(user_id=user.id, name="API test watchlist", objective=objective)
    db.add(watchlist)
    await db.flush()
    return watchlist


async def _add_item(db, watchlist: Watchlist, instrument: Instrument) -> WatchlistItem:
    item = WatchlistItem(watchlist_id=watchlist.id, instrument_id=instrument.id)
    db.add(item)
    await db.flush()
    await db.refresh(item)  # need the server-generated added_at
    return item


async def _cleanup_instrument_rows(db, instrument_id) -> None:
    await db.execute(delete(MarketEvent).where(MarketEvent.instrument_id == instrument_id))
    await db.execute(delete(MarketHistory).where(MarketHistory.instrument_id == instrument_id))
    await db.execute(delete(MarketState).where(MarketState.instrument_id == instrument_id))


def _unique_ticker() -> str:
    return f"API{uuid.uuid4().hex[:8].upper()}"


# ---- 1. ownership/404 -------------------------------------------------

@pytest.mark.asyncio
async def test_get_returns_404_for_non_owner(client, db, make_user):
    owner, _owner_token = await make_user()
    other, other_token = await make_user()
    watchlist = await _mk_watchlist(db, owner)
    await db.commit()

    try:
        response = await client.get(f"/watchlists/{watchlist.id}", headers=_auth(other_token))
        assert response.status_code == 404
        body = response.json()
        assert body["error"]["code"] == "NOT_FOUND"
    finally:
        await db.execute(delete(Watchlist).where(Watchlist.id == watchlist.id))
        await db.commit()


# ---- 2. first visit returns eligible events ----------------------------

@pytest.mark.asyncio
async def test_first_visit_returns_eligible_events(client, db, make_user):
    user, token = await make_user()
    instrument = await _mk_instrument(db, _unique_ticker())
    watchlist = await _mk_watchlist(db, user, objective="GROWTH")
    await _add_item(db, watchlist, instrument)
    await db.commit()

    try:
        now = datetime.now(timezone.utc)
        obs1 = MarketObservation(ticker=instrument.ticker, price=Decimal("100.00"), volume=Decimal("1000"),
                                  observed_at=now, source="api_test")
        await ingest_observation(db, obs1)
        obs2 = MarketObservation(ticker=instrument.ticker, price=Decimal("106.00"), volume=Decimal("1000"),
                                  observed_at=now + timedelta(minutes=1), source="api_test")
        await ingest_observation(db, obs2)

        response = await client.get(f"/watchlists/{watchlist.id}", headers=_auth(token))
        assert response.status_code == 200
        body = response.json()

        assert body["watchlist_id"] == str(watchlist.id)
        assert body["objective"] == "GROWTH"
        assert body["since_last_visit"]["meaningful_change_count"] == 1
        assert len(body["since_last_visit"]["events"]) == 1
        event = body["since_last_visit"]["events"][0]
        assert event["what_happened"] == "Price moved up 6.0%."

        assert len(body["instruments"]) == 1
        inst = body["instruments"][0]
        assert inst["ticker"] == instrument.ticker
        assert inst["top_event"] is not None
        assert inst["top_event"]["what_happened"] == "Price moved up 6.0%."
    finally:
        await _cleanup_instrument_rows(db, instrument.id)
        await db.execute(delete(WatchlistItem).where(WatchlistItem.watchlist_id == watchlist.id))
        await db.execute(delete(Watchlist).where(Watchlist.id == watchlist.id))
        await db.execute(delete(Instrument).where(Instrument.id == instrument.id))
        await db.commit()


# ---- 3. repeated GET without POST is identical -------------------------

@pytest.mark.asyncio
async def test_repeated_get_is_identical(client, db, make_user):
    user, token = await make_user()
    instrument = await _mk_instrument(db, _unique_ticker())
    watchlist = await _mk_watchlist(db, user, objective="GROWTH")
    await _add_item(db, watchlist, instrument)
    await db.commit()

    try:
        now = datetime.now(timezone.utc)
        await ingest_observation(db, MarketObservation(
            ticker=instrument.ticker, price=Decimal("100.00"), volume=Decimal("1000"),
            observed_at=now, source="api_test"))
        await ingest_observation(db, MarketObservation(
            ticker=instrument.ticker, price=Decimal("106.00"), volume=Decimal("1000"),
            observed_at=now + timedelta(minutes=1), source="api_test"))

        first = await client.get(f"/watchlists/{watchlist.id}", headers=_auth(token))
        second = await client.get(f"/watchlists/{watchlist.id}", headers=_auth(token))
        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json() == second.json()
    finally:
        await _cleanup_instrument_rows(db, instrument.id)
        await db.execute(delete(WatchlistItem).where(WatchlistItem.watchlist_id == watchlist.id))
        await db.execute(delete(Watchlist).where(Watchlist.id == watchlist.id))
        await db.execute(delete(Instrument).where(Instrument.id == instrument.id))
        await db.commit()


# ---- 4. newly added instrument, no events -------------------------------

@pytest.mark.asyncio
async def test_instrument_with_no_events_still_appears(client, db, make_user):
    user, token = await make_user()
    instrument = await _mk_instrument(db, _unique_ticker())
    watchlist = await _mk_watchlist(db, user, objective="GROWTH")
    item = await _add_item(db, watchlist, instrument)
    await db.commit()

    try:
        response = await client.get(f"/watchlists/{watchlist.id}", headers=_auth(token))
        assert response.status_code == 200
        body = response.json()

        assert body["since_last_visit"]["meaningful_change_count"] == 0
        assert body["since_last_visit"]["events"] == []
        assert len(body["instruments"]) == 1
        inst = body["instruments"][0]
        assert inst["ticker"] == instrument.ticker
        assert inst["top_event"] is None
        # added_at round-trips (allow for JSON timestamp formatting)
        assert inst["added_at"][:19] == item.added_at.isoformat()[:19]
    finally:
        await db.execute(delete(WatchlistItem).where(WatchlistItem.watchlist_id == watchlist.id))
        await db.execute(delete(Watchlist).where(Watchlist.id == watchlist.id))
        await db.execute(delete(Instrument).where(Instrument.id == instrument.id))
        await db.commit()


# ---- 5. co-fired events: two in events[], one top_event -----------------

@pytest.mark.asyncio
async def test_cofired_events_appear_twice_but_one_top_event(client, db, make_user):
    user, token = await make_user()
    instrument = await _mk_instrument(db, _unique_ticker())
    watchlist = await _mk_watchlist(db, user, objective="GROWTH")
    item = await _add_item(db, watchlist, instrument)
    await db.commit()

    detected_at = item.added_at + timedelta(minutes=1)
    try:
        price_move = ChangeEvent(
            instrument_id=str(instrument.id), event_type="PRICE_MOVE",
            previous_value=Decimal("100.00"), current_value=Decimal("106.00"), delta=Decimal("6.0"),
            detected_at=detected_at, reason="price_moved_up_6.0pct",
            details={"previous_price": "100.00", "current_price": "106.00",
                     "pct_change": "6.0", "threshold_pct": "2.0"},
        )
        volume_surge = ChangeEvent(
            instrument_id=str(instrument.id), event_type="VOLUME_SURGE",
            current_value=Decimal("500000"), delta=Decimal("2.5"),
            detected_at=detected_at, reason="volume_surge_2.5x_average",
            details={"current_volume": "500000", "avg_volume_20d": "200000",
                     "ratio": "2.5", "pct_above_average": "150.0", "window": "20", "threshold": "2.0"},
        )
        db.add(change_event_to_market_event(price_move, ticker=instrument.ticker, data_quality="FRESH", source="api_test"))
        db.add(change_event_to_market_event(volume_surge, ticker=instrument.ticker, data_quality="FRESH", source="api_test"))
        await db.commit()

        response = await client.get(f"/watchlists/{watchlist.id}", headers=_auth(token))
        assert response.status_code == 200
        body = response.json()

        assert body["since_last_visit"]["meaningful_change_count"] == 2
        assert len(body["since_last_visit"]["events"]) == 2

        assert len(body["instruments"]) == 1
        assert body["instruments"][0]["top_event"] is not None
    finally:
        await _cleanup_instrument_rows(db, instrument.id)
        await db.execute(delete(WatchlistItem).where(WatchlistItem.watchlist_id == watchlist.id))
        await db.execute(delete(Watchlist).where(Watchlist.id == watchlist.id))
        await db.execute(delete(Instrument).where(Instrument.id == instrument.id))
        await db.commit()


# ---- 6. objective override changes scoring/relevance ---------------------

@pytest.mark.asyncio
async def test_objective_override_changes_tier(client, db, make_user):
    user, token = await make_user()
    instrument = await _mk_instrument(db, _unique_ticker())
    watchlist = await _mk_watchlist(db, user, objective="GROWTH")
    item = await _add_item(db, watchlist, instrument)
    await db.commit()

    detected_at = item.added_at + timedelta(minutes=1)
    try:
        # 3% down-move: magnitude_normalized = 0.625 (between floor and cap)
        # GROWTH: MEDIUM relevance -> composite 0.375 -> MEDIUM tier
        # STABILITY: HIGH relevance -> composite 0.625 -> HIGH tier
        price_move = ChangeEvent(
            instrument_id=str(instrument.id), event_type="PRICE_MOVE",
            previous_value=Decimal("100.00"), current_value=Decimal("97.00"), delta=Decimal("-3.0"),
            detected_at=detected_at, reason="price_moved_down_3.0pct",
            details={"previous_price": "100.00", "current_price": "97.00",
                     "pct_change": "-3.0", "threshold_pct": "2.0"},
        )
        db.add(change_event_to_market_event(price_move, ticker=instrument.ticker, data_quality="FRESH", source="api_test"))
        await db.commit()

        default_response = await client.get(f"/watchlists/{watchlist.id}", headers=_auth(token))
        override_response = await client.get(
            f"/watchlists/{watchlist.id}", params={"objective": "STABILITY"}, headers=_auth(token))

        assert default_response.status_code == 200
        assert override_response.status_code == 200

        default_body = default_response.json()
        override_body = override_response.json()

        assert default_body["objective"] == "GROWTH"
        assert override_body["objective"] == "STABILITY"

        default_event = default_body["since_last_visit"]["events"][0]
        override_event = override_body["since_last_visit"]["events"][0]

        assert default_event["attention_tier"] == "MEDIUM"
        assert override_event["attention_tier"] == "HIGH"
        assert default_event["objective_relevance"] != override_event["objective_relevance"]
    finally:
        await _cleanup_instrument_rows(db, instrument.id)
        await db.execute(delete(WatchlistItem).where(WatchlistItem.watchlist_id == watchlist.id))
        await db.execute(delete(Watchlist).where(Watchlist.id == watchlist.id))
        await db.execute(delete(Instrument).where(Instrument.id == instrument.id))
        await db.commit()


# ---- 7. STALE event includes disclosure -----------------------------------

@pytest.mark.asyncio
async def test_stale_event_includes_disclosure(client, db, make_user):
    user, token = await make_user()
    instrument = await _mk_instrument(db, _unique_ticker())
    watchlist = await _mk_watchlist(db, user, objective="GROWTH")
    item = await _add_item(db, watchlist, instrument)
    await db.commit()

    detected_at = item.added_at + timedelta(minutes=1)
    try:
        price_move = ChangeEvent(
            instrument_id=str(instrument.id), event_type="PRICE_MOVE",
            previous_value=Decimal("100.00"), current_value=Decimal("106.00"), delta=Decimal("6.0"),
            detected_at=detected_at, reason="price_moved_up_6.0pct",
            details={"previous_price": "100.00", "current_price": "106.00",
                     "pct_change": "6.0", "threshold_pct": "2.0"},
        )
        db.add(change_event_to_market_event(price_move, ticker=instrument.ticker, data_quality="STALE", source="api_test"))
        await db.commit()

        response = await client.get(f"/watchlists/{watchlist.id}", headers=_auth(token))
        assert response.status_code == 200
        event = response.json()["since_last_visit"]["events"][0]

        assert event["data_status"]["state"] == "STALE"
        assert event["data_status"]["message"] is not None
        assert "last known price" in event["data_status"]["message"]
        assert "0.5" not in event["data_status"]["message"]
        assert "50%" not in event["data_status"]["message"]
    finally:
        await _cleanup_instrument_rows(db, instrument.id)
        await db.execute(delete(WatchlistItem).where(WatchlistItem.watchlist_id == watchlist.id))
        await db.execute(delete(Watchlist).where(Watchlist.id == watchlist.id))
        await db.execute(delete(Instrument).where(Instrument.id == instrument.id))
        await db.commit()


# ---- 8. UNAVAILABLE event is absent ----------------------------------------

@pytest.mark.asyncio
async def test_unavailable_event_is_absent(client, db, make_user):
    user, token = await make_user()
    instrument = await _mk_instrument(db, _unique_ticker())
    watchlist = await _mk_watchlist(db, user, objective="GROWTH")
    item = await _add_item(db, watchlist, instrument)
    await db.commit()

    detected_at = item.added_at + timedelta(minutes=1)
    try:
        price_move = ChangeEvent(
            instrument_id=str(instrument.id), event_type="PRICE_MOVE",
            previous_value=Decimal("100.00"), current_value=Decimal("106.00"), delta=Decimal("6.0"),
            detected_at=detected_at, reason="price_moved_up_6.0pct",
            details={"previous_price": "100.00", "current_price": "106.00",
                     "pct_change": "6.0", "threshold_pct": "2.0"},
        )
        db.add(change_event_to_market_event(price_move, ticker=instrument.ticker, data_quality="UNAVAILABLE", source="api_test"))
        await db.commit()

        response = await client.get(f"/watchlists/{watchlist.id}", headers=_auth(token))
        assert response.status_code == 200
        body = response.json()

        assert body["since_last_visit"]["meaningful_change_count"] == 0
        assert body["since_last_visit"]["events"] == []
        assert body["instruments"][0]["top_event"] is None
    finally:
        await _cleanup_instrument_rows(db, instrument.id)
        await db.execute(delete(WatchlistItem).where(WatchlistItem.watchlist_id == watchlist.id))
        await db.execute(delete(Watchlist).where(Watchlist.id == watchlist.id))
        await db.execute(delete(Instrument).where(Instrument.id == instrument.id))
        await db.commit()


# ---- 9. GET does not mutate last_viewed_at ---------------------------------

@pytest.mark.asyncio
async def test_get_does_not_mutate_last_viewed_at(client, db, make_user):
    user, token = await make_user()
    watchlist = await _mk_watchlist(db, user, objective="GROWTH")
    await db.commit()
    assert watchlist.last_viewed_at is None

    try:
        response = await client.get(f"/watchlists/{watchlist.id}", headers=_auth(token))
        assert response.status_code == 200
        assert response.json()["last_viewed_at"] is None

        result = await db.execute(select(Watchlist).where(Watchlist.id == watchlist.id))
        reloaded = result.scalar_one()
        assert reloaded.last_viewed_at is None
    finally:
        await db.execute(delete(Watchlist).where(Watchlist.id == watchlist.id))
        await db.commit()


# ---- 10. ExplanationNotImplemented produces 500 ----------------------------

@pytest.mark.asyncio
async def test_explanation_not_implemented_propagates_as_500(client, db, make_user, monkeypatch):
    user, token = await make_user()
    watchlist = await _mk_watchlist(db, user, objective="GROWTH")
    await db.commit()

    from app.services.intelligence import ScoredEvent

    fake_event = ChangeEvent(
        instrument_id="11111111-1111-1111-1111-111111111111",
        event_type="OTHER",  # no explanation template exists for this
        current_value=Decimal("1.0"), delta=Decimal("0"),
        detected_at=datetime.now(timezone.utc), reason="untemplated_event_type", details={},
    )
    fake_scored = ScoredEvent(
        event=fake_event, relevance="LOW", magnitude_normalized=Decimal("0.5"),
        data_confidence=Decimal("1.0"), composite_score=Decimal("0.15"), attention_tier="LOW",
    )

    async def _fake_get_scored_events(db, watchlist_id, objective_override=None):
        return [fake_scored]

    monkeypatch.setattr(
        "app.routers.watchlists.get_scored_events_since_last_visit", _fake_get_scored_events)

    try:
        response = await client.get(f"/watchlists/{watchlist.id}", headers=_auth(token))
        assert response.status_code == 500
        body = response.json()
        assert body["error"]["code"] == "INTERNAL_ERROR"
    finally:
        await db.execute(delete(Watchlist).where(Watchlist.id == watchlist.id))
        await db.commit()
