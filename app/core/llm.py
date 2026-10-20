from typing import Literal

from langchain_anthropic import ChatAnthropic

from app.core.config import get_settings

Tier = Literal["fast", "smart"]


def model_name(tier: Tier) -> str:
    s = get_settings()
    return s.model_fast if tier == "fast" else s.model_smart


def get_llm(tier: Tier = "smart") -> ChatAnthropic:
    """fast = router, guards; smart = tree search, SQL, synthesis, eval judge."""
    return ChatAnthropic(model=model_name(tier), api_key=get_settings().anthropic_api_key, temperature=0)


def litellm_name(tier: Tier) -> str:
    """PageIndex calls models through LiteLLM, which needs the provider prefix."""
    return f"anthropic/{model_name(tier)}"
