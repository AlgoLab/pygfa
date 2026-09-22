"""String utilities for pygfa."""

from __future__ import annotations

import logging

STRING_LOGGER = logging.getLogger(__name__)

# Maps every non-ASCII code point to '?'.
_TRANSLATION_TABLE = {i: ord("?") for i in range(128, 256)}


def sanitize_string(s: str) -> tuple[str, bool]:
    """Replace non-ASCII characters with '?' and log warning.

    :param s: Input string
    :return: (sanitized string, was_sanitized: bool)
    """
    sanitized = s.translate(_TRANSLATION_TABLE)
    was_sanitized = sanitized != s

    if was_sanitized:
        STRING_LOGGER.warning(f"Non-ASCII characters found in string, replaced with '?': {s[:50]}...")

    return sanitized, was_sanitized
