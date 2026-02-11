"""Group Varint integer encoding.

Encodes groups of 4 integers using a single tag byte + variable-length data.
"""

from __future__ import annotations

import logging
import struct
from typing import List, Tuple

from pygfa.exceptions import InvalidEncodingError

logger = logging.getLogger(__name__)


def encode_varint(value: int) -> bytes:
    """Encode a single integer as varint."""
    result = bytearray()
    while value >= 128:
        result.append((value & 0x7F) | 0x80)
        value >>= 7
    result.append(value)
    return bytes(result)


def decode_varint(data: bytes, pos: int) -> Tuple[int, int]:
    """Decode varint from position, return (value, new_position)."""
    val = 0
    shift = 0
    while True:
        if pos >= len(data):
            raise InvalidEncodingError("Truncated varint")
        b = data[pos]
        pos += 1
        val |= (b & 0x7F) << shift
        if (b & 0x80) == 0:
            break
        shift += 7
    return val, pos


def compress_integer_list_group_varint(data: List[int]) -> bytes:
    """Compress integers using Group Varint.

    Format:
    - uint32: number of values
    - groups of 4 values encoded with 1-byte tag + data

    Tag byte format (2 bits per value):
    - 00: 1 byte
    - 01: 2 bytes
    - 10: 3 bytes
    - 11: 4 bytes

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

    # Process in groups of 4
    for i in range(0, n, 4):
        group = data[i : i + 4]

        # Determine size for each value
        tag = 0
        encoded_values = []

        for j, val in enumerate(group):
            if val < (1 << 8):
                size_code = 0  # 1 byte
            elif val < (1 << 16):
                size_code = 1  # 2 bytes
            elif val < (1 << 24):
                size_code = 2  # 3 bytes
            else:
                size_code = 3  # 4 bytes

            tag |= size_code << (j * 2)

            # Encode value (little-endian)
            encoded = val.to_bytes(size_code + 1, "little")
            encoded_values.append(encoded)

        result.append(tag)
        for enc in encoded_values:
            result.extend(enc)

    return bytes(result)


def decompress_integer_list_group_varint(data: bytes, count: int) -> Tuple[List[int], int]:
    """Decompress Group Varint encoded integers.

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
        tag = data[pos]
        pos += 1

        for i in range(4):
            if len(values) >= count:
                break

            size_code = (tag >> (i * 2)) & 0x03
            size = size_code + 1

            if pos + size > len(data):
                raise InvalidEncodingError("Truncated group varint data")

            val = int.from_bytes(data[pos : pos + size], "little")
            values.append(val)
            pos += size

    return values, pos


__all__ = [
    "compress_integer_list_group_varint",
    "decompress_integer_list_group_varint",
]
