"""Safety checks before the agent acts on a message."""

from __future__ import annotations

import re

INJECTION = re.compile(
    r"(ignore (all |any )?(previous|prior|above) (instructions|rules)|system override|admin mode|developer mode|"
    r"you are now|as the developer|i authori[sz]e you|without any checks|disregard (your|the) (rules|instructions))",
    re.I,
)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
CODE = re.compile(r"\b(\d{6})\b")
CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")


def is_injection(text: str) -> bool:
    return bool(INJECTION.search(text))


def redact(text: str) -> str:
    """For logs and model inputs: emails, card numbers and one-time codes removed."""
    text = CARD.sub("[card]", text)
    text = EMAIL.sub("[email]", text)
    return CODE.sub("[code]", text)


def email_in(text: str) -> str | None:
    m = EMAIL.search(text)
    return m.group(0) if m else None


def code_in(text: str) -> str | None:
    m = CODE.search(text)
    return m.group(1) if m else None
