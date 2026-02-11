"""Brotli compression wrapper for pygfa.

Uses the brotli library for high compression ratio.
"""

from __future__ import annotations

import logging
from typing import List

import brotli

from pygfa.exceptions import InvalidCompressionError

logger = logging.getLogger(__name__)


def compress_string_brotli(string: str, quality: int = 4) -> bytes:
    """Compress string using Brotli.

    Brotli provides excellent compression ratios, especially for text data,
    but is slower than LZ4 or zstd.

    Args:
        string: Input string to compress
        quality: Compression quality (0-11, default: 4)
                Higher = better compression but slower

    Returns:
        Compressed bytes

    Raises:
        InvalidCompressionError: If compression fails
    """
    try:
        data = string.encode("utf-8")
        compressed = brotli.compress(data, quality=quality)
        return compressed
    except Exception as e:
        raise InvalidCompressionError(f"Brotli compression failed: {e}") from e


def decompress_string_brotli(data: bytes, lengths: List[int]) -> List[bytes]:
    """Decompress Brotli data and split by lengths.

    Args:
        data: Compressed bytes
        lengths: List of string lengths to extract

    Returns:
        List of decompressed byte strings

    Raises:
        InvalidCompressionError: If decompression fails
    """
    try:
        decompressed = brotli.decompress(data)

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
        raise InvalidCompressionError(f"Brotli decompression failed: {e}") from e


__all__ = [
    "compress_string_brotli",
    "decompress_string_brotli",
]
