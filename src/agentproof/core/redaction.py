from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

SECRET_KEY_FRAGMENTS = ("api_key", "authorization", "token", "password", "secret")
SECRET_STRING_PREFIXES = ("sk-", "Bearer ")
REDACTED = "[REDACTED]"


def redact(value: Any) -> Any:
    """Return a JSON-safe copy with obvious secrets removed."""

    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if _is_secret_key(key_text):
                redacted[key_text] = REDACTED
            else:
                redacted[key_text] = redact(item)
        return redacted
    if isinstance(value, str):
        return REDACTED if value.startswith(SECRET_STRING_PREFIXES) else value
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [redact(item) for item in value]
    return value


def _is_secret_key(key: str) -> bool:
    lowered = key.lower().replace("-", "_")
    return any(fragment in lowered for fragment in SECRET_KEY_FRAGMENTS)
