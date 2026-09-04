from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator


class MarketObservation(BaseModel):
    """Internal contract every provider must produce. Deliberately has NO
    price>0/volume>=0 constraints here — those are a separate pipeline step,
    not structural validation. This model only enforces shape and types."""
    ticker: str = Field(min_length=1, max_length=30)
    price: Decimal
    previous_close: Decimal | None = None
    volume: Decimal
    market_cap: Decimal | None = None
    pe_ratio: Decimal | None = None
    dividend_yield: Decimal | None = None
    observed_at: datetime
    source: str

    @field_validator("observed_at")
    @classmethod
    def must_be_tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        return v
