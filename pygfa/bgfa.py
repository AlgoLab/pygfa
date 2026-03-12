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
    compress_integer_list_fixed,
    compress_integer_list_none,
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
from pygfa.gfa import GFA

# =============================================================================
# Constants
# =============================================================================

# Magic number: "BGFA" in little-endian = 0x41464742
BGFA_MAGIC = 0x41464742
BGFA_VERSION = 1
DEFAULT_BLOCK_SIZE = 1024

# Section IDs
SECTION_ID_SEGMENT_NAMES = 1
SECTION_ID_SEGMENTS = 2
SECTION_ID_LINKS = 3
SECTION_ID_PATHS = 4
SECTION_ID_WALKS = 5

# Integer Strategies (High Byte)
INTEGER_ENCODING_NONE = 0x00
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
INTEGER_ENCODING_IDENTITY = INTEGER_ENCODING_NONE

# String Strategies (Low Byte)
STRING_ENCODING_NONE = 0x00
STRING_ENCODING_IDENTITY = STRING_ENCODING_NONE
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
STRING_ENCODING_LZ4 = 0x0C
STRING_ENCODING_BROTLI = 0x0D
STRING_ENCODING_PPM = 0x0E
STRING_ENCODING_SUPERSTRING_NONE = 0xF0
STRING_ENCODING_SUPERSTRING_HUFFMAN = 0xF4
STRING_ENCODING_SUPERSTRING_2BIT = 0xF5

# Walk/CIGAR decomposition strategies (for 4-byte codes)
WALK_DECOMPOSITION_NONE = 0x00
WALK_DECOMPOSITION_ORIENTATION_STRID = 0x01
WALK_DECOMPOSITION_ORIENTATION_NUMID = 0x02

CIGAR_DECOMPOSITION_NONE = 0x00
CIGAR_DECOMPOSITION_NUM_OPS_LENGTHS_OPS = 0x01
CIGAR_DECOMPOSITION_STRING = 0x02

logger = logging.getLogger(__name__)


# =============================================================================
# Utility Functions
# =============================================================================

def make_compression_code(int_enc: int, str_enc: int) -> int:
    """Create a 2-byte compression code from integer and string encodings."""
    return ((int_enc & 0xFF) << 8) | (str_enc & 0xFF)


def make_4byte_code(byte1: int, byte2: int, byte3: int, byte4: int) -> int:
    """Create a 4-byte strategy code."""
    return (byte1 << 24) | (byte2 << 16) | (byte3 << 8) | byte4


def split_compression_code(code: int) -> tuple[int, int]:
    """Split a 2-byte compression code into integer and string encodings."""
    return (code >> 8) & 0xFF, code & 0xFF


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
                val |= (1 << bit_idx)  # LSB-first
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


INTEGER_DECODERS = {
    INTEGER_ENCODING_NONE: decode_integer_list_none,
    INTEGER_ENCODING_VARINT: decode_integer_list_varint,
    INTEGER_ENCODING_FIXED16: decode_integer_list_fixed16,
    INTEGER_ENCODING_FIXED32: decode_integer_list_fixed32,
    INTEGER_ENCODING_FIXED64: decode_integer_list_fixed64,
    INTEGER_ENCODING_DELTA: decode_integer_list_delta,
}


def get_integer_decoder(code: int) -> Callable:
    """Get the integer decoder function for a compression code."""
    int_code = (code >> 8) & 0xFF
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
    
    return compress_integer_list_varint


# =============================================================================
# String Decompression Functions
# =============================================================================

def decompress_string_none_from_blob(blob: bytes, lengths: list[int]) -> list[bytes]:
    """Extract strings from a blob given their lengths."""
    result = []
    pos = 0
    for length in lengths:
        result.append(blob[pos:pos + length])
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


def decompress_string_superstring_none(payload: bytes, record_num: int, int_decoder: Callable) -> list[bytes]:
    """Decode superstring with no compression."""
    starts, consumed1 = int_decoder(payload, record_num)
    ends, consumed2 = int_decoder(payload[consumed1:], record_num)
    blob = payload[consumed1 + consumed2:]
    return [blob[s:e] for s, e in zip(starts, ends)]


def decompress_string_superstring_huffman(payload: bytes, record_num: int, int_decoder: Callable) -> list[bytes]:
    """Decode superstring with Huffman compression."""
    starts, consumed1 = int_decoder(payload, record_num)
    ends, consumed2 = int_decoder(payload[consumed1:], record_num)
    remaining = payload[consumed1 + consumed2:]
    super_len = max(ends) if ends else 0
    from pygfa.encoding.huffman_nibble import decompress_nibble_huffman
    superstring = decompress_nibble_huffman(remaining, int_decoder, super_len * 2)
    return [superstring[s:e] for s, e in zip(starts, ends)]


