import logging
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.auth import router as auth_router
from app.api.analysis_runs import (
    router as analysis_runs_router,
)
from app.api.datasets import (
    router as datasets_router,
)
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.database import engine


PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Keep this temporarily because existing LLM
# provider adapters still read some values through
# environment lookups.
load_dotenv(PROJECT_ROOT / ".env")

configure_logging(settings.log_level)

logger = logging.getLogger(__name__)

logger.info(
    "Application configuration validated",
    extra={
        "event": "application_startup",
        "provider": settings.llm_provider,
        "llm_auto_limit":
            settings.llm_auto_explanation_limit,
        "cors_origin_count":
            len(settings.cors_origins),
    },
)


app = FastAPI(
    title="AI Business Analytics",
    version="0.1.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router)
app.include_router(datasets_router)
app.include_router(analysis_runs_router)


@app.get("/health")
def health_check():
    """Cheap process liveness check."""

    return {
        "status": "ok",
        "service": "backend",
    }


def _database_is_ready():
    """Check database reachability with no application data access."""

    try:
        with engine.connect() as connection:
            connection.execute(
                text("SELECT 1")
            )
    except SQLAlchemyError:
        logger.warning(
            "Database readiness check failed",
            extra={
                "event":
                    "database_readiness_failed",
            },
        )
        return False

    return True


def _llm_readiness():
    """
    Report configuration state only.

    Readiness deliberately does not call an
    external LLM provider.
    """

    enabled = (
        settings.llm_auto_explanation_limit
        > 0
    )

    return {
        "provider":
            settings.llm_provider,
        "automatic_explanations_enabled":
            enabled,
        "configuration":
            (
                "valid"
                if enabled
                else "not_required"
            ),
        "connectivity_checked":
            False,
    }


@app.get("/ready")
def readiness_check():
    """
    Application readiness check.

    Database connectivity is required.
    External LLM connectivity is intentionally
    not probed here.
    """

    database_ready = (
        _database_is_ready()
    )

    payload = {
        "status": (
            "ready"
            if database_ready
            else "not_ready"
        ),
        "database": (
            "ready"
            if database_ready
            else "unavailable"
        ),
        "llm": _llm_readiness(),
    }

    if not database_ready:
        return JSONResponse(
            status_code=503,
            content=payload,
        )

    return payload
