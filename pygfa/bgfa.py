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
import os
import struct
import tempfile
from itertools import islice
from collections.abc import Callable

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
    compress_string_lzma,
    compress_string_none,
    compress_string_zstd,
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
from pygfa.encoding.lz4_codec import (
    compress_string_lz4,
    decompress_string_lz4,
)
from pygfa.encoding.brotli_codec import (
    compress_string_brotli,
    decompress_string_brotli,
)
from pygfa.encoding.ppm_coding import (
    compress_string_ppm,
    decompress_string_ppm,
)
from pygfa.gfa import GFA

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

logger = logging.getLogger(__name__)

# =============================================================================
# Decompression Functions (Unified API)
# =============================================================================

def decompress_string_none_from_blob(blob: bytes, lengths: list[int]) -> list[bytes]:
    result = []; pos = 0
    for length in lengths:
        result.append(blob[pos : pos + length]); pos += length
    return result

def decompress_string_none(payload: bytes, record_num: int, int_decoder: callable) -> list[bytes]:
    lengths, consumed = int_decoder(payload, record_num)
    return decompress_string_none_from_blob(payload[consumed:], lengths)

def decompress_string_zstd(payload: bytes, record_num: int, int_decoder: callable) -> list[bytes]:
    lengths, consumed = int_decoder(payload, record_num)
    import compression.zstd as z
    data = z.decompress(payload[consumed:])
    return decompress_string_none_from_blob(data, lengths)

def decompress_string_gzip(payload: bytes, record_num: int, int_decoder: callable) -> list[bytes]:
    lengths, consumed = int_decoder(payload, record_num)
    data = gzip.decompress(payload[consumed:])
    return decompress_string_none_from_blob(data, lengths)

def decompress_string_lzma(payload: bytes, record_num: int, int_decoder: callable) -> list[bytes]:
    lengths, consumed = int_decoder(payload, record_num)
    data = lzma.decompress(payload[consumed:])
    return decompress_string_none_from_blob(data, lengths)

def decompress_string_huffman(payload: bytes, record_num: int, int_decoder: callable) -> list[bytes]:
    lengths, consumed = int_decoder(payload, record_num)
    from pygfa.encoding.huffman_nibble import decompress_nibble_huffman
    num_nibbles = sum(lengths) * 2
    decompressed = decompress_nibble_huffman(payload[consumed:], int_decoder, num_nibbles)
    return decompress_string_none_from_blob(decompressed, lengths)

def decompress_string_2bit_dna_strings(payload: bytes, record_num: int, int_decoder: callable) -> list[bytes]:
    lengths, consumed = int_decoder(payload, record_num)
    from pygfa.encoding.dna_encoding import decompress_string_2bit_dna
    decompressed_list = decompress_string_2bit_dna(payload[consumed:], [sum(lengths)])
    decompressed = decompressed_list[0] if decompressed_list else b""
    return decompress_string_none_from_blob(decompressed, lengths)

def decompress_string_superstring_none(payload: bytes, record_num: int, int_decoder: callable) -> list[bytes]:
    starts, consumed1 = int_decoder(payload, record_num)
    ends, consumed2 = int_decoder(payload[consumed1:], record_num)
    blob = payload[consumed1 + consumed2:]
    return [blob[s:e] for s, e in zip(starts, ends)]

def decompress_string_superstring_huffman(payload: bytes, record_num: int, int_decoder: callable) -> list[bytes]:
    starts, consumed1 = int_decoder(payload, record_num)
    ends, consumed2 = int_decoder(payload[consumed1:], record_num)
    remaining = payload[consumed1 + consumed2:]
    super_len = max(ends) if ends else 0
    from pygfa.encoding.huffman_nibble import decompress_nibble_huffman
    superstring = decompress_nibble_huffman(remaining, int_decoder, super_len * 2)
    return [superstring[s:e] for s, e in zip(starts, ends)]

