"""BGFA codec utility functions."""

from __future__ import annotations

import math
import struct


def make_4byte_code(byte1: int, byte2: int, byte3: int, byte4: int) -> int:
    """Create a 4-byte strategy code."""
    return (byte1 << 24) | (byte2 << 16) | (byte3 << 8) | byte4


def split_4byte_code(code: int) -> tuple[int, int, int, int]:
    """Split a 4-byte strategy code into individual bytes."""
    return (code >> 24) & 0xFF, (code >> 16) & 0xFF, (code >> 8) & 0xFF, code & 0xFF


def pack_bits_lsb(bits: list[int]) -> bytes:
    """Pack a list of bits into bytes using LSB-first strategy within uint64 words.

    Bit at index i is stored at position (i % 64) within word (i // 64).
    Unused bits in the final word are set to 0.

    :param bits: List of 0/1 values
    :return: Packed bytes (multiple of 8 bytes)
    """
    n = len(bits)
    if n == 0:
        return b""

    num_uint64 = math.ceil(n / 64)
    result = bytearray()

    for word_idx in range(num_uint64):
        val = 0
        for bit_idx in range(64):
            idx = word_idx * 64 + bit_idx
            if idx < n and bits[idx]:
                val |= 1 << bit_idx  # LSB-first
        result.extend(struct.pack("<Q", val))

    return bytes(result)


def unpack_bits_lsb(data: bytes, count: int) -> tuple[list[int], int]:
    """Unpack bits from LSB-first packed uint64 words.

    :param data: Packed bytes
    :param count: Number of bits to extract
    :return: Tuple of (list of bits, bytes consumed)
    """
    if count == 0:
        return [], 0

    n = math.ceil(count / 64)
    bytes_consumed = n * 8
    result = []

    for word_idx in range(n):
        if word_idx * 8 + 8 > len(data):
            break
        val = struct.unpack_from("<Q", data, word_idx * 8)[0]
        for bit_idx in range(64):
            if len(result) >= count:
                break
            result.append((val >> bit_idx) & 1)

    return result, bytes_consumed
