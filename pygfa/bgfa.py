"""
Binary GFA (BGFA) serialization module.
Strictly following the specification in spec/gfa_binary_format.md.
"""

from __future__ import annotations

import gzip
import io
import logging
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
    decompress_string_cigar,
    decompress_string_cigar_decomposed,
)
from pygfa.encoding.dictionary_encoding import (
    decompress_string_dictionary,
)
from pygfa.encoding.lz4_codec import (
    decompress_string_lz4,
)
from pygfa.encoding.brotli_codec import (
    decompress_string_brotli,
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
STRING_ENCODING_CIGAR = StringEncoding.CIGAR
STRING_ENCODING_DICTIONARY = StringEncoding.DICTIONARY
STRING_ENCODING_ZSTD_DICT = StringEncoding.ZSTD_DICT
STRING_ENCODING_LZ4 = StringEncoding.LZ4
STRING_ENCODING_BROTLI = StringEncoding.BROTLI
STRING_ENCODING_PPM = StringEncoding.PPM
STRING_ENCODING_SUPERSTRING_NONE = StringEncoding.SUPERSTRING_NONE
STRING_ENCODING_SUPERSTRING_HUFFMAN = StringEncoding.SUPERSTRING_HUFFMAN
STRING_ENCODING_SUPERSTRING_2BIT = StringEncoding.SUPERSTRING_2BIT
STRING_ENCODING_SUPERSTRING_PPM = StringEncoding.SUPERSTRING_PPM

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


def _decompress_string_cigar_with_metadata(payload: bytes, record_num: int, int_decoder: Callable) -> list[bytes]:
    """Decode CIGAR strings with metadata (lengths prefix)."""
    # First decode the lengths metadata
    lengths, consumed = int_decoder(payload, record_num)
    # Then decode the CIGAR blob
    cigar_blob = payload[consumed:]
    return decompress_string_cigar(cigar_blob, lengths)


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
        # Fallback: identity for unsupported encodings
        return lambda x: x


def _decompress_cigar_payload(comp_code: int, payload: bytes, record_num: int, int_decoder: Callable) -> list[bytes]:
    """Decode CIGAR strings, dispatching on 2-byte vs 4-byte strategy code.

    For 2-byte codes (0x??09): uses standard string encoding with metadata lengths.
    For 4-byte code 0x01??????: uses numOperations+lengths+operations decomposition.
    For 4-byte code 0x02??????: treats as plain compressed string.
    """
    byte1 = (comp_code >> 24) & 0xFF if comp_code > 0xFFFF else 0
    if byte1 == CIGAR_DECOMPOSITION_NUM_OPS_LENGTHS_OPS:
        byte2 = (comp_code >> 16) & 0xFF  # int encoding for op counts
        byte3 = (comp_code >> 8) & 0xFF  # int encoding for lengths
        byte4 = comp_code & 0xFF  # string encoding for packed ops
        num_ops_decoder = get_integer_decoder_from_code(byte2)
        lengths_decoder = get_integer_decoder_from_code(byte3)
        ops_decoder = _ops_string_decoder_for_code(byte4)
        return decompress_string_cigar_decomposed(payload, record_num, num_ops_decoder, lengths_decoder, ops_decoder)
    elif byte1 == CIGAR_DECOMPOSITION_STRING:
        byte2 = (comp_code >> 16) & 0xFF
        str_dec = STRING_DECODERS.get(byte2, decompress_string_none)
        return str_dec(payload, record_num, get_integer_decoder_from_code(0x01))
    else:
        int_dec = get_integer_decoder(comp_code)
        str_dec = STRING_DECODERS.get(comp_code & 0xFF, decompress_string_none)
        return str_dec(payload, record_num, int_dec)


def decompress_string_superstring_none(payload: bytes, record_num: int, int_decoder: Callable) -> list[bytes]:
    """Decode superstring with no compression."""
    starts, consumed1 = int_decoder(payload, record_num)
    ends, consumed2 = int_decoder(payload[consumed1:], record_num)
    blob = payload[consumed1 + consumed2 :]
    return [blob[s:e] for s, e in zip(starts, ends)]


def decompress_string_superstring_huffman(payload: bytes, record_num: int, int_decoder: Callable) -> list[bytes]:
    """Decode superstring with Huffman compression."""
    starts, consumed1 = int_decoder(payload, record_num)
    ends, consumed2 = int_decoder(payload[consumed1:], record_num)
    remaining = payload[consumed1 + consumed2 :]
    super_len = max(ends) if ends else 0
    from pygfa.encoding.huffman_nibble import decompress_nibble_huffman

    superstring = decompress_nibble_huffman(remaining, int_decoder, super_len * 2)
    return [superstring[s:e] for s, e in zip(starts, ends)]


def decompress_string_superstring_2bit(payload: bytes, record_num: int, int_decoder: Callable) -> list[bytes]:
    """Decode superstring with 2-bit DNA compression."""
    starts, consumed1 = int_decoder(payload, record_num)
    ends, consumed2 = int_decoder(payload[consumed1:], record_num)
    remaining = payload[consumed1 + consumed2 :]
    super_len = max(ends) if ends else 0
    superstring_list = decompress_string_2bit_dna(remaining, [super_len])
    superstring = superstring_list[0] if superstring_list else b""
    return [superstring[s:e] for s, e in zip(starts, ends)]


def decompress_string_superstring_ppm(payload: bytes, record_num: int, int_decoder: Callable) -> list[bytes]:
    """Decode superstring with PPM compression."""
    starts, consumed1 = int_decoder(payload, record_num)
    ends, consumed2 = int_decoder(payload[consumed1:], record_num)
    remaining = payload[consumed1 + consumed2 :]
    super_len = max(ends) if ends else 0
    superstring_list = decompress_string_ppm(remaining, [super_len])
    superstring = superstring_list[0] if superstring_list else b""
    return [superstring[s:e] for s, e in zip(starts, ends)]


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


STRING_DECODERS = {
    STRING_ENCODING_NONE: decompress_string_none,
    STRING_ENCODING_ZSTD: decompress_string_zstd,
    STRING_ENCODING_GZIP: decompress_string_gzip,
    STRING_ENCODING_LZMA: decompress_string_lzma,
    STRING_ENCODING_HUFFMAN: decompress_string_huffman,
    STRING_ENCODING_2BIT_DNA: decompress_string_2bit_dna_strings,
    STRING_ENCODING_ARITHMETIC: lambda p, rn, id: decompress_string_arithmetic(p, [0] * rn),
    STRING_ENCODING_BWT_HUFFMAN: lambda p, rn, id: decompress_string_bwt_huffman(p, [0] * rn),
    STRING_ENCODING_RLE: lambda p, rn, id: decompress_string_rle(p, [0] * rn),
    STRING_ENCODING_CIGAR: lambda p, rn, id: _decompress_string_cigar_with_metadata(p, rn, id),
    STRING_ENCODING_DICTIONARY: lambda p, rn, id: decompress_string_dictionary(p, [0] * rn),
    STRING_ENCODING_ZSTD_DICT: decompress_string_none,
    STRING_ENCODING_LZ4: lambda p, rn, id: decompress_string_lz4(p, [0] * rn),
    STRING_ENCODING_BROTLI: lambda p, rn, id: decompress_string_brotli(p, [0] * rn),
    STRING_ENCODING_PPM: lambda p, rn, id: decompress_string_ppm(p, [0] * rn, id),
    STRING_ENCODING_SUPERSTRING_NONE: decompress_string_superstring_none,
    STRING_ENCODING_SUPERSTRING_HUFFMAN: decompress_string_superstring_huffman,
    STRING_ENCODING_SUPERSTRING_2BIT: decompress_string_superstring_2bit,
    STRING_ENCODING_SUPERSTRING_PPM: decompress_string_superstring_ppm,
}


# =============================================================================
# String Compression Helper
# =============================================================================


def _compress_string_for_bgfa(string_list: list[str], compression_code: int) -> bytes:
    """Compress a list of strings using the specified compression code."""
    str_encoding = compression_code & 0xFF
    int_encoding = (compression_code >> 8) & 0xFF
    int_encoder = get_integer_encoder(compression_code)

    from pygfa.encoding.string_encoding import compress_string_list, compress_string_list_superstring

    # Superstring encodings (0xF0+)
    if str_encoding >= 0xF0:
        method = "none"
        if str_encoding == STRING_ENCODING_SUPERSTRING_HUFFMAN:
            method = "huffman"
        elif str_encoding == STRING_ENCODING_SUPERSTRING_2BIT:
            method = "2bit"
        return compress_string_list_superstring(string_list, int_encoder, method, first_byte_strategy=int_encoding)

    # Concatenation encodings
    method_map = {
        STRING_ENCODING_NONE: "none",
        STRING_ENCODING_ZSTD: "zstd",
        STRING_ENCODING_GZIP: "gzip",
        STRING_ENCODING_LZMA: "lzma",
        STRING_ENCODING_HUFFMAN: "huffman",
        STRING_ENCODING_2BIT_DNA: "2bit",
        STRING_ENCODING_RLE: "rle",
        STRING_ENCODING_CIGAR: "cigar",
        STRING_ENCODING_DICTIONARY: "dictionary",
        STRING_ENCODING_LZ4: "lz4",
        STRING_ENCODING_BROTLI: "brotli",
        STRING_ENCODING_PPM: "ppm",
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
        names = [b.decode("ascii") for b in names_bytes]

        # Parse sequences payload
        seqs_payload = data[offset + clen_names : offset + clen_names + clen_str]
        int_dec_str = get_integer_decoder(comp_str)
        str_dec_str = STRING_DECODERS.get(comp_str & 0xFF, decompress_string_none)
        seqs_bytes = str_dec_str(seqs_payload, record_num, int_dec_str)

        # Build segments dict with names
        segments = {}
        for i in range(record_num):
            name = names[i] if i < len(names) else f"s{i}"
            seq = seqs_bytes[i].decode("ascii") if i < len(seqs_bytes) and seqs_bytes[i] else "*"
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
                    "alignment": cigars_bytes[i].decode("ascii") if i < len(cigars_bytes) else "*",
                }
            )

        bytes_consumed = (offset + clen_fromto + clen_cigars) - start_offset
        return links, bytes_consumed

    def _decode_walk(
        self, walk_data: bytes, record_num: int, walk_compression: int, int_decoder: Callable, segment_names: list[str]
    ) -> list[list[str]]:
        """Decode walk data according to 4-byte walk strategy code.

        Walk compression codes (4 bytes):
        - 0x00??????: none (identity)
        - 0x01??????: orientation + strid (string IDs)
        - 0x02??????: orientation + numid (numeric IDs)

        :param walk_data: Raw walk data bytes
        :param record_num: Number of walk records
        :param walk_compression: 4-byte walk compression code
        :param int_decoder: Integer decoder function
        :param segment_names: List of segment names for ID lookup
        :return: List of walks, each walk is a list of oriented segment IDs
        """
        if record_num == 0:
            return []

        if walk_compression == 0:
            # No walk data - return empty walks
            return [[] for _ in range(record_num)]

        walk_byte = (walk_compression >> 24) & 0xFF
        # bytes 2-4 are for future use, currently ignored
        # byte 2 would be for orientation bit count (usually 0x00)
        # bytes 3-4 would be for ID encoding strategy

        if walk_byte == 0x00:
            # None/identity - walk data is already decoded as strings
            # This shouldn't happen in practice as walks need orientation
            raise NotImplementedError("Walk encoding 0x00 (none) not supported")
        elif walk_byte == 0x01:
            # orientation + strid: orientation bits + string segment IDs
            # First decode orientation bits
            orientations, consumed = unpack_bits_lsb(walk_data, record_num)
            # Then decode segment ID strings from remaining data
            # For strid, we need to decode as strings
            str_enc_code = walk_compression & 0xFFFF
            str_decoder = STRING_DECODERS.get(str_enc_code & 0xFF, decompress_string_none)
            int_enc_for_strings = (str_enc_code >> 8) & 0xFF
            int_decoder_for_strings = INTEGER_DECODERS.get(int_enc_for_strings, decode_integer_list_varint)

            # Decode the segment ID strings
            segment_id_strings, _ = str_decoder(walk_data[consumed:], record_num, int_decoder_for_strings)

            # Combine orientations with segment IDs
            walks = []
            for i in range(record_num):
                seg_id = segment_id_strings[i].decode("ascii") if i < len(segment_id_strings) else ""
                orn = "-" if orientations[i] else "+"
                walks.append(f"{seg_id}{orn}")
            return walks
        elif walk_byte == 0x02:
            # orientation + numid: orientation bits + numeric segment IDs
            # First decode orientation bits
            orientations, consumed = unpack_bits_lsb(walk_data, record_num)
            # Then decode numeric segment IDs
            int_enc_code = walk_compression & 0xFFFF
            int_decoder_func = INTEGER_DECODERS.get(int_enc_code & 0xFF, decode_integer_list_varint)
            segment_ids, _ = int_decoder_func(walk_data[consumed:], record_num)

            # Combine orientations with segment IDs (convert to names)
            walks = []
            for i in range(record_num):
                seg_idx = segment_ids[i]
                seg_name = segment_names[seg_idx] if 0 <= seg_idx < len(segment_names) else f"s{seg_idx}"
                orn = "-" if orientations[i] else "+"
                walks.append(f"{seg_name}{orn}")
            return walks
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
        # We need to decode the walk for each path
        # The walk compression is given by comp_paths (4 bytes)
        # For paths, the walk is encoded as oriented segment IDs
        walks_start = offset
        walks = self._decode_walk(
            data[walks_start:], record_num, comp_paths, get_integer_decoder(comp_paths & 0xFF), segment_names
        )

        # Build paths list
        paths = []
        for i in range(record_num):
            path_name = path_names[i].decode("ascii") if i < len(path_names) else f"path{i}"
            cigar = cigar_bytes[i].decode("ascii") if i < len(cigar_bytes) else "*"
            segments = walks[i] if i < len(walks) else []

            paths.append({"path_name": path_name, "segments": segments, "overlaps": [cigar] if cigar != "*" else []})

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
        walks = self._decode_walk(walks_payload, record_num, comp_walks, int_dec_walks, segment_names)
        offset += clen_walks

        # Build walks list
        walks_list = []
        for i in range(record_num):
            sample_id = sample_ids[i].decode("ascii") if i < len(sample_ids) else f"sample{i}"
            hap_idx = hap_indices[i] if i < len(hap_indices) else 0
            seq_id = sequence_ids[i].decode("ascii") if i < len(sequence_ids) else f"seq{i}"
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
        self._comp_options = comp_options or {}
        self._segment_map = {}

    def _write_header(self, buf: io.BytesIO) -> None:
        """Write the BGFA file header."""
        header_text = b"H\tVN:Z:1.0"
        buf.write(struct.pack("<I", BGFA_MAGIC))
        buf.write(struct.pack("<H", BGFA_VERSION))
        buf.write(struct.pack("<H", len(header_text)))
        buf.write(header_text)
        buf.write(b"\0")  # Null terminator

    def _write_segments_block(self, buf: io.BytesIO, chunk: list[tuple], names_enc: int, seqs_enc: int) -> None:
        """Write a segments block.

        New spec format: Segment names and sequences in single block with separate encodings.
        Chunk is a list of (name, segment_id) tuples.
        Payload layout: [names encoded][sequences encoded]
        """
        nodes_data = dict(self._gfa.nodes(data=True))

        names = [name for name, sid in chunk]
        seqs = []
        for name, sid in chunk:
            s = nodes_data[name].get("sequence", "*")
            if s is None or s == "":
                s = "*"
            seqs.append(s)

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

    def _write_links_block(self, buf: io.BytesIO, chunk: list, c_ft: int, c_cig: int) -> None:
        """Write a links block.

        Payload layout: [from_ids][to_ids][from_orientation][to_orientation][cigar_strings]
        """
        f_ids = []
        t_ids = []
        f_os = []
        t_os = []
        cigs = []

        for u, v, k, d in chunk:
            fn = d.get("from_node", u)
            tn = d.get("to_node", v)
            f_ids.append(self._segment_map.get(fn, 0) + 1)  # 1-based for links
            t_ids.append(self._segment_map.get(tn, 0) + 1)
            f_os.append(0 if d.get("from_orn", "+") == "+" else 1)
            t_os.append(0 if d.get("to_orn", "+") == "+" else 1)
            cigs.append(d.get("alignment", "*"))

        # Encode from/to IDs and orientations
        int_encoder = get_integer_encoder(c_ft)
        p_from = int_encoder(f_ids)
        p_to = int_encoder(t_ids)
        p_f_or = pack_bits_lsb(f_os)
        p_t_or = pack_bits_lsb(t_os)
        p_ft = p_from + p_to + p_f_or + p_t_or

        # Encode cigars
        p_cig = _compress_string_for_bgfa(cigs, c_cig)

        buf.write(struct.pack("<B", SECTION_ID_LINKS))
        buf.write(struct.pack("<H", len(chunk)))
        buf.write(struct.pack("<H", c_ft))
        buf.write(struct.pack("<Q", len(p_ft)))
        buf.write(struct.pack("<I", c_cig))
        buf.write(struct.pack("<Q", len(p_cig)))
        buf.write(struct.pack("<Q", sum(len(c) for c in cigs)))
        buf.write(p_ft + p_cig)

    def to_bgfa(self, verbose: bool = False, debug: bool = False, logfile: str = None, **kwargs) -> bytes:
        """Convert GFA to BGFA format.

        New spec: Single segments block containing both names and sequences.
        No separate segment names block.
        """
        # Apply compression options from kwargs
        for k, v in kwargs.items():
            if k.endswith("_enc"):
                self._comp_options[k] = parse_compression_strategy(v)

        buf = io.BytesIO()

        # Write header
        self._write_header(buf)

        # Build segment map
        names = list(self._gfa.nodes())
        self._segment_map = {n: i for i, n in enumerate(names)}

        # Write single segments block with names and sequences
        # No block_size chunking in new spec
        names_enc = self._comp_options.get(
            "names_enc", make_compression_code(INTEGER_ENCODING_VARINT, STRING_ENCODING_NONE)
        )
        seqs_enc = self._comp_options.get(
            "seq_enc", make_compression_code(INTEGER_ENCODING_VARINT, STRING_ENCODING_2BIT_DNA)
        )

        sorted_segs = [(name, i) for i, name in enumerate(names)]
        self._write_segments_block(buf, sorted_segs, names_enc, seqs_enc)

        # Write links blocks
        edges = list(self._gfa.edges(data=True, keys=True))
        links_ft_enc = self._comp_options.get(
            "links_fromto_enc", make_compression_code(INTEGER_ENCODING_VARINT, STRING_ENCODING_NONE)
        )
        links_cig_enc = self._comp_options.get(
            "links_cigars_enc", make_compression_code(INTEGER_ENCODING_VARINT, STRING_ENCODING_CIGAR)
        )

        for i in range(0, len(edges), self._block_size):
            chunk = edges[i : i + self._block_size]
            self._write_links_block(buf, chunk, links_ft_enc, links_cig_enc)

        return buf.getvalue()


