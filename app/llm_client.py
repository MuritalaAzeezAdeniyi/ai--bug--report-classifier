from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Mapping, Protocol

SUPPORTED_PROVIDERS = {"openai", "gemini"}
SAFE_PROVIDER_ERROR_CODES = {
    "UNAUTHENTICATED",
    "PERMISSION_DENIED",
    "API_KEY_INVALID",
    "INVALID_API_KEY",
    "AUTHENTICATION_ERROR",
    "UNAUTHORIZED",
    "RESOURCE_EXHAUSTED",
    "RATE_LIMIT_EXCEEDED",
    "QUOTA_EXCEEDED",
    "QUOTA_EXHAUSTED",
    "DEADLINE_EXCEEDED",
    "TIMEOUT",
    "TIMED_OUT",
    "MODEL_NOT_FOUND",
    "MODEL_NOT_FOUND_ERROR",
    "UNKNOWN_MODEL",
    "NOT_FOUND",
    "INVALID_ARGUMENT",
    "INTERNAL",
    "UNAVAILABLE",
    "FAILED_PRECONDITION",
    "CANCELLED",
    "UNKNOWN",
    "BAD_REQUEST",
    "SERVER_ERROR",
    "SERVICE_UNAVAILABLE",
}
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

    def __init__(
        self,
        message: str,
        *,
        status_code: int | str | None = None,
        retryable: bool = False,
        provider_error_type: str | None = None,
        provider_error_code: str | None = None,
        diagnostic_cause: str = "unknown",
    ):
        super().__init__(_redact_sensitive_details(message))
        self.status_code = status_code
        self.retryable = retryable
        self.provider_error_type = provider_error_type
        self.provider_error_code = provider_error_code
        self.diagnostic_cause = diagnostic_cause

    @property
    def diagnostics(self) -> dict[str, str | int | None]:
        return {
            "provider_error_type": self.provider_error_type,
            "http_status_code": self.status_code,
            "provider_error_code": self.provider_error_code,
            "diagnostic_cause": self.diagnostic_cause,
        }


class LLMTimeoutError(ProviderRequestError):
    """Raised when the provider request exceeds the configured timeout window."""

    def __init__(self, message: str, *, status_code: int | str | None = None, **diagnostics: Any):
        super().__init__(message, status_code=status_code, retryable=True, **diagnostics)


class LLMRateLimitError(ProviderRequestError):
    """Raised when the provider rejects the request because of rate limiting or quota exhaustion."""

    def __init__(self, message: str, *, status_code: int | str | None = None, **diagnostics: Any):
        super().__init__(message, status_code=status_code, retryable=True, **diagnostics)


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
            getattr(exc, "code", None),
        ):
            if isinstance(candidate, int) and 100 <= candidate <= 599:
                return candidate
            if isinstance(candidate, str) and candidate.isdigit() and 100 <= int(candidate) <= 599:
                return int(candidate)
        return None

    @staticmethod
    def _safe_error_code(value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        normalized = value.strip()
        normalized_code = re.sub(r"[-.]", "_", normalized).upper()
        return normalized_code if normalized_code in SAFE_PROVIDER_ERROR_CODES else None

    @staticmethod
    def _extract_error_code(exc: BaseException) -> str | None:
        candidates: list[Any] = []
        for source in (exc, getattr(exc, "error", None)):
            if source is None:
                continue
            if isinstance(source, Mapping):
                candidates.extend(source.get(key) for key in ("reason", "status", "code"))
            else:
                candidates.extend((getattr(source, "status", None), getattr(source, "code", None)))

        details = getattr(exc, "details", None)
        if isinstance(details, (list, tuple)):
            for detail in details:
                if isinstance(detail, Mapping):
                    candidates.extend(detail.get(key) for key in ("reason", "status", "code"))
                else:
                    candidates.extend(getattr(detail, key, None) for key in ("reason", "status", "code"))

        for candidate in candidates:
            safe_code = BaseProvider._safe_error_code(candidate)
            if safe_code is not None:
                return safe_code
        return None

    @staticmethod
    def _classify_diagnostic_cause(
        exc: BaseException,
        status_code: int | str | None,
        provider_error_code: str | None,
    ) -> str:
        normalized_code = (provider_error_code or "").lower().replace("-", "_").replace(".", "_")
        exception_type = exc.__class__.__name__.lower()
        if status_code in (401, 403) or normalized_code in {
            "unauthenticated", "permission_denied", "api_key_invalid", "invalid_api_key",
            "authentication_error", "unauthorized",
        }:
            return "authentication"
        if status_code == 429 or normalized_code in {
            "resource_exhausted", "rate_limit_exceeded", "quota_exceeded", "quota_exhausted",
        }:
            return "rate_limit_or_quota"
        if status_code in (408, 504) or normalized_code in {
            "deadline_exceeded", "timeout", "timed_out",
        } or "timeout" in exception_type or "deadlineexceeded" in exception_type:
            return "timeout"
        if normalized_code in {"model_not_found", "model_not_found_error", "unknown_model"}:
            return "model_not_found"
        if status_code == 404 and ("model" in exception_type and "notfound" in exception_type):
            return "model_not_found"
        if status_code is not None or provider_error_code is not None:
            return "provider_error"
        return "unknown"

    @staticmethod
    def _coerce_provider_error(provider_name: str, exc: BaseException) -> ProviderRequestError:
        status_code = BaseProvider._extract_status_code(exc)
        provider_error_code = BaseProvider._extract_error_code(exc)
        diagnostic_cause = BaseProvider._classify_diagnostic_cause(exc, status_code, provider_error_code)
        provider_error_type = re.sub(r"[^A-Za-z0-9_.]", "", exc.__class__.__name__)[:80] or "unknown"
        diagnostic_parts = [f"cause={diagnostic_cause}", f"exception={provider_error_type}"]
        if status_code is not None:
            diagnostic_parts.append(f"http_status={status_code}")
        if provider_error_code is not None:
            diagnostic_parts.append(f"provider_code={provider_error_code}")
        details = {
            "status_code": status_code,
            "provider_error_type": provider_error_type,
            "provider_error_code": provider_error_code,
            "diagnostic_cause": diagnostic_cause,
        }
        suffix = "; ".join(diagnostic_parts)

        if diagnostic_cause == "rate_limit_or_quota":
            return LLMRateLimitError(f"{provider_name} request was rate limited ({suffix}).", **details)
        if diagnostic_cause == "timeout":
            return LLMTimeoutError(f"{provider_name} request timed out ({suffix}).", **details)
        return ProviderRequestError(f"{provider_name} request failed ({suffix}).", retryable=False, **details)

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
