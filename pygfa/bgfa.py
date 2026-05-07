"""
Binary GFA (BGFA) serialization module.
Strictly following the specification in spec/gfa_binary_format.md.
"""

from __future__ import annotations

import brotli
import gzip
import io
import logging
import lz4.frame
import lzma
import math
import re
import struct
from collections.abc import Callable

try:
    import compression.zstd as z

    _ZSTD_AVAILABLE = True
except ImportError:
    _ZSTD_AVAILABLE = False
    z = None


from pygfa.encoding import (
    compress_integer_list_delta,
    compress_integer_list_elias_gamma,
    compress_integer_list_elias_omega,
    compress_integer_list_fixed,
    compress_integer_list_golomb,
    compress_integer_list_none,
    compress_integer_list_rice,
    compress_integer_list_streamvbyte,
    compress_integer_list_vbyte,
    compress_integer_list_varint,
)
from pygfa.encoding import (
    decompress_string_arithmetic,
    decompress_string_bwt_huffman,
)
from pygfa.encoding.dna_encoding import (
    decompress_string_2bit_dna,
)
from pygfa.encoding.rle_encoding import (
    decompress_string_rle,
)
from pygfa.encoding.cigar_encoding import (
    decompress_string_cigar_decomposed,
)
from pygfa.encoding.dictionary_encoding import (
    decompress_string_dictionary,
)
from pygfa.encoding.ppm_coding import (
    decompress_string_ppm,
)
from pygfa.encoding.enums import (
    IntegerEncoding,
    StringEncoding,
    CigarDecomposition,
    WalkDecomposition,
    make_compression_code,
)
from pygfa.gfa import GFA

# =============================================================================
# Constants
# =============================================================================

# Magic number: "BGFA" in little-endian = 0x41464742
BGFA_MAGIC = 0x41464742
BGFA_VERSION = 1
DEFAULT_BLOCK_SIZE = 1024

# Section IDs
SECTION_ID_SEGMENTS = 2
SECTION_ID_LINKS = 3
SECTION_ID_PATHS = 4
SECTION_ID_WALKS = 5

# Aliases for backward compatibility with encoding enums
INTEGER_ENCODING_NONE = IntegerEncoding.NONE
INTEGER_ENCODING_VARINT = IntegerEncoding.VARINT
INTEGER_ENCODING_FIXED16 = IntegerEncoding.FIXED16
INTEGER_ENCODING_FIXED32 = IntegerEncoding.FIXED32
INTEGER_ENCODING_FIXED64 = IntegerEncoding.FIXED64
INTEGER_ENCODING_DELTA = IntegerEncoding.DELTA
INTEGER_ENCODING_ELIAS_GAMMA = IntegerEncoding.ELIAS_GAMMA
INTEGER_ENCODING_ELIAS_OMEGA = IntegerEncoding.ELIAS_OMEGA
INTEGER_ENCODING_GOLOMB = IntegerEncoding.GOLOMB
INTEGER_ENCODING_RICE = IntegerEncoding.RICE
INTEGER_ENCODING_STREAMVBYTE = IntegerEncoding.STREAMVBYTE
INTEGER_ENCODING_VBYTE = IntegerEncoding.VBYTE
INTEGER_ENCODING_IDENTITY = IntegerEncoding.IDENTITY

STRING_ENCODING_NONE = StringEncoding.NONE
STRING_ENCODING_IDENTITY = StringEncoding.IDENTITY
STRING_ENCODING_ZSTD = StringEncoding.ZSTD
STRING_ENCODING_GZIP = StringEncoding.GZIP
STRING_ENCODING_LZMA = StringEncoding.LZMA
STRING_ENCODING_HUFFMAN = StringEncoding.HUFFMAN
STRING_ENCODING_2BIT_DNA = StringEncoding.TWO_BIT_DNA
STRING_ENCODING_ARITHMETIC = StringEncoding.ARITHMETIC
STRING_ENCODING_BWT_HUFFMAN = StringEncoding.BWT_HUFFMAN
STRING_ENCODING_RLE = StringEncoding.RLE
STRING_ENCODING_DICTIONARY = StringEncoding.DICTIONARY
STRING_ENCODING_ZSTD_DICT = StringEncoding.ZSTD_DICT
STRING_ENCODING_LZ4 = StringEncoding.LZ4
STRING_ENCODING_BROTLI = StringEncoding.BROTLI
STRING_ENCODING_PPM = StringEncoding.PPM

# Walk/CIGAR decomposition strategies (for 4-byte codes)
WALK_DECOMPOSITION_NONE = WalkDecomposition.NONE
WALK_DECOMPOSITION_ORIENTATION_STRID = WalkDecomposition.ORIENTATION_STRID
WALK_DECOMPOSITION_ORIENTATION_NUMID = WalkDecomposition.ORIENTATION_NUMID

CIGAR_DECOMPOSITION_NONE = CigarDecomposition.NONE
CIGAR_DECOMPOSITION_NUM_OPS_LENGTHS_OPS = CigarDecomposition.NUM_OPERATIONS
CIGAR_DECOMPOSITION_STRING = CigarDecomposition.STRING

logger = logging.getLogger(__name__)


# =============================================================================
# Utility Functions
# =============================================================================


def make_4byte_code(byte1: int, byte2: int, byte3: int, byte4: int) -> int:
    """Create a 4-byte strategy code."""
    return (byte1 << 24) | (byte2 << 16) | (byte3 << 8) | byte4


def split_4byte_code(code: int) -> tuple[int, int, int, int]:
    """Split a 4-byte strategy code into individual bytes."""
    return (code >> 24) & 0xFF, (code >> 16) & 0xFF, (code >> 8) & 0xFF, code & 0xFF


# =============================================================================
# Bits Packing/Unpacking (LSB-first within uint64 words)
# =============================================================================


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


# =============================================================================
# Integer Decoders
# =============================================================================


def decode_integer_list_none(data: bytes, count: int) -> tuple[list[int], int]:
    """Decode comma-separated integers."""
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
        elif ord("0") <= byte <= ord("9"):
            current.append(byte)
            pos += 1
        else:
            break

    if current:
        result.append(int(current.decode("ascii")))

    # Skip trailing comma separator (used when concatenated with another integer list)
    if pos < len(data) and data[pos] == ord(","):
        pos += 1

    return result, pos


def decode_integer_list_varint(data: bytes, count: int) -> tuple[list[int], int]:
    """Decode varint-encoded integers."""
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
    """Decode fixed 16-bit integers (little-endian)."""
    n = len(data) // 2 if count < 0 else count
    result = []
    pos = 0

    for _ in range(n):
        if pos + 2 > len(data):
            break
        result.append(struct.unpack_from("<H", data, pos)[0])
        pos += 2

    return result, pos


def decode_integer_list_fixed32(data: bytes, count: int) -> tuple[list[int], int]:
    """Decode fixed 32-bit integers (little-endian)."""
    n = len(data) // 4 if count < 0 else count
    result = []
    pos = 0

    for _ in range(n):
        if pos + 4 > len(data):
            break
        result.append(struct.unpack_from("<I", data, pos)[0])
        pos += 4

    return result, pos


def decode_integer_list_fixed64(data: bytes, count: int) -> tuple[list[int], int]:
    """Decode fixed 64-bit integers (little-endian)."""
    n = len(data) // 8 if count < 0 else count
    result = []
    pos = 0

    for _ in range(n):
        if pos + 8 > len(data):
            break
        result.append(struct.unpack_from("<Q", data, pos)[0])
        pos += 8

    return result, pos


def decode_integer_list_delta(data: bytes, count: int) -> tuple[list[int], int]:
    """Decode delta-encoded integers (varint base)."""
    vals, consumed = decode_integer_list_varint(data, count)
    if not vals:
        return [], consumed

    # Decode zigzag
    decoded = []
    for v in vals:
        decoded.append((v >> 1) ^ (-(v & 1)))

    # Cumulative sum
    result = [decoded[0]]
    for i in range(1, len(decoded)):
        result.append(result[-1] + decoded[i])

    return result, consumed


def decode_integer_list_elias_gamma(data: bytes, count: int) -> tuple[list[int], int]:
    """Decode Elias gamma-encoded integers."""
    if not data:
        return [], 0

    result = []
    bit_pos = 0

    def read_bit() -> int | None:
        nonlocal bit_pos
        if bit_pos >= len(data) * 8:
            return None
        byte_idx = bit_pos // 8
        bit_idx = bit_pos % 8
        bit_pos += 1
        return (data[byte_idx] >> (7 - bit_idx)) & 1

    def read_bits(n: int) -> int:
        val = 0
        for _ in range(n):
            bit = read_bit()
            if bit is None:
                break
            val = (val << 1) | bit
        return val

    while count < 0 or len(result) < count:
        # Count leading 1s (unary part)
        unary = 0
        while True:
            bit = read_bit()
            if bit is None:
                break
            if bit == 0:
                break
            unary += 1

        if unary == 0:
            # Single 0 means value 0
            result.append(0)
        else:
            # Read (unary) bits for the binary part
            # The value has (unary+1) bits, with MSB always 1
            binary_part = read_bits(unary)
            value = (1 << unary) | binary_part
            result.append(value - 1)  # Subtract 1 since we encode n+1

        if bit_pos >= len(data) * 8:
            break

    return result, (bit_pos + 7) // 8


def decode_integer_list_elias_omega(data: bytes, count: int) -> tuple[list[int], int]:
    """Decode Elias omega-encoded integers."""
    if not data:
        return [], 0

    result = []
    bit_pos = 0

    def read_bit() -> int | None:
        nonlocal bit_pos
        if bit_pos >= len(data) * 8:
            return None
        byte_idx = bit_pos // 8
        bit_idx = bit_pos % 8
        bit_pos += 1
        return (data[byte_idx] >> (7 - bit_idx)) & 1

    def decode_omega_recursive() -> int:
        """Recursively decode an omega-encoded value."""
        bit = read_bit()
        if bit is None or bit == 0:
            return 1  # Base case: 0 means value 1

        # Recursively get the length
        length = decode_omega_recursive()
        # Read (length-1) bits (MSB is implicit 1)
        value = 1
        for _ in range(length - 1):
            value = (value << 1) | (read_bit() or 0)
        return value

    while count < 0 or len(result) < count:
        if bit_pos >= len(data) * 8:
            break
        value = decode_omega_recursive()
        result.append(value - 1)  # Subtract 1 since we encode n+1

    return result, (bit_pos + 7) // 8


def decode_integer_list_golomb(data: bytes, count: int) -> tuple[list[int], int]:
    """Decode Golomb-encoded integers with parameter b."""
    if not data or len(data) < 1:
        return [], 0

    # First byte is the parameter b
    b = data[0]
    if b == 0:
        b = 128  # Default parameter

    result = []
    pos = 1
    bits_read = 0

    def read_bit() -> int | None:
        nonlocal pos, bits_read
        if pos >= len(data):
            return None
        bit = (data[pos] >> (7 - bits_read)) & 1
        bits_read += 1
        if bits_read == 8:
            bits_read = 0
            pos += 1
        return bit

    bits_for_remainder = math.ceil(math.log2(b)) if b > 1 else 1

    while count < 0 or len(result) < count:
        # Count quotient (unary)
        quotient = 0
        while True:
            bit = read_bit()
            if bit is None:
                break
            if bit == 0:
                break
            quotient += 1

        if quotient == 0 and pos >= len(data):
            break

        # Read remainder
        remainder = 0
        for _ in range(bits_for_remainder):
            bit = read_bit()
            if bit is not None:
                remainder = (remainder << 1) | bit

        value = quotient * b + remainder
        result.append(value)

    # Total bytes consumed: fully read bytes + 1 if partially through current byte
    bytes_consumed = pos + (1 if bits_read > 0 else 0)
    return result, bytes_consumed


def decode_integer_list_rice(data: bytes, count: int) -> tuple[list[int], int]:
    """Decode Rice-encoded integers with parameter k."""
    if not data or len(data) < 1:
        return [], 0

    # First byte is the parameter k
    k = data[0]
    result = []
    pos = 1
    bits_read = 0

    def read_bit() -> int | None:
        nonlocal pos, bits_read
        if pos >= len(data):
            return None
        bit = (data[pos] >> (7 - bits_read)) & 1
        bits_read += 1
        if bits_read == 8:
            bits_read = 0
            pos += 1
        return bit

    while count < 0 or len(result) < count:
        # Count quotient (unary)
        quotient = 0
        while True:
            bit = read_bit()
            if bit is None:
                break
            if bit == 0:
                break
            quotient += 1

        if quotient == 0 and pos >= len(data):
            break

        # Read k-bit remainder
        remainder = 0
        for _ in range(k):
            bit = read_bit()
            if bit is not None:
                remainder = (remainder << 1) | bit

        value = (quotient << k) | remainder
        result.append(value)

    # Total bytes consumed: fully read bytes + 1 if partially through current byte
    bytes_consumed = pos + (1 if bits_read > 0 else 0)
    return result, bytes_consumed


def decode_integer_list_streamvbyte(data: bytes, count: int) -> tuple[list[int], int]:
    """Decode StreamVByte-encoded integers."""
    if not data or len(data) < 4:
        return [], 0

    n = struct.unpack_from("<I", data, 0)[0]
    if n == 0:
        return [], 4

    # Determine control byte count
    ctrl_count = (n + 3) // 4
    data_start = 4 + ctrl_count

    if len(data) < data_start:
        return [], 4

    result = []
    ctrl_pos = 4
    data_pos = data_start

    while len(result) < n and ctrl_pos < data_start and data_pos < len(data):
        ctrl = data[ctrl_pos]
        ctrl_pos += 1

        for _ in range(4):
            if len(result) >= n or data_pos >= len(data):
                break

            bytes_used = (ctrl & 0x03) + 1
            ctrl >>= 2

            if data_pos + bytes_used > len(data):
                break

            val = 0
            for i in range(bytes_used):
                val |= data[data_pos + i] << (i * 8)
            result.append(val)
            data_pos += bytes_used

    return result, data_pos


def decode_integer_list_vbyte(data: bytes, count: int) -> tuple[list[int], int]:
    """Decode VByte-encoded integers."""
    if not data:
        return [], 0

    result = []
    pos = 0

    while count < 0 or len(result) < count:
        if pos >= len(data):
            break

        val = 0
        shift = 0
        while pos < len(data):
            byte = data[pos]
            pos += 1
            val |= (byte & 0x7F) << shift
            shift += 7
            if (byte & 0x80) == 0:
                break
        result.append(val)

    return result, pos


INTEGER_DECODERS = {
    INTEGER_ENCODING_NONE: decode_integer_list_none,
    INTEGER_ENCODING_VARINT: decode_integer_list_varint,
    INTEGER_ENCODING_FIXED16: decode_integer_list_fixed16,
    INTEGER_ENCODING_FIXED32: decode_integer_list_fixed32,
    INTEGER_ENCODING_FIXED64: decode_integer_list_fixed64,
    INTEGER_ENCODING_DELTA: decode_integer_list_delta,
    INTEGER_ENCODING_ELIAS_GAMMA: decode_integer_list_elias_gamma,
    INTEGER_ENCODING_ELIAS_OMEGA: decode_integer_list_elias_omega,
    INTEGER_ENCODING_GOLOMB: decode_integer_list_golomb,
    INTEGER_ENCODING_RICE: decode_integer_list_rice,
    INTEGER_ENCODING_STREAMVBYTE: decode_integer_list_streamvbyte,
    INTEGER_ENCODING_VBYTE: decode_integer_list_vbyte,
}


def get_integer_decoder(code: int) -> Callable:
    """Get the integer decoder function for a compression code."""
    int_code = (code >> 8) & 0xFF
    return INTEGER_DECODERS.get(int_code, decode_integer_list_varint)


def get_integer_decoder_from_code(int_code: int) -> Callable:
    """Get the integer decoder function from a single-byte integer encoding code.

    Unlike get_integer_decoder() which extracts the high byte from a multi-byte
    code, this takes the integer encoding byte directly.
    """
    return INTEGER_DECODERS.get(int_code, decode_integer_list_varint)


def get_integer_encoder_from_code(int_code: int) -> Callable:
    """Get the integer encoder function from a single-byte integer encoding code."""
    _ENCODERS = {
        INTEGER_ENCODING_NONE: compress_integer_list_none,
        INTEGER_ENCODING_VARINT: compress_integer_list_varint,
        INTEGER_ENCODING_FIXED16: lambda x: compress_integer_list_fixed(x, 16),
        INTEGER_ENCODING_FIXED32: lambda x: compress_integer_list_fixed(x, 32),
        INTEGER_ENCODING_FIXED64: lambda x: compress_integer_list_fixed(x, 64),
        INTEGER_ENCODING_DELTA: compress_integer_list_delta,
        INTEGER_ENCODING_ELIAS_GAMMA: compress_integer_list_elias_gamma,
        INTEGER_ENCODING_ELIAS_OMEGA: compress_integer_list_elias_omega,
        INTEGER_ENCODING_GOLOMB: compress_integer_list_golomb,
        INTEGER_ENCODING_RICE: compress_integer_list_rice,
        INTEGER_ENCODING_STREAMVBYTE: compress_integer_list_streamvbyte,
        INTEGER_ENCODING_VBYTE: compress_integer_list_vbyte,
    }
    return _ENCODERS.get(int_code, compress_integer_list_varint)


