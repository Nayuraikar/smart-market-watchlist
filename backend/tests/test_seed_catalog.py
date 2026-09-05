import pytest
from sqlalchemy import delete, select

from app.models import Instrument, Watchlist, WatchlistItem
from app.seed import TICKERS, ensure_instruments_exist


REQUIRED_TICKERS = {
    "TCS.NS", "LTM.NS", "PERSISTENT.NS", "COFORGE.NS",
    "HDFCBANK.NS", "SHRIRAMFIN.NS", "RELIANCE.NS", "SUNPHARMA.NS",
    "MARUTI.NS", "ITC.NS", "TATASTEEL.NS", "BHARTIARTL.NS", "LT.NS",
}


def test_curated_catalog_is_unique_and_cross_sector():
    assert len(TICKERS) == 57
    assert len(TICKERS) == len(set(TICKERS))
    assert REQUIRED_TICKERS <= set(TICKERS)
    assert all(ticker.endswith(".NS") for ticker in TICKERS)


@pytest.mark.asyncio
async def test_seeded_new_instrument_can_be_added_to_watchlist(client, db, make_user):
    # Phase A is DB-only and idempotent, so this also verifies the seed does
    # not require Yahoo availability in order to make the catalog usable.
    await ensure_instruments_exist()

    result = await db.execute(
        select(Instrument.ticker).where(Instrument.ticker.in_(REQUIRED_TICKERS))
    )
    assert REQUIRED_TICKERS <= set(result.scalars())

    user, token = await make_user()
    watchlist = Watchlist(user_id=user.id, name="Expanded catalog", objective="GROWTH")
    db.add(watchlist)
    await db.commit()
    await db.refresh(watchlist)

    try:
        response = await client.post(
            f"/watchlists/{watchlist.id}/stocks",
            json={"ticker": "COFORGE.NS"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 201
        assert response.json()["ticker"] == "COFORGE.NS"
    finally:
        await db.execute(delete(WatchlistItem).where(WatchlistItem.watchlist_id == watchlist.id))
        await db.execute(delete(Watchlist).where(Watchlist.id == watchlist.id))
        await db.commit()
