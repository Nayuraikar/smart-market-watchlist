"""add market_event data_quality snapshot (Decision 15)

Revision ID: b26bf74ee8a1
Revises: d3698e0a0a61
Create Date: 2026-09-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b26bf74ee8a1"
down_revision: Union[str, None] = "d3698e0a0a61"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "market_events",
        sa.Column("data_quality", sa.String(length=20), nullable=True),
    )
    op.create_check_constraint(
        "ck_market_event_data_quality",
        "market_events",
        "data_quality IS NULL OR data_quality IN ('FRESH','STALE','UNAVAILABLE')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_market_event_data_quality", "market_events", type_="check")
    op.drop_column("market_events", "data_quality")
