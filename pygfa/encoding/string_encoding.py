from __future__ import annotations

import gzip
import lzma
import struct
import threading
from collections.abc import Callable

try:
    import compression.zstd as z
    _ZSTD_AVAILABLE = True
except ImportError:
    _ZSTD_AVAILABLE = False
    z = None

def compress_string_zstd(string: str) -> bytes:
    if not _ZSTD_AVAILABLE:
        raise ImportError("zstandard package required")
    assert z is not None
    return z.compress(string.encode("ascii"), level=19)

_ZSTD_STATIC_DICT = None
_zstd_dict_lock = threading.Lock()

def _get_zstd_dict():
    global _ZSTD_STATIC_DICT
    if _ZSTD_STATIC_DICT is None:
        with _zstd_dict_lock:
            if _ZSTD_STATIC_DICT is None:
                import zstandard as zstd
                common_strings = (b"ACGTTGCAAAAATTTTGGGGCCCCATATTATAGCGCCGCGACGT") * 1000
                _ZSTD_STATIC_DICT = zstd.ZstdCompressionDict(common_strings)
    return _ZSTD_STATIC_DICT

def compress_string_zstd_dict(string: str) -> bytes:
    import zstandard as zstd
    data = string.encode("ascii")
    dictionary = _get_zstd_dict()
    compressor = zstd.ZstdCompressor(dict_data=dictionary, level=3)
    return compressor.compress(data)

def decompress_string_zstd_dict(data: bytes, lengths: list[int]) -> list[bytes]:
    import zstandard as zstd
    dictionary = _get_zstd_dict()
    decompressor = zstandard.ZstdDecompressor(dict_data=dictionary)
    decompressed = decompressor.decompress(data)
    from pygfa.bgfa import decompress_string_none
    return decompress_string_none(decompressed, lengths)

def compress_string_gzip(string: str) -> bytes:
    return gzip.compress(string.encode("ascii"))

def compress_string_lzma(string: str) -> bytes:
    return lzma.compress(string.encode("ascii"))

def compress_string_none(string: str) -> bytes:
    return string.encode("ascii")

def compress_string_list(
    string_list: list[str],
    int_encoder: Callable[[list[int]], bytes] | None = None,
    compression_method: str = "none",
    compression_level: int = 19,
    first_byte_strategy: int = 0x01,
) -> bytes:
    """Compress a list of strings using Concatenation + strategy.
    
    Format: [Metadata:int_encoding] [Blob]
    """
    if int_encoder is None:
        from pygfa.encoding.integer_list_encoding import compress_integer_list_varint
        int_encoder = compress_integer_list_varint

    strings = [s.encode("ascii") for s in string_list]
    metadata = int_encoder([len(s) for s in strings])

    concatenated = b"".join(strings)

    if compression_method == "zstd":
        if not _ZSTD_AVAILABLE:
            raise ImportError("zstandard package required")
        assert z is not None
        blob = z.compress(concatenated, level=compression_level)
    elif compression_method == "gzip":
        blob = gzip.compress(concatenated, compresslevel=compression_level)
    elif compression_method == "lzma":
        blob = lzma.compress(concatenated, preset=compression_level)
    elif compression_method == "huffman":
        from pygfa.encoding.huffman_nibble import compress_nibble_huffman
        blob = compress_nibble_huffman(concatenated, int_encoder, first_byte_strategy)
    elif compression_method == "2bit":
        from pygfa.encoding.dna_encoding import compress_string_2bit_dna
        blob = compress_string_2bit_dna(concatenated.decode("ascii"))
    elif compression_method == "none":
        blob = concatenated
    else:
        # Fallback for other methods if they are single-string encoders
        blob = concatenated # Placeholder
        
    return metadata + blob

def overlap(a: bytes, b: bytes) -> int:
    max_len = min(len(a), len(b))
    for i in range(max_len, 0, -1):
        if a.endswith(b[:i]):
            return i
    return 0

def greedy_scs(strings: list[bytes]) -> bytes:
    if not strings:
        return b""
    candidates = list(set(s for s in strings if s))
    if not candidates:
        return b""
    while len(candidates) > 1:
        max_overlap = -1
        best_pair = (0, 1)
        for i in range(len(candidates)):
            for j in range(len(candidates)):
                if i == j: continue
                ov = overlap(candidates[i], candidates[j])
                if ov > max_overlap:
                    max_overlap = ov
                    best_pair = (i, j)
        i, j = best_pair
        merged = candidates[i] + candidates[j][max_overlap:]
        if i > j:
            candidates.pop(i); candidates.pop(j)
        else:
            candidates.pop(j); candidates.pop(i)
        candidates.append(merged)
    return candidates[0]

def compress_string_list_superstring(
    string_list: list[str],
    int_encoder: Callable[[list[int]], bytes] | None = None,
    compression_method: str = "none",
    first_byte_strategy: int = 0x01,
) -> bytes:
    """Compress a list of strings using Superstring + strategy.
    
    Format: [Starts:int_encoding] [Ends:int_encoding] [Blob]
    """
    if not string_list:
        return b""
    if int_encoder is None:
        from pygfa.encoding.integer_list_encoding import compress_integer_list_varint
        int_encoder = compress_integer_list_varint

    strings = [s.encode("ascii") for s in string_list]
    superstring = greedy_scs(strings)
    
    # Validation: Ensure it's a superstring
    for s in strings:
        if s not in superstring:
            superstring = b"".join(strings)
            break
            
    starts = [superstring.find(s) for s in strings]
    ends = [start + len(s) for start, s in zip(starts, strings)]
    
    metadata = int_encoder(starts) + int_encoder(ends)
    
    if compression_method == "huffman":
        from pygfa.encoding.huffman_nibble import compress_nibble_huffman
        blob = compress_nibble_huffman(superstring, int_encoder, first_byte_strategy)
    elif compression_method == "2bit":
        from pygfa.encoding.dna_encoding import compress_string_2bit_dna
        blob = compress_string_2bit_dna(superstring.decode("ascii"))
    elif compression_method == "none":
        blob = superstring
    else:
        blob = superstring # Default
        
    return metadata + blob

def compress_string_list_superstring_huffman(string_list, int_encoder=None):
    return compress_string_list_superstring(string_list, int_encoder, "huffman")

def compress_string_list_superstring_2bit(string_list, int_encoder=None):
    return compress_string_list_superstring(string_list, int_encoder, "2bit")

def compress_string_list_superstring_none(string_list, int_encoder=None):
    return compress_string_list_superstring(string_list, int_encoder, "none")

# Keep wrappers for compatibility or other methods if needed
def compress_string_list_dictionary(string_list, int_encoder=None):
    return b"" # Placeholder

def compress_string_list_huffman(string_list, int_encoder=None):
    return compress_string_list(string_list, int_encoder, "huffman")

def compress_string_list_2bit_dna(string_list, int_encoder=None):
    return compress_string_list(string_list, int_encoder, "2bit")

def compress_string_list_frontcoding(string_list, int_encoder=None):
    return b"" # Placeholder

def compress_string_list_delta(string_list, int_encoder=None, compression_method="none"):
    return b"" # Placeholder
