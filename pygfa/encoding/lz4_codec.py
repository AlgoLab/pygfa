"""LZ4 compression wrapper for pygfa.

Uses the lz4 library for fast compression.
"""

from __future__ import annotations

import logging
from typing import List

import lz4.frame

from pygfa.exceptions import InvalidCompressionError

logger = logging.getLogger(__name__)


def compress_string_lz4(string: str) -> bytes:
    """Compress string using LZ4.

    LZ4 provides very fast compression and decompression,
    making it ideal for real-time applications.

    Args:
        string: Input string to compress

    Returns:
        Compressed bytes

    Raises:
        InvalidCompressionError: If compression fails
    """
    try:
        data = string.encode("utf-8")
        compressed = lz4.frame.compress(data)
        return compressed
    except Exception as e:
        raise InvalidCompressionError(f"LZ4 compression failed: {e}") from e


def decompress_string_lz4(data: bytes, lengths: List[int]) -> List[bytes]:
    """Decompress LZ4 data and split by lengths.

    Args:
        data: Compressed bytes
        lengths: List of string lengths to extract

    Returns:
        List of decompressed byte strings

    Raises:
        InvalidCompressionError: If decompression fails
    """
    try:
        decompressed = lz4.frame.decompress(data)

        # Split by lengths
        result = []
        pos = 0
        for length in lengths:
            if pos + length > len(decompressed):
                raise InvalidCompressionError(f"Data too short: need {pos + length} bytes, have {len(decompressed)}")
            result.append(decompressed[pos : pos + length])
            pos += length

        return result
    except Exception as e:
        raise InvalidCompressionError(f"LZ4 decompression failed: {e}") from e


__all__ = [
    "compress_string_lz4",
    "decompress_string_lz4",
]
