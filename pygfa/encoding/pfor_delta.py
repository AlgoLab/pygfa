"""PFOR-DELTA (Patched Frame-of-Reference with Delta) integer encoding.

Combines frame-of-reference with delta encoding and patches for outliers.
"""

from __future__ import annotations

import logging
import struct
from typing import List, Tuple

from pygfa.exceptions import InvalidEncodingError

logger = logging.getLogger(__name__)


def compress_integer_list_pfor_delta(data: List[int]) -> bytes:
    """Compress integers using PFOR-DELTA.

    Algorithm:
    1. Find base value (minimum)
    2. Delta encode from base
    3. Identify outliers (values > threshold)
    4. Patch outliers separately

    Format:
    - uint32: number of values
    - uint32: base value
    - uint32: threshold for outliers
    - uint32: number of outliers
    - outlier positions (varint encoded)
    - outlier values (varint encoded)
    - packed deltas for regular values

    Args:
        data: List of integers to compress

    Returns:
        Compressed bytes
    """
    if not data:
        return struct.pack("<I", 0)

    n = len(data)
    if n == 0:
        return struct.pack("<I", 0)

    # Find base (minimum value)
    base = min(data)

    # Delta encode
    deltas = [v - base for v in data]

    # Determine threshold (e.g., 95th percentile)
    sorted_deltas = sorted(deltas)
    threshold_idx = int(len(sorted_deltas) * 0.95)
    threshold = sorted_deltas[min(threshold_idx, len(sorted_deltas) - 1)]
    threshold = max(threshold, 1)  # At least 1

    # Separate outliers and regular values
    outlier_positions = []
    outlier_values = []
    regular_deltas = []

    for i, d in enumerate(deltas):
        if d > threshold:
            outlier_positions.append(i)
            outlier_values.append(d)
            regular_deltas.append(0)  # Placeholder
        else:
            regular_deltas.append(d)

    # Pack regular deltas using bit width needed for threshold
    bit_width = max(1, threshold.bit_length())
    bit_width = min(bit_width, 32)
    bytes_per_value = (bit_width + 7) // 8

    # Build output
    result = bytearray()
    result.extend(struct.pack("<I", n))  # count
    result.extend(struct.pack("<i", base))  # base (signed)
    result.extend(struct.pack("<I", threshold))  # threshold
    result.extend(struct.pack("<I", len(outlier_positions)))  # num outliers

    # Encode outlier positions (varint)
    for pos in outlier_positions:
        # Simple varint encoding
        val = pos
        while val >= 128:
            result.append((val & 0x7F) | 0x80)
            val >>= 7
        result.append(val)

    # Encode outlier values (varint)
    for val in outlier_values:
        v = val
        while v >= 128:
            result.append((v & 0x7F) | 0x80)
            v >>= 7
        result.append(v)

    # Pack regular deltas
    for d in regular_deltas:
        for i in range(bytes_per_value):
            result.append((d >> (i * 8)) & 0xFF)

    return bytes(result)


def decompress_integer_list_pfor_delta(data: bytes, count: int) -> Tuple[List[int], int]:
    """Decompress PFOR-DELTA encoded integers.

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

    pos = 4
    base = struct.unpack_from("<i", data, pos)[0]
    pos += 4

    threshold = struct.unpack_from("<I", data, pos)[0]
    pos += 4

    num_outliers = struct.unpack_from("<I", data, pos)[0]
    pos += 4

    # Decode outlier positions
    outlier_positions = []
    for _ in range(num_outliers):
        val = 0
        shift = 0
        while True:
            if pos >= len(data):
                raise InvalidEncodingError("Truncated outlier positions")
            b = data[pos]
            pos += 1
            val |= (b & 0x7F) << shift
            if (b & 0x80) == 0:
                break
            shift += 7
        outlier_positions.append(val)

    # Decode outlier values
    outlier_values = []
    for _ in range(num_outliers):
        val = 0
        shift = 0
        while True:
            if pos >= len(data):
                raise InvalidEncodingError("Truncated outlier values")
            b = data[pos]
            pos += 1
            val |= (b & 0x7F) << shift
            if (b & 0x80) == 0:
                break
            shift += 7
        outlier_values.append(val)

    # Calculate bit width and read regular deltas
    bit_width = max(1, threshold.bit_length())
    bit_width = min(bit_width, 32)
    bytes_per_value = (bit_width + 7) // 8

    # Read regular deltas
    regular_deltas = []
    for i in range(n):
        if pos + bytes_per_value > len(data):
            raise InvalidEncodingError("Truncated delta data")
        d = 0
        for j in range(bytes_per_value):
            d |= data[pos + j] << (j * 8)
        # Mask to bit_width
        d &= (1 << bit_width) - 1
        regular_deltas.append(d)
        pos += bytes_per_value

    # Reconstruct values
    # Apply outliers
    for idx, val in zip(outlier_positions, outlier_values):
        if idx < len(regular_deltas):
            regular_deltas[idx] = val

    # Add base back
    values = [d + base for d in regular_deltas]

    if count > 0:
        values = values[:count]

    return values, pos


__all__ = [
    "compress_integer_list_pfor_delta",
    "decompress_integer_list_pfor_delta",
]