def decompress_string_superstring_2bit(payload: bytes, record_num: int, int_decoder: Callable) -> list[bytes]:
    """Decode superstring with 2-bit DNA compression."""
    starts, consumed1 = int_decoder(payload, record_num)
    ends, consumed2 = int_decoder(payload[consumed1:], record_num)
    remaining = payload[consumed1 + consumed2:]
    super_len = max(ends) if ends else 0
    superstring_list = decompress_string_2bit_dna(remaining, [super_len])
    superstring = superstring_list[0] if superstring_list else b""
    return [superstring[s:e] for s, e in zip(starts, ends)]


STRING_DECODERS = {
    STRING_ENCODING_NONE: decompress_string_none,
    STRING_ENCODING_ZSTD: decompress_string_zstd,
    STRING_ENCODING_GZIP: decompress_string_gzip,
    STRING_ENCODING_LZMA: decompress_string_lzma,
    STRING_ENCODING_HUFFMAN: decompress_string_huffman,
    STRING_ENCODING_2BIT_DNA: decompress_string_2bit_dna_strings,
    STRING_ENCODING_ARITHMETIC: lambda p, rn, id: decompress_string_arithmetic(p, [0]*rn),
    STRING_ENCODING_BWT_HUFFMAN: lambda p, rn, id: decompress_string_bwt_huffman(p, [0]*rn),
    STRING_ENCODING_RLE: lambda p, rn, id: decompress_string_rle(p, [0]*rn),
    STRING_ENCODING_CIGAR: lambda p, rn, id: _decompress_string_cigar_with_metadata(p, rn, id),
    STRING_ENCODING_DICTIONARY: lambda p, rn, id: decompress_string_dictionary(p, [0]*rn),
    STRING_ENCODING_ZSTD_DICT: decompress_string_none,
    STRING_ENCODING_LZ4: lambda p, rn, id: decompress_string_lz4(p, [0]*rn),
    STRING_ENCODING_BROTLI: lambda p, rn, id: decompress_string_brotli(p, [0]*rn),
    STRING_ENCODING_PPM: lambda p, rn, id: decompress_string_ppm(p, [0]*rn),
    STRING_ENCODING_SUPERSTRING_NONE: decompress_string_superstring_none,
    STRING_ENCODING_SUPERSTRING_HUFFMAN: decompress_string_superstring_huffman,
    STRING_ENCODING_SUPERSTRING_2BIT: decompress_string_superstring_2bit,
}


# =============================================================================
# String Compression Helper
# =============================================================================

