from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class WatchlistCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    objective: str = Field(pattern="^(GROWTH|VALUE|STABILITY)$")


class WatchlistUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    objective: str | None = Field(default=None, pattern="^(GROWTH|VALUE|STABILITY)$")


class WatchlistOut(BaseModel):
    id: UUID
    name: str
    objective: str
    last_viewed_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class WatchlistItemCreate(BaseModel):
    instrument_id: UUID
