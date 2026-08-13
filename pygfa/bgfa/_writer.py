"""BGFA writer module."""

from __future__ import annotations

import io
import struct

from pygfa.bgfa._codec_utils import pack_bits_lsb, serialize_opt_fields
from pygfa.encoding.integer_list_encoding import compress_integer_list_uints_delta
from pygfa.bgfa._constants import (
    BGFA_MAGIC,
    BGFA_VERSION,
    CIGAR_DECOMPOSITION_NONE,
    CIGAR_DECOMPOSITION_NUM_OPS_LENGTHS_OPS,
    CIGAR_DECOMPOSITION_STRING,
    DEFAULT_BLOCK_SIZE,
    INTEGER_ENCODING_VARINT,
    SECTION_ID_LINKS,
    SECTION_ID_OPT_FIELDS,
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
    WALK_DECOMPOSITION_ORIENTATION_NUMID,
    WALK_DECOMPOSITION_ORIENTATION_STRID,
    logger,
)
from pygfa.bgfa._reader import get_integer_encoder, get_integer_encoder_from_code
from pygfa.encoding.cigar_encoding import (
    _ops_string_encoder_for_code,
    compress_string_cigar_decomposed,
)
from pygfa.encoding.enums import IntegerEncoding, StringEncoding, make_compression_code
from pygfa.encoding.heuristic import select_string_encoding
from pygfa.exceptions import GFAError
from pygfa.gfa import GFA

# =============================================================================
# String Compression Helper
# =============================================================================


def _compress_string_for_bgfa(string_list: list[str], compression_code: int) -> bytes:
    """Compress a list of strings using the specified compression code."""
    str_encoding = compression_code & 0xFF
    int_encoding = (compression_code >> 8) & 0xFF

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
        STRING_ENCODING_ZSTD_DICT: "zstd_dict",
    }
    method = method_map.get(str_encoding, "none")
    int_encoder = get_integer_encoder(compression_code)
    return compress_string_list(string_list, int_encoder, method, first_byte_strategy=int_encoding)


def _parse_walk_string(walk_str: str) -> list[tuple[str, str]]:
    """Parse a GFA walk string into (segment_name, orientation) pairs.

    Handles both the '>'/'<' char form and the '+'/'-' sign form, e.g.
    "1+2-3+" and ">1<2>3" both yield [("1", "+"), ("2", "-"), ("3", "+")].
    """
    result: list[tuple[str, str]] = []
    i = 0
    n = len(walk_str)
    while i < n:
        c = walk_str[i]
        if c == ">":
            orientation = "+"
            i += 1
        elif c == "<":
            orientation = "-"
            i += 1
        else:
            orientation = None
        start = i
        while i < n and walk_str[i] not in "><":
            if orientation is None and walk_str[i] in "+-":
                break
            i += 1
        name = walk_str[start:i]
        if orientation is None:
            if i < n and walk_str[i] in "+-":
                orientation = "+" if walk_str[i] == "+" else "-"
                i += 1
            else:
                orientation = "+"
        if name:
            result.append((name, orientation))
    return result


# =============================================================================
# Compression Strategy Parser
# =============================================================================


