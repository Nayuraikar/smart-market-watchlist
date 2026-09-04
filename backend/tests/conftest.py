"""Shared pytest fixtures.

DATABASE_URL and JWT_SECRET both default here (before any app import)
so `pytest` works out of the box on the host without manually exporting
them each time — mirrors app/db.py and app/core/security.py's hard
os.environ[...] requirements. Still overridable by the environment
(e.g. inside the backend container, where both are already set).
"""

import os
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://app:app@localhost:5432/watchlist")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")

import uuid

import pytest
import httpx

from app.db import AsyncSessionLocal
from app.core.security import create_access_token, hash_password
from app.models import User


@pytest.fixture
async def db():
    async with AsyncSessionLocal() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client():
    """httpx AsyncClient wired directly to the real FastAPI app via
    ASGITransport — no mocking, hits the real routers/deps/DB exactly as
    a live request would (same no-isolated-test-DB philosophy as the db
    fixture above)."""
    from app.main import app
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def make_user(db):
    """Factory fixture: make_user() -> (User, bearer_token). Each call
    creates a fresh row with a unique email; caller is responsible for
    cleanup (delete the returned user, per this project's no-isolated-
    test-DB convention)."""
    created_users = []

    async def _make_user():
        user = User(
            email=f"apitest-{uuid.uuid4().hex[:12]}@test.local",
            password_hash=hash_password("irrelevant-for-tests"),
        )
        db.add(user)
        await db.flush()
        token = create_access_token(str(user.id))
        created_users.append(user)
        return user, token

    yield _make_user

    for user in created_users:
        await db.delete(user)
    await db.commit()
