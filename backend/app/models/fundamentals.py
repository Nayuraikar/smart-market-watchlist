import uuid
from decimal import Decimal
from datetime import datetime
from sqlalchemy import (
    String, Numeric, BigInteger, ForeignKey, CheckConstraint, DateTime, func, Index
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base


class FundamentalSnapshot(Base):
    __tablename__ = "fundamental_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("instruments.id", ondelete="RESTRICT"), nullable=False
    )
    period: Mapped[str] = mapped_column(String(30), nullable=False)  # raw provider date, e.g. "2026-06-30"
    period_type: Mapped[str] = mapped_column(String(15), nullable=False)

    revenue: Mapped[Decimal | None] = mapped_column(Numeric(24, 4), nullable=True)
    revenue_growth: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    eps: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    eps_growth: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    profit: Mapped[Decimal | None] = mapped_column(Numeric(24, 4), nullable=True)
    profit_growth: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    roe: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    roce: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    debt_to_equity: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    interest_coverage: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    free_cash_flow: Mapped[Decimal | None] = mapped_column(Numeric(24, 4), nullable=True)

    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint("period_type IN ('QUARTERLY','ANNUAL')", name="ck_fundamental_snapshot_period_type"),
        Index("ix_fundamental_snapshots_instrument_snapshot", "instrument_id", "snapshot_at"),
        Index("ix_fundamental_snapshots_instrument_period_snapshot", "instrument_id", "period_type", "snapshot_at"),
    )


class ValuationSnapshot(Base):
    __tablename__ = "valuation_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("instruments.id", ondelete="RESTRICT"), nullable=False
    )
    pe_ratio: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    pb_ratio: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    ev_ebitda: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    price_to_sales: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    fcf_yield: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    fcf_yield_basis: Mapped[str | None] = mapped_column(String(20), nullable=True)
    dividend_yield: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "fcf_yield_basis IS NULL OR fcf_yield_basis IN ('TTM_QUARTERLY','ANNUAL')",
            name="ck_valuation_snapshot_fcf_basis_enum",
        ),
        CheckConstraint(
            "(fcf_yield IS NULL) OR (fcf_yield_basis IS NOT NULL)",
            name="ck_valuation_snapshot_fcf_basis_required",
        ),
        Index("ix_valuation_snapshots_instrument_observed", "instrument_id", "observed_at"),
    )
