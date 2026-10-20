"""Input checks before any retrieval: size, PII masking, off-topic / prompt-injection."""
from typing import Literal


def scrub_pii(text: str) -> str:
    """Mask emails, phone numbers, card numbers. (M5)"""
    raise NotImplementedError("M5")


def classify_input(question: str) -> Literal["ok", "off_topic", "injection"]:
    """Cheap-model classifier. (M5)"""
    raise NotImplementedError("M5")