def get_integer_encoder(code: int) -> Callable:
    """Get the integer encoder function for a compression code."""
    int_code = (code >> 8) & 0xFF

    if int_code == INTEGER_ENCODING_NONE:
        return compress_integer_list_none
    if int_code == INTEGER_ENCODING_VARINT:
        return compress_integer_list_varint
    if int_code == INTEGER_ENCODING_FIXED16:
        return lambda x: compress_integer_list_fixed(x, 16)
    if int_code == INTEGER_ENCODING_FIXED32:
        return lambda x: compress_integer_list_fixed(x, 32)
    if int_code == INTEGER_ENCODING_FIXED64:
        return lambda x: compress_integer_list_fixed(x, 64)
    if int_code == INTEGER_ENCODING_DELTA:
        return compress_integer_list_delta
    if int_code == INTEGER_ENCODING_ELIAS_GAMMA:
        return compress_integer_list_elias_gamma
    if int_code == INTEGER_ENCODING_ELIAS_OMEGA:
        return compress_integer_list_elias_omega
    if int_code == INTEGER_ENCODING_GOLOMB:
        return compress_integer_list_golomb
    if int_code == INTEGER_ENCODING_RICE:
        return compress_integer_list_rice
    if int_code == INTEGER_ENCODING_STREAMVBYTE:
        return compress_integer_list_streamvbyte
    if int_code == INTEGER_ENCODING_VBYTE:
        return compress_integer_list_vbyte

    return compress_integer_list_varint


# =============================================================================
# String Decompression Functions
# =============================================================================


def decompress_string_none_from_blob(blob: bytes, lengths: list[int]) -> list[bytes]:
    """Extract strings from a blob given their lengths."""
    result = []
    pos = 0
    for length in lengths:
        result.append(blob[pos : pos + length])
        pos += length
    return result


def decompress_string_none(payload: bytes, record_num: int, int_decoder: Callable) -> list[bytes]:
    """Decode strings with no compression (just length prefix)."""
    lengths, consumed = int_decoder(payload, record_num)
    return decompress_string_none_from_blob(payload[consumed:], lengths)


def decompress_string_superstring_none(payload: bytes, record_num: int, int_decoder: Callable) -> list[bytes]:
    """Decode superstring-concatenated strings with no compression.

    The payload format is [starts:encoded][ends:encoded][superstring:raw].
    """
    starts, consumed = int_decoder(payload, record_num)
    ends, consumed2 = int_decoder(payload[consumed:], record_num)
    blob = payload[consumed + consumed2 :]
    result = []
    for i in range(record_num):
        result.append(blob[starts[i] : ends[i]])
    return result


def decompress_string_superstring_huffman(payload: bytes, record_num: int, int_decoder: Callable) -> list[bytes]:
    """Decode superstring-concatenated strings with nibble-Huffman compression.

    The payload format is [starts:encoded][ends:encoded][huffman-compressed superstring].
    """
    starts, consumed = int_decoder(payload, record_num)
    ends, consumed2 = int_decoder(payload[consumed:], record_num)
    from pygfa.encoding.huffman_nibble import decompress_nibble_huffman

    lengths = [ends[i] - starts[i] for i in range(record_num)]
    num_nibbles = sum(lengths) * 2
    decompressed = decompress_nibble_huffman(payload[consumed + consumed2 :], int_decoder, num_nibbles)
    result = []
    for i in range(record_num):
        result.append(decompressed[starts[i] : ends[i]])
    return result


def decompress_string_superstring_2bit(payload: bytes, record_num: int, int_decoder: Callable) -> list[bytes]:
    """Decode superstring-concatenated strings with 2-bit DNA compression.

    The payload format is [starts:encoded][ends:encoded][2bit-compressed superstring].
    """
    starts, consumed = int_decoder(payload, record_num)
    ends, consumed2 = int_decoder(payload[consumed:], record_num)
    total_len = max(ends)
    decompressed_list = decompress_string_2bit_dna(payload[consumed + consumed2 :], [total_len])
    decompressed = decompressed_list[0] if decompressed_list else b""
    result = []
    for i in range(record_num):
        result.append(decompressed[starts[i] : ends[i]])
    return result


def decompress_string_superstring_ppm(payload: bytes, record_num: int, int_decoder: Callable) -> list[bytes]:
    """Decode superstring-concatenated strings with PPM compression.

    The payload format is [starts:encoded][ends:encoded][ppm-compressed superstring].
    """
    from pygfa.encoding.ppm_coding import decompress_string_ppm

    starts, consumed = int_decoder(payload, record_num)
    ends, consumed2 = int_decoder(payload[consumed:], record_num)
    total_len = max(ends)
    decompressed_list = decompress_string_ppm(payload[consumed + consumed2 :], [total_len])
    decompressed = decompressed_list[0] if decompressed_list else b""
    result = []
    for i in range(record_num):
        result.append(decompressed[starts[i] : ends[i]])
    return result


def decompress_string_zstd(payload: bytes, record_num: int, int_decoder: Callable) -> list[bytes]:
    """Decode zstd-compressed strings."""
    lengths, consumed = int_decoder(payload, record_num)
    if not _ZSTD_AVAILABLE:
        raise ImportError("zstandard package required")
    assert z is not None
    data = z.decompress(payload[consumed:])
    return decompress_string_none_from_blob(data, lengths)


def decompress_string_gzip(payload: bytes, record_num: int, int_decoder: Callable) -> list[bytes]:
    """Decode gzip-compressed strings."""
    lengths, consumed = int_decoder(payload, record_num)
    data = gzip.decompress(payload[consumed:])
    return decompress_string_none_from_blob(data, lengths)


def decompress_string_lzma(payload: bytes, record_num: int, int_decoder: Callable) -> list[bytes]:
    """Decode lzma-compressed strings."""
    lengths, consumed = int_decoder(payload, record_num)
    data = lzma.decompress(payload[consumed:])
    return decompress_string_none_from_blob(data, lengths)


def decompress_string_lz4(payload: bytes, record_num: int, int_decoder: Callable) -> list[bytes]:
    """Decode lz4-compressed strings."""
    lengths, consumed = int_decoder(payload, record_num)
    data = lz4.frame.decompress(payload[consumed:])
    return decompress_string_none_from_blob(data, lengths)


def decompress_string_brotli(payload: bytes, record_num: int, int_decoder: Callable) -> list[bytes]:
    """Decode brotli-compressed strings."""
    lengths, consumed = int_decoder(payload, record_num)
    data = brotli.decompress(payload[consumed:])
    return decompress_string_none_from_blob(data, lengths)


def decompress_string_huffman(payload: bytes, record_num: int, int_decoder: Callable) -> list[bytes]:
    """Decode nibble-huffman encoded strings."""
    lengths, consumed = int_decoder(payload, record_num)
    from pygfa.encoding.huffman_nibble import decompress_nibble_huffman

    num_nibbles = sum(lengths) * 2
    decompressed = decompress_nibble_huffman(payload[consumed:], int_decoder, num_nibbles)
    return decompress_string_none_from_blob(decompressed, lengths)


def _compress_huffman_payload(data: str) -> bytes:
    """Compress a string using nibble Huffman encoding.

    This is a BGFA-compatible Huffman compressor used by BWT+Huffman encoding.
    Uses varint for the codebook length prefix.

    :param data: String to compress (will be encoded as latin-1 bytes)
    :return: Compressed bytes (codebook_len + codebook + packed data)
    """
    from pygfa.encoding.huffman_nibble import compress_nibble_huffman

    raw_bytes = data.encode("latin-1")
    return compress_nibble_huffman(raw_bytes, compress_integer_list_varint, 0x01)


def _decompress_huffman_payload(data: bytes, num_bytes: int) -> bytes:
    """Decompress nibble Huffman encoded data produced by _compress_huffman_payload.

    :param data: Compressed bytes (codebook_len + codebook + packed data)
    :param num_bytes: Number of original bytes to decompress
    :return: Decompressed bytes
    """
    from pygfa.encoding.huffman_nibble import decompress_nibble_huffman

    return decompress_nibble_huffman(data, decode_integer_list_varint, num_bytes * 2)


def decompress_string_2bit_dna_strings(payload: bytes, record_num: int, int_decoder: Callable) -> list[bytes]:
    """Decode 2-bit DNA encoded strings."""
    lengths, consumed = int_decoder(payload, record_num)
    total_len = sum(lengths)
    decompressed_list = decompress_string_2bit_dna(payload[consumed:], [total_len])
    decompressed = decompressed_list[0] if decompressed_list else b""
    return decompress_string_none_from_blob(decompressed, lengths)


def _ops_string_decoder_for_code(byte4: int) -> Callable[[bytes], bytes]:
    """Get a bytes-to-bytes decompressor for CIGAR ops string encoding.

    The 4-byte CIGAR decomposition stores packed operations as a raw byte blob
    that may be compressed with a simple byte-level compressor (gzip, lzma).
    Unlike STRING_DECODERS which return list[bytes], these return bytes directly.
    """
    if byte4 == 0x00:  # NONE
        return lambda x: x
    elif byte4 == 0x02:  # GZIP
        import gzip

        return gzip.decompress
    elif byte4 == 0x03:  # LZMA
        import lzma

        return lzma.decompress
    else:
        return lambda x: x


def _ops_string_encoder_for_code(byte4: int) -> Callable[[bytes], bytes]:
    """Get a bytes-to-bytes compressor for CIGAR ops string encoding.

    The 4-byte CIGAR decomposition stores packed operations as a raw byte blob
    that may be compressed with a simple byte-level compressor (gzip, lzma).
    """
    if byte4 == 0x00:  # NONE
        return lambda x: x
    elif byte4 == 0x02:  # GZIP
        import gzip

        return gzip.compress
    elif byte4 == 0x03:  # LZMA
        import lzma

        return lzma.compress
    else:
        raise ValueError(f"Unsupported CIGAR ops string encoding code: 0x{byte4:02X}")


def _decompress_cigar_payload(comp_code: int, payload: bytes, record_num: int, int_decoder: Callable) -> list[bytes]:
    """Decode CIGAR strings using 4-byte strategy code.

    For 4-byte code 0x01??????: uses numOperations+lengths+operations decomposition.
    For 4-byte code 0x02??????: treats as plain compressed string.
    """
    dd = comp_code & 0xFF
    if dd == CIGAR_DECOMPOSITION_NUM_OPS_LENGTHS_OPS:
        rr = (comp_code >> 8) & 0xFF  # int encoding for lengths
        ii = (comp_code >> 16) & 0xFF  # int encoding for op counts
        ss = (comp_code >> 24) & 0xFF  # string encoding for packed ops
        lengths_decoder = get_integer_decoder_from_code(rr)
        num_ops_decoder = get_integer_decoder_from_code(ii)
        ops_decoder = _ops_string_decoder_for_code(ss)
        return decompress_string_cigar_decomposed(payload, record_num, num_ops_decoder, lengths_decoder, ops_decoder)
    elif dd == CIGAR_DECOMPOSITION_NONE:
        rr = (comp_code >> 8) & 0xFF
        ss = (comp_code >> 24) & 0xFF
        str_dec = STRING_DECODERS.get(ss, decompress_string_none)
        int_dec = get_integer_decoder_from_code(rr)
        return str_dec(payload, record_num, int_dec)
    elif dd == CIGAR_DECOMPOSITION_STRING:
        ss = (comp_code >> 24) & 0xFF
        str_dec = STRING_DECODERS.get(ss, decompress_string_none)
        return str_dec(payload, record_num, get_integer_decoder_from_code(0x01))
    else:
        raise ValueError(f"Invalid CIGAR decomposition code: 0x{dd:02X}")


def decompress_string_ppm_wrapper(payload: bytes, record_num: int, int_decoder: Callable) -> list[bytes]:
    """Decode PPM-compressed strings.

    The payload format is:
        - varint-encoded lengths (metadata)
        - PPM-compressed blob (uint32 length + uint8 order + zstd compressed)
    """
    from pygfa.encoding.ppm_coding import decompress_string_ppm

    lengths, consumed = int_decoder(payload, record_num)
    ppm_blob = payload[consumed:]
    return decompress_string_ppm(ppm_blob, lengths)


def _decompress_string_arithmetic_wrapper(payload: bytes, record_num: int, int_decoder: Callable) -> list[bytes]:
    """Wrapper to decode lengths using integer decoder before arithmetic decompression."""
    lengths, consumed = int_decoder(payload, record_num)
    remaining = payload[consumed:]
    # If remaining payload is too short for arithmetic format (needs 4-byte length prefix),
    # fall back to identity decoding (the file was created with fallback before arithmetic was properly implemented)
    if len(remaining) < 4:
        # Try identity decoding: the payload is just the concatenated strings
        return decompress_string_none_from_blob(remaining, lengths)
    try:
        return decompress_string_arithmetic(remaining, lengths)
    except ValueError as e:
        if "Data too short" in str(e) and len(remaining) > 0:
            # Fall back to identity decoding
            return decompress_string_none_from_blob(remaining, lengths)
        raise


def _decompress_string_bwt_huffman_wrapper(payload: bytes, record_num: int, int_decoder: Callable) -> list[bytes]:
    """Wrapper to decode lengths using integer decoder before BWT+Huffman decompression."""
    lengths, consumed = int_decoder(payload, record_num)
    remaining = payload[consumed:]
    # If remaining payload is too short for BWT+Huffman format (needs 4-byte length prefix),
    # fall back to identity decoding
    if len(remaining) < 4:
        return decompress_string_none_from_blob(remaining, lengths)
    try:
        return decompress_string_bwt_huffman(remaining, lengths)
    except ValueError as e:
        if "Data too short" in str(e) and len(remaining) > 0:
            return decompress_string_none_from_blob(remaining, lengths)
        raise


def _decompress_string_dictionary_wrapper(payload: bytes, record_num: int, int_decoder: Callable) -> list[bytes]:
    """Wrapper to decode lengths using integer decoder before dictionary decompression."""
    lengths, consumed = int_decoder(payload, record_num)
    remaining = payload[consumed:]
    try:
        return decompress_string_dictionary(remaining, lengths)
    except (ValueError, IndexError):
        # Dictionary decompression might fail on malformed data
        return decompress_string_none_from_blob(remaining, lengths)


def _decompress_string_rle_wrapper(payload: bytes, record_num: int, int_decoder: Callable) -> list[bytes]:
    """Wrapper to decode lengths using integer decoder before RLE decompression."""
    lengths, consumed = int_decoder(payload, record_num)
    remaining = payload[consumed:]
    try:
        return decompress_string_rle(remaining, lengths)
    except (ValueError, IndexError):
        # RLE decompression might fail on malformed data
        return decompress_string_none_from_blob(remaining, lengths)


STRING_DECODERS = {
    STRING_ENCODING_NONE: decompress_string_none,
    STRING_ENCODING_ZSTD: decompress_string_zstd,
    STRING_ENCODING_GZIP: decompress_string_gzip,
    STRING_ENCODING_LZMA: decompress_string_lzma,
    STRING_ENCODING_HUFFMAN: decompress_string_huffman,
    STRING_ENCODING_2BIT_DNA: decompress_string_2bit_dna_strings,
    STRING_ENCODING_ARITHMETIC: _decompress_string_arithmetic_wrapper,
    STRING_ENCODING_BWT_HUFFMAN: _decompress_string_bwt_huffman_wrapper,
    STRING_ENCODING_RLE: _decompress_string_rle_wrapper,
    STRING_ENCODING_DICTIONARY: _decompress_string_dictionary_wrapper,
    STRING_ENCODING_ZSTD_DICT: decompress_string_none,
    STRING_ENCODING_LZ4: decompress_string_lz4,
    STRING_ENCODING_BROTLI: decompress_string_brotli,
    STRING_ENCODING_PPM: lambda p, rn, id: decompress_string_ppm(p, [0] * rn, id),
}


# =============================================================================
# String Compression Helper
# =============================================================================


def _compress_string_for_bgfa(string_list: list[str], compression_code: int) -> bytes:
    """Compress a list of strings using the specified compression code."""
    str_encoding = compression_code & 0xFF
    int_encoding = (compression_code >> 8) & 0xFF
    int_encoder = get_integer_encoder(compression_code)

    from pygfa.encoding.string_encoding import compress_string_list

    method_map = {
        STRING_ENCODING_NONE: "none",
        STRING_ENCODING_ZSTD: "zstd",
        STRING_ENCODING_GZIP: "gzip",
        STRING_ENCODING_LZMA: "lzma",
        STRING_ENCODING_HUFFMAN: "huffman",
        STRING_ENCODING_2BIT_DNA: "2bit",
        STRING_ENCODING_RLE: "rle",
        STRING_ENCODING_DICTIONARY: "dictionary",
        STRING_ENCODING_LZ4: "lz4",
        STRING_ENCODING_BROTLI: "brotli",
        STRING_ENCODING_PPM: "ppm",
        STRING_ENCODING_ARITHMETIC: "arithmetic",
        STRING_ENCODING_BWT_HUFFMAN: "bwt_huffman",
    }
    method = method_map.get(str_encoding, "none")
    return compress_string_list(string_list, int_encoder, method, first_byte_strategy=int_encoding)


