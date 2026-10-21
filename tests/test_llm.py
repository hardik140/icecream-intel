"""Provider selection and fallback, without network calls."""
import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from app.core import llm
from app.core.config import get_settings


class Broken(FakeListChatModel):
    def _call(self, *args, **kwargs):
        raise RuntimeError("429 RESOURCE_EXHAUSTED")


def _set(monkeypatch, **env):
    env = {"MODEL_FAST": "groq:openai/gpt-oss-20b", "MODEL_FAST_FALLBACK": "google_genai:gemini-3.5-flash-lite",
           "MODEL_SMART": "google_genai:gemini-3.5-flash", "MODEL_SMART_FALLBACK": "groq:openai/gpt-oss-120b", **env}
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    get_settings.cache_clear()


def test_both_keys_gives_primary_then_fallback(monkeypatch):
    _set(monkeypatch, GOOGLE_API_KEY="g", GROQ_API_KEY="q")
    assert llm._specs("fast") == ["groq:openai/gpt-oss-20b", "google_genai:gemini-3.5-flash-lite"]
    assert llm._specs("smart") == ["google_genai:gemini-3.5-flash", "groq:openai/gpt-oss-120b"]
    _set(monkeypatch, MODEL_SMART_FALLBACK="groq:a, groq:b")
    assert llm._specs("smart") == ["google_genai:gemini-3.5-flash", "groq:a", "groq:b"]
    assert llm.litellm_name("smart") == "gemini/gemini-3.5-flash"


def test_missing_key_skips_that_provider(monkeypatch):
    _set(monkeypatch, GOOGLE_API_KEY="", GROQ_API_KEY="q")
    assert llm._specs("smart") == ["groq:openai/gpt-oss-120b"]
    assert llm.litellm_name("smart") == "groq/openai/gpt-oss-120b"


def test_no_keys_is_a_clear_error(monkeypatch):
    _set(monkeypatch, GOOGLE_API_KEY="", GROQ_API_KEY="")
    with pytest.raises(ValueError, match="No API key"):
        llm._specs("fast")


def test_failing_primary_falls_back(monkeypatch):
    _set(monkeypatch, GOOGLE_API_KEY="g", GROQ_API_KEY="q")
    fakes = {"google_genai:gemini-3.5-flash": Broken(responses=["never"]),
             "groq:openai/gpt-oss-120b": FakeListChatModel(responses=["from groq"])}
    monkeypatch.setattr(llm, "_chat_model", fakes.__getitem__)
    assert llm.get_llm("smart").invoke("hi").content == "from groq"
