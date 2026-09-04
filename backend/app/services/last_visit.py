# backend/app/services/last_visit.py
"""Per-watchlist 'what changed since you last looked' pipeline.

get_since_last_visit_events() answers "which raw MarketEvent rows
happened since the boundary" (Decision 13). score_events_for_watchlist()
is the Phase 7.2 read-time integration: converts those rows back to
ChangeEvents and runs them through intelligence.score_event() per the
watchlist's objective — scoring is never baked in at ingestion time
(Decision 16, Option A), only computed here, at GET time.
"""

from sqlalchemy import select, case, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Watchlist, WatchlistItem, MarketEvent
from app.services.event_persistence import market_event_to_change_event, LegacyEventNotConvertible
from app.services.intelligence import score_event, ScoredEvent, Objective, RELEVANCE_WEIGHT


def _comparison_boundary():
    """Decision 13: added_at if never viewed, else max(last_viewed_at, added_at)."""
    return case(
        (Watchlist.last_viewed_at.is_(None), WatchlistItem.added_at),
        else_=func.greatest(Watchlist.last_viewed_at, WatchlistItem.added_at),
    )


async def get_since_last_visit_events(db: AsyncSession, watchlist_id) -> list[MarketEvent]:
    boundary = _comparison_boundary()
    stmt = (
        select(MarketEvent)
        .join(WatchlistItem, WatchlistItem.instrument_id == MarketEvent.instrument_id)
        .join(Watchlist, Watchlist.id == WatchlistItem.watchlist_id)
        .where(
            WatchlistItem.watchlist_id == watchlist_id,
            MarketEvent.timestamp > boundary,
        )
    )
    result = await db.execute(stmt)
    return result.scalars().all()


def score_events_for_watchlist(
    events: list[MarketEvent], objective: Objective,
) -> list[ScoredEvent]:
    """Converts each raw MarketEvent row back to a ChangeEvent and runs it
    through the real intelligence.score_event() pipeline for the given
    objective. Sorted by composite_score descending, ties broken by
    relevance_weight then magnitude_normalized (section 4 rule 3).

    Two categories of event are silently excluded, each for a distinct,
    documented reason — neither is a bug:
      - LegacyEventNotConvertible: Phase 5 placeholder rows predating
        Decision 16's canonical details contract.
      - score_event() returns None: data_confidence == 0 (UNAVAILABLE)
        or NotScoreable (event_type/sub-type with no scoring curve yet).
    A malformed details contract (ValueError from get_relevance's
    FUNDAMENTAL_CHANGE/CORPORATE_ACTION validation) is NOT swallowed
    here — that's a genuine data bug and must propagate, per
    score_event()'s own contract.
    """
    scored: list[ScoredEvent] = []
    for row in events:
        try:
            change_event = market_event_to_change_event(row)
        except LegacyEventNotConvertible:
            continue

        data_quality = row.data_quality or "UNAVAILABLE"
        result = score_event(change_event, objective, data_quality)
        if result is not None:
            scored.append(result)

    scored.sort(
        key=lambda s: (s.composite_score, RELEVANCE_WEIGHT[s.relevance], s.magnitude_normalized),
        reverse=True,
    )
    return scored


async def get_scored_events_since_last_visit(
    db: AsyncSession, watchlist_id,
) -> list[ScoredEvent]:
    """Full orchestration: fetches the watchlist (for its objective) and
    every MarketEvent since the last-visit boundary, then scores them.
    Returns [] if the watchlist doesn't exist — ownership/404 enforcement
    is the router layer's job (via the existing _get_owned_watchlist
    pattern), not this function's."""
    result = await db.execute(select(Watchlist).where(Watchlist.id == watchlist_id))
    watchlist = result.scalar_one_or_none()
    if watchlist is None:
        return []

    events = await get_since_last_visit_events(db, watchlist_id)
    return score_events_for_watchlist(events, watchlist.objective)
