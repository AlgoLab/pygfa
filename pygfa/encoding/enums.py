"""Encoding enums for type-safe encoding selection.

This module provides IntEnum classes for all encoding methods supported by pygfa.
"""

from __future__ import annotations

from enum import IntEnum


class IntegerEncoding(IntEnum):
    """Integer list encoding strategies.

    These encodings are used for compressing lists of integers.
    The high byte (0x??00) of a compression code represents the integer encoding.
    """

    IDENTITY = 0x00
    VARINT = 0x01
    FIXED16 = 0x02
    DELTA = 0x03
    ELIAS_GAMMA = 0x04
    ELIAS_OMEGA = 0x05
    GOLOMB = 0x06
    RICE = 0x07
    STREAMVBYTE = 0x08
    VBYTE = 0x09
    FIXED32 = 0x0A
    FIXED64 = 0x0B
    PFOR_DELTA = 0x0C
    SIMPLE_8B = 0x0D
    GROUP_VARINT = 0x0E
    BIT_PACKING = 0x0F
    FIBONACCI = 0x10
    EXP_GOLOMB = 0x11
    BYTE_PACKED = 0x12
    MASKED_VBYTE = 0x13


class StringEncoding(IntEnum):
    """String encoding strategies.

    These encodings are used for compressing strings.
    The low byte (0x00??) of a compression code represents the string encoding.
    """

    IDENTITY = 0x00
    ZSTD = 0x01
    GZIP = 0x02
    LZMA = 0x03
    HUFFMAN = 0x04
    TWO_BIT_DNA = 0x05
    ARITHMETIC = 0x06
    BWT_HUFFMAN = 0x07
    RLE = 0x08
    CIGAR = 0x09
    DICTIONARY = 0x0A
    ZSTD_DICT = 0x0B
    LZ4 = 0x0C
    BROTLI = 0x0D
    PPM = 0x0E


class WalkDecomposition(IntEnum):
    """Walk decomposition strategies.

    These strategies determine how walk data is decomposed for compression.
    """

    IDENTITY = 0x00
    ORIENTATION_STRID = 0x01
    ORIENTATION_NUMID = 0x02


class CigarDecomposition(IntEnum):
    """CIGAR string decomposition strategies.

    These strategies determine how CIGAR strings are decomposed for compression.
    """

    IDENTITY = 0x00
    NUM_OPERATIONS = 0x01
    STRING = 0x02


class SpecialEncoding(IntEnum):
    """Special encoding strategies.

    These encodings have special meanings or behaviors.
    """

    HEURISTIC = 0xFF  # Auto-select best encoding based on data characteristics


def make_compression_code(int_encoding: IntegerEncoding, str_encoding: StringEncoding) -> int:
    """Create a 2-byte compression code from integer and string encodings.

    Args:
        int_encoding: Integer encoding strategy
        str_encoding: String encoding strategy

    Returns:
        2-byte compression code (high byte = integer, low byte = string)

    Example:
        >>> make_compression_code(IntegerEncoding.VARINT, StringEncoding.ZSTD)
        0x0101
    """
    return (int_encoding.value << 8) | str_encoding.value


def split_compression_code(code: int) -> tuple[IntegerEncoding, StringEncoding]:
    """Split a 2-byte compression code into integer and string encodings.

    Args:
        code: 2-byte compression code

    Returns:
        Tuple of (integer_encoding, string_encoding)

    Example:
        >>> split_compression_code(0x0101)
        (IntegerEncoding.VARINT, StringEncoding.ZSTD)
    """
    int_code = (code >> 8) & 0xFF
    str_code = code & 0xFF
    return IntegerEncoding(int_code), StringEncoding(str_code)


__all__ = [
    "IntegerEncoding",
    "StringEncoding",
    "WalkDecomposition",
    "CigarDecomposition",
    "SpecialEncoding",
    "make_compression_code",
    "split_compression_code",
]
