"""BGFA codec utility functions."""

from __future__ import annotations

import math
import struct
from typing import Any


def make_4byte_code(byte1: int, byte2: int, byte3: int, byte4: int) -> int:
    """Create a 4-byte strategy code."""
    return (byte1 << 24) | (byte2 << 16) | (byte3 << 8) | byte4


def split_4byte_code(code: int) -> tuple[int, int, int, int]:
    """Split a 4-byte strategy code into individual bytes."""
    return (code >> 24) & 0xFF, (code >> 16) & 0xFF, (code >> 8) & 0xFF, code & 0xFF


def pack_bits_lsb(bits: list[int], use_numpy: bool = False) -> bytes:
    """Pack a list of bits into bytes using LSB-first strategy within uint64 words.

    Bit at index i is stored at position (i % 64) within word (i // 64).
    Unused bits in the final word are set to 0.

    :param bits: List of 0/1 values
    :param use_numpy: Use numpy-accelerated backend if available
    :return: Packed bytes (multiple of 8 bytes)
    """
    if use_numpy:
        try:
            from pygfa.encoding.numpy_backend import pack_bits_lsb_numpy

            return pack_bits_lsb_numpy(bits)
        except ImportError:
            pass

    n = len(bits)
    if n == 0:
        return b""

    num_uint64 = math.ceil(n / 64)
    result = bytearray()

    for word_idx in range(num_uint64):
        start = word_idx * 64
        end = min(start + 64, n)
        val = 0
        for i in range(start, end):
            if bits[i]:
                val |= 1 << (i - start)  # LSB-first
        result.extend(struct.pack("<Q", val))

    return bytes(result)


def unpack_bits_lsb(data: bytes, count: int, use_numpy: bool = False) -> tuple[list[int], int]:
    """Unpack bits from LSB-first packed uint64 words.

    :param data: Packed bytes
    :param count: Number of bits to extract
    :param use_numpy: Use numpy-accelerated backend if available
    :return: Tuple of (list of bits, bytes consumed)
    """
    if use_numpy:
        try:
            from pygfa.encoding.numpy_backend import unpack_bits_lsb_numpy

            return unpack_bits_lsb_numpy(data, count)
        except ImportError:
            pass

    if count == 0:
        return [], 0

    n = math.ceil(count / 64)
    bytes_consumed = n * 8
    result = [0] * count

    for word_idx in range(n):
        if word_idx * 8 + 8 > len(data):
            break
        val = struct.unpack_from("<Q", data, word_idx * 8)[0]
        start = word_idx * 64
        end = min(start + 64, count)
        for bit_idx in range(start, end):
            result[bit_idx] = (val >> (bit_idx - start)) & 1

    return result, bytes_consumed


def serialize_opt_fields(opt_fields: dict) -> str:
    """Serialize an optional-fields dict into a tab-joined ``TAG:TYPE:VALUE`` string.

    Integer and float values keep their type tag; everything else is written as
    a string (``Z``). An empty dict produces an empty string.
    """
    parts = []
    for tag, value in opt_fields.items():
        if isinstance(value, bool):
            parts.append(f"{tag}:Z:{value}")
        elif isinstance(value, int):
            parts.append(f"{tag}:i:{value}")
        elif isinstance(value, float):
            parts.append(f"{tag}:f:{value}")
        else:
            parts.append(f"{tag}:Z:{value}")
    return "\t".join(parts)


def parse_opt_fields(s: str) -> dict:
    """Parse a tab-joined ``TAG:TYPE:VALUE`` string back into an optional-fields dict.

    Values are coerced to ``int``/``float`` for the ``i``/``f`` type tags and kept
    as strings otherwise. An empty string yields an empty dict.
    """
    result: dict[str, Any] = {}
    if not s:
        return result
    for field in s.split("\t"):
        if not field:
            continue
        try:
            tag, value_type, value = field.split(":", 2)
            if value_type == "i":
                result[tag] = int(value)
            elif value_type == "f":
                result[tag] = float(value)
            else:
                result[tag] = value
        except ValueError as e:
            raise ValueError(f"Malformed opt fields payload: {field!r}") from e
    return result
