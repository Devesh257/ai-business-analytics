import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class LLMConfigurationError(RuntimeError):
    """Raised when a configured explanation provider cannot be created."""


class AzureOpenAIExplanationProvider:
    """Azure OpenAI adapter for verified explanation evidence."""

    def __init__(
        self,
        api_key,
        endpoint,
        model,
        client_factory=None,
    ):
        self.api_key = api_key
        self.endpoint = endpoint
        self.model = model
        self._client_factory = client_factory

    def _get_client(self):
        if self._client_factory is not None:
            return self._client_factory(
                self.api_key,
                self.endpoint,
            )

        from openai import OpenAI

        return OpenAI(
            api_key=self.api_key,
            base_url=(
                f"{self.endpoint.rstrip('/')}/openai/v1/"
            ),
        )

    def generate(self, prompt):
        client = self._get_client()

        response = client.responses.create(
            model=self.model,
            instructions=prompt["instruction"],
            input=json.dumps(
                prompt["verified_evidence"]
            ),
            store=False,
        )

        return {
            "text": response.output_text,
        }


class OllamaExplanationProvider:
    """Ollama adapter for verified explanation evidence."""

    def __init__(
        self,
        base_url,
        model,
        timeout_seconds=60,
        request_func=None,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self._request_func = request_func

    def _request(
        self,
        payload,
    ):
        url = (
            f"{self.base_url}/api/chat"
        )

        if self._request_func is not None:
            return self._request_func(
                url,
                payload,
                self.timeout_seconds,
            )

        request = Request(
            url,
            data=json.dumps(
                payload
            ).encode("utf-8"),
            headers={
                "Content-Type":
                    "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(
                request,
                timeout=self.timeout_seconds,
            ) as response:
                body = (
                    response
                    .read()
                    .decode("utf-8")
                )
        except HTTPError as exc:
            raise RuntimeError(
                "Ollama request failed with "
                f"HTTP {exc.code}."
            ) from exc
        except (
            URLError,
            TimeoutError,
        ) as exc:
            raise RuntimeError(
                "Ollama request failed."
            ) from exc

        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "Ollama returned invalid JSON."
            ) from exc

    def generate(
        self,
        prompt,
    ):
        instruction = (
            f"{prompt['instruction']}\n\n"
            "Use only the verified evidence "
            "provided below. Do not infer "
            "causes, strategies, customer "
            "behavior, market conditions, or "
            "other facts that are not explicitly "
            "present in the evidence. Do not "
            "invent or alter numbers."
        )

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": instruction,
                },
                {
                    "role": "user",
                    "content": (
                        "Verified evidence:\n"
                        + json.dumps(
                            prompt[
                                "verified_evidence"
                            ]
                        )
                    ),
                },
            ],
            "stream": False,
            "options": {
                "temperature": 0.1,
            },
        }

        response = self._request(
            payload
        )

        try:
            text = response[
                "message"
            ]["content"]
        except (
            KeyError,
            TypeError,
        ) as exc:
            raise RuntimeError(
                "Ollama returned an unexpected "
                "response structure."
            ) from exc

        if not isinstance(
            text,
            str,
        ):
            raise RuntimeError(
                "Ollama returned an unexpected "
                "response structure."
            )

        return {
            "text": text,
        }


class GeminiExplanationProvider:
    """Gemini adapter for verified explanation evidence."""

    def __init__(
        self,
        api_key,
        model,
        client_factory=None,
    ):
        self.api_key = api_key
        self.model = model
        self._client_factory = client_factory

    def _get_client(self):
        if self._client_factory is not None:
            return self._client_factory(
                self.api_key,
            )

        from google import genai

        return genai.Client(
            api_key=self.api_key,
        )

    def generate(self, prompt):
        content = (
            f"{prompt['instruction']}\n\n"
            "Verified evidence:\n"
            f"{json.dumps(prompt['verified_evidence'])}"
        )

        client = self._get_client()

        response = client.models.generate_content(
            model=self.model,
            contents=content,
        )

        return {
            "text": response.text or "",
        }


def get_configured_provider(
    client_factory=None,
):
    provider_name = os.getenv(
        "LLM_PROVIDER"
    )

    model = os.getenv(
        "LLM_MODEL"
    )

    if (
        provider_name
        in {
            "azure_openai",
            "gemini",
        }
        and not model
    ):
        raise LLMConfigurationError(
            "LLM_MODEL is required."
        )

    if provider_name == "azure_openai":
        api_key = os.getenv(
            "AZURE_OPENAI_API_KEY"
        )

        endpoint = os.getenv(
            "AZURE_OPENAI_ENDPOINT"
        )

        if not api_key:
            raise LLMConfigurationError(
                "AZURE_OPENAI_API_KEY is required."
            )

        if not endpoint:
            raise LLMConfigurationError(
                "AZURE_OPENAI_ENDPOINT is required."
            )

        return AzureOpenAIExplanationProvider(
            api_key=api_key,
            endpoint=endpoint,
            model=model,
            client_factory=client_factory,
        )

    if provider_name == "gemini":
        api_key = os.getenv(
            "GEMINI_API_KEY"
        )

        if not api_key:
            raise LLMConfigurationError(
                "GEMINI_API_KEY is required."
            )

        return GeminiExplanationProvider(
            api_key=api_key,
            model=model,
            client_factory=client_factory,
        )

    if provider_name == "ollama":
        base_url = os.getenv(
            "OLLAMA_BASE_URL"
        )

        ollama_model = os.getenv(
            "OLLAMA_MODEL"
        )

        if not base_url:
            raise LLMConfigurationError(
                "OLLAMA_BASE_URL is required."
            )

        if not ollama_model:
            raise LLMConfigurationError(
                "OLLAMA_MODEL is required."
            )

        timeout_raw = os.getenv(
            "OLLAMA_REQUEST_TIMEOUT_SECONDS",
            "60",
        )

        try:
            timeout_seconds = int(
                timeout_raw
            )
        except ValueError as exc:
            raise LLMConfigurationError(
                "OLLAMA_REQUEST_TIMEOUT_SECONDS "
                "must be an integer."
            ) from exc

        if not (
            5
            <= timeout_seconds
            <= 300
        ):
            raise LLMConfigurationError(
                "OLLAMA_REQUEST_TIMEOUT_SECONDS "
                "must be between 5 and 300."
            )

        return OllamaExplanationProvider(
            base_url=base_url,
            model=ollama_model,
            timeout_seconds=(
                timeout_seconds
            ),
            request_func=client_factory,
        )

    raise LLMConfigurationError(
        "LLM_PROVIDER must be set to "
        "'azure_openai', 'gemini', "
        "or 'ollama'."
    )


def generate_explanation(
    prompt,
    llm_function=None,
):
    """
    Generate an explanation through an injected fake
    or configured provider.
    """
    if llm_function is not None:
        return llm_function(
            prompt
        )

    provider = get_configured_provider()

    return provider.generate(
        prompt
    )