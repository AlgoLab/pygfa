"""MaskedVByte integer encoding.

A SIMD-friendly variant of variable-length byte encoding that uses continuation
bits in the high bit position. This format is compatible with fast SIMD decoding
algorithms while maintaining reasonable compression ratios.

Format: Each byte uses bit 7 as continuation flag (1 = more bytes follow).
"""

from __future__ import annotations

import struct
from typing import List, Tuple

from pygfa.exceptions import InvalidEncodingError


def _encode_masked_vbyte(value: int) -> bytearray:
    """Encode a single integer using MaskedVByte format.

    Args:
        value: Non-negative integer to encode

    Returns:
        Encoded bytes
    """
    if value == 0:
        return bytearray([0])

    result = bytearray()
    while value > 0:
        # Take 7 bits
        byte = value & 0x7F
        value >>= 7
        # Set continuation bit if more bytes follow
        if value > 0:
            byte |= 0x80
        result.append(byte)

    return result


def _decode_masked_vbyte(data: bytes, pos: int) -> Tuple[int, int]:
    """Decode a single MaskedVByte encoded integer.

    Args:
        data: Byte array containing encoded data
        pos: Starting position

    Returns:
        Tuple of (decoded_value, new_position)
    """
    val = 0
    shift = 0

    while pos < len(data):
        b = data[pos]
        pos += 1
        val |= (b & 0x7F) << shift
        if (b & 0x80) == 0:
            break
        shift += 7
        if shift > 63:
            raise InvalidEncodingError("MaskedVByte value too large")

    return val, pos


def compress_integer_list_masked_vbyte(data: List[int]) -> bytes:
    """Compress integers using MaskedVByte encoding.

    Format:
    - uint32: number of values
    - MaskedVByte encoded integers

    Args:
        data: List of non-negative integers to compress

    Returns:
        Compressed bytes
    """
    if not data:
        return struct.pack("<I", 0)

    n = len(data)

    # Encode all values
    result = bytearray()
    result.extend(struct.pack("<I", n))

    for val in data:
        if val < 0:
            raise ValueError("MaskedVByte encoding only supports non-negative integers")
        encoded = _encode_masked_vbyte(val)
        result.extend(encoded)

    return bytes(result)


def decompress_integer_list_masked_vbyte(data: bytes, count: int) -> Tuple[List[int], int]:
    """Decompress MaskedVByte encoded integers.

    Args:
        data: Compressed bytes
        count: Number of values to decompress (-1 for all)

    Returns:
        Tuple of (values, bytes_consumed)
    """
    if len(data) < 4:
        raise InvalidEncodingError("Data too short for MaskedVByte decoding")

    n = struct.unpack_from("<I", data, 0)[0]
    if n == 0:
        return [], 4

    if count < 0:
        count = n

    values = []
    pos = 4

    while len(values) < count and pos < len(data):
        val, pos = _decode_masked_vbyte(data, pos)
        values.append(val)

    return values, pos


__all__ = [
    "compress_integer_list_masked_vbyte",
    "decompress_integer_list_masked_vbyte",
]
