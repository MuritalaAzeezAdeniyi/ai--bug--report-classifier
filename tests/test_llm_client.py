import sys
from types import SimpleNamespace

import pytest

from app.llm_client import (
    LLMClient,
    LLMClientConfig,
    LLMRateLimitError,
    LLMTimeoutError,
    MissingConfigurationError,
    ProviderInitializationError,
    ProviderRequestError,
    UnsupportedProviderError,
)


def test_valid_configuration():
    config = LLMClientConfig(provider="openai", model="gpt-4o-mini", api_key="test-key")
    assert config.provider == "openai"
    assert config.model == "gpt-4o-mini"
    assert config.api_key == "test-key"


def test_client_from_valid_env(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("LLM_API_KEY", "secret-key")

    client = LLMClient.from_env()
    assert client.provider == "openai"
    assert client.model == "gpt-4o-mini"
    assert client.config.api_key == "secret-key"


def test_missing_api_key_raises(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    with pytest.raises(MissingConfigurationError, match="LLM_API_KEY"):
        LLMClientConfig.from_env()


def test_missing_provider_raises(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setenv("LLM_API_KEY", "test-key")

    with pytest.raises(MissingConfigurationError, match="LLM_PROVIDER"):
        LLMClientConfig.from_env()


def test_unsupported_provider_raises(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "unknown-provider")
    monkeypatch.setenv("LLM_API_KEY", "test-key")

    with pytest.raises(UnsupportedProviderError, match="Unsupported LLM provider"):
        LLMClientConfig.from_env()


def test_default_model_is_applied_when_not_explicitly_set(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("LLM_API_KEY", "gemini-key")

    config = LLMClientConfig.from_env()
    assert config.model == "gemini-2.5-flash"


def test_client_construction_requires_config():
    with pytest.raises(TypeError):
        LLMClient("openai")


def test_provider_independent_interface_is_exposed():
    config = LLMClientConfig(provider="openai", model="gpt-4o-mini", api_key="key")
    client = LLMClient(config)
    assert hasattr(client, "generate")
    assert callable(client.generate)


def test_gemini_selected_when_provider_is_gemini(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("LLM_API_KEY", "gemini-key")

    client = LLMClient.from_env()
    assert client.provider == "gemini"
    assert client.model == "gemini-2.5-flash"
    assert client._provider.__class__.__name__ == "GeminiProvider"


def test_openai_selected_when_provider_is_openai(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "gpt-4.1-mini")
    monkeypatch.setenv("LLM_API_KEY", "openai-key")

    client = LLMClient.from_env()
    assert client.provider == "openai"
    assert client.model == "gpt-4.1-mini"
    assert client._provider.__class__.__name__ == "OpenAIProvider"


def test_gemini_provider_initializes_and_returns_structured_response(monkeypatch):
    class FakeResponse:
        text = '{"status": "ok"}'

    class FakeModel:
        def __init__(self, *args, **kwargs):
            pass

        def generate_content(self, *args, **kwargs):
            return FakeResponse()

    fake_google_module = SimpleNamespace(
        Client=lambda api_key: SimpleNamespace(models=SimpleNamespace(generate_content=lambda **kwargs: FakeResponse())),
        configure=lambda api_key: None,
        GenerativeModel=lambda model_name: FakeModel(),
    )
    monkeypatch.setitem(sys.modules, "google", SimpleNamespace(genai=fake_google_module))
    monkeypatch.setitem(sys.modules, "google.genai", fake_google_module)

    provider = LLMClient(LLMClientConfig(provider="gemini", model="gemini-2.5-flash", api_key="abc"))._provider
    assert provider.generate("hello") == {"status": "ok"}


def test_openai_provider_initializes_and_returns_structured_response(monkeypatch):
    class FakeResponse:
        output_text = '{"status": "ok"}'

    class FakeOpenAIClient:
        def __init__(self, *args, **kwargs):
            self.responses = SimpleNamespace(create=lambda **kwargs: FakeResponse())

    fake_openai_module = SimpleNamespace(OpenAI=lambda api_key: FakeOpenAIClient())
    monkeypatch.setitem(sys.modules, "openai", fake_openai_module)

    provider = LLMClient(LLMClientConfig(provider="openai", model="gpt-4o-mini", api_key="abc"))._provider
    assert provider.generate("hello") == {"status": "ok"}


def test_gemini_provider_translates_request_failure(monkeypatch):
    class FakeModel:
        def __init__(self, *args, **kwargs):
            pass

        def generate_content(self, *args, **kwargs):
            raise RuntimeError("gemini exploded")

    fake_google_module = SimpleNamespace(
        configure=lambda *args, **kwargs: None,
        GenerativeModel=lambda model_name: FakeModel(),
    )
    monkeypatch.setitem(sys.modules, "google", SimpleNamespace(genai=fake_google_module))
    monkeypatch.setitem(sys.modules, "google.genai", fake_google_module)

    provider = LLMClient(LLMClientConfig(provider="gemini", model="gemini-2.5-flash", api_key="abc"))._provider
    with pytest.raises(ProviderRequestError):
        provider.generate("hello")


def test_openai_provider_translates_request_failure(monkeypatch):
    class FakeOpenAIClient:
        def __init__(self, *args, **kwargs):
            self.responses = SimpleNamespace(create=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("openai exploded")))

    fake_openai_module = SimpleNamespace(OpenAI=lambda api_key: FakeOpenAIClient())
    monkeypatch.setitem(sys.modules, "openai", fake_openai_module)

    provider = LLMClient(LLMClientConfig(provider="openai", model="gpt-4o-mini", api_key="abc"))._provider
    with pytest.raises(ProviderRequestError):
        provider.generate("hello")


def test_gemini_provider_translates_timeout_error(monkeypatch):
    class TimeoutErrorException(Exception):
        status_code = 504

    class FakeModel:
        def __init__(self, *args, **kwargs):
            pass

        def generate_content(self, *args, **kwargs):
            raise TimeoutErrorException("deadline exceeded")

    fake_google_module = SimpleNamespace(
        configure=lambda *args, **kwargs: None,
        GenerativeModel=lambda model_name: FakeModel(),
    )
    monkeypatch.setitem(sys.modules, "google", SimpleNamespace(genai=fake_google_module))
    monkeypatch.setitem(sys.modules, "google.genai", fake_google_module)

    provider = LLMClient(LLMClientConfig(provider="gemini", model="gemini-2.5-flash", api_key="abc"))._provider
    with pytest.raises(LLMTimeoutError):
        provider.generate("hello")


def test_openai_provider_translates_rate_limit_error(monkeypatch):
    class RateLimitErrorException(Exception):
        status_code = 429

    class FakeOpenAIClient:
        def __init__(self, *args, **kwargs):
            self.responses = SimpleNamespace(create=lambda **kwargs: (_ for _ in ()).throw(RateLimitErrorException("too many requests")))

    fake_openai_module = SimpleNamespace(OpenAI=lambda api_key: FakeOpenAIClient())
    monkeypatch.setitem(sys.modules, "openai", fake_openai_module)

    provider = LLMClient(LLMClientConfig(provider="openai", model="gpt-4o-mini", api_key="abc"))._provider
    with pytest.raises(LLMRateLimitError):
        provider.generate("hello")


def test_provider_errors_do_not_expose_api_keys(monkeypatch):
    class FakeModel:
        def __init__(self, *args, **kwargs):
            pass

        def generate_content(self, *args, **kwargs):
            raise RuntimeError("secret api key abc123")

    fake_google_module = SimpleNamespace(
        configure=lambda *args, **kwargs: None,
        GenerativeModel=lambda model_name: FakeModel(),
    )
    monkeypatch.setitem(sys.modules, "google", SimpleNamespace(genai=fake_google_module))
    monkeypatch.setitem(sys.modules, "google.genai", fake_google_module)

    provider = LLMClient(LLMClientConfig(provider="gemini", model="gemini-2.5-flash", api_key="abc123"))._provider
    with pytest.raises(ProviderRequestError, match="Gemini request failed") as excinfo:
        provider.generate("hello")
    assert "abc123" not in str(excinfo.value)


def test_provider_initialization_failure_is_translated(monkeypatch):
    def broken_import():
        raise ImportError("SDK missing")

    monkeypatch.setitem(sys.modules, "google", None)
    monkeypatch.setitem(sys.modules, "google.genai", None)
    monkeypatch.setitem(sys.modules, "openai", None)

    with pytest.raises(ProviderInitializationError):
        LLMClient(LLMClientConfig(provider="gemini", model="gemini-2.5-flash", api_key="abc")).generate("hello")