def _compress_string_for_bgfa(string_list: list[str], compression_code: int) -> bytes:
    """Compress a list of strings using the specified compression code."""
    str_encoding = compression_code & 0xFF
    int_encoding = (compression_code >> 8) & 0xFF
    int_encoder = get_integer_encoder(compression_code)
    
    from pygfa.encoding.string_encoding import (
        compress_string_list, compress_string_list_superstring
    )
    
    # Superstring encodings (0xF0+)
    if str_encoding >= 0xF0:
        method = "none"
        if str_encoding == STRING_ENCODING_SUPERSTRING_HUFFMAN:
            method = "huffman"
        elif str_encoding == STRING_ENCODING_SUPERSTRING_2BIT:
            method = "2bit"
        return compress_string_list_superstring(
            string_list, int_encoder, method, first_byte_strategy=int_encoding
        )
    
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

        header_text = data[8:8+header_len].decode("ascii")

        return {
            "magic": magic,
            "version": version,
            "header": header_text,
            "header_text": header_text,  # Alias for backward compatibility
            "header_size": 8 + header_len + 1
        }
    
    def _parse_segment_names_block(self, data: bytes, start_offset: int) -> tuple[list[str], int]:
        """Parse a segment names block."""
        offset = start_offset + 1  # Skip section_id
        
        record_num = struct.unpack_from("<H", data, offset)[0]
        offset += 2
        
        compression = struct.unpack_from("<H", data, offset)[0]
        offset += 2
        
        compressed_len = struct.unpack_from("<Q", data, offset)[0]
        offset += 8
        
        _ = struct.unpack_from("<Q", data, offset)[0]  # uncompressed_len (not used)
        offset += 8
        
        payload = data[offset:offset + compressed_len]
        
        int_decoder = get_integer_decoder(compression)
        str_decoder = STRING_DECODERS.get(compression & 0xFF, decompress_string_none)
        
        names_bytes = str_decoder(payload, record_num, int_decoder)
        names = [b.decode("ascii") for b in names_bytes]
        
        bytes_consumed = (offset + compressed_len) - start_offset
        return names, bytes_consumed
    
    def _parse_segments_block(self, data: bytes, start_offset: int) -> tuple[dict, int]:
        """Parse a segments block.
        
        Payload layout: [segment_ids encoded][sequences encoded]
        """
        offset = start_offset + 1
        
        record_num = struct.unpack_from("<H", data, offset)[0]
        offset += 2
        
        compression = struct.unpack_from("<H", data, offset)[0]
        offset += 2
        
        compressed_len = struct.unpack_from("<Q", data, offset)[0]
        offset += 8
        
        _ = struct.unpack_from("<Q", data, offset)[0]  # uncompressed_len (not used)
        offset += 8
        
        payload = data[offset:offset + compressed_len]
        
        int_decoder = get_integer_decoder(compression)
        str_decoder = STRING_DECODERS.get(compression & 0xFF, decompress_string_none)
        
        # Parse segment IDs
        ids, ids_consumed = int_decoder(payload, record_num)
        
        # Parse sequences
        seqs_bytes = str_decoder(payload[ids_consumed:], record_num, int_decoder)
        
        segments = {}
        for i in range(record_num):
            seq = seqs_bytes[i].decode("ascii") if i < len(seqs_bytes) else "*"
            if not seq:
                seq = "*"
            segments[ids[i]] = {"sequence": seq}
        
        bytes_consumed = (offset + compressed_len) - start_offset
        return segments, bytes_consumed
    
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
        
        comp_cigars = struct.unpack_from("<H", data, offset)[0]
        offset += 2
        
        clen_cigars = struct.unpack_from("<Q", data, offset)[0]
        offset += 8
        
        _ = struct.unpack_from("<Q", data, offset)[0]  # uncompressed_cigars_len (not used)
        offset += 8
        
        # Parse fromto payload: [from_ids][to_ids][from_orientation][to_orientation]
        fromto_payload = data[offset:offset + clen_fromto]
        int_dec_fromto = get_integer_decoder(comp_fromto)
        
        from_ids, c1 = int_dec_fromto(fromto_payload, record_num)
        to_ids, c2 = int_dec_fromto(fromto_payload[c1:], record_num)
        
        f_orns, c3 = unpack_bits_lsb(fromto_payload[c1 + c2:], record_num)
        t_orns, c4 = unpack_bits_lsb(fromto_payload[c1 + c2 + c3:], record_num)
        
        # Parse cigar strings
        cigar_payload = data[offset + clen_fromto:offset + clen_fromto + clen_cigars]
        int_dec_cigars = get_integer_decoder(comp_cigars)
        str_dec_cigars = STRING_DECODERS.get(comp_cigars & 0xFF, decompress_string_none)
        cigars_bytes = str_dec_cigars(cigar_payload, record_num, int_dec_cigars)
        
        # Build links list
        # Note: Links use 1-based segment IDs (0 is reserved for "no connection")
        links = []
        for i in range(record_num):
            # Convert 1-based IDs to 0-based for lookup
            from_idx = from_ids[i] - 1
            to_idx = to_ids[i] - 1
            
            from_name = self._segment_names[from_idx] if 0 <= from_idx < len(self._segment_names) else f"s{from_ids[i]}"
            to_name = self._segment_names[to_idx] if 0 <= to_idx < len(self._segment_names) else f"s{to_ids[i]}"
            
            links.append({
                "from_node": from_name,
                "to_node": to_name,
                "from_orn": "-" if f_orns[i] else "+",
                "to_orn": "-" if t_orns[i] else "+",
                "alignment": cigars_bytes[i].decode("ascii") if i < len(cigars_bytes) else "*"
            })
        
        bytes_consumed = (offset + clen_fromto + clen_cigars) - start_offset
        return links, bytes_consumed
    
    def read_bgfa(self, file_path: str, verbose: bool = False, debug: bool = False, 
                  logfile: str = None, skip_payloads: bool = False) -> GFA:
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

        while offset < len(data):
            section_id = data[offset]

            if section_id == SECTION_ID_SEGMENT_NAMES:
                if skip_payloads:
                    # Skip block payload but advance offset correctly
                    try:
                        _, consumed = self._skip_block(data, offset)
                    except ValueError:
                        # Truncated file - stop reading
                        break
                    offset += consumed
                else:
                    names, consumed = self._parse_segment_names_block(data, offset)
                    self._segment_names.extend(names)
                    offset += consumed

            elif section_id == SECTION_ID_SEGMENTS:
                if skip_payloads:
                    try:
                        _, consumed = self._skip_block(data, offset)
                    except ValueError:
                        break
                    offset += consumed
                else:
                    segs, consumed = self._parse_segments_block(data, offset)
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
                    # TODO: Implement paths parsing
                    logger.warning("Paths section not yet implemented")
                    break

            elif section_id == SECTION_ID_WALKS:
                if skip_payloads:
                    try:
                        _, consumed = self._skip_block(data, offset)
                    except ValueError:
                        break
                    offset += consumed
                else:
                    # TODO: Implement walks parsing
                    logger.warning("Walks section not yet implemented")
                    break

            else:
                logger.warning(f"Unknown section ID: {section_id}")
                break

        # Build GFA object
        from pygfa.graph_element.node import Node
        from pygfa.graph_element.edge import Edge

        gfa = GFA()
        
        # Store header info in GFA object
        gfa._header_info = {
            "version": header["version"],
            "header_text": header["header_text"]
        }

        # Only add nodes and edges if not skipping payloads
        if not skip_payloads:
            # Add nodes
            for name in self._segment_names:
                gfa.add_node(Node(name, "*"))

            # Add sequences to nodes
            for sid, seg_data in segments.items():
                if sid < len(self._segment_names):
                    name = self._segment_names[sid]
                    gfa._graph.nodes[name]["sequence"] = seg_data["sequence"]

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
                    alignment=link["alignment"]
                )
                gfa.add_edge(edge)

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
            if section_id == SECTION_ID_SEGMENT_NAMES:
                # Format: [compression][compressed_len][uncompressed_len]
                if len(data) < offset + 2 + 8 + 8:
                    raise ValueError("BGFA file is too short")
                offset += 2  # compression
                compressed_len = struct.unpack_from("<Q", data, offset)[0]
                offset += 8  # compressed_len
                offset += 8  # uncompressed_len
                
            elif section_id == SECTION_ID_SEGMENTS:
                # Format: [compression][compressed_len][uncompressed_len]
                if len(data) < offset + 2 + 8 + 8:
                    raise ValueError("BGFA file is too short")
                offset += 2  # compression
                compressed_len = struct.unpack_from("<Q", data, offset)[0]
                offset += 8  # compressed_len
                offset += 8  # uncompressed_len
                
            elif section_id == SECTION_ID_LINKS:
                # Format: [comp_fromto][clen_fromto][comp_cigars][clen_cigars][uncompressed_cigars_len]
                if len(data) < offset + 2 + 8 + 2 + 8 + 8:
                    raise ValueError("BGFA file is too short")
                offset += 2  # comp_fromto
                clen_fromto = struct.unpack_from("<Q", data, offset)[0]
                offset += 8  # clen_fromto
                offset += 2  # comp_cigars
                clen_cigars = struct.unpack_from("<Q", data, offset)[0]
                offset += 8  # clen_cigars
                offset += 8  # uncompressed_cigars_len
                compressed_len = clen_fromto + clen_cigars
                
            elif section_id == SECTION_ID_PATHS:
                # Format: [comp_names][clen_names][comp_paths][clen_paths][comp_cigars][clen_cigars]
                #         [uncompressed_*_len for each field]
                if len(data) < offset + 2 + 8 + 2 + 8 + 2 + 8 + 8 * 3:
                    raise ValueError("BGFA file is too short")
                offset += 2  # comp_names
                clen_names = struct.unpack_from("<Q", data, offset)[0]
                offset += 8  # clen_names
                offset += 2  # comp_paths
                clen_paths = struct.unpack_from("<Q", data, offset)[0]
                offset += 8  # clen_paths
                offset += 2  # comp_cigars
                clen_cigars = struct.unpack_from("<Q", data, offset)[0]
                offset += 8  # clen_cigars
                offset += 8 * 3  # uncompressed_*_len fields
                compressed_len = clen_names + clen_paths + clen_cigars
                
            elif section_id == SECTION_ID_WALKS:
                # Format: [comp_*][clen_*] for 6 fields + [uncompressed_*_len] for 6 fields
                if len(data) < offset + 6 * (2 + 8) + 6 * 8:
                    raise ValueError("BGFA file is too short")
                compressed_len = 0
                for _ in range(6):
                    offset += 2  # compression
                    clen = struct.unpack_from("<Q", data, offset)[0]
                    offset += 8  # clen
                    compressed_len += clen
                offset += 8 * 6  # uncompressed_*_len fields
                
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
    
    def _write_segment_names_block(self, buf: io.BytesIO, chunk: list[str], code: int) -> None:
        """Write a segment names block."""
        payload = _compress_string_for_bgfa(chunk, code)
        
        buf.write(struct.pack("<B", SECTION_ID_SEGMENT_NAMES))
        buf.write(struct.pack("<H", len(chunk)))
        buf.write(struct.pack("<H", code))
        buf.write(struct.pack("<Q", len(payload)))
        buf.write(struct.pack("<Q", sum(len(n) for n in chunk)))
        buf.write(payload)
    
    def _write_segments_block(self, buf: io.BytesIO, chunk: list[tuple], code: int) -> None:
        """Write a segments block.
        
        Chunk is a list of (name, segment_id) tuples.
        Payload layout: [segment_ids encoded][sequences encoded]
        """
        nodes_data = dict(self._gfa.nodes(data=True))
        
        ids = [sid for name, sid in chunk]
        seqs = []
        for name, sid in chunk:
            s = nodes_data[name].get("sequence", "*")
            if s is None or s == "":
                s = "*"
            seqs.append(s)
        
        # Encode IDs
        int_encoder = get_integer_encoder(code)
        payload_ids = int_encoder(ids)
        
        # Encode sequences
        payload_seqs = _compress_string_for_bgfa(seqs, code)
        
        payload = payload_ids + payload_seqs
        
        buf.write(struct.pack("<B", SECTION_ID_SEGMENTS))
        buf.write(struct.pack("<H", len(chunk)))
        buf.write(struct.pack("<H", code))
        buf.write(struct.pack("<Q", len(payload)))
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
        buf.write(struct.pack("<H", c_cig))
        buf.write(struct.pack("<Q", len(p_cig)))
        buf.write(struct.pack("<Q", sum(len(c) for c in cigs)))
        buf.write(p_ft + p_cig)
    
    def to_bgfa(self, verbose: bool = False, debug: bool = False, logfile: str = None, **kwargs) -> bytes:
        """Convert GFA to BGFA format."""
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
        
        # Write segment names blocks
        names_enc = self._comp_options.get("names_enc", make_compression_code(INTEGER_ENCODING_VARINT, STRING_ENCODING_NONE))
        for i in range(0, len(names), self._block_size):
            chunk = names[i:i + self._block_size]
            self._write_segment_names_block(buf, chunk, names_enc)
        
        # Write segments blocks
        seq_enc = self._comp_options.get("seq_enc", make_compression_code(INTEGER_ENCODING_VARINT, STRING_ENCODING_2BIT_DNA))
        sorted_segs = sorted(self._segment_map.items(), key=lambda x: x[1])
        for i in range(0, len(sorted_segs), self._block_size):
            chunk = sorted_segs[i:i + self._block_size]
            self._write_segments_block(buf, chunk, seq_enc)
        
        # Write links blocks
        edges = list(self._gfa.edges(data=True, keys=True))
        links_ft_enc = self._comp_options.get("links_fromto_enc", make_compression_code(INTEGER_ENCODING_VARINT, STRING_ENCODING_NONE))
        links_cig_enc = self._comp_options.get("links_cigars_enc", make_compression_code(INTEGER_ENCODING_VARINT, STRING_ENCODING_CIGAR))
        
        for i in range(0, len(edges), self._block_size):
            chunk = edges[i:i + self._block_size]
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
    
    p = s.lower().replace("_", "").split("-")
    
    i_map = {e.name.lower().replace("_", ""): e.value for e in IntegerEncoding}
    s_map = {e.name.lower().replace("_", ""): e.value for e in StringEncoding}
    
    # Aliases
    i_map["identity"] = 0
    s_map["identity"] = 0
    s_map["2bit"] = 5
    
    int_enc = i_map.get(p[0], INTEGER_ENCODING_VARINT)
    str_enc = s_map.get(p[1] if len(p) > 1 else "none", STRING_ENCODING_NONE)
    
    return make_compression_code(int_enc, str_enc)


def to_bgfa(gfa: GFA, file: str = None, block_size: int = DEFAULT_BLOCK_SIZE,
            compression_options: dict = None, **kwargs) -> bytes:
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


def measure_bgfa(input_file: str, output_file: str) -> None:
    """Measure BGFA file statistics."""
    # TODO: Implement measurement
    pass
