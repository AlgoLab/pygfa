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
from typing import TYPE_CHECKING

from pygfa.gfa import GFA
from pygfa.graph_element import node, edge as ge

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
    compress_string_gzip,
    compress_string_list,
    compress_string_list_huffman,
    compress_string_lzma,
    compress_string_none,
    compress_string_zstd,
)

import compression.zstd as z

__all__ = ["BGFAWriter", "ReaderBGFA", "to_bgfa", "read_bgfa"]


# =============================================================================
# Decompression functions for reading BGFA files
# =============================================================================


def decompress_string_identity(data: bytes) -> bytes:
    """Identity decompression (no-op)."""
    return data


def decompress_string_zstd(data: bytes) -> bytes:
    """Decompress zstd-compressed data."""
    return z.decompress(data)


def decompress_string_gzip(data: bytes) -> bytes:
    """Decompress gzip-compressed data."""
    return gzip.decompress(data)


def decompress_string_lzma(data: bytes) -> bytes:
    """Decompress lzma-compressed data."""
    return lzma.decompress(data)


def decompress_string_huffman(data: bytes, num_strings: int) -> tuple[list[bytes], int]:
    """Decompress Huffman-encoded string list.

    The format is:
    - uint32: total uncompressed data length
    - uint32: codebook length
    - codebook bytes (encoded with integer list encoding)
    - uint32: compressed bitstream length
    - lengths of each string (encoded with integer list encoding)
    - compressed bitstream bytes

    :param data: Compressed data
    :param num_strings: Number of strings to decode
    :return: Tuple of (list of decoded byte strings, bytes consumed)
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

    # Read compressed bitstream length
    bitstream_len = struct.unpack_from("<I", data, pos)[0]
    pos += 4

    # Decode string lengths using varint
    lengths, lengths_consumed = decode_integer_list_varint(data[pos:], num_strings)
    pos += lengths_consumed

    # Read compressed bitstream
    bitstream = data[pos : pos + bitstream_len]
    pos += bitstream_len

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

    # Split decoded data into strings using lengths
    strings = []
    data_pos = 0
    for length in lengths:
        if data_pos + length <= len(decoded_data):
            strings.append(bytes(decoded_data[data_pos : data_pos + length]))
            data_pos += length
        else:
            break

    return strings, pos


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
                result.append(
                    data[data_idx] | (data[data_idx + 1] << 8) | (data[data_idx + 2] << 16)
                )
                data_idx += 3
        else:
            # 4 bytes
            if data_idx + 4 <= len(data):
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
    # Huffman requires special handling (decompress_string_huffman)
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


class ReaderBGFA:
    def __init__(self):
        pass

    def read_bgfa(
        self,
        file_path: str,
        verbose: bool = False,
        debug: bool = False,
        logfile: str = None,
    ) -> "GFA":
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
                # Create a temporary log file
                temp_log = tempfile.NamedTemporaryFile(
                    mode="w", delete=False, suffix=".log"
                )
                logfile = temp_log.name
                temp_log.close()
                print(f"Logging to temporary file: {logfile}")
        else:
            # If we're not logging, use a dummy logfile
            if os.name == "nt":  # Windows
                logfile = "NUL"
            else:  # Unix-like
                logfile = "/dev/null"

        # Clear any existing handlers
        logging.getLogger().handlers.clear()

        # Create formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        handlers = []

        # Only add file handler if we're actually logging to a file

        if logfile != "/dev/null" and logfile != "NUL":
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

        with open(file_path, "rb") as f:
            bgfa_data = f.read()

        gfa = GFA()

        # Parse header
        header = self._parse_header(bgfa_data)
        # Store header information in the GFA object
        gfa._header_info = header.copy()
        logger.info(
            f"Header parsed: version={header['version']}, s_len={header['s_len']}, "
            f"l_len={header['l_len']}, p_len={header['p_len']}, w_len={header['w_len']}"
        )
        logger.debug(f"Full header: {header}")
        # Parse segment names
        offset = header["header_size"]
        segment_names = []
        num_blocks = math.ceil(header["s_len"] / header["block_size"])
        logger.info(f"Parsing {num_blocks} segment name blocks")
        for i in range(num_blocks):
            segment_names_block, read_bytes = self._parse_segment_names_block(
                bgfa_data, offset
            )
            offset += read_bytes
            segment_names.extend(segment_names_block)
            logger.info(
                f"Parsed segment names block {i+1}: {len(segment_names_block)} names"
            )
        logger.info(f"Total segment names: {len(segment_names)}")
        logger.debug(f"First 5 segment names: {segment_names[:5]}")

        # Parse segments
        num_blocks = math.ceil(header["s_len"] / header["block_size"])
        logger.info(f"Parsing {num_blocks} segment blocks")
        for i in range(num_blocks):
            segment_block, read_bytes = self._parse_segments_block(bgfa_data, offset)
            offset += read_bytes
            logger.info(f"Parsed segments block {i+1}: {len(segment_block)} segments")
            # Add nodes to GFA graph with segment IDs
            for segment_id, segment_data in segment_block.items():
                # Get node name from segment_names list (0-based index)
                if 0 <= segment_id < len(segment_names):
                    node_name = segment_names[segment_id]
                else:
                    node_name = f"segment_{segment_id}"

                n = node.Node(
                    node_name,
                    segment_data["sequence"],
                    segment_data["length"],
                    opt_fields={},
                )
                gfa.add_node(n)
                # The GFA class has a _segment_map attribute
                gfa._segment_map[node_name] = segment_id
                if i == 0 and segment_id < 5:  # Log first few segments
                    logger.debug(
                        f"Added segment {segment_id}: {node_name}, length={segment_data['length']}"
                    )
                elif i == 0 and segment_id == 5:
                    logger.debug("... (remaining segments logged at debug level)")

        # Parse links
        num_blocks = math.ceil(header["l_len"] / header["block_size"])
        logger.info(f"Parsing {num_blocks} link blocks")
        for i in range(num_blocks):
            links, read_bytes = self._parse_links_block(
                bgfa_data, segment_names, offset
            )
            offset += read_bytes
            logger.info(f"Parsed links block {i+1}: {len(links)} links")

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
                        is_dovetail=True,
                    )
                )
            if verbose:
                logger.info(f"Added {len(links)} links from block {i+1}")
                if i == 0 and links:
                    logger.debug(f"First link: {links[0]}")

        # TODO: Parse paths
        # TODO: Parse walks

        logger.info(
            f"BGFA reading complete. Graph has {len(gfa.nodes())} nodes and {len(gfa.edges())} edges"
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
        # Read block_size (uint16)
        block_size = struct.unpack_from("<H", bgfa_data, offset)[0]
        offset += 2

        # Read counts (uint64)
        s_len = struct.unpack_from("<Q", bgfa_data, offset)[0]
        offset += 8
        l_len = struct.unpack_from("<Q", bgfa_data, offset)[0]
        offset += 8
        p_len = struct.unpack_from("<Q", bgfa_data, offset)[0]
        offset += 8
        w_len = struct.unpack_from("<Q", bgfa_data, offset)[0]
        offset += 8

        # Read header text (C string)
        header_text = ""
        while offset < len(bgfa_data) and bgfa_data[offset] != 0:
            header_text += chr(bgfa_data[offset])
            offset += 1
        offset += 1  # Skip null terminator

        return {
            "version": version,
            "s_len": s_len,
            "l_len": l_len,
            "p_len": p_len,
            "w_len": w_len,
            "block_size": block_size,
            "header_text": header_text,
            "header_size": offset,
        }

    def _parse_segment_names_block(
        self, bgfa_data: bytes, offset: int
    ) -> tuple[list[str], int]:
        """Parse segment names from BGFA data.

        Supports all compression methods defined in the BGFA spec:
        - Integer encoding (high byte): identity, varint, fixed16, delta, elias_gamma,
          elias_omega, golomb, rice, streamvbyte, vbyte, fixed32, fixed64
        - String encoding (low byte): identity, zstd, gzip, lzma, huffman

        :param bgfa_data: Binary BGFA data
        :param offset: number of bytes to skip
        :return: (List of segment names, number of bytes read)
        """
        segment_names = []
        initial_offset = offset

        # Read block header - new order: uint16 fields first
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
            f"compression={compression_names:#06x} (int={int_encoding:#04x}, str={str_encoding:#04x}), "
            f"compressed_len={compressed_len}, uncompressed_len={uncompressed_len}"
        )

        # Handle identity encoding (0x0000): null-terminated strings
        if compression_names == 0x0000:
            pos = 0
            for _ in range(record_num):
                name_bytes = bytearray()
                while pos < len(payload) and payload[pos] != 0:
                    name_bytes.append(payload[pos])
                    pos += 1
                if pos >= len(payload):
                    raise ValueError("Missing null terminator in segment name")
                pos += 1  # skip null terminator
                name = name_bytes.decode("ascii")
                segment_names.append(name)

            # Verify length
            if pos != uncompressed_len:
                raise ValueError(
                    f"Segment names length mismatch: expected {uncompressed_len} bytes, got {pos}"
                )
            return segment_names, offset - initial_offset

        # Handle Huffman encoding specially (0x??04)
        if str_encoding == STRING_ENCODING_HUFFMAN:
            strings, _ = decompress_string_huffman(payload, record_num)
            segment_names = [s.decode("ascii") for s in strings]
            return segment_names, offset - initial_offset

        # For other encodings, the payload format is:
        # 1. Encoded lengths of strings (using integer encoding)
        # 2. Compressed concatenated strings (using string encoding)

        # Get the appropriate decoders
        int_decoder = get_integer_decoder(compression_names)
        str_decoder = get_string_decoder(compression_names)

        # The payload contains: [encoded_lengths][compressed_strings]
        # We need to decode lengths first to know how many bytes they take

        # Decode string lengths from the payload
        lengths, lengths_consumed = int_decoder(payload, record_num)

        if len(lengths) != record_num:
            raise ValueError(
                f"Length count mismatch: expected {record_num}, got {len(lengths)}"
            )

        # Get the compressed string data (rest of payload after lengths)
        compressed_strings = payload[lengths_consumed:]

        # Decompress the concatenated strings
        if str_encoding == STRING_ENCODING_IDENTITY:
            decompressed_strings = compressed_strings
        else:
            decompressed_strings = str_decoder(compressed_strings)

        # Split the decompressed data into individual names using lengths
        pos = 0
        for length in lengths:
            if pos + length > len(decompressed_strings):
                raise ValueError(
                    f"Decompressed data too short: need {pos + length} bytes, "
                    f"have {len(decompressed_strings)}"
                )
            name = decompressed_strings[pos : pos + length].decode("ascii")
            segment_names.append(name)
            pos += length

        logger.debug(f"Decoded {len(segment_names)} segment names")

        return segment_names, offset - initial_offset

    def _parse_segments_block(
        self, bgfa_data: bytes, start_offset: int
    ) -> tuple[dict, int]:
        """Parse segments from BGFA data.

        :param bgfa_data: Binary BGFA data
        :param header: Parsed header information
        :param segment_names: List of segment names
        :param start_offset: Offset where segments blocks start
        :return: (Dictionary mapping segment names to segment data, number of bytes read)
        """
        initial_offset = start_offset
        offset = start_offset
        segments = {}

        # Read block header - new order: uint16 fields first
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

        # For now, assume simple format without compression
        # In a real implementation, we would decompress based on compression_str
        pos = 0
        for _ in range(record_num):
            # Read segment ID (uint64) - this is the index in the segment_names list
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

            segments[segment_id] = {
                "sequence": sequence,
                "length": sequence_length,
            }

        return segments, offset - initial_offset

    def _parse_links_block(
        self, bgfa_data: bytes, segment_names: list, start_offset: int
    ) -> tuple[list, int]:
        """Parse links from BGFA data.

        :param bgfa_data: Binary BGFA data
        :param header: Parsed header information
        :param segment_names: List of segment names
        :param start_offset: Offset where links blocks start
        :return: (List of link dictionaries, offset after reading all links blocks)
        """

        offset = start_offset
        links = []

        # Read block header - new order: uint16 fields first
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

        # For now, assume simple format without compression
        pos = 0
        for _ in range(record_num):
            # Read from node (uint64) - this is the index in the segment_names list
            from_node_id = struct.unpack_from("<Q", link_data, pos)[0]
            pos += 8
            # Read to node (uint64) - this is the index in the segment_names list
            to_node_id = struct.unpack_from("<Q", link_data, pos)[0]
            pos += 8
            # Read cigar string (null-terminated string)
            cigar_bytes = bytearray()
            while pos < len(link_data) and link_data[pos] != 0:
                cigar_bytes.append(link_data[pos])
                pos += 1
            pos += 1  # Skip null terminator
            cigar = cigar_bytes.decode("ascii")

            # Convert node IDs to names using segment_names list
            from_name = (
                segment_names[from_node_id - 1]
                if 0 < from_node_id <= len(segment_names)
                else f"node_{from_node_id}"
            )
            to_name = (
                segment_names[to_node_id - 1]
                if 0 < to_node_id <= len(segment_names)
                else f"node_{to_node_id}"
            )
            orientation_from = "+"
            orientation_to = "+"

            links.append(
                {
                    "from_node": from_name,
                    "from_orn": orientation_from,
                    "to_node": to_name,
                    "to_orn": orientation_to,
                    "alignment": cigar,
                }
            )

        return links, offset

    def _parse_paths_blocks(
        self, bgfa_data: bytes, header: dict, segment_names: list, start_offset: int
    ) -> tuple[list, int]:
        """Parse a paths block from BGFA data.

        :param bgfa_data: Binary BGFA data
        :param header: Parsed header information
        :param start_offset: Offset where the paths block start
        :return: (List of paths dictionaries, number of bytes read)
        """
        offset = start_offset

        # Read block header
        record_num = int.from_bytes(
            bgfa_data[offset : offset + 2], byteorder="little", signed=False
        )
        offset += 2
        compressed_len_cigar = int.from_bytes(
            bgfa_data[offset : offset + 8], byteorder="little", signed=False
        )
        offset += 8
        uncompressed_len_cigar = int.from_bytes(
            bgfa_data[offset : offset + 8], byteorder="little", signed=False
        )
        offset += 8
        compressed_len_name = int.from_bytes(
            bgfa_data[offset : offset + 8], byteorder="little", signed=False
        )
        offset += 8
        uncompressed_len_name = int.from_bytes(
            bgfa_data[offset : offset + 8], byteorder="little", signed=False
        )
        offset += 8
        compression_path_names = int.from_bytes(
            bgfa_data[offset : offset + 2], byteorder="little", signed=False
        )
        offset += 2
        compression_paths = int.from_bytes(
            bgfa_data[offset : offset + 2], byteorder="little", signed=False
        )
        offset += 2
        compression_cigars = struct.unpack_from("<H", bgfa_data, offset)[0]
        offset += 2

        # Skip the payload for now
        total_payload_len = compressed_len_name + compressed_len_cigar
        offset += total_payload_len

        # Return empty list for paths
        paths = []
        return paths, offset - start_offset


class BGFAWriter:
    def __init__(
        self, gfa_graph: GFA, block_size: int = 1024, compression_options: dict = None
    ):
        self._gfa = gfa_graph
        self._compression_options = compression_options
        self._block_size = block_size

    def to_bgfa(
        self,
        verbose: bool = False,
        debug: bool = False,
        logfile: str = None,
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
                # Create a temporary log file
                temp_log = tempfile.NamedTemporaryFile(
                    mode="w", delete=False, suffix=".log"
                )
                logfile = temp_log.name
                temp_log.close()
                print(f"Logging to temporary file: {logfile}")
        else:
            # If we're not logging, use a dummy logfile
            if os.name == "nt":  # Windows
                logfile = "NUL"
            else:  # Unix-like
                logfile = "/dev/null"

        # Clear any existing handlers
        logging.getLogger().handlers.clear()

        # Create formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        handlers = []

        # Only add file handler if we're actually logging to a file

        if logfile != "/dev/null" and logfile != "NUL":
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

        # Compute counts
        s_len = len(self._gfa.nodes())
        l_len = len(self._gfa.edges())
        p_len = len(self._gfa.paths())
        w_len = len(self._gfa.walks())

        # Write the header
        logger.info(
            f"Writing header: S_len={s_len}, L_len={l_len}, P_len={p_len}, W_len={w_len}"
        )
        self._write_header(
            buffer,
            s_len,
            l_len,
            p_len,
            w_len,
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
        logger.info(
            f"Writing {total_names} segment names in blocks of size {block_size}"
        )
        logger.debug(
            f"Segment names: {segment_names[:5] if len(segment_names) > 5 else segment_names}"
        )
        while offset < total_names:
            chunk = segment_names[offset : min(offset + block_size, total_names)]
            block_num = offset // block_size + 1
            logger.info(f"Writing segment names block {block_num}: {len(chunk)} names")
            logger.debug(
                f"Block {block_num} contains: {chunk[:3] if len(chunk) > 3 else chunk}"
            )
            # Get compression code from options (default: 0x0000 = identity)
            segment_names_compression_code = self._compression_options.get(
                "segment_names_compression_code", 0x0000
            )
            self._write_segment_names_block(
                buffer, chunk, compression_code=segment_names_compression_code
            )
            offset += len(chunk)

        # Write segments blocks
        logger.debug(f"Writing segment blocks")
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
                logger.debug(
                    f"First segment in block {block_num}: name={name}, id={seg_id}"
                )
            # Get compression code from options (default: 0x0000 = identity)
            segments_compression_code = self._compression_options.get(
                "segments_compression_code", 0x0000
            )
            self._write_segments_block(
                buffer,
                chunk,
                compression_code=segments_compression_code,
            )
            offset += len(chunk)

        # Write links blocks
        edges = list(self._gfa.edges(data=True, keys=True))
        offset = 0
        total_links = len(edges)
        logger.info(f"Writing {total_links} links in blocks of size {block_size}")
        while offset < total_links:
            chunk = edges[offset : offset + block_size]
            block_num = offset // block_size + 1
            logger.info(f"Writing links block {block_num}: {len(chunk)} links")
            if len(chunk) > 0:
                # chunk[0] is (u, v, key, data)
                u, v, key, data = chunk[0]
                from_node = data.get("from_node", u)
                to_node = data.get("to_node", v)
                logger.debug(
                    f"First link in block {block_num}: from={from_node}, to={to_node}"
                )
            # Get compression codes from options (default: 0x0000 = identity)
            links_fromto_compression = self._compression_options.get(
                "links_fromto_compression_code", 0x0000
            )
            links_cigars_compression = self._compression_options.get(
                "links_cigars_compression_code", 0x0000
            )
            self._write_links_block(
                buffer,
                chunk,
                compression_fromto=links_fromto_compression,
                compression_cigars=links_cigars_compression,
            )
            offset += block_size

        # Write paths blocks
        paths = list(self._gfa.paths_iter(data=True))
        offset = 0
        total_paths = len(paths)
        logger.info(f"Writing {total_paths} paths in blocks of size {block_size}")
        while offset < total_paths:
            chunk = paths[offset : offset + block_size]
            block_num = offset // block_size + 1
            logger.info(f"Writing paths block {block_num}: {len(chunk)} paths")
            # Get compression codes from options (default: 0x0000 = identity)
            paths_names_compression = self._compression_options.get(
                "paths_names_compression_code", 0x0000
            )
            paths_paths_compression = self._compression_options.get(
                "paths_paths_compression_code", 0x0000
            )
            paths_cigars_compression = self._compression_options.get(
                "paths_cigars_compression_code", 0x0000
            )
            self._write_paths_block(
                buffer,
                chunk,
                compression_path_names=paths_names_compression,
                compression_paths=paths_paths_compression,
                compression_cigars=paths_cigars_compression,
            )
            offset += block_size

        # Write walks blocks
        walks = list(self._gfa.walks_iter(data=True))
        offset = 0
        total_walks = len(walks)
        logger.info(f"Writing {total_walks} walks in blocks of size {block_size}")
        while offset < total_walks:
            chunk = walks[offset : offset + block_size]
            block_num = offset // block_size + 1
            logger.info(f"Writing walks block {block_num}: {len(chunk)} walks")
            # Get compression codes from options (default: 0x0000 = identity)
            walks_sample_ids_compression = self._compression_options.get(
                "walks_sample_ids_compression_code", 0x0000
            )
            walks_hap_indices_compression = self._compression_options.get(
                "walks_hap_indices_compression_code", 0x0000
            )
            walks_seq_ids_compression = self._compression_options.get(
                "walks_seq_ids_compression_code", 0x0000
            )
            walks_start_compression = self._compression_options.get(
                "walks_start_compression_code", 0x0000
            )
            walks_end_compression = self._compression_options.get(
                "walks_end_compression_code", 0x0000
            )
            walks_walks_compression = self._compression_options.get(
                "walks_walks_compression_code", 0x0000
            )
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
            offset += block_size

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
        for u, v, key, data in self._gfa.edges(data=True, keys=True):
            if data.get("is_dovetail", False):
                alignment = data.get("alignment", "*")
                total += 8 + 8 + len(alignment) + 1  # from_id + to_id + cigar + null
        return total

    def _write_header(
        self,
        buffer,
        s_len,
        l_len,
        p_len,
        w_len,
        block_size,
    ):
        """Write BGFA header in binary format."""
        # Write version (uint16)
        buffer.write(struct.pack("<H", 1))
        # Write block_size (uint16)
        buffer.write(struct.pack("<H", block_size))
        # Write counts (uint64)
        buffer.write(struct.pack("<Q", s_len))
        buffer.write(struct.pack("<Q", l_len))
        buffer.write(struct.pack("<Q", p_len))
        buffer.write(struct.pack("<Q", w_len))

        # Write header text (C string)
        header_text = "H\tVN:Z:1.0"
        buffer.write(header_text.encode("ascii"))
        buffer.write(b"\x00")  # null terminator

    def header(self, block_size: int = 1024) -> bytes:
        """Create placeholder header with zeros."""
        buffer = io.BytesIO()
        self._write_header(buffer, 0, 0, 0, 0, block_size)
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
        :param compression_code: uint16 compression code (high byte=integer encoding for lengths,
                                 low byte=string encoding for names). Default 0x0000 (identity).
                                 See BGFA spec for encoding strategies:
                                 - Integer: 0x00=identity, 0x01=varint, 0x02=fixed16, etc.
                                 - String: 0x00=identity, 0x01=zstd, 0x02=gzip, 0x03=lzma, 0x04=huffman
        :return: Number of bytes written
        """
        record_num = len(to_write)
        logger.info(f"Writing segment names block with {record_num} names")
        logger.debug(f"Compression code: {compression_code:#06x}")

        # Extract encoding strategies from compression code
        int_encoding = (compression_code >> 8) & 0xFF
        str_encoding = compression_code & 0xFF
        logger.debug(
            f"Integer encoding: {int_encoding:#04x}, String encoding: {str_encoding:#04x}"
        )

        # Build uncompressed payload: names as null-terminated strings
        uncompressed_payload = b"".join(
            name.encode("ascii") + b"\x00" for name in to_write
        )
        uncompressed_len = len(uncompressed_payload)

        # Apply string compression based on compression code
        string_encoder = get_string_encoder(compression_code)
        if string_encoder is not None and str_encoding != STRING_ENCODING_IDENTITY:
            try:
                # Concatenate all names for compression
                concatenated = "\x00".join(to_write) + "\x00"
                compressed_payload = string_encoder(concatenated)
                logger.debug(
                    f"Applied string compression {str_encoding:#04x}: "
                    f"{uncompressed_len} -> {len(compressed_payload)} bytes"
                )
            except Exception as e:
                logger.warning(f"Compression failed, falling back to identity: {e}")
                compressed_payload = uncompressed_payload
                compression_code = 0x0000  # Reset to identity
        else:
            compressed_payload = uncompressed_payload

        compressed_len = len(compressed_payload)

        logger.debug(
            f"Segment names block payload: compressed_len={compressed_len}, "
            f"uncompressed_len={uncompressed_len}, compression={compression_code:#06x}"
        )

        # Write block header according to spec: uint16, uint16, uint64, uint64
        buffer.write(struct.pack("<H", record_num))
        buffer.write(struct.pack("<H", compression_code))
        buffer.write(struct.pack("<Q", compressed_len))
        buffer.write(struct.pack("<Q", uncompressed_len))
        buffer.write(compressed_payload)

        bytes_written = 2 + 2 + 8 + 8 + compressed_len
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
        :param compression_code: uint16 compression code (high byte=integer encoding,
                                 low byte=string encoding). Default 0x0000 (identity).
                                 See BGFA spec for encoding strategies:
                                 - Integer: 0x00=identity, 0x01=varint, 0x02=fixed16, etc.
                                 - String: 0x00=identity, 0x01=zstd, 0x02=gzip, 0x03=lzma, 0x04=huffman
        """
        record_num = len(chunk)
        logger.info(f"Writing segments block with {record_num} segments")
        logger.debug(f"Compression code: {compression_code:#06x}")

        # Extract encoding strategies from compression code
        int_encoding = (compression_code >> 8) & 0xFF
        str_encoding = compression_code & 0xFF
        logger.debug(
            f"Integer encoding: {int_encoding:#04x}, String encoding: {str_encoding:#04x}"
        )

        # Collect segment data
        payload_parts = []
        sequences = []
        for i, (name, seg_id) in enumerate(chunk):
            node_data = dict(self._gfa.nodes(data=True))[name]
            sequence = node_data.get("sequence", "*")
            seq_len = len(sequence) if sequence != "*" else 0
            sequences.append(sequence)

            if i < 3:
                logger.debug(
                    f"Segment {i}: name={name}, seg_id={seg_id}, seq_len={seq_len}"
                )
            elif i == 3:
                logger.debug("... (remaining segments omitted)")

            # Write segment_id (uint64), sequence_length (uint64), sequence (null-terminated)
            payload_parts.append(struct.pack("<Q", seg_id))
            payload_parts.append(struct.pack("<Q", seq_len))
            payload_parts.append(sequence.encode("ascii") + b"\x00")

        # Build uncompressed payload
        uncompressed_payload = b"".join(payload_parts)
        uncompressed_len = len(uncompressed_payload)

        # Apply string compression based on compression code
        string_encoder = get_string_encoder(compression_code)
        if string_encoder is not None and str_encoding != STRING_ENCODING_IDENTITY:
            try:
                # Concatenate all sequences for compression
                concatenated = "".join(sequences)
                compressed_payload = string_encoder(concatenated)
                logger.debug(
                    f"Applied string compression {str_encoding:#04x}: "
                    f"{uncompressed_len} -> {len(compressed_payload)} bytes"
                )
            except Exception as e:
                logger.warning(f"Compression failed, falling back to identity: {e}")
                compressed_payload = uncompressed_payload
                compression_code = 0x0000  # Reset to identity
        else:
            compressed_payload = uncompressed_payload

        compressed_len = len(compressed_payload)

        logger.debug(
            f"Segments block payload: compressed_len={compressed_len}, "
            f"uncompressed_len={uncompressed_len}, compression={compression_code:#06x}"
        )

        # Write header
        buffer.write(struct.pack("<H", record_num))
        buffer.write(struct.pack("<H", compression_code))
        buffer.write(struct.pack("<Q", compressed_len))
        buffer.write(struct.pack("<Q", uncompressed_len))

        buffer.write(compressed_payload)

        logger.info(f"Segments block written: {20 + compressed_len} bytes")

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
        logger.debug(
            f"Compression codes: fromto={compression_fromto:#06x}, "
            f"cigars={compression_cigars:#06x}"
        )

        # Collect link data
        from_ids = []
        to_ids = []
        cigars = []

        for u, v, key, data in chunk:
            # Get from and to IDs from segment_names
            from_name = data.get("from_node", u)
            to_name = data.get("to_node", v)
            alignment = data.get("alignment", "*")

            # Find segment IDs using the segment_map created in to_bgfa
            # Use 1-based indices to match what the reader expects
            from_id = self._segment_map.get(from_name, -1) + 1
            to_id = self._segment_map.get(to_name, -1) + 1

            from_ids.append(from_id)
            to_ids.append(to_id)
            cigars.append(alignment)

        if record_num > 0:
            logger.debug(
                f"First link: from_id={from_ids[0]}, to_id={to_ids[0]}, "
                f"cigar={cigars[0]}"
            )

        # Build uncompressed payload
        payload_parts = []
        for from_id, to_id, cigar in zip(from_ids, to_ids, cigars):
            payload_parts.append(struct.pack("<Q", from_id))
            payload_parts.append(struct.pack("<Q", to_id))
            payload_parts.append(cigar.encode("ascii") + b"\x00")

        uncompressed_payload = b"".join(payload_parts)
        uncompressed_len = len(uncompressed_payload)

        # Apply compression for from/to fields (integer encoding)
        fromto_encoding = (compression_fromto >> 8) & 0xFF
        if fromto_encoding != INTEGER_ENCODING_IDENTITY:
            int_encoder = get_integer_encoder(compression_fromto)
            try:
                # Interleave from and to IDs for compression
                interleaved_ids = []
                for f, t in zip(from_ids, to_ids):
                    interleaved_ids.extend([f, t])
                compressed_ids = int_encoder(interleaved_ids)
                logger.debug(
                    f"Applied integer compression {fromto_encoding:#04x} to from/to IDs"
                )
            except Exception as e:
                logger.warning(f"Integer compression failed, using identity: {e}")
                compression_fromto = 0x0000

        # Apply compression for CIGAR strings
        cigar_str_encoding = compression_cigars & 0xFF
        if cigar_str_encoding != STRING_ENCODING_IDENTITY:
            string_encoder = get_string_encoder(compression_cigars)
            if string_encoder is not None:
                try:
                    concatenated_cigars = "\x00".join(cigars) + "\x00"
                    compressed_cigars = string_encoder(concatenated_cigars)
                    logger.debug(
                        f"Applied string compression {cigar_str_encoding:#04x} to CIGARs"
                    )
                except Exception as e:
                    logger.warning(f"CIGAR compression failed, using identity: {e}")
                    compression_cigars = 0x0000

        # For now, use uncompressed payload (full compression implementation TODO)
        compressed_payload = uncompressed_payload
        compressed_len = len(compressed_payload)

        logger.debug(
            f"Links block payload: compressed_len={compressed_len}, "
            f"uncompressed_len={uncompressed_len}"
        )

        # Write header according to spec: record_num, compression_fromto, compression_cigars,
        # compressed_len, uncompressed_len
        buffer.write(struct.pack("<H", record_num))
        buffer.write(struct.pack("<H", compression_fromto))
        buffer.write(struct.pack("<H", compression_cigars))
        buffer.write(struct.pack("<Q", compressed_len))
        buffer.write(struct.pack("<Q", uncompressed_len))
        buffer.write(compressed_payload)

        bytes_written = 2 + 2 + 2 + 8 + 8 + compressed_len
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
            logger.debug(
                f"First path: name={path_names[0]}, "
                f"segments={len(path_segments[0]) if path_segments else 0}"
            )

        # Build uncompressed payloads
        # Path names payload
        names_payload = b"".join(name.encode("ascii") + b"\x00" for name in path_names)
        uncompressed_len_name = len(names_payload)

        # Paths payload (segment IDs with orientations)
        # For now, simple format: each path is list of segment references
        paths_payload_parts = []
        for segments in path_segments:
            for seg in segments:
                if isinstance(seg, str):
                    # Parse orientation from segment string (e.g., "seg1+")
                    if seg.endswith("+") or seg.endswith("-"):
                        seg_name = seg[:-1]
                        orientation = 0 if seg.endswith("+") else 1
                    else:
                        seg_name = seg
                        orientation = 0
                    seg_id = self._segment_map.get(seg_name, 0)
                else:
                    seg_id = seg
                    orientation = 0
                # Pack as orientation byte + segment ID
                paths_payload_parts.append(struct.pack("<BQ", orientation, seg_id))
        paths_payload = b"".join(paths_payload_parts)

        # CIGAR payload
        all_cigars = []
        for cigars in path_cigars:
            all_cigars.extend(cigars if cigars else [])
        cigar_payload = b"".join(c.encode("ascii") + b"\x00" for c in all_cigars)
        uncompressed_len_cigar = len(cigar_payload)

        # Apply compression (placeholder - using identity for now)
        compressed_names = names_payload
        compressed_len_name = len(compressed_names)

        compressed_cigars = cigar_payload
        compressed_len_cigar = len(compressed_cigars)

        # Apply string compression to names if requested
        names_str_encoding = compression_path_names & 0xFF
        if names_str_encoding != STRING_ENCODING_IDENTITY:
            string_encoder = get_string_encoder(compression_path_names)
            if string_encoder is not None:
                try:
                    concatenated_names = "\x00".join(path_names) + "\x00"
                    compressed_names = string_encoder(concatenated_names)
                    compressed_len_name = len(compressed_names)
                    logger.debug(
                        f"Applied string compression {names_str_encoding:#04x} to path names: "
                        f"{uncompressed_len_name} -> {compressed_len_name} bytes"
                    )
                except Exception as e:
                    logger.warning(
                        f"Path names compression failed, using identity: {e}"
                    )
                    compression_path_names = 0x0000

        # Apply string compression to cigars if requested
        cigars_str_encoding = compression_cigars & 0xFF
        if cigars_str_encoding != STRING_ENCODING_IDENTITY:
            string_encoder = get_string_encoder(compression_cigars)
            if string_encoder is not None:
                try:
                    concatenated_cigars = (
                        "\x00".join(all_cigars) + "\x00" if all_cigars else ""
                    )
                    if concatenated_cigars:
                        compressed_cigars = string_encoder(concatenated_cigars)
                        compressed_len_cigar = len(compressed_cigars)
                        logger.debug(
                            f"Applied string compression {cigars_str_encoding:#04x} to CIGARs: "
                            f"{uncompressed_len_cigar} -> {compressed_len_cigar} bytes"
                        )
                except Exception as e:
                    logger.warning(f"CIGAR compression failed, using identity: {e}")
                    compression_cigars = 0x0000

        logger.debug(
            f"Paths block: names={compressed_len_name}/{uncompressed_len_name} bytes, "
            f"cigars={compressed_len_cigar}/{uncompressed_len_cigar} bytes"
        )

        # Write header according to spec
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
            2
            + 2
            + 2
            + 2
            + 8
            + 8
            + 8
            + 8
            + compressed_len_name
            + len(paths_payload)
            + compressed_len_cigar
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
                walk_id, data = walk_data
            else:
                walk_id = str(walk_data)
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

        # Build uncompressed payloads

        # Sample IDs payload (strings)
        samples_payload = b"".join(s.encode("ascii") + b"\x00" for s in sample_ids)
        uncompressed_len_sam = len(samples_payload)

        # Sequence IDs payload (strings)
        seqids_payload = b"".join(s.encode("ascii") + b"\x00" for s in seq_ids)
        uncompressed_len_seq = len(seqids_payload)

        # Walks payload (segment IDs with orientations)
        walks_payload_parts = []
        for segments in walk_segments:
            # First write number of segments in this walk
            walks_payload_parts.append(struct.pack("<Q", len(segments)))
            for seg in segments:
                if isinstance(seg, str):
                    # Parse orientation from segment string (e.g., ">seg1" or "<seg1")
                    if seg.startswith(">") or seg.startswith("<"):
                        orientation = 0 if seg.startswith(">") else 1
                        seg_name = seg[1:]
                    elif seg.endswith("+") or seg.endswith("-"):
                        orientation = 0 if seg.endswith("+") else 1
                        seg_name = seg[:-1]
                    else:
                        seg_name = seg
                        orientation = 0
                    seg_id = self._segment_map.get(seg_name, 0)
                else:
                    seg_id = seg
                    orientation = 0
                # Pack as orientation byte + segment ID
                walks_payload_parts.append(struct.pack("<BQ", orientation, seg_id))
        walks_payload = b"".join(walks_payload_parts)
        uncompressed_len_walk = len(walks_payload)

        # Apply compression (using identity for now, with compression code support)
        compressed_samples = samples_payload
        compressed_len_sam = len(compressed_samples)

        compressed_seqids = seqids_payload
        compressed_len_seq = len(compressed_seqids)

        compressed_walks = walks_payload
        compressed_len_walk = len(compressed_walks)

        # Apply string compression to sample IDs if requested
        sam_str_encoding = compression_sample_ids & 0xFF
        if sam_str_encoding != STRING_ENCODING_IDENTITY and sample_ids:
            string_encoder = get_string_encoder(compression_sample_ids)
            if string_encoder is not None:
                try:
                    concatenated = "\x00".join(sample_ids) + "\x00"
                    compressed_samples = string_encoder(concatenated)
                    compressed_len_sam = len(compressed_samples)
                    logger.debug(
                        f"Applied compression to sample IDs: "
                        f"{uncompressed_len_sam} -> {compressed_len_sam} bytes"
                    )
                except Exception as e:
                    logger.warning(f"Sample IDs compression failed: {e}")
                    compression_sample_ids = 0x0000

        # Apply string compression to sequence IDs if requested
        seq_str_encoding = compression_seq_ids & 0xFF
        if seq_str_encoding != STRING_ENCODING_IDENTITY and seq_ids:
            string_encoder = get_string_encoder(compression_seq_ids)
            if string_encoder is not None:
                try:
                    concatenated = "\x00".join(seq_ids) + "\x00"
                    compressed_seqids = string_encoder(concatenated)
                    compressed_len_seq = len(compressed_seqids)
                    logger.debug(
                        f"Applied compression to sequence IDs: "
                        f"{uncompressed_len_seq} -> {compressed_len_seq} bytes"
                    )
                except Exception as e:
                    logger.warning(f"Sequence IDs compression failed: {e}")
                    compression_seq_ids = 0x0000

        logger.debug(
            f"Walks block: samples={compressed_len_sam}/{uncompressed_len_sam}, "
            f"seqs={compressed_len_seq}/{uncompressed_len_seq}, "
            f"walks={compressed_len_walk}/{uncompressed_len_walk} bytes"
        )

        # Write header according to spec
        buffer.write(struct.pack("<H", record_num))
        buffer.write(struct.pack("<Q", compressed_len_sam))
        buffer.write(struct.pack("<Q", uncompressed_len_sam))
        buffer.write(struct.pack("<Q", compressed_len_seq))
        buffer.write(struct.pack("<Q", uncompressed_len_seq))
        buffer.write(struct.pack("<Q", compressed_len_walk))
        buffer.write(struct.pack("<Q", uncompressed_len_walk))

        # Write payloads
        buffer.write(compressed_samples)
        # Haplotype indices (packed as uint64)
        for hap in hap_indices:
            buffer.write(struct.pack("<Q", hap))
        buffer.write(compressed_seqids)
        # Start positions (packed as uint64)
        for start in start_positions:
            buffer.write(struct.pack("<Q", start))
        # End positions (packed as uint64)
        for end in end_positions:
            buffer.write(struct.pack("<Q", end))
        buffer.write(compressed_walks)

        hap_size = len(hap_indices) * 8
        pos_size = len(start_positions) * 8 + len(end_positions) * 8
        bytes_written = (
            2
            + 6 * 8  # header
            + compressed_len_sam
            + hap_size
            + compressed_len_seq
            + pos_size
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
            if data.get("is_dovetail", False):
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
    gfa_graph: "GFA",
    file=None,
    block_size: int = 1024,
    segment_names_header_compression_strategy=None,
    segment_names_payload_lengths_compression_strategy=None,
    segment_names_payload_names_compression_strategy=None,
    segments_header_compression_strategy=None,
    segments_payload_lengths_compression_strategy=None,
    segments_payload_strings_compression_strategy=None,
    links_header_compression_strategy=None,
    links_payload_from_compression_strategy=None,
    links_payload_to_compression_strategy=None,
    links_payload_cigar_lengths_compression_strategy=None,
    links_payload_cigar_compression_strategy=None,
    paths_header_compression_strategy=None,
    paths_payload_names_compression_strategy=None,
    paths_payload_segment_lengths_compression_strategy=None,
    paths_payload_path_ids_compression_strategy=None,
    paths_payload_cigar_lengths_compression_strategy=None,
    paths_payload_cigar_compression_strategy=None,
    walks_header_compression_strategy=None,
    walks_payload_sample_ids_compression_strategy=None,
    walks_payload_hep_indices_compression_strategy=None,
    walks_payload_sequence_ids_compression_strategy=None,
    walks_payload_start_compression_strategy=None,
    walks_payload_end_compression_strategy=None,
    walks_payload_walks_compression_strategy=None,
    verbose: bool = False,
    debug: bool = False,
    logfile: str = None,
) -> bytes:
    """Computes a BGFA representing the GFA graph. If a file is given, then write the BGFA to the file.

    :param gfa_graph: The GFA graph to convert to BGFA format
    :param file: Optional file path to write the BGFA data to
    :param block_size: Block size for BGFA format (default: 1024)
    :param segment_names_header_compression_strategy: Compression strategy for segment names block header
    :param segment_names_payload_lengths_compression_strategy: Compression strategy for segment names payload lengths
    :param segment_names_payload_names_compression_strategy: Compression strategy for segment names payload names
    :param segments_header_compression_strategy: Compression strategy for segments block header
    :param segments_payload_lengths_compression_strategy: Compression strategy for segments payload lengths
    :param segments_payload_strings_compression_strategy: Compression strategy for segments payload strings
    :param links_header_compression_strategy: Compression strategy for links block header
    :param links_payload_from_compression_strategy: Compression strategy for links payload 'from' field
    :param links_payload_to_compression_strategy: Compression strategy for links payload 'to' field
    :param links_payload_cigar_lengths_compression_strategy: Compression strategy for links payload cigar lengths
    :param links_payload_cigar_compression_strategy: Compression strategy for links payload cigar strings
    :param paths_header_compression_strategy: Compression strategy for paths block header
    :param paths_payload_names_compression_strategy: Compression strategy for paths payload names
    :param paths_payload_segment_lengths_compression_strategy: Compression strategy for paths payload segment lengths
    :param paths_payload_path_ids_compression_strategy: Compression strategy for paths payload path IDs
    :param paths_payload_cigar_lengths_compression_strategy: Compression strategy for paths payload cigar lengths
    :param paths_payload_cigar_compression_strategy: Compression strategy for paths payload cigar strings
    :param walks_header_compression_strategy: Compression strategy for walks block header
    :param walks_payload_sample_ids_compression_strategy: Compression strategy for walks payload sample IDs
    :param walks_payload_hep_indices_compression_strategy: Compression strategy for walks payload haplotype indices
    :param walks_payload_sequence_ids_compression_strategy: Compression strategy for walks payload sequence IDs
    :param walks_payload_start_compression_strategy: Compression strategy for walks payload start positions
    :param walks_payload_end_compression_strategy: Compression strategy for walks payload end positions
    :param walks_payload_walks_compression_strategy: Compression strategy for walks payload walks
    :param verbose: If True, log detailed information
    :param debug: If True, log debug information
    :param logfile: Path to log file (if None and verbose=True, uses a temporary file)

    :return: The BGFA representation of the input GFA graph as bytes, or empty bytes if file is provided
    """
    compression_options = {
        "segment_names_header_compression_strategy": segment_names_header_compression_strategy,
        "segment_names_payload_lengths_compression_strategy": segment_names_payload_lengths_compression_strategy,
        "segment_names_payload_names_compression_strategy": segment_names_payload_names_compression_strategy,
        "segments_header_compression_strategy": segments_header_compression_strategy,
        "segments_payload_lengths_compression_strategy": segments_payload_lengths_compression_strategy,
        "segments_payload_strings_compression_strategy": segments_payload_strings_compression_strategy,
        "links_header_compression_strategy": links_header_compression_strategy,
        "links_payload_from_compression_strategy": links_payload_from_compression_strategy,
        "links_payload_to_compression_strategy": links_payload_to_compression_strategy,
        "links_payload_cigar_lengths_compression_strategy": links_payload_cigar_lengths_compression_strategy,
        "links_payload_cigar_compression_strategy": links_payload_cigar_compression_strategy,
        "paths_header_compression_strategy": paths_header_compression_strategy,
        "paths_payload_names_compression_strategy": paths_payload_names_compression_strategy,
        "paths_payload_segment_lengths_compression_strategy": paths_payload_segment_lengths_compression_strategy,
        "paths_payload_path_ids_compression_strategy": paths_payload_path_ids_compression_strategy,
        "paths_payload_cigar_lengths_compression_strategy": paths_payload_cigar_lengths_compression_strategy,
        "paths_payload_cigar_compression_strategy": paths_payload_cigar_compression_strategy,
        "walks_header_compression_strategy": walks_header_compression_strategy,
        "walks_payload_sample_ids_compression_strategy": walks_payload_sample_ids_compression_strategy,
        "walks_payload_hep_indices_compression_strategy": walks_payload_hep_indices_compression_strategy,
        "walks_payload_sequence_ids_compression_strategy": walks_payload_sequence_ids_compression_strategy,
        "walks_payload_start_compression_strategy": walks_payload_start_compression_strategy,
        "walks_payload_end_compression_strategy": walks_payload_end_compression_strategy,
        "walks_payload_walks_compression_strategy": walks_payload_walks_compression_strategy,
    }
    bgfa = BGFAWriter(gfa_graph, block_size, compression_options)
    # If file is given, write the BGFA to the file
    if file != None:
        with open(file, "wb") as f:
            f.write(bgfa.to_bgfa(verbose=verbose, debug=debug, logfile=logfile))
    return bgfa.to_bgfa(verbose=verbose, debug=debug, logfile=logfile)


def read_bgfa(
    file_path: str, verbose: bool = False, debug: bool = False, logfile: str = None
) -> "GFA":
    """Read a BGFA file and create the corresponding GFA graph.

    :param file_path: Path to the BGFA file
    :param verbose: If True, log detailed information
    :param logfile: Path to log file (if None and verbose=True, uses a temporary file)
    :return: GFA graph object
    """
    reader = ReaderBGFA()
    return reader.read_bgfa(file_path, verbose=verbose, debug=debug, logfile=logfile)
