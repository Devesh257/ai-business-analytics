import pytest
from pydantic import ValidationError

from app.core.config import Settings


def build_settings(**overrides):
    values = {
        "database_url": "sqlite:///test.db",
        "app_environment": "development",
        "cors_allow_origins": "http://localhost:5173",
        "llm_auto_explanation_limit": 0,
    }
    values.update(overrides)

    return Settings(
        _env_file=None,
        **values,
    )


def test_development_defaults_to_local_storage():
    settings = build_settings()

    assert settings.storage_backend == "local"
    assert settings.storage_local_root_path.is_absolute()


def test_s3_backend_requires_bucket():
    with pytest.raises(
        ValidationError,
        match="STORAGE_S3_BUCKET",
    ):
        build_settings(
            storage_backend="s3",
        )



def test_production_accepts_s3_storage_configuration():
    settings = build_settings(
        app_environment="production",
        cors_allow_origins="https://example.com",
        auth_jwt_secret="x" * 32,
        storage_backend="s3",
        storage_s3_bucket="signal-ledger-production",
        storage_s3_region="ap-south-1",
    )

    assert settings.storage_backend == "s3"
    assert (
        settings.storage_s3_bucket
        == "signal-ledger-production"
    )


def test_production_rejects_insecure_s3_endpoint():
    with pytest.raises(
        ValidationError,
        match="must use HTTPS",
    ):
        build_settings(
            app_environment="production",
            cors_allow_origins="https://example.com",
            auth_jwt_secret="x" * 32,
            storage_backend="s3",
            storage_s3_bucket="signal-ledger",
            storage_s3_endpoint_url=(
                "http://object-storage.example.com"
            ),
        )


@pytest.mark.parametrize(
    "prefix",
    [
        "../datasets",
        "datasets/../private",
        r"datasets\private",
    ],
)
def test_storage_prefix_rejects_unsafe_paths(prefix):
    with pytest.raises(ValidationError):
        build_settings(
            storage_backend="s3",
            storage_s3_bucket="signal-ledger",
            storage_s3_prefix=prefix,
        )