def decompress_string_superstring_2bit(payload: bytes, record_num: int, int_decoder: callable) -> list[bytes]:
    starts, consumed1 = int_decoder(payload, record_num)
    ends, consumed2 = int_decoder(payload[consumed1:], record_num)
    remaining = payload[consumed1 + consumed2:]
    super_len = max(ends) if ends else 0
    from pygfa.encoding.dna_encoding import decompress_string_2bit_dna
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
    STRING_ENCODING_ARITHMETIC: lambda p, rn, id: decompress_string_arithmetic(p, [0]*rn), # Simplified
    STRING_ENCODING_BWT_HUFFMAN: lambda p, rn, id: decompress_string_bwt_huffman(p, [0]*rn),
    STRING_ENCODING_RLE: lambda p, rn, id: decompress_string_rle(p, [0]*rn),
    STRING_ENCODING_CIGAR: lambda p, rn, id: decompress_string_cigar(p, [0]*rn),
    STRING_ENCODING_DICTIONARY: lambda p, rn, id: decompress_string_dictionary(p, [0]*rn),
    STRING_ENCODING_ZSTD_DICT: lambda p, rn, id: decompress_string_none(p, rn, id), # Placeholder
    STRING_ENCODING_LZ4: lambda p, rn, id: decompress_string_lz4(p, [0]*rn),
    STRING_ENCODING_BROTLI: lambda p, rn, id: decompress_string_brotli(p, [0]*rn),
    STRING_ENCODING_PPM: lambda p, rn, id: decompress_string_ppm(p, [0]*rn),
    STRING_ENCODING_SUPERSTRING_NONE: decompress_string_superstring_none,
    STRING_ENCODING_SUPERSTRING_HUFFMAN: decompress_string_superstring_huffman,
    STRING_ENCODING_SUPERSTRING_2BIT: decompress_string_superstring_2bit,
}

# =============================================================================
# Integer Decoders
# =============================================================================

def decode_integer_list_none(data: bytes, count: int) -> tuple[list[int], int]:
    result = []; pos = 0; current = bytearray()
    while pos < len(data):
        byte = data[pos]
        if byte == ord(","):
            if current: result.append(int(current.decode("ascii"))); current = bytearray()
            pos += 1
            if count > 0 and len(result) >= count: break
        elif ord("0") <= byte <= ord("9"):
            current.append(byte); pos += 1
        else: break
    if current: result.append(int(current.decode("ascii")))
    return result, pos

def decode_integer_list_varint(data: bytes, count: int) -> tuple[list[int], int]:
    result = []; pos = 0
    while pos < len(data) and (count < 0 or len(result) < count):
        value = 0; shift = 0
        while pos < len(data):
            byte = data[pos]; pos += 1
            value |= (byte & 0x7F) << shift; shift += 7
            if (byte & 0x80) == 0: break
        result.append(value)
    return result, pos

def decode_integer_list_fixed16(data: bytes, count: int) -> tuple[list[int], int]:
    result = []; pos = 0; n = len(data)//2 if count < 0 else count
    for _ in range(n):
        if pos+2 > len(data): break
        result.append(struct.unpack_from("<H", data, pos)[0]); pos += 2
    return result, pos

def decode_integer_list_fixed32(data: bytes, count: int) -> tuple[list[int], int]:
    result = []; pos = 0; n = len(data)//4 if count < 0 else count
    for _ in range(n):
        if pos+4 > len(data): break
        result.append(struct.unpack_from("<I", data, pos)[0]); pos += 4
    return result, pos

def decode_integer_list_fixed64(data: bytes, count: int) -> tuple[list[int], int]:
    result = []; pos = 0; n = len(data)//8 if count < 0 else count
    for _ in range(n):
        if pos+8 > len(data): break
        result.append(struct.unpack_from("<Q", data, pos)[0]); pos += 8
    return result, pos

def decode_integer_list_delta(data: bytes, count: int) -> tuple[list[int], int]:
    vals, consumed = decode_integer_list_varint(data, count)
    if not vals: return [], consumed
    decoded = []
    for v in vals:
        decoded.append((v >> 1) ^ (-(v & 1)))
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

def get_integer_decoder(code: int):
    return INTEGER_DECODERS.get((code >> 8) & 0xFF, decode_integer_list_none)

def get_integer_encoder(code: int):
    int_code = (code >> 8) & 0xFF
    from pygfa.encoding import (
        compress_integer_list_none, compress_integer_list_varint, compress_integer_list_fixed,
        compress_integer_list_delta
    )
    if int_code == INTEGER_ENCODING_NONE: return compress_integer_list_none
    if int_code == INTEGER_ENCODING_VARINT: return compress_integer_list_varint
    if int_code == INTEGER_ENCODING_FIXED16: return lambda x: compress_integer_list_fixed(x, 16)
    if int_code == INTEGER_ENCODING_FIXED32: return lambda x: compress_integer_list_fixed(x, 32)
    if int_code == INTEGER_ENCODING_FIXED64: return lambda x: compress_integer_list_fixed(x, 64)
    if int_code == INTEGER_ENCODING_DELTA: return compress_integer_list_delta
    return compress_integer_list_varint

