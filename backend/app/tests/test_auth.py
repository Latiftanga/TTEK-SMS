"""
Auth flow integration tests.
Run inside Docker: docker compose exec api pytest app/tests/test_auth.py -v
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import hash_password
from app.core.config import settings
from app.models.auth import LoginType, User


@pytest_asyncio.fixture
async def active_user(db_session: AsyncSession) -> User:
    """A normal active staff user with EMAIL login."""
    user = User(
        login_type=LoginType.EMAIL,
        email="teacher@testschool.edu.gh",
        password_hash=hash_password("password123"),
        is_active=True,
        is_superadmin=False,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def inactive_user(db_session: AsyncSession) -> User:
    """A deactivated user — login must be rejected."""
    user = User(
        login_type=LoginType.EMAIL,
        email="suspended@testschool.edu.gh",
        password_hash=hash_password("password123"),
        is_active=False,
        is_superadmin=False,
    )
    db_session.add(user)
    await db_session.flush()
    return user


# ── Login ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, active_user: User):
    resp = await client.post("/auth/login", json={
        "login_type": "EMAIL",
        "identifier": "teacher@testschool.edu.gh",
        "password": "password123",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_returns_valid_jwt(client: AsyncClient, active_user: User):
    """The access_token must be a properly signed JWT with the expected claims."""
    resp = await client.post("/auth/login", json={
        "login_type": "EMAIL",
        "identifier": "teacher@testschool.edu.gh",
        "password": "password123",
    })
    token = resp.json()["access_token"]
    payload = jwt.decode(token, settings.app_secret_key, algorithms=[settings.jwt_algorithm])
    assert "sub" in payload
    assert "exp" in payload


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, active_user: User):
    resp = await client.post("/auth/login", json={
        "login_type": "EMAIL",
        "identifier": "teacher@testschool.edu.gh",
        "password": "wrongpassword",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_user(client: AsyncClient):
    resp = await client.post("/auth/login", json={
        "login_type": "EMAIL",
        "identifier": "nobody@nowhere.com",
        "password": "password123",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_deactivated_user_rejected(client: AsyncClient, inactive_user: User):
    """A suspended user must not receive a token even with the correct password."""
    resp = await client.post("/auth/login", json={
        "login_type": "EMAIL",
        "identifier": "suspended@testschool.edu.gh",
        "password": "password123",
    })
    assert resp.status_code == 403


# ── Token rotation ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_refresh_rotates_token(client: AsyncClient, active_user: User):
    login_resp = await client.post("/auth/login", json={
        "login_type": "EMAIL",
        "identifier": "teacher@testschool.edu.gh",
        "password": "password123",
    })
    old_refresh = login_resp.json()["refresh_token"]

    resp = await client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert resp.status_code == 200
    assert resp.json()["refresh_token"] != old_refresh


@pytest.mark.asyncio
async def test_refresh_old_token_rejected(client: AsyncClient, active_user: User):
    """A refresh token must be invalidated after first use (rotation)."""
    login_resp = await client.post("/auth/login", json={
        "login_type": "EMAIL",
        "identifier": "teacher@testschool.edu.gh",
        "password": "password123",
    })
    old_refresh = login_resp.json()["refresh_token"]

    await client.post("/auth/refresh", json={"refresh_token": old_refresh})

    resp = await client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert resp.status_code == 401


# ── Logout ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_logout_revokes_refresh(client: AsyncClient, active_user: User):
    login_resp = await client.post("/auth/login", json={
        "login_type": "EMAIL",
        "identifier": "teacher@testschool.edu.gh",
        "password": "password123",
    })
    tokens = login_resp.json()

    resp = await client.post("/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 204

    resp = await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 401


# ── /me ───────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_me_endpoint(client: AsyncClient, active_user: User):
    login_resp = await client.post("/auth/login", json={
        "login_type": "EMAIL",
        "identifier": "teacher@testschool.edu.gh",
        "password": "password123",
    })
    access_token = login_resp.json()["access_token"]

    resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "teacher@testschool.edu.gh"
    assert data["is_superadmin"] is False


@pytest.mark.asyncio
async def test_me_requires_auth(client: AsyncClient):
    resp = await client.get("/auth/me")
    assert resp.status_code == 403


# ── Change password ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_change_password_success(client: AsyncClient, active_user: User):
    """After changing the password, old credentials must be rejected."""
    login_resp = await client.post("/auth/login", json={
        "login_type": "EMAIL",
        "identifier": "teacher@testschool.edu.gh",
        "password": "password123",
    })
    access_token = login_resp.json()["access_token"]

    resp = await client.post(
        "/auth/change-password",
        json={"current_password": "password123", "new_password": "NewSecure!99"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 204

    # Old password must now be rejected
    resp = await client.post("/auth/login", json={
        "login_type": "EMAIL",
        "identifier": "teacher@testschool.edu.gh",
        "password": "password123",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_change_password_wrong_current(client: AsyncClient, active_user: User):
    """Providing the wrong current password must be rejected with 400."""
    login_resp = await client.post("/auth/login", json={
        "login_type": "EMAIL",
        "identifier": "teacher@testschool.edu.gh",
        "password": "password123",
    })
    access_token = login_resp.json()["access_token"]

    resp = await client.post(
        "/auth/change-password",
        json={"current_password": "notmypassword", "new_password": "NewSecure!99"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 400
