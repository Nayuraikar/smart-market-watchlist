from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user
from app.models import User, Watchlist, Instrument, WatchlistItem
from app.schemas.watchlist import StockAdd, StockOut
from app.schemas.instrument_detail import CurrentMarketData, InstrumentDetailOut
from app.models import MarketEvent, MarketState
from app.services.explanation import build_explanation
from app.services.last_visit import score_events_for_watchlist
from app.services.event_persistence import market_event_to_change_event, LegacyEventNotConvertible
from app.services.intelligence import Objective

router = APIRouter(prefix="/watchlists/{watchlist_id}/stocks", tags=["stocks"])


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error": {"code": "NOT_FOUND", "message": "Watchlist not found", "request_id": None}},
    )


def _instrument_not_found(ticker: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error": {"code": "INSTRUMENT_NOT_FOUND", "message": f"No instrument found for ticker '{ticker}'", "request_id": None}},
    )


def _already_in_watchlist() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"error": {"code": "ALREADY_IN_WATCHLIST", "message": "This instrument is already in the watchlist", "request_id": None}},
    )


async def _get_owned_watchlist(db: AsyncSession, watchlist_id: UUID, user: User) -> Watchlist:
    """Same ownership chokepoint pattern as watchlists.py — 404, not 403,
    for another user's watchlist."""
    result = await db.execute(select(Watchlist).where(Watchlist.id == watchlist_id))
    watchlist = result.scalar_one_or_none()
    if watchlist is None or watchlist.user_id != user.id:
        raise _not_found()
    return watchlist


@router.get("", response_model=list[StockOut])
async def list_stocks(
    watchlist_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_owned_watchlist(db, watchlist_id, current_user)

    result = await db.execute(
        select(Instrument, WatchlistItem.added_at)
        .join(WatchlistItem, WatchlistItem.instrument_id == Instrument.id)
        .where(WatchlistItem.watchlist_id == watchlist_id)
    )
    rows = result.all()
    return [
        StockOut(
            instrument_id=instrument.id,
            ticker=instrument.ticker,
            name=instrument.name,
            exchange=instrument.exchange,
            added_at=added_at,
        )
        for instrument, added_at in rows
    ]


@router.get("/{instrument_id}", response_model=InstrumentDetailOut)
async def get_stock_detail(
    watchlist_id: UUID,
    instrument_id: UUID,
    objective: Objective | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    watchlist = await _get_owned_watchlist(db, watchlist_id, current_user)

    membership = await db.execute(
        select(WatchlistItem, Instrument).join(
            Instrument,
            Instrument.id == WatchlistItem.instrument_id,
        ).where(
            WatchlistItem.watchlist_id == watchlist_id,
            WatchlistItem.instrument_id == instrument_id,
        )
    )
    row = membership.one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Instrument not found in this watchlist", "request_id": None}},
        )

    item, instrument = row
    state_result = await db.execute(
        select(MarketState).where(MarketState.instrument_id == instrument_id)
    )
    market_state = state_result.scalar_one_or_none()

    current_data = None
    if market_state is not None:
        data_status = {
            "state": market_state.data_quality,
            "message": (
                "This is the last known market state and may not reflect the most recent activity."
                if market_state.data_quality == "STALE"
                else "Market data is unavailable."
                if market_state.data_quality == "UNAVAILABLE"
                else None
            ),
        }
        current_data = CurrentMarketData(
            price=market_state.price if market_state.data_quality != "UNAVAILABLE" else None,
            previous_close=market_state.previous_close if market_state.data_quality != "UNAVAILABLE" else None,
            volume=market_state.volume if market_state.data_quality != "UNAVAILABLE" else None,
            market_cap=market_state.market_cap if market_state.data_quality != "UNAVAILABLE" else None,
            pe_ratio=market_state.pe_ratio if market_state.data_quality != "UNAVAILABLE" else None,
            dividend_yield=market_state.dividend_yield if market_state.data_quality != "UNAVAILABLE" else None,
            observed_at=market_state.observed_at,
            data_status=data_status,
        )

    events_result = await db.execute(
        select(MarketEvent).where(
            MarketEvent.instrument_id == instrument_id,
            MarketEvent.timestamp > item.added_at,
        ).order_by(MarketEvent.timestamp.desc())
    )
    event_rows = events_result.scalars().all()
    convertible_events = []
    for event_row in event_rows:
        try:
            market_event_to_change_event(event_row)
            convertible_events.append(event_row)
        except LegacyEventNotConvertible:
            continue

    effective_objective = objective or watchlist.objective
    scored_events = score_events_for_watchlist(convertible_events, effective_objective)
    explanations = [
        build_explanation(scored, effective_objective)
        for scored in scored_events
    ]

    return InstrumentDetailOut(
        instrument_id=instrument.id,
        ticker=instrument.ticker,
        name=instrument.name,
        exchange=instrument.exchange,
        objective=effective_objective,
        current_data=current_data,
        events=explanations,
    )


@router.post("", response_model=StockOut, status_code=status.HTTP_201_CREATED)
async def add_stock(
    watchlist_id: UUID,
    payload: StockAdd,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_owned_watchlist(db, watchlist_id, current_user)

    ticker = payload.ticker.strip().upper()
    result = await db.execute(select(Instrument).where(Instrument.ticker == ticker))
    instrument = result.scalar_one_or_none()
    if instrument is None:
        raise _instrument_not_found(ticker)

    # Pre-check rather than relying solely on the IntegrityError catch,
    # so we can return a clean 409 without poisoning the session on most calls.
    existing = await db.execute(
        select(WatchlistItem).where(
            WatchlistItem.watchlist_id == watchlist_id,
            WatchlistItem.instrument_id == instrument.id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise _already_in_watchlist()

    item = WatchlistItem(watchlist_id=watchlist_id, instrument_id=instrument.id)
    db.add(item)
    try:
        await db.commit()
    except IntegrityError:
        # Race-condition fallback: two concurrent adds could both pass the
        # pre-check before either commits. The composite PK is the real guard.
        await db.rollback()
        raise _already_in_watchlist()

    await db.refresh(item)
    return StockOut(
        instrument_id=instrument.id,
        ticker=instrument.ticker,
        name=instrument.name,
        exchange=instrument.exchange,
        added_at=item.added_at,
    )


@router.delete("/{instrument_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_stock(
    watchlist_id: UUID,
    instrument_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_owned_watchlist(db, watchlist_id, current_user)

    result = await db.execute(
        select(WatchlistItem).where(
            WatchlistItem.watchlist_id == watchlist_id,
            WatchlistItem.instrument_id == instrument_id,
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Instrument not found in this watchlist", "request_id": None}},
        )

    await db.delete(item)
    await db.commit()