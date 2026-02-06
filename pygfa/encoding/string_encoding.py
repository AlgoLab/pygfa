from __future__ import annotations

import gzip
import lzma
import struct
from collections.abc import Callable

try:
    import compression.zstd as z

    _ZSTD_AVAILABLE = True
except ImportError:
    _ZSTD_AVAILABLE = False
    z = None


def compress_string_zstd(string: str) -> bytes:
    if not _ZSTD_AVAILABLE:
        raise ImportError(
            "The 'compression' package is required for zstd compression. "
            "Install it with: pip install compression"
        )
    assert z is not None
    return z.compress(string.encode("ascii"), level=19)


def compress_string_gzip(string: str) -> bytes:
    return gzip.compress(string.encode("ascii"))


def compress_string_lzma(string: str) -> bytes:
    return lzma.compress(string.encode("ascii"))


def compress_string_none(string: str) -> bytes:
    return string.encode("ascii")


def compress_string_list(
    string_list: list[str],
    compress_integer_list: Callable[[list[int]], bytes] | None = None,
    compression_method: str = "zstd",
    compression_level: int = 19,
) -> bytes:
    strings = [string.encode("ascii") for string in string_list]
    if compress_integer_list is None:
        from pygfa.encoding import compress_integer_list_varint

        compress_integer_list = compress_integer_list_varint
    length_bytes = compress_integer_list([len(s) for s in strings])

    concatenated_strings = b"".join(strings)

    if compression_method == "zstd":
        if not _ZSTD_AVAILABLE:
            raise ImportError(
                "The 'compression' package is required for zstd compression. "
                "Install it with: pip install compression"
            )
        assert z is not None
        compressed_data = z.compress(concatenated_strings, level=compression_level)
    elif compression_method == "gzip":
        compressed_data = gzip.compress(concatenated_strings, compresslevel=compression_level)
    elif compression_method == "lzma":
        compressed_data = lzma.compress(concatenated_strings, preset=compression_level)
    elif compression_method == "none":
        compressed_data = concatenated_strings
    else:
        raise ValueError(f"Unsupported compression method: {compression_method}")

    return length_bytes + compressed_data


def compress_string_list_frontcoding(
    string_list: list[str],
    compress_integer_list: Callable[[list[int]], bytes] | None = None,
) -> bytes:
    if not string_list:
        return b""
    if compress_integer_list is None:
        from pygfa.encoding import compress_integer_list_varint

        compress_integer_list = compress_integer_list_varint

    encoded = bytearray()
    prev = b""
    prefixes = []
    suffixes = []

    for s in string_list:
        cur = s.encode("ascii")
        i = 0
        while i < min(len(prev), len(cur)) and prev[i] == cur[i]:
            i += 1
        prefixes.append(i)
        suffixes.append(cur[i:])
        prev = cur

    encoded.extend(compress_integer_list(prefixes))
    encoded.extend(compress_integer_list([len(s) for s in suffixes]))
    encoded.extend(b"".join(suffixes))

    return bytes(encoded)


def compress_string_list_delta(
    string_list: list[str],
    compress_integer_list: Callable[[list[int]], bytes] | None = None,
    compression_method: str = "none",
    compression_level: int = 19,
) -> bytes:
    if not string_list:
        return b""
    if compress_integer_list is None:
        from pygfa.encoding import compress_integer_list_varint

        compress_integer_list = compress_integer_list_varint

    strings = [s.encode("ascii") for s in string_list]
    deltas = [strings[0]]
    for i in range(1, len(strings)):
        a = strings[i - 1]
        b = strings[i]
        j = 0
        while j < min(len(a), len(b)) and a[j] == b[j]:
            j += 1
        deltas.append(b[j:])

    if compress_integer_list is None:
        from pygfa.encoding import compress_integer_list_varint

        compress_integer_list = compress_integer_list_varint

    lengths = compress_integer_list([len(d) for d in deltas])
    concatenated = b"".join(deltas)

    if compression_method == "zstd" and _ZSTD_AVAILABLE:
        assert z is not None
        concatenated = z.compress(concatenated, level=compression_level)
    elif compression_method == "gzip":
        concatenated = gzip.compress(concatenated, compresslevel=compression_level)
    elif compression_method == "lzma":
        concatenated = lzma.compress(concatenated, preset=compression_level)

    return lengths + concatenated


