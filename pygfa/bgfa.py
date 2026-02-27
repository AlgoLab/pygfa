"""
Binary GFA (BGFA) serialization module.

This module provides functionality to convert GFA graphs to a binary format
for efficient storage and compression.

Functions:
    to_bgfa: Convert a GFA graph to BGFA binary format.
"""

from __future__ import annotations

import gzip
import io
import logging
import lzma
import math
import os
import struct
import tempfile
from itertools import islice

from pygfa.utils.file_opener import open_gfa_file
from pygfa.utils.output_manager import OutputManager

from pygfa.encoding import (
    compress_integer_list_delta,
    compress_integer_list_elias_gamma,
    compress_integer_list_elias_omega,
    compress_integer_list_fixed,
    compress_integer_list_golomb,
    compress_integer_list_none,
    compress_integer_list_rice,
    compress_integer_list_streamvbyte,
    compress_integer_list_varint,
    compress_integer_list_vbyte,
    compress_string_arithmetic,
    compress_string_bwt_huffman,
    compress_string_gzip,
    compress_string_list,
    compress_string_lzma,
    compress_string_none,
    compress_string_zstd,
    compress_string_zstd_dict,
)
from pygfa.encoding import (
    decompress_string_arithmetic,
    decompress_string_bwt_huffman,
)
from pygfa.encoding.dna_encoding import (
    compress_string_2bit_dna,
    decompress_string_2bit_dna,
)
from pygfa.encoding.rle_encoding import (
    compress_string_rle,
    decompress_string_rle,
)
from pygfa.encoding.cigar_encoding import (
    compress_string_cigar,
    decompress_string_cigar,
)
from pygfa.encoding.dictionary_encoding import (
    compress_string_dictionary,
    decompress_string_dictionary,
)
from pygfa.encoding.string_encoding import _build_codes, _build_huffman_tree
from pygfa.gfa import GFA
from pygfa.graph_element import edge as ge
from pygfa.graph_element import node

__all__ = [
    "INTEGER_ENCODING_DELTA",
    "INTEGER_ENCODING_ELIAS_GAMMA",
    "INTEGER_ENCODING_ELIAS_OMEGA",
    "INTEGER_ENCODING_FIXED16",
    "INTEGER_ENCODING_FIXED32",
    "INTEGER_ENCODING_FIXED64",
    "INTEGER_ENCODING_GOLOMB",
    "INTEGER_ENCODING_IDENTITY",
    "INTEGER_ENCODING_RICE",
    "INTEGER_ENCODING_STREAMVBYTE",
    "INTEGER_ENCODING_VARINT",
    "INTEGER_ENCODING_VBYTE",
    "STRING_ENCODING_ARITHMETIC",
    "STRING_ENCODING_BWT_HUFFMAN",
    "STRING_ENCODING_GZIP",
    "STRING_ENCODING_HUFFMAN",
    "STRING_ENCODING_IDENTITY",
    "STRING_ENCODING_LZMA",
    "STRING_ENCODING_ZSTD",
    "STRING_ENCODING_ZSTD_DICT",
    "WALK_DECOMP_IDENTITY",
    "WALK_DECOMP_ORIENTATION_NUMID",
    "WALK_DECOMP_ORIENTATION_STRID",
    "SECTION_ID_SEGMENT_NAMES",
    "SECTION_ID_SEGMENTS",
    "SECTION_ID_LINKS",
    "SECTION_ID_PATHS",
    "SECTION_ID_WALKS",
    "BGFAWriter",
    "ReaderBGFA",
    "make_compression_code",
    "read_bgfa",
    "to_bgfa",
]


# Section IDs for block types (uint8)
SECTION_ID_SEGMENT_NAMES = 1
SECTION_ID_SEGMENTS = 2
SECTION_ID_LINKS = 3
SECTION_ID_PATHS = 4
SECTION_ID_WALKS = 5


# =============================================================================
# Decompression functions for reading BGFA files
# =============================================================================


def decompress_string_identity(data: bytes, lengths: list[int]) -> list[bytes]:
    """Extract strings from concatenated payload using lengths.

    :param data: Concatenated string data (uncompressed)
    :param lengths: List of string lengths
    :return: List of extracted byte strings
    """
    result = []
    pos = 0
    for length in lengths:
        if pos + length > len(data):
            raise ValueError(f"Data too short: need {pos + length} bytes, have {len(data)}")
        result.append(data[pos : pos + length])
        pos += length
    return result


def decompress_string_zstd(data: bytes, lengths: list[int]) -> list[bytes]:
    """Decompress zstd-compressed data and extract strings.

    :param data: Zstd-compressed concatenated string data
    :param lengths: List of string lengths
    :return: List of extracted byte strings
    """
    import compression.zstd as z

    decompressed = z.decompress(data)
    return decompress_string_identity(decompressed, lengths)


def decompress_string_zstd_dict(data: bytes, lengths: list[int]) -> list[bytes]:
    """Decompress zstd-dict-compressed data and extract strings.

    :param data: Zstd-dict-compressed concatenated string data
    :param lengths: List of string lengths
    :return: List of extracted byte strings
    """
    from pygfa.encoding.string_encoding import decompress_string_zstd_dict as dec

    return dec(data, lengths)


def decompress_string_gzip(data: bytes, lengths: list[int]) -> list[bytes]:
    """Decompress gzip-compressed data and extract strings.

    :param data: Gzip-compressed concatenated string data
    :param lengths: List of string lengths
    :return: List of extracted byte strings
    """
    decompressed = gzip.decompress(data)
    return decompress_string_identity(decompressed, lengths)


def decompress_string_lzma(data: bytes, lengths: list[int]) -> list[bytes]:
    """Decompress lzma-compressed data and extract strings.

    :param data: Lzma-compressed concatenated string data
    :param lengths: List of string lengths
    :return: List of extracted byte strings
    """
    decompressed = lzma.decompress(data)
    return decompress_string_identity(decompressed, lengths)


def decompress_string_huffman(data: bytes, lengths: list[int]) -> list[bytes]:
    """Decompress Huffman-encoded string list.

    The format is:
    - uint32: total uncompressed data length
    - uint32: codebook length
    - codebook bytes (encoded with integer list encoding)
    - compressed bitstream bytes

    :param data: Huffman-compressed data
    :param lengths: List of string lengths
    :return: List of extracted byte strings
    """
    pos = 0

    # Read total uncompressed data length
    total_len = struct.unpack_from("<I", data, pos)[0]
    pos += 4

    # Read codebook length
    codebook_len = struct.unpack_from("<I", data, pos)[0]
    pos += 4

    # Parse codebook (encoded as integer list)
    codebook_data = data[pos : pos + codebook_len]
    pos += codebook_len

    # Decode codebook entries using varint
    codebook_entries, _ = decode_integer_list_varint(codebook_data, -1)

    # Build decoding tree from codebook
    # Codebook format: [code_len, code_bits..., code_len, code_bits..., ...]
    # Characters are in sorted order (0-255)
    decode_table: dict[tuple[int, ...], int] = {}
    entry_idx = 0
    char_val = 0
    while entry_idx < len(codebook_entries):
        code_len = codebook_entries[entry_idx]
        entry_idx += 1
        if code_len > 0 and entry_idx + code_len <= len(codebook_entries):
            code_bits = tuple(codebook_entries[entry_idx : entry_idx + code_len])
            decode_table[code_bits] = char_val
            entry_idx += code_len
        char_val += 1

    # Read compressed bitstream (rest of data)
    bitstream = data[pos:]

    # Decode bitstream
    decoded_data = bytearray()
    bit_pos = 0
    current_bits: list[int] = []

    while len(decoded_data) < total_len and bit_pos < len(bitstream) * 8:
        byte_idx = bit_pos // 8
        bit_idx = 7 - (bit_pos % 8)
        bit = (bitstream[byte_idx] >> bit_idx) & 1
        current_bits.append(bit)
        bit_pos += 1

        code = tuple(current_bits)
        if code in decode_table:
            decoded_data.append(decode_table[code])
            current_bits = []

    # Split decoded data into strings using provided lengths
    return decompress_string_identity(bytes(decoded_data), lengths)


def decode_integer_list_identity(data: bytes, count: int) -> tuple[list[int], int]:
    """Decode identity-encoded integer list (comma-separated ASCII).

    :param data: Encoded data
    :param count: Expected number of integers (-1 for all available)
    :return: Tuple of (list of integers, bytes consumed)
    """
    # Find the extent of comma-separated integers
    result = []
    pos = 0
    current = bytearray()

    while pos < len(data):
        byte = data[pos]
        if byte == ord(","):
            if current:
                result.append(int(current.decode("ascii")))
                current = bytearray()
            pos += 1
            if count > 0 and len(result) >= count:
                break
        elif byte >= ord("0") and byte <= ord("9"):
            current.append(byte)
            pos += 1
        else:
            break

    if current:
        result.append(int(current.decode("ascii")))

    return result, pos


def decode_integer_list_varint(data: bytes, count: int) -> tuple[list[int], int]:
    """Decode varint-encoded integer list.

    :param data: Encoded data
    :param count: Expected number of integers (-1 for all available)
    :return: Tuple of (list of integers, bytes consumed)
    """
    result = []
    pos = 0
    while pos < len(data) and (count < 0 or len(result) < count):
        value = 0
        shift = 0
        while pos < len(data):
            byte = data[pos]
            pos += 1
            value |= (byte & 0x7F) << shift
            shift += 7
            if (byte & 0x80) == 0:
                break
        result.append(value)
    return result, pos


def decode_integer_list_fixed16(data: bytes, count: int) -> tuple[list[int], int]:
    """Decode fixed 16-bit integer list.

    :param data: Encoded data
    :param count: Expected number of integers (-1 for all available)
    :return: Tuple of (list of integers, bytes consumed)
    """
    result = []
    pos = 0
    max_count = len(data) // 2 if count < 0 else count
    for _ in range(max_count):
        if pos + 2 > len(data):
            break
        value = struct.unpack_from("<H", data, pos)[0]
        pos += 2
        result.append(value)
    return result, pos


def decode_integer_list_fixed32(data: bytes, count: int) -> tuple[list[int], int]:
    """Decode fixed 32-bit integer list.

    :param data: Encoded data
    :param count: Expected number of integers (-1 for all available)
    :return: Tuple of (list of integers, bytes consumed)
    """
    result = []
    pos = 0
    max_count = len(data) // 4 if count < 0 else count
    for _ in range(max_count):
        if pos + 4 > len(data):
            break
        value = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        result.append(value)
    return result, pos


def decode_integer_list_fixed64(data: bytes, count: int) -> tuple[list[int], int]:
    """Decode fixed 64-bit integer list.

    :param data: Encoded data
    :param count: Expected number of integers (-1 for all available)
    :return: Tuple of (list of integers, bytes consumed)
    """
    result = []
    pos = 0
    max_count = len(data) // 8 if count < 0 else count
    for _ in range(max_count):
        if pos + 8 > len(data):
            break
        value = struct.unpack_from("<Q", data, pos)[0]
        pos += 8
        result.append(value)
    return result, pos


def decode_integer_list_delta(data: bytes, count: int) -> tuple[list[int], int]:
    """Decode delta-encoded integer list (deltas stored as varint).

    :param data: Encoded data
    :param count: Expected number of integers (-1 for all available)
    :return: Tuple of (list of integers, bytes consumed)
    """
    deltas, consumed = decode_integer_list_varint(data, count)
    if not deltas:
        return [], consumed

    # Reconstruct original values from deltas
    result = [deltas[0]]
    for i in range(1, len(deltas)):
        result.append(result[-1] + deltas[i])

    return result, consumed


def decode_integer_list_elias_gamma(data: bytes, count: int) -> tuple[list[int], int]:
    """Decode Elias gamma-encoded integer list.

    :param data: Encoded data
    :param count: Expected number of integers (-1 for all available)
    :return: Tuple of (list of integers, bytes consumed)
    """
    result = []
    pos = 0

    while pos < len(data) and (count < 0 or len(result) < count):
        # Count leading 0x80 bytes (unary encoding of length-1)
        length = 1
        while pos < len(data) and data[pos] == 0x80:
            length += 1
            pos += 1

        if pos >= len(data):
            break

        # Read the actual length value
        actual_length = data[pos]
        pos += 1
        length = actual_length + 1

        # Read the value bytes
        num_bytes = (length + 7) // 8
        if pos + num_bytes > len(data):
            break

        value = int.from_bytes(data[pos : pos + num_bytes], byteorder="big")
        pos += num_bytes

        # Elias gamma encodes n+1, so subtract 1
        result.append(value - 1)

    return result, pos


def decode_integer_list_elias_omega(data: bytes, count: int) -> tuple[list[int], int]:
    """Decode Elias omega-encoded integer list.

    :param data: Encoded data
    :param count: Expected number of integers (-1 for all available)
    :return: Tuple of (list of integers, bytes consumed)
    """
    result = []
    pos = 0

    while pos < len(data) and (count < 0 or len(result) < count):
        if data[pos] == 0x01:
            # Special case for 0
            result.append(0)
            pos += 1
            continue

        # Count leading 0x80 bytes
        bit_count = 0
        while pos < len(data) and data[pos] == 0x80:
            bit_count += 1
            pos += 1

        if pos >= len(data):
            break

        # Read the remaining bits
        remaining = data[pos : pos + bit_count + 1]
        pos += len(remaining)

        # Reconstruct the value
        value = 0
        for b in remaining:
            value = (value << 1) | (b & 1)

        result.append(value)

    return result, pos


def decode_integer_list_golomb(data: bytes, count: int) -> tuple[list[int], int]:
    """Decode Golomb-encoded integer list.

    :param data: Encoded data
    :param count: Expected number of integers (-1 for all available)
    :return: Tuple of (list of integers, bytes consumed)
    """
    if len(data) < 1:
        return [], 0

    # First byte is the divisor b
    b = data[0]
    if b == 0:
        b = 1
    pos = 1
    result = []

    while pos < len(data) and (count < 0 or len(result) < count):
        # Count leading 0x80 bytes (quotient in unary)
        quotient = 0
        while pos < len(data) and data[pos] == 0x80:
            quotient += 1
            pos += 1

        if pos >= len(data):
            break

        # Read remainder (lower bits)
        byte_val = data[pos]
        pos += 1
        remainder = byte_val & 0x7F

        value = quotient * b + remainder
        result.append(value)

    return result, pos


def decode_integer_list_rice(data: bytes, count: int) -> tuple[list[int], int]:
    """Decode Rice-encoded integer list.

    :param data: Encoded data
    :param count: Expected number of integers (-1 for all available)
    :return: Tuple of (list of integers, bytes consumed)
    """
    if len(data) < 1:
        return [], 0

    # First byte is k (the Rice parameter)
    k = data[0]
    b = 1 << k
    pos = 1
    result = []

    while pos < len(data) and (count < 0 or len(result) < count):
        # Count leading 0x80 bytes (quotient in unary)
        quotient = 0
        while pos < len(data) and data[pos] == 0x80:
            quotient += 1
            pos += 1

        if pos >= len(data):
            break

        # Read remainder
        byte_val = data[pos]
        pos += 1
        remainder = byte_val & 0x7F

        value = quotient * b + remainder
        result.append(value)

    return result, pos


