from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Mapping, Protocol

SUPPORTED_PROVIDERS = {"openai", "gemini"}
DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "gemini": "gemini-2.5-flash",
}


def _redact_sensitive_details(message: str) -> str:
    redacted = message or ""
    redacted = redacted.replace("\r", " ").replace("\n", " ")
    for key_name in ("api_key", "apikey", "authorization", "token", "secret", "password"):
        redacted = re.sub(
            rf"(?i)(?:\b{key_name}\b\s*[:=]\s*)[^\s,;\]]+",
            f"{key_name}=[REDACTED]",
            redacted,
        )
    return redacted


class LLMClientError(RuntimeError):
    """Base error for LLM client configuration and provider issues."""


class MissingConfigurationError(LLMClientError):
    """Raised when required configuration values are missing."""


class UnsupportedProviderError(LLMClientError):
    """Raised when a provider name is not recognized by the abstraction."""


class ProviderInitializationError(LLMClientError):
    """Raised when an SDK-backed provider cannot be initialized."""


class ProviderRequestError(LLMClientError):
    """Raised when a provider request fails after initialization."""

    def __init__(self, message: str, *, status_code: int | str | None = None, retryable: bool = False):
        super().__init__(_redact_sensitive_details(message))
        self.status_code = status_code
        self.retryable = retryable


class LLMTimeoutError(ProviderRequestError):
    """Raised when the provider request exceeds the configured timeout window."""

    def __init__(self, message: str, *, status_code: int | str | None = None):
        super().__init__(message, status_code=status_code, retryable=True)


class LLMRateLimitError(ProviderRequestError):
    """Raised when the provider rejects the request because of rate limiting or quota exhaustion."""

    def __init__(self, message: str, *, status_code: int | str | None = None):
        super().__init__(message, status_code=status_code, retryable=True)


@dataclass(frozen=True)
class LLMClientConfig:
    provider: str
    model: str | None = None
    api_key: str | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "LLMClientConfig":
        source = os.environ if env is None else env
        provider = (source.get("LLM_PROVIDER") or "").strip().lower()
        model = (source.get("LLM_MODEL") or "").strip() or None
        api_key = (source.get("LLM_API_KEY") or "").strip() or None

        if not provider:
            raise MissingConfigurationError("LLM_PROVIDER is required but was not set.")
        if provider not in SUPPORTED_PROVIDERS:
            raise UnsupportedProviderError(f"Unsupported LLM provider: {provider!r}")
        if not api_key:
            raise MissingConfigurationError(f"LLM_API_KEY is required for provider '{provider}'.")

        resolved_model = model or DEFAULT_MODELS.get(provider)
        if not resolved_model:
            raise MissingConfigurationError(f"No default model is configured for provider '{provider}'.")

        return cls(provider=provider, model=resolved_model, api_key=api_key)


class LLMProvider(Protocol):
    def generate(self, prompt: str, *, response_format: str | None = None, **kwargs: object) -> dict[str, Any] | str:
        ...


class BaseProvider:
    def __init__(self, config: LLMClientConfig):
        self.config = config

    @staticmethod
    def _extract_status_code(exc: BaseException) -> int | str | None:
        for candidate in (
            getattr(exc, "status_code", None),
            getattr(getattr(exc, "response", None), "status_code", None),
            getattr(getattr(exc, "body", None), "status_code", None),
            getattr(getattr(exc, "error", None), "status_code", None),
        ):
            if candidate is not None:
                return candidate

        for candidate in (
            getattr(exc, "code", None),
            getattr(getattr(exc, "error", None), "code", None),
        ):
            if candidate is not None:
                return candidate
        return None

    @staticmethod
    def _coerce_provider_error(provider_name: str, exc: BaseException) -> ProviderRequestError:
        status_code = BaseProvider._extract_status_code(exc)
        error_text = str(exc).strip() or exc.__class__.__name__
        lowered = error_text.lower()

        if status_code == 429 or status_code == "429" or status_code in {"rate_limit_exceeded", "rate-limit-exceeded"}:
            return LLMRateLimitError(f"{provider_name} request was rate limited.", status_code=status_code)
        if "rate limit" in lowered or "too many requests" in lowered or "quota exceeded" in lowered:
            return LLMRateLimitError(f"{provider_name} request was rate limited.", status_code=status_code)

        if status_code in {408, 504} or status_code in {"408", "504", "timeout", "timed_out", "deadline_exceeded"}:
            return LLMTimeoutError(f"{provider_name} request timed out.", status_code=status_code)
        if any(token in lowered for token in ("timed out", "timeout", "deadline exceeded", "time out")):
            return LLMTimeoutError(f"{provider_name} request timed out.", status_code=status_code)

        return ProviderRequestError(f"{provider_name} request failed.", status_code=status_code, retryable=False)

    def _coerce_structured_output(self, payload: Any) -> dict[str, Any] | str:
        if payload is None:
            return {}
        if isinstance(payload, dict):
            return payload
        if isinstance(payload, str):
            stripped = payload.strip()
            if not stripped:
                return {}
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                return stripped
            if isinstance(parsed, dict):
                return parsed
            return {"content": parsed}
        if hasattr(payload, "model_dump"):
            return payload.model_dump()
        if hasattr(payload, "dict"):
            return payload.dict()
        return {"content": payload}


