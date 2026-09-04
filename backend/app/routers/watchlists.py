from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user
from app.models import User, Watchlist, WatchlistItem, Instrument
from app.schemas.watchlist import WatchlistCreate, WatchlistUpdate, WatchlistOut
from app.schemas.watchlist_since_last_visit import (
    WatchlistSinceLastVisitOut, SinceLastVisit, InstrumentSinceLastVisit,
)
from app.services.last_visit import get_scored_events_since_last_visit
from app.services.explanation import build_explanation
from app.services.intelligence import select_top_event

router = APIRouter(prefix="/watchlists", tags=["watchlists"])


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error": {"code": "NOT_FOUND", "message": "Watchlist not found", "request_id": None}},
    )


async def _get_owned_watchlist(db: AsyncSession, watchlist_id: UUID, user: User) -> Watchlist:
    """Fetches a watchlist and enforces ownership in one place.
    Deliberately returns 404 (not 403) for another user's watchlist —
    existence of someone else's resource is not confirmed to a non-owner.
    This is the ONLY ownership check in the router — every other endpoint
    below, including the Phase 7.4 since-last-visit read, calls this and
    nothing else duplicates its logic."""
    result = await db.execute(select(Watchlist).where(Watchlist.id == watchlist_id))
    watchlist = result.scalar_one_or_none()
    if watchlist is None or watchlist.user_id != user.id:
        raise _not_found()
    return watchlist


@router.post("", response_model=WatchlistOut, status_code=status.HTTP_201_CREATED)
async def create_watchlist(
    payload: WatchlistCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    watchlist = Watchlist(user_id=current_user.id, name=payload.name, objective=payload.objective)
    db.add(watchlist)
    await db.commit()
    await db.refresh(watchlist)
    return watchlist


@router.get("", response_model=list[WatchlistOut])
async def list_watchlists(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Watchlist).where(Watchlist.user_id == current_user.id))
    return result.scalars().all()


@router.get("/{watchlist_id}", response_model=WatchlistSinceLastVisitOut)
async def get_watchlist(
    watchlist_id: UUID,
    objective: str | None = Query(
        default=None, pattern="^(GROWTH|VALUE|STABILITY)$",
        description="Optional: score this read under a different objective "
                    "than the watchlist's stored one. Not persisted.",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Phase 7.4: the since-last-visit dashboard read. GET is read-only —
    last_viewed_at is NEVER written here (that's Phase 7.5's POST
    /viewed). LegacyEventNotConvertible and NotScoreable/UNAVAILABLE
    events are already filtered inside get_scored_events_since_last_visit
    -> score_events_for_watchlist (Phase 7.2); this endpoint adds no
    duplicate filtering of its own, per Decision (req 6).

    ExplanationNotImplemented from build_explanation() is deliberately
    NOT caught here: it means a scoreable event_type has no explanation
    template, a developer invariant violation, not a data problem.
    FastAPI's default exception handling turns any uncaught exception
    into a 500 — that propagation IS the fail-loud behavior (req 5)."""
    watchlist = await _get_owned_watchlist(db, watchlist_id, current_user)
    effective_objective = objective or watchlist.objective

    scored_events = await get_scored_events_since_last_visit(db, watchlist_id, effective_objective)

    # Build every explanation once; keyed by identity so the per-instrument
    # top_event below reuses the same explanation object instead of
    # re-deriving it (build_explanation is pure, but there's no reason to
    # call it twice for the same ScoredEvent).
    explanation_by_id: dict[int, "ScoredEventExplanation"] = {}
    events_by_instrument: dict[str, list] = {}
    flat_explanations = []

    for scored in scored_events:
        explanation = build_explanation(scored, effective_objective)
        explanation_by_id[id(scored)] = explanation
        flat_explanations.append(explanation)
        events_by_instrument.setdefault(scored.event.instrument_id, []).append(scored)

    items_result = await db.execute(
        select(WatchlistItem, Instrument)
        .join(Instrument, Instrument.id == WatchlistItem.instrument_id)
        .where(WatchlistItem.watchlist_id == watchlist_id)
    )

    instruments = []
    for item, instrument in items_result.all():
        instrument_scored = events_by_instrument.get(str(instrument.id), [])
        top_scored = select_top_event(instrument_scored)
        top_event = explanation_by_id.get(id(top_scored)) if top_scored is not None else None
        instruments.append(InstrumentSinceLastVisit(
            instrument_id=instrument.id,
            ticker=instrument.ticker,
            name=instrument.name,
            exchange=instrument.exchange,
            added_at=item.added_at,
            top_event=top_event,
        ))

    return WatchlistSinceLastVisitOut(
        watchlist_id=watchlist.id,
        objective=effective_objective,
        last_viewed_at=watchlist.last_viewed_at,
        since_last_visit=SinceLastVisit(
            meaningful_change_count=len(flat_explanations),
            events=flat_explanations,
        ),
        instruments=instruments,
    )


@router.patch("/{watchlist_id}", response_model=WatchlistOut)
async def update_watchlist(
    watchlist_id: UUID,
    payload: WatchlistUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    watchlist = await _get_owned_watchlist(db, watchlist_id, current_user)
    if payload.name is not None:
        watchlist.name = payload.name
    if payload.objective is not None:
        watchlist.objective = payload.objective
    await db.commit()
    await db.refresh(watchlist)
    return watchlist


@router.delete("/{watchlist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_watchlist(
    watchlist_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    watchlist = await _get_owned_watchlist(db, watchlist_id, current_user)
    await db.delete(watchlist)
    await db.commit()
