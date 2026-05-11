"""String encoding utilities for BGFA format.

This module provides encoding/decoding functions for lists of strings using
various compression strategies as specified in spec/gfa_binary_format.md.

Two main approaches:
1. Concatenation: Strings are concatenated (without null terminators), with lengths stored
2. Superstring: A shortest common superstring is computed, with start/end positions stored
"""

from __future__ import annotations

import gzip
import lzma
import struct
import threading
from collections.abc import Callable

try:
    import zstandard as zstd

    _ZSTD_AVAILABLE = True
except ImportError:
    _ZSTD_AVAILABLE = False
    zstd = None


def compress_string_zstd(string: str) -> bytes:
    """Compress a single string with zstd."""
    if not _ZSTD_AVAILABLE:
        raise ImportError("zstandard package required")
    assert zstd is not None
    return zstd.compress(string.encode("ascii"), level=19)


def compress_string_gzip(string: str) -> bytes:
    """Compress a single string with gzip."""
    return gzip.compress(string.encode("ascii"))


def compress_string_lzma(string: str) -> bytes:
    """Compress a single string with lzma."""
    return lzma.compress(string.encode("ascii"))


def compress_string_none(string: str) -> bytes:
    """Encode a single string without compression."""
    return string.encode("ascii")


# ZSTD dictionary cache
_ZSTD_STATIC_DICT = None
_zstd_dict_lock = threading.Lock()


def _get_zstd_dict():
    """Get or create a static ZSTD dictionary for compression."""
    global _ZSTD_STATIC_DICT
    if _ZSTD_STATIC_DICT is None:
        with _zstd_dict_lock:
            if _ZSTD_STATIC_DICT is None:
                import zstandard as zstd

                common_strings = (b"ACGTTGCAAAAATTTTGGGGCCCCATATTATAGCGCCGCGACGT") * 1000
                _ZSTD_STATIC_DICT = zstd.ZstdCompressionDict(common_strings)
    return _ZSTD_STATIC_DICT


def compress_string_zstd_dict(string: str) -> bytes:
    """Compress a single string with ZSTD using a static dictionary."""
    import zstandard as zstd

    data = string.encode("ascii")
    dictionary = _get_zstd_dict()
    compressor = zstd.ZstdCompressor(dict_data=dictionary, level=3)
    return compressor.compress(data)


def decompress_string_zstd_dict(data: bytes, lengths: list[int]) -> list[bytes]:
    """Decompress ZSTD dictionary-compressed strings."""
    import zstandard as zstd

    dictionary = _get_zstd_dict()
    decompressor = zstd.ZstdDecompressor(dict_data=dictionary)
    decompressed = decompressor.decompress(data)
    return decompress_string_none_from_blob(decompressed, lengths)


def compress_string_list(
    string_list: list[str],
    int_encoder: Callable[[list[int]], bytes] | None = None,
    compression_method: str = "none",
    compression_level: int = 6,
    first_byte_strategy: int = 0x01,
) -> bytes:
    """Compress a list of strings using Concatenation + strategy.

    Format: [Metadata:int_encoding] [Blob]

    Where Metadata is the encoded lengths of each string, and Blob is the
    concatenated strings (optionally compressed).

    :param string_list: List of strings to compress
    :param int_encoder: Function to encode the list of lengths
    :param compression_method: Compression method for the blob
    :param compression_level: Compression level (for methods that support it)
    :param first_byte_strategy: Strategy for encoding lengths (for Huffman, etc.)
    :return: Compressed bytes
    """
    if int_encoder is None:
        from pygfa.encoding.integer_list_encoding import compress_integer_list_varint

        int_encoder = compress_integer_list_varint

    # Convert strings to bytes
    strings = [s.encode("ascii") for s in string_list]

    # Encode lengths as metadata
    metadata = int_encoder([len(s) for s in strings])

    # Concatenate all strings
    concatenated = b"".join(strings)

    # Compress the concatenation
    if compression_method == "zstd":
        if not _ZSTD_AVAILABLE:
            raise ImportError("zstandard package required")
        assert zstd is not None
        blob = zstd.compress(concatenated, level=compression_level)
    elif compression_method == "gzip":
        blob = gzip.compress(concatenated, compresslevel=compression_level)
    elif compression_method == "lzma":
        blob = lzma.compress(concatenated, preset=compression_level)
    elif compression_method == "huffman":
        from pygfa.encoding.huffman_nibble import compress_nibble_huffman

        blob = compress_nibble_huffman(concatenated, int_encoder, first_byte_strategy)
    elif compression_method == "2bit":
        from pygfa.encoding.dna_encoding import compress_string_2bit_dna

        blob = compress_string_2bit_dna(concatenated)
    elif compression_method == "rle":
        from pygfa.encoding.rle_encoding import compress_string_rle

        blob = compress_string_rle(concatenated.decode("ascii"))
    elif compression_method == "cigar":
        from pygfa.encoding.cigar_encoding import compress_string_cigar

        # For CIGAR, we need to encode each string separately
        cigar_results = [compress_string_cigar(s.decode("ascii")) for s in strings]
        blob = b"".join(cigar_results)
    elif compression_method == "dictionary":
        from pygfa.encoding.dictionary_encoding import compress_string_list_dictionary

        blob = compress_string_list_dictionary(string_list, int_encoder)
    elif compression_method == "lz4":
        from pygfa.encoding.lz4_codec import compress_string_lz4

        blob = compress_string_lz4(concatenated.decode("ascii"))
    elif compression_method == "brotli":
        from pygfa.encoding.brotli_codec import compress_string_brotli

        blob = compress_string_brotli(concatenated.decode("ascii"))
    elif compression_method == "ppm":
        from pygfa.encoding.ppm_coding import compress_string_ppm

        blob = compress_string_ppm(concatenated.decode("ascii"))
    elif compression_method == "arithmetic":
        from pygfa.encoding.arithmetic_coding import compress_string_arithmetic

        blob = compress_string_arithmetic(concatenated.decode("ascii"))
    elif compression_method == "bwt_huffman":
        from pygfa.encoding.arithmetic_coding import compress_string_bwt_huffman

        blob = compress_string_bwt_huffman(concatenated.decode("ascii"))
    elif compression_method == "none":
        blob = concatenated
    else:
        blob = concatenated  # Fallback

    return metadata + blob