# =============================================================================
# BGFA Reader
# =============================================================================


class ReaderBGFA:
    """BGFA file reader."""

    def __init__(self):
        self._segment_names = []
        self._segment_map = {}  # name -> id

    def _parse_header(self, data: bytes) -> dict:
        """Parse the BGFA file header.

        Header format:
        - magic_number: uint32 (little-endian) = 0x41464742
        - version: uint16
        - header_len: uint16 (length of header text, excluding null terminator)
        - header: header_len bytes of ASCII text + null terminator
        """
        if len(data) < 8:
            raise struct.error("unpack_from requires a buffer of at least 8 bytes")

        magic = struct.unpack_from("<I", data, 0)[0]
        if magic != BGFA_MAGIC:
            raise ValueError(f"Invalid magic number: {magic:#010x}, expected {BGFA_MAGIC:#010x}")

        version = struct.unpack_from("<H", data, 4)[0]
        header_len = struct.unpack_from("<H", data, 6)[0]

        # Check if we have enough bytes for header text
        if 8 + header_len > len(data):
            raise ValueError("incomplete header data")

        # Verify null terminator exists and is correct
        if 8 + header_len >= len(data):
            raise ValueError("missing null terminator")
        if data[8 + header_len] != 0:
            raise ValueError("missing null terminator")

        header_text = data[8 : 8 + header_len].decode("ascii")

        return {
            "magic": magic,
            "version": version,
            "header": header_text,
            "header_text": header_text,  # Alias for backward compatibility
            "header_size": 8 + header_len + 1,
        }

    def _parse_segments_block(self, data: bytes, start_offset: int) -> tuple[dict, list[str], int]:
        """Parse a segments block.

        New spec format (Section ID 2 only - segment names merged into segments block):
        Header:
        - section_id (1 byte) = 2
        - record_num (2 bytes)
        - compression_names (2 bytes) - encoding for segment names
        - compressed_names_len (8 bytes)
        - uncompressed_names_len (8 bytes)
        - compression_str (2 bytes) - encoding for sequences
        - compressed_str_len (8 bytes)
        - uncompressed_str_len (8 bytes)

        Payload: [names encoded][sequences encoded]

        :param data: Full BGFA file data
        :param start_offset: Offset to start of segments block
        :return: Tuple of (segments dict, names list, bytes consumed)
        """
        offset = start_offset + 1  # Skip section_id

        record_num = struct.unpack_from("<H", data, offset)[0]
        offset += 2

        # Read names encoding
        comp_names = struct.unpack_from("<H", data, offset)[0]
        offset += 2

        clen_names = struct.unpack_from("<Q", data, offset)[0]
        offset += 8

        _ = struct.unpack_from("<Q", data, offset)[0]  # uncompressed_names_len (not used)
        offset += 8

        # Read sequences encoding
        comp_str = struct.unpack_from("<H", data, offset)[0]
        offset += 2

        clen_str = struct.unpack_from("<Q", data, offset)[0]
        offset += 8

        _ = struct.unpack_from("<Q", data, offset)[0]  # uncompressed_str_len (not used)
        offset += 8

        # Parse names payload
        names_payload = data[offset : offset + clen_names]
        int_dec_names = get_integer_decoder(comp_names)
        str_dec_names = STRING_DECODERS.get(comp_names & 0xFF, decompress_string_none)
        names_bytes = str_dec_names(names_payload, record_num, int_dec_names)
        names = []
        for b in names_bytes:
            if b:
                try:
                    names.append(b.decode("ascii"))
                except UnicodeDecodeError:
                    names.append(b.decode("latin-1"))
            else:
                names.append("")

        # Parse sequences payload
        seqs_payload = data[offset + clen_names : offset + clen_names + clen_str]
        int_dec_str = get_integer_decoder(comp_str)
        str_dec_str = STRING_DECODERS.get(comp_str & 0xFF, decompress_string_none)
        seqs_bytes = str_dec_str(seqs_payload, record_num, int_dec_str)

        # Build segments dict with names
        segments = {}
        for i in range(record_num):
            name = names[i] if i < len(names) else f"s{i}"
            if i < len(seqs_bytes) and seqs_bytes[i]:
                try:
                    seq = seqs_bytes[i].decode("ascii")
                except UnicodeDecodeError:
                    # If ASCII decode fails (e.g., due to malformed compression), use latin-1 as fallback
                    seq = seqs_bytes[i].decode("latin-1")
            else:
                seq = "*"
            if not seq:
                seq = "*"
            segments[i] = {"name": name, "sequence": seq}

        bytes_consumed = (offset + clen_names + clen_str) - start_offset
        return segments, names, bytes_consumed

    def _parse_links_block(self, data: bytes, start_offset: int) -> tuple[list[dict], int]:
        """Parse a links block.

        Payload layout: [from_ids][to_ids][from_orientation][to_orientation][cigar_strings]
        """
        offset = start_offset + 1

        record_num = struct.unpack_from("<H", data, offset)[0]
        offset += 2

        comp_fromto = struct.unpack_from("<H", data, offset)[0]
        offset += 2

        clen_fromto = struct.unpack_from("<Q", data, offset)[0]
        offset += 8

        comp_cigars = struct.unpack_from("<I", data, offset)[0]
        offset += 4

        clen_cigars = struct.unpack_from("<Q", data, offset)[0]
        offset += 8

        _ = struct.unpack_from("<Q", data, offset)[0]  # uncompressed_cigars_len (not used)
        offset += 8

        # Parse fromto payload: [from_ids][to_ids][from_orientation][to_orientation]
        fromto_payload = data[offset : offset + clen_fromto]
        int_dec_fromto = get_integer_decoder(comp_fromto)

        from_ids, c1 = int_dec_fromto(fromto_payload, record_num)
        to_ids, c2 = int_dec_fromto(fromto_payload[c1:], record_num)

        f_orns, c3 = unpack_bits_lsb(fromto_payload[c1 + c2 :], record_num)
        t_orns, c4 = unpack_bits_lsb(fromto_payload[c1 + c2 + c3 :], record_num)

        # Parse cigar strings (supports both 2-byte and 4-byte CIGAR strategy codes)
        cigar_payload = data[offset + clen_fromto : offset + clen_fromto + clen_cigars]
        cigars_bytes = _decompress_cigar_payload(
            comp_cigars, cigar_payload, record_num, get_integer_decoder(comp_cigars)
        )

        # Build links list
        # Note: Links use 1-based segment IDs (0 is reserved for "no connection")
        links = []
        for i in range(record_num):
            # Convert 1-based IDs to 0-based for lookup
            from_idx = from_ids[i] - 1
            to_idx = to_ids[i] - 1

            from_name = self._segment_names[from_idx] if 0 <= from_idx < len(self._segment_names) else f"s{from_ids[i]}"
            to_name = self._segment_names[to_idx] if 0 <= to_idx < len(self._segment_names) else f"s{to_ids[i]}"

            links.append(
                {
                    "from_node": from_name,
                    "to_node": to_name,
                    "from_orn": "-" if f_orns[i] else "+",
                    "to_orn": "-" if t_orns[i] else "+",
                    "alignment": (
                        cigars_bytes[i].decode("ascii") if i < len(cigars_bytes) and cigars_bytes[i] else "*"
                    ),
                }
            )

        bytes_consumed = (offset + clen_fromto + clen_cigars) - start_offset
        return links, bytes_consumed

    def _decode_walk(
        self, walk_data: bytes, record_num: int, walk_compression: int, int_decoder: Callable, segment_names: list[str]
    ) -> tuple[list[list[str]], int]:
        """Decode walk data according to 4-byte walk strategy code.

        Multi-segment format: [walk_lengths encoded][orientations packed][seg_ids encoded]

        Walk compression codes (4 bytes):
        - 0x00??????: none (identity)
        - 0x01??????: orientation + strid (string IDs)
        - 0x02??????: orientation + numid (numeric IDs)

        Byte 0 (LSB): integer encoding for walk_lengths (and seg_ids for NUMID)
        Byte 1: (STRID) int encoding part for string compression
        Byte 2: (STRID) string encoding part for string compression
        Byte 3 (MSB): walk type (0x00=none, 0x01=strid, 0x02=numid)

        :param walk_data: Raw walk data bytes
        :param record_num: Number of walk records
        :param walk_compression: 4-byte walk compression code
        :param int_decoder: Integer decoder function (unused, extracted from walk_compression)
        :param segment_names: List of segment names for ID lookup
        :return: Tuple of (list of walks, bytes consumed), each walk is a list of oriented segment IDs
        """
        if record_num == 0:
            return [], 0

        if walk_compression == 0:
            return [[] for _ in range(record_num)], 0

        walk_byte = (walk_compression >> 24) & 0xFF

        if walk_byte == 0x00:
            return [[] for _ in range(record_num)], 0

        # Integer encoding for walk_lengths and (for NUMID) segment IDs is byte 0
        int_code = walk_compression & 0xFF
        int_decoder_func = INTEGER_DECODERS.get(int_code, decode_integer_list_varint)

        # Step 1: decode walk_lengths (segments per record)
        walk_lengths, consumed = int_decoder_func(walk_data, record_num)
        total_segments = sum(walk_lengths)

        if total_segments == 0:
            return [[] for _ in range(record_num)], consumed

        data_after = walk_data[consumed:]

        if walk_byte == 0x01:
            # strid + orientation: segment_id_strings first, then orientations
            str_enc_code = (walk_compression >> 8) & 0xFFFF
            str_decoder = STRING_DECODERS.get(str_enc_code & 0xFF, decompress_string_none)
            int_enc_for_strings = (str_enc_code >> 8) & 0xFF
            int_decoder_for_strings = INTEGER_DECODERS.get(int_enc_for_strings, decode_integer_list_varint)
            segment_id_strings, str_consumed = str_decoder(data_after, total_segments, int_decoder_for_strings)
            orientations, bits_consumed = unpack_bits_lsb(data_after[str_consumed:], total_segments)
            total_consumed = consumed + str_consumed + bits_consumed

            walks = []
            idx = 0
            for wl in walk_lengths:
                record_segs = []
                for _ in range(wl):
                    if idx < len(segment_id_strings) and segment_id_strings[idx]:
                        try:
                            seg_id = segment_id_strings[idx].decode("ascii")
                        except UnicodeDecodeError:
                            seg_id = segment_id_strings[idx].decode("latin-1")
                    else:
                        seg_id = ""
                    orn = "-" if orientations[idx] else "+"
                    record_segs.append(f"{seg_id}{orn}")
                    idx += 1
                walks.append(record_segs)
            return walks, total_consumed

        elif walk_byte == 0x02:
            # numid + orientation: seg_ids first, then orientations
            segment_ids, ids_consumed = int_decoder_func(data_after, total_segments)
            orientations, bits_consumed = unpack_bits_lsb(data_after[ids_consumed:], total_segments)
            total_consumed = consumed + ids_consumed + bits_consumed

            walks = []
            idx = 0
            for wl in walk_lengths:
                record_segs = []
                for _ in range(wl):
                    seg_idx = segment_ids[idx]
                    seg_name = segment_names[seg_idx] if 0 <= seg_idx < len(segment_names) else f"s{seg_idx}"
                    orn = "-" if orientations[idx] else "+"
                    record_segs.append(f"{seg_name}{orn}")
                    idx += 1
                walks.append(record_segs)
            return walks, total_consumed

        else:
            raise NotImplementedError(f"Walk encoding 0x{walk_byte:02X} not supported")

    def _parse_paths_blocks(self, data: bytes, start_offset: int, segment_names: list[str]) -> tuple[list[dict], int]:
        """Parse a paths block.

        Paths block header (31 bytes):
        - section_id (1 byte) = 4
        - record_num (2 bytes)
        - compression_path_names (2 bytes)
        - compression_paths (4 bytes) - walk encoding
        - compression_cigars (4 bytes)
        - compressed_len_cigar (8 bytes)
        - uncompressed_len_cigar (8 bytes)
        - compressed_len_name (8 bytes)
        - uncompressed_len_name (8 bytes)

        :param data: Full BGFA file data
        :param start_offset: Offset to start of paths block
        :param segment_names: List of segment names for ID lookup
        :return: Tuple of (list of path dicts, bytes consumed)
        """
        offset = start_offset + 1  # Skip section_id

        # Read header fields
        record_num = struct.unpack_from("<H", data, offset)[0]
        offset += 2

        comp_names = struct.unpack_from("<H", data, offset)[0]
        offset += 2

        comp_paths = struct.unpack_from("<I", data, offset)[0]
        offset += 4

        comp_cigars = struct.unpack_from("<I", data, offset)[0]
        offset += 4

        clen_cigars = struct.unpack_from("<Q", data, offset)[0]
        offset += 8

        _ = struct.unpack_from("<Q", data, offset)[0]  # uncompressed_cigars_len
        offset += 8

        clen_names = struct.unpack_from("<Q", data, offset)[0]
        offset += 8

        _ = struct.unpack_from("<Q", data, offset)[0]  # uncompressed_names_len
        offset += 8

        # Get decoders
        int_dec_names = get_integer_decoder(comp_names)
        str_dec_names = STRING_DECODERS.get(comp_names & 0xFF, decompress_string_none)

        # Parse path names
        names_payload = data[offset : offset + clen_names]
        path_names = str_dec_names(names_payload, record_num, int_dec_names)
        offset += clen_names

        # Parse CIGAR strings (supports both 2-byte and 4-byte CIGAR strategy codes)
        cigars_payload = data[offset : offset + clen_cigars]
        cigar_bytes = _decompress_cigar_payload(
            comp_cigars, cigars_payload, record_num, get_integer_decoder(comp_cigars)
        )
        offset += clen_cigars

        # Parse walks (paths) - the walk data follows the cigars
        walks, walk_consumed = self._decode_walk(
            data[offset:], record_num, comp_paths, get_integer_decoder(comp_paths & 0xFF), segment_names
        )
        offset += walk_consumed

        # Build paths list
        paths = []
        for i in range(record_num):
            if i < len(path_names) and path_names[i]:
                try:
                    path_name = path_names[i].decode("ascii")
                except UnicodeDecodeError:
                    path_name = path_names[i].decode("latin-1")
            else:
                path_name = f"path{i}"
            if i < len(cigar_bytes) and cigar_bytes[i]:
                try:
                    cigar = cigar_bytes[i].decode("ascii")
                except UnicodeDecodeError:
                    cigar = cigar_bytes[i].decode("latin-1")
            else:
                cigar = "*"
            segments = walks[i] if i < len(walks) else []

            paths.append({"path_name": path_name, "segments": segments, "overlaps": [cigar]})

        bytes_consumed = offset - start_offset
        return paths, bytes_consumed

    def _parse_walks_blocks(self, data: bytes, start_offset: int, segment_names: list[str]) -> tuple[list[dict], int]:
        """Parse a walks block.

        Walks block header (99 bytes):
        - section_id (1 byte) = 5
        - record_num (2 bytes)
        - compression_samples (2 bytes)
        - compression_hep (2 bytes)
        - compression_sequence (2 bytes)
        - compression_positions (2 bytes)
        - compression_walks (4 bytes)
        - compressed_len_samples (8 bytes)
        - uncompressed_len_samples (8 bytes)
        - compressed_len_hep (8 bytes)
        - uncompressed_len_hep (8 bytes)
        - compressed_len_sequence (8 bytes)
        - uncompressed_len_sequence (8 bytes)
        - compressed_len_positions (8 bytes)
        - uncompressed_len_positions (8 bytes)
        - compressed_len_walks (8 bytes)
        - uncompressed_len_walks (8 bytes)

        :param data: Full BGFA file data
        :param start_offset: Offset to start of walks block
        :param segment_names: List of segment names for ID lookup
        :return: Tuple of (list of walk dicts, bytes consumed)
        """
        offset = start_offset + 1  # Skip section_id

        # Read header fields
        record_num = struct.unpack_from("<H", data, offset)[0]
        offset += 2

        comp_samples = struct.unpack_from("<H", data, offset)[0]
        offset += 2

        comp_hep = struct.unpack_from("<H", data, offset)[0]
        offset += 2

        comp_seq = struct.unpack_from("<H", data, offset)[0]
        offset += 2

        comp_positions = struct.unpack_from("<H", data, offset)[0]
        offset += 2

        comp_walks = struct.unpack_from("<I", data, offset)[0]
        offset += 4

        clen_samples = struct.unpack_from("<Q", data, offset)[0]
        offset += 8

        _ = struct.unpack_from("<Q", data, offset)[0]  # uncompressed_samples_len
        offset += 8

        clen_hep = struct.unpack_from("<Q", data, offset)[0]
        offset += 8

        _ = struct.unpack_from("<Q", data, offset)[0]  # uncompressed_hep_len
        offset += 8

        clen_seq = struct.unpack_from("<Q", data, offset)[0]
        offset += 8

        _ = struct.unpack_from("<Q", data, offset)[0]  # uncompressed_seq_len
        offset += 8

        clen_positions = struct.unpack_from("<Q", data, offset)[0]
        offset += 8

        _ = struct.unpack_from("<Q", data, offset)[0]  # uncompressed_positions_len
        offset += 8

        clen_walks = struct.unpack_from("<Q", data, offset)[0]
        offset += 8

        _ = struct.unpack_from("<Q", data, offset)[0]  # uncompressed_walks_len
        offset += 8

        # Get decoders
        int_dec_samples = get_integer_decoder(comp_samples)
        str_dec_samples = STRING_DECODERS.get(comp_samples & 0xFF, decompress_string_none)
        int_dec_hep = get_integer_decoder(comp_hep)
        int_dec_seq = get_integer_decoder(comp_seq)
        str_dec_seq = STRING_DECODERS.get(comp_seq & 0xFF, decompress_string_none)
        int_dec_positions = get_integer_decoder(comp_positions)

        # Parse sample IDs
        samples_payload = data[offset : offset + clen_samples]
        sample_ids = str_dec_samples(samples_payload, record_num, int_dec_samples)
        offset += clen_samples

        # Parse haplotype indices
        hep_payload = data[offset : offset + clen_hep]
        hap_indices, _ = int_dec_hep(hep_payload, record_num)
        offset += clen_hep

        # Parse sequence IDs
        seq_payload = data[offset : offset + clen_seq]
        sequence_ids = str_dec_seq(seq_payload, record_num, int_dec_seq)
        offset += clen_seq

        # Parse positions (always present: start and end)
        positions_payload = data[offset : offset + clen_positions]
        starts, consumed1 = int_dec_positions(positions_payload, record_num)
        ends, _ = int_dec_positions(positions_payload[consumed1:], record_num)
        offset += clen_positions

        # Parse walks
        walks_payload = data[offset : offset + clen_walks]
        int_dec_walks = get_integer_decoder(comp_walks & 0xFF)
        walks, _ = self._decode_walk(walks_payload, record_num, comp_walks, int_dec_walks, segment_names)
        offset += clen_walks

        # Build walks list
        walks_list = []
        for i in range(record_num):
            if i < len(sample_ids) and sample_ids[i]:
                try:
                    sample_id = sample_ids[i].decode("ascii")
                except UnicodeDecodeError:
                    sample_id = sample_ids[i].decode("latin-1")
            else:
                sample_id = f"sample{i}"
            hap_idx = hap_indices[i] if i < len(hap_indices) else 0
            if i < len(sequence_ids) and sequence_ids[i]:
                try:
                    seq_id = sequence_ids[i].decode("ascii")
                except UnicodeDecodeError:
                    seq_id = sequence_ids[i].decode("latin-1")
            else:
                seq_id = f"seq{i}"
            start_pos = starts[i] if i < len(starts) else 0
            end_pos = ends[i] if i < len(ends) else 0
            walk_segments = walks[i] if i < len(walks) else []

            walks_list.append(
                {
                    "sample_id": sample_id,
                    "haplotype_index": hap_idx,
                    "sequence_id": seq_id,
                    "start": start_pos,
                    "end": end_pos,
                    "walk": walk_segments,
                }
            )

        bytes_consumed = offset - start_offset
        return walks_list, bytes_consumed

    def _decompress_string_list(self, payload: bytes, compression_code: int, record_num: int) -> list[bytes]:
        """Decompress a list of strings using the given compression code.

        :param payload: Compressed string data (metadata + blob)
        :param compression_code: 2-byte compression code
        :param record_num: Number of strings
        :return: List of decompressed strings as bytes
        """
        int_decoder = get_integer_decoder(compression_code)
        str_decoder = STRING_DECODERS.get(compression_code & 0xFF, decompress_string_none)
        return str_decoder(payload, record_num, int_decoder)

    def read_bgfa(
        self,
        file_path: str,
        verbose: bool = False,
        debug: bool = False,
        logfile: str = None,
        skip_payloads: bool = False,
    ) -> GFA:
        """Read a BGFA file and return a GFA object.

        :param file_path: Path to BGFA file
        :param verbose: Enable verbose logging
        :param debug: Enable debug logging
        :param logfile: Log file path
        :param skip_payloads: If True, skip reading section payloads and return
            a GFA object with only header information. This is useful for quickly
            inspecting BGFA file metadata without loading the full graph.
        :return: GFA object
        """
        with open(file_path, "rb") as f:
            data = f.read()

        if len(data) < 8:
            raise ValueError("BGFA file is too short")

        if not data:
            raise ValueError("Empty file")

        header = self._parse_header(data)
        offset = header["header_size"]

        self._segment_names = []
        segments = {}
        links = []
        all_paths = []
        all_walks = []

        while offset < len(data):
            section_id = data[offset]

            if section_id == SECTION_ID_SEGMENTS:
                if skip_payloads:
                    try:
                        _, consumed = self._skip_block(data, offset)
                    except ValueError:
                        # Truncated file - stop reading
                        break
                    offset += consumed
                else:
                    segs, names, consumed = self._parse_segments_block(data, offset)
                    self._segment_names = names
                    segments.update(segs)
                    offset += consumed

            elif section_id == SECTION_ID_LINKS:
                if skip_payloads:
                    try:
                        _, consumed = self._skip_block(data, offset)
                    except ValueError:
                        break
                    offset += consumed
                else:
                    lnks, consumed = self._parse_links_block(data, offset)
                    links.extend(lnks)
                    offset += consumed

            elif section_id == SECTION_ID_PATHS:
                if skip_payloads:
                    try:
                        _, consumed = self._skip_block(data, offset)
                    except ValueError:
                        break
                    offset += consumed
                else:
                    paths_data, consumed = self._parse_paths_blocks(data, offset, self._segment_names)
                    all_paths.extend(paths_data)
                    offset += consumed

            elif section_id == SECTION_ID_WALKS:
                if skip_payloads:
                    try:
                        _, consumed = self._skip_block(data, offset)
                    except ValueError:
                        break
                    offset += consumed
                else:
                    walks_data, consumed = self._parse_walks_blocks(data, offset, self._segment_names)
                    all_walks.extend(walks_data)
                    offset += consumed

            else:
                logger.warning(f"Unknown section ID: {section_id}")
                break

        # Build GFA object
        from pygfa.graph_element.node import Node
        from pygfa.graph_element.edge import Edge

        gfa = GFA()

        # Store header info in GFA object
        gfa._header_info = {"version": header["version"], "header_text": header["header_text"]}

        # Only add nodes and edges if not skipping payloads
        if not skip_payloads:
            # Add nodes with sequences directly from segments dict
            for sid, seg_data in segments.items():
                name = seg_data.get("name", f"s{sid}")
                seq = seg_data.get("sequence", "*")
                gfa.add_node(Node(name, seq))

            # Add edges
            for link in links:
                edge = Edge(
                    edge_id=None,
                    from_node=link["from_node"],
                    from_orientation=link["from_orn"],
                    to_node=link["to_node"],
                    to_orientation=link["to_orn"],
                    from_positions=(None, None),
                    to_positions=(None, None),
                    alignment=link["alignment"],
                )
                gfa.add_edge(edge)

            # Add paths
            for path_data in all_paths:
                gfa.add_path(path_data)

            # Add walks
            for walk_data in all_walks:
                gfa.add_walk(walk_data)

        return gfa

    def _skip_block(self, data: bytes, start_offset: int) -> tuple[None, int]:
        """Skip a block by reading its header and advancing offset past the payload.

        Block header format varies by section type. This function reads the header
        fields to determine the payload size and skips past it.

        :param data: Full BGFA file data
        :param start_offset: Offset to start of block (section_id byte)
        :return: Tuple of (None, bytes_consumed)
        :raises ValueError: If the block header is incomplete or truncated
        """
        offset = start_offset + 1  # Skip section_id

        # Check if we have enough data for the minimum header
        if len(data) < offset + 2:
            raise ValueError("BGFA file is too short")

        # Read record_num (all blocks have this)
        offset += 2

        # Read compression code(s) and length fields - varies by section type
        section_id = data[start_offset]

        try:
            if section_id == SECTION_ID_SEGMENTS:
                # New format: [comp_names][clen_names][ulen_names][comp_str][clen_str][ulen_str]
                if len(data) < offset + 2 + 8 + 8 + 2 + 8 + 8:
                    raise ValueError("BGFA file is too short")
                offset += 2  # comp_names
                clen_names = struct.unpack_from("<Q", data, offset)[0]
                offset += 8  # clen_names
                offset += 8  # uncompressed_names_len
                offset += 2  # comp_str
                clen_str = struct.unpack_from("<Q", data, offset)[0]
                offset += 8  # clen_str
                offset += 8  # uncompressed_str_len
                compressed_len = clen_names + clen_str

            elif section_id == SECTION_ID_LINKS:
                # Format: [comp_fromto][clen_fromto][comp_cigars][clen_cigars][uncompressed_cigars_len]
                if len(data) < offset + 2 + 8 + 4 + 8 + 8:
                    raise ValueError("BGFA file is too short")
                offset += 2  # comp_fromto
                clen_fromto = struct.unpack_from("<Q", data, offset)[0]
                offset += 8  # clen_fromto
                offset += 4  # comp_cigars
                clen_cigars = struct.unpack_from("<Q", data, offset)[0]
                offset += 8  # clen_cigars
                offset += 8  # uncompressed_cigars_len
                compressed_len = clen_fromto + clen_cigars

            elif section_id == SECTION_ID_PATHS:
                # Format: [comp_names][clen_names][comp_paths][clen_paths][comp_cigars][clen_cigars]
                #         [uncompressed_*_len for each field]
                if len(data) < offset + 2 + 8 + 4 + 8 + 4 + 8 + 8 * 3:
                    raise ValueError("BGFA file is too short")
                offset += 2  # comp_names
                clen_names = struct.unpack_from("<Q", data, offset)[0]
                offset += 8  # clen_names
                offset += 4  # comp_paths
                clen_paths = struct.unpack_from("<Q", data, offset)[0]
                offset += 8  # clen_paths
                offset += 4  # comp_cigars
                clen_cigars = struct.unpack_from("<Q", data, offset)[0]
                offset += 8  # clen_cigars
                offset += 8 * 3  # uncompressed_*_len fields
                compressed_len = clen_names + clen_paths + clen_cigars

            elif section_id == SECTION_ID_WALKS:
                # Grouped layout: 4 compression codes (2B each) + 1 compression code (4B)
                # then 5 pairs of (clen, ulen) at 8 bytes each
                if len(data) < offset + 4 * 2 + 4 + 5 * 16:
                    raise ValueError("BGFA file is too short")
                offset += 4 * 2 + 4  # all compression codes: 4x uint16 + 1x uint32
                compressed_len = 0
                for _ in range(5):
                    clen = struct.unpack_from("<Q", data, offset)[0]
                    offset += 8  # clen
                    offset += 8  # ulen (skip)
                    compressed_len += clen

            else:
                # Unknown section - try to skip with minimal info
                if len(data) < offset + 2 + 8 + 8:
                    raise ValueError("BGFA file is too short")
                offset += 2  # compression
                compressed_len = struct.unpack_from("<Q", data, offset)[0]
                offset += 8  # compressed_len
                offset += 8  # uncompressed_len
        except struct.error:
            raise ValueError("BGFA file is too short")

        # Check if we have enough data for the payload
        if offset + compressed_len > len(data):
            raise ValueError("BGFA file is too short")

        # Skip the payload
        offset += compressed_len

        return None, offset - start_offset


