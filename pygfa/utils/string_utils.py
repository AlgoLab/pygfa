"""String utilities for pygfa."""

from __future__ import annotations

import logging

STRING_LOGGER = logging.getLogger(__name__)


def sanitize_string(s: str) -> tuple[str, bool]:
    """Replace non-ASCII characters with '?' and log warning.

    :param s: Input string
    :return: (sanitized string, was_sanitized: bool)
    """
    sanitized = []
    was_sanitized = False
    for char in s:
        if ord(char) > 127:
            was_sanitized = True
            sanitized.append("?")
        else:
            sanitized.append(char)

    if was_sanitized:
        STRING_LOGGER.warning(f"Non-ASCII characters found in string, replaced with '?': {s[:50]}...")

    return "".join(sanitized), was_sanitized
