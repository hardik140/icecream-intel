"""Input checks before any retrieval: PII masking, off-topic / prompt-injection classification."""
import re
from typing import Literal

from pydantic import BaseModel

from app.core.llm import get_llm
from app.prompts import INPUT_CLASSIFIER

# Order matters: cards (13-19 digits) before phones so a card isn't half-masked as a phone.
_PII = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[EMAIL]"),
    (re.compile(r"\b(?:\d[ -]?){12,18}\d\b"), "[CARD]"),
    (re.compile(r"(?<!\w)\+?\d[\d -]{8,13}\d\b"), "[PHONE]"),
]


def scrub_pii(text: str) -> str:
    for pattern, label in _PII:
        text = pattern.sub(label, text)
    return text


class InputVerdict(BaseModel):
    label: Literal["ok", "off_topic", "injection"]
    reason: str


def classify_input(question: str) -> InputVerdict:
    llm = get_llm("fast").with_structured_output(InputVerdict)
    return llm.invoke(INPUT_CLASSIFIER.format(question=question))