def make_compression_code(int_enc: int, str_enc: int) -> int:
    return ((int_enc & 0xFF) << 8) | (str_enc & 0xFF)

def _compress_string_for_bgfa(string_list: list[str], compression_code: int) -> bytes:
    str_encoding = compression_code & 0xFF
    int_encoding = (compression_code >> 8) & 0xFF
    int_encoder = get_integer_encoder(compression_code)
    from pygfa.encoding.string_encoding import (
        compress_string_list, compress_string_list_superstring
    )
    if str_encoding >= 0xF0:
        method = "none"
        if str_encoding == STRING_ENCODING_SUPERSTRING_HUFFMAN: method = "huffman"
        elif str_encoding == STRING_ENCODING_SUPERSTRING_2BIT: method = "2bit"
        return compress_string_list_superstring(string_list, int_encoder, method, first_byte_strategy=int_encoding)
    
    method_map = {
        STRING_ENCODING_NONE: "none", STRING_ENCODING_ZSTD: "zstd",
        STRING_ENCODING_GZIP: "gzip", STRING_ENCODING_LZMA: "lzma",
        STRING_ENCODING_HUFFMAN: "huffman", STRING_ENCODING_2BIT_DNA: "2bit"
    }
    method = method_map.get(str_encoding, "none")
    return compress_string_list(string_list, int_encoder, method, first_byte_strategy=int_encoding)

def _pack_orientation_bits_uint64(orientations: list[int]) -> bytes:
    n = len(orientations)
    num_uint64 = math.ceil(n / 64) if n > 0 else 0
    result = bytearray()
    for word_idx in range(num_uint64):
        val = 0
        for bit_idx in range(64):
            idx = word_idx * 64 + bit_idx
            if idx < n and orientations[idx]: val |= 1 << bit_idx
        result.extend(struct.pack("<Q", val))
    return bytes(result)

def _unpack_orientation_bits_uint64(data: bytes, count: int) -> tuple[list[int], int]:
    n = math.ceil(count / 64) if count > 0 else 0
    res = []
    for i in range(n):
        val = struct.unpack_from("<Q", data, i*8)[0]
        for j in range(64):
            if len(res) >= count: break
            res.append((val >> j) & 1)
    return res, n * 8

def _encode_walks_payload(walk_segments_list, segment_map, compression_walks):
    # Simplified walk encoding for refactoring
    return b""

