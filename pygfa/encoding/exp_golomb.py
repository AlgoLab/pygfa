"""Exp-Golomb coding for integers.

Exp-Golomb coding is used in H.264/HEVC video compression and is optimal for
data following a geometric distribution where smaller values are more frequent.
It encodes non-negative integers using unary coding for the exponent and
binary coding for the remainder.
"""

from __future__ import annotations

import math
import struct
from typing import List, Tuple

from pygfa.exceptions import InvalidEncodingError


def _encode_exp_golomb(n: int, k: int = 0) -> List[int]:
    """Encode a single integer using Exp-Golomb coding with parameter k.

    Args:
        n: Non-negative integer to encode
        k: Coding parameter (default 0 for standard Exp-Golomb)

    Returns:
        List of bits (0s and 1s)
    """
    if n < 0:
        raise ValueError("Exp-Golomb coding only supports non-negative integers")

    # Exp-Golomb formula: encode floor(n / 2^k) using unary + binary
    # Then encode remainder n % 2^k in k bits

    quotient = n >> k  # floor(n / 2^k)

    # Encode quotient + 1 in unary (quotient zeros followed by 1)
    bits = [0] * quotient + [1]

    # Encode remainder in k bits
    remainder = n & ((1 << k) - 1)  # n % 2^k
    for i in range(k - 1, -1, -1):
        bits.append((remainder >> i) & 1)

    return bits


def _decode_exp_golomb(data: bytes, bit_pos: int, k: int = 0) -> Tuple[int, int]:
    """Decode a single Exp-Golomb encoded integer.

    Args:
        data: Byte array containing encoded data
        bit_pos: Starting bit position
        k: Coding parameter

    Returns:
        Tuple of (decoded_value, new_bit_position)
    """
    # Read unary code: count leading zeros
    quotient = 0
    total_bits = len(data) * 8

    while bit_pos < total_bits:
        byte_idx = bit_pos // 8
        bit_idx_in_byte = 7 - (bit_pos % 8)

        if byte_idx >= len(data):
            raise InvalidEncodingError("Truncated Exp-Golomb code")

        bit = (data[byte_idx] >> bit_idx_in_byte) & 1
        bit_pos += 1

        if bit == 1:
            break
        quotient += 1

    # Read k-bit remainder
    remainder = 0
    for _ in range(k):
        if bit_pos >= total_bits:
            raise InvalidEncodingError("Truncated Exp-Golomb remainder")

        byte_idx = bit_pos // 8
        bit_idx_in_byte = 7 - (bit_pos % 8)
        bit = (data[byte_idx] >> bit_idx_in_byte) & 1
        remainder = (remainder << 1) | bit
        bit_pos += 1

    # Decode: n = (quotient * 2^k) + remainder
    value = (quotient << k) | remainder

    return value, bit_pos


def compress_integer_list_exp_golomb(data: List[int], k: int = 0) -> bytes:
    """Compress integers using Exp-Golomb coding.

    Format:
    - uint32: number of values
    - uint8: parameter k
    - Exp-Golomb encoded integers (bit-packed)

    Args:
        data: List of non-negative integers to compress
        k: Exp-Golomb parameter (0 for standard, higher for larger values)

    Returns:
        Compressed bytes
    """
    if not data:
        return struct.pack("<I", 0) + bytes([k])

    # Auto-select k if not specified (k=0)
    if k == 0 and len(data) > 0:
        # Estimate optimal k based on data distribution
        max_val = max(data)
        if max_val > 0:
            # k = floor(log2(mean / 2)) is a heuristic
            mean_val = sum(data) / len(data)
            if mean_val > 1:
                k = max(0, int(math.log2(mean_val)) - 1)

    n = len(data)

    # Encode all values to bits
    all_bits = []
    for val in data:
        if val < 0:
            raise ValueError("Exp-Golomb coding only supports non-negative integers")
        bits = _encode_exp_golomb(val, k)
        all_bits.extend(bits)

    # Convert bits to bytes
    result = bytearray()
    result.extend(struct.pack("<I", n))
    result.append(k)

    current_byte = 0
    bit_count = 0

    for bit in all_bits:
        current_byte = (current_byte << 1) | bit
        bit_count += 1
        if bit_count == 8:
            result.append(current_byte)
            current_byte = 0
            bit_count = 0

    # Pad final byte
    if bit_count > 0:
        current_byte <<= 8 - bit_count
        result.append(current_byte)

    return bytes(result)


def decompress_integer_list_exp_golomb(data: bytes, count: int) -> Tuple[List[int], int]:
    """Decompress Exp-Golomb encoded integers.

    Args:
        data: Compressed bytes
        count: Number of values to decompress (-1 for all)

    Returns:
        Tuple of (values, bytes_consumed)
    """
    if len(data) < 5:
        raise InvalidEncodingError("Data too short for Exp-Golomb decoding")

    n = struct.unpack_from("<I", data, 0)[0]
    if n == 0:
        return [], 5

    k = data[4]

    if count < 0:
        count = n

    values = []
    bit_pos = 40  # Start after the header (4 bytes count + 1 byte k)
    total_bits = len(data) * 8

    while len(values) < count and bit_pos < total_bits:
        value, bit_pos = _decode_exp_golomb(data, bit_pos, k)
        values.append(value)

    # Calculate bytes consumed
    bytes_consumed = (bit_pos + 7) // 8

    return values, bytes_consumed


__all__ = [
    "compress_integer_list_exp_golomb",
    "decompress_integer_list_exp_golomb",
]
