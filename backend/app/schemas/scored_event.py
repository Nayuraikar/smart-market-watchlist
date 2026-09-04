"""Response shape for Phase 7.3's explanation contract
(RELEVANCE_ATTENTION_SPEC.md section 7). Identifying metadata
(instrument_id/event_type/detected_at) sits alongside the frozen 8-field
contract, not mixed into it — the 8 fields below are exactly section 7's
list, no more, no fewer.
"""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class DataStatus(BaseModel):
    state: Literal["FRESH", "STALE", "UNAVAILABLE"]
    message: str | None


class ScoredEventExplanation(BaseModel):
    # Identifying metadata — not part of the frozen 8-field contract.
    instrument_id: str
    event_type: str
    detected_at: datetime

    # ---- RELEVANCE_ATTENTION_SPEC.md section 7 — frozen, 8 fields ----
    what_happened: str
    magnitude: str
    benchmark_comparison: str | None
    objective_relevance: str
    data_status: DataStatus
    data_confidence: Decimal  # tests/debugging only — never rendered as a %
    attention_tier: Literal["HIGH", "MEDIUM", "LOW"]
    composite_score: Decimal  # tests/debugging only