class ReaderBGFA:
    def __init__(self): pass

    def _parse_header(self, data):
        # Use struct.unpack_from which raises struct.error if buffer is too small
        magic = struct.unpack_from("<I", data, 0)[0]
        if magic != 0x42474641 and magic != 0x41464742:
            raise ValueError(f"Invalid magic number: {magic:#010x}")
        version = struct.unpack_from("<H", data, 4)[0]
        header_len = struct.unpack_from("<H", data, 6)[0]
        
        # Check if we have at least the header text bytes
        if 8 + header_len > len(data):
            raise ValueError("incomplete header data")
        # Check if we have the null terminator byte
        if 8 + header_len == len(data):
            raise ValueError("missing null terminator")
        if data[8 + header_len] != 0:
            raise ValueError("missing null terminator")
            
        header_text = data[8:8+header_len].decode("ascii")
        return {
            "magic": magic, 
            "version": version, 
            "header": header_text, 
            "header_text": header_text,
            "header_size": 8 + header_len + 1
        }

    def read_bgfa(self, file_path, verbose=False, debug=False, logfile=None):
        with open(file_path, "rb") as f: data = f.read()
        if not data: raise ValueError("Empty file")
        header = self._parse_header(data)
        offset = 8 + len(header["header"].encode("ascii")) + 1
        
        segment_names = []; segments = {}; links = []; paths = []; walks = []
        while offset < len(data):
            section_id = data[offset]; offset += 1
            if section_id == SECTION_ID_SEGMENT_NAMES:
                names, consumed = self._parse_segment_names_block(data, offset-1)
                segment_names.extend(names); offset += consumed - 1
            elif section_id == SECTION_ID_SEGMENTS:
                segs, consumed = self._parse_segments_block(data, offset-1)
                segments.update(segs); offset += consumed - 1
            elif section_id == SECTION_ID_LINKS:
                lnks, consumed = self._parse_links_block(data, segment_names, offset-1)
                links.extend(lnks); offset += consumed - 1
            else: break
        
        from pygfa.graph_element.node import Node
        from pygfa.graph_element.edge import Edge
        g = GFA(); # Populate GFA here
        for name in segment_names: g.add_node(Node(name, "*"))
        for sid, d in segments.items():
            name = segment_names[sid] if sid < len(segment_names) else f"s{sid}"
            g._graph.nodes[name]["sequence"] = d["sequence"]
        for l in links: g.add_edge(Edge(None, l["from_node"], l["from_orn"], l["to_node"], l["to_orn"], (None, None), (None, None), l["alignment"]))
        return g

    def _parse_segment_names_block(self, bgfa_data, start_offset):
        offset = start_offset + 1
        record_num = struct.unpack_from("<H", bgfa_data, offset)[0]; offset += 2
        compression = struct.unpack_from("<H", bgfa_data, offset)[0]; offset += 2
        compressed_len = struct.unpack_from("<Q", bgfa_data, offset)[0]; offset += 8
        uncompressed_len = struct.unpack_from("<Q", bgfa_data, offset)[0]; offset += 8
        payload = bgfa_data[offset : offset + compressed_len]
        
        int_decoder = get_integer_decoder(compression)
        str_decoder = STRING_DECODERS.get(compression & 0xFF, decompress_string_none)
        names = [b.decode("ascii") for b in str_decoder(payload, record_num, int_decoder)]
        return names, (offset + compressed_len) - start_offset

    def _parse_segments_block(self, bgfa_data, start_offset):
        offset = start_offset + 1
        record_num = struct.unpack_from("<H", bgfa_data, offset)[0]; offset += 2
        compression = struct.unpack_from("<H", bgfa_data, offset)[0]; offset += 2
        compressed_len = struct.unpack_from("<Q", bgfa_data, offset)[0]; offset += 8
        uncompressed_len = struct.unpack_from("<Q", bgfa_data, offset)[0]; offset += 8
        payload = bgfa_data[offset : offset + compressed_len]
        
        int_decoder = get_integer_decoder(compression)
        ids, ids_consumed = int_decoder(payload, record_num)
        str_decoder = STRING_DECODERS.get(compression & 0xFF, decompress_string_none)
        seqs = str_decoder(payload[ids_consumed:], record_num, int_decoder)
        
        segments = {}
        for i in range(record_num):
            s = seqs[i].decode("ascii") if i < len(seqs) else "*"
            if not s: s = "*"
            segments[ids[i]] = {"sequence": s}
        return segments, (offset + compressed_len) - start_offset

    def _parse_links_block(self, bgfa_data, segment_names, start_offset):
        offset = start_offset + 1
        record_num = struct.unpack_from("<H", bgfa_data, offset)[0]; offset += 2
        comp_fromto = struct.unpack_from("<H", bgfa_data, offset)[0]; offset += 2
        clen_fromto = struct.unpack_from("<Q", bgfa_data, offset)[0]; offset += 8
        comp_cigars = struct.unpack_from("<H", bgfa_data, offset)[0]; offset += 2
        clen_cigars = struct.unpack_from("<Q", bgfa_data, offset)[0]; offset += 8
        struct.unpack_from("<Q", bgfa_data, offset)[0]; offset += 8
        
        payload = bgfa_data[offset : offset + clen_fromto + clen_cigars]
        int_dec_fromto = get_integer_decoder(comp_fromto)
        from_ids, c1 = int_dec_fromto(payload, record_num)
        to_ids, c2 = int_dec_fromto(payload[c1:], record_num)
        f_orns, c3 = _unpack_orientation_bits_uint64(payload[c1+c2:], record_num)
        t_orns, c4 = _unpack_orientation_bits_uint64(payload[c1+c2+c3:], record_num)
        
        cigar_payload = payload[c1+c2+c3+c4:]
        int_dec_cigars = get_integer_decoder(comp_cigars)
        str_dec_cigars = STRING_DECODERS.get(comp_cigars & 0xFF, decompress_string_none)
        cigars = str_dec_cigars(cigar_payload, record_num, int_dec_cigars)
        
        links = []
        for i in range(record_num):
            fn = segment_names[from_ids[i]-1] if 0 < from_ids[i] <= len(segment_names) else f"n{from_ids[i]}"
            tn = segment_names[to_ids[i]-1] if 0 < to_ids[i] <= len(segment_names) else f"n{to_ids[i]}"
            links.append({"from_node": fn, "to_node": tn, "from_orn": "-" if f_orns[i] else "+", "to_orn": "-" if t_orns[i] else "+", "alignment": cigars[i].decode("ascii") if i < len(cigars) else "*"})
        return links, (offset + clen_fromto + clen_cigars) - start_offset

