from datetime import (
    datetime,
    timedelta,
    timezone,
)
import uuid

import jwt
from jwt import (
    ExpiredSignatureError,
    InvalidTokenError,
)

from app.core.config import settings


ALGORITHM = "HS256"


class InvalidAccessToken(Exception):
    pass


class ExpiredAccessToken(
    InvalidAccessToken
):
    pass


def _get_jwt_secret() -> str:
    secret = settings.auth_jwt_secret.strip()

    if len(secret) < 32:
        raise RuntimeError(
            "AUTH_JWT_SECRET must contain "
            "at least 32 characters."
        )

    return secret


def create_access_token(
    user_id: uuid.UUID,
) -> str:
    now = datetime.now(timezone.utc)

    expires_at = now + timedelta(
        minutes=settings.auth_access_token_minutes
    )

    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": expires_at,
    }

    return jwt.encode(
        payload,
        _get_jwt_secret(),
        algorithm=ALGORITHM,
    )


def decode_access_token(
    token: str,
) -> uuid.UUID:
    try:
        payload = jwt.decode(
            token,
            _get_jwt_secret(),
            algorithms=[ALGORITHM],
        )
    except ExpiredSignatureError as exc:
        raise ExpiredAccessToken(
            "Access token has expired."
        ) from exc
    except InvalidTokenError as exc:
        raise InvalidAccessToken(
            "Invalid access token."
        ) from exc

    if payload.get("type") != "access":
        raise InvalidAccessToken(
            "Invalid token type."
        )

    subject = payload.get("sub")

    if not subject:
        raise InvalidAccessToken(
            "Token subject is missing."
        )

    try:
        return uuid.UUID(subject)
    except ValueError as exc:
        raise InvalidAccessToken(
            "Token subject is invalid."
        ) from exc
