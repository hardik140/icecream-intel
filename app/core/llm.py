from typing import Literal

from langchain_anthropic import ChatAnthropic

from app.core.config import get_settings


def get_llm(tier: Literal["fast", "smart"] = "smart") -> ChatAnthropic:
    """fast = router, guards; smart = SQL, synthesis, eval judge."""
    s = get_settings()
    model = s.model_fast if tier == "fast" else s.model_smart
    return ChatAnthropic(model=model, api_key=s.anthropic_api_key, temperature=0)
