import os
from types import SimpleNamespace

import pytest

from app.services.llm_client import (
    AzureOpenAIExplanationProvider,
    GeminiExplanationProvider,
    OllamaExplanationProvider,
    LLMConfigurationError,
    generate_explanation,
    get_configured_provider,
)


class FakeGeminiModels:
    def __init__(self):
        self.calls = []

    def generate_content(
        self,
        model,
        contents,
    ):
        self.calls.append(
            {
                "model": model,
                "contents": contents,
            }
        )

        return SimpleNamespace(
            text="Verified explanation"
        )


class FakeGeminiClient:
    def __init__(self):
        self.models = FakeGeminiModels()


def test_get_configured_provider_returns_gemini_provider(
    monkeypatch,
):
    monkeypatch.setenv(
        "LLM_PROVIDER",
        "gemini",
    )

    monkeypatch.setenv(
        "LLM_MODEL",
        "gemini-3.6-flash",
    )

    monkeypatch.setenv(
        "GEMINI_API_KEY",
        "test-key",
    )

    provider = get_configured_provider()

    assert isinstance(
        provider,
        GeminiExplanationProvider,
    )

    assert (
        provider.model
        == "gemini-3.6-flash"
    )

    assert (
        provider.api_key
        == "test-key"
    )


def test_get_configured_provider_requires_gemini_api_key(
    monkeypatch,
):
    monkeypatch.setenv(
        "LLM_PROVIDER",
        "gemini",
    )

    monkeypatch.setenv(
        "LLM_MODEL",
        "gemini-3.6-flash",
    )

    monkeypatch.delenv(
        "GEMINI_API_KEY",
        raising=False,
    )

    with pytest.raises(
        LLMConfigurationError,
        match="GEMINI_API_KEY is required",
    ):
        get_configured_provider()


def test_gemini_provider_generates_expected_response():
    fake_client = FakeGeminiClient()

    def fake_client_factory(
        api_key,
    ):
        assert api_key == "test-key"

        return fake_client

    provider = GeminiExplanationProvider(
        api_key="test-key",
        model="gemini-3.6-flash",
        client_factory=fake_client_factory,
    )

    prompt = {
        "instruction": (
            "Explain clearly and preserve numbers."
        ),
        "verified_evidence": {
            "insight_type": "correlation",
            "title": "Age and Salary",
            "source_columns": [
                "Age",
                "Salary",
            ],
            "method": "pearson_correlation",
            "evidence": {
                "correlation": 0.9,
                "sample_size": 10,
            },
            "verification": {
                "status": "verified",
            },
            "limitations": [],
        },
    }

    result = provider.generate(
        prompt
    )

    assert result == {
        "text": "Verified explanation",
    }

    assert len(
        fake_client.models.calls
    ) == 1

    call = (
        fake_client.models.calls[0]
    )

    assert (
        call["model"]
        == "gemini-3.6-flash"
    )

    assert (
        "Explain clearly and preserve numbers."
        in call["contents"]
    )

    assert (
        '"correlation": 0.9'
        in call["contents"]
    )

    assert (
        '"sample_size": 10'
        in call["contents"]
    )


def test_generate_explanation_uses_configured_gemini_provider(
    monkeypatch,
):
    fake_client = FakeGeminiClient()

    def fake_client_factory(
        api_key,
    ):
        return fake_client

    monkeypatch.setenv(
        "LLM_PROVIDER",
        "gemini",
    )

    monkeypatch.setenv(
        "LLM_MODEL",
        "gemini-3.6-flash",
    )

    monkeypatch.setenv(
        "GEMINI_API_KEY",
        "test-key",
    )

    provider = get_configured_provider(
        client_factory=fake_client_factory,
    )

    prompt = {
        "instruction": "Explain.",
        "verified_evidence": {
            "insight_type": "correlation",
            "title": "Test",
            "source_columns": [
                "A",
                "B",
            ],
            "method": "pearson_correlation",
            "evidence": {
                "correlation": 0.8,
            },
            "verification": {
                "status": "verified",
            },
            "limitations": [],
        },
    }

    result = provider.generate(
        prompt
    )

    assert result == {
        "text": "Verified explanation",
    }


def test_generate_explanation_still_supports_injected_llm_function():
    prompt = {
        "instruction": "Explain.",
        "verified_evidence": {},
    }

    result = generate_explanation(
        prompt,
        lambda received_prompt: {
            "text": (
                "Injected explanation"
            )
        },
    )

    assert result == {
        "text": "Injected explanation",
    }


def test_get_configured_provider_still_supports_azure_openai(
    monkeypatch,
):
    monkeypatch.setenv(
        "LLM_PROVIDER",
        "azure_openai",
    )

    monkeypatch.setenv(
        "LLM_MODEL",
        "gpt-4o-mini",
    )

    monkeypatch.setenv(
        "AZURE_OPENAI_API_KEY",
        "azure-test-key",
    )

    monkeypatch.setenv(
        "AZURE_OPENAI_ENDPOINT",
        "https://example.openai.azure.com/",
    )

    provider = get_configured_provider()

    assert isinstance(
        provider,
        AzureOpenAIExplanationProvider,
    )

    assert (
        provider.api_key
        == "azure-test-key"
    )

    assert (
        provider.endpoint
        == "https://example.openai.azure.com/"
    )

    assert (
        provider.model
        == "gpt-4o-mini"
    )


def test_get_configured_provider_requires_model(
    monkeypatch,
):
    monkeypatch.setenv(
        "LLM_PROVIDER",
        "gemini",
    )

    monkeypatch.delenv(
        "LLM_MODEL",
        raising=False,
    )

    monkeypatch.setenv(
        "GEMINI_API_KEY",
        "test-key",
    )

    with pytest.raises(
        LLMConfigurationError,
        match="LLM_MODEL is required",
    ):
        get_configured_provider()