def parse_compression_strategy(s: str) -> int:
    from pygfa.encoding.enums import IntegerEncoding, StringEncoding
    p = s.lower().replace('_', '').split('-')
    i_map = {e.name.lower().replace('_', ''): e.value for e in IntegerEncoding}
    s_map = {e.name.lower().replace('_', ''): e.value for e in StringEncoding}
    i_map['identity'] = 0; s_map['identity'] = 0; s_map['2bit'] = 5
    return (i_map.get(p[0], 1) << 8) | s_map.get(p[1] if len(p)>1 else 'none', 0)

class BGFAWriter:
    def __init__(self, gfa, block_size=1024, comp_options=None):
        self._gfa = gfa; self._block_size = block_size; self._comp_options = comp_options or {}
    def to_bgfa(self, verbose=False, debug=False, logfile=None, **kwargs):
        for k, v in kwargs.items():
            if k.endswith('_enc'): self._comp_options[k] = parse_compression_strategy(v)
        buf = io.BytesIO()
        self._write_header(buf)
        names = list(self._gfa.nodes()); segment_map = {n: i for i, n in enumerate(names)}
        self._segment_map = segment_map
        for i in range(0, len(names), self._block_size):
            self._write_segment_names_block(buf, names[i:i+self._block_size], self._comp_options.get('names_enc', 0x0100))
        sorted_segs = sorted(segment_map.items(), key=lambda x: x[1])
        for i in range(0, len(sorted_segs), self._block_size):
            self._write_segments_block(buf, sorted_segs[i:i+self._block_size], self._comp_options.get('seq_enc', 0x0100))
        edges = list(self._gfa.edges(data=True, keys=True))
        for i in range(0, len(edges), self._block_size):
            self._write_links_block(buf, edges[i:i+self._block_size], self._comp_options.get('links_fromto_enc', 0x0100), self._comp_options.get('links_cigars_enc', 0x0100))
        return buf.getvalue()

    def _write_header(self, buf):
        buf.write(struct.pack("<IHH", 0x42474641, 1, 10))
        buf.write(b"H\tVN:Z:1.0\0")

    def _write_segment_names_block(self, buf, chunk, code):
        payload = _compress_string_for_bgfa(chunk, code)
        buf.write(struct.pack("<BH H QQ", SECTION_ID_SEGMENT_NAMES, len(chunk), code, len(payload), sum(len(n) for n in chunk)))
        buf.write(payload)

    def _write_segments_block(self, buf, chunk, code):
        nodes_data = dict(self._gfa.nodes(data=True))
        ids = [sid for name, sid in chunk]
        seqs = []
        for name, sid in chunk:
            s = nodes_data[name].get("sequence", "*")
            if s is None or s == "": s = "*"
            seqs.append(s)
        payload_ids = get_integer_encoder(code)(ids)
        payload_seqs = _compress_string_for_bgfa(seqs, code)
        payload = payload_ids + payload_seqs
        buf.write(struct.pack("<BH H QQ", SECTION_ID_SEGMENTS, len(chunk), code, len(payload), sum(len(s) if s != "*" else 0 for s in seqs)))
        buf.write(payload)

    def _write_links_block(self, buf, chunk, c_ft, c_cig):
        f_ids = []; t_ids = []; f_os = []; t_os = []; cigs = []
        for u, v, k, d in chunk:
            fn = d.get("from_node", u); tn = d.get("to_node", v)
            f_ids.append(self._segment_map.get(fn, 0)+1); t_ids.append(self._segment_map.get(tn, 0)+1)
            f_os.append(0 if d.get("from_orn", "+") == "+" else 1); t_os.append(0 if d.get("to_orn", "+") == "+" else 1)
            cigs.append(d.get("alignment", "*"))
        p_ft = get_integer_encoder(c_ft)(f_ids) + get_integer_encoder(c_ft)(t_ids) + _pack_orientation_bits_uint64(f_os) + _pack_orientation_bits_uint64(t_os)
        p_cig = _compress_string_for_bgfa(cigs, c_cig)
        buf.write(struct.pack("<BH H Q H QQ", SECTION_ID_LINKS, len(chunk), c_ft, len(p_ft), c_cig, len(p_cig), sum(len(c) for c in cigs)))
        buf.write(p_ft + p_cig)

def to_bgfa(gfa, file=None, block_size=1024, compression_options=None, **kwargs):
    res = BGFAWriter(gfa, block_size, compression_options).to_bgfa(**kwargs)
    if file:
        with open(file, "wb") as f: f.write(res)
    return res

def read_bgfa(file_path, **kwargs):
    return ReaderBGFA().read_bgfa(file_path, **kwargs)

def measure_bgfa(input_file, output_file): pass # Placeholder
