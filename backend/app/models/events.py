import uuid
from datetime import datetime
from sqlalchemy import String, BigInteger, ForeignKey, CheckConstraint, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base

ALLOWED_EVENT_TYPES = (
    "PRICE_MOVE", "VOLUME_SURGE", "52W_HIGH", "52W_LOW",
    "RELATIVE_OUTPERFORMANCE", "FUNDAMENTAL_CHANGE",
    "CORPORATE_ACTION", "EARNINGS", "OTHER",
)


class MarketEvent(Base):
    __tablename__ = "market_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("instruments.id", ondelete="RESTRICT"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    importance: Mapped[str] = mapped_column(String(10), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "event_type IN ('PRICE_MOVE','VOLUME_SURGE','52W_HIGH','52W_LOW',"
            "'RELATIVE_OUTPERFORMANCE','FUNDAMENTAL_CHANGE','CORPORATE_ACTION','EARNINGS','OTHER')",
            name="ck_market_event_type",
        ),
        CheckConstraint("importance IN ('HIGH','MEDIUM','LOW')", name="ck_market_event_importance"),
        Index("ix_market_events_instrument_ts", "instrument_id", "timestamp"),
        Index("ix_market_events_instrument_importance_ts", "instrument_id", "importance", "timestamp"),
    )
