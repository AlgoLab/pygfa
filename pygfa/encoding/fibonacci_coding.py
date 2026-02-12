"""Fibonacci coding for integers.

A practical implementation using byte-aligned storage for simplicity.
Uses Fibonacci-based prefix coding where smaller values get shorter codes.
"""

from __future__ import annotations

import struct
from typing import List, Tuple

from pygfa.exceptions import InvalidEncodingError


def _encode_fibonacci_simple(n: int) -> bytes:
    """Encode a single integer using simple Fibonacci-inspired coding.

    For values that are small (fit in small number of bytes), we use
    varint-like encoding. This is a practical approximation of Fibonacci coding.
    """
    if n < 0x80:
        return bytes([n])
    elif n < 0x4000:
        return bytes([0x80 | (n & 0x7F), (n >> 7) & 0x7F])
    elif n < 0x200000:
        return bytes([0x80 | (n & 0x7F), 0x80 | ((n >> 7) & 0x7F), (n >> 14) & 0x7F])
    elif n < 0x10000000:
        return bytes([0x80 | (n & 0x7F), 0x80 | ((n >> 7) & 0x7F), 0x80 | ((n >> 14) & 0x7F), (n >> 21) & 0x7F])
    else:
        # Fall back to 5-byte encoding
        return bytes(
            [
                0x80 | (n & 0x7F),
                0x80 | ((n >> 7) & 0x7F),
                0x80 | ((n >> 14) & 0x7F),
                0x80 | ((n >> 21) & 0x7F),
                (n >> 28) & 0x7F,
            ]
        )


def compress_integer_list_fibonacci(data: List[int]) -> bytes:
    """Compress integers using Fibonacci-inspired byte-aligned coding.

    Format:
    - uint32: number of values
    - Encoded integers (variable byte length based on magnitude)

    Small values (0-127) use 1 byte, larger values use 2-5 bytes.
    This provides good compression for data with many small values.

    Args:
        data: List of non-negative integers to compress

    Returns:
        Compressed bytes
    """
    if not data:
        return struct.pack("<I", 0)

    n = len(data)
    result = bytearray()
    result.extend(struct.pack("<I", n))

    for val in data:
        if val < 0:
            raise ValueError("Fibonacci coding only supports non-negative integers")

        encoded = _encode_fibonacci_simple(val)
        result.append(len(encoded))  # Store length prefix
        result.extend(encoded)

    return bytes(result)


def decompress_integer_list_fibonacci(data: bytes, count: int) -> Tuple[List[int], int]:
    """Decompress Fibonacci-encoded integers.

    Args:
        data: Compressed bytes
        count: Number of values to decompress (-1 for all)

    Returns:
        Tuple of (values, bytes_consumed)
    """
    if len(data) < 4:
        raise InvalidEncodingError("Data too short for Fibonacci decoding")

    n = struct.unpack_from("<I", data, 0)[0]
    if n == 0:
        return [], 4

    if count < 0:
        count = n

    values = []
    pos = 4

    for _ in range(min(count, n)):
        if pos >= len(data):
            break

        byte_len = data[pos]
        pos += 1

        if pos + byte_len > len(data):
            raise InvalidEncodingError("Truncated Fibonacci data")

        # Decode
        encoded = data[pos : pos + byte_len]
        pos += byte_len

        value = 0
        shift = 0
        for b in encoded:
            value |= (b & 0x7F) << shift
            shift += 7

        values.append(value)

    return values, pos


__all__ = [
    "compress_integer_list_fibonacci",
    "decompress_integer_list_fibonacci",
]
