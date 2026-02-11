"""Bit packing integer encoding.

Variable bit width encoding with byte alignment.
Each field is padded to byte boundary.
"""

from __future__ import annotations

import logging
import struct
from typing import List, Tuple

from pygfa.exceptions import InvalidEncodingError

logger = logging.getLogger(__name__)


def compute_bit_width(values: List[int]) -> int:
    """Compute minimum bit width needed to represent all values.

    Args:
        values: List of integer values

    Returns:
        Minimum number of bits needed (1-32)
    """
    if not values:
        return 1
    max_val = max(values)
    if max_val == 0:
        return 1
    # Find number of bits needed
    bits = max_val.bit_length()
    return min(bits, 32)  # Cap at 32 bits


def pack_values(values: List[int], bit_width: int) -> bytes:
    """Pack values using specified bit width, padded to byte boundary.

    Args:
        values: List of integers to pack
        bit_width: Bits per value (1-32)

    Returns:
        Packed bytes
    """
    if bit_width <= 0 or bit_width > 32:
        raise InvalidEncodingError(f"Invalid bit width: {bit_width}")

    # Calculate bytes needed per value (padded to byte boundary)
    bytes_per_value = (bit_width + 7) // 8

    result = bytearray()
    for val in values:
        # Pack value as little-endian
        for i in range(bytes_per_value):
            byte_val = (val >> (i * 8)) & 0xFF
            result.append(byte_val)

    return bytes(result)


def unpack_values(data: bytes, bit_width: int, count: int) -> List[int]:
    """Unpack values from bytes using specified bit width.

    Args:
        data: Packed bytes
        bit_width: Bits per value (1-32)
        count: Number of values to unpack

    Returns:
        List of unpacked integers
    """
    if bit_width <= 0 or bit_width > 32:
        raise InvalidEncodingError(f"Invalid bit width: {bit_width}")

    bytes_per_value = (bit_width + 7) // 8
    mask = (1 << bit_width) - 1

    values = []
    pos = 0
    for _ in range(count):
        if pos + bytes_per_value > len(data):
            raise InvalidEncodingError("Data too short for unpacking")

        val = 0
        for i in range(bytes_per_value):
            val |= data[pos + i] << (i * 8)
        values.append(val & mask)
        pos += bytes_per_value

    return values


def compress_integer_list_bitpacking(data: List[int]) -> bytes:
    """Compress integer list using bit packing.

    Format:
    - uint8: bit width
    - uint32: number of values
    - packed data (byte-aligned)

    Args:
        data: List of integers to compress

    Returns:
        Compressed bytes
    """
    if not data:
        return struct.pack("<BI", 0, 0)

    bit_width = compute_bit_width(data)
    packed = pack_values(data, bit_width)

    result = struct.pack("<BI", bit_width, len(data)) + packed
    return result


def decompress_integer_list_bitpacking(data: bytes, count: int) -> Tuple[List[int], int]:
    """Decompress integer list from bit packed format.

    Args:
        data: Compressed bytes
        count: Number of values to decompress (if -1, read from header)

    Returns:
        Tuple of (values, bytes_consumed)
    """
    if len(data) < 5:
        raise InvalidEncodingError("Data too short for bit packing header")

    bit_width = data[0]
    num_values = struct.unpack_from("<I", data, 1)[0]

    if count < 0:
        count = num_values
    else:
        count = min(count, num_values)

    if bit_width == 0 or count == 0:
        return [], 5

    bytes_per_value = (bit_width + 7) // 8
    header_size = 5
    data_size = bytes_per_value * count

    if header_size + data_size > len(data):
        raise InvalidEncodingError("Data too short for bit packed values")

    values = unpack_values(data[header_size:], bit_width, count)
    return values, header_size + data_size


__all__ = [
    "compress_integer_list_bitpacking",
    "decompress_integer_list_bitpacking",
]