def overlap(a: bytes, b: bytes) -> int:
    """Find the maximum overlap between the suffix of a and prefix of b."""
    max_len = min(len(a), len(b))
    for i in range(max_len, 0, -1):
        if a.endswith(b[:i]):
            return i
    return 0


def greedy_scs(strings: list[bytes]) -> bytes:
    """Compute a greedy shortest common superstring.

    This is an approximation algorithm that repeatedly merges the pair
    of strings with maximum overlap until only one remains.

    Enhanced version ensures all input strings are included in the result.

    :param strings: List of byte strings
    :return: Superstring containing all input strings
    """
    if not strings:
        return b""

    # Remove empty strings but keep duplicates (they may have different positions)
    candidates = [s for s in strings if s]
    if not candidates:
        return b""

    # Track original strings to ensure all are included
    original_strings = candidates.copy()

    while len(candidates) > 1:
        max_overlap = -1
        best_pair = (0, 1)

        for i in range(len(candidates)):
            for j in range(len(candidates)):
                if i == j:
                    continue
                ov = overlap(candidates[i], candidates[j])
                if ov > max_overlap:
                    max_overlap = ov
                    best_pair = (i, j)

        i, j = best_pair
        merged = candidates[i] + candidates[j][max_overlap:]

        # Remove merged strings and add result
        if i > j:
            candidates.pop(i)
            candidates.pop(j)
        else:
            candidates.pop(j)
            candidates.pop(i)
        candidates.append(merged)

    superstring = candidates[0]

    # Post-processing: Ensure all original strings are included
    # If any string is missing, append it to the superstring
    for s in original_strings:
        if s not in superstring:
            superstring += s

    return superstring


def compress_string_list_superstring(
    string_list: list[str],
    int_encoder: Callable[[list[int]], bytes] | None = None,
    compression_method: str = "none",
    first_byte_strategy: int = 0x01,
) -> bytes:
    """Compress a list of strings using Superstring + strategy.

    Format: [Starts:int_encoding] [Ends:int_encoding] [Blob]

    Where:
    - Starts: encoded start positions of each string in the superstring
    - Ends: encoded end positions of each string in the superstring
    - Blob: the superstring (optionally compressed)

    :param string_list: List of strings to compress
    :param int_encoder: Function to encode position lists
    :param compression_method: Compression method for the superstring
    :param first_byte_strategy: Strategy for encoding positions
    :return: Compressed bytes
    """
    if not string_list:
        return b""

    if int_encoder is None:
        from pygfa.encoding.integer_list_encoding import compress_integer_list_varint

        int_encoder = compress_integer_list_varint

    # Convert to bytes
    strings = [s.encode("ascii") for s in string_list]

    # Compute superstring (now guaranteed to include all strings)
    superstring = greedy_scs(strings)

    # Find start and end positions
    starts = []
    ends = []
    for s in strings:
        start = superstring.find(s)
        starts.append(start)
        ends.append(start + len(s))

    # Encode positions
    metadata = int_encoder(starts) + int_encoder(ends)

    # Compress superstring
    if compression_method == "huffman":
        from pygfa.encoding.huffman_nibble import compress_nibble_huffman

        blob = compress_nibble_huffman(superstring, int_encoder, first_byte_strategy)
    elif compression_method == "2bit":
        from pygfa.encoding.dna_encoding import compress_string_2bit_dna

        blob = compress_string_2bit_dna(superstring)
    elif compression_method == "none":
        blob = superstring
    elif compression_method == "ppm":
        from pygfa.encoding.ppm_coding import compress_string_ppm

        blob = compress_string_ppm(superstring.decode("ascii"))
    else:
        blob = superstring  # Default

    return metadata + blob