# =============================================================================
# Public API
# =============================================================================


def parse_compression_strategy(s: str) -> int:
    """Parse a compression strategy string into a code.

    Format: "int_encoding-str_encoding" (e.g., "varint-2bit")
    """
    from pygfa.encoding.enums import IntegerEncoding, StringEncoding

    p = re.split(r"[-_]", s.lower())

    i_map = {e.name.lower().replace("_", ""): e.value for e in IntegerEncoding}
    s_map = {e.name.lower().replace("_", ""): e.value for e in StringEncoding}

    # Aliases
    i_map["identity"] = 0
    s_map["identity"] = 0
    s_map["2bit"] = 5

    int_enc = i_map.get(p[0], INTEGER_ENCODING_VARINT)
    str_enc = s_map.get(p[1] if len(p) > 1 else "none", STRING_ENCODING_NONE)

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


def measure_bgfa(input_file: str, output_file: str, verbose: bool = False, debug: bool = False) -> None:
    """Measure BGFA file statistics.

    :param input_file: Path to input BGFA file
    :param output_file: Path to output CSV file
    :param verbose: Enable verbose logging of everything read from the file
    :param debug: Enable debug logging
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

            stats.append({
                "block_index": block_index,
                "section_id": section_id,
                "section_type": "segments",
                "record_num": record_num,
                "compressed_length": clen_names + clen_str,
                "uncompressed_length": ulen_names + ulen_str,
            })
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
                    logger.info("    [%d] %s%s -> %s%s  %s", i, link["from_node"], link["from_orn"], link["to_node"], link["to_orn"], link["alignment"])

            stats.append({
                "block_index": block_index,
                "section_id": section_id,
                "section_type": "links",
                "record_num": record_num,
                "compressed_length": clen_fromto + clen_cigars,
                "uncompressed_length": ulen_cigars,
            })
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
                    logger.info("    [%d] %s: %s  overlaps=%s", i, p.get("path_name", "?"), segments_str, p.get("overlaps", []))

            stats.append({
                "block_index": block_index,
                "section_id": section_id,
                "section_type": "paths",
                "record_num": record_num,
                "compressed_length": clen_names + clen_cigars,
                "uncompressed_length": ulen_names + ulen_cigars,
            })
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
                    logger.info("    [%d] sample=%s hap=%s seq=%s start=%s end=%s: %s", i, w.get("sample_id", "?"), w.get("haplotype_index", "?"), w.get("sequence_id", "?"), w.get("start", "?"), w.get("end", "?"), walk_str)

            total_compressed = clen_samples + clen_hep + clen_seq + clen_positions + clen_walks
            total_uncompressed = ulen_samples + ulen_hep + ulen_seq + ulen_positions + ulen_walks
            stats.append({
                "block_index": block_index,
                "section_id": section_id,
                "section_type": "walks",
                "record_num": record_num,
                "compressed_length": total_compressed,
                "uncompressed_length": total_uncompressed,
            })
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

    # Write CSV
    with open(output_file, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=["block_index", "section_id", "section_type", "record_num", "compressed_length", "uncompressed_length"])
        writer.writeheader()
        writer.writerows(stats)
