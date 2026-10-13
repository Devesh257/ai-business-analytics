import uuid

import jwt
import pytest

from app.core.config import settings
from app.security.tokens import (
    ALGORITHM,
    InvalidAccessToken,
    create_access_token,
    decode_access_token,
)


def configure_secret(monkeypatch):
    monkeypatch.setattr(
        settings,
        "auth_jwt_secret",
        "a" * 64,
    )

    monkeypatch.setattr(
        settings,
        "auth_access_token_minutes",
        30,
    )


def test_access_token_round_trip(
    monkeypatch,
):
    configure_secret(monkeypatch)

    user_id = uuid.uuid4()

    token = create_access_token(
        user_id
    )

    assert (
        decode_access_token(token)
        == user_id
    )


def test_invalid_token_is_rejected(
    monkeypatch,
):
    configure_secret(monkeypatch)

    with pytest.raises(
        InvalidAccessToken
    ):
        decode_access_token(
            "not-a-valid-token"
        )


def test_wrong_token_type_is_rejected(
    monkeypatch,
):
    configure_secret(monkeypatch)

    token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "type": "refresh",
        },
        settings.auth_jwt_secret,
        algorithm=ALGORITHM,
    )

    with pytest.raises(
        InvalidAccessToken
    ):
        decode_access_token(token)


def test_short_secret_is_rejected(
    monkeypatch,
):
    monkeypatch.setattr(
        settings,
        "auth_jwt_secret",
        "short",
    )

    with pytest.raises(RuntimeError):
        create_access_token(
            uuid.uuid4()
        )


def test_expired_access_token_is_rejected(
    monkeypatch,
):
    from datetime import (
        datetime,
        timedelta,
        timezone,
    )

    from app.security.tokens import (
        ExpiredAccessToken,
    )

    configure_secret(monkeypatch)

    now = datetime.now(
        timezone.utc
    )

    token = jwt.encode(
        {
            "sub": str(
                uuid.uuid4()
            ),
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

    with pytest.raises(
        ExpiredAccessToken
    ):
        decode_access_token(
            token
        )