def decode_integer_list_streamvbyte(data: bytes, count: int) -> tuple[list[int], int]:
    """Decode StreamVByte-encoded integer list.

    :param data: Encoded data
    :param count: Expected number of integers (-1 for all available, but we use header)
    :return: Tuple of (list of integers, bytes consumed)
    """
    if len(data) < 4:
        return [], 0

    # First 4 bytes: count of integers
    n = struct.unpack_from("<I", data, 0)[0]
    if count >= 0:
        n = min(n, count)

    ctrl_start = 4
    data_start = 4 + ((n + 3) // 4) * 4

    result = []
    ctrl_idx = ctrl_start
    data_idx = data_start

    for i in range(n):
        if ctrl_idx >= len(data) or data_idx >= len(data):
            break

        ctrl = data[ctrl_idx]
        if ctrl == 0:
            # 1 byte
            if data_idx < len(data):
                result.append(data[data_idx])
                data_idx += 1
        elif ctrl == 1:
            # 2 bytes
            if data_idx + 2 <= len(data):
                result.append(data[data_idx] | (data[data_idx + 1] << 8))
                data_idx += 2
        elif ctrl == 2:
            # 3 bytes
            if data_idx + 3 <= len(data):
                result.append(data[data_idx] | (data[data_idx + 1] << 8) | (data[data_idx + 2] << 16))
                data_idx += 3
        # 4 bytes
        elif data_idx + 4 <= len(data):
            result.append(struct.unpack_from("<I", data, data_idx)[0])
            data_idx += 4

        if (i & 3) == 3:
            ctrl_idx += 4

    return result, data_idx


def decode_integer_list_vbyte(data: bytes, count: int) -> tuple[list[int], int]:
    """Decode VByte-encoded integer list.

    :param data: Encoded data
    :param count: Expected number of integers (-1 for all available)
    :return: Tuple of (list of integers, bytes consumed)
    """
    result = []
    pos = 0

    while pos < len(data) and (count < 0 or len(result) < count):
        byte = data[pos]
        ctrl = byte & 0xC0

        if ctrl == 0x00:
            # 4-byte value (but this shouldn't happen as first byte)
            # Actually this means end of vbyte or different encoding
            if byte < 0x40:
                result.append(byte)
                pos += 1
            else:
                break
        elif ctrl == 0x40:
            # 1-byte value (6 bits)
            result.append(byte & 0x3F)
            pos += 1
        elif ctrl == 0x80:
            # 2-byte value
            if pos + 2 > len(data):
                break
            val = (byte & 0x3F) | (data[pos + 1] << 6)
            result.append(val)
            pos += 2
        elif ctrl == 0xC0:
            # 3 or 4 byte value
            if pos + 2 > len(data):
                break
            next_ctrl = data[pos + 1] & 0xC0
            if next_ctrl == 0xC0:
                # 4-byte value
                if pos + 4 > len(data):
                    break
                val = (
                    (byte & 0x3F)
                    | ((data[pos + 1] & 0x3F) << 6)
                    | ((data[pos + 2] & 0x3F) << 14)
                    | (data[pos + 3] << 22)
                )
                result.append(val)
                pos += 4
            else:
                # 3-byte value
                if pos + 3 > len(data):
                    break
                val = (byte & 0x3F) | ((data[pos + 1] & 0x3F) << 6) | (data[pos + 2] << 14)
                result.append(val)
                pos += 3

    return result, pos


# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# Encoding strategy tables (from BGFA spec)
# =============================================================================
# The compression code is a uint16 where:
#   - High byte (bits 8-15): integer list encoding strategy
#   - Low byte (bits 0-7): string encoding strategy
#
# Example: 0x0102 means varint (0x01) for integers, gzip (0x02) for strings

# Integer list encoding strategies (high byte)
INTEGER_ENCODING_IDENTITY = 0x00
INTEGER_ENCODING_VARINT = 0x01
INTEGER_ENCODING_FIXED16 = 0x02
INTEGER_ENCODING_DELTA = 0x03
INTEGER_ENCODING_ELIAS_GAMMA = 0x04
INTEGER_ENCODING_ELIAS_OMEGA = 0x05
INTEGER_ENCODING_GOLOMB = 0x06
INTEGER_ENCODING_RICE = 0x07
INTEGER_ENCODING_STREAMVBYTE = 0x08
INTEGER_ENCODING_VBYTE = 0x09
INTEGER_ENCODING_FIXED32 = 0x0A
INTEGER_ENCODING_FIXED64 = 0x0B

# String encoding strategies (low byte)
STRING_ENCODING_IDENTITY = 0x00
STRING_ENCODING_ZSTD = 0x01
STRING_ENCODING_GZIP = 0x02
STRING_ENCODING_LZMA = 0x03
STRING_ENCODING_HUFFMAN = 0x04
STRING_ENCODING_2BIT_DNA = 0x05
STRING_ENCODING_ARITHMETIC = 0x06
STRING_ENCODING_BWT_HUFFMAN = 0x07
STRING_ENCODING_RLE = 0x08
STRING_ENCODING_CIGAR = 0x09
STRING_ENCODING_DICTIONARY = 0x0A
STRING_ENCODING_ZSTD_DICT = 0x0B

# Mapping from integer encoding codes to compression functions
INTEGER_ENCODERS = {
    INTEGER_ENCODING_IDENTITY: compress_integer_list_none,
    INTEGER_ENCODING_VARINT: compress_integer_list_varint,
    INTEGER_ENCODING_FIXED16: lambda x: compress_integer_list_fixed(x, size=16),
    INTEGER_ENCODING_DELTA: compress_integer_list_delta,
    INTEGER_ENCODING_ELIAS_GAMMA: compress_integer_list_elias_gamma,
    INTEGER_ENCODING_ELIAS_OMEGA: compress_integer_list_elias_omega,
    INTEGER_ENCODING_GOLOMB: compress_integer_list_golomb,
    INTEGER_ENCODING_RICE: compress_integer_list_rice,
    INTEGER_ENCODING_STREAMVBYTE: compress_integer_list_streamvbyte,
    INTEGER_ENCODING_VBYTE: compress_integer_list_vbyte,
    INTEGER_ENCODING_FIXED32: lambda x: compress_integer_list_fixed(x, size=32),
    INTEGER_ENCODING_FIXED64: lambda x: compress_integer_list_fixed(x, size=64),
}

# Mapping from string encoding codes to compression functions
STRING_ENCODERS = {
    STRING_ENCODING_IDENTITY: compress_string_none,
    STRING_ENCODING_ZSTD: compress_string_zstd,
    STRING_ENCODING_GZIP: compress_string_gzip,
    STRING_ENCODING_LZMA: compress_string_lzma,
    STRING_ENCODING_HUFFMAN: None,  # Huffman requires special handling (list-based)
    STRING_ENCODING_2BIT_DNA: compress_string_2bit_dna,
    STRING_ENCODING_ARITHMETIC: compress_string_arithmetic,
    STRING_ENCODING_BWT_HUFFMAN: compress_string_bwt_huffman,
    STRING_ENCODING_RLE: compress_string_rle,
    STRING_ENCODING_CIGAR: compress_string_cigar,
    STRING_ENCODING_DICTIONARY: compress_string_dictionary,
    STRING_ENCODING_ZSTD_DICT: compress_string_zstd_dict,
}

# Mapping from integer encoding codes to decompression functions
INTEGER_DECODERS = {
    INTEGER_ENCODING_IDENTITY: decode_integer_list_identity,
    INTEGER_ENCODING_VARINT: decode_integer_list_varint,
    INTEGER_ENCODING_FIXED16: decode_integer_list_fixed16,
    INTEGER_ENCODING_DELTA: decode_integer_list_delta,
    INTEGER_ENCODING_ELIAS_GAMMA: decode_integer_list_elias_gamma,
    INTEGER_ENCODING_ELIAS_OMEGA: decode_integer_list_elias_omega,
    INTEGER_ENCODING_GOLOMB: decode_integer_list_golomb,
    INTEGER_ENCODING_RICE: decode_integer_list_rice,
    INTEGER_ENCODING_STREAMVBYTE: decode_integer_list_streamvbyte,
    INTEGER_ENCODING_VBYTE: decode_integer_list_vbyte,
    INTEGER_ENCODING_FIXED32: decode_integer_list_fixed32,
    INTEGER_ENCODING_FIXED64: decode_integer_list_fixed64,
}

# Mapping from string encoding codes to decompression functions
STRING_DECODERS = {
    STRING_ENCODING_IDENTITY: decompress_string_identity,
    STRING_ENCODING_ZSTD: decompress_string_zstd,
    STRING_ENCODING_GZIP: decompress_string_gzip,
    STRING_ENCODING_LZMA: decompress_string_lzma,
    STRING_ENCODING_HUFFMAN: decompress_string_huffman,
    STRING_ENCODING_2BIT_DNA: decompress_string_2bit_dna,
    STRING_ENCODING_ARITHMETIC: decompress_string_arithmetic,
    STRING_ENCODING_BWT_HUFFMAN: decompress_string_bwt_huffman,
    STRING_ENCODING_RLE: decompress_string_rle,
    STRING_ENCODING_CIGAR: decompress_string_cigar,
    STRING_ENCODING_DICTIONARY: decompress_string_dictionary,
    STRING_ENCODING_ZSTD_DICT: decompress_string_zstd_dict,
}


def get_integer_encoder(code: int):
    """Get the integer encoding function for a compression code.

    :param code: The uint16 compression code
    :return: The compression function for integers
    """
    int_code = (code >> 8) & 0xFF
    return INTEGER_ENCODERS.get(int_code, compress_integer_list_none)


def get_string_encoder(code: int):
    """Get the string encoding function for a compression code.

    :param code: The uint16 compression code
    :return: The compression function for strings
    """
    str_code = code & 0xFF
    return STRING_ENCODERS.get(str_code, compress_string_none)


def get_integer_decoder(code: int):
    """Get the integer decoding function for a compression code.

    :param code: The uint16 compression code
    :return: The decompression function for integers
    """
    int_code = (code >> 8) & 0xFF
    return INTEGER_DECODERS.get(int_code, decode_integer_list_identity)


def get_string_decoder(code: int):
    """Get the string decoding function for a compression code.

    :param code: The uint16 compression code
    :return: The decompression function for strings
    """
    str_code = code & 0xFF
    return STRING_DECODERS.get(str_code, decompress_string_identity)


def make_compression_code(int_encoding: int, str_encoding: int) -> int:
    """Create a compression code from integer and string encoding strategies.

    :param int_encoding: Integer encoding strategy (0x00-0x0B)
    :param str_encoding: String encoding strategy (0x00-0x04)
    :return: Combined uint16 compression code
    """
    return ((int_encoding & 0xFF) << 8) | (str_encoding & 0xFF)


def _compress_huffman_payload(concatenated: str) -> bytes:
    """Produce Huffman-compressed payload matching the format expected by decompress_string_huffman.

    Format: uint32(total_len) + uint32(codebook_len) + codebook_bytes + bitstream_bytes

    The codebook is encoded as varint integers, with entries ordered by character value.
    Each entry is: code_len followed by code_len bits.

    :param concatenated: The concatenated string data to compress
    :return: Huffman-compressed bytes
    """
    data = concatenated.encode("ascii")
    if not data:
        return struct.pack("<I", 0) + struct.pack("<I", 0)

    # Build frequency table
    freq: dict[int, int] = {}
    for byte in data:
        freq[byte] = freq.get(byte, 0) + 1

    # Build Huffman tree and codes
    if len(freq) == 1:
        single_char = next(iter(freq))
        codes = {single_char: [0]}
    else:
        tree = _build_huffman_tree(freq)
        codes = _build_codes(tree)

    # Build bitstream
    bitstream_bits: list[int] = []
    for byte in data:
        bitstream_bits.extend(codes[byte])

    # Pad to byte boundary
    while len(bitstream_bits) % 8 != 0:
        bitstream_bits.append(0)

    # Convert bits to bytes
    bitstream_bytes = bytearray()
    for i in range(0, len(bitstream_bits), 8):
        byte_val = 0
        for j in range(8):
            byte_val = (byte_val << 1) | bitstream_bits[i + j]
        bitstream_bytes.append(byte_val & 0xFF)

    # Build codebook: entries ordered by char value 0..max_char
    # Each entry: code_len, code_bits...
    codebook_entries: list[int] = []
    if codes:
        max_char = max(codes.keys())
        for char_val in range(max_char + 1):
            if char_val in codes:
                code = codes[char_val]
                codebook_entries.append(len(code))
                codebook_entries.extend(code)
            else:
                codebook_entries.append(0)
    codebook_bytes = compress_integer_list_varint(codebook_entries)

    # Assemble: total_len + codebook_len + codebook + bitstream
    result = (
        struct.pack("<I", len(data)) + struct.pack("<I", len(codebook_bytes)) + codebook_bytes + bytes(bitstream_bytes)
    )
    return result


def _compress_string_for_bgfa(concatenated: str, str_encoding: int) -> bytes:
    """Compress a concatenated string using the specified string encoding strategy.

    :param concatenated: The concatenated string data to compress
    :param str_encoding: String encoding strategy code (low byte of compression code)
    :return: Compressed bytes
    """
    if str_encoding == STRING_ENCODING_IDENTITY:
        return concatenated.encode("ascii")
    elif str_encoding == STRING_ENCODING_HUFFMAN:
        return _compress_huffman_payload(concatenated)
    else:
        encoder = STRING_ENCODERS.get(str_encoding)
        if encoder is not None:
            return encoder(concatenated)
        return concatenated.encode("ascii")


# Walks/paths decomposition strategy constants (high byte of compression_paths/compression_walks)
WALK_DECOMP_IDENTITY = 0x00
WALK_DECOMP_ORIENTATION_STRID = 0x01
WALK_DECOMP_ORIENTATION_NUMID = 0x02


def _pack_orientation_bits(orientations: list[int]) -> bytes:
    """Pack a list of 0/1 orientation values into bytes (MSB first).

    :param orientations: List of orientation values (0 or 1)
    :return: Packed bytes
    """
    result = bytearray()
    for i in range(0, len(orientations), 8):
        byte_val = 0
        for j in range(8):
            if i + j < len(orientations):
                byte_val = (byte_val << 1) | (orientations[i + j] & 1)
            else:
                byte_val <<= 1
        result.append(byte_val & 0xFF)
    return bytes(result)


def _pack_orientation_bits_uint64(orientations: list[int]) -> bytes:
    """Pack 0/1 orientation values into little-endian uint64 values (LSB-first).

    Per the BGFA spec, a ``bits`` field is a list of uint64.
    Bit 0 (LSB) of the first uint64 holds the first orientation, bit 1 the
    second, etc.  For *N* orientations we emit ``ceil(N / 64)`` uint64 values.

    :param orientations: List of orientation values (0 = "+", 1 = "-")
    :return: Packed bytes (multiple of 8)
    """
    import math

    n = len(orientations)
    num_uint64 = max(1, math.ceil(n / 64)) if n > 0 else 0
    result = bytearray()
    for word_idx in range(num_uint64):
        val = 0
        for bit_idx in range(64):
            orn_idx = word_idx * 64 + bit_idx
            if orn_idx < n and orientations[orn_idx]:
                val |= 1 << bit_idx
        result.extend(struct.pack("<Q", val))
    return bytes(result)


def _unpack_orientation_bits_uint64(data: bytes, count: int) -> tuple[list[int], int]:
    """Unpack *count* orientation bits from little-endian uint64 values.

    :param data: Raw bytes containing the packed uint64 values
    :param count: Number of orientation bits to extract
    :return: (list of 0/1 values, number of bytes consumed)
    """
    import math

    num_uint64 = max(1, math.ceil(count / 64)) if count > 0 else 0
    consumed = num_uint64 * 8
    orientations: list[int] = []
    for word_idx in range(num_uint64):
        val = struct.unpack_from("<Q", data, word_idx * 8)[0]
        for bit_idx in range(64):
            if len(orientations) >= count:
                break
            orientations.append((val >> bit_idx) & 1)
    return orientations, consumed


def _encode_walks_payload(
    walk_segments_list: list[list],
    segment_map: dict,
    compression_walks: int,
) -> bytes:
    """Encode walks/paths segment lists according to the decomposition strategy.

    The compression_walks uint16 encodes:
    - High byte: decomposition strategy (0x00=identity, 0x01=orientation+strid, 0x02=orientation+numid)
    - Low byte: sub-encoding (for strid: string encoding 0x00-0x04;
      for numid: integer encoding 0x00-0x0B)

    :param walk_segments_list: List of lists of segment references (strings like ">seg1" or "<seg2")
    :param segment_map: Mapping from segment name to numeric ID
    :param compression_walks: uint16 compression code
    :return: Encoded bytes
    """
    decomp_mode = (compression_walks >> 8) & 0xFF
    sub_encoding = compression_walks & 0xFF

    # Collect all orientations and segment identifiers, plus per-walk counts
    all_orientations = []
    all_seg_names = []
    all_seg_ids = []
    walk_counts = []

    for segments in walk_segments_list:
        walk_counts.append(len(segments))
        for seg in segments:
            if isinstance(seg, str):
                if seg.startswith(">") or seg.startswith("<"):
                    orientation = 0 if seg.startswith(">") else 1
                    seg_name = seg[1:]
                elif seg.endswith("+") or seg.endswith("-"):
                    orientation = 0 if seg.endswith("+") else 1
                    seg_name = seg[:-1]
                else:
                    seg_name = seg
                    orientation = 0
                seg_id = segment_map.get(seg_name, 0)
            else:
                seg_id = seg
                seg_name = str(seg)
                orientation = 0
            all_orientations.append(orientation)
            all_seg_names.append(seg_name)
            all_seg_ids.append(seg_id)

    if decomp_mode == WALK_DECOMP_IDENTITY:
        # Identity: per-walk count (uint64) + orientation byte + segment_id (uint64)
        parts = []
        idx = 0
        for count in walk_counts:
            parts.append(struct.pack("<Q", count))
            for _ in range(count):
                parts.append(struct.pack("<BQ", all_orientations[idx], all_seg_ids[idx]))
                idx += 1
        return b"".join(parts)

    elif decomp_mode == WALK_DECOMP_ORIENTATION_STRID:
        # orientation+strid: per-walk counts + packed orientation bits + segment IDs as string list
        # Per-walk counts encoded as varint
        counts_encoded = compress_integer_list_varint(walk_counts)
        orientation_bits = _pack_orientation_bits(all_orientations)
        # Segment IDs as string list: encode lengths + compress concatenated names
        str_encoding = sub_encoding
        seg_name_lengths = [len(n.encode("ascii")) for n in all_seg_names]
        int_encoder = compress_integer_list_varint  # lengths always as varint
        encoded_lengths = int_encoder(seg_name_lengths)
        compressed_names = _compress_string_for_bgfa("".join(all_seg_names), str_encoding)
        return (
            counts_encoded
            + struct.pack("<I", len(orientation_bits))
            + orientation_bits
            + encoded_lengths
            + compressed_names
        )

    elif decomp_mode == WALK_DECOMP_ORIENTATION_NUMID:
        # orientation+numid: per-walk counts + packed orientation bits + segment IDs as integer list
        counts_encoded = compress_integer_list_varint(walk_counts)
        orientation_bits = _pack_orientation_bits(all_orientations)
        # Segment IDs as integer list
        int_encoding = sub_encoding
        int_encoder = INTEGER_ENCODERS.get(int_encoding, compress_integer_list_none)
        encoded_ids = int_encoder(all_seg_ids)
        return counts_encoded + struct.pack("<I", len(orientation_bits)) + orientation_bits + encoded_ids

    else:
        raise ValueError(f"Unknown walks/paths decomposition mode: {decomp_mode:#04x}")


class ReaderBGFA:
    def __init__(self):
        pass

    def read_bgfa(
        self,
        file_path: str,
        verbose: bool = False,
        debug: bool = False,
        logfile: str | None = None,
    ) -> GFA:
        """Read a BGFA file and create the corresponding GFA graph.

        :param file_path: Path to the BGFA file
        :param verbose: If True, log detailed information
        :param debug: If True, log debug information
        :param logfile: Path to log file (if None and verbose=True, uses a temporary file)
        :return: GFA graph object
        """
        # Determine log level based on verbosity
        if debug:
            log_level = logging.DEBUG
        elif verbose:
            log_level = logging.INFO
        else:
            log_level = logging.WARNING

        # Only create log file if we're actually logging something
        if log_level <= logging.INFO:
            if logfile is None:
                # Create a temporary log file in appropriate directory
                try:
                    # Try to use results directory if available
                    output_mgr = OutputManager()
                    temp_log = output_mgr.create_temp_file(".log", output_mgr.get_test_dir("bgfa"))
                    logfile = str(temp_log)
                except Exception:
                    # Fallback to system temp directory
                    temp_log = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log")
                    logfile = temp_log.name
                    temp_log.close()
                print(f"Logging to temporary file: {logfile}")
        # If we're not logging, use a dummy logfile
        elif os.name == "nt":  # Windows
            logfile = "NUL"
        else:  # Unix-like
            logfile = "/dev/null"

        # Clear any existing handlers
        logging.getLogger().handlers.clear()

        # Create formatter
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

        handlers = []

        # Only add file handler if we're actually logging to a file

        if logfile not in {"/dev/null", "NUL"}:
            file_handler = logging.FileHandler(logfile)
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            handlers.append(file_handler)

        # Always add stream handler for console output
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(log_level)
        stream_handler.setFormatter(formatter)
        handlers.append(stream_handler)

        # Configure root logger
        logging.basicConfig(level=log_level, handlers=handlers)

        # Get logger for this module
        logger = logging.getLogger(__name__)

        logger.info(f"Reading BGFA file: {file_path}")
        if debug:
            logger.debug(f"Debug mode enabled, logfile: {logfile}")
        else:
            logger.debug(f"Verbose mode enabled, logfile: {logfile}")

        with open_gfa_file(file_path, "rb") as f:
            bgfa_data = f.read()

        gfa = GFA()

        # Parse header
        header = self._parse_header(bgfa_data)
        # Store header information in the GFA object
        gfa._header_info = header.copy()
        logger.info(f"Header parsed: version={header['version']}")
        logger.debug(f"Full header: {header}")

        # Check minimum file size
        if len(bgfa_data) < header["header_size"]:
            raise ValueError(
                f"BGFA file is too short: {len(bgfa_data)} bytes, expected at least {header['header_size']}"
            )

        # Default block size (used for reference only, section_id determines block type now)
        block_size = 1024

        # Parse blocks in any order using section_id
        # First pass: collect all segment names (needed for segment/links/paths parsing)
        offset = header["header_size"]
        segment_names = []
        segments_data = {}
        links = []
        paths = []
        walks = []

        logger.info("Parsing blocks (any order)")

        while offset < len(bgfa_data):
            # Check if we have enough bytes to read the section_id
            if offset + 1 > len(bgfa_data):
                break

            # Read section_id to determine block type
            section_id = struct.unpack_from("<B", bgfa_data, offset)[0]

            if section_id == SECTION_ID_SEGMENT_NAMES:
                logger.debug(f"Parsing segment names block at offset {offset}")
                segment_names_block, read_bytes = self._parse_segment_names_block(bgfa_data, offset)
                offset += read_bytes
                segment_names.extend(segment_names_block)
                logger.info(f"Parsed segment names: {len(segment_names)} names")

            elif section_id == SECTION_ID_SEGMENTS:
                logger.debug(f"Parsing segments block at offset {offset}")
                segment_block, read_bytes = self._parse_segments_block(bgfa_data, offset)
                offset += read_bytes
                # Merge segment_block into segments_data
                segments_data.update(segment_block)
                logger.info(f"Parsed segments: {len(segment_block)} segments (total: {len(segments_data)})")

            elif section_id == SECTION_ID_LINKS:
                logger.debug(f"Parsing links block at offset {offset}")
                links_block, read_bytes = self._parse_links_block(bgfa_data, segment_names, offset)
                offset += read_bytes
                links.extend(links_block)
                logger.info(f"Parsed links: {len(links_block)} links")

            elif section_id == SECTION_ID_PATHS:
                logger.debug(f"Parsing paths block at offset {offset}")
                paths_block, read_bytes = self._parse_paths_blocks(bgfa_data, header, segment_names, offset)
                offset += read_bytes
                paths.extend(paths_block)
                logger.info(f"Parsed paths: {len(paths_block)} paths")

            elif section_id == SECTION_ID_WALKS:
                logger.debug(f"Parsing walks block at offset {offset}")
                walks_block, read_bytes = self._parse_walks_blocks(bgfa_data, header, segment_names, offset)
                offset += read_bytes
                walks.extend(walks_block)
                logger.info(f"Parsed walks: {len(walks_block)} walks")

            else:
                logger.warning(f"Unknown section_id={section_id} at offset {offset}, skipping")
                # Try to skip this block - read remaining header fields to skip
                # We need to read enough to skip to the next potential section_id
                # For safety, just break to avoid infinite loop
                break

        logger.info(f"Total segment names: {len(segment_names)}")
        logger.info(f"Total segments: {len(segments_data)}")
        logger.info(f"Total links: {len(links)}")
        logger.info(f"Total paths: {len(paths)}")
        logger.info(f"Total walks: {len(walks)}")

        # Add nodes to GFA graph with segment IDs
        for segment_id, segment_data in segments_data.items():
            # Get node name from segment_names list (0-based index)
            if 0 <= segment_id < len(segment_names):
                node_name = segment_names[segment_id]
            else:
                node_name = f"segment_{segment_id}"

            n = node.Node(
                node_name,
                segment_data["sequence"],
                segment_data["length"],
                opt_fields=segment_data.get("opt_fields", {}),
            )
            gfa.add_node(n)
            # The GFA class has a _segment_map attribute
            gfa._segment_map[node_name] = segment_id

        # Add edges to GFA graph
        for link in links:
            gfa.add_edge(
                ge.Edge(
                    None,  # eid
                    link["from_node"],
                    link["from_orn"],
                    link["to_node"],
                    link["to_orn"],
                    (None, None),  # from_positions
                    (None, None),  # to_positions
                    link["alignment"],
                    None,  # distance
                    None,  # variance
                    opt_fields={},
                )
            )

        return gfa

    def _parse_header(self, bgfa_data: bytes) -> dict:
        """Parse the BGFA file header.

        :param bgfa_data: Binary BGFA data
        :return: Dictionary containing header information
        """
        offset = 0

        # Read version (uint16)
        version = struct.unpack_from("<H", bgfa_data, offset)[0]
        offset += 2

        # Skip reserved space (previously block_size + S_len, L_len, P_len, W_len)
        offset += 34

        # Read header text (C string)
        header_text = ""
        while offset < len(bgfa_data) and bgfa_data[offset] != 0:
            header_text += chr(bgfa_data[offset])
            offset += 1
        offset += 1  # Skip null terminator

        return {
            "version": version,
            "header_text": header_text,
            "header_size": offset,
        }

    def _parse_segment_names_block(self, bgfa_data: bytes, offset: int) -> tuple[list[str], int]:
        """Parse segment names from BGFA data.

        Supports all compression methods defined in the BGFA spec:
        - Integer encoding (high byte): identity, varint, fixed16, delta, elias_gamma,
          elias_omega, golomb, rice, streamvbyte, vbyte, fixed32, fixed64
        - String encoding (low byte): identity, zstd, gzip, lzma, huffman

        :param bgfa_data: Binary BGFA data
        :param offset: number of bytes to skip
        :return: (List of segment names, number of bytes read)
        """
        initial_offset = offset

        # Read block header - new order: section_id (uint8), then uint16 fields
        section_id = struct.unpack_from("<B", bgfa_data, offset)[0]
        offset += 1
        if section_id != SECTION_ID_SEGMENT_NAMES:
            raise ValueError(f"Expected section_id={SECTION_ID_SEGMENT_NAMES}, got {section_id}")

        record_num = struct.unpack_from("<H", bgfa_data, offset)[0]
        offset += 2
        compression_names = struct.unpack_from("<H", bgfa_data, offset)[0]
        offset += 2
        compressed_len = struct.unpack_from("<Q", bgfa_data, offset)[0]
        offset += 8
        uncompressed_len = struct.unpack_from("<Q", bgfa_data, offset)[0]
        offset += 8

        # Read payload
        payload = bgfa_data[offset : offset + compressed_len]
        offset += compressed_len

        # Extract encoding strategies from compression code
        int_encoding = (compression_names >> 8) & 0xFF
        str_encoding = compression_names & 0xFF

        logger.debug(
            f"Parsing segment names block: record_num={record_num}, "
            f"compression={compression_names:#06x} (int={int_encoding:#04x}, "
            f"str={str_encoding:#04x}), compressed_len={compressed_len}, "
            f"uncompressed_len={uncompressed_len}"
        )

        # Handle legacy identity encoding (0x0000): null-terminated strings
        if compression_names == 0x0000:
            segment_names = []
            pos = 0
            for _ in range(record_num):
                name_bytes = bytearray()
                while pos < len(payload) and payload[pos] != 0:
                    name_bytes.append(payload[pos])
                    pos += 1
                if pos >= len(payload):
                    raise ValueError("Missing null terminator in segment name")
                pos += 1  # skip null terminator
                segment_names.append(name_bytes.decode("ascii"))

            # Verify length
            if pos != uncompressed_len:
                raise ValueError(f"Segment names length mismatch: expected {uncompressed_len} bytes, got {pos}")
            return segment_names, offset - initial_offset

        # For all other encodings, the payload format is:
        # 1. Encoded lengths of strings (using integer encoding from high byte)
        # 2. Compressed concatenated strings (using string encoding from low byte)

        # Get the appropriate decoders
        int_decoder = get_integer_decoder(compression_names)
        str_decoder = get_string_decoder(compression_names)

        # Decode string lengths from the payload
        lengths, lengths_consumed = int_decoder(payload, record_num)

        if len(lengths) != record_num:
            raise ValueError(f"Length count mismatch: expected {record_num}, got {len(lengths)}")

        # Get the compressed string data (rest of payload after lengths)
        compressed_strings = payload[lengths_consumed:]

        # Decompress and extract strings using unified interface
        string_bytes = str_decoder(compressed_strings, lengths)
        segment_names = [s.decode("ascii") for s in string_bytes]

        logger.debug(f"Decoded {len(segment_names)} segment names")

        return segment_names, offset - initial_offset

    def _parse_segments_block(self, bgfa_data: bytes, start_offset: int) -> tuple[dict, int]:
        """Parse segments from BGFA data.

        Supports all compression methods defined in the BGFA spec:
        - Integer encoding (high byte): identity, varint, fixed16, delta, elias_gamma,
          elias_omega, golomb, rice, streamvbyte, vbyte, fixed32, fixed64
        - String encoding (low byte): identity, zstd, gzip, lzma, huffman

        :param bgfa_data: Binary BGFA data
        :param start_offset: Offset where segments blocks start
        :return: (Dictionary mapping segment IDs to segment data, number of bytes read)
        """
        initial_offset = start_offset
        offset = start_offset
        segments = {}

        # Read block header - section_id (uint8), then uint16 fields
        section_id = struct.unpack_from("<B", bgfa_data, offset)[0]
        offset += 1
        if section_id != SECTION_ID_SEGMENTS:
            raise ValueError(f"Expected section_id={SECTION_ID_SEGMENTS}, got {section_id}")

        record_num = struct.unpack_from("<H", bgfa_data, offset)[0]
        offset += 2
        compression_str = struct.unpack_from("<H", bgfa_data, offset)[0]
        offset += 2
        compressed_len = struct.unpack_from("<Q", bgfa_data, offset)[0]
        offset += 8
        uncompressed_len = struct.unpack_from("<Q", bgfa_data, offset)[0]
        offset += 8

        # Read segment data
        segment_data = bgfa_data[offset : offset + compressed_len]
        offset += compressed_len

        # Extract encoding strategies from compression code
        int_encoding = (compression_str >> 8) & 0xFF
        str_encoding = compression_str & 0xFF

        logger.debug(
            f"Parsing segments block: record_num={record_num}, "
            f"compression={compression_str:#06x} (int={int_encoding:#04x}, "
            f"str={str_encoding:#04x}), compressed_len={compressed_len}, "
            f"uncompressed_len={uncompressed_len}"
        )

        # Handle legacy identity encoding (0x0000): fixed format with null-terminated strings
        if compression_str == 0x0000:
            import json

            pos = 0
            for _ in range(record_num):
                # Read segment ID (uint64)
                segment_id = struct.unpack_from("<Q", segment_data, pos)[0]
                pos += 8
                # Read sequence length (uint64)
                sequence_length = struct.unpack_from("<Q", segment_data, pos)[0]
                pos += 8
                # Read sequence (null-terminated string)
                sequence_bytes = bytearray()
                while pos < len(segment_data) and segment_data[pos] != 0:
                    sequence_bytes.append(segment_data[pos])
                    pos += 1
                pos += 1  # Skip null terminator
                sequence = sequence_bytes.decode("ascii")

                # Read optional fields JSON (null-terminated string) - new addition
                opt_fields_bytes = bytearray()
                while pos < len(segment_data) and segment_data[pos] != 0:
                    opt_fields_bytes.append(segment_data[pos])
                    pos += 1
                pos += 1  # Skip null terminator
                opt_fields_str = opt_fields_bytes.decode("ascii")
                opt_fields = json.loads(opt_fields_str) if opt_fields_str.strip() else {}

                segments[segment_id] = {
                    "sequence": sequence,
                    "length": sequence_length,
                    "opt_fields": opt_fields,
                }

            return segments, offset - initial_offset

        # For all other encodings, the payload format is:
        # 1. Encoded segment IDs (using integer encoding from high byte)
        # 2. Encoded sequence lengths (using integer encoding from high byte)
        # 3. Compressed concatenated sequences (using string encoding from low byte)

        # Get the appropriate decoders
        int_decoder = get_integer_decoder(compression_str)
        str_decoder = get_string_decoder(compression_str)

        # Decode segment IDs from the payload
        segment_ids, ids_consumed = int_decoder(segment_data, record_num)

        if len(segment_ids) != record_num:
            raise ValueError(f"Segment ID count mismatch: expected {record_num}, got {len(segment_ids)}")

        # Decode sequence lengths
        remaining_data = segment_data[ids_consumed:]
        sequence_lengths, lengths_consumed = int_decoder(remaining_data, record_num)

        if len(sequence_lengths) != record_num:
            seq_len_count = len(sequence_lengths)
            raise ValueError(f"Sequence length count mismatch: expected {record_num}, got {seq_len_count}")

        # Get the compressed sequence data (rest of payload after lengths)
        compressed_sequences = remaining_data[lengths_consumed:]

        # Decompress and extract sequences using unified interface
        sequence_bytes_list = str_decoder(compressed_sequences, sequence_lengths)

        # Build segments dictionary
        for i in range(record_num):
            segment_id = segment_ids[i]
            sequence_length = sequence_lengths[i]
            if sequence_length == 0:
                sequence = "*"
            else:
                sequence = sequence_bytes_list[i].decode("ascii")

            segments[segment_id] = {
                "sequence": sequence,
                "length": sequence_length,
                "opt_fields": {},  # Default empty for backward compatibility
            }

        logger.debug(f"Decoded {len(segments)} segments")

        return segments, offset - initial_offset

    def _parse_links_block(self, bgfa_data: bytes, segment_names: list, start_offset: int) -> tuple[list, int]:
        """Parse links from BGFA data.

        Supports all compression methods defined in the BGFA spec:
        - compression_fromto: encoding strategy for from/to segment IDs
        - compression_cigars: encoding strategy for CIGAR strings
          (high byte for CIGAR lengths, low byte for CIGAR string compression)

        :param bgfa_data: Binary BGFA data
        :param segment_names: List of segment names
        :param start_offset: Offset where links blocks start
        :return: (List of link dictionaries, bytes consumed)
        """
        initial_offset = start_offset
        offset = start_offset
        links = []

        # Read block header - section_id (uint8), then uint16 fields
        section_id = struct.unpack_from("<B", bgfa_data, offset)[0]
        offset += 1
        if section_id != SECTION_ID_LINKS:
            raise ValueError(f"Expected section_id={SECTION_ID_LINKS}, got {section_id}")

        record_num = struct.unpack_from("<H", bgfa_data, offset)[0]
        offset += 2
        compression_fromto = struct.unpack_from("<H", bgfa_data, offset)[0]
        offset += 2
        compression_cigars = struct.unpack_from("<H", bgfa_data, offset)[0]
        offset += 2
        compressed_len = struct.unpack_from("<Q", bgfa_data, offset)[0]
        offset += 8
        uncompressed_len = struct.unpack_from("<Q", bgfa_data, offset)[0]
        offset += 8

        # Read link data
        link_data = bgfa_data[offset : offset + compressed_len]
        offset += compressed_len

        # Extract encoding strategies (currently unused but reserved for future use)
        _ = (compression_fromto >> 8) & 0xFF  # fromto_int_encoding
        _ = (compression_cigars >> 8) & 0xFF  # cigars_int_encoding
        _ = compression_cigars & 0xFF  # cigars_str_encoding

        logger.debug(
            f"Parsing links block: record_num={record_num}, "
            f"compression_fromto={compression_fromto:#06x}, "
            f"compression_cigars={compression_cigars:#06x}, "
            f"compressed_len={compressed_len}, uncompressed_len={uncompressed_len}"
        )

        # Identity encoding (both 0x0000): column-wise layout
        if compression_fromto == 0x0000 and compression_cigars == 0x0000:
            pos = 0
            # Read all from IDs
            from_ids = []
            for _ in range(record_num):
                from_ids.append(struct.unpack_from("<Q", link_data, pos)[0])
                pos += 8
            # Read all to IDs
            to_ids = []
            for _ in range(record_num):
                to_ids.append(struct.unpack_from("<Q", link_data, pos)[0])
                pos += 8
            # Read orientation bits (uint64 list)
            from_orns, consumed = _unpack_orientation_bits_uint64(link_data[pos:], record_num)
            pos += consumed
            to_orns, consumed = _unpack_orientation_bits_uint64(link_data[pos:], record_num)
            pos += consumed
            # Read null-terminated cigar strings
            cigar_list = []
            for _ in range(record_num):
                cigar_bytes = bytearray()
                while pos < len(link_data) and link_data[pos] != 0:
                    cigar_bytes.append(link_data[pos])
                    pos += 1
                pos += 1  # Skip null terminator
                cigar_list.append(cigar_bytes.decode("ascii"))

            for i in range(record_num):
                from_name = (
                    segment_names[from_ids[i] - 1] if 0 < from_ids[i] <= len(segment_names) else f"node_{from_ids[i]}"
                )
                to_name = segment_names[to_ids[i] - 1] if 0 < to_ids[i] <= len(segment_names) else f"node_{to_ids[i]}"
                links.append(
                    {
                        "from_node": from_name,
                        "from_orn": "-" if from_orns[i] else "+",
                        "to_node": to_name,
                        "to_orn": "-" if to_orns[i] else "+",
                        "alignment": cigar_list[i],
                    }
                )

            return links, offset - initial_offset

        # Non-identity: payload layout is:
        # 1. Encoded from IDs
        # 2. Encoded to IDs
        # 3. from_orientation bits (uint64 list)
        # 4. to_orientation bits (uint64 list)
        # 5. Encoded CIGAR lengths
        # 6. Compressed concatenated CIGARs

        fromto_int_decoder = get_integer_decoder(compression_fromto)
        cigars_int_decoder = get_integer_decoder(compression_cigars)
        cigars_str_decoder = get_string_decoder(compression_cigars)

        # Decode from IDs
        from_ids, from_consumed = fromto_int_decoder(link_data, record_num)
        if len(from_ids) != record_num:
            raise ValueError(f"From ID count mismatch: expected {record_num}, got {len(from_ids)}")

        # Decode to IDs
        remaining_data = link_data[from_consumed:]
        to_ids, to_consumed = fromto_int_decoder(remaining_data, record_num)
        if len(to_ids) != record_num:
            raise ValueError(f"To ID count mismatch: expected {record_num}, got {len(to_ids)}")

        # Decode orientation bits
        remaining_data = remaining_data[to_consumed:]
        from_orns, from_orn_consumed = _unpack_orientation_bits_uint64(remaining_data, record_num)
        remaining_data = remaining_data[from_orn_consumed:]
        to_orns, to_orn_consumed = _unpack_orientation_bits_uint64(remaining_data, record_num)
        remaining_data = remaining_data[to_orn_consumed:]

        # Decode CIGAR lengths
        cigar_lengths, lengths_consumed = cigars_int_decoder(remaining_data, record_num)
        if len(cigar_lengths) != record_num:
            raise ValueError(f"CIGAR length count mismatch: expected {record_num}, got {len(cigar_lengths)}")

        # Get the compressed CIGAR data
        compressed_cigars = remaining_data[lengths_consumed:]

        # Decompress and extract CIGARs
        cigar_bytes_list = cigars_str_decoder(compressed_cigars, cigar_lengths)

        # Build links list
        for i in range(record_num):
            from_node_id = from_ids[i]
            to_node_id = to_ids[i]
            cigar = cigar_bytes_list[i].decode("ascii")

            from_name = (
                segment_names[from_node_id - 1] if 0 < from_node_id <= len(segment_names) else f"node_{from_node_id}"
            )
            to_name = segment_names[to_node_id - 1] if 0 < to_node_id <= len(segment_names) else f"node_{to_node_id}"

            links.append(
                {
                    "from_node": from_name,
                    "from_orn": "-" if from_orns[i] else "+",
                    "to_node": to_name,
                    "to_orn": "-" if to_orns[i] else "+",
                    "alignment": cigar,
                }
            )

        logger.debug(f"Decoded {len(links)} links")

        return links, offset - initial_offset

    def _decompress_string_list(self, compressed_data: bytes, compression_type: int, record_num: int) -> list[str]:
        """Decompress a list of strings based on compression type.

        :param compressed_data: Compressed string data
        :param compression_type: Compression type code
        :param record_num: Number of strings to decode
        :return: List of decompressed strings
        """

        def decode_string(string_bytes: bytes) -> str:
            """Decode bytes to string, trying UTF-8 first, then Latin-1 as fallback."""
            try:
                return string_bytes.decode("utf-8")
            except UnicodeDecodeError:
                return string_bytes.decode("latin-1")

        str_encoding = compression_type & 0xFF

        if str_encoding == STRING_ENCODING_IDENTITY:
            strings = []
            pos = 0
            while pos < len(compressed_data):
                end_pos = compressed_data.find(0, pos)
                if end_pos == -1:
                    break
                string_bytes = compressed_data[pos:end_pos]
                strings.append(decode_string(string_bytes))
                pos = end_pos + 1
            return strings
        else:
            int_decoder = get_integer_decoder(compression_type)
            str_decoder = get_string_decoder(compression_type)

            try:
                lengths, lengths_consumed = int_decoder(compressed_data, record_num)
                compressed_strings = compressed_data[lengths_consumed:]
                string_bytes = str_decoder(compressed_strings, lengths)
                strings = [s.decode("ascii") for s in string_bytes]
                return strings
            except Exception as e:
                logger.warning(f"Failed to decompress string list: {e}")
                return []

    def _parse_paths_blocks(
        self, bgfa_data: bytes, header: dict, segment_names: list, start_offset: int
    ) -> tuple[list, int]:
        """Parse a paths block from BGFA data.

        :param bgfa_data: Binary BGFA data
        :param header: Parsed header information
        :param segment_names: List of segment names
        :param start_offset: Offset where the paths block start
        :return: (List of paths dictionaries, number of bytes read)
        """
        offset = start_offset

        # Read block header - section_id (uint8), then uint16 fields
        section_id = struct.unpack_from("<B", bgfa_data, offset)[0]
        offset += 1
        if section_id != SECTION_ID_PATHS:
            raise ValueError(f"Expected section_id={SECTION_ID_PATHS}, got {section_id}")

        record_num = int.from_bytes(bgfa_data[offset : offset + 2], byteorder="little", signed=False)
        offset += 2
        compression_path_names = int.from_bytes(bgfa_data[offset : offset + 2], byteorder="little", signed=False)
        offset += 2
        compression_cigars = int.from_bytes(bgfa_data[offset : offset + 2], byteorder="little", signed=False)
        offset += 2
        compressed_len_cigar = int.from_bytes(bgfa_data[offset : offset + 8], byteorder="little", signed=False)
        offset += 8
        offset += 8  # Skip uncompressed_len_cigar
        compressed_len_name = int.from_bytes(bgfa_data[offset : offset + 8], byteorder="little", signed=False)
        offset += 8
        offset += 8  # Skip uncompressed_len_name

        # Extract compressed payloads - order: cigars first, then names
        if compressed_len_cigar > 0:
            compressed_cigars = bgfa_data[offset : offset + compressed_len_cigar]
            offset += compressed_len_cigar

            # Decompress cigar strings
            try:
                cigar_strings = self._decompress_string_list(compressed_cigars, compression_cigars, record_num)
            except Exception as e:
                logger.warning(f"Failed to decompress cigar strings: {e}")
                cigar_strings = []
        else:
            cigar_strings = []

        if compressed_len_name > 0:
            compressed_names = bgfa_data[offset : offset + compressed_len_name]
            offset += compressed_len_name

            # Decompress path names
            try:
                path_names = self._decompress_string_list(compressed_names, compression_path_names, record_num)
            except Exception as e:
                logger.warning(f"Failed to decompress path names: {e}")
                path_names = []
        else:
            path_names = []

        # Parse paths data (stored as walks - sequence of oriented segment IDs)
        paths = []
        for i in range(record_num):
            if i < len(path_names):
                path_name = path_names[i]
            else:
                path_name = f"path_{i}"

            if i < len(cigar_strings):
                cigar = cigar_strings[i]
            else:
                cigar = "*"

            # Create path dictionary
            path_data = {
                "name": path_name,
                "segments": [],  # TODO: Parse actual path segments when walks are implemented
                "cigar": cigar,
            }
            paths.append(path_data)

        return paths, offset - start_offset

    def _parse_walks_blocks(
        self, bgfa_data: bytes, header: dict, segment_names: list, start_offset: int
    ) -> tuple[list, int]:
        """Parse a walks block from BGFA data.

        :param bgfa_data: Binary BGFA data
        :param header: Parsed header information
        :param segment_names: List of segment names
        :param start_offset: Offset where the walks block start
        :return: (List of walks dictionaries, number of bytes read)
        """
        offset = start_offset

        # Read block header - section_id (uint8), then uint16 fields + length fields
        section_id = struct.unpack_from("<B", bgfa_data, offset)[0]
        offset += 1
        if section_id != SECTION_ID_WALKS:
            raise ValueError(f"Expected section_id={SECTION_ID_WALKS}, got {section_id}")

        record_num = int.from_bytes(bgfa_data[offset : offset + 2], byteorder="little", signed=False)
        offset += 2
        offset += 10  # Skip 5 compression code fields (each uint16)
        compressed_len_sam = int.from_bytes(bgfa_data[offset : offset + 8], byteorder="little", signed=False)
        offset += 8
        offset += 8  # Skip uncompressed_len_sam
        compressed_len_seq = int.from_bytes(bgfa_data[offset : offset + 8], byteorder="little", signed=False)
        offset += 8
        offset += 8  # Skip uncompressed_len_seq
        compressed_len_walk = int.from_bytes(bgfa_data[offset : offset + 8], byteorder="little", signed=False)
        offset += 8
        offset += 8  # Skip uncompressed_len_walk

        # Extract and decompress payloads
        if compressed_len_sam > 0:
            compressed_sam = bgfa_data[offset : offset + compressed_len_sam]
            offset += compressed_len_sam
            sample_ids = self._decompress_string_list(
                compressed_sam, 0x0000, record_num
            )  # Sample IDs are typically identity encoded
        else:
            sample_ids = []

        if compressed_len_seq > 0:
            compressed_seq = bgfa_data[offset : offset + compressed_len_seq]
            offset += compressed_len_seq
            sequence_ids = self._decompress_string_list(
                compressed_seq, 0x0000, record_num
            )  # Sequence IDs are typically identity encoded
        else:
            sequence_ids = []

        if compressed_len_walk > 0:
            compressed_walks = bgfa_data[offset : offset + compressed_len_walk]
            offset += compressed_len_walk

            # For now, treat walk data as simple sequence data
            # TODO: Implement proper walk decoding (segment IDs + orientations)
            try:
                walks_data = self._decompress_string_list(compressed_walks, 0x0000, record_num)
            except Exception as e:
                logger.warning(f"Failed to decompress walks data: {e}")
                walks_data = []
        else:
            walks_data = []

        # Create walk dictionaries
        walks = []
        for i in range(record_num):
            if i < len(sample_ids):
                sample_id = sample_ids[i]
            else:
                sample_id = f"sample_{i}"

            if i < len(sequence_ids):
                sequence_id = sequence_ids[i]
            else:
                sequence_id = f"sequence_{i}"

            if i < len(walks_data):
                walk_data = walks_data[i]
            else:
                walk_data = "*"

            # Create walk dictionary
            walk_dict = {
                "sample_id": sample_id,
                "sequence_id": sequence_id,
                "walk": walk_data,  # TODO: Parse actual walk segments and orientations
                "haplotype_index": 0,  # TODO: Parse from walk data
                "start_position": 0,  # TODO: Parse from walk data
                "end_position": 0,  # TODO: Parse from walk data
            }
            walks.append(walk_dict)

        return walks, offset - start_offset


class BGFAWriter:
    def __init__(self, gfa_graph: GFA, block_size: int = 1024, compression_options: dict | None = None):
        self._gfa = gfa_graph
        self._compression_options = compression_options
        self._block_size = block_size

    def to_bgfa(
        self,
        verbose: bool = False,
        debug: bool = False,
        logfile: str | None = None,
    ) -> bytes:
        block_size = self._block_size
        # Create a BytesIO buffer
        buffer = io.BytesIO()

        # Determine log level based on verbosity
        if debug:
            log_level = logging.DEBUG
        elif verbose:
            log_level = logging.INFO
        else:
            log_level = logging.WARNING

        # Only create log file if we're actually logging something
        if log_level <= logging.INFO:
            if logfile is None:
                # Create a temporary log file in appropriate directory
                try:
                    # Try to use results directory if available
                    output_mgr = OutputManager()
                    temp_log = output_mgr.create_temp_file(".log", output_mgr.get_test_dir("bgfa"))
                    logfile = str(temp_log)
                except Exception:
                    # Fallback to system temp directory
                    temp_log = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log")
                    logfile = temp_log.name
                    temp_log.close()
                print(f"Logging to temporary file: {logfile}")
        # If we're not logging, use a dummy logfile
        elif os.name == "nt":  # Windows
            logfile = "NUL"
        else:  # Unix-like
            logfile = "/dev/null"

        # Clear any existing handlers
        logging.getLogger().handlers.clear()

        # Create formatter
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

        handlers = []

        # Only add file handler if we're actually logging to a file

        if logfile not in {"/dev/null", "NUL"}:
            file_handler = logging.FileHandler(logfile)
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            handlers.append(file_handler)

        # Always add stream handler for console output
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(log_level)
        stream_handler.setFormatter(formatter)
        handlers.append(stream_handler)

        # Configure root logger
        logging.basicConfig(level=log_level, handlers=handlers)

        # Get logger for this module
        logger = logging.getLogger(__name__)

        logger.info(f"Starting BGFA conversion with block_size={block_size}")
        if debug:
            logger.debug(f"Debug mode enabled, logfile: {logfile}")
            logger.debug(f"Compression options: {self._compression_options}")
        elif verbose:
            logger.debug(f"Verbose mode enabled, logfile: {logfile}")
            logger.debug(f"Compression options: {self._compression_options}")

        # Write the header
        self._write_header(
            buffer,
            self._block_size,
        )

        # Get segment names sorted by segment ID
        segment_names = list(self._gfa.nodes())
        segment_map = {name: idx for idx, name in enumerate(segment_names)}
        # Store for use by _write_links_block
        self._segment_map = segment_map

        # Write segment names in blocks
        offset = 0
        total_names = len(segment_names)
        logger.info(f"Writing {total_names} segment names in blocks of size {block_size}")
        logger.debug(f"Segment names: {segment_names[:5] if len(segment_names) > 5 else segment_names}")
        while offset < total_names:
            chunk = segment_names[offset : min(offset + block_size, total_names)]
            block_num = offset // block_size + 1
            logger.info(f"Writing segment names block {block_num}: {len(chunk)} names")
            logger.debug(f"Block {block_num} contains: {chunk[:3] if len(chunk) > 3 else chunk}")
            # Get compression code from options (default: 0x0000 = identity)
            segment_names_compression_code = self._compression_options.get("segment_names_compression_code", 0x0000)
            self._write_segment_names_block(buffer, chunk, compression_code=segment_names_compression_code)
            offset += len(chunk)

        # Write segments blocks
        logger.debug("Writing segment blocks")
        offset = 0
        # Use segment_map created above (contains all nodes)
        sorted_items = sorted(segment_map.items(), key=lambda x: x[1])
        total_segments = len(sorted_items)
        logger.info(f"Writing {total_segments} segments in blocks of size {block_size}")
        while offset < total_segments:
            chunk = sorted_items[offset : min(offset + block_size, total_segments)]
            block_num = offset // block_size + 1
            logger.info(f"Writing segments block {block_num}: {len(chunk)} segments")
            if len(chunk) > 0:
                name, seg_id = chunk[0]
                logger.debug(f"First segment in block {block_num}: name={name}, id={seg_id}")
            # Get compression code from options (default: 0x0000 = identity)
            segments_compression_code = self._compression_options.get("segments_compression_code", 0x0000)
            self._write_segments_block(
                buffer,
                chunk,
                compression_code=segments_compression_code,
            )
            offset += len(chunk)

        # Write links blocks
        edges_iter = iter(self._gfa.edges(data=True, keys=True))
        total_links = len(self._gfa.edges())
        logger.info(f"Writing {total_links} links in blocks of size {block_size}")
        block_num = 1
        while True:
            chunk = list(islice(edges_iter, block_size))
            if not chunk:
                break
            logger.info(f"Writing links block {block_num}: {len(chunk)} links")
            # chunk[0] is (u, v, key, data)
            u, v, key, data = chunk[0]
            from_node = data.get("from_node", u)
            to_node = data.get("to_node", v)
            logger.debug(f"First link in block {block_num}: from={from_node}, to={to_node}")
            # Get compression codes from options (default: 0x0000 = identity)
            links_fromto_compression = self._compression_options.get("links_fromto_compression_code", 0x0000)
            links_cigars_compression = self._compression_options.get("links_cigars_compression_code", 0x0000)
            self._write_links_block(
                buffer,
                chunk,
                compression_fromto=links_fromto_compression,
                compression_cigars=links_cigars_compression,
            )
            block_num += 1

        # Write paths blocks
        paths_iter = iter(self._gfa.paths_iter(data=True))
        total_paths = len(self._gfa.paths())
        logger.info(f"Writing {total_paths} paths in blocks of size {block_size}")
        block_num = 1
        while True:
            chunk = list(islice(paths_iter, block_size))
            if not chunk:
                break
            logger.info(f"Writing paths block {block_num}: {len(chunk)} paths")
            # Get compression codes from options (default: 0x0000 = identity)
            paths_names_compression = self._compression_options.get("paths_names_compression_code", 0x0000)
            paths_paths_compression = self._compression_options.get("paths_paths_compression_code", 0x0000)
            paths_cigars_compression = self._compression_options.get("paths_cigars_compression_code", 0x0000)
            self._write_paths_block(
                buffer,
                chunk,
                compression_path_names=paths_names_compression,
                compression_paths=paths_paths_compression,
                compression_cigars=paths_cigars_compression,
            )
            block_num += 1

        # Write walks blocks
        walks_iter = iter(self._gfa.walks_iter(data=True))
        total_walks = len(self._gfa.walks())
        logger.info(f"Writing {total_walks} walks in blocks of size {block_size}")
        block_num = 1
        while True:
            chunk = list(islice(walks_iter, block_size))
            if not chunk:
                break
            logger.info(f"Writing walks block {block_num}: {len(chunk)} walks")
            # Get compression codes from options (default: 0x0000 = identity)
            walks_sample_ids_compression = self._compression_options.get("walks_sample_ids_compression_code", 0x0000)
            walks_hap_indices_compression = self._compression_options.get("walks_hap_indices_compression_code", 0x0000)
            walks_seq_ids_compression = self._compression_options.get("walks_seq_ids_compression_code", 0x0000)
            walks_start_compression = self._compression_options.get("walks_start_compression_code", 0x0000)
            walks_end_compression = self._compression_options.get("walks_end_compression_code", 0x0000)
            walks_walks_compression = self._compression_options.get("walks_walks_compression_code", 0x0000)
            self._write_walks_block(
                buffer,
                chunk,
                compression_sample_ids=walks_sample_ids_compression,
                compression_hap_indices=walks_hap_indices_compression,
                compression_seq_ids=walks_seq_ids_compression,
                compression_start=walks_start_compression,
                compression_end=walks_end_compression,
                compression_walks=walks_walks_compression,
            )
            block_num += 1

        # Get the entire buffer as bytes
        result = buffer.getvalue()
        logger.info(f"BGFA conversion complete. Total size: {len(result)} bytes")
        logger.debug(
            f"Result breakdown: header={self._compute_header_size()}, "
            f"segments={self._compute_segments_size()}, links={self._compute_links_size()}"
        )
        return result

    def _compute_header_size(self):
        """Estimate header size."""
        # Version (2) + block_size (2) + counts (4*8) + header text (variable)
        return 2 + 2 + 32  # Base size, actual text will add more

    def _compute_segments_size(self):
        """Estimate segments data size."""
        total = 0
        for node_id in self._gfa.nodes():
            node_data = dict(self._gfa.nodes(data=True))[node_id]
            sequence = node_data.get("sequence", "*")
            total += 8 + 8 + len(sequence) + 1  # segment_id + seq_len + sequence + null
        return total

    def _compute_links_size(self):
        """Estimate links data size."""
        total = 0
        for _u, _v, _key, data in self._gfa.edges(data=True, keys=True):
            alignment = data.get("alignment", "*")
            total += 8 + 8 + len(alignment) + 1  # from_id + to_id + cigar + null
        return total

    def _write_header(
        self,
        buffer,
        block_size,
    ):
        """Write BGFA header in binary format."""
        # Write version (uint16)
        buffer.write(struct.pack("<H", 1))
        # Write reserved space (previously block_size + S_len, L_len, P_len, W_len)
        buffer.write(b"\x00" * 34)

        # Write header text (C string)
        header_text = "H\tVN:Z:1.0"
        buffer.write(header_text.encode("ascii"))
        buffer.write(b"\x00")  # null terminator

    def header(self, block_size: int = 1024) -> bytes:
        """Create placeholder header with zeros."""
        buffer = io.BytesIO()
        self._write_header(buffer, block_size)
        return buffer.getvalue()

    def _write_segment_names_block(
        self,
        buffer,
        to_write,
        compression_code: int = 0x0000,
    ) -> int:
        """Write a segment names block to the buffer.

        :param buffer: BytesIO buffer to write to
        :param to_write: List of segment names to write
        :param compression_code: uint16 compression code
            (high byte=integer encoding for lengths,
            low byte=string encoding for names). Default 0x0000 (identity).
            See BGFA spec for encoding strategies:
            - Integer: 0x00=identity, 0x01=varint, 0x02=fixed16, etc.
            - String: 0x00=identity, 0x01=zstd, 0x02=gzip, 0x03=lzma,
            0x04=huffman
        :return: Number of bytes written
        """
        record_num = len(to_write)
        logger.info(f"Writing segment names block with {record_num} names")
        logger.debug(f"Compression code: {compression_code:#06x}")

        # Extract encoding strategies from compression code
        int_encoding = (compression_code >> 8) & 0xFF
        str_encoding = compression_code & 0xFF
        logger.debug(f"Integer encoding: {int_encoding:#04x}, String encoding: {str_encoding:#04x}")

        if compression_code == 0x0000:
            # Identity encoding: null-terminated strings
            payload = b"".join(name.encode("ascii") + b"\x00" for name in to_write)
            uncompressed_len = len(payload)
            compressed_len = len(payload)
        else:
            # Non-identity: format matching reader's _parse_segment_names_block
            # 1. Encode string lengths with integer encoder
            # 2. Compress concatenated names (no null terminators) with string encoder
            int_encoder = get_integer_encoder(compression_code)
            int_encoding = (compression_code >> 8) & 0xFF
            lengths = [len(name.encode("ascii")) for name in to_write]
            encoded_lengths = int_encoder(lengths)
            # Add comma delimiter for identity integer encoding to separate from compressed names
            if int_encoding == INTEGER_ENCODING_IDENTITY and lengths:
                encoded_lengths += b","

            concatenated = "".join(to_write)
            compressed_names = _compress_string_for_bgfa(concatenated, str_encoding)

            payload = encoded_lengths + compressed_names
            uncompressed_len = sum(lengths)
            compressed_len = len(payload)

        logger.debug(
            f"Segment names block payload: compressed_len={compressed_len}, "
            f"uncompressed_len={uncompressed_len}, compression={compression_code:#06x}"
        )

        # Write block header according to spec: uint8, uint16, uint16, uint64, uint64
        buffer.write(struct.pack("<B", SECTION_ID_SEGMENT_NAMES))
        buffer.write(struct.pack("<H", record_num))
        buffer.write(struct.pack("<H", compression_code))
        buffer.write(struct.pack("<Q", compressed_len))
        buffer.write(struct.pack("<Q", uncompressed_len))
        buffer.write(payload)

        bytes_written = 1 + 2 + 2 + 8 + 8 + compressed_len
        logger.info(f"Segment names block written: {bytes_written} bytes")
        return bytes_written

    def _write_segments_block(
        self,
        buffer,
        chunk,
        compression_code: int = 0x0000,
    ) -> None:
        """Write a segments block to buffer.

        :param buffer: BytesIO buffer to write to
        :param chunk: List of (name, seg_id) tuples to write
        :param compression_code: uint16 compression code
            (high byte=integer encoding, low byte=string encoding).
            Default 0x0000 (identity). See BGFA spec for encoding:
            - Integer: 0x00=identity, 0x01=varint, 0x02=fixed16, etc.
            - String: 0x00=identity, 0x01=zstd, 0x02=gzip, 0x03=lzma, 0x04=huffman
        """
        record_num = len(chunk)
        logger.info(f"Writing segments block with {record_num} segments")
        logger.debug(f"Compression code: {compression_code:#06x}")

        # Extract encoding strategies from compression code
        int_encoding = (compression_code >> 8) & 0xFF
        str_encoding = compression_code & 0xFF
        logger.debug(f"Integer encoding: {int_encoding:#04x}, String encoding: {str_encoding:#04x}")

        # Collect segment data
        segment_ids = []
        sequence_lengths = []
        sequences = []
        opt_fields_list = []
        for i, (name, seg_id) in enumerate(chunk):
            node_data = dict(self._gfa.nodes(data=True))[name]
            sequence = node_data.get("sequence", "*")
            seq_len = len(sequence) if sequence != "*" else 0

            # Extract optional fields (excluding standard GFA fields)
            opt_fields = {}
            for key, value in node_data.items():
                if key not in ["nid", "sequence", "slen"]:
                    opt_fields[key] = value

            segment_ids.append(seg_id)
            sequence_lengths.append(seq_len)
            sequences.append(sequence)
            opt_fields_list.append(opt_fields)

            if i < 3:
                logger.debug(
                    f"Segment {i}: name={name}, seg_id={seg_id}, seq_len={seq_len}, opt_fields={list(opt_fields.keys())}"
                )
            elif i == 3:
                logger.debug("... (remaining segments omitted)")

        # Convert optional fields to JSON strings for storage
        import json

        opt_fields_strings = [json.dumps(opt_fields) if opt_fields else "{}" for opt_fields in opt_fields_list]

        if compression_code == 0x0000:
            # Identity encoding: segment_id (uint64) + seq_len (uint64) + null-terminated sequence + null-terminated optional fields JSON
            payload_parts = []
            for seg_id, seq_len, sequence, opt_fields_str in zip(
                segment_ids, sequence_lengths, sequences, opt_fields_strings, strict=False
            ):
                payload_parts.append(struct.pack("<Q", seg_id))
                payload_parts.append(struct.pack("<Q", seq_len))
                payload_parts.append(sequence.encode("ascii") + b"\x00")
                payload_parts.append(opt_fields_str.encode("ascii") + b"\x00")
            payload = b"".join(payload_parts)
            uncompressed_len = len(payload)
            compressed_len = len(payload)
        else:
            # Non-identity: format matching reader's _parse_segments_block
            # 1. Encoded segment IDs (using integer encoding)
            # 2. Encoded sequence lengths (using integer encoding)
            # 3. Compressed concatenated sequences (using string encoding)
            # 4. Compressed concatenated optional fields JSON strings (using string encoding)
            int_encoder = get_integer_encoder(compression_code)
            encoded_ids = int_encoder(segment_ids)
            # Add comma delimiter for identity integer encoding to separate from lengths
            if int_encoding == INTEGER_ENCODING_IDENTITY and encoded_ids:
                encoded_ids += b","
            encoded_lengths = int_encoder(sequence_lengths)
            compressed_sequences = _compress_string_for_bgfa("".join(sequences), str_encoding)
            compressed_opt_fields = _compress_string_for_bgfa("".join(opt_fields_strings), str_encoding)
            payload = encoded_ids + encoded_lengths + compressed_sequences + compressed_opt_fields
            uncompressed_len = sum(sequence_lengths) + sum(len(opt_str) for opt_str in opt_fields_strings)
            compressed_len = len(payload)

        logger.debug(
            f"Segments block payload: compressed_len={compressed_len}, "
            f"uncompressed_len={uncompressed_len}, compression={compression_code:#06x}"
        )

        # Write header: section_id (uint8) + record_num (uint16) + compression (uint16) + lengths (2x uint64)
        buffer.write(struct.pack("<B", SECTION_ID_SEGMENTS))
        buffer.write(struct.pack("<H", record_num))
        buffer.write(struct.pack("<H", compression_code))
        buffer.write(struct.pack("<Q", compressed_len))
        buffer.write(struct.pack("<Q", uncompressed_len))
        buffer.write(payload)

        logger.info(f"Segments block written: {21 + compressed_len} bytes")

    def _write_links_block(
        self,
        buffer,
        chunk,
        compression_fromto: int = 0x0000,
        compression_cigars: int = 0x0000,
    ) -> None:
        """Write a links block to buffer.

        :param buffer: BytesIO buffer to write to
        :param chunk: List of (u, v, key, data) edge tuples to write
        :param compression_fromto: uint16 compression code for from/to segment IDs.
                                   See BGFA spec for encoding strategies:
                                   - 0x00=identity, 0x01=varint, 0x02=fixed16, etc.
        :param compression_cigars: uint16 compression code for CIGAR strings.
                                   See BGFA spec for encoding strategies:
                                   - 0x00=identity, 0x01=zstd, 0x02=gzip, 0x03=lzma, 0x04=huffman
        """
        record_num = len(chunk)
        logger.info(f"Writing links block with {record_num} links")
        logger.debug(f"Compression codes: fromto={compression_fromto:#06x}, cigars={compression_cigars:#06x}")

        # Collect link data
        from_ids = []
        to_ids = []
        from_orns = []  # 0 = "+", 1 = "-"
        to_orns = []
        cigars = []

        for u, v, _key, data in chunk:
            from_name = data.get("from_node", u)
            to_name = data.get("to_node", v)
            alignment = data.get("alignment", "*")

            # 1-based segment IDs
            from_id = self._segment_map.get(from_name, -1) + 1
            to_id = self._segment_map.get(to_name, -1) + 1

            from_ids.append(from_id)
            to_ids.append(to_id)
            from_orns.append(0 if data.get("from_orn", "+") == "+" else 1)
            to_orns.append(0 if data.get("to_orn", "+") == "+" else 1)
            cigars.append(alignment)

        if record_num > 0:
            logger.debug(
                f"First link: from_id={from_ids[0]}, to_id={to_ids[0]}, "
                f"from_orn={from_orns[0]}, to_orn={to_orns[0]}, cigar={cigars[0]}"
            )

        # Pack orientation bits as uint64 list (per spec: `bits` = list of uint64)
        from_orn_bytes = _pack_orientation_bits_uint64(from_orns)
        to_orn_bytes = _pack_orientation_bits_uint64(to_orns)

        if compression_fromto == 0x0000 and compression_cigars == 0x0000:
            # Identity encoding — column-wise layout per spec:
            # all from_ids | all to_ids | from_orientation bits | to_orientation bits | cigars
            payload_parts = []
            for fid in from_ids:
                payload_parts.append(struct.pack("<Q", fid))
            for tid in to_ids:
                payload_parts.append(struct.pack("<Q", tid))
            payload_parts.append(from_orn_bytes)
            payload_parts.append(to_orn_bytes)
            for cigar in cigars:
                payload_parts.append(cigar.encode("ascii") + b"\x00")
            payload = b"".join(payload_parts)
            uncompressed_len = len(payload)
            compressed_len = len(payload)
        else:
            # Non-identity: format matching reader's _parse_links_block
            # 1. Encoded from IDs
            # 2. Encoded to IDs
            # 3. from_orientation bits (uint64 list)
            # 4. to_orientation bits (uint64 list)
            # 5. Encoded CIGAR lengths
            # 6. Compressed concatenated CIGARs
            fromto_int_encoder = get_integer_encoder(compression_fromto)
            fromto_int_encoding = (compression_fromto >> 8) & 0xFF
            cigars_int_encoder = get_integer_encoder(compression_cigars)
            cigars_str_encoding = compression_cigars & 0xFF

            encoded_from = fromto_int_encoder(from_ids)
            # Add comma delimiter for identity integer encoding to separate from to_ids
            if fromto_int_encoding == INTEGER_ENCODING_IDENTITY and encoded_from:
                encoded_from += b","
            encoded_to = fromto_int_encoder(to_ids)
            cigar_lengths = [len(c.encode("ascii")) for c in cigars]
            encoded_cigar_lengths = cigars_int_encoder(cigar_lengths)
            compressed_cigars_data = _compress_string_for_bgfa("".join(cigars), cigars_str_encoding)

            payload = (
                encoded_from
                + encoded_to
                + from_orn_bytes
                + to_orn_bytes
                + encoded_cigar_lengths
                + compressed_cigars_data
            )
            uncompressed_len = sum(cigar_lengths)
            compressed_len = len(payload)

        logger.debug(f"Links block payload: compressed_len={compressed_len}, uncompressed_len={uncompressed_len}")

        # Write header according to spec: section_id (uint8), record_num, compression_fromto, compression_cigars,
        # compressed_len, uncompressed_len
        buffer.write(struct.pack("<B", SECTION_ID_LINKS))
        buffer.write(struct.pack("<H", record_num))
        buffer.write(struct.pack("<H", compression_fromto))
        buffer.write(struct.pack("<H", compression_cigars))
        buffer.write(struct.pack("<Q", compressed_len))
        buffer.write(struct.pack("<Q", uncompressed_len))
        buffer.write(payload)

        bytes_written = 1 + 2 + 2 + 2 + 8 + 8 + compressed_len
        logger.info(f"Links block written: {bytes_written} bytes")

    def _write_paths_block(
        self,
        buffer,
        chunk,
        compression_path_names: int = 0x0000,
        compression_paths: int = 0x0000,
        compression_cigars: int = 0x0000,
    ) -> None:
        """Write a paths block to buffer.

        :param buffer: BytesIO buffer to write to
        :param chunk: List of path data tuples to write
        :param compression_path_names: uint16 compression code for path names.
                                       See BGFA spec for encoding strategies.
        :param compression_paths: uint16 compression code for paths (segment ID lists).
                                  See BGFA spec for walks/paths encoding strategies:
                                  - 0x00=identity, 0x01=orientation+strid, 0x02=orientation+numid
        :param compression_cigars: uint16 compression code for CIGAR strings.
                                   See BGFA spec for encoding strategies.
        """
        record_num = len(chunk)
        logger.info(f"Writing paths block with {record_num} paths")
        logger.debug(
            f"Compression codes: path_names={compression_path_names:#06x}, "
            f"paths={compression_paths:#06x}, cigars={compression_cigars:#06x}"
        )

        # Collect path data
        path_names = []
        path_segments = []  # List of lists of segment IDs
        path_cigars = []  # List of lists of CIGAR strings

        for path_data in chunk:
            # path_data is typically (path_id, data_dict) from paths_iter
            if isinstance(path_data, tuple) and len(path_data) == 2:
                path_id, data = path_data
            else:
                path_id = str(path_data)
                data = {}

            path_names.append(str(path_id))

            # Get segments and cigars from path data
            segments = data.get("segments", [])
            cigars = data.get("cigars", [])
            path_segments.append(segments)
            path_cigars.append(cigars)

        if record_num > 0:
            logger.debug(f"First path: name={path_names[0]}, segments={len(path_segments[0]) if path_segments else 0}")

        # Build path names payload
        names_str_encoding = compression_path_names & 0xFF
        if compression_path_names == 0x0000:
            # Identity: null-terminated strings
            compressed_names = b"".join(name.encode("ascii") + b"\x00" for name in path_names)
            uncompressed_len_name = len(compressed_names)
        else:
            # Non-identity: encode name lengths with integer encoder + compress names
            names_int_encoder = get_integer_encoder(compression_path_names)
            names_int_encoding = (compression_path_names >> 8) & 0xFF
            name_lengths = [len(name.encode("ascii")) for name in path_names]
            encoded_name_lengths = names_int_encoder(name_lengths)
            # Add comma delimiter for identity integer encoding
            if names_int_encoding == INTEGER_ENCODING_IDENTITY and name_lengths:
                encoded_name_lengths += b","
            compressed_name_data = _compress_string_for_bgfa("".join(path_names), names_str_encoding)
            compressed_names = encoded_name_lengths + compressed_name_data
            uncompressed_len_name = sum(name_lengths)
        compressed_len_name = len(compressed_names)

        # Paths payload (segment IDs with orientations) using walks/paths decomposition
        paths_payload = _encode_walks_payload(path_segments, self._segment_map, compression_paths)

        # Build CIGAR payload
        all_cigars = []
        for cigars in path_cigars:
            all_cigars.extend(cigars if cigars else [])

        cigars_str_encoding = compression_cigars & 0xFF
        if compression_cigars == 0x0000:
            # Identity: null-terminated strings
            compressed_cigars = b"".join(c.encode("ascii") + b"\x00" for c in all_cigars)
            uncompressed_len_cigar = len(compressed_cigars)
        else:
            # Non-identity: encode cigar lengths with integer encoder + compress cigars
            cigars_int_encoder = get_integer_encoder(compression_cigars)
            cigars_int_encoding = (compression_cigars >> 8) & 0xFF
            cigar_lengths = [len(c.encode("ascii")) for c in all_cigars]
            encoded_cigar_lengths = cigars_int_encoder(cigar_lengths)
            # Add comma delimiter for identity integer encoding
            if cigars_int_encoding == INTEGER_ENCODING_IDENTITY and cigar_lengths:
                encoded_cigar_lengths += b","
            compressed_cigar_data = _compress_string_for_bgfa("".join(all_cigars), cigars_str_encoding)
            compressed_cigars = encoded_cigar_lengths + compressed_cigar_data
            uncompressed_len_cigar = sum(cigar_lengths)
        compressed_len_cigar = len(compressed_cigars)

        logger.debug(
            f"Paths block: names={compressed_len_name}/{uncompressed_len_name} bytes, "
            f"cigars={compressed_len_cigar}/{uncompressed_len_cigar} bytes"
        )

        # Write header according to spec: section_id (uint8), record_num, compression fields, length fields
        buffer.write(struct.pack("<B", SECTION_ID_PATHS))
        buffer.write(struct.pack("<H", record_num))
        buffer.write(struct.pack("<H", compression_path_names))
        buffer.write(struct.pack("<H", compression_paths))
        buffer.write(struct.pack("<H", compression_cigars))
        buffer.write(struct.pack("<Q", compressed_len_cigar))
        buffer.write(struct.pack("<Q", uncompressed_len_cigar))
        buffer.write(struct.pack("<Q", compressed_len_name))
        buffer.write(struct.pack("<Q", uncompressed_len_name))

        # Write payloads
        buffer.write(compressed_names)
        buffer.write(paths_payload)
        buffer.write(compressed_cigars)

        bytes_written = (
            1 + 2 + 2 + 2 + 2 + 8 + 8 + 8 + 8 + compressed_len_name + len(paths_payload) + compressed_len_cigar
        )
        logger.info(f"Paths block written: {bytes_written} bytes")

    def _write_walks_block(
        self,
        buffer,
        chunk,
        compression_sample_ids: int = 0x0000,
        compression_hap_indices: int = 0x0000,
        compression_seq_ids: int = 0x0000,
        compression_start: int = 0x0000,
        compression_end: int = 0x0000,
        compression_walks: int = 0x0000,
    ) -> None:
        """Write a walks block to buffer.

        :param buffer: BytesIO buffer to write to
        :param chunk: List of walk data tuples to write
        :param compression_sample_ids: uint16 compression code for sample IDs (strings).
        :param compression_hap_indices: uint16 compression code for haplotype indices (integers).
        :param compression_seq_ids: uint16 compression code for sequence IDs (strings).
        :param compression_start: uint16 compression code for start positions (integers).
        :param compression_end: uint16 compression code for end positions (integers).
        :param compression_walks: uint16 compression code for walks (segment ID lists).
                                  See BGFA spec for walks encoding strategies:
                                  - 0x00=identity, 0x01=orientation+strid, 0x02=orientation+numid
        """
        record_num = len(chunk)
        logger.info(f"Writing walks block with {record_num} walks")
        logger.debug(
            f"Compression codes: sample_ids={compression_sample_ids:#06x}, "
            f"hap_indices={compression_hap_indices:#06x}, seq_ids={compression_seq_ids:#06x}, "
            f"start={compression_start:#06x}, end={compression_end:#06x}, "
            f"walks={compression_walks:#06x}"
        )

        # Collect walk data
        sample_ids = []
        hap_indices = []
        seq_ids = []
        start_positions = []
        end_positions = []
        walk_segments = []  # List of lists of segment references

        for walk_data in chunk:
            # walk_data is typically (walk_id, data_dict) from walks_iter
            if isinstance(walk_data, tuple) and len(walk_data) == 2:
                _, data = walk_data
            else:
                data = {}

            # Extract walk fields
            sample_id = data.get("sample_id", "")
            hap_index = data.get("haplotype_index", 0)
            seq_id = data.get("sequence_id", "")
            start_pos = data.get("start", 0)
            end_pos = data.get("end", 0)
            segments = data.get("segments", [])

            sample_ids.append(str(sample_id))
            hap_indices.append(int(hap_index) if hap_index else 0)
            seq_ids.append(str(seq_id))
            start_positions.append(int(start_pos) if start_pos else 0)
            end_positions.append(int(end_pos) if end_pos else 0)
            walk_segments.append(segments)

        if record_num > 0:
            logger.debug(
                f"First walk: sample={sample_ids[0]}, hap={hap_indices[0]}, "
                f"seq={seq_ids[0]}, segments={len(walk_segments[0]) if walk_segments else 0}"
            )

        # Build sample IDs payload
        sam_str_encoding = compression_sample_ids & 0xFF
        if compression_sample_ids == 0x0000:
            compressed_samples = b"".join(s.encode("ascii") + b"\x00" for s in sample_ids)
            uncompressed_len_sam = len(compressed_samples)
        else:
            sam_int_encoder = get_integer_encoder(compression_sample_ids)
            sam_int_encoding = (compression_sample_ids >> 8) & 0xFF
            sam_lengths = [len(s.encode("ascii")) for s in sample_ids]
            encoded_sam_lengths = sam_int_encoder(sam_lengths)
            # Add comma delimiter for identity integer encoding
            if sam_int_encoding == INTEGER_ENCODING_IDENTITY and sam_lengths:
                encoded_sam_lengths += b","
            compressed_sam_data = _compress_string_for_bgfa("".join(sample_ids), sam_str_encoding)
            compressed_samples = encoded_sam_lengths + compressed_sam_data
            uncompressed_len_sam = sum(sam_lengths)
        compressed_len_sam = len(compressed_samples)

        # Build haplotype indices payload
        if compression_hap_indices == 0x0000:
            compressed_haps = b"".join(struct.pack("<Q", hap) for hap in hap_indices)
        else:
            hap_int_encoder = get_integer_encoder(compression_hap_indices)
            compressed_haps = hap_int_encoder(hap_indices)

        # Build sequence IDs payload
        seq_str_encoding = compression_seq_ids & 0xFF
        if compression_seq_ids == 0x0000:
            compressed_seqids = b"".join(s.encode("ascii") + b"\x00" for s in seq_ids)
            uncompressed_len_seq = len(compressed_seqids)
        else:
            seq_int_encoder = get_integer_encoder(compression_seq_ids)
            seq_int_encoding = (compression_seq_ids >> 8) & 0xFF
            seq_lengths = [len(s.encode("ascii")) for s in seq_ids]
            encoded_seq_lengths = seq_int_encoder(seq_lengths)
            # Add comma delimiter for identity integer encoding
            if seq_int_encoding == INTEGER_ENCODING_IDENTITY and seq_lengths:
                encoded_seq_lengths += b","
            compressed_seq_data = _compress_string_for_bgfa("".join(seq_ids), seq_str_encoding)
            compressed_seqids = encoded_seq_lengths + compressed_seq_data
            uncompressed_len_seq = sum(seq_lengths)
        compressed_len_seq = len(compressed_seqids)

        # Build start positions payload
        if compression_start == 0x0000:
            compressed_starts = b"".join(struct.pack("<Q", s) for s in start_positions)
        else:
            start_int_encoder = get_integer_encoder(compression_start)
            compressed_starts = start_int_encoder(start_positions)

        # Build end positions payload
        if compression_end == 0x0000:
            compressed_ends = b"".join(struct.pack("<Q", e) for e in end_positions)
        else:
            end_int_encoder = get_integer_encoder(compression_end)
            compressed_ends = end_int_encoder(end_positions)

        # Walks payload (segment IDs with orientations) using walks/paths decomposition
        compressed_walks = _encode_walks_payload(walk_segments, self._segment_map, compression_walks)
        uncompressed_len_walk = len(compressed_walks)
        compressed_len_walk = len(compressed_walks)

        logger.debug(
            f"Walks block: samples={compressed_len_sam}/{uncompressed_len_sam}, "
            f"seqs={compressed_len_seq}/{uncompressed_len_seq}, "
            f"walks={compressed_len_walk}/{uncompressed_len_walk} bytes"
        )

        # Write header according to spec: section_id (uint8), record_num, 5 compression codes, 6 length fields
        buffer.write(struct.pack("<B", SECTION_ID_WALKS))
        buffer.write(struct.pack("<H", record_num))
        buffer.write(struct.pack("<H", compression_sample_ids))
        buffer.write(struct.pack("<H", compression_hap_indices))
        buffer.write(struct.pack("<H", compression_seq_ids))
        buffer.write(struct.pack("<H", compression_start))  # shared for start/end positions
        buffer.write(struct.pack("<H", compression_walks))
        buffer.write(struct.pack("<Q", compressed_len_sam))
        buffer.write(struct.pack("<Q", uncompressed_len_sam))
        buffer.write(struct.pack("<Q", compressed_len_seq))
        buffer.write(struct.pack("<Q", uncompressed_len_seq))
        buffer.write(struct.pack("<Q", compressed_len_walk))
        buffer.write(struct.pack("<Q", uncompressed_len_walk))

        # Write payloads
        buffer.write(compressed_samples)
        buffer.write(compressed_haps)
        buffer.write(compressed_seqids)
        buffer.write(compressed_starts)
        buffer.write(compressed_ends)
        buffer.write(compressed_walks)

        bytes_written = (
            1
            + 2
            + 5 * 2  # record_num + 5 compression codes
            + 6 * 8  # 6 length fields
            + compressed_len_sam
            + len(compressed_haps)
            + compressed_len_seq
            + len(compressed_starts)
            + len(compressed_ends)
            + compressed_len_walk
        )
        logger.info(f"Walks block written: {bytes_written} bytes")

    def segments_blocks(
        self,
        block_size: int = 1024,
        compression_method: str = "zstd",
        compression_level: int = 19,
    ) -> bytes:
        # Get segment map
        segment_map = getattr(self._gfa, "_segment_map", {})
        if not segment_map:
            nodes_list = list(self._gfa.nodes())
            segment_map = {name: idx for idx, name in enumerate(sorted(nodes_list))}
            self._gfa._segment_map = segment_map

        # Sort nodes by segment ID
        sorted_items = sorted(segment_map.items(), key=lambda x: x[1])

        # Prepare data for each segment
        segments_data = []
        for node_id, seg_id in sorted_items:
            node_data = dict(self._gfa.nodes(data=True))[node_id]
            sequence = node_data.get("sequence", "*")
            seq_len = len(sequence) if sequence != "*" else 0
            # Each segment entry: segment_id (uint64), sequence_length (uint64), sequence (null-terminated string)
            entry = (
                seg_id.to_bytes(8, byteorder="little", signed=False)
                + seq_len.to_bytes(8, byteorder="little", signed=False)
                + sequence.encode("ascii")
                + b"\x00"
            )
            segments_data.append(entry)

        # Split into blocks
        all_blocks = []
        total_segments = len(segments_data)
        for start in range(0, total_segments, block_size):
            chunk = segments_data[start : start + block_size]
            record_num = len(chunk)
            payload = b"".join(chunk)
            compressed_len = len(payload)
            uncompressed_len = compressed_len  # identity compression
            compression_str = 0x0000  # identity for sequences (and for IDs/lengths)

            # Write block header according to spec: uint16, uint16, uint64, uint64
            header = (
                record_num.to_bytes(2, byteorder="little", signed=False)
                + compression_str.to_bytes(2, byteorder="little", signed=False)
                + compressed_len.to_bytes(8, byteorder="little", signed=False)
                + uncompressed_len.to_bytes(8, byteorder="little", signed=False)
            )
            all_blocks.append(header + payload)

        # Concatenate all blocks
        result = b"".join(all_blocks)
        return result

    def links_blocks(self, block_size: int = 1024) -> bytes:
        from_names = []
        to_names = []
        cigar_lengths = []
        cigars = []

        for u, v, data in self._gfa.edges(data=True):
            from_node = data.get("from_node", u)
            to_node = data.get("to_node", v)
            alignment = data.get("alignment", "*")

            from_names.append(from_node)
            to_names.append(to_node)
            cigar_lengths.append(len(alignment))
            cigars.append(alignment)

        from_bytes = compress_string_list(
            from_names,
            compress_integer_list=compress_integer_list_varint,
            compression_method="none",
        )
        to_bytes = compress_string_list(
            to_names,
            compress_integer_list=compress_integer_list_varint,
            compression_method="none",
        )
        cigar_lengths_bytes = compress_integer_list_varint(cigar_lengths)
        cigars_bytes = compress_string_list(
            cigars,
            compress_integer_list=compress_integer_list_varint,
            compression_method="none",
        )

        result = from_bytes + to_bytes + cigar_lengths_bytes + cigars_bytes

        padding_needed = block_size - len(result) % block_size
        if padding_needed < block_size:
            result += b"\x00" * padding_needed

        return result

    def paths_blocks(self, block_size: int = 1024) -> bytes:
        path_names = []
        segment_lengths = []
        path_ids = []

        for path_id in sorted(self._gfa.paths()):
            path_data = self._gfa.paths()[path_id]
            path_names.append(path_id)
            segments = path_data.get("segments", [])
            segment_lengths.append(len(segments))
            for seg in segments:
                path_ids.append(seg)

        names_bytes = compress_string_list(
            path_names,
            compress_integer_list=compress_integer_list_varint,
            compression_method="none",
        )
        segment_lengths_bytes = compress_integer_list_varint(segment_lengths)
        path_ids_bytes = compress_string_list(
            path_ids,
            compress_integer_list=compress_integer_list_varint,
            compression_method="none",
        )

        result = names_bytes + segment_lengths_bytes + path_ids_bytes

        padding_needed = block_size - len(result) % block_size
        if padding_needed < block_size:
            result += b"\x00" * padding_needed

        return result

    def walks_blocks(self, block_size: int = 1024) -> bytes:
        return b""


def to_bgfa(
    gfa_graph: GFA,
    file=None,
    block_size: int = 1024,
    segment_names_int_encoding: int = INTEGER_ENCODING_IDENTITY,
    segment_names_str_encoding: int = STRING_ENCODING_IDENTITY,
    segments_int_encoding: int = INTEGER_ENCODING_IDENTITY,
    segments_str_encoding: int = STRING_ENCODING_IDENTITY,
    links_fromto_int_encoding: int = INTEGER_ENCODING_IDENTITY,
    links_cigars_int_encoding: int = INTEGER_ENCODING_IDENTITY,
    links_cigars_str_encoding: int = STRING_ENCODING_IDENTITY,
    paths_names_int_encoding: int = INTEGER_ENCODING_IDENTITY,
    paths_names_str_encoding: int = STRING_ENCODING_IDENTITY,
    paths_paths_compression: int = 0x0000,
    paths_cigars_int_encoding: int = INTEGER_ENCODING_IDENTITY,
    paths_cigars_str_encoding: int = STRING_ENCODING_IDENTITY,
    walks_sample_ids_int_encoding: int = INTEGER_ENCODING_IDENTITY,
    walks_sample_ids_str_encoding: int = STRING_ENCODING_IDENTITY,
    walks_hap_indices_int_encoding: int = INTEGER_ENCODING_IDENTITY,
    walks_seq_ids_int_encoding: int = INTEGER_ENCODING_IDENTITY,
    walks_seq_ids_str_encoding: int = STRING_ENCODING_IDENTITY,
    walks_start_int_encoding: int = INTEGER_ENCODING_IDENTITY,
    walks_end_int_encoding: int = INTEGER_ENCODING_IDENTITY,
    walks_walks_compression: int = 0x0000,
    verbose: bool = False,
    debug: bool = False,
    logfile: str | None = None,
) -> bytes:
    """Computes a BGFA representing the GFA graph. If a file is given, then write the BGFA to the file.

    :param gfa_graph: The GFA graph to convert to BGFA format
    :param file: Optional file path to write the BGFA data to
    :param block_size: Block size for BGFA format (default: 1024)
    :param segment_names_int_encoding: Integer encoding for segment name lengths (0x00-0x0B)
    :param segment_names_str_encoding: String encoding for segment names (0x00-0x04)
    :param segments_int_encoding: Integer encoding for segment IDs/lengths (0x00-0x0B)
    :param segments_str_encoding: String encoding for sequences (0x00-0x04)
    :param links_fromto_int_encoding: Integer encoding for link from/to IDs (0x00-0x0B)
    :param links_cigars_int_encoding: Integer encoding for CIGAR lengths (0x00-0x0B)
    :param links_cigars_str_encoding: String encoding for CIGARs (0x00-0x04)
    :param paths_names_int_encoding: Integer encoding for path name lengths (0x00-0x0B)
    :param paths_names_str_encoding: String encoding for path names (0x00-0x04)
    :param paths_paths_compression: Compression code for paths segment lists (uint16)
    :param paths_cigars_int_encoding: Integer encoding for path CIGAR lengths (0x00-0x0B)
    :param paths_cigars_str_encoding: String encoding for path CIGARs (0x00-0x04)
    :param walks_sample_ids_int_encoding: Integer encoding for walk sample ID lengths (0x00-0x0B)
    :param walks_sample_ids_str_encoding: String encoding for walk sample IDs (0x00-0x04)
    :param walks_hap_indices_int_encoding: Integer encoding for haplotype indices (0x00-0x0B)
    :param walks_seq_ids_int_encoding: Integer encoding for walk sequence ID lengths (0x00-0x0B)
    :param walks_seq_ids_str_encoding: String encoding for walk sequence IDs (0x00-0x04)
    :param walks_start_int_encoding: Integer encoding for walk start positions (0x00-0x0B)
    :param walks_end_int_encoding: Integer encoding for walk end positions (0x00-0x0B)
    :param walks_walks_compression: Compression code for walks segment lists (uint16)
    :param verbose: If True, log detailed information
    :param debug: If True, log debug information
    :param logfile: Path to log file (if None and verbose=True, uses a temporary file)

    :return: The BGFA representation of the input GFA graph as bytes, or empty bytes if file is provided
    """
    compression_options = {
        "segment_names_compression_code": make_compression_code(segment_names_int_encoding, segment_names_str_encoding),
        "segments_compression_code": make_compression_code(segments_int_encoding, segments_str_encoding),
        "links_fromto_compression_code": make_compression_code(links_fromto_int_encoding, STRING_ENCODING_IDENTITY),
        "links_cigars_compression_code": make_compression_code(links_cigars_int_encoding, links_cigars_str_encoding),
        "paths_names_compression_code": make_compression_code(paths_names_int_encoding, paths_names_str_encoding),
        "paths_paths_compression_code": paths_paths_compression,
        "paths_cigars_compression_code": make_compression_code(paths_cigars_int_encoding, paths_cigars_str_encoding),
        "walks_sample_ids_compression_code": make_compression_code(
            walks_sample_ids_int_encoding, walks_sample_ids_str_encoding
        ),
        "walks_hap_indices_compression_code": make_compression_code(
            walks_hap_indices_int_encoding, STRING_ENCODING_IDENTITY
        ),
        "walks_seq_ids_compression_code": make_compression_code(walks_seq_ids_int_encoding, walks_seq_ids_str_encoding),
        "walks_start_compression_code": make_compression_code(walks_start_int_encoding, STRING_ENCODING_IDENTITY),
        "walks_end_compression_code": make_compression_code(walks_end_int_encoding, STRING_ENCODING_IDENTITY),
        "walks_walks_compression_code": walks_walks_compression,
    }
    bgfa = BGFAWriter(gfa_graph, block_size, compression_options)
    result = bgfa.to_bgfa(verbose=verbose, debug=debug, logfile=logfile)
    # If file is given, write the BGFA to the file
    if file is not None:
        with open(file, "wb") as f:
            f.write(result)
    return result


def read_bgfa(file_path: str, verbose: bool = False, debug: bool = False, logfile: str | None = None) -> GFA:
    """Read a BGFA file and create the corresponding GFA graph.

    :param file_path: Path to the BGFA file
    :param verbose: If True, log detailed information
    :param logfile: Path to log file (if None and verbose=True, uses a temporary file)
    :return: GFA graph object
    """
    reader = ReaderBGFA()
    return reader.read_bgfa(file_path, verbose=verbose, debug=debug, logfile=logfile)


MEASURE_PARAM_COLUMNS = [
    "param_segment_names_header",
    "param_segment_names_payload_lengths",
    "param_segment_names_payload_names",
    "param_segments_header",
    "param_segments_payload_lengths",
    "param_segments_payload_strings",
    "param_links_header",
    "param_links_payload_from",
    "param_links_payload_to",
    "param_links_payload_cigar_lengths",
    "param_links_payload_cigar",
    "param_paths_header",
    "param_paths_payload_names",
    "param_paths_payload_segment_lengths",
    "param_paths_payload_path_ids",
    "param_paths_payload_cigar_lengths",
    "param_paths_payload_cigar",
    "param_walks_header",
    "param_walks_payload_sample_ids",
    "param_walks_payload_hep_indices",
    "param_walks_payload_sequence_ids",
    "param_walks_payload_start",
    "param_walks_payload_end",
    "param_walks_payload_walks",
]


def get_int_encoding_name(code: int) -> str:
    """Map integer encoding code to name."""
    from pygfa.encoding.enums import IntegerEncoding

    INT_ENCODING_NAMES = {v.value: v.name.lower() for v in IntegerEncoding}
    return INT_ENCODING_NAMES.get(code, f"0x{code:02x}")


def get_str_encoding_name(code: int) -> str:
    """Map string encoding code to name."""
    from pygfa.encoding.enums import StringEncoding

    STR_ENCODING_NAMES = {v.value: v.name.lower() for v in StringEncoding}
    return STR_ENCODING_NAMES.get(code, f"0x{code:02x}")


def measure_bgfa(input_file: str, output_file: str, original_gfa: str = "") -> list[dict]:
    """Analyze BGFA file structure and output block statistics to CSV.

    :param input_file: Path to input BGFA file
    :param output_file: Path to output CSV file
    :param original_gfa: Path to original GFA file
    """
    import csv
    import struct

    with open_gfa_file(input_file, "rb") as f:
        bgfa_data = f.read()

    rows = []
    offset = 0
    filename = os.path.basename(input_file)
    original_gfa_path = original_gfa if original_gfa else ""

    def create_base_row():
        row = {
            "original_gfa": original_gfa_path,
            "filename": filename,
            "block_type": "",
            "block_index": 0,
            "section_id": 0,
            "block_size": "",
            "record_count": 0,
            "offset_start": 0,
            "offset_end": 0,
            "size_bytes": 0,
            "compression_ratio": "",
            "version": "",
            "s_len": "",
            "l_len": "",
            "p_len": "",
            "w_len": "",
            "header_text": "",
            "encoding_high": "",
            "encoding_low": "",
            "compressed_size": 0,
            "uncompressed_size": 0,
        }
        for col in MEASURE_PARAM_COLUMNS:
            row[col] = ""
        return row

    header_start = 0

    version = struct.unpack_from("<H", bgfa_data, offset)[0]
    offset += 2

    offset += 34

    header_text = ""
    while offset < len(bgfa_data) and bgfa_data[offset] != 0:
        header_text += chr(bgfa_data[offset])
        offset += 1
    offset += 1

    header_end = offset

    rows.append(
        {
            "original_gfa": original_gfa_path,
            "filename": filename,
            "block_type": "header",
            "block_index": 0,
            "block_size": "",
            "record_count": "",
            "offset_start": header_start,
            "offset_end": header_end,
            "size_bytes": header_end - header_start,
            "compression_ratio": "",
            "version": version,
            "s_len": "",
            "l_len": "",
            "p_len": "",
            "w_len": "",
            "header_text": header_text,
            "encoding_high": "",
            "encoding_low": "",
            "compressed_size": header_end - header_start,
            "uncompressed_size": header_end - header_start,
        }
    )

    while offset < len(bgfa_data):
        if offset + 1 > len(bgfa_data):
            break

        block_start = offset

        section_id = struct.unpack_from("<B", bgfa_data, offset)[0]
        offset += 1

        if section_id == 1:
            record_num = struct.unpack_from("<H", bgfa_data, offset)[0]
            offset += 2
            compression_names = struct.unpack_from("<H", bgfa_data, offset)[0]
            offset += 2
            compressed_len = struct.unpack_from("<Q", bgfa_data, offset)[0]
            offset += 8
            uncompressed_len = struct.unpack_from("<Q", bgfa_data, offset)[0]
            offset += 8

            if offset + compressed_len > len(bgfa_data):
                raise ValueError(f"BGFA file is too short: cannot read segment names payload at offset {offset}")

            offset += compressed_len
            block_end = offset

            ratio = compressed_len / uncompressed_len if uncompressed_len > 0 else 0

            int_encoding = (compression_names >> 8) & 0xFF
            str_encoding = compression_names & 0xFF

            row = create_base_row()
            row["block_type"] = "segment_names"
            row["section_id"] = section_id
            row["record_count"] = record_num
            row["offset_start"] = block_start
            row["offset_end"] = block_end
            row["size_bytes"] = block_end - block_start
            row["compression_ratio"] = f"{ratio:.4f}"
            row["encoding_high"] = f"0x{int_encoding:02x}"
            row["encoding_low"] = f"0x{str_encoding:02x}"
            row["compressed_size"] = compressed_len
            row["uncompressed_size"] = uncompressed_len
            row["param_segment_names_payload_lengths"] = get_int_encoding_name(int_encoding)
            row["param_segment_names_payload_names"] = get_str_encoding_name(str_encoding)
            rows.append(row)

        elif section_id == 2:
            record_num = struct.unpack_from("<H", bgfa_data, offset)[0]
            offset += 2
            compression = struct.unpack_from("<H", bgfa_data, offset)[0]
            offset += 2
            compressed_len = struct.unpack_from("<Q", bgfa_data, offset)[0]
            offset += 8
            uncompressed_len = struct.unpack_from("<Q", bgfa_data, offset)[0]
            offset += 8

            offset += compressed_len
            block_end = offset

            ratio = compressed_len / uncompressed_len if uncompressed_len > 0 else 0
            int_encoding = (compression >> 8) & 0xFF
            str_encoding = compression & 0xFF

            row = create_base_row()
            row["block_type"] = "segments"
            row["section_id"] = section_id
            row["record_count"] = record_num
            row["offset_start"] = block_start
            row["offset_end"] = block_end
            row["size_bytes"] = block_end - block_start
            row["compression_ratio"] = f"{ratio:.4f}"
            row["encoding_high"] = f"0x{int_encoding:02x}"
            row["encoding_low"] = f"0x{str_encoding:02x}"
            row["compressed_size"] = compressed_len
            row["uncompressed_size"] = uncompressed_len
            rows.append(row)

        elif section_id == 3:
            record_num = struct.unpack_from("<H", bgfa_data, offset)[0]
            offset += 2
            offset += 2
            offset += 2
            compressed_len = struct.unpack_from("<Q", bgfa_data, offset)[0]
            offset += 8
            uncompressed_len = struct.unpack_from("<Q", bgfa_data, offset)[0]
            offset += 8

            offset += compressed_len
            block_end = offset

            ratio = compressed_len / uncompressed_len if uncompressed_len > 0 else 0

            row = create_base_row()
            row["block_type"] = "links"
            row["section_id"] = section_id
            row["record_count"] = record_num
            row["offset_start"] = block_start
            row["offset_end"] = block_end
            row["size_bytes"] = block_end - block_start
            row["compression_ratio"] = f"{ratio:.4f}"
            row["compressed_size"] = compressed_len
            row["uncompressed_size"] = uncompressed_len
            rows.append(row)

        elif section_id == 4:
            record_num = struct.unpack_from("<H", bgfa_data, offset)[0]
            offset += 2
            offset += 6
            offset += 16
            compressed_len_cigar = struct.unpack_from("<Q", bgfa_data, offset)[0]
            offset += 8
            offset += 8
            compressed_len_name = struct.unpack_from("<Q", bgfa_data, offset)[0]
            offset += 8
            offset += 8

            offset += compressed_len_cigar + compressed_len_name
            block_end = offset

            total_compressed = compressed_len_cigar + compressed_len_name
            ratio = total_compressed / total_compressed if total_compressed > 0 else 0

            row = create_base_row()
            row["block_type"] = "paths"
            row["section_id"] = section_id
            row["record_count"] = record_num
            row["offset_start"] = block_start
            row["offset_end"] = block_end
            row["size_bytes"] = block_end - block_start
            row["compression_ratio"] = f"{ratio:.4f}"
            row["compressed_size"] = total_compressed
            row["uncompressed_size"] = total_compressed
            rows.append(row)

        elif section_id == 5:
            record_num = struct.unpack_from("<H", bgfa_data, offset)[0]
            offset += 2
            offset += 10
            offset += 48

            block_end = offset + 100

            row = create_base_row()
            row["block_type"] = "walks"
            row["section_id"] = section_id
            row["record_count"] = record_num
            row["offset_start"] = block_start
            row["size_bytes"] = 0
            rows.append(row)

        else:
            break

    fieldnames = [
        "original_gfa",
        "filename",
        "block_type",
        "section_id",
        "block_index",
        "block_size",
        "record_count",
        "offset_start",
        "offset_end",
        "size_bytes",
        "compression_ratio",
        "version",
        "s_len",
        "l_len",
        "p_len",
        "w_len",
        "header_text",
        "encoding_high",
        "encoding_low",
        "compressed_size",
        "uncompressed_size",
    ] + MEASURE_PARAM_COLUMNS

    with open(output_file, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return rows
