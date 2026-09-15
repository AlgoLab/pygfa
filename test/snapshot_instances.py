"""Registry of BGFA snapshot test instances.

Each instance is a dict with:
- id: unique snake_case identifier (used as the snapshot filename)
- gfa_text: GFA text parsed via GFA.from_gfa, OR
- build: callable returning a GFA object
- comp_options: dict passed to to_bgfa(compression_options=...)
- block_size: block size (default 1024)
- tags: list of spec areas covered

The snapshot test (test_bgfa_snapshots.py) encodes each instance to BGFA and
compares the bytes against test/snapshots/bgfa/{id}.bgfa, then roundtrips the
file through read_bgfa() and validates it with validate_bgfa().
"""

from pygfa.encoding.enums import (
    CigarDecomposition,
    IntegerEncoding,
    StringEncoding,
    WalkDecomposition,
    make_compression_code,
)
from pygfa.graph_element.edge import Edge
from pygfa.graph_element.node import Node
from pygfa.gfa import GFA

# --- codec helpers -----------------------------------------------------------


def _code(int_enc, str_enc):
    """2-byte compression code (int encoding in the high byte)."""
    return make_compression_code(int_enc, str_enc)


def _cigar_code(dd, rr, ii, ss):
    """4-byte CIGAR strategy code, little-endian byte order [dd, rr, ii, ss]."""
    return (dd << 0) | (rr << 8) | (ii << 16) | (ss << 24)


def _walk_code(decomp, int_enc, names_code=0x0000):
    """4-byte walk strategy code: [decomp, names_hi, names_lo, int_enc].

    The names code (bits 8-23) is only used by the STRID decomposition;
    NUMID stores segment ids as integers and ignores it.
    """
    return (int_enc << 0) | (names_code << 8) | (decomp << 24)


# --- encoding constants ------------------------------------------------------

VARINT = IntegerEncoding.VARINT
FIXED16 = IntegerEncoding.FIXED16
FIXED32 = IntegerEncoding.FIXED32
FIXED64 = IntegerEncoding.FIXED64
ELIAS_GAMMA = IntegerEncoding.ELIAS_GAMMA
ELIAS_OMEGA = IntegerEncoding.ELIAS_OMEGA
GOLOMB = IntegerEncoding.GOLOMB
RICE = IntegerEncoding.RICE
STREAMVBYTE = IntegerEncoding.STREAMVBYTE
VBYTE = IntegerEncoding.VBYTE
PFOR_DELTA = IntegerEncoding.PFOR_DELTA
SIMPLE_8B = IntegerEncoding.SIMPLE_8B
GROUP_VARINT = IntegerEncoding.GROUP_VARINT
BIT_PACKING = IntegerEncoding.BIT_PACKING
FIBONACCI = IntegerEncoding.FIBONACCI
EXP_GOLOMB = IntegerEncoding.EXP_GOLOMB
BYTE_PACKED = IntegerEncoding.BYTE_PACKED
MASKED_VBYTE = IntegerEncoding.MASKED_VBYTE

NONE = StringEncoding.NONE
ZSTD = StringEncoding.ZSTD
GZIP = StringEncoding.GZIP
LZMA = StringEncoding.LZMA
HUFFMAN = StringEncoding.HUFFMAN
TWO_BIT = StringEncoding.TWO_BIT_DNA
ARITHMETIC = StringEncoding.ARITHMETIC
BWT_HUFFMAN = StringEncoding.BWT_HUFFMAN
RLE = StringEncoding.RLE
DICTIONARY = StringEncoding.DICTIONARY
ZSTD_DICT = StringEncoding.ZSTD_DICT
LZ4 = StringEncoding.LZ4
BROTLI = StringEncoding.BROTLI
PPM = StringEncoding.PPM

NUMID = WalkDecomposition.ORIENTATION_NUMID
STRID = WalkDecomposition.ORIENTATION_STRID

CIGAR_NONE = CigarDecomposition.NONE
CIGAR_NUMOPS = CigarDecomposition.NUM_OPERATIONS
CIGAR_STRING = CigarDecomposition.STRING

# --- graph builders ----------------------------------------------------------


def _chain_text(n, orn="+"):
    """GFA text for a chain of n segments connected by n-1 links."""
    lines = ["H\tVN:Z:1.0"]
    for i in range(n):
        lines.append(f"S\ts{i}\tACGT")
    for i in range(n - 1):
        lines.append(f"L\ts{i}\t{orn}\ts{i + 1}\t{orn}\t4M")
    return "\n".join(lines) + "\n"


def _chain_gfa(n, orn="+"):
    """GFA object for a chain of n segments connected by n-1 links."""
    g = GFA()
    for i in range(n):
        g.add_node(Node(f"s{i}", "ACGT"))
    for i in range(n - 1):
        g.add_edge(Edge(None, f"s{i}", orn, f"s{i + 1}", orn, (None, None), (None, None), "4M"))
    return g


def _cycle_gfa(n, orn="+"):
    """GFA object for a cycle of n segments connected by n links."""
    g = GFA()
    for i in range(n):
        g.add_node(Node(f"s{i}", "ACGT"))
    for i in range(n):
        g.add_edge(Edge(None, f"s{i}", orn, f"s{(i + 1) % n}", orn, (None, None), (None, None), "4M"))
    return g


def _many_segments(n):
    """GFA object with n segments and no other elements."""
    g = GFA()
    for i in range(n):
        g.add_node(Node(f"s{i}", "ACGT"))
    return g