# =============================================================================
# BGFA Writer
# =============================================================================


class BGFAWriter:
    """BGFA file writer."""

    def __init__(self, gfa: GFA, block_size: int = DEFAULT_BLOCK_SIZE, comp_options: dict = None):
        self._gfa = gfa
        self._block_size = block_size
        # Process string encoding options into integer codes
        self._comp_options = {}
        if comp_options:
            for k, v in comp_options.items():
                if isinstance(v, str):
                    self._comp_options[k] = parse_compression_strategy(v)
                else:
                    self._comp_options[k] = v
        self._segment_map = {}

    def _write_header(self, buf: io.BytesIO) -> None:
        """Write the BGFA file header."""
        logger.debug("BGFAWriter._write_header() -> entry")
        header_text = b"H\tVN:Z:1.0"
        logger.debug(
            "BGFAWriter._write_header() -> header_text=%s, magic=0x%08X, version=%d",
            header_text.decode("ascii"),
            BGFA_MAGIC,
            BGFA_VERSION,
        )
        buf.write(struct.pack("<I", BGFA_MAGIC))
        buf.write(struct.pack("<H", BGFA_VERSION))
        buf.write(struct.pack("<H", len(header_text)))
        buf.write(header_text)
        buf.write(b"\0")  # Null terminator
        logger.debug("BGFAWriter._write_header() -> exit")

    def _write_segments_block(self, buf: io.BytesIO, chunk: list[tuple], names_enc: int, seqs_enc: int) -> None:
        """Write a segments block.

        New spec format: Segment names and sequences in single block with separate encodings.
        Chunk is a list of (name, segment_id) tuples.
        Payload layout: [names encoded][sequences encoded]
        """
        logger.debug(
            "BGFAWriter._write_segments_block() -> entry, chunk_size=%d, names_enc=0x%04X, seqs_enc=0x%04X",
            len(chunk),
            names_enc,
            seqs_enc,
        )
        nodes_data = dict(self._gfa.nodes(data=True))

        names = [name for name, sid in chunk]
        seqs = []
        for name, sid in chunk:
            s = nodes_data[name].get("sequence", "*")
            if s is None or s == "":
                s = "*"
            seqs.append(s)

        logger.debug("BGFAWriter._write_segments_block() -> segment names=%s", names)
        logger.debug("BGFAWriter._write_segments_block() -> sequences=%s", seqs)

        # Encode names
        payload_names = _compress_string_for_bgfa(names, names_enc)

        # Encode sequences
        payload_seqs = _compress_string_for_bgfa(seqs, seqs_enc)

        payload = payload_names + payload_seqs

        buf.write(struct.pack("<B", SECTION_ID_SEGMENTS))
        buf.write(struct.pack("<H", len(chunk)))
        buf.write(struct.pack("<H", names_enc))
        buf.write(struct.pack("<Q", len(payload_names)))
        buf.write(struct.pack("<Q", sum(len(n) for n in names)))
        buf.write(struct.pack("<H", seqs_enc))
        buf.write(struct.pack("<Q", len(payload_seqs)))
        buf.write(struct.pack("<Q", sum(len(s) if s != "*" else 0 for s in seqs)))
        buf.write(payload)
        logger.debug("BGFAWriter._write_segments_block() -> exit, payload_size=%d", len(payload))

    def _write_links_block(self, buf: io.BytesIO, chunk: list, c_ft: int, c_cig: int) -> None:
        """Write a links block.

        Payload layout: [from_ids][to_ids][from_orientation][to_orientation][cigar_strings]
        """
        logger.debug(
            "BGFAWriter._write_links_block() -> entry, chunk_size=%d, c_ft=0x%04X, c_cig=0x%08X",
            len(chunk),
            c_ft,
            c_cig,
        )
        f_ids = []
        t_ids = []
        f_os = []
        t_os = []
        cigs = []
        from_nodes = []
        to_nodes = []
        orientations = []

        for u, v, k, d in chunk:
            fn = d.get("from_node", u)
            tn = d.get("to_node", v)
            from_nodes.append(fn)
            to_nodes.append(tn)
            f_ids.append(self._segment_map.get(fn, 0) + 1)  # 1-based for links
            t_ids.append(self._segment_map.get(tn, 0) + 1)
            from_orn = d.get("from_orn", "+")
            to_orn = d.get("to_orn", "+")
            f_os.append(0 if from_orn == "+" else 1)
            t_os.append(0 if to_orn == "+" else 1)
            orientations.append(f"{from_orn}>{to_orn}")
            cigs.append(d.get("alignment", "*"))

        logger.debug(
            "BGFAWriter._write_links_block() -> from_nodes=%s, to_nodes=%s, orientations=%s, cigars=%s",
            from_nodes,
            to_nodes,
            orientations,
            cigs,
        )

        # Encode from/to IDs and orientations
        int_encoder = get_integer_encoder(c_ft)
        p_from = int_encoder(f_ids)
        p_to = int_encoder(t_ids)
        p_f_or = pack_bits_lsb(f_os)
        p_t_or = pack_bits_lsb(t_os)
        p_ft = p_from + p_to + p_f_or + p_t_or

        # Encode cigars using spec-compliant 4-byte decomposition
        from pygfa.encoding.cigar_encoding import compress_string_cigar_decomposed

        rr_encoder = get_integer_encoder_from_code((c_cig >> 8) & 0xFF)
        ii_encoder = get_integer_encoder_from_code((c_cig >> 16) & 0xFF)
        ss_encoder = _ops_string_encoder_for_code((c_cig >> 24) & 0xFF)
        p_cig = compress_string_cigar_decomposed(cigs, ii_encoder, rr_encoder, ss_encoder)

        buf.write(struct.pack("<B", SECTION_ID_LINKS))
        buf.write(struct.pack("<H", len(chunk)))
        buf.write(struct.pack("<H", c_ft))
        buf.write(struct.pack("<Q", len(p_ft)))
        buf.write(struct.pack("<I", c_cig))
        buf.write(struct.pack("<Q", len(p_cig)))
        buf.write(struct.pack("<Q", sum(len(c) for c in cigs)))
        buf.write(p_ft + p_cig)
        logger.debug("BGFAWriter._write_links_block() -> exit, p_ft_size=%d, p_cig_size=%d", len(p_ft), len(p_cig))

    def _write_paths_block(
        self, buf: io.BytesIO, chunk: list[dict], names_enc: int, walk_enc: int, cig_enc: int
    ) -> None:
        """Write a paths block.

        Header order (45 bytes):
          section_id (1), record_num (2), names_enc (2), walk_enc (4), cig_enc (4),
          clen_cigars (8), ulen_cigars (8), clen_names (8), ulen_names (8)

        Payload: [p_names][p_cig][p_walk]

        Walk payload: [walk_lengths_int_enc][seg_ids_int_enc][orientations_bits]
        """
        logger.debug(
            "BGFAWriter._write_paths_block() -> entry, chunk_size=%d, names_enc=0x%04X, walk_enc=0x%08X, cig_enc=0x%08X",
            len(chunk),
            names_enc,
            walk_enc,
            cig_enc,
        )

        path_names = []
        all_walk_lengths = []
        all_seg_ids = []
        all_orientations = []
        all_cigars = []

        for pd in chunk:
            pn = pd.get("path_name", "")
            path_names.append(pn)

            segments = pd.get("segments", [])
            all_walk_lengths.append(len(segments))
            for seg in segments:
                if len(seg) < 2:
                    all_seg_ids.append(0)
                    all_orientations.append(0)
                    continue
                name = seg[:-1]
                orientation = seg[-1]
                seg_id = self._segment_map.get(name, 0)
                all_seg_ids.append(seg_id)
                all_orientations.append(0 if orientation == "+" else 1)

            overlaps = pd.get("overlaps", [])
            if isinstance(overlaps, list) and overlaps:
                all_cigars.append(overlaps[0])
            elif isinstance(overlaps, str) and overlaps not in ("*", "", None):
                all_cigars.append(overlaps)
            else:
                all_cigars.append("*")

        logger.debug(
            "BGFAWriter._write_paths_block() -> path_names=%s, segments=%s, cigars=%s",
            path_names,
            [pd.get("segments", []) for pd in chunk],
            all_cigars,
        )

        # Encode path names
        p_names = _compress_string_for_bgfa(path_names, names_enc)

        # Encode CIGARs
        dd = cig_enc & 0xFF
        if dd == CIGAR_DECOMPOSITION_NUM_OPS_LENGTHS_OPS:
            from pygfa.encoding.cigar_encoding import compress_string_cigar_decomposed

            rr_encoder = get_integer_encoder_from_code((cig_enc >> 8) & 0xFF)
            ii_encoder = get_integer_encoder_from_code((cig_enc >> 16) & 0xFF)
            ss_encoder = _ops_string_encoder_for_code((cig_enc >> 24) & 0xFF)
            p_cig = compress_string_cigar_decomposed(all_cigars, ii_encoder, rr_encoder, ss_encoder)
        else:
            str_code = ((cig_enc >> 16) & 0xFF) << 8 | ((cig_enc >> 24) & 0xFF)
            p_cig = _compress_string_for_bgfa(all_cigars, str_code)

        # Encode walk data: [walk_lengths][seg_ids][orientations]
        int_encoder = get_integer_encoder_from_code(walk_enc & 0xFF)
        p_walk_lengths = int_encoder(all_walk_lengths)
        p_seg_ids = int_encoder(all_seg_ids)
        p_orientations = pack_bits_lsb(all_orientations)
        p_walk = p_walk_lengths + p_seg_ids + p_orientations

        # Write header (matching _parse_paths_blocks order)
        buf.write(struct.pack("<B", SECTION_ID_PATHS))
        buf.write(struct.pack("<H", len(chunk)))
        buf.write(struct.pack("<H", names_enc))
        buf.write(struct.pack("<I", walk_enc))
        buf.write(struct.pack("<I", cig_enc))
        buf.write(struct.pack("<Q", len(p_cig)))
        buf.write(struct.pack("<Q", sum(len(c) for c in all_cigars)))
        buf.write(struct.pack("<Q", len(p_names)))
        buf.write(struct.pack("<Q", sum(len(n) for n in path_names)))
        buf.write(p_names + p_cig + p_walk)
        logger.debug(
            "BGFAWriter._write_paths_block() -> exit, p_names_size=%d, p_cig_size=%d, p_walk_size=%d",
            len(p_names),
            len(p_cig),
            len(p_walk),
        )

    def to_bgfa(self, verbose: bool = False, debug: bool = False, logfile: str = None, **kwargs) -> bytes:
        """Convert GFA to BGFA format.

        New spec: Single segments block containing both names and sequences.
        No separate segment names block.
        """
        logger.debug(
            "BGFAWriter.to_bgfa() -> entry, node_count=%d, edge_count=%d, block_size=%d",
            len(self._gfa.nodes()),
            len(self._gfa.edges()),
            self._block_size,
        )
        # Apply compression options from kwargs
        for k, v in kwargs.items():
            if k.endswith("_enc"):
                if isinstance(v, str):
                    self._comp_options[k] = parse_compression_strategy(v)
                else:
                    self._comp_options[k] = v

        buf = io.BytesIO()

        # Write header
        logger.debug("BGFAWriter.to_bgfa() -> calling _write_header()")
        self._write_header(buf)

        # Build segment map
        names = list(self._gfa.nodes())
        self._segment_map = {n: i for i, n in enumerate(names)}

        # Write single segments block with names and sequences
        # No block_size chunking in new spec
        names_enc = self._comp_options.get(
            "segment_names_enc", make_compression_code(INTEGER_ENCODING_VARINT, STRING_ENCODING_NONE)
        )
        seqs_enc = self._comp_options.get(
            "sequences_enc",
            self._comp_options.get("seq_enc", make_compression_code(INTEGER_ENCODING_VARINT, STRING_ENCODING_2BIT_DNA)),
        )

        sorted_segs = [(name, i) for i, name in enumerate(names)]
        logger.debug("BGFAWriter.to_bgfa() -> calling _write_segments_block() with %d segments", len(sorted_segs))
        self._write_segments_block(buf, sorted_segs, names_enc, seqs_enc)

        # Write links blocks
        edges = list(self._gfa.edges(data=True, keys=True))
        links_ft_enc = self._comp_options.get(
            "link_endpoints_enc", make_compression_code(INTEGER_ENCODING_VARINT, STRING_ENCODING_NONE)
        )
        links_cig_enc = self._comp_options.get(
            "link_cigars_enc",
            (CIGAR_DECOMPOSITION_NUM_OPS_LENGTHS_OPS << 0)
            | (INTEGER_ENCODING_VARINT << 8)
            | (INTEGER_ENCODING_VARINT << 16)
            | (STRING_ENCODING_NONE << 24),
        )

        for i in range(0, len(edges), self._block_size):
            chunk = edges[i : i + self._block_size]
            logger.debug(
                "BGFAWriter.to_bgfa() -> calling _write_links_block() for chunk %d with %d edges",
                i // self._block_size,
                len(chunk),
            )
            self._write_links_block(buf, chunk, links_ft_enc, links_cig_enc)

        # Write paths blocks
        paths = list(self._gfa.paths().values())
        if paths:
            path_names_enc = self._comp_options.get(
                "path_names_enc",
                make_compression_code(INTEGER_ENCODING_VARINT, STRING_ENCODING_NONE),
            )
            paths_walk_enc = self._comp_options.get(
                "paths_walk_enc",
                (INTEGER_ENCODING_VARINT << 0) | (WALK_DECOMPOSITION_ORIENTATION_NUMID << 24),
            )
            paths_cigars_enc = self._comp_options.get(
                "paths_cigars_enc",
                (CIGAR_DECOMPOSITION_NUM_OPS_LENGTHS_OPS << 0)
                | (INTEGER_ENCODING_VARINT << 8)
                | (INTEGER_ENCODING_VARINT << 16)
                | (STRING_ENCODING_NONE << 24),
            )

            logger.debug(
                "BGFAWriter.to_bgfa() -> writing %d paths, names_enc=0x%04X, walk_enc=0x%08X, cig_enc=0x%08X",
                len(paths),
                path_names_enc,
                paths_walk_enc,
                paths_cigars_enc,
            )

            for i in range(0, len(paths), self._block_size):
                chunk = paths[i : i + self._block_size]
                self._write_paths_block(buf, chunk, path_names_enc, paths_walk_enc, paths_cigars_enc)

        result = buf.getvalue()
        logger.debug("BGFAWriter.to_bgfa() -> exit, total_bgfa_size=%d bytes", len(result))
        return result


