from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.scored_event import DataStatus, ScoredEventExplanation


class CurrentMarketData(BaseModel):
    price: Decimal | None
    previous_close: Decimal | None
    volume: Decimal | None
    market_cap: Decimal | None
    pe_ratio: Decimal | None
    dividend_yield: Decimal | None
    observed_at: datetime | None
    data_status: DataStatus


class PriceHistoryPoint(BaseModel):
    timestamp: datetime
    price: Decimal
    volume: Decimal


class InstrumentDetailOut(BaseModel):
    instrument_id: UUID
    ticker: str
    name: str
    exchange: str
    objective: str
    current_data: CurrentMarketData | None
    events: list[ScoredEventExplanation]
    price_history: list[PriceHistoryPoint] = Field(default_factory=list)