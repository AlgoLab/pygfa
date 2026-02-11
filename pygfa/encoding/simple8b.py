"""Simple-8b integer encoding.

Packs integers using 8-bit selectors for various bit widths.
"""

from __future__ import annotations

import logging
import struct
from typing import List, Tuple

from pygfa.exceptions import InvalidEncodingError

logger = logging.getLogger(__name__)

# Simple-8b selectors and their bit widths
SIMPLE8B_SELECTORS = [
    (0, 0),  # 0: invalid
    (1, 60),  # 1: 1 bit x 60 values
    (2, 30),  # 2: 2 bits x 30 values
    (3, 20),  # 3: 3 bits x 20 values
    (4, 15),  # 4: 4 bits x 15 values
    (5, 12),  # 5: 5 bits x 12 values
    (6, 10),  # 6: 6 bits x 10 values
    (7, 8),  # 7: 7 bits x 8 values
    (8, 7),  # 8: 8 bits x 7 values (with 4 bits unused)
    (10, 6),  # 9: 10 bits x 6 values
    (12, 5),  # 10: 12 bits x 5 values
    (15, 4),  # 11: 15 bits x 4 values
    (20, 3),  # 12: 20 bits x 3 values
    (30, 2),  # 13: 30 bits x 2 values
    (60, 1),  # 14: 60 bits x 1 value
]


def compress_integer_list_simple8b(data: List[int]) -> bytes:
    """Compress integers using Simple-8b.

    Format:
    - uint32: number of values
    - sequence of 8-byte blocks with 4-bit selector + 60-bit data

    Args:
        data: List of integers to compress

    Returns:
        Compressed bytes
    """
    if not data:
        return struct.pack("<I", 0)

    n = len(data)
    result = bytearray()
    result.extend(struct.pack("<I", n))

    pos = 0
    while pos < n:
        # Find best selector for next chunk
        best_selector = 14  # Default to 60 bits per value
        best_count = 1

        for sel_idx, (bits, count) in enumerate(SIMPLE8B_SELECTORS[1:], 1):
            max_val = (1 << bits) - 1
            chunk = data[pos : pos + count]
            if all(0 <= v <= max_val for v in chunk):
                best_selector = sel_idx
                best_count = count
                break

        bits, count = SIMPLE8B_SELECTORS[best_selector]
        chunk = data[pos : pos + count]
        pos += len(chunk)

        # Pack into 60 bits (8 bytes with 4-bit selector)
        block = bytearray(8)
        block[0] = best_selector & 0x0F  # Lower 4 bits of first byte

        bit_pos = 4  # Start after selector
        for val in chunk:
            for b in range(bits):
                byte_idx = bit_pos // 8
                bit_idx = bit_pos % 8
                if byte_idx < 8:
                    if (val >> b) & 1:
                        block[byte_idx] |= 1 << bit_idx
                bit_pos += 1

        result.extend(block)

    return bytes(result)


def decompress_integer_list_simple8b(data: bytes, count: int) -> Tuple[List[int], int]:
    """Decompress Simple-8b encoded integers.

    Args:
        data: Compressed bytes
        count: Number of values to decompress (-1 for all)

    Returns:
        Tuple of (values, bytes_consumed)
    """
    if len(data) < 4:
        raise InvalidEncodingError("Data too short")

    n = struct.unpack_from("<I", data, 0)[0]
    if n == 0:
        return [], 4

    if count < 0:
        count = n

    values = []
    pos = 4

    while len(values) < count and pos < len(data):
        if pos + 8 > len(data):
            break

        selector = data[pos] & 0x0F
        if selector >= len(SIMPLE8B_SELECTORS):
            selector = 14

        bits, max_count = SIMPLE8B_SELECTORS[selector]

        # Unpack values
        block = data[pos : pos + 8]
        pos += 8

        bit_pos = 4
        for _ in range(max_count):
            if len(values) >= count:
                break
            val = 0
            for b in range(bits):
                byte_idx = bit_pos // 8
                bit_idx = bit_pos % 8
                if byte_idx < 8 and (block[byte_idx] >> bit_idx) & 1:
                    val |= 1 << b
                bit_pos += 1
            values.append(val)

    return values, pos


__all__ = [
    "compress_integer_list_simple8b",
    "decompress_integer_list_simple8b",
]
