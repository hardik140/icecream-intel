"""LLM factory. Two providers work together: each tier has a primary model and a fallback on the other
provider, so a quota error or outage on one switches to the other automatically.

Models are "provider:model" strings, e.g. "google_genai:gemini-3.5-flash" or "groq:openai/gpt-oss-20b".
"""
from functools import lru_cache
from typing import Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain_core.runnables import Runnable
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq

from app.core.config import get_settings

Tier = Literal["fast", "smart"]
LITELLM_PREFIX = {"google_genai": "gemini", "groq": "groq"}  # PageIndex calls models through LiteLLM


def _specs(tier: Tier) -> list[str]:
    """Primary then fallback, skipping providers without an API key."""
    s = get_settings()
    specs = [s.model_fast, s.model_fast_fallback] if tier == "fast" else [s.model_smart, s.model_smart_fallback]
    keys = {"google_genai": s.google_api_key, "groq": s.groq_api_key}
    usable = [sp for sp in specs if sp and keys.get(sp.split(":", 1)[0])]
    if not usable:
        raise ValueError(f"No API key for any {tier} model ({specs}). Set GOOGLE_API_KEY and/or GROQ_API_KEY.")
    return usable


@lru_cache
def _chat_model(spec: str) -> BaseChatModel:
    """One instance + rate limiter per model, shared by every call, so we stay under its quota.

    shortcut: per-process limiter; with several workers each gets the full budget.
    """
    s = get_settings()
    provider, model = spec.split(":", 1)
    rpm = s.gemini_rpm if provider == "google_genai" else s.groq_rpm
    limiter = InMemoryRateLimiter(requests_per_second=rpm / 60, check_every_n_seconds=0.2, max_bucket_size=1)
    if provider == "google_genai":
        # Gemini free quota is per day: retrying is pointless, fail over to the other provider at once
        return ChatGoogleGenerativeAI(model=model, google_api_key=s.google_api_key, rate_limiter=limiter, max_retries=1)
    if provider == "groq":
        # Groq free quota is tokens per minute and refills in seconds; its client honours retry-after
        return ChatGroq(model=model, api_key=s.groq_api_key, rate_limiter=limiter, max_retries=4)
    raise ValueError(f"Unknown provider in {spec!r}; use google_genai: or groq:")


class LLM:
    """Same two methods the code uses on a chat model, each with automatic provider fallback."""

    def __init__(self, tier: Tier):
        self.models = [_chat_model(sp) for sp in _specs(tier)]

    @staticmethod
    def _chain(runnables: list[Runnable]) -> Runnable:
        return runnables[0].with_fallbacks(runnables[1:]) if len(runnables) > 1 else runnables[0]

    def invoke(self, prompt):
        return self._chain(self.models).invoke(prompt)

    def with_structured_output(self, schema) -> Runnable:
        # Groq's default (tool calling) fails on gpt-oss models ("model did not call a tool"); json_schema works
        return self._chain([m.with_structured_output(schema, method="json_schema") if isinstance(m, ChatGroq)
                            else m.with_structured_output(schema) for m in self.models])


def get_llm(tier: Tier = "smart") -> LLM:
    """fast = guards, router, judges; smart = tree search, SQL, synthesis."""
    return LLM(tier)


def litellm_name(tier: Tier) -> str:
    provider, model = _specs(tier)[0].split(":", 1)
    return f"{LITELLM_PREFIX[provider]}/{model}"
