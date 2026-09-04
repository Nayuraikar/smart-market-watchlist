from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user
from app.models import User, Watchlist
from app.schemas.watchlist import WatchlistCreate, WatchlistUpdate, WatchlistOut

router = APIRouter(prefix="/watchlists", tags=["watchlists"])


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error": {"code": "NOT_FOUND", "message": "Watchlist not found", "request_id": None}},
    )


async def _get_owned_watchlist(db: AsyncSession, watchlist_id: UUID, user: User) -> Watchlist:
    """Fetches a watchlist and enforces ownership in one place.
    Deliberately returns 404 (not 403) for another user's watchlist —
    existence of someone else's resource is not confirmed to a non-owner."""
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


@router.get("/{watchlist_id}", response_model=WatchlistOut)
async def get_watchlist(
    watchlist_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _get_owned_watchlist(db, watchlist_id, current_user)


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