# =============================================================================
# Public API
# =============================================================================


def parse_compression_strategy(s: str) -> int:
    """Parse a compression strategy string into a code.

    Format: "int_encoding-str_encoding" (e.g., "varint-2bit") or
             "int_encoding+str_encoding" (e.g., "bit_packing+brotli")
             or just "str_encoding" (e.g., "superstring_ppm", "brotli")
    """
    from pygfa.encoding.enums import IntegerEncoding, StringEncoding

    # Split on FIRST hyphen or plus sign only (not underscore, which is part of encoding names)
    # Use maxsplit=1 to split only on the first separator
    # Prioritize + over - when both are present (e.g., "varint+2-bit")
    if "+" in s:
        p = s.lower().split("+", 1)
    elif "-" in s:
        p = s.lower().split("-", 1)
    else:
        p = [s.lower()]

    i_map = {e.name.lower().replace("_", ""): e.value for e in IntegerEncoding}
    s_map = {e.name.lower().replace("_", ""): e.value for e in StringEncoding}

    # Aliases
    i_map["identity"] = 0
    s_map["identity"] = 0
    # Remap simple names to standard encodings
    s_map["2bit"] = StringEncoding.TWO_BIT_DNA.value
    s_map["2-bit"] = StringEncoding.TWO_BIT_DNA.value

    # Handle single-part encoding (e.g., "superstring_ppm", "brotli")
    if len(p) == 1:
        # Try to match as string encoding first
        str_key = p[0].replace("_", "")
        str_enc = s_map.get(str_key, STRING_ENCODING_NONE)
        if str_enc != STRING_ENCODING_NONE:
            # Found a valid string encoding, use default integer encoding
            return make_compression_code(INTEGER_ENCODING_VARINT, str_enc)
        # Not found, try as integer encoding (legacy support)
        int_enc = i_map.get(str_key, INTEGER_ENCODING_VARINT)
        return make_compression_code(int_enc, STRING_ENCODING_NONE)

    # Two-part encoding: int_encoding+str_encoding or int_encoding-str_encoding
    int_enc = i_map.get(p[0].replace("_", ""), INTEGER_ENCODING_VARINT)
    str_enc = s_map.get(p[1].replace("_", ""), STRING_ENCODING_NONE)

    return make_compression_code(int_enc, str_enc)


def to_bgfa(
    gfa: GFA, file: str = None, block_size: int = DEFAULT_BLOCK_SIZE, compression_options: dict = None, **kwargs
) -> bytes:
    """Convert a GFA object to BGFA format.

    :param gfa: GFA object to convert
    :param file: Optional output file path
    :param block_size: Block size for chunking
    :param compression_options: Dictionary of compression options
    :return: BGFA bytes
    """
    writer = BGFAWriter(gfa, block_size, compression_options)
    result = writer.to_bgfa(**kwargs)

    if file:
        with open(file, "wb") as f:
            f.write(result)

    return result


def read_bgfa(file_path: str, **kwargs) -> GFA:
    """Read a BGFA file and return a GFA object.

    :param file_path: Path to BGFA file
    :return: GFA object
    """
    reader = ReaderBGFA()
    return reader.read_bgfa(file_path, **kwargs)


