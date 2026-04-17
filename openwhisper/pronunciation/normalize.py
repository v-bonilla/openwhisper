from __future__ import annotations

import re

_PUNCT_RE = re.compile(r"[^a-z0-9']+")


def normalize_text(text: str) -> str:
    lowered = text.lower()
    cleaned = _PUNCT_RE.sub(" ", lowered)
    tokens = [token.strip("'") for token in cleaned.split()]
    return " ".join(token for token in tokens if token)


def tokenize(text: str) -> list[str]:
    normalized = normalize_text(text)
    return normalized.split() if normalized else []
