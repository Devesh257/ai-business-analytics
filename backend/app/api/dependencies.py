from fastapi import (
    Depends,
    HTTPException,
    status,
)
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.user import User
from app.security.tokens import (
    ExpiredAccessToken,
    InvalidAccessToken,
    decode_access_token,
)


bearer_scheme = HTTPBearer(
    auto_error=False
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


def get_current_user(
    credentials: (
        HTTPAuthorizationCredentials | None
    ) = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=(
            "Invalid or missing authentication "
            "credentials."
        ),
        headers={
            "WWW-Authenticate": "Bearer"
        },
    )

    if credentials is None:
        raise unauthorized

    try:
        user_id = decode_access_token(
            credentials.credentials
        )
    except ExpiredAccessToken:
        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail=(
                "Authentication session "
                "expired."
            ),
            headers={
                "WWW-Authenticate": "Bearer"
            },
        )
    except InvalidAccessToken:
        raise unauthorized

    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if user is None:
        raise unauthorized

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive.",
        )

    return user
