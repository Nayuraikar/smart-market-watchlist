"""Shared pytest fixtures for DB-touching tests.

Uses the same DATABASE_URL as the running app (docker-compose postgres) —
these tests are NOT run against an isolated test DB, so every fixture
that creates rows is responsible for cleaning them up in a finally block.
This matches the project's existing style: no ORM factory libraries, no
heavyweight fixture layers, plain and explicit.

DATABASE_URL defaults to localhost:5432 (the host-mapped port from
docker-compose.yml) so `pytest` works out of the box on the host without
manually exporting it each time. Still overridable by the environment
(e.g. inside the backend container, where it's already set to
postgres:5432).
"""

import os
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://app:app@localhost:5432/watchlist")

import pytest
from app.db import AsyncSessionLocal


@pytest.fixture
async def db():
    async with AsyncSessionLocal() as session:
        yield session
        await session.rollback()
