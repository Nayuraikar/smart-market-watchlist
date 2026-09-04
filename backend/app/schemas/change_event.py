"""ChangeEvent — the frozen output contract for Phase 6's detect_change().
Pure data shape. No DB session, no provider, no FastAPI dependency may
ever appear in this file — that's what keeps the intelligence layer
independently testable per BUILD_ROADMAP.md Phase 6's goal."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field

# Locked in PRODUCT_SPEC.md Phase 1 — do not add a 10th type mid-build.
EVENT_TYPES = (
    "PRICE_MOVE", "VOLUME_SURGE", "52W_HIGH", "52W_LOW",
    "RELATIVE_OUTPERFORMANCE", "FUNDAMENTAL_CHANGE",
    "CORPORATE_ACTION", "EARNINGS", "OTHER",
)


class Importance(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ChangeEvent(BaseModel):
    instrument_id: str  # UUID as str — pure layer doesn't import DB UUID types
    event_type: str = Field(pattern="^(" + "|".join(EVENT_TYPES) + ")$")

    previous_value: Decimal | None = None
    current_value: Decimal
    delta: Decimal  # current_value - previous_value, or provider-specific meaning per event_type

    importance: Importance = Importance.LOW  # set later by the attention engine (6.12), not detect_change() itself

    detected_at: datetime
    baseline_timestamp: datetime | None = None  # what "previous" was compared against

    reason: str  # short machine-oriented label, e.g. "price_moved_2pct"
    details: dict[str, Any] = Field(default_factory=dict)  # human-facing explanation inputs, filled in by 6.13

    class Config:
        use_enum_values = True