def parse_compression_strategy(s: str) -> int:
    """Parse a compression strategy string into a code.

    Format: "int_encoding-str_encoding" (e.g., "varint-2bit") or
             "int_encoding+str_encoding" (e.g., "bit_packing+brotli")
             or just "str_encoding" (e.g., "superstring_ppm", "brotli")
    """
    if "+" in s:
        p = s.lower().split("+", 1)
    elif "-" in s:
        p = s.lower().split("-", 1)
    else:
        p = [s.lower()]

    i_map = {e.name.lower().replace("_", ""): e.value for e in IntegerEncoding}
    s_map = {e.name.lower().replace("_", ""): e.value for e in StringEncoding}

    i_map["identity"] = 0
    s_map["identity"] = 0
    s_map["2bit"] = StringEncoding.TWO_BIT_DNA.value
    s_map["2-bit"] = StringEncoding.TWO_BIT_DNA.value

    if len(p) == 1:
        str_key = p[0].replace("_", "")
        str_enc = s_map.get(str_key, STRING_ENCODING_NONE)
        if str_enc != STRING_ENCODING_NONE:
            return make_compression_code(INTEGER_ENCODING_VARINT, str_enc)
        int_enc = i_map.get(str_key, INTEGER_ENCODING_VARINT)
        return make_compression_code(int_enc, STRING_ENCODING_NONE)

    int_enc = i_map.get(p[0].replace("_", ""), INTEGER_ENCODING_VARINT)
    str_enc = s_map.get(p[1].replace("_", ""), STRING_ENCODING_NONE)

    return make_compression_code(int_enc, str_enc)


# =============================================================================
# BGFA Writer
# =============================================================================


