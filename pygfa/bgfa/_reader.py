"""BGFA reader module."""

from __future__ import annotations

import csv
import struct
from collections.abc import Callable

from pygfa.bgfa._codec_utils import unpack_bits_lsb
from pygfa.bgfa._constants import (
    BGFA_MAGIC,
    CIGAR_DECOMPOSITION_NONE,
    CIGAR_DECOMPOSITION_NUM_OPS_LENGTHS_OPS,
    CIGAR_DECOMPOSITION_STRING,
    INTEGER_ENCODING_DELTA,
    INTEGER_ENCODING_ELIAS_GAMMA,
    INTEGER_ENCODING_ELIAS_OMEGA,
    INTEGER_ENCODING_FIXED16,
    INTEGER_ENCODING_FIXED32,
    INTEGER_ENCODING_FIXED64,
    INTEGER_ENCODING_GOLOMB,
    INTEGER_ENCODING_NONE,
    INTEGER_ENCODING_RICE,
    INTEGER_ENCODING_STREAMVBYTE,
    INTEGER_ENCODING_VARINT,
    INTEGER_ENCODING_VBYTE,
    SECTION_ID_LINKS,
    SECTION_ID_PATHS,
    SECTION_ID_SEGMENTS,
    SECTION_ID_WALKS,
    STRING_ENCODING_2BIT_DNA,
    STRING_ENCODING_ARITHMETIC,
    STRING_ENCODING_BROTLI,
    STRING_ENCODING_BWT_HUFFMAN,
    STRING_ENCODING_DICTIONARY,
    STRING_ENCODING_GZIP,
    STRING_ENCODING_HUFFMAN,
    STRING_ENCODING_LZ4,
    STRING_ENCODING_LZMA,
    STRING_ENCODING_NONE,
    STRING_ENCODING_PPM,
    STRING_ENCODING_RLE,
    STRING_ENCODING_ZSTD,
    STRING_ENCODING_ZSTD_DICT,
    logger,
)
from pygfa.encoding import (
    compress_integer_list_uints_delta,
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
from pygfa.encoding.arithmetic_coding import (
    _decompress_string_arithmetic_wrapper,
    _decompress_string_bwt_huffman_wrapper,
)
from pygfa.encoding.cigar_encoding import (
    _ops_string_decoder_for_code,
    decompress_string_cigar_decomposed,
)
from pygfa.encoding.dictionary_encoding import _decompress_string_dictionary_wrapper
from pygfa.encoding.dna_encoding import decompress_string_2bit_dna_strings
from pygfa.encoding.integer_list_encoding import (
    decode_integer_list_uints_delta,
    decode_integer_list_elias_gamma,
    decode_integer_list_elias_omega,
    decode_integer_list_fixed16,
    decode_integer_list_fixed32,
    decode_integer_list_fixed64,
    decode_integer_list_golomb,
    decode_integer_list_none,
    decode_integer_list_rice,
    decode_integer_list_streamvbyte,
    decode_integer_list_varint,
    decode_integer_list_vbyte,
)
from pygfa.encoding.ppm_coding import decompress_string_ppm
from pygfa.encoding.rle_encoding import _decompress_string_rle_wrapper
from pygfa.encoding.string_encoding import (
    decompress_string_brotli,
    decompress_string_gzip,
    decompress_string_huffman,
    decompress_string_lz4,
    decompress_string_lzma,
    decompress_string_none,
    decompress_string_zstd,
)
from pygfa.gfa import GFA

# =============================================================================
# Integer Decoders
# =============================================================================

INTEGER_DECODERS = {
    INTEGER_ENCODING_NONE: decode_integer_list_none,
    INTEGER_ENCODING_VARINT: decode_integer_list_varint,
    INTEGER_ENCODING_FIXED16: decode_integer_list_fixed16,
    INTEGER_ENCODING_FIXED32: decode_integer_list_fixed32,
    INTEGER_ENCODING_FIXED64: decode_integer_list_fixed64,
    INTEGER_ENCODING_DELTA: decode_integer_list_uints_delta,
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
        INTEGER_ENCODING_DELTA: compress_integer_list_uints_delta,
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
        return compress_integer_list_uints_delta
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
# BGFA Reader
# =============================================================================


class ReaderBGFA:
    """BGFA file reader."""

    def __init__(self):
        self._segment_names = []
        self._segment_map = {}  # name -> id

    def _parse_header(self, data: bytes) -> dict:
        if len(data) < 8:
            raise struct.error("unpack_from requires a buffer of at least 8 bytes")

        magic = struct.unpack_from("<I", data, 0)[0]
        if magic != BGFA_MAGIC:
            raise ValueError(f"Invalid magic number: {magic:#010x}, expected {BGFA_MAGIC:#010x}")

        version = struct.unpack_from("<H", data, 4)[0]
        header_len = struct.unpack_from("<H", data, 6)[0]

        if 8 + header_len > len(data):
            raise ValueError("incomplete header data")

        if 8 + header_len >= len(data):
            raise ValueError("missing null terminator")
        if data[8 + header_len] != 0:
            raise ValueError("missing null terminator")

        header_text = data[8 : 8 + header_len].decode("ascii")

        return {
            "magic": magic,
            "version": version,
            "header": header_text,
            "header_text": header_text,
            "header_size": 8 + header_len + 1,
        }

    def _parse_segments_block(self, data: bytes, start_offset: int) -> tuple[dict, list[str], int]:
        offset = start_offset + 1

        record_num = struct.unpack_from("<H", data, offset)[0]
        offset += 2

        comp_names = struct.unpack_from("<H", data, offset)[0]
        offset += 2

        clen_names = struct.unpack_from("<Q", data, offset)[0]
        offset += 8

        _ = struct.unpack_from("<Q", data, offset)[0]
        offset += 8

        comp_str = struct.unpack_from("<H", data, offset)[0]
        offset += 2

        clen_str = struct.unpack_from("<Q", data, offset)[0]
        offset += 8

        _ = struct.unpack_from("<Q", data, offset)[0]
        offset += 8

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

        seqs_payload = data[offset + clen_names : offset + clen_names + clen_str]
        int_dec_str = get_integer_decoder(comp_str)
        str_dec_str = STRING_DECODERS.get(comp_str & 0xFF, decompress_string_none)
        seqs_bytes = str_dec_str(seqs_payload, record_num, int_dec_str)

        segments = {}
        for i in range(record_num):
            name = names[i] if i < len(names) else f"s{i}"
            if i < len(seqs_bytes) and seqs_bytes[i]:
                try:
                    seq = seqs_bytes[i].decode("ascii")
                except UnicodeDecodeError:
                    seq = seqs_bytes[i].decode("latin-1")
            else:
                seq = "*"
            if not seq:
                seq = "*"
            segments[i] = {"name": name, "sequence": seq}

        bytes_consumed = (offset + clen_names + clen_str) - start_offset
        return segments, names, bytes_consumed

    def _parse_links_block(self, data: bytes, start_offset: int) -> tuple[list[dict], int]:
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

        _ = struct.unpack_from("<Q", data, offset)[0]
        offset += 8

        fromto_payload = data[offset : offset + clen_fromto]
        int_dec_fromto = get_integer_decoder(comp_fromto)

        from_ids, c1 = int_dec_fromto(fromto_payload, record_num)
        to_ids, c2 = int_dec_fromto(fromto_payload[c1:], record_num)

        f_orns, c3 = unpack_bits_lsb(fromto_payload[c1 + c2 :], record_num)
        t_orns, c4 = unpack_bits_lsb(fromto_payload[c1 + c2 + c3 :], record_num)

        cigar_payload = data[offset + clen_fromto : offset + clen_fromto + clen_cigars]
        cigars_bytes = _decompress_cigar_payload(
            comp_cigars, cigar_payload, record_num, get_integer_decoder(comp_cigars)
        )

        links = []
        for i in range(record_num):
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
        if record_num == 0:
            return [], 0

        if walk_compression == 0:
            return [[] for _ in range(record_num)], 0

        walk_byte = (walk_compression >> 24) & 0xFF

        if walk_byte == 0x00:
            return [[] for _ in range(record_num)], 0

        int_code = walk_compression & 0xFF
        int_decoder_func = INTEGER_DECODERS.get(int_code, decode_integer_list_varint)

        walk_lengths, consumed = int_decoder_func(walk_data, record_num)
        total_segments = sum(walk_lengths)

        if total_segments == 0:
            return [[] for _ in range(record_num)], consumed

        data_after = walk_data[consumed:]

        if walk_byte == 0x01:
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
        offset = start_offset + 1

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

        _ = struct.unpack_from("<Q", data, offset)[0]
        offset += 8

        clen_names = struct.unpack_from("<Q", data, offset)[0]
        offset += 8

        _ = struct.unpack_from("<Q", data, offset)[0]
        offset += 8

        int_dec_names = get_integer_decoder(comp_names)
        str_dec_names = STRING_DECODERS.get(comp_names & 0xFF, decompress_string_none)

        names_payload = data[offset : offset + clen_names]
        path_names = str_dec_names(names_payload, record_num, int_dec_names)
        offset += clen_names

        cigars_payload = data[offset : offset + clen_cigars]
        cigar_bytes = _decompress_cigar_payload(
            comp_cigars, cigars_payload, record_num, get_integer_decoder(comp_cigars)
        )
        offset += clen_cigars

        walks, walk_consumed = self._decode_walk(
            data[offset:], record_num, comp_paths, get_integer_decoder(comp_paths & 0xFF), segment_names
        )
        offset += walk_consumed

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
        offset = start_offset + 1

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

        _ = struct.unpack_from("<Q", data, offset)[0]
        offset += 8

        clen_hep = struct.unpack_from("<Q", data, offset)[0]
        offset += 8

        _ = struct.unpack_from("<Q", data, offset)[0]
        offset += 8

        clen_seq = struct.unpack_from("<Q", data, offset)[0]
        offset += 8

        _ = struct.unpack_from("<Q", data, offset)[0]
        offset += 8

        clen_positions = struct.unpack_from("<Q", data, offset)[0]
        offset += 8

        _ = struct.unpack_from("<Q", data, offset)[0]
        offset += 8

        clen_walks = struct.unpack_from("<Q", data, offset)[0]
        offset += 8

        _ = struct.unpack_from("<Q", data, offset)[0]
        offset += 8

        int_dec_samples = get_integer_decoder(comp_samples)
        str_dec_samples = STRING_DECODERS.get(comp_samples & 0xFF, decompress_string_none)
        int_dec_hep = get_integer_decoder(comp_hep)
        int_dec_seq = get_integer_decoder(comp_seq)
        str_dec_seq = STRING_DECODERS.get(comp_seq & 0xFF, decompress_string_none)
        int_dec_positions = get_integer_decoder(comp_positions)

        samples_payload = data[offset : offset + clen_samples]
        sample_ids = str_dec_samples(samples_payload, record_num, int_dec_samples)
        offset += clen_samples

        hep_payload = data[offset : offset + clen_hep]
        hap_indices, _ = int_dec_hep(hep_payload, record_num)
        offset += clen_hep

        seq_payload = data[offset : offset + clen_seq]
        sequence_ids = str_dec_seq(seq_payload, record_num, int_dec_seq)
        offset += clen_seq

        positions_payload = data[offset : offset + clen_positions]
        starts, consumed1 = int_dec_positions(positions_payload, record_num)
        ends, _ = int_dec_positions(positions_payload[consumed1:], record_num)
        offset += clen_positions

        walks_payload = data[offset : offset + clen_walks]
        int_dec_walks = get_integer_decoder(comp_walks & 0xFF)
        walks, _ = self._decode_walk(walks_payload, record_num, comp_walks, int_dec_walks, segment_names)
        offset += clen_walks

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

        from pygfa.graph_element.node import Node
        from pygfa.graph_element.edge import Edge

        gfa = GFA()

        gfa._header_info = {"version": header["version"], "header_text": header["header_text"]}

        if not skip_payloads:
            for sid, seg_data in segments.items():
                name = seg_data.get("name", f"s{sid}")
                seq = seg_data.get("sequence", "*")
                gfa.add_node(Node(name, seq))

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

            for path_data in all_paths:
                gfa.add_path(path_data)

            for walk_data in all_walks:
                gfa.add_walk(walk_data)

        return gfa

    def _skip_block(self, data: bytes, start_offset: int) -> tuple[None, int]:
        offset = start_offset + 1

        if len(data) < offset + 2:
            raise ValueError("BGFA file is too short")

        offset += 2

        section_id = data[start_offset]

        try:
            if section_id == SECTION_ID_SEGMENTS:
                if len(data) < offset + 2 + 8 + 8 + 2 + 8 + 8:
                    raise ValueError("BGFA file is too short")
                offset += 2
                clen_names = struct.unpack_from("<Q", data, offset)[0]
                offset += 8
                offset += 8
                offset += 2
                clen_str = struct.unpack_from("<Q", data, offset)[0]
                offset += 8
                offset += 8
                compressed_len = clen_names + clen_str

            elif section_id == SECTION_ID_LINKS:
                if len(data) < offset + 2 + 8 + 4 + 8 + 8:
                    raise ValueError("BGFA file is too short")
                offset += 2
                clen_fromto = struct.unpack_from("<Q", data, offset)[0]
                offset += 8
                offset += 4
                clen_cigars = struct.unpack_from("<Q", data, offset)[0]
                offset += 8
                offset += 8
                compressed_len = clen_fromto + clen_cigars

            elif section_id == SECTION_ID_PATHS:
                if len(data) < offset + 2 + 8 + 4 + 8 + 4 + 8 + 8 * 3:
                    raise ValueError("BGFA file is too short")
                offset += 2
                clen_names = struct.unpack_from("<Q", data, offset)[0]
                offset += 8
                offset += 4
                clen_paths = struct.unpack_from("<Q", data, offset)[0]
                offset += 8
                offset += 4
                clen_cigars = struct.unpack_from("<Q", data, offset)[0]
                offset += 8
                offset += 8 * 3
                compressed_len = clen_names + clen_paths + clen_cigars

            elif section_id == SECTION_ID_WALKS:
                if len(data) < offset + 4 * 2 + 4 + 5 * 16:
                    raise ValueError("BGFA file is too short")
                offset += 4 * 2 + 4
                compressed_len = 0
                for _ in range(5):
                    clen = struct.unpack_from("<Q", data, offset)[0]
                    offset += 8
                    offset += 8
                    compressed_len += clen

            else:
                if len(data) < offset + 2 + 8 + 8:
                    raise ValueError("BGFA file is too short")
                offset += 2
                compressed_len = struct.unpack_from("<Q", data, offset)[0]
                offset += 8
                offset += 8
        except struct.error:
            raise ValueError("BGFA file is too short")

        if offset + compressed_len > len(data):
            raise ValueError("BGFA file is too short")

        offset += compressed_len

        return None, offset - start_offset


# =============================================================================
# Public API - Reader functions
# =============================================================================


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
    with open(input_file, "rb") as f:
        data = f.read()

    if len(data) < 8:
        raise ValueError("BGFA file is too short")

    if not data:
        raise ValueError("Empty file")

    reader = ReaderBGFA()

    header = reader._parse_header(data)
    if verbose:
        logger.info("=== BGFA File Header ===")
        logger.info("  Magic number: 0x%08X", header["magic"])
        logger.info("  Version: %d", header["version"])
        logger.info("  Header text: %s", header["header_text"])
        logger.info("  Header size: %d bytes", header["header_size"])

    offset = header["header_size"]
    reader._segment_names = []

    stats = []

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
                    "ulen_fromto": clen_fromto,
                    "clen_cigars": clen_cigars,
                    "ulen_cigars": ulen_cigars,
                }
            )
            offset += consumed

        elif section_id == SECTION_ID_PATHS:
            if verbose:
                logger.info("")
                logger.info("=== Block %d: Paths (section_id=%d) ===", block_index, section_id)

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
                    "clen_paths": clen_cigars,
                    "ulen_paths": ulen_cigars,
                    "clen_cigars": clen_cigars,
                    "ulen_cigars": ulen_cigars,
                }
            )
            offset += consumed

        elif section_id == SECTION_ID_WALKS:
            if verbose:
                logger.info("")
                logger.info("=== Block %d: Walks (section_id=%d) ===", block_index, section_id)

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

    filtered_stats = []
    if option_filter and option_filter in OPTION_SECTION_LENGTH_MAP:
        target_section_id, compressed_field, uncompressed_field = OPTION_SECTION_LENGTH_MAP[option_filter]

        for stat in stats:
            if stat["section_id"] == target_section_id:
                filtered_stat = {
                    "block_index": stat["block_index"],
                    "section_id": stat["section_id"],
                    "section_type": stat["section_type"],
                    "record_num": stat["record_num"],
                    "compressed_length": stat.get(compressed_field, 0),
                    "uncompressed_length": stat.get(uncompressed_field, 0),
                }
                filtered_stats.append(filtered_stat)

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
        filtered_stats = stats

    csv_fieldnames = [
        "block_index",
        "section_id",
        "section_type",
        "record_num",
        "compressed_length",
        "uncompressed_length",
    ]

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
        import sys as _sys

        writer = csv.DictWriter(_sys.stdout, fieldnames=csv_fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(csv_stats)
    else:
        with open(output_file, "w", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=csv_fieldnames, lineterminator="\n")
            writer.writeheader()
            writer.writerows(csv_stats)