def test_get_configured_provider_rejects_unknown_provider(
    monkeypatch,
):
    monkeypatch.setenv(
        "LLM_PROVIDER",
        "unknown",
    )

    monkeypatch.setenv(
        "LLM_MODEL",
        "test-model",
    )

    with pytest.raises(
        LLMConfigurationError,
        match=(
            "LLM_PROVIDER must be set to "
            "'azure_openai', 'gemini', "
            "or 'ollama'"
        ),
    ):
        get_configured_provider()

def test_get_configured_provider_returns_ollama_provider(
    monkeypatch,
):
    monkeypatch.setenv(
        "LLM_PROVIDER",
        "ollama",
    )

    monkeypatch.delenv(
        "LLM_MODEL",
        raising=False,
    )

    monkeypatch.setenv(
        "OLLAMA_BASE_URL",
        "http://192.168.1.7:11434",
    )

    monkeypatch.setenv(
        "OLLAMA_MODEL",
        "llama3.2:3b",
    )

    monkeypatch.setenv(
        "OLLAMA_REQUEST_TIMEOUT_SECONDS",
        "60",
    )

    provider = get_configured_provider()

    assert isinstance(
        provider,
        OllamaExplanationProvider,
    )

    assert (
        provider.base_url
        == "http://192.168.1.7:11434"
    )

    assert (
        provider.model
        == "llama3.2:3b"
    )

    assert (
        provider.timeout_seconds
        == 60
    )


def test_get_configured_provider_requires_ollama_base_url(
    monkeypatch,
):
    monkeypatch.setenv(
        "LLM_PROVIDER",
        "ollama",
    )

    monkeypatch.setenv(
        "OLLAMA_MODEL",
        "llama3.2:3b",
    )

    monkeypatch.delenv(
        "OLLAMA_BASE_URL",
        raising=False,
    )

    with pytest.raises(
        LLMConfigurationError,
        match="OLLAMA_BASE_URL is required",
    ):
        get_configured_provider()


def test_get_configured_provider_requires_ollama_model(
    monkeypatch,
):
    monkeypatch.setenv(
        "LLM_PROVIDER",
        "ollama",
    )

    monkeypatch.setenv(
        "OLLAMA_BASE_URL",
        "http://192.168.1.7:11434",
    )

    monkeypatch.delenv(
        "OLLAMA_MODEL",
        raising=False,
    )

    with pytest.raises(
        LLMConfigurationError,
        match="OLLAMA_MODEL is required",
    ):
        get_configured_provider()


def test_ollama_provider_generates_expected_response():
    calls = []

    def fake_request(
        url,
        payload,
        timeout_seconds,
    ):
        calls.append(
            {
                "url": url,
                "payload": payload,
                "timeout_seconds":
                    timeout_seconds,
            }
        )

        return {
            "message": {
                "role": "assistant",
                "content":
                    "Verified explanation",
            }
        }

    provider = OllamaExplanationProvider(
        base_url=(
            "http://192.168.1.7:11434"
        ),
        model="llama3.2:3b",
        timeout_seconds=60,
        request_func=fake_request,
    )

    prompt = {
        "instruction": (
            "Explain clearly and preserve "
            "verified numbers."
        ),
        "verified_evidence": {
            "insight_type": "correlation",
            "title": "Age and Salary",
            "source_columns": [
                "Age",
                "Salary",
            ],
            "method":
                "pearson_correlation",
            "evidence": {
                "correlation": 0.9,
                "sample_size": 10,
            },
            "verification": {
                "status": "verified",
            },
            "limitations": [],
        },
    }

    result = provider.generate(
        prompt
    )

    assert result == {
        "text": "Verified explanation",
    }

    assert len(calls) == 1

    call = calls[0]

    assert (
        call["url"]
        == (
            "http://192.168.1.7:11434"
            "/api/chat"
        )
    )

    assert (
        call["timeout_seconds"]
        == 60
    )

    payload = call["payload"]

    assert (
        payload["model"]
        == "llama3.2:3b"
    )

    assert payload["stream"] is False

    assert (
        payload["options"][
            "temperature"
        ]
        == 0.1
    )

    assert (
        payload["messages"][0]["role"]
        == "system"
    )

    assert (
        "Do not invent or alter numbers"
        in payload["messages"][0]["content"]
    )

    assert (
        '"correlation": 0.9'
        in payload["messages"][1]["content"]
    )


def test_ollama_provider_rejects_invalid_response():
    def fake_request(
        url,
        payload,
        timeout_seconds,
    ):
        return {
            "unexpected": True
        }

    provider = OllamaExplanationProvider(
        base_url=(
            "http://192.168.1.7:11434"
        ),
        model="llama3.2:3b",
        request_func=fake_request,
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "unexpected response "
            "structure"
        ),
    ):
        provider.generate(
            {
                "instruction": "Explain.",
                "verified_evidence": {},
            }
        )


def test_invalid_ollama_timeout_is_rejected_by_provider_config(
    monkeypatch,
):
    monkeypatch.setenv(
        "LLM_PROVIDER",
        "ollama",
    )

    monkeypatch.setenv(
        "OLLAMA_BASE_URL",
        "http://192.168.1.7:11434",
    )

    monkeypatch.setenv(
        "OLLAMA_MODEL",
        "llama3.2:3b",
    )

    monkeypatch.setenv(
        "OLLAMA_REQUEST_TIMEOUT_SECONDS",
        "1",
    )

    with pytest.raises(
        LLMConfigurationError,
        match="must be between 5 and 300",
    ):
        get_configured_provider()
