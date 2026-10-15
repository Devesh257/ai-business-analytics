from fastapi.testclient import TestClient

import app.main as main_module


client = TestClient(
    main_module.app
)


def test_health_reports_liveness():
    response = client.get(
        "/health"
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "backend",
    }


def test_health_does_not_require_database(
    monkeypatch,
):
    def fail_if_called():
        raise AssertionError(
            "Health check must not probe "
            "the database."
        )

    monkeypatch.setattr(
        main_module,
        "_database_is_ready",
        fail_if_called,
    )

    response = client.get(
        "/health"
    )

    assert response.status_code == 200


def test_ready_when_database_available(
    monkeypatch,
):
    monkeypatch.setattr(
        main_module,
        "_database_is_ready",
        lambda: True,
    )

    response = client.get(
        "/ready"
    )

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "ready"
    assert body["database"] == "ready"

    assert body["llm"]["provider"] == (
        main_module.settings.llm_provider
    )

    assert (
        body["llm"][
            "connectivity_checked"
        ]
        is False
    )


def test_ready_returns_503_when_database_unavailable(
    monkeypatch,
):
    monkeypatch.setattr(
        main_module,
        "_database_is_ready",
        lambda: False,
    )

    response = client.get(
        "/ready"
    )

    assert response.status_code == 503

    body = response.json()

    assert body["status"] == (
        "not_ready"
    )

    assert body["database"] == (
        "unavailable"
    )


def test_readiness_does_not_expose_secrets(
    monkeypatch,
):
    monkeypatch.setattr(
        main_module,
        "_database_is_ready",
        lambda: True,
    )

    response = client.get(
        "/ready"
    )

    serialized = (
        response.text.lower()
    )

    assert "gemini_api_key" not in serialized
    assert "azure_openai_api_key" not in serialized
    assert "auth_jwt_secret" not in serialized
    assert "database_url" not in serialized
