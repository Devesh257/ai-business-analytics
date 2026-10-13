from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.auth import router
from app.api.dependencies import get_db
from app.core.config import settings
from app.models.user import User
from app.security.login_rate_limiter import (
    login_rate_limiter,
)


@pytest.fixture
def client(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={
            "check_same_thread": False
        },
        poolclass=StaticPool,
    )

    User.__table__.create(engine)

    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )

    def override_get_db():
        db = TestingSessionLocal()

        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr(
        settings,
        "auth_jwt_secret",
        "b" * 64,
    )

    monkeypatch.setattr(
        settings,
        "auth_access_token_minutes",
        30,
    )

    monkeypatch.setattr(
        settings,
        "auth_login_max_attempts",
        3,
    )

    monkeypatch.setattr(
        settings,
        "auth_login_window_seconds",
        60,
    )

    login_rate_limiter.reset_all()

    app = FastAPI()
    app.include_router(router)

    app.dependency_overrides[
        get_db
    ] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    login_rate_limiter.reset_all()


def register(client):
    return client.post(
        "/auth/register",
        json={
            "email": "User@Example.com",
            "password":
                "Strong-Password-123!",
        },
    )


def test_register_user(client):
    response = register(client)

    assert response.status_code == 201

    payload = response.json()

    assert (
        payload["email"]
        == "user@example.com"
    )

    assert payload["is_active"] is True

    assert "hashed_password" not in payload
    assert "password" not in payload


def test_duplicate_registration_fails(
    client,
):
    assert register(client).status_code == 201

    assert register(client).status_code == 409


def test_login_returns_access_token(
    client,
):
    register(client)

    response = client.post(
        "/auth/login",
        json={
            "email": "user@example.com",
            "password":
                "Strong-Password-123!",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["token_type"] == "bearer"
    assert payload["access_token"]


def test_wrong_password_is_rejected(
    client,
):
    register(client)

    response = client.post(
        "/auth/login",
        json={
            "email": "user@example.com",
            "password": "Wrong-Password",
        },
    )

    assert response.status_code == 401


def test_me_requires_authentication(
    client,
):
    response = client.get(
        "/auth/me"
    )

    assert response.status_code == 401


def test_authenticated_user_can_get_me(
    client,
):
    register(client)

    login = client.post(
        "/auth/login",
        json={
            "email": "user@example.com",
            "password":
                "Strong-Password-123!",
        },
    )

    token = login.json()[
        "access_token"
    ]

    response = client.get(
        "/auth/me",
        headers={
            "Authorization":
                f"Bearer {token}"
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert (
        payload["email"]
        == "user@example.com"
    )

    assert "hashed_password" not in payload


def test_expired_token_returns_expiry_message(
    client,
):
    from datetime import (
        datetime,
        timedelta,
        timezone,
    )

    import jwt

    from app.security.tokens import (
        ALGORITHM,
    )

    registration = register(client)

    assert (
        registration.status_code
        == 201
    )

    user_id = registration.json()[
        "id"
    ]

    now = datetime.now(
        timezone.utc
    )

    token = jwt.encode(
        {
            "sub": user_id,
            "type": "access",
            "iat": (
                now
                - timedelta(
                    minutes=2
                )
            ),
            "exp": (
                now
                - timedelta(
                    minutes=1
                )
            ),
        },
        settings.auth_jwt_secret,
        algorithm=ALGORITHM,
    )

    response = client.get(
        "/auth/me",
        headers={
            "Authorization":
                f"Bearer {token}"
        },
    )

    assert response.status_code == 401

    assert response.json() == {
        "detail":
            "Authentication session expired."
    }


def test_repeated_login_failures_are_rate_limited(
    client,
):
    register(client)

    for _ in range(
        settings.auth_login_max_attempts
    ):
        response = client.post(
            "/auth/login",
            json={
                "email":
                    "user@example.com",
                "password":
                    "Wrong-Password",
            },
        )

        assert (
            response.status_code
            == 401
        )

        assert response.json() == {
            "detail":
                "Invalid email or password."
        }

    blocked = client.post(
        "/auth/login",
        json={
            "email":
                "user@example.com",
            "password":
                "Strong-Password-123!",
        },
    )

    assert blocked.status_code == 429

    assert blocked.json() == {
        "detail": (
            "Too many login attempts. "
            "Try again later."
        )
    }

    retry_after = int(
        blocked.headers[
            "Retry-After"
        ]
    )

    assert 1 <= retry_after <= (
        settings
        .auth_login_window_seconds
    )


def test_successful_login_resets_failure_count(
    client,
):
    register(client)

    for _ in range(2):
        response = client.post(
            "/auth/login",
            json={
                "email":
                    "user@example.com",
                "password":
                    "Wrong-Password",
            },
        )

        assert (
            response.status_code
            == 401
        )

    success = client.post(
        "/auth/login",
        json={
            "email":
                "user@example.com",
            "password":
                "Strong-Password-123!",
        },
    )

    assert success.status_code == 200

    for _ in range(3):
        response = client.post(
            "/auth/login",
            json={
                "email":
                    "user@example.com",
                "password":
                    "Wrong-Password",
            },
        )

        assert (
            response.status_code
            == 401
        )

    blocked = client.post(
        "/auth/login",
        json={
            "email":
                "user@example.com",
            "password":
                "Strong-Password-123!",
        },
    )

    assert blocked.status_code == 429


def test_unknown_email_is_also_rate_limited(
    client,
):
    for _ in range(
        settings.auth_login_max_attempts
    ):
        response = client.post(
            "/auth/login",
            json={
                "email":
                    "missing@example.com",
                "password":
                    "Wrong-Password",
            },
        )

        assert (
            response.status_code
            == 401
        )

    blocked = client.post(
        "/auth/login",
        json={
            "email":
                "missing@example.com",
            "password":
                "Wrong-Password",
        },
    )

    assert blocked.status_code == 429


def test_rate_limit_uses_normalized_email(
    client,
):
    register(client)

    emails = [
        "USER@example.com",
        "User@Example.com",
        "user@example.com",
    ]

    for email in emails:
        response = client.post(
            "/auth/login",
            json={
                "email": email,
                "password":
                    "Wrong-Password",
            },
        )

        assert (
            response.status_code
            == 401
        )

    blocked = client.post(
        "/auth/login",
        json={
            "email":
                "USER@EXAMPLE.COM",
            "password":
                "Strong-Password-123!",
        },
    )

    assert blocked.status_code == 429