def _combined_large():
    """300 segments, 300 links, 5 paths, 5 walks with opt fields."""
    g = GFA()
    for i in range(300):
        g.add_node(Node(f"s{i}", "ACGT" * 10, opt_fields={"LN": 40}))
    for i in range(299):
        g.add_edge(Edge(None, f"s{i}", "+", f"s{i + 1}", "+", (None, None), (None, None), "10M"))
    g.add_edge(Edge(None, "s299", "+", "s0", "+", (None, None), (None, None), "10M"))
    for p in range(5):
        segs = [f"s{i}+" for i in range(p * 60, p * 60 + 10)]
        g.add_path({"path_name": f"p{p}", "segments": segs, "overlaps": ["10M"] * (len(segs) - 1)})
    for w in range(5):
        segs = "".join(f"s{i}+" for i in range(w * 60, w * 60 + 10))
        g.add_walk(
            {
                "sample_id": f"sample{w}",
                "hapindex": 0,
                "seq_id": "chr1",
                "seq_start": w * 100,
                "seq_end": w * 100 + 1000,
                "walk": segs,
            }
        )
    return g


def _many_paths(n):
    """GFA object with n paths over a 10-segment chain."""
    g = _chain_gfa(10)
    for p in range(n):
        segs = [f"s{i}+" for i in (p % 8, (p + 1) % 8, (p + 2) % 8)]
        g.add_path({"path_name": f"p{p}", "segments": segs, "overlaps": ["4M", "4M"]})
    return g


def _many_walks(n):
    """GFA object with n walks over a 10-segment chain."""
    g = _chain_gfa(10)
    for w in range(n):
        segs = "".join(f"s{i}+" for i in (w % 8, (w + 1) % 8, (w + 2) % 8))
        g.add_walk(
            {
                "sample_id": f"sample{w}",
                "hapindex": 0,
                "seq_id": "chr1",
                "seq_start": 0,
                "seq_end": 100,
                "walk": segs,
            }
        )
    return g


# --- shared GFA text snippets ------------------------------------------------

_SEGS_4 = (
    "H\tVN:Z:1.0\n"
    "S\ts1\tACGTACGTACGTACGTACGTACGTACGTACGT\n"
    "S\ts2\tTGCAACGTACGTACGTACGTACGTACGTACGT\n"
    "S\ts3\tACGTACGTACGTACGTACGTACGTACGTACGT\n"
    "S\ts4\tGGGGCCCCAAAATTTTACGTACGTACGTACGT\n"
)

_LINKS_4 = (
    "H\tVN:Z:1.0\n"
    "S\ts1\tACGT\nS\ts2\tTGCA\nS\ts3\tAAAA\nS\ts4\tCCCC\n"
    "L\ts1\t+\ts2\t+\t4M\n"
    "L\ts2\t-\ts3\t+\t4M\n"
    "L\ts3\t+\ts4\t-\t4M\n"
    "L\ts4\t-\ts1\t+\t4M\n"
)

_PATHS_2 = (
    "H\tVN:Z:1.0\n"
    "S\ts1\tACGT\nS\ts2\tTGCA\nS\ts3\tAAAA\nS\ts4\tCCCC\n"
    "P\tp1\ts1+,s2-,s3+\t4M,4M\n"
    "P\tp2\ts4+,s1+\t4M\n"
)

_WALKS_2 = (
    "H\tVN:Z:1.0\n"
    "S\ts1\tACGT\nS\ts2\tTGCA\nS\ts3\tAAAA\n"
    "W\tsample1\t0\tchr1\t0\t100\ts1+s2-s3+\n"
    "W\tsample2\t1\tchr2\t50\t150\ts3+s2+\n"
)

# --- instances ---------------------------------------------------------------