def compress_string_list_dictionary(
    string_list: list[str],
    compress_integer_list: Callable[[list[int]], bytes] | None = None,
    max_dict_size: int = 65536,
) -> bytes:
    if not string_list:
        return b""

    if compress_integer_list is None:
        from pygfa.encoding import compress_integer_list_varint

        compress_integer_list = compress_integer_list_varint

    strings = [s.encode("ascii") for s in string_list]
    unique_strings = list(dict.fromkeys(strings))
    if len(unique_strings) > max_dict_size:
        unique_strings = unique_strings[:max_dict_size]

    dict_map = {s: i for i, s in enumerate(unique_strings)}
    dict_offsets = []
    offset = 0
    for s in unique_strings:
        dict_offsets.append(offset)
        offset += len(s)

    dict_data = b"".join(unique_strings)
    indices = [dict_map.get(s, 0) for s in strings]

    indices_bytes = compress_integer_list(indices)
    offsets_bytes = compress_integer_list(dict_offsets)

    return struct.pack("<I", len(unique_strings)) + offsets_bytes + dict_data + indices_bytes


class _HuffmanNode:
    __slots__ = ("char", "freq", "left", "right")

    def __init__(self, char: int | None, freq: int):
        self.char = char
        self.freq = freq
        self.left: _HuffmanNode | None = None
        self.right: _HuffmanNode | None = None

    def __lt__(self, other: _HuffmanNode) -> bool:
        return self.freq < other.freq


def _build_huffman_tree(freq: dict[int, int]) -> _HuffmanNode:
    import heapq

    nodes = [_HuffmanNode(c, f) for c, f in freq.items()]
    heapq.heapify(nodes)

    while len(nodes) > 1:
        left = heapq.heappop(nodes)
        right = heapq.heappop(nodes)
        parent = _HuffmanNode(None, left.freq + right.freq)
        parent.left = left
        parent.right = right
        heapq.heappush(nodes, parent)

    return nodes[0] if nodes else _HuffmanNode(0, 0)


def _build_codes(
    node: _HuffmanNode | None,
    current: int = 0,
    bits: list[int] | None = None,
    codes: dict[int, list[int]] | None = None,
) -> dict[int, list[int]]:
    if codes is None:
        codes = {}
    if bits is None:
        bits = []

    if node is None:
        return codes

    if node.char is not None:
        codes[node.char] = bits.copy()
        if len(bits) == 0:
            codes[node.char] = [0]
    else:
        if node.left:
            _build_codes(node.left, current, bits + [0], codes)
        if node.right:
            _build_codes(node.right, current, bits + [1], codes)

    return codes


def compress_string_list_huffman(
    string_list: list[str],
    compress_integer_list: Callable[[list[int]], bytes] | None = None,
) -> bytes:
    if not string_list:
        return b""

    if compress_integer_list is None:
        from pygfa.encoding import compress_integer_list_varint

        compress_integer_list = compress_integer_list_varint

    data = b"".join(s.encode("ascii") for s in string_list)
    if not data:
        return b"\x00\x00\x00\x00"

    freq: dict[int, int] = {}
    for byte in data:
        freq[byte] = freq.get(byte, 0) + 1

    if len(freq) == 1:
        single_char = next(iter(freq))
        codes = {single_char: [0]}
    else:
        tree = _build_huffman_tree(freq)
        codes = _build_codes(tree)

    bitstream: list[int] = []
    for byte in data:
        bitstream.extend(codes[byte])

    while len(bitstream) % 8 != 0:
        bitstream.append(0)

    encoded_bytes = 0
    bit_count = 0
    result = bytearray()
    for bit in bitstream:
        encoded_bytes = (encoded_bytes << 1) | bit
        bit_count += 1
        if bit_count == 8:
            result.append(encoded_bytes & 0xFF)
            encoded_bytes = 0
            bit_count = 0

    codebook: list[tuple[int, list[int]]] = sorted(codes.items(), key=lambda x: x[0])
    codebook_entries: list[int] = []
    for char, code in codebook:
        code_len = len(code)
        codebook_entries.append(code_len)
        codebook_entries.extend(code)

    codebook_bytes = compress_integer_list(codebook_entries)
    lengths = compress_integer_list([len(s.encode("ascii")) for s in string_list])

    return (
        struct.pack("<I", len(data))
        + struct.pack("<I", len(codebook_bytes))
        + codebook_bytes
        + struct.pack("<I", len(result))
        + lengths
        + bytes(result)
    )