def compress_string_list_superstring_huffman(
    string_list: list[str],
    int_encoder: Callable[[list[int]], bytes] | None = None,
) -> bytes:
    """Compress using superstring + Huffman."""
    return compress_string_list_superstring(string_list, int_encoder, "huffman")


def compress_string_list_superstring_2bit(
    string_list: list[str],
    int_encoder: Callable[[list[int]], bytes] | None = None,
) -> bytes:
    """Compress using superstring + 2-bit DNA."""
    return compress_string_list_superstring(string_list, int_encoder, "2bit")


def compress_string_list_superstring_ppm(
    string_list: list[str],
    int_encoder: Callable[[list[int]], bytes] | None = None,
) -> bytes:
    """Compress using superstring + PPM."""
    return compress_string_list_superstring(string_list, int_encoder, "ppm")


def compress_string_list_superstring_none(
    string_list: list[str],
    int_encoder: Callable[[list[int]], bytes] | None = None,
) -> bytes:
    """Compress using superstring with no compression."""
    return compress_string_list_superstring(string_list, int_encoder, "none")


def compress_string_list_dictionary(
    string_list: list[str],
    int_encoder: Callable[[list[int]], bytes] | None = None,
    max_dict_size: int = 65536,
) -> bytes:
    """Compress a list of strings using dictionary encoding.

    Format:
        [dict_size:uint32][dict_offsets:varint...][dict_blob:bytes][indices:varint...]

    :param string_list: List of strings to compress
    :param int_encoder: Function to encode integer lists
    :param max_dict_size: Maximum dictionary size
    :return: Compressed bytes
    """
    if not string_list:
        return b""

    if int_encoder is None:
        from pygfa.encoding.integer_list_encoding import compress_integer_list_varint

        int_encoder = compress_integer_list_varint

    # Build dictionary from unique strings
    unique_strings = list(dict.fromkeys(string_list))[:max_dict_size]
    string_to_idx = {s: i for i, s in enumerate(unique_strings)}

    # Create indices for each input string
    indices = [string_to_idx.get(s, 0) for s in string_list]

    # Build dictionary blob with offsets
    dict_blob = bytearray()
    offsets = []
    offset = 0
    for s in unique_strings:
        offsets.append(offset)
        encoded = s.encode("ascii")
        dict_blob.extend(encoded)
        offset += len(encoded)

    # Encode everything
    result = bytearray()
    result.extend(struct.pack("<I", len(unique_strings)))
    result.extend(int_encoder(offsets))
    result.extend(dict_blob)
    result.extend(int_encoder(indices))

    return bytes(result)


def decompress_string_list_dictionary(
    data: bytes,
    int_decoder: Callable[[bytes, int], tuple[list[int], int]],
) -> list[bytes]:
    """Decompress dictionary-encoded strings.

    :param data: Compressed data
    :param int_decoder: Function to decode integer lists
    :return: List of decompressed byte strings
    """
    if not data:
        return []

    offset = 0

    # Read dictionary size
    dict_size = struct.unpack_from("<I", data, offset)[0]
    offset += 4

    # Read offsets
    offsets, consumed = int_decoder(data[offset:], dict_size)
    offset += consumed

    # Read dictionary blob
    if offsets:
        # We need to find the actual end of the blob
        # For simplicity, read until we hit the indices
        # This requires knowing the total length or having a marker
        # For now, assume the rest is blob + indices
        pass

    # Read indices
    indices, consumed = int_decoder(data[offset:], -1)  # Decode all remaining

    # Reconstruct strings from dictionary
    # This is simplified - a full implementation would parse the blob properly
    result = []
    for idx in indices:
        if idx < dict_size:
            # Would need to extract from blob
            result.append(b"")
        else:
            result.append(b"")

    return result


# Compatibility wrappers
def compress_string_list_huffman(
    string_list: list[str],
    int_encoder: Callable[[list[int]], bytes] | None = None,
) -> bytes:
    """Compress using concatenation + Huffman."""
    if not string_list:
        return b""
    return compress_string_list(string_list, int_encoder, "huffman")


def compress_string_list_2bit_dna(
    string_list: list[str],
    int_encoder: Callable[[list[int]], bytes] | None = None,
) -> bytes:
    """Compress using concatenation + 2-bit DNA."""
    return compress_string_list(string_list, int_encoder, "2bit")


