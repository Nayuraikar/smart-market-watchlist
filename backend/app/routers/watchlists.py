from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user
from app.models import User, Watchlist, WatchlistItem, Instrument
from app.schemas.watchlist import WatchlistCreate, WatchlistUpdate, WatchlistOut
from app.schemas.watchlist_since_last_visit import (
    WatchlistSinceLastVisitOut,
    SinceLastVisit,
    InstrumentSinceLastVisit,
)
from app.services.last_visit import get_scored_events_since_last_visit
from app.services.explanation import build_explanation
from app.services.intelligence import select_top_event


router = APIRouter(prefix="/watchlists", tags=["watchlists"])


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "error": {
                "code": "NOT_FOUND",
                "message": "Watchlist not found",
                "request_id": None,
            }
        },
    )


async def _get_owned_watchlist(
    db: AsyncSession,
    watchlist_id: UUID,
    user: User,
) -> Watchlist:
    """Fetch a watchlist and enforce ownership.

    Deliberately returns 404 rather than 403 for another user's
    watchlist so the existence of someone else's resource is not
    revealed.

    This is the single ownership check used by every watchlist
    endpoint.
    """
    result = await db.execute(
        select(Watchlist).where(Watchlist.id == watchlist_id)
    )

    watchlist = result.scalar_one_or_none()

    if watchlist is None or watchlist.user_id != user.id:
        raise _not_found()

    return watchlist


@router.post(
    "",
    response_model=WatchlistOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_watchlist(
    payload: WatchlistCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    watchlist = Watchlist(
        user_id=current_user.id,
        name=payload.name,
        objective=payload.objective,
    )

    db.add(watchlist)

    await db.commit()
    await db.refresh(watchlist)

    return watchlist


@router.get(
    "",
    response_model=list[WatchlistOut],
)
async def list_watchlists(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Watchlist).where(
            Watchlist.user_id == current_user.id
        )
    )

    return result.scalars().all()


@router.get(
    "/{watchlist_id}",
    response_model=WatchlistSinceLastVisitOut,
)
async def get_watchlist(
    watchlist_id: UUID,
    objective: str | None = Query(
        default=None,
        pattern="^(GROWTH|VALUE|STABILITY)$",
        description=(
            "Optional: score this read under a different objective "
            "than the watchlist's stored one. Not persisted."
        ),
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Phase 7.4: since-last-visit dashboard read.

    GET is strictly read-only.
    last_viewed_at is NEVER modified here.

    Phase 7.5 provides POST /watchlists/{watchlist_id}/viewed
    as the only endpoint that advances last_viewed_at.
    """

    watchlist = await _get_owned_watchlist(
        db,
        watchlist_id,
        current_user,
    )

    effective_objective = objective or watchlist.objective

    scored_events = await get_scored_events_since_last_visit(
        db,
        watchlist_id,
        effective_objective,
    )

    # Build every explanation once.
    # The same explanation object is reused when determining
    # the top event for each instrument.
    explanation_by_id: dict[int, "ScoredEventExplanation"] = {}
    events_by_instrument: dict[str, list] = {}
    flat_explanations = []

    for scored in scored_events:
        explanation = build_explanation(
            scored,
            effective_objective,
        )

        explanation_by_id[id(scored)] = explanation
        flat_explanations.append(explanation)

        events_by_instrument.setdefault(
            scored.event.instrument_id,
            [],
        ).append(scored)

    items_result = await db.execute(
        select(WatchlistItem, Instrument)
        .join(
            Instrument,
            Instrument.id == WatchlistItem.instrument_id,
        )
        .where(
            WatchlistItem.watchlist_id == watchlist_id
        )
    )

    instruments = []

    for item, instrument in items_result.all():
        instrument_scored = events_by_instrument.get(
            str(instrument.id),
            [],
        )

        top_scored = select_top_event(instrument_scored)

        top_event = (
            explanation_by_id.get(id(top_scored))
            if top_scored is not None
            else None
        )

        instruments.append(
            InstrumentSinceLastVisit(
                instrument_id=instrument.id,
                ticker=instrument.ticker,
                name=instrument.name,
                exchange=instrument.exchange,
                added_at=item.added_at,
                top_event=top_event,
            )
        )

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


@router.post(
    "/{watchlist_id}/viewed",
    response_model=WatchlistOut,
)
async def mark_watchlist_viewed(
    watchlist_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Phase 7.5: mark a watchlist as viewed.

    This is the ONLY endpoint that advances last_viewed_at.

    GET /watchlists/{watchlist_id} remains strictly read-only.

    Ownership is enforced through _get_owned_watchlist(), so
    non-owners receive 404 rather than 403.
    """

    watchlist = await _get_owned_watchlist(
        db,
        watchlist_id,
        current_user,
    )

    watchlist.last_viewed_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(watchlist)

    return watchlist


@router.patch(
    "/{watchlist_id}",
    response_model=WatchlistOut,
)
async def update_watchlist(
    watchlist_id: UUID,
    payload: WatchlistUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    watchlist = await _get_owned_watchlist(
        db,
        watchlist_id,
        current_user,
    )

    if payload.name is not None:
        watchlist.name = payload.name

    if payload.objective is not None:
        watchlist.objective = payload.objective

    await db.commit()
    await db.refresh(watchlist)

    return watchlist


@router.delete(
    "/{watchlist_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_watchlist(
    watchlist_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    watchlist = await _get_owned_watchlist(
        db,
        watchlist_id,
        current_user,
    )

    await db.delete(watchlist)
    await db.commit()