class GeminiProvider(BaseProvider):
    def __init__(self, config: LLMClientConfig):
        super().__init__(config)
        self._client = self._initialize_client()

    def _initialize_client(self) -> Any:
        try:
            import google.genai as google_genai
        except Exception as exc:  # pragma: no cover - guarded by provider failure tests
            raise ProviderInitializationError("Gemini provider initialization failed.") from exc

        try:
            if hasattr(google_genai, "Client"):
                return google_genai.Client(api_key=self.config.api_key)
            if hasattr(google_genai, "configure"):
                google_genai.configure(api_key=self.config.api_key)
                if hasattr(google_genai, "GenerativeModel"):
                    return google_genai.GenerativeModel(self.config.model)
            raise ProviderInitializationError("Gemini provider initialization failed.")
        except Exception as exc:
            if isinstance(exc, ProviderInitializationError):
                raise
            raise ProviderInitializationError("Gemini provider initialization failed.") from exc

    def generate(self, prompt: str, *, response_format: str | None = None, **kwargs: object) -> dict[str, Any] | str:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must be a non-empty string.")
        try:
            model = getattr(self._client, "models", None)
            if model is not None and hasattr(model, "generate_content"):
                response = model.generate_content(
                    model=self.config.model,
                    contents=prompt,
                    config={"response_mime_type": "application/json"} if response_format else None,
                )
            else:
                response = self._client.generate_content(
                    prompt,
                    generation_config={"response_mime_type": "application/json"} if response_format else None,
                )
            payload = getattr(response, "text", None)
            return self._coerce_structured_output(payload)
        except Exception as exc:
            raise self._coerce_provider_error("Gemini", exc) from exc


class OpenAIProvider(BaseProvider):
    def __init__(self, config: LLMClientConfig):
        super().__init__(config)
        self._client = self._initialize_client()

    def _initialize_client(self) -> Any:
        try:
            import openai
        except Exception as exc:  # pragma: no cover - guarded by provider failure tests
            raise ProviderInitializationError("OpenAI provider initialization failed.") from exc

        try:
            return openai.OpenAI(api_key=self.config.api_key)
        except Exception as exc:
            raise ProviderInitializationError("OpenAI provider initialization failed.") from exc

    def generate(self, prompt: str, *, response_format: str | None = None, **kwargs: object) -> dict[str, Any] | str:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must be a non-empty string.")
        try:
            request_kwargs = {
                "model": self.config.model,
                "input": prompt,
            }
            if response_format:
                request_kwargs["response_format"] = {"type": "json_object"}
            response = self._client.responses.create(**request_kwargs)
            payload = getattr(response, "output_text", None)
            if payload is None and hasattr(response, "output"):
                try:
                    payload = response.output[0].content[0].text
                except (IndexError, AttributeError, TypeError):
                    payload = None
            return self._coerce_structured_output(payload)
        except Exception as exc:
            raise self._coerce_provider_error("OpenAI", exc) from exc


class LLMClient:
    """Provider-independent LLM client boundary.

    The application switches providers through configuration and delegates actual SDK calls
    to provider-specific adapters that remain isolated behind this interface.
    """

    def __init__(self, config: LLMClientConfig):
        if not isinstance(config, LLMClientConfig):
            raise TypeError("config must be an LLMClientConfig instance.")
        self.config = config
        self._provider = self._build_provider(config)

    @staticmethod
    def _build_provider(config: LLMClientConfig) -> LLMProvider:
        if config.provider == "gemini":
            return GeminiProvider(config)
        if config.provider == "openai":
            return OpenAIProvider(config)
        raise UnsupportedProviderError(f"Unsupported LLM provider: {config.provider!r}")

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "LLMClient":
        return cls(LLMClientConfig.from_env(env))

    @property
    def provider(self) -> str:
        return self.config.provider

    @property
    def model(self) -> str:
        return self.config.model or DEFAULT_MODELS[self.config.provider]

    def generate(self, prompt: str, *, response_format: str | None = None, **kwargs: object) -> dict[str, Any] | str:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must be a non-empty string.")
        return self._provider.generate(prompt, response_format=response_format, **kwargs)
