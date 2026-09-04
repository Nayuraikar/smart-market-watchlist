import pytest


@pytest.mark.asyncio
async def test_health_endpoint_reachable(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_watchlists_requires_auth(client):
    response = await client.get("/watchlists")
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_make_user_and_authed_request(client, db, make_user):
    user, token = await make_user()
    await db.commit()
    response = await client.get("/watchlists", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == []
