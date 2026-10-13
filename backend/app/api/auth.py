from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_current_user,
    get_db,
)
from app.core.config import settings
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.security.login_rate_limiter import (
    login_rate_limiter,
)
from app.security.passwords import (
    hash_password,
    verify_password,
)
from app.security.tokens import (
    create_access_token,
)


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


def normalize_email(
    email: str,
) -> str:
    return email.strip().lower()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_user(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
):
    email = normalize_email(
        str(payload.email)
    )

    existing = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "An account with this email "
                "already exists."
            ),
        )

    user = User(
        email=email,
        hashed_password=hash_password(
            payload.password
        ),
    )

    db.add(user)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "An account with this email "
                "already exists."
            ),
        ) from exc

    db.refresh(user)

    return user


@router.post(
    "/login",
    response_model=TokenResponse,
)
def login_user(
    payload: LoginRequest,
    db: Session = Depends(get_db),
):
    email = normalize_email(
        str(payload.email)
    )

    retry_after = (
        login_rate_limiter.retry_after(
            email,
            max_attempts=(
                settings
                .auth_login_max_attempts
            ),
            window_seconds=(
                settings
                .auth_login_window_seconds
            ),
        )
    )

    if retry_after is not None:
        raise HTTPException(
            status_code=(
                status
                .HTTP_429_TOO_MANY_REQUESTS
            ),
            detail=(
                "Too many login attempts. "
                "Try again later."
            ),
            headers={
                "Retry-After":
                    str(retry_after)
            },
        )

    user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if (
        user is None
        or not verify_password(
            payload.password,
            user.hashed_password,
        )
    ):
        login_rate_limiter.record_failure(
            email,
            window_seconds=(
                settings
                .auth_login_window_seconds
            ),
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={
                "WWW-Authenticate": "Bearer"
            },
        )

    login_rate_limiter.reset(
        email
    )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive.",
        )

    return TokenResponse(
        access_token=create_access_token(
            user.id
        )
    )


@router.get(
    "/me",
    response_model=UserResponse,
)
def get_me(
    current_user: User = Depends(
        get_current_user
    ),
):
    return current_user
