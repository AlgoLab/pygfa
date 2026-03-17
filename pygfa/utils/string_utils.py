"""String utilities for pygfa."""

from __future__ import annotations

import logging

STRING_LOGGER = logging.getLogger(__name__)


def sanitize_string(s: str) -> tuple[str, bool]:
    """Replace non-ASCII characters with '?' and log warning.

    :param s: Input string
    :return: (sanitized string, was_sanitized: bool)
    """
    # Create translation table once (cached on function)
    if not hasattr(sanitize_string, "_translation_table"):
        sanitize_string._translation_table = {}
        for i in range(128, 256):
            sanitize_string._translation_table[i] = ord("?")

    # Use translate for bulk of work
    sanitized = s.translate(sanitize_string._translation_table)
    was_sanitized = sanitized != s

    if was_sanitized:
        STRING_LOGGER.warning(f"Non-ASCII characters found in string, replaced with '?': {s[:50]}...")

    return sanitized, was_sanitized
