from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


BASE_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    database_url: str

    llm_provider: Literal[
        "gemini",
        "azure_openai",
        "ollama",
        "mock",
    ] = "mock"

    llm_model: str = ""

    llm_auto_explanation_limit: int = Field(
        default=0,
        ge=0,
        le=10,
    )

    gemini_api_key: str = ""

    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = ""

    ollama_base_url: str = ""
    ollama_model: str = ""
    ollama_request_timeout_seconds: int = Field(
        default=60,
        ge=5,
        le=300,
    )

    cors_allow_origins: str = (
        "http://localhost:5173"
    )

    log_level: str = "INFO"

    auth_jwt_secret: str = ""
    auth_access_token_minutes: int = Field(
        default=30,
        ge=5,
        le=1440,
    )

    auth_login_max_attempts: int = Field(
        default=5,
        ge=2,
        le=20,
    )

    auth_login_window_seconds: int = Field(
        default=300,
        ge=30,
        le=3600,
    )

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value):
        value = value.strip()

        if not value:
            raise ValueError(
                "DATABASE_URL is required."
            )

        try:
            parsed = make_url(value)
        except Exception as exc:
            raise ValueError(
                "DATABASE_URL is not a valid "
                "SQLAlchemy database URL."
            ) from exc

        driver = parsed.drivername

        if not (
            driver.startswith("postgresql")
            or driver.startswith("sqlite")
        ):
            raise ValueError(
                "DATABASE_URL must use "
                "PostgreSQL or SQLite."
            )

        return value

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value):
        value = value.strip().upper()

        allowed = {
            "DEBUG",
            "INFO",
            "WARNING",
            "ERROR",
            "CRITICAL",
        }

        if value not in allowed:
            raise ValueError(
                "LOG_LEVEL must be one of: "
                "DEBUG, INFO, WARNING, ERROR, CRITICAL."
            )

        return value

    @field_validator("cors_allow_origins")
    @classmethod
    def validate_cors_origins(cls, value):
        origins = [
            origin.strip()
            for origin in value.split(",")
            if origin.strip()
        ]

        if not origins:
            raise ValueError(
                "CORS_ALLOW_ORIGINS must contain "
                "at least one origin."
            )

        return value

    @model_validator(mode="after")
    def validate_llm_configuration(self):
        # LLM completely disabled for automatic
        # explanations. Credentials are not required.
        if self.llm_auto_explanation_limit == 0:
            return self

        if (
            self.llm_provider
            in {"gemini", "azure_openai"}
            and not self.llm_model.strip()
        ):
            raise ValueError(
                "LLM_MODEL is required when "
                "Gemini or Azure OpenAI "
                "automatic explanations "
                "are enabled."
            )

        if self.llm_provider == "gemini":
            if not self.gemini_api_key.strip():
                raise ValueError(
                    "GEMINI_API_KEY is required "
                    "when Gemini automatic "
                    "explanations are enabled."
                )

        elif self.llm_provider == "azure_openai":
            missing = []

            if not self.azure_openai_endpoint.strip():
                missing.append(
                    "AZURE_OPENAI_ENDPOINT"
                )

            if not self.azure_openai_api_key.strip():
                missing.append(
                    "AZURE_OPENAI_API_KEY"
                )

            if not self.azure_openai_api_version.strip():
                missing.append(
                    "AZURE_OPENAI_API_VERSION"
                )

            if missing:
                raise ValueError(
                    "Missing Azure OpenAI "
                    "configuration: "
                    + ", ".join(missing)
                )

        elif self.llm_provider == "ollama":
            missing = []

            if not self.ollama_base_url.strip():
                missing.append(
                    "OLLAMA_BASE_URL"
                )

            if not self.ollama_model.strip():
                missing.append(
                    "OLLAMA_MODEL"
                )

            if missing:
                raise ValueError(
                    "Missing Ollama "
                    "configuration: "
                    + ", ".join(missing)
                )

        return self

    @property
    def cors_origins(self):
        return [
            origin.strip()
            for origin in self.cors_allow_origins.split(",")
            if origin.strip()
        ]


settings = Settings()