INSTANCES = [
    # --- File header ---------------------------------------------------------
    {
        "id": "header_minimal",
        "gfa_text": "H\tVN:Z:1.0\nS\ts1\tACGT\n",
        "tags": ["header"],
    },
    {
        "id": "header_no_header",
        "gfa_text": "S\ts1\tACGT\n",
        "tags": ["header"],
    },
    {
        "id": "header_comments",
        "gfa_text": "# a comment line\n# another comment\nH\tVN:Z:1.0\nS\ts1\tACGT\n",
        "tags": ["header"],
    },
    # --- Segments: structure -------------------------------------------------
    {
        "id": "segments_single",
        "gfa_text": "H\tVN:Z:1.0\nS\ts1\tACGT\n",
        "tags": ["segments"],
    },
    {
        "id": "segments_multi",
        "gfa_text": "H\tVN:Z:1.0\nS\ts1\tACGT\nS\ts2\tTGCA\nS\ts3\tAAAA\n",
        "tags": ["segments"],
    },
    {
        "id": "segments_star_sequence",
        "gfa_text": "H\tVN:Z:1.0\nS\ts1\t*\nS\ts2\tACGT\n",
        "tags": ["segments"],
    },
    {
        "id": "segments_numeric_names",
        "gfa_text": "H\tVN:Z:1.0\nS\t1\tACGT\nS\t2\tTGCA\nS\t3\tAAAA\n",
        "tags": ["segments"],
    },
    {
        "id": "segments_special_names",
        "gfa_text": "H\tVN:Z:1.0\nS\tcontig_1\tACGT\nS\tchr.2\tTGCA\nS\tx/y:3\tAAAA\n",
        "tags": ["segments"],
    },
    {
        "id": "segments_many_255",
        "build": lambda: _many_segments(255),
        "tags": ["segments", "uint16"],
    },
    {
        "id": "segments_many_256",
        "build": lambda: _many_segments(256),
        "tags": ["segments", "uint16"],
    },
    {
        "id": "segments_long_sequence",
        "gfa_text": "H\tVN:Z:1.0\nS\ts1\t" + "ACGT" * 250 + "\n",
        "tags": ["segments"],
    },
    {
        "id": "segments_lowercase_dna",
        "gfa_text": "H\tVN:Z:1.0\nS\ts1\tacgtacgtacgt\n",
        "comp_options": {"sequences_enc": "varint-none"},
        "tags": ["segments"],
    },
    # --- Segments: string encodings ------------------------------------------
    {
        "id": "segments_enc_identity",
        "gfa_text": _SEGS_4,
        "comp_options": {"sequences_enc": "varint-none"},
        "tags": ["segments", "string-encoding"],
    },
    {
        "id": "segments_enc_zstd",
        "gfa_text": _SEGS_4,
        "comp_options": {"sequences_enc": "varint-zstd"},
        "tags": ["segments", "string-encoding"],
    },
    {
        "id": "segments_enc_gzip",
        "gfa_text": _SEGS_4,
        "comp_options": {"sequences_enc": "varint-gzip"},
        "tags": ["segments", "string-encoding"],
    },
    {
        "id": "segments_enc_lzma",
        "gfa_text": _SEGS_4,
        "comp_options": {"sequences_enc": "varint-lzma"},
        "tags": ["segments", "string-encoding"],
    },
    {
        "id": "segments_enc_huffman",
        "gfa_text": _SEGS_4,
        "comp_options": {"sequences_enc": "varint-huffman"},
        "tags": ["segments", "string-encoding"],
    },
    {
        "id": "segments_enc_2bit",
        "gfa_text": _SEGS_4,
        "comp_options": {"sequences_enc": "varint-2bit"},
        "tags": ["segments", "string-encoding"],
    },
    {
        "id": "segments_enc_2bit_exceptions",
        "gfa_text": "H\tVN:Z:1.0\nS\ts1\tACGTNACGTNACGT\nS\ts2\tACGTACGTACGT\n",
        "comp_options": {"sequences_enc": "varint-2bit"},
        "tags": ["segments", "string-encoding", "2bit-exceptions"],
    },
    {
        "id": "segments_enc_2bit_ambiguous",
        "gfa_text": "H\tVN:Z:1.0\nS\ts1\tACGTNRYKMSWBDHV-ACGT\n",
        "comp_options": {"sequences_enc": "varint-2bit"},
        "tags": ["segments", "string-encoding", "2bit-exceptions"],
    },
    {
        "id": "segments_enc_rle",
        "gfa_text": "H\tVN:Z:1.0\nS\ts1\tAAAAACCCCCGGGGGTTTTTAAAAACCCCC\nS\ts2\tACGTACGTACGTACGT\n",
        "comp_options": {"sequences_enc": "varint-rle"},
        "tags": ["segments", "string-encoding"],
    },
    {
        "id": "segments_enc_dictionary",
        "gfa_text": (
            "H\tVN:Z:1.0\n"
            "S\ts1\tACGTACGT\nS\ts2\tACGTACGT\nS\ts3\tTTTTGGGG\n"
            "S\ts4\tACGTACGT\nS\ts5\tCCCCAAAA\n"
        ),
        "comp_options": {"sequences_enc": "varint-dictionary"},
        "tags": ["segments", "string-encoding"],
    },
    {
        "id": "segments_enc_lz4",
        "gfa_text": _SEGS_4,
        "comp_options": {"sequences_enc": "varint-lz4"},
        "tags": ["segments", "string-encoding"],
    },
    {
        "id": "segments_enc_brotli",
        "gfa_text": _SEGS_4,
        "comp_options": {"sequences_enc": "varint-brotli"},
        "tags": ["segments", "string-encoding"],
    },
    {
        "id": "segments_enc_arithmetic",
        "gfa_text": _SEGS_4,
        "comp_options": {"sequences_enc": "varint-arithmetic"},
        "tags": ["segments", "string-encoding"],
    },
    {
        "id": "segments_enc_bwt_huffman",
        "gfa_text": _SEGS_4,
        "comp_options": {"sequences_enc": "varint-bwt_huffman"},
        "tags": ["segments", "string-encoding"],
    },
    {
        "id": "segments_enc_ppm",
        "gfa_text": _SEGS_4,
        "comp_options": {"sequences_enc": "varint-ppm"},
        "tags": ["segments", "string-encoding"],
    },
    {
        "id": "segments_enc_zstd_dict",
        "gfa_text": _SEGS_4,
        "comp_options": {"sequences_enc": "varint-zstd_dict"},
        "tags": ["segments", "string-encoding"],
    },
    # --- Segments: integer metadata encodings --------------------------------
    {
        "id": "segments_int_varint",
        "gfa_text": _SEGS_4,
        "comp_options": {"segment_names_enc": "varint-none"},
        "tags": ["segments", "int-encoding"],
    },
    {
        "id": "segments_int_fixed16",
        "gfa_text": _SEGS_4,
        "comp_options": {"segment_names_enc": "fixed16-none"},
        "tags": ["segments", "int-encoding"],
    },
    {
        "id": "segments_int_fixed32",
        "gfa_text": _SEGS_4,
        "comp_options": {"segment_names_enc": "fixed32-none"},
        "tags": ["segments", "int-encoding"],
    },
    {
        "id": "segments_int_fixed64",
        "gfa_text": _SEGS_4,
        "comp_options": {"segment_names_enc": "fixed64-none"},
        "tags": ["segments", "int-encoding"],
    },
    {
        "id": "segments_int_elias_gamma",
        "gfa_text": _SEGS_4,
        "comp_options": {"segment_names_enc": "elias_gamma-none"},
        "tags": ["segments", "int-encoding"],
    },
    {
        "id": "segments_int_elias_omega",
        "gfa_text": _SEGS_4,
        "comp_options": {"segment_names_enc": "elias_omega-none"},
        "tags": ["segments", "int-encoding"],
    },
    # --- Links: structure ----------------------------------------------------
    {
        "id": "links_single_pp",
        "gfa_text": "H\tVN:Z:1.0\nS\ts1\tACGT\nS\ts2\tTGCA\nL\ts1\t+\ts2\t+\t4M\n",
        "tags": ["links"],
    },
    {
        "id": "links_orientations_all",
        "gfa_text": _LINKS_4,
        "tags": ["links", "orientations"],
    },
    {
        "id": "links_cigar_star",
        "gfa_text": "H\tVN:Z:1.0\nS\ts1\tACGT\nS\ts2\tTGCA\nL\ts1\t+\ts2\t+\t*\n",
        "tags": ["links", "cigar"],
    },
    {
        "id": "links_multi_edge_same_nodes",
        "gfa_text": (
            "H\tVN:Z:1.0\nS\ts1\tACGT\nS\ts2\tTGCA\n"
            "L\ts1\t+\ts2\t+\t4M\nL\ts1\t-\ts2\t-\t2M2I\n"
        ),
        "tags": ["links", "multigraph"],
    },
    {
        "id": "links_chain",
        "gfa_text": _chain_text(5),
        "tags": ["links"],
    },
    {
        "id": "links_self_loop",
        "gfa_text": "H\tVN:Z:1.0\nS\ts1\tACGT\nL\ts1\t+\ts1\t+\t4M\n",
        "tags": ["links"],
    },
    {
        "id": "links_many_links",
        "build": lambda: _cycle_gfa(70),
        "tags": ["links", "bit-packing"],
    },
    {
        "id": "links_no_links",
        "gfa_text": "H\tVN:Z:1.0\nS\ts1\tACGT\nS\ts2\tTGCA\n",
        "tags": ["links"],
    },
    # --- Links: orientation bit-packing --------------------------------------
    {
        "id": "links_bits_under_64",
        "gfa_text": _chain_text(10),
        "tags": ["links", "bit-packing"],
    },
    {
        "id": "links_bits_exact_64",
        "build": lambda: _chain_gfa(65),
        "tags": ["links", "bit-packing"],
    },
    {
        "id": "links_bits_over_64",
        "build": lambda: _chain_gfa(66),
        "tags": ["links", "bit-packing"],
    },
    {
        "id": "links_bits_all_minus",
        "build": lambda: _cycle_gfa(70, orn="-"),
        "tags": ["links", "bit-packing"],
    },
    # --- Links: CIGAR decompositions -----------------------------------------
    {
        "id": "links_cigar_identity",
        "gfa_text": _LINKS_4,
        "comp_options": {"link_cigars_enc": _cigar_code(CIGAR_NONE, VARINT, 0, NONE)},
        "tags": ["links", "cigar"],
    },
    {
        "id": "links_cigar_numops",
        "gfa_text": _LINKS_4,
        "comp_options": {"link_cigars_enc": _cigar_code(CIGAR_NUMOPS, VARINT, VARINT, NONE)},
        "tags": ["links", "cigar"],
    },
    {
        "id": "links_cigar_string",
        "gfa_text": _LINKS_4,
        "comp_options": {"link_cigars_enc": _cigar_code(CIGAR_STRING, VARINT, 0, NONE)},
        "tags": ["links", "cigar"],
    },
    {
        "id": "links_cigar_complex",
        "gfa_text": (
            "H\tVN:Z:1.0\nS\ts1\tACGT\nS\ts2\tTGCA\nS\ts3\tAAAA\nS\ts4\tCCCC\n"
            "L\ts1\t+\ts2\t+\t10M2I5D3N1S\n"
            "L\ts2\t-\ts3\t+\t5H2S3M\n"
            "L\ts3\t+\ts4\t-\t*\n"
            "L\ts4\t-\ts1\t+\t1M1I1D1N1S1H1P1=1X\n"
        ),
        "comp_options": {"link_cigars_enc": _cigar_code(CIGAR_NUMOPS, VARINT, VARINT, NONE)},
        "tags": ["links", "cigar"],
    },
    {
        "id": "links_cigar_identity_zstd",
        "gfa_text": _LINKS_4,
        "comp_options": {"link_cigars_enc": _cigar_code(CIGAR_NONE, VARINT, 0, ZSTD)},
        "tags": ["links", "cigar"],
    },
    {
        "id": "links_cigar_string_zstd",
        "gfa_text": _LINKS_4,
        "comp_options": {"link_cigars_enc": _cigar_code(CIGAR_STRING, VARINT, 0, ZSTD)},
        "tags": ["links", "cigar"],
    },
    {
        "id": "links_cigar_all_ops",
        "gfa_text": (
            "H\tVN:Z:1.0\nS\ts1\tACGT\nS\ts2\tTGCA\n"
            "L\ts1\t+\ts2\t+\t1M1I1D1N1S1H1P1=1X\n"
        ),
        "comp_options": {"link_cigars_enc": _cigar_code(CIGAR_NUMOPS, VARINT, VARINT, NONE)},
        "tags": ["links", "cigar"],
    },
    # --- Links: integer encodings for endpoints ------------------------------
    {
        "id": "links_int_varint",
        "gfa_text": _chain_text(10),
        "comp_options": {"link_endpoints_enc": "varint-none"},
        "tags": ["links", "int-encoding"],
    },
    {
        "id": "links_int_fixed16",
        "gfa_text": _chain_text(10),
        "comp_options": {"link_endpoints_enc": "fixed16-none"},
        "tags": ["links", "int-encoding"],
    },
    {
        "id": "links_int_fixed32",
        "gfa_text": _chain_text(10),
        "comp_options": {"link_endpoints_enc": "fixed32-none"},
        "tags": ["links", "int-encoding"],
    },
    {
        "id": "links_int_fixed64",
        "gfa_text": _chain_text(10),
        "comp_options": {"link_endpoints_enc": "fixed64-none"},
        "tags": ["links", "int-encoding"],
    },
    {
        "id": "links_int_streamvbyte",
        "gfa_text": _chain_text(10),
        "comp_options": {"link_endpoints_enc": "streamvbyte-none"},
        "tags": ["links", "int-encoding"],
    },
    {
        "id": "links_int_vbyte",
        "gfa_text": _chain_text(10),
        "comp_options": {"link_endpoints_enc": "vbyte-none"},
        "tags": ["links", "int-encoding"],
    },
    {
        "id": "links_int_elias_gamma",
        "gfa_text": _chain_text(10),
        "comp_options": {"link_endpoints_enc": "elias_gamma-none"},
        "tags": ["links", "int-encoding"],
    },
    {
        "id": "links_int_elias_omega",
        "gfa_text": _chain_text(10),
        "comp_options": {"link_endpoints_enc": "elias_omega-none"},
        "tags": ["links", "int-encoding"],
    },
    {
        "id": "links_int_golomb",
        "gfa_text": _chain_text(10),
        "comp_options": {"link_endpoints_enc": "golomb-none"},
        "tags": ["links", "int-encoding"],
    },
    {
        "id": "links_int_rice",
        "gfa_text": _chain_text(10),
        "comp_options": {"link_endpoints_enc": "rice-none"},
        "tags": ["links", "int-encoding"],
    },
    {
        "id": "links_int_simple8b",
        "gfa_text": _chain_text(10),
        "comp_options": {"link_endpoints_enc": "simple8b-none"},
        "tags": ["links", "int-encoding"],
    },
    {
        "id": "links_int_pfor_delta",
        "gfa_text": _chain_text(10),
        "comp_options": {"link_endpoints_enc": "pfor_delta-none"},
        "tags": ["links", "int-encoding"],
    },
    {
        "id": "links_int_group_varint",
        "gfa_text": _chain_text(10),
        "comp_options": {"link_endpoints_enc": "group_varint-none"},
        "tags": ["links", "int-encoding"],
    },
    {
        "id": "links_int_bit_packing",
        "gfa_text": _chain_text(10),
        "comp_options": {"link_endpoints_enc": "bit_packing-none"},
        "tags": ["links", "int-encoding"],
    },
    {
        "id": "links_int_fibonacci",
        "gfa_text": _chain_text(10),
        "comp_options": {"link_endpoints_enc": "fibonacci-none"},
        "tags": ["links", "int-encoding"],
    },
    {
        "id": "links_int_exp_golomb",
        "gfa_text": _chain_text(10),
        "comp_options": {"link_endpoints_enc": "exp_golomb-none"},
        "tags": ["links", "int-encoding"],
    },
    {
        "id": "links_int_byte_packed",
        "gfa_text": _chain_text(10),
        "comp_options": {"link_endpoints_enc": "byte_packed-none"},
        "tags": ["links", "int-encoding"],
    },
    {
        "id": "links_int_masked_vbyte",
        "gfa_text": _chain_text(10),
        "comp_options": {"link_endpoints_enc": "masked_vbyte-none"},
        "tags": ["links", "int-encoding"],
    },
    # --- Paths: structure ----------------------------------------------------
    {
        "id": "paths_single",
        "gfa_text": "H\tVN:Z:1.0\nS\ts1\tACGT\nS\ts2\tTGCA\nP\tp1\ts1+,s2+\t4M\n",
        "tags": ["paths"],
    },
    {
        "id": "paths_multi_segment",
        "gfa_text": (
            "H\tVN:Z:1.0\nS\ts1\tACGT\nS\ts2\tTGCA\nS\ts3\tAAAA\nS\ts4\tCCCC\nS\ts5\tGGGG\n"
            "P\tp1\ts1+,s2+,s3+,s4+,s5+\t4M,4M,4M,4M\n"
        ),
        "tags": ["paths"],
    },
    {
        "id": "paths_overlaps",
        "gfa_text": "H\tVN:Z:1.0\nS\ts1\tACGT\nS\ts2\tTGCA\nS\ts3\tAAAA\nP\tp1\ts1+,s2+,s3+\t10M,5M\n",
        "tags": ["paths"],
    },
    {
        "id": "paths_overlap_star",
        "gfa_text": "H\tVN:Z:1.0\nS\ts1\tACGT\nS\ts2\tTGCA\nP\tp1\ts1+,s2+\t*\n",
        "tags": ["paths"],
    },
    {
        "id": "paths_reversed",
        "gfa_text": "H\tVN:Z:1.0\nS\ts1\tACGT\nS\ts2\tTGCA\nS\ts3\tAAAA\nP\tp1\ts1-,s2-,s3+\t4M,4M\n",
        "tags": ["paths", "orientations"],
    },
    {
        "id": "paths_many",
        "gfa_text": (
            "H\tVN:Z:1.0\nS\ts1\tACGT\nS\ts2\tTGCA\nS\ts3\tAAAA\nS\ts4\tCCCC\n"
            "P\tp1\ts1+,s2+\t4M\n"
            "P\tp2\ts2+,s3+\t4M\n"
            "P\tp3\ts3+,s4+\t4M\n"
            "P\tp4\ts4+,s1+\t4M\n"
            "P\tp5\ts1+,s3+\t4M\n"
        ),
        "tags": ["paths"],
    },
    {
        "id": "paths_no_paths",
        "gfa_text": _LINKS_4,
        "tags": ["paths"],
    },
    # --- Paths: walk decomposition -------------------------------------------
    {
        "id": "paths_walk_numid",
        "gfa_text": _PATHS_2,
        "comp_options": {"paths_walk_enc": _walk_code(NUMID, VARINT)},
        "tags": ["paths", "walk-decomposition"],
    },
    {
        "id": "paths_walk_strid",
        "gfa_text": _PATHS_2,
        "comp_options": {"paths_walk_enc": _walk_code(STRID, VARINT, _code(VARINT, NONE))},
        "tags": ["paths", "walk-decomposition"],
    },
    {
        "id": "paths_walk_strid_zstd_names",
        "gfa_text": _PATHS_2,
        "comp_options": {"paths_walk_enc": _walk_code(STRID, VARINT, _code(VARINT, ZSTD))},
        "tags": ["paths", "walk-decomposition"],
    },
    # --- Paths: CIGAR --------------------------------------------------------
    {
        "id": "paths_cigar_identity",
        "gfa_text": _PATHS_2,
        "comp_options": {"paths_cigars_enc": _cigar_code(CIGAR_NONE, VARINT, 0, NONE)},
        "tags": ["paths", "cigar"],
    },
    {
        "id": "paths_cigar_numops",
        "gfa_text": _PATHS_2,
        "comp_options": {"paths_cigars_enc": _cigar_code(CIGAR_NUMOPS, VARINT, VARINT, NONE)},
        "tags": ["paths", "cigar"],
    },
    {
        "id": "paths_cigar_string",
        "gfa_text": _PATHS_2,
        "comp_options": {"paths_cigars_enc": _cigar_code(CIGAR_STRING, VARINT, 0, NONE)},
        "tags": ["paths", "cigar"],
    },
    {
        "id": "paths_cigar_string_zstd",
        "gfa_text": _PATHS_2,
        "comp_options": {"paths_cigars_enc": _cigar_code(CIGAR_STRING, VARINT, 0, ZSTD)},
        "tags": ["paths", "cigar"],
    },
    # --- Walks: structure ----------------------------------------------------
    {
        "id": "walks_single",
        "gfa_text": "H\tVN:Z:1.0\nS\ts1\tACGT\nS\ts2\tTGCA\nW\tsample1\t0\tchr1\t0\t100\ts1+s2+\n",
        "tags": ["walks"],
    },
    {
        "id": "walks_metadata",
        "gfa_text": "H\tVN:Z:1.0\nS\ts1\tACGT\nS\ts2\tTGCA\nS\ts3\tAAAA\nW\tsample1\t1\tchr1\t100\t200\ts1+s2-s3+\n",
        "tags": ["walks"],
    },
    {
        "id": "walks_positions_zero",
        "gfa_text": "H\tVN:Z:1.0\nS\ts1\tACGT\nW\tsample1\t0\tchr1\t0\t0\ts1+\n",
        "tags": ["walks"],
    },
    {
        "id": "walks_multi_same_sample",
        "gfa_text": (
            "H\tVN:Z:1.0\nS\ts1\tACGT\nS\ts2\tTGCA\nS\ts3\tAAAA\n"
            "W\tsample1\t0\tchr1\t0\t100\ts1+\n"
            "W\tsample1\t0\tchr2\t0\t100\ts2+\n"
            "W\tsample1\t0\tchr3\t0\t100\ts3+\n"
        ),
        "tags": ["walks"],
    },
    {
        "id": "walks_multi_diff_samples",
        "gfa_text": (
            "H\tVN:Z:1.0\nS\ts1\tACGT\nS\ts2\tTGCA\nS\ts3\tAAAA\n"
            "W\tsample1\t0\tchr1\t0\t100\ts1+\n"
            "W\tsample2\t0\tchr1\t0\t100\ts2+\n"
            "W\tsample3\t0\tchr1\t0\t100\ts3+\n"
        ),
        "tags": ["walks"],
    },
    {
        "id": "walks_many_steps",
        "gfa_text": (
            "H\tVN:Z:1.0\n"
            + "".join(f"S\ts{i}\tACGT\n" for i in range(1, 11))
            + "W\tsample1\t0\tchr1\t0\t100\ts1+s2-s3+s4-s5+s6-s7+s8-s9+s10-\n"
        ),
        "tags": ["walks"],
    },
    {
        "id": "walks_no_walks",
        "gfa_text": _LINKS_4,
        "tags": ["walks"],
    },
    {
        "id": "walks_char_form",
        "gfa_text": "H\tVN:Z:1.0\nS\t1\tACGT\nS\t2\tTGCA\nS\t3\tAAAA\nW\tsample1\t0\tchr1\t0\t100\t>1<2>3\n",
        "tags": ["walks"],
    },
    # --- Walks: decomposition -------------------------------------------------
    {
        "id": "walks_decomp_numid",
        "gfa_text": _WALKS_2,
        "comp_options": {"walk_steps_enc": _walk_code(NUMID, VARINT)},
        "tags": ["walks", "walk-decomposition"],
    },
    {
        "id": "walks_decomp_strid",
        "gfa_text": _WALKS_2,
        "comp_options": {"walk_steps_enc": _walk_code(STRID, VARINT, _code(VARINT, NONE))},
        "tags": ["walks", "walk-decomposition"],
    },
    {
        "id": "walks_strid_zstd_names",
        "gfa_text": _WALKS_2,
        "comp_options": {"walk_steps_enc": _walk_code(STRID, VARINT, _code(VARINT, ZSTD))},
        "tags": ["walks", "walk-decomposition"],
    },
    # --- Walks: uints-delta positions ----------------------------------------
    {
        "id": "walks_positions_increasing",
        "gfa_text": (
            "H\tVN:Z:1.0\nS\ts1\tACGT\nS\ts2\tTGCA\nS\ts3\tAAAA\nS\ts4\tCCCC\n"
            "W\tsample1\t0\tchr1\t0\t5\ts1+\n"
            "W\tsample2\t0\tchr1\t10\t15\ts2+\n"
            "W\tsample3\t0\tchr1\t20\t25\ts3+\n"
            "W\tsample4\t0\tchr1\t30\t35\ts4+\n"
        ),
        "tags": ["walks", "uints-delta"],
    },
    {
        "id": "walks_positions_decreasing",
        "gfa_text": (
            "H\tVN:Z:1.0\nS\ts1\tACGT\nS\ts2\tTGCA\nS\ts3\tAAAA\n"
            "W\tsample1\t0\tchr1\t100\t110\ts1+\n"
            "W\tsample2\t0\tchr1\t90\t100\ts2+\n"
            "W\tsample3\t0\tchr1\t80\t90\ts3+\n"
        ),
        "tags": ["walks", "uints-delta"],
    },
    {
        "id": "walks_positions_mixed",
        "gfa_text": (
            "H\tVN:Z:1.0\nS\ts1\tACGT\nS\ts2\tTGCA\nS\ts3\tAAAA\nS\ts4\tCCCC\n"
            "W\tsample1\t0\tchr1\t0\t10\ts1+\n"
            "W\tsample2\t0\tchr1\t50\t60\ts2+\n"
            "W\tsample3\t0\tchr1\t10\t20\ts3+\n"
            "W\tsample4\t0\tchr1\t40\t50\ts4+\n"
        ),
        "tags": ["walks", "uints-delta"],
    },
    # --- Walks: string encodings ---------------------------------------------
    {
        "id": "walks_samples_identity",
        "gfa_text": _WALKS_2,
        "comp_options": {"walk_sample_ids_enc": "varint-none"},
        "tags": ["walks", "string-encoding"],
    },
    {
        "id": "walks_samples_zstd",
        "gfa_text": _WALKS_2,
        "comp_options": {"walk_sample_ids_enc": "varint-zstd"},
        "tags": ["walks", "string-encoding"],
    },
    {
        "id": "walks_samples_dictionary",
        "gfa_text": (
            "H\tVN:Z:1.0\nS\ts1\tACGT\nS\ts2\tTGCA\nS\ts3\tAAAA\n"
            "W\tsample1\t0\tchr1\t0\t100\ts1+\n"
            "W\tsample1\t0\tchr2\t0\t100\ts2+\n"
            "W\tsample1\t0\tchr3\t0\t100\ts3+\n"
            "W\tsample1\t0\tchr4\t0\t100\ts1+\n"
            "W\tsample1\t0\tchr5\t0\t100\ts2+\n"
        ),
        "comp_options": {"walk_sample_ids_enc": "varint-dictionary"},
        "tags": ["walks", "string-encoding"],
    },
    {
        "id": "walks_hep_fixed16",
        "gfa_text": _WALKS_2,
        "comp_options": {"walk_haplotype_indices_enc": "fixed16-none"},
        "tags": ["walks", "int-encoding"],
    },
    {
        "id": "walks_positions_fixed16",
        "gfa_text": _WALKS_2,
        "comp_options": {"walk_positions_start_enc": "fixed16-none"},
        "tags": ["walks", "int-encoding"],
    },
    # --- Opt-fields block (section 6) ----------------------------------------
    {
        "id": "optfields_seg_int",
        "gfa_text": "H\tVN:Z:1.0\nS\ts1\tACGT\tLN:i:100\n",
        "tags": ["opt-fields"],
    },
    {
        "id": "optfields_seg_float",
        "gfa_text": "H\tVN:Z:1.0\nS\ts1\tACGT\tXX:f:1.5\n",
        "tags": ["opt-fields"],
    },
    {
        "id": "optfields_seg_string",
        "gfa_text": "H\tVN:Z:1.0\nS\ts1\tACGT\tXX:Z:hello\n",
        "tags": ["opt-fields"],
    },
    {
        "id": "optfields_seg_multi",
        "gfa_text": "H\tVN:Z:1.0\nS\ts1\tACGT\tLN:i:100\tRC:i:42\tXX:Z:tag\n",
        "tags": ["opt-fields"],
    },
    {
        "id": "optfields_link",
        "gfa_text": "H\tVN:Z:1.0\nS\ts1\tACGT\nS\ts2\tTGCA\nL\ts1\t+\ts2\t+\t4M\tXX:i:7\n",
        "tags": ["opt-fields"],
    },
    {
        "id": "optfields_seg_and_link",
        "gfa_text": (
            "H\tVN:Z:1.0\nS\ts1\tACGT\tLN:i:100\nS\ts2\tTGCA\tXX:Z:seg\n"
            "L\ts1\t+\ts2\t+\t4M\tXX:i:7\n"
        ),
        "tags": ["opt-fields"],
    },
    {
        "id": "optfields_none",
        "gfa_text": "H\tVN:Z:1.0\nS\ts1\tACGT\nS\ts2\tTGCA\nL\ts1\t+\ts2\t+\t4M\n",
        "tags": ["opt-fields"],
    },
    {
        "id": "optfields_path",
        "gfa_text": "H\tVN:Z:1.0\nS\ts1\tACGT\nS\ts2\tTGCA\nP\tp1\ts1+,s2+\t4M\tXX:Z:foo\tYY:i:7\n",
        "tags": ["opt-fields"],
    },
    {
        "id": "optfields_walk",
        "gfa_text": "H\tVN:Z:1.0\nS\ts1\tACGT\nS\ts2\tTGCA\nW\tsample1\t0\tchr1\t0\t100\t>s1>s2\tZZ:Z:bar\n",
        "tags": ["opt-fields"],
    },
    {
        "id": "optfields_path_and_walk",
        "gfa_text": (
            "H\tVN:Z:1.0\nS\ts1\tACGT\nS\ts2\tTGCA\n"
            "P\tp1\ts1+,s2+\t4M\tXX:Z:foo\n"
            "W\tsample1\t0\tchr1\t0\t100\t>s1>s2\tZZ:Z:bar\n"
        ),
        "tags": ["opt-fields"],
    },
    {
        "id": "walks_positions_star",
        "gfa_text": "H\tVN:Z:1.0\nS\ts1\tACGT\nS\ts2\tTGCA\nW\tsample1\t0\tchr1\t*\t*\t>s1>s2\n",
        "tags": ["walks"],
    },
    {
        "id": "walks_positions_start_end_enc",
        "gfa_text": _WALKS_2,
        "comp_options": {
            "walk_positions_start_enc": "varint-none",
            "walk_positions_end_enc": "fixed16-none",
        },
        "tags": ["walks", "int-encoding"],
    },
    # --- Multi-block / chunking ----------------------------------------------
    {
        "id": "chunking_block_size_one",
        "gfa_text": (
            "H\tVN:Z:1.0\nS\ts1\tACGT\nS\ts2\tTGCA\nS\ts3\tAAAA\n"
            "L\ts1\t+\ts2\t+\t4M\nL\ts2\t+\ts3\t+\t4M\nL\ts3\t+\ts1\t+\t4M\n"
            "P\tp1\ts1+,s2+\t4M\nP\tp2\ts2+,s3+\t4M\nP\tp3\ts3+,s1+\t4M\n"
            "W\tsample1\t0\tchr1\t0\t100\ts1+\n"
            "W\tsample2\t0\tchr1\t0\t100\ts2+\n"
            "W\tsample3\t0\tchr1\t0\t100\ts3+\n"
        ),
        "block_size": 1,
        "tags": ["chunking"],
    },
    {
        "id": "chunking_paths",
        "gfa_text": (
            "H\tVN:Z:1.0\nS\ts1\tACGT\nS\ts2\tTGCA\nS\ts3\tAAAA\nS\ts4\tCCCC\n"
            "P\tp1\ts1+,s2+\t4M\nP\tp2\ts2+,s3+\t4M\nP\tp3\ts3+,s4+\t4M\n"
            "P\tp4\ts4+,s1+\t4M\nP\tp5\ts1+,s3+\t4M\n"
        ),
        "block_size": 2,
        "tags": ["chunking"],
    },
    {
        "id": "chunking_walks",
        "gfa_text": (
            "H\tVN:Z:1.0\nS\ts1\tACGT\nS\ts2\tTGCA\nS\ts3\tAAAA\nS\ts4\tCCCC\n"
            "W\tsample1\t0\tchr1\t0\t100\ts1+\n"
            "W\tsample2\t0\tchr1\t0\t100\ts2+\n"
            "W\tsample3\t0\tchr1\t0\t100\ts3+\n"
            "W\tsample4\t0\tchr1\t0\t100\ts4+\n"
            "W\tsample5\t0\tchr1\t0\t100\ts1+\n"
        ),
        "block_size": 2,
        "tags": ["chunking"],
    },
    # --- Full combined graphs ------------------------------------------------
    {
        "id": "combined_minimal",
        "gfa_text": (
            "H\tVN:Z:1.0\nS\ts1\tACGT\nS\ts2\tTGCA\n"
            "L\ts1\t+\ts2\t+\t4M\n"
            "P\tp1\ts1+,s2+\t4M\n"
            "W\tsample1\t0\tchr1\t0\t100\ts1+s2+\n"
        ),
        "tags": ["combined"],
    },
    {
        "id": "combined_full",
        "gfa_text": (
            "H\tVN:Z:1.0\n"
            "S\ts1\tACGT\tLN:i:100\nS\ts2\tTGCA\tLN:i:100\nS\ts3\tAAAA\tLN:i:50\n"
            "S\ts4\tCCCC\tLN:i:50\nS\ts5\tGGGG\tLN:i:50\n"
            "L\ts1\t+\ts2\t+\t4M\tXX:i:1\n"
            "L\ts2\t-\ts3\t+\t4M\n"
            "L\ts3\t+\ts4\t-\t4M\tXX:Z:edge\n"
            "L\ts4\t-\ts5\t+\t4M\n"
            "L\ts5\t+\ts1\t-\t4M\n"
            "L\ts2\t+\ts4\t+\t4M\n"
            "P\tp1\ts1+,s2-,s3+\t4M,4M\n"
            "P\tp2\ts4+,s5-\t4M\n"
            "W\tsample1\t0\tchr1\t0\t100\ts1+s2-s3+\n"
            "W\tsample2\t1\tchr2\t50\t150\ts4+s5-s1+\n"
        ),
        "tags": ["combined"],
    },
    {
        "id": "combined_large",
        "build": _combined_large,
        "tags": ["combined"],
    },
    # --- Extra edge cases ----------------------------------------------------
    {
        "id": "containment_single",
        "gfa_text": "H\tVN:Z:1.0\nS\ts1\tACGT\nS\ts2\tTGCA\nC\ts1\t+\ts2\t-\t5\t10M\n",
        "tags": ["containment"],
    },
    {
        "id": "segments_names_zstd",
        "gfa_text": (
            "H\tVN:Z:1.0\n"
            "S\tcontig_1\tACGT\nS\tcontig_2\tTGCA\nS\tcontig_3\tAAAA\nS\tcontig_4\tCCCC\n"
        ),
        "comp_options": {"segment_names_enc": "varint-zstd"},
        "tags": ["segments", "string-encoding"],
    },
    {
        "id": "segments_names_dictionary",
        "gfa_text": (
            "H\tVN:Z:1.0\n"
            "S\tcontig_1\tACGT\nS\tcontig_2\tTGCA\nS\tcontig_3\tAAAA\nS\tcontig_4\tCCCC\n"
        ),
        "comp_options": {"segment_names_enc": "varint-dictionary"},
        "tags": ["segments", "string-encoding"],
    },
    {
        "id": "paths_many_paths_300",
        "build": lambda: _many_paths(300),
        "block_size": 64,
        "tags": ["paths", "chunking"],
    },
    {
        "id": "walks_many_walks_300",
        "build": lambda: _many_walks(300),
        "block_size": 64,
        "tags": ["walks", "chunking"],
    },
]

__all__ = ["INSTANCES"]