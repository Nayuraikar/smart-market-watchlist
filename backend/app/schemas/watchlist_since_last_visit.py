"""Response shape for Phase 7.4's GET /watchlists/{id} endpoint. A
superset of the plain watchlist fields (watchlist_id/objective/
last_viewed_at) plus the since-last-visit event feed and the
per-instrument roster. Built entirely from Phase 7.1-7.3 outputs
(ScoredEvent -> ScoredEventExplanation via build_explanation(),
top_event via intelligence.select_top_event()) — no new scoring
logic here, this module is presentation shape only.
"""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel

from app.schemas.scored_event import ScoredEventExplanation


class InstrumentSinceLastVisit(BaseModel):
    instrument_id: UUID
    ticker: str
    name: str
    exchange: str
    added_at: datetime
    top_event: ScoredEventExplanation | None


class SinceLastVisit(BaseModel):
    meaningful_change_count: int
    events: list[ScoredEventExplanation]


class WatchlistSinceLastVisitOut(BaseModel):
    watchlist_id: UUID
    objective: str
    last_viewed_at: datetime | None
    since_last_visit: SinceLastVisit
    instruments: list[InstrumentSinceLastVisit]
