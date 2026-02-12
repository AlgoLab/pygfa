"""Byte-Packed Auto-width integer encoding.

Automatically selects the smallest byte width (1, 2, 4, or 8 bytes) based on
the maximum value in the dataset. This provides optimal space efficiency when
values have a limited range.
"""

from __future__ import annotations

import struct
from typing import List, Tuple

from pygfa.exceptions import InvalidEncodingError


def _get_min_byte_width(max_value: int) -> int:
    """Determine minimum byte width needed to represent max_value.

    Args:
        max_value: Maximum value to encode

    Returns:
        Byte width (1, 2, 4, or 8)
    """
    if max_value <= 0xFF:
        return 1
    elif max_value <= 0xFFFF:
        return 2
    elif max_value <= 0xFFFFFFFF:
        return 4
    else:
        return 8


def compress_integer_list_byte_packed(data: List[int]) -> bytes:
    """Compress integers using byte-packed auto-width encoding.

    Format:
    - uint32: number of values
    - uint8: byte width (1, 2, 4, or 8)
    - packed integers (little-endian, fixed width)

    Args:
        data: List of non-negative integers to compress

    Returns:
        Compressed bytes
    """
    if not data:
        return struct.pack("<I", 0) + bytes([1])

    n = len(data)

    # Check for negative values
    for val in data:
        if val < 0:
            raise ValueError("Byte-packed encoding only supports non-negative integers")

    # Determine optimal byte width
    max_value = max(data) if data else 0
    byte_width = _get_min_byte_width(max_value)

    # Pack the data
    result = bytearray()
    result.extend(struct.pack("<I", n))
    result.append(byte_width)

    for val in data:
        result.extend(val.to_bytes(byte_width, byteorder="little", signed=False))

    return bytes(result)


def decompress_integer_list_byte_packed(data: bytes, count: int) -> Tuple[List[int], int]:
    """Decompress byte-packed auto-width encoded integers.

    Args:
        data: Compressed bytes
        count: Number of values to decompress (-1 for all)

    Returns:
        Tuple of (values, bytes_consumed)
    """
    if len(data) < 5:
        raise InvalidEncodingError("Data too short for byte-packed decoding")

    n = struct.unpack_from("<I", data, 0)[0]
    if n == 0:
        return [], 5

    byte_width = data[4]
    if byte_width not in (1, 2, 4, 8):
        raise InvalidEncodingError(f"Invalid byte width: {byte_width}")

    if count < 0:
        count = n

    values = []
    pos = 5

    for _ in range(min(count, n)):
        if pos + byte_width > len(data):
            raise InvalidEncodingError("Truncated byte-packed data")

        val = int.from_bytes(data[pos : pos + byte_width], byteorder="little", signed=False)
        values.append(val)
        pos += byte_width

    return values, pos


__all__ = [
    "compress_integer_list_byte_packed",
    "decompress_integer_list_byte_packed",
]