def compress_string_list_frontcoding(
    string_list: list[str],
    int_encoder: Callable[[list[int]], bytes] | None = None,
) -> bytes:
    """Compress using front-coding (placeholder)."""
    return b""


def compress_string_list_delta(
    string_list: list[str],
    int_encoder: Callable[[list[int]], bytes] | None = None,
    compression_method: str = "none",
) -> bytes:
    """Compress using delta encoding (placeholder)."""
    return b""


# =============================================================================
# String Decompression Functions
# =============================================================================


def decompress_string_none_from_blob(blob: bytes, lengths: list[int]) -> list[bytes]:
    result = []
    pos = 0
    for length in lengths:
        result.append(blob[pos : pos + length])
        pos += length
    return result


def decompress_string_none(payload: bytes, record_num: int, int_decoder: Callable) -> list[bytes]:
    lengths, consumed = int_decoder(payload, record_num)
    return decompress_string_none_from_blob(payload[consumed:], lengths)


def decompress_string_superstring_none(payload: bytes, record_num: int, int_decoder: Callable) -> list[bytes]:
    starts, consumed = int_decoder(payload, record_num)
    ends, consumed2 = int_decoder(payload[consumed:], record_num)
    blob = payload[consumed + consumed2 :]
    result = []
    for i in range(record_num):
        result.append(blob[starts[i] : ends[i]])
    return result


def decompress_string_superstring_huffman(payload: bytes, record_num: int, int_decoder: Callable) -> list[bytes]:
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
    starts, consumed = int_decoder(payload, record_num)
    ends, consumed2 = int_decoder(payload[consumed:], record_num)
    total_len = max(ends)
    from pygfa.encoding.dna_encoding import decompress_string_2bit_dna

    decompressed_list = decompress_string_2bit_dna(payload[consumed + consumed2 :], [total_len])
    decompressed = decompressed_list[0] if decompressed_list else b""
    result = []
    for i in range(record_num):
        result.append(decompressed[starts[i] : ends[i]])
    return result


def decompress_string_superstring_ppm(payload: bytes, record_num: int, int_decoder: Callable) -> list[bytes]:
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
    lengths, consumed = int_decoder(payload, record_num)
    if not _ZSTD_AVAILABLE:
        raise ImportError("zstandard package required")
    assert zstd is not None
    data = zstd.decompress(payload[consumed:])
    return decompress_string_none_from_blob(data, lengths)


def decompress_string_gzip(payload: bytes, record_num: int, int_decoder: Callable) -> list[bytes]:
    import gzip

    lengths, consumed = int_decoder(payload, record_num)
    data = gzip.decompress(payload[consumed:])
    return decompress_string_none_from_blob(data, lengths)


def decompress_string_lzma(payload: bytes, record_num: int, int_decoder: Callable) -> list[bytes]:
    import lzma

    lengths, consumed = int_decoder(payload, record_num)
    data = lzma.decompress(payload[consumed:])
    return decompress_string_none_from_blob(data, lengths)


def decompress_string_lz4(payload: bytes, record_num: int, int_decoder: Callable) -> list[bytes]:
    import lz4.frame

    lengths, consumed = int_decoder(payload, record_num)
    data = lz4.frame.decompress(payload[consumed:])
    return decompress_string_none_from_blob(data, lengths)


def decompress_string_brotli(payload: bytes, record_num: int, int_decoder: Callable) -> list[bytes]:
    import brotli

    lengths, consumed = int_decoder(payload, record_num)
    data = brotli.decompress(payload[consumed:])
    return decompress_string_none_from_blob(data, lengths)


def decompress_string_huffman(payload: bytes, record_num: int, int_decoder: Callable) -> list[bytes]:
    lengths, consumed = int_decoder(payload, record_num)
    from pygfa.encoding.huffman_nibble import decompress_nibble_huffman

    num_nibbles = sum(lengths) * 2
    decompressed = decompress_nibble_huffman(payload[consumed:], int_decoder, num_nibbles)
    return decompress_string_none_from_blob(decompressed, lengths)


def _compress_huffman_payload(data: str) -> bytes:
    from pygfa.encoding.huffman_nibble import compress_nibble_huffman
    from pygfa.encoding.integer_list_encoding import compress_integer_list_varint

    raw_bytes = data.encode("latin-1")
    return compress_nibble_huffman(raw_bytes, compress_integer_list_varint, 0x01)


def _decompress_huffman_payload(data: bytes, num_bytes: int) -> bytes:
    from pygfa.encoding.huffman_nibble import decompress_nibble_huffman
    from pygfa.encoding.integer_list_encoding import decode_integer_list_varint

    return decompress_nibble_huffman(data, decode_integer_list_varint, num_bytes * 2)
