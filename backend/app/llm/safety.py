from __future__ import annotations

# ---------------------------------------------------------------------------
# Rules-based safety validator
# ---------------------------------------------------------------------------

_INJECTION_PATTERNS: tuple[str, ...] = (
    "ignore previous instructions",
    "ignore all previous",
    "disregard your",
    "you are now",
    "pretend you are",
    "act as if",
    "system:",
    "\n\nsystem",
    "[system]",
)

_DENYLIST_WORDS: tuple[str, ...] = (
    "bomb",
    "weapon",
    "exploit",
    "malware",
    "ransomware",
)

_MAX_INPUT_LENGTH = 4000


def validate_input(text: str) -> tuple[bool, str]:
    """Return (True, "") if the input is safe, else (False, reason)."""
    if len(text) > _MAX_INPUT_LENGTH:
        return False, "input_too_long"

    lower = text.lower()

    for pattern in _INJECTION_PATTERNS:
        if pattern.lower() in lower:
            return False, "injection_attempt"

    for word in _DENYLIST_WORDS:
        if word in lower:
            return False, f"denylist_word:{word}"

    return True, ""


def validate_output(text: str) -> tuple[bool, str]:
    """Return (True, "") if the LLM output is safe, else (False, reason)."""
    lower = text.lower()

    for pattern in _INJECTION_PATTERNS:
        if pattern.lower() in lower:
            return False, "injection_in_output"

    for word in _DENYLIST_WORDS:
        if word in lower:
            return False, f"denylist_word:{word}"

    return True, ""