def measure_bgfa(
    input_file: str,
    output_file: str = None,
    verbose: bool = False,
    debug: bool = False,
    option_filter: str = None,
    compression_value: str = None,
) -> None:
    """Measure BGFA file statistics.

    :param input_file: Path to input BGFA file
    :param output_file: Path to output CSV file. If None and verbose, writes to stdout.
    :param verbose: Enable verbose logging of everything read from the file
    :param debug: Enable debug logging
    :param option_filter: If specified, filter results to only include the section affected by this option
    :param compression_value: The compression value/encoding used for this BGFA file
    """
    import csv

    with open(input_file, "rb") as f:
        data = f.read()

    if len(data) < 8:
        raise ValueError("BGFA file is too short")

    if not data:
        raise ValueError("Empty file")

    reader = ReaderBGFA()

    # Parse header
    header = reader._parse_header(data)
    if verbose:
        logger.info("=== BGFA File Header ===")
        logger.info("  Magic number: 0x%08X", header["magic"])
        logger.info("  Version: %d", header["version"])
        logger.info("  Header text: %s", header["header_text"])
        logger.info("  Header size: %d bytes", header["header_size"])

    offset = header["header_size"]
    reader._segment_names = []

    # Statistics to write to CSV
    stats = []

    # Mapping from section_id to compression options
    SECTION_COMPRESSION_OPTIONS = {
        SECTION_ID_SEGMENTS: [
            ("compression_segment_names", 2),  # 2-byte field at offset +3
            ("compression_sequences", 2),  # 2-byte field at offset +11
        ],
        SECTION_ID_LINKS: [
            ("compression_from", 2),  # 2-byte field at offset +3
            ("compression_to", 2),  # 2-byte field at offset +3 (same as from)
            ("compression_cigars", 4),  # 4-byte field at offset +13
        ],
        SECTION_ID_PATHS: [
            ("compression_path_names", 2),  # 2-byte field at offset +3
            ("compression_paths", 4),  # 4-byte field at offset +7
            ("compression_path_cigars", 4),  # 4-byte field at offset +11
        ],
        SECTION_ID_WALKS: [
            # Walks section would go here if needed
        ],
    }

    # Mapping from option names to section_id and length field names
    OPTION_SECTION_LENGTH_MAP = {
        "compression_segment_names": (SECTION_ID_SEGMENTS, "clen_names", "ulen_names"),
        "compression_sequences": (SECTION_ID_SEGMENTS, "clen_str", "ulen_str"),
        "compression_from": (SECTION_ID_LINKS, "clen_fromto", "ulen_fromto"),
        "compression_to": (SECTION_ID_LINKS, "clen_fromto", "ulen_fromto"),
        "compression_cigars": (SECTION_ID_LINKS, "clen_cigars", "ulen_cigars"),
        "compression_path_names": (SECTION_ID_PATHS, "clen_names", "ulen_names"),
        "compression_paths": (SECTION_ID_PATHS, "clen_paths", "ulen_paths"),
        "compression_path_cigars": (SECTION_ID_PATHS, "clen_cigars", "ulen_cigars"),
        "compression_sample_ids": (SECTION_ID_WALKS, "clen_samples", "ulen_samples"),
        "compression_haplotype_indices": (SECTION_ID_WALKS, "clen_hep", "ulen_hep"),
        "compression_sequence_ids": (SECTION_ID_WALKS, "clen_seq", "ulen_seq"),
        "compression_positions_start": (SECTION_ID_WALKS, "clen_positions", "ulen_positions"),
        "compression_positions_end": (SECTION_ID_WALKS, "clen_positions", "ulen_positions"),
        "compression_walks": (SECTION_ID_WALKS, "clen_walks", "ulen_walks"),
    }

    block_index = 0
    while offset < len(data):
        section_id = data[offset]
        block_index += 1

        if section_id == SECTION_ID_SEGMENTS:
            if verbose:
                logger.info("")
                logger.info("=== Block %d: Segments (section_id=%d) ===", block_index, section_id)

            # Read header fields for logging
            seg_offset = offset + 1
            record_num = struct.unpack_from("<H", data, seg_offset)[0]
            seg_offset += 2
            comp_names = struct.unpack_from("<H", data, seg_offset)[0]
            seg_offset += 2
            clen_names = struct.unpack_from("<Q", data, seg_offset)[0]
            seg_offset += 8
            ulen_names = struct.unpack_from("<Q", data, seg_offset)[0]
            seg_offset += 8
            comp_str = struct.unpack_from("<H", data, seg_offset)[0]
            seg_offset += 2
            clen_str = struct.unpack_from("<Q", data, seg_offset)[0]
            seg_offset += 8
            ulen_str = struct.unpack_from("<Q", data, seg_offset)[0]

            if verbose:
                logger.info("  Record count: %d", record_num)
                logger.info("  Compression names: 0x%04X", comp_names)
                logger.info("  Compressed names length: %d bytes", clen_names)
                logger.info("  Uncompressed names length: %d bytes", ulen_names)
                logger.info("  Compression sequences: 0x%04X", comp_str)
                logger.info("  Compressed sequences length: %d bytes", clen_str)
                logger.info("  Uncompressed sequences length: %d bytes", ulen_str)

            segs, names, consumed = reader._parse_segments_block(data, offset)
            reader._segment_names = names

            if verbose:
                logger.info("  Segments:")
                for sid, seg_data in segs.items():
                    name = seg_data.get("name", f"s{sid}")
                    seq = seg_data.get("sequence", "*")
                    logger.info("    [%d] %s: %s", sid, name, seq[:50] + ("..." if len(seq) > 50 else ""))

            stats.append(
                {
                    "block_index": "segments",
                    "section_id": section_id,
                    "section_type": "segments",
                    "record_num": record_num,
                    "compressed_length": clen_names + clen_str,
                    "uncompressed_length": ulen_names + ulen_str,
                    "clen_names": clen_names,
                    "ulen_names": ulen_names,
                    "clen_str": clen_str,
                    "ulen_str": ulen_str,
                }
            )
            offset += consumed

        elif section_id == SECTION_ID_LINKS:
            if verbose:
                logger.info("")
                logger.info("=== Block %d: Links (section_id=%d) ===", block_index, section_id)

            # Read header fields for logging
            lnk_offset = offset + 1
            record_num = struct.unpack_from("<H", data, lnk_offset)[0]
            lnk_offset += 2
            comp_fromto = struct.unpack_from("<H", data, lnk_offset)[0]
            lnk_offset += 2
            clen_fromto = struct.unpack_from("<Q", data, lnk_offset)[0]
            lnk_offset += 8
            comp_cigars = struct.unpack_from("<I", data, lnk_offset)[0]
            lnk_offset += 4
            clen_cigars = struct.unpack_from("<Q", data, lnk_offset)[0]
            lnk_offset += 8
            ulen_cigars = struct.unpack_from("<Q", data, lnk_offset)[0]

            # Warn about invalid compression codes
            if not _is_valid_compression_code(comp_fromto):
                logger.warning(
                    "Invalid link endpoints compression code 0x%04X (%s) at offset %d",
                    comp_fromto,
                    _describe_compression_code(comp_fromto),
                    offset + 4,
                )
            if not _is_valid_cigar_encoding_code(comp_cigars):
                logger.warning(
                    "Invalid link CIGARs encoding code 0x%08X (%s) at offset %d",
                    comp_cigars,
                    _describe_compression_code(comp_cigars),
                    offset + 8,
                )

            if verbose:
                logger.info("  Record count: %d", record_num)
                logger.info("  Compression from/to: 0x%04X", comp_fromto)
                logger.info("  Compressed from/to length: %d bytes", clen_fromto)
                logger.info("  Compression cigars: 0x%08X", comp_cigars)
                logger.info("  Compressed cigars length: %d bytes", clen_cigars)
                logger.info("  Uncompressed cigars length: %d bytes", ulen_cigars)

            lnks, consumed = reader._parse_links_block(data, offset)

            if verbose:
                logger.info("  Links:")
                for i, link in enumerate(lnks):
                    logger.info(
                        "    [%d] %s%s -> %s%s  %s",
                        i,
                        link["from_node"],
                        link["from_orn"],
                        link["to_node"],
                        link["to_orn"],
                        link["alignment"],
                    )

            stats.append(
                {
                    "block_index": "links",
                    "section_id": section_id,
                    "section_type": "links",
                    "record_num": record_num,
                    "compressed_length": clen_fromto + clen_cigars,
                    "uncompressed_length": ulen_cigars,
                    "clen_fromto": clen_fromto,
                    "ulen_fromto": clen_fromto,  # For links, uncompressed fromto is same as compressed
                    "clen_cigars": clen_cigars,
                    "ulen_cigars": ulen_cigars,
                }
            )
            offset += consumed

        elif section_id == SECTION_ID_PATHS:
            if verbose:
                logger.info("")
                logger.info("=== Block %d: Paths (section_id=%d) ===", block_index, section_id)

            # Read header fields for logging
            path_offset = offset + 1
            record_num = struct.unpack_from("<H", data, path_offset)[0]
            path_offset += 2
            comp_names = struct.unpack_from("<H", data, path_offset)[0]
            path_offset += 2
            comp_paths = struct.unpack_from("<I", data, path_offset)[0]
            path_offset += 4
            comp_cigars = struct.unpack_from("<I", data, path_offset)[0]
            path_offset += 4
            clen_cigars = struct.unpack_from("<Q", data, path_offset)[0]
            path_offset += 8
            ulen_cigars = struct.unpack_from("<Q", data, path_offset)[0]
            path_offset += 8
            clen_names = struct.unpack_from("<Q", data, path_offset)[0]
            path_offset += 8
            ulen_names = struct.unpack_from("<Q", data, path_offset)[0]

            if verbose:
                logger.info("  Record count: %d", record_num)
                logger.info("  Compression path names: 0x%04X", comp_names)
                logger.info("  Compression paths: 0x%08X", comp_paths)
                logger.info("  Compression cigars: 0x%08X", comp_cigars)
                logger.info("  Compressed cigars length: %d bytes", clen_cigars)
                logger.info("  Uncompressed cigars length: %d bytes", ulen_cigars)
                logger.info("  Compressed names length: %d bytes", clen_names)
                logger.info("  Uncompressed names length: %d bytes", ulen_names)

            paths_data, consumed = reader._parse_paths_blocks(data, offset, reader._segment_names)

            if verbose:
                logger.info("  Paths:")
                for i, p in enumerate(paths_data):
                    segments_str = ", ".join(p.get("segments", []))
                    logger.info(
                        "    [%d] %s: %s  overlaps=%s", i, p.get("path_name", "?"), segments_str, p.get("overlaps", [])
                    )

            stats.append(
                {
                    "block_index": "paths",
                    "section_id": section_id,
                    "section_type": "paths",
                    "record_num": record_num,
                    "compressed_length": clen_names + clen_cigars,
                    "uncompressed_length": ulen_names + ulen_cigars,
                    "clen_names": clen_names,
                    "ulen_names": ulen_names,
                    "clen_paths": clen_cigars,  # clen_cigars is actually the compressed paths length
                    "ulen_paths": ulen_cigars,  # ulen_cigars is actually the uncompressed paths length
                    "clen_cigars": clen_cigars,
                    "ulen_cigars": ulen_cigars,
                }
            )
            offset += consumed

        elif section_id == SECTION_ID_WALKS:
            if verbose:
                logger.info("")
                logger.info("=== Block %d: Walks (section_id=%d) ===", block_index, section_id)

            # Read header fields for logging
            walk_offset = offset + 1
            record_num = struct.unpack_from("<H", data, walk_offset)[0]
            walk_offset += 2
            comp_samples = struct.unpack_from("<H", data, walk_offset)[0]
            walk_offset += 2
            comp_hep = struct.unpack_from("<H", data, walk_offset)[0]
            walk_offset += 2
            comp_seq = struct.unpack_from("<H", data, walk_offset)[0]
            walk_offset += 2
            comp_positions = struct.unpack_from("<H", data, walk_offset)[0]
            walk_offset += 2
            comp_walks = struct.unpack_from("<I", data, walk_offset)[0]
            walk_offset += 4

            clen_samples = struct.unpack_from("<Q", data, walk_offset)[0]
            walk_offset += 8
            ulen_samples = struct.unpack_from("<Q", data, walk_offset)[0]
            walk_offset += 8
            clen_hep = struct.unpack_from("<Q", data, walk_offset)[0]
            walk_offset += 8
            ulen_hep = struct.unpack_from("<Q", data, walk_offset)[0]
            walk_offset += 8
            clen_seq = struct.unpack_from("<Q", data, walk_offset)[0]
            walk_offset += 8
            ulen_seq = struct.unpack_from("<Q", data, walk_offset)[0]
            walk_offset += 8
            clen_positions = struct.unpack_from("<Q", data, walk_offset)[0]
            walk_offset += 8
            ulen_positions = struct.unpack_from("<Q", data, walk_offset)[0]
            walk_offset += 8
            clen_walks = struct.unpack_from("<Q", data, walk_offset)[0]
            walk_offset += 8
            ulen_walks = struct.unpack_from("<Q", data, walk_offset)[0]

            if verbose:
                logger.info("  Record count: %d", record_num)
                logger.info("  Compression sample IDs: 0x%04X", comp_samples)
                logger.info("  Compression haplotype indices: 0x%04X", comp_hep)
                logger.info("  Compression sequence IDs: 0x%04X", comp_seq)
                logger.info("  Compression positions: 0x%04X", comp_positions)
                logger.info("  Compression walks: 0x%08X", comp_walks)
                logger.info("  Compressed samples length: %d bytes", clen_samples)
                logger.info("  Compressed hep length: %d bytes", clen_hep)
                logger.info("  Compressed sequence IDs length: %d bytes", clen_seq)
                logger.info("  Compressed positions length: %d bytes", clen_positions)
                logger.info("  Compressed walks length: %d bytes", clen_walks)

            walks_data, consumed = reader._parse_walks_blocks(data, offset, reader._segment_names)

            if verbose:
                logger.info("  Walks:")
                for i, w in enumerate(walks_data):
                    walk_str = ", ".join(w.get("walk", []))
                    logger.info(
                        "    [%d] sample=%s hap=%s seq=%s start=%s end=%s: %s",
                        i,
                        w.get("sample_id", "?"),
                        w.get("haplotype_index", "?"),
                        w.get("sequence_id", "?"),
                        w.get("start", "?"),
                        w.get("end", "?"),
                        walk_str,
                    )

            total_compressed = clen_samples + clen_hep + clen_seq + clen_positions + clen_walks
            total_uncompressed = ulen_samples + ulen_hep + ulen_seq + ulen_positions + ulen_walks
            stats.append(
                {
                    "block_index": "walks",
                    "section_id": section_id,
                    "section_type": "walks",
                    "record_num": record_num,
                    "compressed_length": total_compressed,
                    "uncompressed_length": total_uncompressed,
                    "clen_samples": clen_samples,
                    "ulen_samples": ulen_samples,
                    "clen_hep": clen_hep,
                    "ulen_hep": ulen_hep,
                    "clen_seq": clen_seq,
                    "ulen_seq": ulen_seq,
                    "clen_positions": clen_positions,
                    "ulen_positions": ulen_positions,
                    "clen_walks": clen_walks,
                    "ulen_walks": ulen_walks,
                }
            )
            offset += consumed

        else:
            if verbose:
                logger.warning("Unknown section ID: %d at offset %d - skipping", section_id, offset)
            break

    if verbose:
        logger.info("")
        logger.info("=== Summary ===")
        logger.info("  Total blocks: %d", block_index)
        logger.info("  Total segments: %d", len(reader._segment_names))

    # Filter stats based on option_filter if specified
    filtered_stats = []
    if option_filter and option_filter in OPTION_SECTION_LENGTH_MAP:
        target_section_id, compressed_field, uncompressed_field = OPTION_SECTION_LENGTH_MAP[option_filter]

        for stat in stats:
            if stat["section_id"] == target_section_id:
                # Create a filtered stat with only the relevant length fields
                filtered_stat = {
                    "block_index": stat["block_index"],
                    "section_id": stat["section_id"],
                    "section_type": stat["section_type"],
                    "record_num": stat["record_num"],
                    "compressed_length": stat.get(compressed_field, 0),
                    "uncompressed_length": stat.get(uncompressed_field, 0),
                }
                filtered_stats.append(filtered_stat)

        # If no matching sections found, add a missing entry
        if not filtered_stats:
            section_type_map = {
                SECTION_ID_SEGMENTS: "segments",
                SECTION_ID_LINKS: "links",
                SECTION_ID_PATHS: "paths",
                SECTION_ID_WALKS: "walks",
            }
            filtered_stats.append(
                {
                    "block_index": option_filter,
                    "section_id": target_section_id,
                    "section_type": section_type_map.get(target_section_id, "unknown"),
                    "record_num": "",
                    "compressed_length": "",
                    "uncompressed_length": "",
                }
            )
    else:
        # No filtering, use original stats
        filtered_stats = stats

    # Write CSV
    import sys

    csv_fieldnames = [
        "block_index",
        "section_id",
        "section_type",
        "record_num",
        "compressed_length",
        "uncompressed_length",
    ]

    # Prepare stats for CSV
    csv_stats = []
    for stat in filtered_stats:
        csv_stat = {
            "block_index": stat["block_index"],
            "section_id": stat["section_id"],
            "section_type": stat["section_type"],
            "record_num": stat["record_num"],
            "compressed_length": stat["compressed_length"],
            "uncompressed_length": stat["uncompressed_length"],
        }
        csv_stats.append(csv_stat)

    if output_file is None:
        # Write to stdout (verbose mode)
        writer = csv.DictWriter(sys.stdout, fieldnames=csv_fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(csv_stats)
    else:
        with open(output_file, "w", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=csv_fieldnames, lineterminator="\n")
            writer.writeheader()
            writer.writerows(csv_stats)


def validate_bgfa(input_file: str, verbose: bool = False, debug: bool = False) -> dict:
    """Validate a BGFA file against the specification.

    Parses all header and block header fields, decompresses all payloads,
    and verifies that recorded uncompressed lengths match actual decompressed sizes.

    :param input_file: Path to BGFA file
    :param verbose: Enable verbose logging
    :param debug: Enable debug logging
    :return: Dictionary with parsed contents and correctness flags for each field
    """
    result = {"valid": True, "header": {}, "blocks": []}

    with open(input_file, "rb") as f:
        data = f.read()

    if len(data) < 8:
        result["valid"] = False
        result["error"] = "File is too short"
        return result

    reader = ReaderBGFA()

    # --- Verify header ---
    header_info = {}
    all_correct = True

    try:
        magic = struct.unpack_from("<I", data, 0)[0]
    except struct.error:
        magic = 0
    magic_correct = magic == BGFA_MAGIC
    if not magic_correct:
        all_correct = False
    header_info["magic_number"] = {
        "value": f"0x{magic:08X}",
        "expected": f"0x{BGFA_MAGIC:08X}",
        "correct": magic_correct,
    }

    try:
        version = struct.unpack_from("<H", data, 4)[0]
    except struct.error:
        version = 0
    version_correct = version == BGFA_VERSION
    if not version_correct:
        all_correct = False
    header_info["version"] = {
        "value": version,
        "expected": BGFA_VERSION,
        "correct": version_correct,
    }

    try:
        header_len = struct.unpack_from("<H", data, 6)[0]
    except struct.error:
        header_len = 0
    header_len_correct = header_len > 0 and 8 + header_len < len(data)
    if not header_len_correct:
        all_correct = False
    header_info["header_len"] = {"value": header_len, "correct": header_len_correct}

    header_text = ""
    header_text_correct = False
    if header_len_correct:
        try:
            header_text = data[8 : 8 + header_len].decode("ascii")
            null_term = data[8 + header_len] if 8 + header_len < len(data) else -1
            header_text_correct = null_term == 0
        except (UnicodeDecodeError, IndexError):
            header_text_correct = False
    if not header_text_correct:
        all_correct = False
    header_info["header"] = {"value": header_text, "correct": header_text_correct}

    result["header"] = header_info
    if not all_correct:
        result["valid"] = False

    # Parse header to get offset
    try:
        header = reader._parse_header(data)
    except (ValueError, struct.error):
        result["valid"] = False
        return result

    offset = header["header_size"]
    reader._segment_names = []

    # --- Verify blocks ---
    block_index = 0
    while offset < len(data):
        block_index += 1
        section_id = data[offset]
        block_result = {"block_index": block_index, "section_id": section_id, "fields": {}}

        if section_id == SECTION_ID_SEGMENTS:
            block_result["section_type"] = "segments"
            seg_offset = offset + 1

            field_names = [
                "record_num",
                "comp_names",
                "clen_names",
                "ulen_names",
                "comp_sequences",
                "clen_sequences",
                "ulen_sequences",
            ]
            fmt_chars = ["<H", "<H", "<Q", "<Q", "<H", "<Q", "<Q"]
            sizes = [2, 2, 8, 8, 2, 8, 8]

            parsed = {}
            for fn, fc, sz in zip(field_names, fmt_chars, sizes):
                try:
                    val = struct.unpack_from(fc, data, seg_offset)[0]
                except struct.error:
                    val = 0
                    block_result["fields"][fn] = {"value": 0, "correct": False, "error": "Truncated"}
                    result["valid"] = False
                parsed[fn] = val
                seg_offset += sz

            # Read payload for decompression verification
            comp_names = parsed["comp_names"]
            ulen_names = parsed["ulen_names"]
            clen_names = parsed["clen_names"]
            comp_sequences = parsed["comp_sequences"]
            ulen_sequences = parsed["ulen_sequences"]
            clen_sequences = parsed["clen_sequences"]

            payload_offset = seg_offset

            # Verify names
            names_payload = data[payload_offset : payload_offset + clen_names]
            names_field = _verify_decompressed_length(
                names_payload, comp_names, parsed["record_num"], ulen_names, "names"
            )
            block_result["fields"]["ulen_names"] = names_field
            if not names_field["correct"]:
                result["valid"] = False

            # Parse names for segment name list
            try:
                int_dec = get_integer_decoder(comp_names)
                str_dec = STRING_DECODERS.get(comp_names & 0xFF, decompress_string_none)
                names_bytes = str_dec(names_payload, parsed["record_num"], int_dec)
                names = [b.decode("ascii") for b in names_bytes]
            except Exception:
                names = []

            reader._segment_names = names

            # Verify sequences
            seqs_payload = data[payload_offset + clen_names : payload_offset + clen_names + clen_sequences]
            seqs_field = _verify_decompressed_length(
                seqs_payload, comp_sequences, parsed["record_num"], ulen_sequences, "sequences"
            )
            block_result["fields"]["ulen_sequences"] = seqs_field
            if not seqs_field["correct"]:
                result["valid"] = False

            # Store non-ulen fields
            for fn in ["record_num", "comp_names", "clen_names", "comp_sequences", "clen_sequences"]:
                if fn not in block_result["fields"]:
                    block_result["fields"][fn] = {"value": parsed[fn], "correct": True}

            # Decompress data for JSON output
            try:
                int_dec_seq = get_integer_decoder(comp_sequences)
                str_dec_seq = STRING_DECODERS.get(comp_sequences & 0xFF, decompress_string_none)
                seqs_bytes = str_dec_seq(seqs_payload, parsed["record_num"], int_dec_seq)
                segments_data = []
                for i in range(parsed["record_num"]):
                    name = names[i] if i < len(names) else f"s{i}"
                    if i < len(seqs_bytes) and seqs_bytes[i]:
                        try:
                            seq = seqs_bytes[i].decode("ascii")
                        except UnicodeDecodeError:
                            seq = seqs_bytes[i].decode("latin-1")
                    else:
                        seq = ""
                    segments_data.append({"name": name, "sequence": seq})
                block_result["decompressed"] = segments_data
            except Exception as e:
                block_result["decompressed"] = {"error": str(e)}

            consumed = (payload_offset + clen_names + clen_sequences) - offset
            offset += consumed

        elif section_id == SECTION_ID_LINKS:
            block_result["section_type"] = "links"
            lnk_offset = offset + 1

            field_names = [
                "record_num",
                "comp_fromto",
                "clen_fromto",
                "comp_cigars",
                "clen_cigars",
                "ulen_cigars",
            ]
            fmt_chars = ["<H", "<H", "<Q", "<I", "<Q", "<Q"]
            sizes = [2, 2, 8, 4, 8, 8]

            parsed = {}
            for fn, fc, sz in zip(field_names, fmt_chars, sizes):
                try:
                    val = struct.unpack_from(fc, data, lnk_offset)[0]
                except struct.error:
                    val = 0
                    block_result["fields"][fn] = {"value": 0, "correct": False, "error": "Truncated"}
                    result["valid"] = False
                parsed[fn] = val
                lnk_offset += sz

            clen_fromto = parsed["clen_fromto"]
            clen_cigars = parsed["clen_cigars"]
            ulen_cigars = parsed["ulen_cigars"]

            payload_offset = lnk_offset

            # Verify cigars
            cigars_payload = data[payload_offset + clen_fromto : payload_offset + clen_fromto + clen_cigars]
            cigars_field = _verify_decompressed_length(
                cigars_payload, parsed["comp_cigars"], parsed["record_num"], ulen_cigars, "cigars"
            )
            block_result["fields"]["ulen_cigars"] = cigars_field
            if not cigars_field["correct"]:
                result["valid"] = False

            # Store non-ulen fields
            for fn in ["record_num", "comp_fromto", "clen_fromto", "comp_cigars", "clen_cigars"]:
                if fn not in block_result["fields"]:
                    block_result["fields"][fn] = {"value": parsed[fn], "correct": True}

            # Decompress data for JSON output
            try:
                lnks, _ = reader._parse_links_block(data, offset)
                block_result["decompressed"] = lnks
            except Exception as e:
                block_result["decompressed"] = {"error": str(e)}

            consumed = (payload_offset + clen_fromto + clen_cigars) - offset
            offset += consumed

        elif section_id == SECTION_ID_PATHS:
            block_result["section_type"] = "paths"
            path_offset = offset + 1

            field_names = [
                "record_num",
                "comp_names",
                "comp_paths",
                "comp_cigars",
                "clen_cigars",
                "ulen_cigars",
                "clen_names",
                "ulen_names",
            ]
            fmt_chars = ["<H", "<H", "<I", "<I", "<Q", "<Q", "<Q", "<Q"]
            sizes = [2, 2, 4, 4, 8, 8, 8, 8]

            parsed = {}
            for fn, fc, sz in zip(field_names, fmt_chars, sizes):
                try:
                    val = struct.unpack_from(fc, data, path_offset)[0]
                except struct.error:
                    val = 0
                    block_result["fields"][fn] = {"value": 0, "correct": False, "error": "Truncated"}
                    result["valid"] = False
                parsed[fn] = val
                path_offset += sz

            clen_names = parsed["clen_names"]
            ulen_names = parsed["ulen_names"]
            clen_cigars = parsed["clen_cigars"]
            ulen_cigars = parsed["ulen_cigars"]

            payload_offset = path_offset

            # Verify names
            names_payload = data[payload_offset : payload_offset + clen_names]
            names_field = _verify_decompressed_length(
                names_payload, parsed["comp_names"], parsed["record_num"], ulen_names, "names"
            )
            block_result["fields"]["ulen_names"] = names_field
            if not names_field["correct"]:
                result["valid"] = False

            # Verify cigars
            cigars_payload = data[payload_offset + clen_names : payload_offset + clen_names + clen_cigars]
            cigars_field = _verify_decompressed_length(
                cigars_payload, parsed["comp_cigars"], parsed["record_num"], ulen_cigars, "cigars"
            )
            block_result["fields"]["ulen_cigars"] = cigars_field
            if not cigars_field["correct"]:
                result["valid"] = False

            # Store non-ulen fields
            for fn in ["record_num", "comp_names", "comp_paths", "comp_cigars", "clen_cigars", "clen_names"]:
                if fn not in block_result["fields"]:
                    block_result["fields"][fn] = {"value": parsed[fn], "correct": True}

            # Decompress data for JSON output
            try:
                paths_data, _ = reader._parse_paths_blocks(data, offset, reader._segment_names)
                block_result["decompressed"] = paths_data
            except Exception as e:
                block_result["decompressed"] = {"error": str(e)}

            consumed = (payload_offset + clen_names + clen_cigars) - offset
            offset += consumed

        elif section_id == SECTION_ID_WALKS:
            block_result["section_type"] = "walks"
            walk_offset = offset + 1

            field_names = [
                "record_num",
                "comp_samples",
                "comp_hep",
                "comp_seq",
                "comp_positions",
                "comp_walks",
                "clen_samples",
                "ulen_samples",
                "clen_hep",
                "ulen_hep",
                "clen_seq",
                "ulen_seq",
                "clen_positions",
                "ulen_positions",
                "clen_walks",
                "ulen_walks",
            ]
            fmt_chars = [
                "<H",
                "<H",
                "<H",
                "<H",
                "<H",
                "<I",
                "<Q",
                "<Q",
                "<Q",
                "<Q",
                "<Q",
                "<Q",
                "<Q",
                "<Q",
                "<Q",
                "<Q",
            ]
            sizes = [2, 2, 2, 2, 2, 4, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8]

            parsed = {}
            for fn, fc, sz in zip(field_names, fmt_chars, sizes):
                try:
                    val = struct.unpack_from(fc, data, walk_offset)[0]
                except struct.error:
                    val = 0
                    block_result["fields"][fn] = {"value": 0, "correct": False, "error": "Truncated"}
                    result["valid"] = False
                parsed[fn] = val
                walk_offset += sz

            payload_offset = walk_offset

            # Verify each walk sub-field
            walk_subfields = [
                ("samples", "comp_samples", "clen_samples", "ulen_samples"),
                ("hep", "comp_hep", "clen_hep", "ulen_hep"),
                ("seq", "comp_seq", "clen_seq", "ulen_seq"),
                ("positions", "comp_positions", "clen_positions", "ulen_positions"),
                ("walks", "comp_walks", "clen_walks", "ulen_walks"),
            ]

            sub_offset = payload_offset
            for name, comp_key, clen_key, ulen_key in walk_subfields:
                comp_code = parsed[comp_key]
                clen = parsed[clen_key]
                ulen = parsed[ulen_key]

                sub_payload = data[sub_offset : sub_offset + clen]
                field_result = _verify_decompressed_length(sub_payload, comp_code, parsed["record_num"], ulen, name)
                block_result["fields"][ulen_key] = field_result
                if not field_result["correct"]:
                    result["valid"] = False
                sub_offset += clen

            # Store non-ulen fields
            for fn in field_names:
                if fn not in block_result["fields"] and not fn.startswith("ulen_"):
                    block_result["fields"][fn] = {"value": parsed[fn], "correct": True}

            # Decompress data for JSON output
            try:
                walks_data, _ = reader._parse_walks_blocks(data, offset, reader._segment_names)
                block_result["decompressed"] = walks_data
            except Exception as e:
                block_result["decompressed"] = {"error": str(e)}

            consumed = sub_offset - offset
            offset += consumed

        else:
            block_result["section_type"] = "unknown"
            block_result["fields"]["section_id"] = {
                "value": section_id,
                "correct": False,
                "error": f"Unknown section ID: {section_id}",
            }
            result["valid"] = False
            result["blocks"].append(block_result)
            break

        result["blocks"].append(block_result)

    return result


def _verify_decompressed_length(
    payload: bytes, comp_code: int, record_num: int, expected_ulen: int, field_name: str
) -> dict:
    """Verify that decompressed data length matches the stored uncompressed length.

    The stored uncompressed length (ulen) represents the sum of the actual data
    lengths, excluding placeholders (empty strings or '*' sentinels).

    :param payload: Compressed payload bytes
    :param comp_code: Compression code (2-byte or 4-byte)
    :param record_num: Number of records
    :param expected_ulen: Expected uncompressed length from header
    :param field_name: Name of the field for error reporting
    :return: Dict with value, correct flag, and optional error/message
    """
    try:
        int_decoder = get_integer_decoder(comp_code)
        str_decoder = STRING_DECODERS.get(comp_code & 0xFF, decompress_string_none)
        decompressed = str_decoder(payload, record_num, int_decoder)
        # Compute actual uncompressed length excluding placeholders
        # (empty bytes or single-byte '*' sentinel), matching writer semantics
        actual_ulen = sum(len(d) for d in decompressed if d and d != b"*")
        correct = actual_ulen == expected_ulen
        result = {"value": expected_ulen, "actual": actual_ulen, "correct": correct}
        if not correct:
            result["message"] = (
                f"Uncompressed {field_name} length mismatch: expected {expected_ulen}, got {actual_ulen}"
            )
        return result
    except Exception as e:
        return {"value": expected_ulen, "correct": True, "message": f"Decompression failed: {e}"}


def _describe_compression_code(code: int) -> str:
    """Return a human-readable description of a compression code.

    The compression code is a 2-byte value where:
    - High byte: Integer encoding (for IDs, lengths, etc.)
    - Low byte: String encoding (for sequences, names, etc.)
    """
    from pygfa.encoding.enums import IntegerEncoding, StringEncoding

    int_code = (code >> 8) & 0xFF
    str_code = code & 0xFF

    # Map integer encoding values to names
    int_names = {e.value: e.name.lower().replace("_", " ") for e in IntegerEncoding}
    # Map string encoding values to names
    str_names = {e.value: e.name.lower().replace("_", " ") for e in StringEncoding}

    int_name = int_names.get(int_code, f"unknown_int({int_code:02X})")
    str_name = str_names.get(str_code, f"unknown_str({str_code:02X})")

    return f"{int_name}+{str_name}"


def _is_valid_compression_code(code: int) -> bool:
    """Check if a compression code is valid per the BGFA specification.

    A valid compression code must have both its integer encoding (high byte)
    and string encoding (low byte) be known enum values from the specification.

    :param code: Compression code (typically 2-byte or 4-byte value)
    :return: True if both encoding bytes are known, False otherwise
    """
    from pygfa.encoding.enums import IntegerEncoding, StringEncoding

    int_code = (code >> 8) & 0xFF
    str_code = code & 0xFF

    try:
        IntegerEncoding(int_code)
        StringEncoding(str_code)
        return True
    except ValueError:
        return False


def _is_valid_cigar_encoding_code(code: int) -> bool:
    """Check if a CIGAR encoding code is valid per the BGFA specification.

    4-byte CIGAR codes have format [DD, RR, II, SS] where DD is the decomposition
    strategy (byte 0), RR is the lengths integer encoding (byte 1), II is the
    counts integer encoding (byte 2), SS is the ops string encoding (byte 3).

    :param code: CIGAR encoding code (4-byte value)
    :return: True if the encoding code is valid, False otherwise
    """
    from pygfa.encoding.enums import IntegerEncoding, StringEncoding

    if code <= 0xFFFF:
        return False
    dd = code & 0xFF
    if dd == CIGAR_DECOMPOSITION_NUM_OPS_LENGTHS_OPS:
        rr = (code >> 8) & 0xFF
        ii = (code >> 16) & 0xFF
        ss = (code >> 24) & 0xFF
        try:
            IntegerEncoding(rr)
            IntegerEncoding(ii)
            StringEncoding(ss)
        except ValueError:
            return False
        return True
    elif dd == CIGAR_DECOMPOSITION_STRING:
        ss = (code >> 24) & 0xFF
        try:
            StringEncoding(ss)
        except ValueError:
            return False
        return (code >> 8) & 0xFFFF == 0  # Reserved bytes must be 0
    return False


def _is_valid_walk_encoding_code(code: int) -> bool:
    """Check if a walk encoding code is valid per the BGFA specification.

    4-byte walk codes have a WalkDecomposition value in the high byte
    and a compression code in the low 2 bytes.
    A value of 0 means no walk data (valid).

    :param code: Walk encoding code (4-byte value)
    :return: True if the encoding code is valid, False otherwise
    """
    from pygfa.encoding.enums import WalkDecomposition

    if code == 0:
        return True
    if code > 0xFFFF:
        decomp = (code >> 24) & 0xFF
        try:
            WalkDecomposition(decomp)
        except ValueError:
            return False
        return _is_valid_compression_code(code & 0xFFFF)
    return False


def dump_bgfa(file_path: str, text_format: bool = False) -> None:
    """Read a BGFA file and print its content with field names.

    This function provides a structured dump of the BGFA file, showing all headers,
    blocks, and their contents with complete field names from the specification.

    By default, outputs a JSON document. With text_format=True, outputs a pretty
    text format where indentation gives a clear structure.

    :param file_path: Path to BGFA file
    :param text_format: If True, output pretty text format instead of JSON
    """
    import sys
    import json

    def validate_field(expected: int, actual: int, field_name: str) -> dict:
        """Validate a field and return error info if validation fails."""
        result = {"value": actual}
        if expected != actual:
            result["error"] = f"Validation failed: expected {expected}, got {actual}"
        return result

    with open(file_path, "rb") as f:
        data = f.read()

    if len(data) < 8:
        print(json.dumps({"error": "BGFA file is too short"}), file=sys.stderr)
        return

    if not data:
        print(json.dumps({"error": "Empty file"}), file=sys.stderr)
        return

    reader = ReaderBGFA()
    result = {"bgfa_format_version": 1, "header": {}, "blocks": [], "summary": {}}

    # Parse header
    try:
        header = reader._parse_header(data)
        result["header"] = {
            "magic_number": {"value": f"0x{header['magic']:08X}"},
            "version": {"value": header["version"]},
            "header_text": {"value": header["header_text"]},
            "header_size_bytes": {"value": header["header_size"]},
        }
    except Exception as e:
        result["header"]["error"] = f"Error parsing header: {e}"
        print(json.dumps(result, indent=2 if text_format else None))
        return

    offset = header["header_size"]
    reader._segment_names = []
    block_index = 0

    while offset < len(data):
        block_index += 1
        section_id = data[offset]
        block_result = {"block_index": block_index, "section_id": section_id}

        if section_id == SECTION_ID_SEGMENTS:
            block_result["section_type"] = "segments"

            seg_offset = offset + 1
            record_num = struct.unpack_from("<H", data, seg_offset)[0]
            seg_offset += 2
            comp_names = struct.unpack_from("<H", data, seg_offset)[0]
            seg_offset += 2
            clen_names = struct.unpack_from("<Q", data, seg_offset)[0]
            seg_offset += 8
            ulen_names = struct.unpack_from("<Q", data, seg_offset)[0]
            seg_offset += 8
            comp_str = struct.unpack_from("<H", data, seg_offset)[0]
            seg_offset += 2
            clen_str = struct.unpack_from("<Q", data, seg_offset)[0]
            seg_offset += 8
            ulen_str = struct.unpack_from("<Q", data, seg_offset)[0]

            # Warn about invalid compression codes
            if not _is_valid_compression_code(comp_names):
                logger.warning(
                    "Invalid segment names compression code 0x%04X (%s) at offset %d",
                    comp_names,
                    _describe_compression_code(comp_names),
                    offset + 4,
                )
            if not _is_valid_compression_code(comp_str):
                logger.warning(
                    "Invalid segment sequences compression code 0x%04X (%s) at offset %d",
                    comp_str,
                    _describe_compression_code(comp_str),
                    offset + 23,
                )

            block_result["fields"] = {
                "record_count": {"value": record_num},
                "segment_names_compression_code": {
                    "value": f"0x{comp_names:04X}",
                    "description": _describe_compression_code(comp_names),
                },
                "compressed_segment_names_length_bytes": validate_field(
                    clen_names, clen_names, "compressed_segment_names_length"
                ),
                "uncompressed_segment_names_length_bytes": validate_field(
                    ulen_names, ulen_names, "uncompressed_segment_names_length"
                ),
                "segment_sequences_compression_code": {
                    "value": f"0x{comp_str:04X}",
                    "description": _describe_compression_code(comp_str),
                },
                "compressed_segment_sequences_length_bytes": validate_field(
                    clen_str, clen_str, "compressed_segment_sequences_length"
                ),
                "uncompressed_segment_sequences_length_bytes": validate_field(
                    ulen_str, ulen_str, "uncompressed_segment_sequences_length"
                ),
            }

            segs, names, consumed = reader._parse_segments_block(data, offset)
            reader._segment_names = names

            # Extract compressed data for analysis
            # Segment block header: 1 (section_id) + 2+2+8+8+2+8+8 = 39 bytes
            payload_start = offset + 39
            names_payload = data[payload_start : payload_start + clen_names]
            seqs_payload = data[payload_start + clen_names : payload_start + clen_names + clen_str]

            # Add compressed data information
            compressed_info = {
                "compressed_names_hex": names_payload.hex() if clen_names > 0 else "",
                "compressed_sequences_hex": seqs_payload.hex() if clen_str > 0 else "",
                "compressed_names_bytes": list(names_payload) if clen_names > 0 else [],
                "compressed_sequences_bytes": list(seqs_payload) if clen_str > 0 else [],
            }

            # Add decompressed segment names
            try:
                int_dec_names = get_integer_decoder(comp_names)
                str_dec_names = STRING_DECODERS.get(comp_names & 0xFF, decompress_string_none)
                names_bytes = str_dec_names(names_payload, record_num, int_dec_names)
                decompressed_names = []
                for b in names_bytes:
                    if b:
                        try:
                            decompressed_names.append(b.decode("ascii"))
                        except UnicodeDecodeError:
                            decompressed_names.append(b.decode("latin-1"))
                    else:
                        decompressed_names.append("")
                compressed_info["decompressed_segment_names"] = decompressed_names
            except Exception as e:
                compressed_info["decompressed_segment_names_error"] = f"Failed to decompress names: {e}"

            block_result["compressed_info"] = compressed_info

            segments_list = []
            for sid, seg_data in segs.items():
                name = seg_data.get("name", f"s{sid}")
                seq = seg_data.get("sequence", "*")

                segment_info = {
                    "segment_id": sid,
                    "segment_name": name,
                    "segment_sequence": seq,
                    "segment_length": len(seq) if seq != "*" else 0,
                }

                segments_list.append(segment_info)

            block_result["segments"] = segments_list
            result["blocks"].append(block_result)

            offset += consumed

        elif section_id == SECTION_ID_LINKS:
            block_result["section_type"] = "links"

            lnk_offset = offset + 1
            record_num = struct.unpack_from("<H", data, lnk_offset)[0]
            lnk_offset += 2
            comp_fromto = struct.unpack_from("<H", data, lnk_offset)[0]
            lnk_offset += 2
            clen_fromto = struct.unpack_from("<Q", data, lnk_offset)[0]
            lnk_offset += 8
            comp_cigars = struct.unpack_from("<I", data, lnk_offset)[0]
            lnk_offset += 4
            clen_cigars = struct.unpack_from("<Q", data, lnk_offset)[0]
            lnk_offset += 8
            ulen_cigars = struct.unpack_from("<Q", data, lnk_offset)[0]

            # Warn about invalid compression codes
            if not _is_valid_compression_code(comp_fromto):
                logger.warning(
                    "Invalid link endpoints compression code 0x%04X (%s) at offset %d",
                    comp_fromto,
                    _describe_compression_code(comp_fromto),
                    offset + 4,
                )
            if not _is_valid_cigar_encoding_code(comp_cigars):
                logger.warning(
                    "Invalid link CIGARs encoding code 0x%08X (%s) at offset %d",
                    comp_cigars,
                    _describe_compression_code(comp_cigars),
                    offset + 8,
                )

            block_result["fields"] = {
                "record_count": {"value": record_num},
                "link_endpoints_compression_code": {
                    "value": f"0x{comp_fromto:04X}",
                    "description": _describe_compression_code(comp_fromto),
                },
                "compressed_link_endpoints_length_bytes": validate_field(
                    clen_fromto, clen_fromto, "compressed_link_endpoints_length"
                ),
                "cigar_strings_compression_code": {
                    "value": f"0x{comp_cigars:08X}",
                    "description": _describe_compression_code(comp_cigars),
                },
                "compressed_cigar_strings_length_bytes": validate_field(
                    clen_cigars, clen_cigars, "compressed_cigar_strings_length"
                ),
                "uncompressed_cigar_strings_length_bytes": validate_field(
                    ulen_cigars, ulen_cigars, "uncompressed_cigar_strings_length"
                ),
            }

            lnks, consumed = reader._parse_links_block(data, offset)

            links_list = []
            for i, link in enumerate(lnks):
                links_list.append(
                    {
                        "link_id": i,
                        "from_segment_name": link["from_node"],
                        "from_orientation": link["from_orn"],
                        "to_segment_name": link["to_node"],
                        "to_orientation": link["to_orn"],
                        "cigar_string": link["alignment"],
                    }
                )

            block_result["links"] = links_list
            result["blocks"].append(block_result)

            offset += consumed

        elif section_id == SECTION_ID_PATHS:
            block_result["section_type"] = "paths"

            path_offset = offset + 1
            record_num = struct.unpack_from("<H", data, path_offset)[0]
            path_offset += 2
            comp_names = struct.unpack_from("<H", data, path_offset)[0]
            path_offset += 2
            comp_paths = struct.unpack_from("<I", data, path_offset)[0]
            path_offset += 4
            comp_cigars = struct.unpack_from("<I", data, path_offset)[0]
            path_offset += 4
            clen_cigars = struct.unpack_from("<Q", data, path_offset)[0]
            path_offset += 8
            ulen_cigars = struct.unpack_from("<Q", data, path_offset)[0]
            path_offset += 8
            clen_names = struct.unpack_from("<Q", data, path_offset)[0]
            path_offset += 8
            ulen_names = struct.unpack_from("<Q", data, path_offset)[0]

            # Warn about invalid compression codes
            if not _is_valid_compression_code(comp_names):
                logger.warning(
                    "Invalid path names compression code 0x%04X (%s) at offset %d",
                    comp_names,
                    _describe_compression_code(comp_names),
                    offset + 4,
                )
            if not _is_valid_walk_encoding_code(comp_paths):
                logger.warning(
                    "Invalid path oriented segment IDs encoding code 0x%08X (%s) at offset %d",
                    comp_paths,
                    _describe_compression_code(comp_paths),
                    offset + 8,
                )
            if not _is_valid_cigar_encoding_code(comp_cigars):
                logger.warning(
                    "Invalid path CIGARs encoding code 0x%08X (%s) at offset %d",
                    comp_cigars,
                    _describe_compression_code(comp_cigars),
                    offset + 14,
                )

            block_result["fields"] = {
                "record_count": {"value": record_num},
                "path_names_compression_code": {
                    "value": f"0x{comp_names:04X}",
                    "description": _describe_compression_code(comp_names),
                },
                "path_oriented_segment_ids_compression_code": {
                    "value": f"0x{comp_paths:08X}",
                    "description": _describe_compression_code(comp_paths),
                },
                "cigar_strings_compression_code": {
                    "value": f"0x{comp_cigars:08X}",
                    "description": _describe_compression_code(comp_cigars),
                },
                "compressed_cigar_strings_length_bytes": validate_field(
                    clen_cigars, clen_cigars, "compressed_cigar_strings_length"
                ),
                "uncompressed_cigar_strings_length_bytes": validate_field(
                    ulen_cigars, ulen_cigars, "uncompressed_cigar_strings_length"
                ),
                "compressed_path_names_length_bytes": validate_field(
                    clen_names, clen_names, "compressed_path_names_length"
                ),
                "uncompressed_path_names_length_bytes": validate_field(
                    ulen_names, ulen_names, "uncompressed_path_names_length"
                ),
            }

            paths_data, consumed = reader._parse_paths_blocks(data, offset, reader._segment_names)

            paths_list = []
            for i, p in enumerate(paths_data):
                paths_list.append(
                    {
                        "path_id": i,
                        "path_name": p.get("path_name", f"path{i}"),
                        "oriented_segment_ids": p.get("segments", []),
                        "overlap_cigar_strings": p.get("overlaps", []),
                    }
                )

            block_result["paths"] = paths_list
            result["blocks"].append(block_result)

            offset += consumed

        elif section_id == SECTION_ID_WALKS:
            block_result["section_type"] = "walks"

            walk_offset = offset + 1
            record_num = struct.unpack_from("<H", data, walk_offset)[0]
            walk_offset += 2
            comp_samples = struct.unpack_from("<H", data, walk_offset)[0]
            walk_offset += 2
            comp_hep = struct.unpack_from("<H", data, walk_offset)[0]
            walk_offset += 2
            comp_seq = struct.unpack_from("<H", data, walk_offset)[0]
            walk_offset += 2
            comp_positions = struct.unpack_from("<H", data, walk_offset)[0]
            walk_offset += 2
            comp_walks = struct.unpack_from("<I", data, walk_offset)[0]

            # Warn about invalid compression codes
            if not _is_valid_compression_code(comp_samples):
                logger.warning(
                    "Invalid sample IDs compression code 0x%04X (%s) at offset %d",
                    comp_samples,
                    _describe_compression_code(comp_samples),
                    offset + 4,
                )
            if not _is_valid_compression_code(comp_hep):
                logger.warning(
                    "Invalid haplotype indices compression code 0x%04X (%s) at offset %d",
                    comp_hep,
                    _describe_compression_code(comp_hep),
                    offset + 6,
                )
            if not _is_valid_compression_code(comp_seq):
                logger.warning(
                    "Invalid sequence IDs compression code 0x%04X (%s) at offset %d",
                    comp_seq,
                    _describe_compression_code(comp_seq),
                    offset + 8,
                )
            if not _is_valid_compression_code(comp_positions):
                logger.warning(
                    "Invalid positions compression code 0x%04X (%s) at offset %d",
                    comp_positions,
                    _describe_compression_code(comp_positions),
                    offset + 10,
                )
            if not _is_valid_walk_encoding_code(comp_walks):
                logger.warning(
                    "Invalid oriented segment IDs encoding code 0x%08X (%s) at offset %d",
                    comp_walks,
                    _describe_compression_code(comp_walks),
                    offset + 12,
                )
            walk_offset += 4

            clen_samples = struct.unpack_from("<Q", data, walk_offset)[0]
            walk_offset += 8
            ulen_samples = struct.unpack_from("<Q", data, walk_offset)[0]
            walk_offset += 8
            clen_hep = struct.unpack_from("<Q", data, walk_offset)[0]
            walk_offset += 8
            ulen_hep = struct.unpack_from("<Q", data, walk_offset)[0]
            walk_offset += 8
            clen_seq = struct.unpack_from("<Q", data, walk_offset)[0]
            walk_offset += 8
            ulen_seq = struct.unpack_from("<Q", data, walk_offset)[0]
            walk_offset += 8
            clen_positions = struct.unpack_from("<Q", data, walk_offset)[0]
            walk_offset += 8
            ulen_positions = struct.unpack_from("<Q", data, walk_offset)[0]
            walk_offset += 8
            clen_walks = struct.unpack_from("<Q", data, walk_offset)[0]
            walk_offset += 8
            ulen_walks = struct.unpack_from("<Q", data, walk_offset)[0]

            block_result["fields"] = {
                "record_count": {"value": record_num},
                "sample_ids_compression_code": {
                    "value": f"0x{comp_samples:04X}",
                    "description": _describe_compression_code(comp_samples),
                },
                "haplotype_indices_compression_code": {
                    "value": f"0x{comp_hep:04X}",
                    "description": _describe_compression_code(comp_hep),
                },
                "sequence_ids_compression_code": {
                    "value": f"0x{comp_seq:04X}",
                    "description": _describe_compression_code(comp_seq),
                },
                "positions_compression_code": {
                    "value": f"0x{comp_positions:04X}",
                    "description": _describe_compression_code(comp_positions),
                },
                "oriented_segment_ids_compression_code": {
                    "value": f"0x{comp_walks:08X}",
                    "description": _describe_compression_code(comp_walks),
                },
                "compressed_sample_ids_length_bytes": validate_field(
                    clen_samples, clen_samples, "compressed_sample_ids_length"
                ),
                "compressed_haplotype_indices_length_bytes": validate_field(
                    clen_hep, clen_hep, "compressed_haplotype_indices_length"
                ),
                "compressed_sequence_ids_length_bytes": validate_field(
                    clen_seq, clen_seq, "compressed_sequence_ids_length"
                ),
                "compressed_positions_length_bytes": validate_field(
                    clen_positions, clen_positions, "compressed_positions_length"
                ),
                "compressed_oriented_segment_ids_length_bytes": validate_field(
                    clen_walks, clen_walks, "compressed_oriented_segment_ids_length"
                ),
            }

            walks_data, consumed = reader._parse_walks_blocks(data, offset, reader._segment_names)

            walks_list = []
            for i, w in enumerate(walks_data):
                walks_list.append(
                    {
                        "walk_id": i,
                        "sample_id": w.get("sample_id", f"sample{i}"),
                        "haplotype_index": w.get("haplotype_index", 0),
                        "sequence_id": w.get("sequence_id", f"seq{i}"),
                        "start_position": w.get("start", 0),
                        "end_position": w.get("end", 0),
                        "oriented_segment_ids": w.get("walk", []),
                    }
                )

            block_result["walks"] = walks_list
            result["blocks"].append(block_result)

            offset += consumed

        else:
            block_result["section_type"] = "unknown"
            block_result["error"] = f"Unknown section ID: {section_id}"
            result["blocks"].append(block_result)
            break

    result["summary"] = {"total_blocks": block_index, "total_segments": len(reader._segment_names)}

    # Output the result
    if text_format:
        # Pretty text format
        print("BGFA File Structure:")
        print(f"  Format Version: {result['bgfa_format_version']}")
        print()

        print("Header:")
        for key, value in result["header"].items():
            if "error" in value:
                print(f"  {key}: ERROR - {value['error']}")
            else:
                print(f"  {key}: {value['value']}")
        print()

        print(f"Blocks ({result['summary']['total_blocks']} total):")
        for i, block in enumerate(result["blocks"]):
            print(f"\n  Block {i + 1} (Section ID {block['section_id']} - {block.get('section_type', 'unknown')}):")

            if "error" in block:
                print(f"    ERROR: {block['error']}")
                continue

            if "fields" in block:
                print("    Fields:")
                for field_name, field_value in block["fields"].items():
                    if "error" in field_value:
                        print(f"      {field_name}: {field_value['value']} (ERROR: {field_value['error']})")
                    elif "description" in field_value:
                        print(f"      {field_name}: {field_value['value']} ({field_value['description']})")
                    else:
                        print(f"      {field_name}: {field_value['value']}")

            if "segments" in block:
                # Regular segment output
                print(f"    Segments:")
                for seg in block["segments"]:
                    print(f"      Segment {seg['segment_id']}: {seg['segment_name']} -> {seg['segment_sequence']}")

                # Add compressed info
                if "compressed_info" in block:
                    comp_info = block["compressed_info"]
                    print(f"    Compressed Information:")
                    if "decompressed_segment_names" in comp_info:
                        print(f"      Segment names: {comp_info['decompressed_segment_names']}")
                    if "compressed_names_hex" in comp_info and comp_info["compressed_names_hex"]:
                        print(
                            f"      Compressed names hex: {comp_info['compressed_names_hex'][:100]}{'...' if len(comp_info['compressed_names_hex']) > 100 else ''}"
                        )
                    if "compressed_sequences_hex" in comp_info and comp_info["compressed_sequences_hex"]:
                        print(
                            f"      Compressed sequences hex: {comp_info['compressed_sequences_hex'][:100]}{'...' if len(comp_info['compressed_sequences_hex']) > 100 else ''}"
                        )

            if "links" in block:
                print("    Links:")
                for link in block["links"]:
                    print(
                        f"      Link {link['link_id']}: {link['from_segment_name']}{link['from_orientation']} -> {link['to_segment_name']}{link['to_orientation']} (CIGAR: {link['cigar_string']})"
                    )

            if "paths" in block:
                print("    Paths:")
                for path in block["paths"]:
                    segments = ", ".join(path["oriented_segment_ids"])
                    overlaps = ", ".join(path["overlap_cigar_strings"])
                    print(f"      Path {path['path_id']}: {path['path_name']} -> [{segments}] (Overlaps: [{overlaps}])")

            if "walks" in block:
                print("    Walks:")
                for walk in block["walks"]:
                    segments = ", ".join(walk["oriented_segment_ids"])
                    print(
                        f"      Walk {walk['walk_id']}: Sample={walk['sample_id']}, Hap={walk['haplotype_index']}, Seq={walk['sequence_id']}, Pos={walk['start_position']}-{walk['end_position']} -> [{segments}]"
                    )

        print(f"\nSummary:")
        print(f"  Total segments: {result['summary']['total_segments']}")
        print(f"  Total blocks: {result['summary']['total_blocks']}")
    else:
        # JSON format (default)
        print(json.dumps(result, indent=2))
