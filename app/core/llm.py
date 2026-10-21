from typing import Literal

from functools import lru_cache

from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import get_settings

Tier = Literal["fast", "smart"]


def model_name(tier: Tier) -> str:
    s = get_settings()
    return s.model_fast if tier == "fast" else s.model_smart


@lru_cache
def _rate_limiter(tier: Tier) -> InMemoryRateLimiter:
    """One limiter per model, shared by every call, so we stay under the per-minute quota.

    shortcut: per-process; with several workers each gets the full budget. Use a shared limiter
    (e.g. Redis) or a paid quota when running more than one process.
    """
    s = get_settings()
    rpm = s.llm_rpm_fast if tier == "fast" else s.llm_rpm_smart
    return InMemoryRateLimiter(requests_per_second=rpm / 60, check_every_n_seconds=0.2, max_bucket_size=1)


def get_llm(tier: Tier = "smart") -> ChatGoogleGenerativeAI:
    """fast = router, guards; smart = tree search, SQL, synthesis, eval judge."""
    return ChatGoogleGenerativeAI(model=model_name(tier), google_api_key=get_settings().google_api_key,
                                  rate_limiter=_rate_limiter(tier),
                                  max_retries=3)  # Gemini 3.x uses fixed sampling; temperature is ignored


def litellm_name(tier: Tier) -> str:
    """PageIndex calls models through LiteLLM, which needs the provider prefix."""
    return f"gemini/{model_name(tier)}"