class BGFAWriter:
    """BGFA file writer."""

    def __init__(self, gfa: GFA, block_size: int = DEFAULT_BLOCK_SIZE, comp_options: dict = None):
        self._gfa = gfa
        self._block_size = block_size
        self._comp_options = {}
        self._use_heuristic = True
        self._use_numpy = False
        if comp_options:
            for k, v in comp_options.items():
                if k == "use_heuristic":
                    self._use_heuristic = bool(v)
                elif k == "use_numpy":
                    self._use_numpy = bool(v)
                elif isinstance(v, str):
                    self._comp_options[k] = parse_compression_strategy(v)
                else:
                    self._comp_options[k] = v
        self._segment_map = {}

    def _write_header(self, buf: io.BytesIO) -> None:
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
        buf.write(b"\0")
        logger.debug("BGFAWriter._write_header() -> exit")

    def _write_segments_block(self, buf: io.BytesIO, chunk: list[tuple], names_enc: int, seqs_enc: int) -> None:
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

        payload_names = _compress_string_for_bgfa(names, names_enc)
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

        for u, v, k, d in chunk:
            fn = d.get("from_node", u)
            tn = d.get("to_node", v)
            f_ids.append(self._segment_map.get(fn, 0) + 1)
            t_ids.append(self._segment_map.get(tn, 0) + 1)
            from_orn = d.get("from_orn", "+")
            to_orn = d.get("to_orn", "+")
            f_os.append(0 if from_orn == "+" else 1)
            t_os.append(0 if to_orn == "+" else 1)
            cigs.append(d.get("alignment", "*"))

        int_encoder = get_integer_encoder(c_ft)
        p_from = int_encoder(f_ids)
        p_to = int_encoder(t_ids)
        p_f_or = pack_bits_lsb(f_os)
        p_t_or = pack_bits_lsb(t_os)
        p_ft = p_from + p_to + p_f_or + p_t_or

        dd = c_cig & 0xFF
        if dd == CIGAR_DECOMPOSITION_NUM_OPS_LENGTHS_OPS:
            rr_encoder = get_integer_encoder_from_code((c_cig >> 8) & 0xFF)
            ii_encoder = get_integer_encoder_from_code((c_cig >> 16) & 0xFF)
            ss_encoder = _ops_string_encoder_for_code((c_cig >> 24) & 0xFF)
            p_cig = compress_string_cigar_decomposed(cigs, ii_encoder, rr_encoder, ss_encoder)
        elif dd in (CIGAR_DECOMPOSITION_NONE, CIGAR_DECOMPOSITION_STRING):
            # Proper 4-byte CIGAR code: str_enc at bits 31-24, int_enc at bits 15-8
            int_enc = (c_cig >> 8) & 0xFF
            str_enc = (c_cig >> 24) & 0xFF
            str_code = (int_enc << 8) | str_enc
            p_cig = _compress_string_for_bgfa(cigs, str_code)
        else:
            # 2-byte compression code (int_enc << 8 | str_enc) passed as CIGAR encoding
            # Convert to proper 4-byte CIGAR code with CIGAR_DECOMPOSITION_NONE
            str_enc = c_cig & 0xFF
            int_enc = (c_cig >> 8) & 0xFF
            str_code = (int_enc << 8) | str_enc
            p_cig = _compress_string_for_bgfa(cigs, str_code)
            c_cig = (str_enc << 24) | (int_enc << 8) | CIGAR_DECOMPOSITION_NONE

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
        all_seg_names = []
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
                    all_seg_names.append("")
                    all_orientations.append(0)
                    continue
                name = seg[:-1]
                orientation = seg[-1]
                seg_id = self._segment_map.get(name, 0)
                all_seg_ids.append(seg_id)
                all_seg_names.append(name)
                all_orientations.append(0 if orientation == "+" else 1)

            overlaps = pd.get("overlaps", [])
            if isinstance(overlaps, list) and overlaps:
                all_cigars.append(overlaps[0])
            elif isinstance(overlaps, str) and overlaps not in ("*", "", None):
                all_cigars.append(overlaps)
            else:
                all_cigars.append("*")

        p_names = _compress_string_for_bgfa(path_names, names_enc)

        dd = cig_enc & 0xFF
        if dd == CIGAR_DECOMPOSITION_NUM_OPS_LENGTHS_OPS:
            rr_encoder = get_integer_encoder_from_code((cig_enc >> 8) & 0xFF)
            ii_encoder = get_integer_encoder_from_code((cig_enc >> 16) & 0xFF)
            ss_encoder = _ops_string_encoder_for_code((cig_enc >> 24) & 0xFF)
            p_cig = compress_string_cigar_decomposed(all_cigars, ii_encoder, rr_encoder, ss_encoder)
        elif dd in (CIGAR_DECOMPOSITION_NONE, CIGAR_DECOMPOSITION_STRING):
            # Proper 4-byte CIGAR code: str_enc at bits 31-24, int_enc at bits 15-8
            int_enc = (cig_enc >> 8) & 0xFF
            str_enc = (cig_enc >> 24) & 0xFF
            str_code = (int_enc << 8) | str_enc
            p_cig = _compress_string_for_bgfa(all_cigars, str_code)
        else:
            # 2-byte compression code (int_enc << 8 | str_enc) passed as CIGAR encoding
            # Convert to proper 4-byte CIGAR code with CIGAR_DECOMPOSITION_NONE
            str_enc = cig_enc & 0xFF
            int_enc = (cig_enc >> 8) & 0xFF
            str_code = (int_enc << 8) | str_enc
            p_cig = _compress_string_for_bgfa(all_cigars, str_code)
            cig_enc = (str_enc << 24) | (int_enc << 8) | CIGAR_DECOMPOSITION_NONE

        int_encoder = get_integer_encoder_from_code(walk_enc & 0xFF)
        p_walk_lengths = int_encoder(all_walk_lengths)
        p_orientations = pack_bits_lsb(all_orientations, use_numpy=getattr(self, '_use_numpy', False))
        if (walk_enc >> 24) & 0xFF == WALK_DECOMPOSITION_ORIENTATION_STRID:
            # STRID payload: walk lengths + string segment names + orientation bits.
            # Bits 8-23 of walk_enc hold the 16-bit names code (int_enc << 8 | str_enc).
            str_code = (walk_enc >> 8) & 0xFFFF
            p_seg_names = _compress_string_for_bgfa(all_seg_names, str_code)
            p_walk = p_walk_lengths + p_seg_names + p_orientations
        else:
            if getattr(self, '_use_numpy', False):
                from pygfa.encoding.numpy_backend import uints_delta_encode_numpy

                p_seg_ids = uints_delta_encode_numpy(all_seg_ids, int_encoder)
            else:
                p_seg_ids = compress_integer_list_uints_delta(all_seg_ids, int_encoder)
            p_walk = p_walk_lengths + p_seg_ids + p_orientations

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

    def _write_walks_block(
        self,
        buf: io.BytesIO,
        chunk: list[dict],
        comp_samples: int,
        comp_hep: int,
        comp_seq: int,
        comp_positions: int,
        comp_walks: int,
    ) -> None:
        """Write a walks block (section id 5) in the layout `_parse_walks_blocks` consumes."""
        logger.debug(
            "BGFAWriter._write_walks_block() -> entry, chunk_size=%d, comp_samples=0x%04X, comp_hep=0x%04X, comp_seq=0x%04X, comp_positions=0x%04X, comp_walks=0x%08X",
            len(chunk),
            comp_samples,
            comp_hep,
            comp_seq,
            comp_positions,
            comp_walks,
        )

        sample_ids = []
        hap_indices = []
        seq_ids = []
        starts = []
        ends = []
        all_walk_lengths = []
        all_seg_ids = []
        all_seg_names = []
        all_orientations = []

        for wd in chunk:
            sample_ids.append(wd.get("sample_id", ""))
            hap_indices.append(int(wd.get("hapindex", 0)))
            seq_ids.append(wd.get("seq_id", ""))
            start = wd.get("seq_start")
            end = wd.get("seq_end")
            starts.append(0 if start is None else int(start))
            ends.append(0 if end is None else int(end))

            segments = _parse_walk_string(wd.get("walk", ""))
            all_walk_lengths.append(len(segments))
            for name, orientation in segments:
                if name not in self._segment_map:
                    raise GFAError(f"Walk references unknown segment '{name}'")
                all_seg_ids.append(self._segment_map[name])
                all_seg_names.append(name)
                all_orientations.append(0 if orientation == "+" else 1)

        p_samples = _compress_string_for_bgfa(sample_ids, comp_samples)
        int_enc_hep = get_integer_encoder_from_code((comp_hep >> 8) & 0xFF)
        p_hep = int_enc_hep(hap_indices)
        p_seq = _compress_string_for_bgfa(seq_ids, comp_seq)
        int_enc_pos = get_integer_encoder_from_code((comp_positions >> 8) & 0xFF)
        p_positions = compress_integer_list_uints_delta(starts, int_enc_pos) + compress_integer_list_uints_delta(
            ends, int_enc_pos
        )
        int_enc_walk = get_integer_encoder_from_code(comp_walks & 0xFF)
        p_walk_lengths = int_enc_walk(all_walk_lengths)
        p_orientations = pack_bits_lsb(all_orientations, use_numpy=getattr(self, "_use_numpy", False))
        if (comp_walks >> 24) & 0xFF == WALK_DECOMPOSITION_ORIENTATION_STRID:
            # STRID payload: walk lengths + string segment names + orientation bits.
            # Bits 8-23 of comp_walks hold the 16-bit names code (int_enc << 8 | str_enc).
            str_code = (comp_walks >> 8) & 0xFFFF
            p_seg_names = _compress_string_for_bgfa(all_seg_names, str_code)
            p_walks = p_walk_lengths + p_seg_names + p_orientations
        else:
            p_seg_ids = compress_integer_list_uints_delta(all_seg_ids, int_enc_walk)
            p_walks = p_walk_lengths + p_seg_ids + p_orientations

        buf.write(struct.pack("<B", SECTION_ID_WALKS))
        buf.write(struct.pack("<H", len(chunk)))
        buf.write(struct.pack("<H", comp_samples))
        buf.write(struct.pack("<H", comp_hep))
        buf.write(struct.pack("<H", comp_seq))
        buf.write(struct.pack("<H", comp_positions))
        buf.write(struct.pack("<I", comp_walks))
        buf.write(struct.pack("<Q", len(p_samples)))
        buf.write(struct.pack("<Q", sum(len(s) for s in sample_ids)))
        buf.write(struct.pack("<Q", len(p_hep)))
        buf.write(struct.pack("<Q", len(hap_indices)))
        buf.write(struct.pack("<Q", len(p_seq)))
        buf.write(struct.pack("<Q", sum(len(s) for s in seq_ids)))
        buf.write(struct.pack("<Q", len(p_positions)))
        # ulen_positions stores a value count (starts + ends), not a byte sum like
        # samples/seq; the reader ignores it and validate_bgfa checks structurally.
        buf.write(struct.pack("<Q", len(starts) * 2))
        buf.write(struct.pack("<Q", len(p_walks)))
        buf.write(struct.pack("<Q", sum(all_walk_lengths)))
        buf.write(p_samples + p_hep + p_seq + p_positions + p_walks)
        logger.debug(
            "BGFAWriter._write_walks_block() -> exit, p_samples_size=%d, p_hep_size=%d, p_seq_size=%d, p_positions_size=%d, p_walks_size=%d",
            len(p_samples),
            len(p_hep),
            len(p_seq),
            len(p_positions),
            len(p_walks),
        )

    def _write_opt_fields_block(self, buf: io.BytesIO, names: list[str], edges: list, enc: int) -> None:
        """Write a block holding optional fields for segments and links.

        The payload is a list of tab-joined ``TAG:TYPE:VALUE`` strings, one per
        segment (in segment order) followed by one per link (in link order).
        """
        nodes_data = dict(self._gfa.nodes(data=True))
        seg_reserved = {"nid", "sequence", "slen"}
        seg_opts = []
        for name in names:
            data = nodes_data.get(name, {})
            opts = {k: v for k, v in data.items() if k not in seg_reserved}
            seg_opts.append(serialize_opt_fields(opts))

        link_reserved = {
            "eid",
            "from_node",
            "from_orn",
            "to_node",
            "to_orn",
            "alignment",
            "distance",
            "variance",
            "from_positions",
            "to_positions",
            "from_segment_end",
            "to_segment_end",
        }
        link_opts = []
        for _u, _v, _k, d in edges:
            opts = {k2: v2 for k2, v2 in d.items() if k2 not in link_reserved}
            link_opts.append(serialize_opt_fields(opts))

        all_opts = seg_opts + link_opts
        if not any(all_opts):
            logger.debug("BGFAWriter._write_opt_fields_block() -> no opt fields, skipping block")
            return

        payload = _compress_string_for_bgfa(all_opts, enc)

        buf.write(struct.pack("<B", SECTION_ID_OPT_FIELDS))
        buf.write(struct.pack("<H", len(seg_opts)))
        buf.write(struct.pack("<H", len(link_opts)))
        buf.write(struct.pack("<H", enc))
        buf.write(struct.pack("<Q", len(payload)))
        buf.write(struct.pack("<Q", sum(len(s) for s in all_opts)))
        buf.write(payload)
        logger.debug(
            "BGFAWriter._write_opt_fields_block() -> exit, seg_opts=%d, link_opts=%d, payload_size=%d",
            len(seg_opts),
            len(link_opts),
            len(payload),
        )

    def to_bgfa(self, verbose: bool = False, debug: bool = False, logfile: str = None, **kwargs) -> bytes:
        logger.debug(
            "BGFAWriter.to_bgfa() -> entry, node_count=%d, edge_count=%d, block_size=%d",
            len(self._gfa.nodes()),
            len(self._gfa.edges()),
            self._block_size,
        )
        for k, v in kwargs.items():
            if k.endswith("_enc"):
                if isinstance(v, str):
                    self._comp_options[k] = parse_compression_strategy(v)
                else:
                    self._comp_options[k] = v

        buf = io.BytesIO()

        logger.debug("BGFAWriter.to_bgfa() -> calling _write_header()")
        self._write_header(buf)

        names = list(self._gfa.nodes())
        self._segment_map = {n: i for i, n in enumerate(names)}

        if self._use_heuristic:
            if "segment_names_enc" not in self._comp_options:
                names_sample = [n.encode("ascii") for n in names[:100]]
                str_enc = select_string_encoding(b"".join(names_sample))
                self._comp_options["segment_names_enc"] = make_compression_code(
                    INTEGER_ENCODING_VARINT, str_enc.value
                )
            if "sequences_enc" not in self._comp_options and "seq_enc" not in self._comp_options:
                nodes_data = dict(self._gfa.nodes(data=True))
                seq_sample = b"".join(
                    nodes_data[n].get("sequence", "*").encode("ascii")[:100] for n in names[:50]
                )
                str_enc = select_string_encoding(seq_sample)
                self._comp_options["sequences_enc"] = make_compression_code(
                    INTEGER_ENCODING_VARINT, str_enc.value
                )

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

        walks = list(self._gfa.walks().values())
        if walks:
            walk_samples_enc = self._comp_options.get(
                "walk_sample_ids_enc",
                make_compression_code(INTEGER_ENCODING_VARINT, STRING_ENCODING_NONE),
            )
            walk_hep_enc = self._comp_options.get(
                "walk_haplotype_indices_enc",
                make_compression_code(INTEGER_ENCODING_VARINT, STRING_ENCODING_NONE),
            )
            walk_seq_enc = self._comp_options.get(
                "walk_sequence_ids_enc",
                make_compression_code(INTEGER_ENCODING_VARINT, STRING_ENCODING_NONE),
            )
            walk_pos_start_enc = self._comp_options.get(
                "walk_positions_start_enc",
                make_compression_code(INTEGER_ENCODING_VARINT, STRING_ENCODING_NONE),
            )
            # The block stores a single positions code; the end encoding is accepted
            # for CLI compatibility but the start encoding is used for both.
            _ = self._comp_options.get(
                "walk_positions_end_enc",
                make_compression_code(INTEGER_ENCODING_VARINT, STRING_ENCODING_NONE),
            )
            walk_steps_enc = self._comp_options.get(
                "walk_steps_enc",
                make_compression_code(INTEGER_ENCODING_VARINT, STRING_ENCODING_NONE),
            )
            # The block stores a single positions code; use the start encoding.
            comp_positions = walk_pos_start_enc
            # 4-byte walk code: int encoding in the low byte, ORIENTATION_NUMID in the top byte.
            if (walk_steps_enc >> 24) & 0xFF in (
                WALK_DECOMPOSITION_ORIENTATION_STRID,
                WALK_DECOMPOSITION_ORIENTATION_NUMID,
            ):
                comp_walks = walk_steps_enc
            else:
                comp_walks = ((walk_steps_enc >> 8) & 0xFF) | (WALK_DECOMPOSITION_ORIENTATION_NUMID << 24)

            logger.debug(
                "BGFAWriter.to_bgfa() -> writing %d walks, comp_samples=0x%04X, comp_hep=0x%04X, comp_seq=0x%04X, comp_positions=0x%04X, comp_walks=0x%08X",
                len(walks),
                walk_samples_enc,
                walk_hep_enc,
                walk_seq_enc,
                comp_positions,
                comp_walks,
            )

            for i in range(0, len(walks), self._block_size):
                chunk = walks[i : i + self._block_size]
                self._write_walks_block(
                    buf, chunk, walk_samples_enc, walk_hep_enc, walk_seq_enc, comp_positions, comp_walks
                )

        opt_fields_enc = self._comp_options.get(
            "opt_fields_enc", make_compression_code(INTEGER_ENCODING_VARINT, STRING_ENCODING_NONE)
        )
        self._write_opt_fields_block(buf, names, edges, opt_fields_enc)

        result = buf.getvalue()
        logger.debug("BGFAWriter.to_bgfa() -> exit, total_bgfa_size=%d bytes", len(result))
        return result


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
