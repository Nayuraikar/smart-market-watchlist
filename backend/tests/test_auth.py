"""
Authentication tests.

Covers:
  POST /auth/register
  POST /auth/login
  GET  /auth/me

Also verifies that JWTs actually gate a real protected route
(GET /watchlists) end to end, and that passwords are never stored
in plaintext.

Same no-isolated-test-DB convention as the rest of the suite: each
test commits/flushes its own setup data and cleans up in a finally
block.
"""

import uuid

import pytest
from sqlalchemy import delete, select

from app.core.security import decode_access_token, hash_password, verify_password
from app.models import User


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _unique_email() -> str:
    return f"authtest-{uuid.uuid4().hex[:12]}@example.com"


# ============================================================================
# POST /auth/register
# ============================================================================


@pytest.mark.asyncio
async def test_register_valid_user_returns_201(client, db):
    email = _unique_email()

    try:
        response = await client.post(
            "/auth/register",
            json={"email": email, "password": "correct-horse-battery"},
        )

        assert response.status_code == 201

        body = response.json()

        assert body["email"] == email
        assert "id" in body
        assert "created_at" in body
        assert "password" not in body
        assert "password_hash" not in body

    finally:
        await db.execute(delete(User).where(User.email == email))
        await db.commit()


@pytest.mark.asyncio
async def test_register_password_is_hashed_not_plaintext(client, db):
    email = _unique_email()
    raw_password = "correct-horse-battery"

    try:
        response = await client.post(
            "/auth/register",
            json={"email": email, "password": raw_password},
        )

        assert response.status_code == 201

        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one()

        assert user.password_hash != raw_password
        assert user.password_hash.startswith("$2b$")
        assert verify_password(raw_password, user.password_hash) is True

    finally:
        await db.execute(delete(User).where(User.email == email))
        await db.commit()


@pytest.mark.asyncio
async def test_register_duplicate_email_returns_409(client, db):
    email = _unique_email()

    try:
        first = await client.post(
            "/auth/register",
            json={"email": email, "password": "correct-horse-battery"},
        )

        assert first.status_code == 201

        second = await client.post(
            "/auth/register",
            json={"email": email, "password": "another-password-here"},
        )

        assert second.status_code == 409

        body = second.json()

        assert body["error"]["code"] == "EMAIL_TAKEN"

    finally:
        await db.execute(delete(User).where(User.email == email))
        await db.commit()


@pytest.mark.asyncio
async def test_register_password_too_short_returns_422(client):
    response = await client.post(
        "/auth/register",
        json={"email": _unique_email(), "password": "short1"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_password_too_long_returns_422(client):
    response = await client.post(
        "/auth/register",
        json={"email": _unique_email(), "password": "x" * 73},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_invalid_email_returns_422(client):
    response = await client.post(
        "/auth/register",
        json={"email": "not-an-email", "password": "correct-horse-battery"},
    )

    assert response.status_code == 422


# ============================================================================
# POST /auth/login
# ============================================================================


@pytest.mark.asyncio
async def test_login_correct_credentials_returns_token(client, db):
    email = _unique_email()
    password = "correct-horse-battery"

    user = User(email=email, password_hash=hash_password(password))
    db.add(user)
    await db.commit()

    try:
        response = await client.post(
            "/auth/login",
            json={"email": email, "password": password},
        )

        assert response.status_code == 200

        body = response.json()

        assert "access_token" in body
        assert body["token_type"] == "bearer"

        # Token actually decodes to this user's id.
        sub = decode_access_token(body["access_token"])

        assert sub == str(user.id)

    finally:
        await db.execute(delete(User).where(User.email == email))
        await db.commit()


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(client, db):
    email = _unique_email()

    user = User(email=email, password_hash=hash_password("the-real-password"))
    db.add(user)
    await db.commit()

    try:
        response = await client.post(
            "/auth/login",
            json={"email": email, "password": "totally-wrong-password"},
        )

        assert response.status_code == 401

        body = response.json()

        assert body["error"]["code"] == "INVALID_CREDENTIALS"

    finally:
        await db.execute(delete(User).where(User.email == email))
        await db.commit()


@pytest.mark.asyncio
async def test_login_nonexistent_email_returns_401(client):
    response = await client.post(
        "/auth/login",
        json={"email": _unique_email(), "password": "whatever-password"},
    )

    assert response.status_code == 401

    body = response.json()

    assert body["error"]["code"] == "INVALID_CREDENTIALS"


# ============================================================================
# GET /auth/me
# ============================================================================


@pytest.mark.asyncio
async def test_me_with_valid_token_returns_correct_user(client, db):
    email = _unique_email()

    user = User(email=email, password_hash=hash_password("correct-horse-battery"))
    db.add(user)
    await db.commit()

    from app.core.security import create_access_token
    token = create_access_token(str(user.id))

    try:
        response = await client.get("/auth/me", headers=_auth(token))

        assert response.status_code == 200

        body = response.json()

        assert body["id"] == str(user.id)
        assert body["email"] == email

    finally:
        await db.execute(delete(User).where(User.email == email))
        await db.commit()


@pytest.mark.asyncio
async def test_me_without_token_is_rejected(client):
    response = await client.get("/auth/me")

    # HTTPBearer's auto_error path returns 403 when no Authorization
    # header is present at all; get_current_user's own check (for a
    # present-but-invalid token) returns 401. Both are valid "rejected"
    # outcomes here — same convention as test_watchlists_requires_auth.
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_me_with_malformed_token_returns_401(client):
    response = await client.get(
        "/auth/me",
        headers=_auth("this-is-not-a-real-jwt"),
    )

    assert response.status_code == 401

    body = response.json()

    assert body["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_me_with_token_for_deleted_user_returns_401(client, db):
    email = _unique_email()

    user = User(email=email, password_hash=hash_password("correct-horse-battery"))
    db.add(user)
    await db.commit()

    from app.core.security import create_access_token
    token = create_access_token(str(user.id))

    await db.execute(delete(User).where(User.email == email))
    await db.commit()

    response = await client.get("/auth/me", headers=_auth(token))

    assert response.status_code == 401

    body = response.json()

    assert body["error"]["code"] == "UNAUTHORIZED"


# ============================================================================
# JWT actually gates a real protected route end to end
# ============================================================================


@pytest.mark.asyncio
async def test_protected_route_with_invalid_jwt_returns_401(client):
    response = await client.get(
        "/watchlists",
        headers=_auth("garbage.token.value"),
    )

    assert response.status_code == 401

    body = response.json()

    assert body["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_protected_route_with_valid_jwt_succeeds(client, db):
    email = _unique_email()

    user = User(email=email, password_hash=hash_password("correct-horse-battery"))
    db.add(user)
    await db.commit()

    from app.core.security import create_access_token
    token = create_access_token(str(user.id))

    try:
        response = await client.get("/watchlists", headers=_auth(token))

        assert response.status_code == 200
        assert response.json() == []

    finally:
        await db.execute(delete(User).where(User.email == email))
        await db.commit()
