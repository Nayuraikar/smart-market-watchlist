import uuid
from decimal import Decimal
from datetime import datetime
from sqlalchemy import (
    String, Numeric, BigInteger, ForeignKey, CheckConstraint, DateTime, func, Index
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base


class MarketState(Base):
    __tablename__ = "market_state"

    instrument_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("instruments.id", ondelete="RESTRICT"), primary_key=True
    )
    price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    previous_close: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    volume: Mapped[Decimal] = mapped_column(Numeric(24, 4), nullable=False)
    market_cap: Mapped[Decimal | None] = mapped_column(Numeric(24, 4), nullable=True)
    pe_ratio: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    dividend_yield: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ingestion_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    data_quality: Mapped[str] = mapped_column(String(20), nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)

    __table_args__ = (
        CheckConstraint("price > 0", name="ck_market_state_price_positive"),
        CheckConstraint("previous_close IS NULL OR previous_close >= 0", name="ck_market_state_prev_close_nonneg"),
        CheckConstraint("volume >= 0", name="ck_market_state_volume_nonneg"),
        CheckConstraint("data_quality IN ('FRESH','STALE','UNAVAILABLE')", name="ck_market_state_data_quality"),
    )


class MarketHistory(Base):
    __tablename__ = "market_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("instruments.id", ondelete="RESTRICT"), nullable=False
    )
    open_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    high_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    low_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    close_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    volume: Mapped[Decimal] = mapped_column(Numeric(24, 4), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint("open_price > 0 AND high_price > 0 AND low_price > 0 AND close_price > 0",
                         name="ck_market_history_prices_positive"),
        CheckConstraint("volume >= 0", name="ck_market_history_volume_nonneg"),
        CheckConstraint(
            "high_price >= low_price "
            "AND open_price BETWEEN low_price AND high_price "
            "AND close_price BETWEEN low_price AND high_price",
            name="ck_market_history_ohlc_consistency",
        ),
        Index("ix_market_history_instrument_ts", "instrument_id", "timestamp"),
    )
