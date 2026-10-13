import pytest
from pydantic import ValidationError

from app.core.config import Settings


def make_settings(**overrides):
    values = {
        "database_url": "sqlite:///./test.db",
        "llm_provider": "mock",
        "llm_model": "",
        "llm_auto_explanation_limit": 0,
        "cors_allow_origins":
            "http://localhost:5173",
    }

    values.update(overrides)

    return Settings(
        _env_file=None,
        **values,
    )


def test_valid_development_configuration():
    settings = make_settings()

    assert (
        settings.llm_auto_explanation_limit
        == 0
    )


def test_invalid_database_scheme_is_rejected():
    with pytest.raises(ValidationError):
        make_settings(
            database_url=(
                "mysql://user:password@localhost/db"
            )
        )


def test_invalid_llm_limit_is_rejected():
    with pytest.raises(ValidationError):
        make_settings(
            llm_auto_explanation_limit=11
        )


def test_negative_llm_limit_is_rejected():
    with pytest.raises(ValidationError):
        make_settings(
            llm_auto_explanation_limit=-1
        )


def test_gemini_requires_api_key_when_enabled():
    with pytest.raises(ValidationError):
        make_settings(
            llm_provider="gemini",
            llm_model="gemini-test",
            llm_auto_explanation_limit=3,
            gemini_api_key="",
        )


def test_gemini_key_not_required_when_disabled():
    settings = make_settings(
        llm_provider="gemini",
        llm_model="",
        llm_auto_explanation_limit=0,
        gemini_api_key="",
    )

    assert (
        settings.llm_auto_explanation_limit
        == 0
    )


def test_cors_origins_are_parsed():
    settings = make_settings(
        cors_allow_origins=(
            "http://localhost:5173,"
            "https://example.com"
        )
    )

    assert settings.cors_origins == [
        "http://localhost:5173",
        "https://example.com",
    ]


def test_azure_requires_credentials_when_enabled():
    with pytest.raises(ValidationError):
        make_settings(
            llm_provider="azure_openai",
            llm_model="test-model",
            llm_auto_explanation_limit=3,
            azure_openai_endpoint="",
            azure_openai_api_key="",
            azure_openai_api_version="",
        )


def test_log_level_is_normalized():
    settings = make_settings(
        log_level="warning"
    )

    assert settings.log_level == "WARNING"


def test_invalid_log_level_is_rejected():
    with pytest.raises(ValidationError):
        make_settings(
            log_level="verbose"
        )


def test_login_rate_limit_defaults():
    settings = make_settings()

    assert (
        settings.auth_login_max_attempts
        == 5
    )

    assert (
        settings.auth_login_window_seconds
        == 300
    )


def test_login_max_attempts_too_low_is_rejected():
    with pytest.raises(
        ValidationError
    ):
        make_settings(
            auth_login_max_attempts=1
        )


def test_login_window_too_short_is_rejected():
    with pytest.raises(
        ValidationError
    ):
        make_settings(
            auth_login_window_seconds=10
        )
