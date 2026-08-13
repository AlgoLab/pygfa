#!/usr/bin/env python3
"""Per-section, per-field encoding roundtrip tests on small example GFA files.

For each small GFA file (filename starting with ``example`` in ``data/``),
iterates over every section present (segments, links, paths).  Within each
section, iterates over every encoding field and every **legitimate** encoding
code for that field.

*Legitimate* means the code is a valid combination of sub-encodings as
enumerated by ``show_full_encodings()`` from ``pygfa.encoding`` — the same
source used by ``bin/bgfatools show-full-encodings``.

For *2-byte fields* whose data are **strings** (segment names, sequences,
path names) the test varies only the string encoding (integer encoding fixed
to VARINT).  For the *2-byte field* whose data are **integers** (link
endpoints) the test varies only the integer encoding (string encoding fixed
to NONE).

For *4-byte CIGAR fields* (link cigars, path cigars) and *4-byte walk fields*
(path walk encoding) the full set of combinations returned by
``show_full_encodings()`` is used, respecting the byte-layout of the BGFA
writer.

All *other* encoding fields are set to NONE/IDENTITY so the test isolates the
behaviour of a single encoding choice.

Each combination checks:
  1. Dump succeeds (BGFA file is created without error).
  2. Converting back to GFA produces a structurally identical graph.
"""

from __future__ import annotations

import glob
import os
import sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from pygfa.gfa import GFA  # noqa: E402
from pygfa.encoding import (  # noqa: E402
    COMPRESSION_OPTIONS,
    show_full_encodings,
)
from pygfa.encoding.enums import (  # noqa: E402
    IntegerEncoding,
    StringEncoding,
    WalkDecomposition,
    CigarDecomposition,
    make_compression_code,
)
from pygfa.bgfa._codec_utils import make_4byte_code  # noqa: E402
from pygfa.bgfa._validation import dump_bgfa  # noqa: E402

import io
from contextlib import redirect_stdout

try:
    import pytest

    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False

    class DummyPytest:
        @staticmethod
        def mark(*args, **kwargs):
            class DummyMark:
                @staticmethod
                def parametrize(*args, **kwargs):
                    return lambda f: f
            return DummyMark()

        @staticmethod
        def skip(reason):
            raise Exception(f"Skipped: {reason}")

    pytest = DummyPytest()


# ---------------------------------------------------------------------------
# Constants — name → enum lookups
# ---------------------------------------------------------------------------

_INT_FROM_NAME: dict[str, IntegerEncoding] = {
    e.name.lower(): e for e in IntegerEncoding
}
_STR_FROM_NAME: dict[str, StringEncoding] = {
    e.name.lower(): e for e in StringEncoding
}
_CIGAR_DECOMP_FROM_NAME: dict[str, CigarDecomposition] = {
    "none": CigarDecomposition.NONE,
    "numops_lengths_ops": CigarDecomposition.NUM_OPERATIONS,
    "string": CigarDecomposition.STRING,
}
_WALK_DECOMP_FROM_NAME: dict[str, WalkDecomposition] = {
    "none": WalkDecomposition.NONE,
    "orientation_strid": WalkDecomposition.ORIENTATION_STRID,
    "orientation_numid": WalkDecomposition.ORIENTATION_NUMID,
}


# ---------------------------------------------------------------------------
# Build base options (working defaults for ALL fields)
# ---------------------------------------------------------------------------

_DEFAULT_SEGMENT_NAMES_ENC = make_compression_code(IntegerEncoding.VARINT, StringEncoding.NONE)
_DEFAULT_SEQUENCES_ENC = make_compression_code(IntegerEncoding.VARINT, StringEncoding.TWO_BIT_DNA)
_DEFAULT_LINK_FROMTO_ENC = make_compression_code(IntegerEncoding.VARINT, StringEncoding.NONE)
_DEFAULT_LINK_CIGARS_ENC = make_4byte_code(
    StringEncoding.NONE.value,
    IntegerEncoding.VARINT.value,
    IntegerEncoding.VARINT.value,
    CigarDecomposition.NUM_OPERATIONS.value,
)
_DEFAULT_PATH_NAMES_ENC = make_compression_code(IntegerEncoding.VARINT, StringEncoding.NONE)
_DEFAULT_PATHS_WALK_ENC = (
    (IntegerEncoding.VARINT.value << 0)
    | (WalkDecomposition.ORIENTATION_NUMID.value << 24)
)
_DEFAULT_PATHS_CIGARS_ENC = make_4byte_code(
    StringEncoding.NONE.value,
    IntegerEncoding.VARINT.value,
    IntegerEncoding.VARINT.value,
    CigarDecomposition.NUM_OPERATIONS.value,
)


def _base_options() -> dict:
    """Return compression options with ALL fields at working defaults.

    Every field uses a reliable default encoding so that all data can be
    written and read back correctly.  The caller overrides only the single
    field under test.
    """
    return {
        "segment_names_enc": _DEFAULT_SEGMENT_NAMES_ENC,
        "sequences_enc": _DEFAULT_SEQUENCES_ENC,
        "link_endpoints_enc": _DEFAULT_LINK_FROMTO_ENC,
        "link_cigars_enc": _DEFAULT_LINK_CIGARS_ENC,
        "path_names_enc": _DEFAULT_PATH_NAMES_ENC,
        "paths_walk_enc": _DEFAULT_PATHS_WALK_ENC,
        "paths_cigars_enc": _DEFAULT_PATHS_CIGARS_ENC,
    }


# ---------------------------------------------------------------------------
# Parse an encoding string from ``show_full_encodings()`` into a numeric code
# ---------------------------------------------------------------------------

_SUPPORTED_INT_NAMES: set[str] = set(
    n for n in _INT_FROM_NAME
)
_SUPPORTED_STR_NAMES: set[str] = set(
    n for n in _STR_FROM_NAME
)

# For string-type 2-byte fields we want to vary only the string encoding,
# keeping the integer encoding fixed to VARINT.  Which string names should
# be skipped because the data won't survive a round-trip?
#
#   * ``two_bit_dna`` — can only encode ACGTN, corrupts names/sequences
#     that contain other characters.
_SKIP_STRING_NAMES: set[str] = {"two_bit_dna"}

# Integer encodings skipped because they cannot roundtrip the small
# integer ranges found in example GFA files (currently none; elias
# gamma/omega were fixed in ENCODING_BUGS.md bugs 7/8).
_SKIP_INT_NAMES: set[str] = set()

# CIGAR ops-string encoding support in the codec
# (``_ops_string_encoder_for_code``) is limited to NONE, GZIP, LZMA.
_SUPPORTED_CIGAR_OPS_NAMES: set[str] = {"none", "gzip", "lzma"}

# Walk decomposition: NONE loses data trivially (kept excluded by design).
_SKIP_WALK_DECOMP_NAMES: set[str] = {"none"}

# CIGAR decomposition STRING is fixed (ENCODING_BUGS.md bug 12); the blob
# string codecs are restricted to the generic compressors, same as the
# NUM_OPERATIONS ops-string field.
_SKIP_CIGAR_DECOMP_NAMES: set[str] = set()


def _parse_encoding_string(enc_key: str, enc_str: str) -> tuple[str, int] | None:
    """Convert a ``show_full_encodings()`` encoding string into a numeric code.

    Returns a (label, code) pair suitable for test parameterisation.
    Returns ``None`` when the combination is known to be incompatible
    with the example data or current codec limitations.
    """
    field_type = COMPRESSION_OPTIONS[enc_key]

    if field_type == "2byte":
        int_name, str_name = enc_str.split("+", 1)
        int_enc = _INT_FROM_NAME[int_name]
        str_enc = _STR_FROM_NAME[str_name]

        # For string data: vary only string encoding, fix int to VARINT
        if int_name != "varint":
            return None
        if str_name in _SKIP_STRING_NAMES:
            return None
        label = f"str={str_name}(0x{str_enc.value:02X})"
        code = make_compression_code(int_enc, str_enc)
        return label, code

    elif field_type == "1byte_int":
        # Used for link_endpoints_enc: writer needs a 2-byte code.
        # Only the integer encoding (high byte) matters; string=0 (NONE).
        int_name = enc_str
        if int_name in _SKIP_INT_NAMES:
            return None
        int_enc = _INT_FROM_NAME[int_name]
        label = f"int={int_name}(0x{int_enc.value:02X})"
        code = make_compression_code(int_enc, StringEncoding.NONE)
        return label, code

    elif field_type == "4byte_cigar":
        parts = enc_str.split("+")
        if len(parts) != 4:
            return None
        decomp_name, int1_name, int2_name, str_name = parts
        if decomp_name in _SKIP_CIGAR_DECOMP_NAMES:
            return None
        decomp = _CIGAR_DECOMP_FROM_NAME[decomp_name]
        if decomp == CigarDecomposition.NONE:
            # Show_full_encodings produces 5054 variants of ``none+int1+int2+str``
            # but they all collapse to the same code (0x00000000).  Keep only
            # the simplest one.
            if int1_name == "none" and int2_name == "none" and str_name == "none":
                label = "cigar_decomp=NONE"
                return label, 0x00000000
            return None

        # decomp == NUM_OPERATIONS: vary one sub-field at a time
        if decomp == CigarDecomposition.NUM_OPERATIONS:
            # int1 (lengths) and int2 (counts): skip gamma/omega
            if int1_name in _SKIP_INT_NAMES or int2_name in _SKIP_INT_NAMES:
                return None
            if str_name not in _SUPPORTED_CIGAR_OPS_NAMES:
                return None

            int1 = _INT_FROM_NAME[int1_name]
            int2 = _INT_FROM_NAME[int2_name]
            str_enc = _STR_FROM_NAME[str_name]

            # Vary only one sub-field, keep others at VARINT/NONE
            if int1_name != "varint" and int2_name == "varint" and str_name == "none":
                label = f"cigar_decomp=NUM_OPS_len_int={int1_name}(0x{int1.value:02X})"
            elif int2_name != "varint" and int1_name == "varint" and str_name == "none":
                label = f"cigar_decomp=NUM_OPS_counts_int={int2_name}(0x{int2.value:02X})"
            elif str_name != "none" and int1_name == "varint" and int2_name == "varint":
                label = f"cigar_decomp=NUM_OPS_ops_str={str_name}(0x{str_enc.value:02X})"
            else:
                # Multiple variations at once — skip to keep isolation
                return None

            code = make_4byte_code(
                str_enc.value,
                int2.value,
                int1.value,
                decomp.value,
            )
            return label, code

        # decomp == STRING: vary one sub-field at a time.  int1 (bits 15-8)
        # is the integer encoding for the lengths list; str (bits 31-24) is
        # the string encoding for the CIGAR blob.  int2 (bits 16-23) is unused.
        if decomp == CigarDecomposition.STRING:
            if int1_name != "varint" and int2_name == "varint" and str_name == "none":
                label = f"cigar_decomp=STRING_len_int={int1_name}(0x{_INT_FROM_NAME[int1_name].value:02X})"
                int1 = _INT_FROM_NAME[int1_name]
                code = make_4byte_code(StringEncoding.NONE.value, 0, int1.value, decomp.value)
                return label, code
            if str_name in _SUPPORTED_CIGAR_OPS_NAMES and str_name != "none" and int1_name == "varint" and int2_name == "varint":
                label = f"cigar_decomp=STRING_blob_str={str_name}(0x{_STR_FROM_NAME[str_name].value:02X})"
                str_enc = _STR_FROM_NAME[str_name]
                code = make_4byte_code(str_enc.value, 0, IntegerEncoding.VARINT.value, decomp.value)
                return label, code
            return None

        return None

    elif field_type == "4byte_walks":
        parts = enc_str.split("+")
        if len(parts) != 3:
            return None
        decomp_name, int_name, _str_name = parts
        if decomp_name in _SKIP_WALK_DECOMP_NAMES:
            return None
        if int_name in _SKIP_INT_NAMES:
            return None

        walk_decomp = _WALK_DECOMP_FROM_NAME[decomp_name]
        int_enc = _INT_FROM_NAME[int_name]
        label = (
            f"walk_decomp={decomp_name}_int={int_name}(0x{int_enc.value:02X})"
        )
        code = (walk_decomp.value << 24) | (int_enc.value << 0)
        return label, code

    return None


# ---------------------------------------------------------------------------
# Discover example GFA files (filename starts with "example")
# ---------------------------------------------------------------------------

def _discover_example_gfa_files(data_dir: str = "data") -> list[str]:
    pattern = os.path.join(data_dir, "example*.gfa")
    return sorted(glob.glob(pattern))


EXAMPLE_GFA_FILES = _discover_example_gfa_files()


# ---------------------------------------------------------------------------
# Section-aware detection
# ---------------------------------------------------------------------------

def _sections_in_gfa(gfa_path: str) -> set[str]:
    g = GFA.from_gfa(gfa_path)
    sections = {"segments"}
    if list(g.edges()):
        sections.add("links")
    if g.paths():
        sections.add("paths")
    return sections


# ---------------------------------------------------------------------------
# Map writer field → ``show_full_encodings()`` key
# ---------------------------------------------------------------------------

_FIELD_TO_ENC_KEY: dict[str, str] = {
    "segment_names_enc": "compression_segment_names",
    "sequences_enc": "compression_sequences",
    "link_endpoints_enc": "compression_from",
    "link_cigars_enc": "compression_cigars",
    "path_names_enc": "compression_path_names",
    "paths_walk_enc": "compression_paths",
    "paths_cigars_enc": "compression_cigars",
}

_FIELD_SECTIONS: dict[str, str] = {
    "segment_names_enc": "segments",
    "sequences_enc": "segments",
    "link_endpoints_enc": "links",
    "link_cigars_enc": "links",
    "path_names_enc": "paths",
    "paths_walk_enc": "paths",
    "paths_cigars_enc": "paths",
}

_ALL_FIELD_NAMES = sorted(_FIELD_TO_ENC_KEY.keys())


# ---------------------------------------------------------------------------
# Get legitimate encodings from ``show_full_encodings()``
# ---------------------------------------------------------------------------

_LEGIT_ENCODINGS = show_full_encodings()


def _codes_for_field(field_name: str) -> list[tuple[str, int]]:
    """Return (label, code) pairs for every legitimate encoding of *field_name*."""
    enc_key = _FIELD_TO_ENC_KEY[field_name]
    results: list[tuple[str, int]] = []
    for enc_str in _LEGIT_ENCODINGS.get(enc_key, []):
        parsed = _parse_encoding_string(enc_key, enc_str)
        if parsed is not None:
            results.append(parsed)
    return results


# ---------------------------------------------------------------------------
# Test ID helper
# ---------------------------------------------------------------------------

def _make_test_id(gfa_path: str, field_name: str, encoding_label: str) -> str:
    fname = os.path.basename(gfa_path).replace(".gfa", "")
    label_short = encoding_label[:60]
    return f"[{fname}]-{field_name}-{label_short}"


# ---------------------------------------------------------------------------
# Build the full test parameter matrix
# ---------------------------------------------------------------------------

ALL_TEST_PARAMS: list[tuple[str, str, str, int]] = []
ALL_TEST_IDS: list[str] = []

for gfa_path in EXAMPLE_GFA_FILES:
    sections = _sections_in_gfa(gfa_path)
    for field_name in _ALL_FIELD_NAMES:
        if _FIELD_SECTIONS[field_name] not in sections:
            continue
        for label, code in _codes_for_field(field_name):
            ALL_TEST_PARAMS.append((gfa_path, field_name, label, code))
            ALL_TEST_IDS.append(_make_test_id(gfa_path, field_name, label))


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "gfa_path,field_name,encoding_label,encoding_code",
    ALL_TEST_PARAMS,
    ids=ALL_TEST_IDS,
)
class TestEncodingPerSection:
    """For each section encoding field, test every legitimate code in isolation."""

    def test_encoding_roundtrip(
        self,
        gfa_path: str,
        field_name: str,
        encoding_label: str,
        encoding_code: int,
        test_output_dir,
    ):
        if not os.path.exists(gfa_path):
            pytest.skip(f"Test file not found: {gfa_path}")

        # Build output path under results/encodings_per_section/
        fname = os.path.basename(gfa_path).replace(".gfa", "")
        out_dir = os.path.join("results", "encodings_per_section")
        os.makedirs(out_dir, exist_ok=True)
        bgfa_path = os.path.join(out_dir, f"{fname}__{field_name}__{encoding_label}.bgfa")

        # Build options: ALL fields start at working defaults, then override
        # only the single field under test.
        opts = _base_options()
        opts[field_name] = encoding_code

        # 1: BGFA file is created and roundtrip preserves content
        g_orig, g_round = _roundtrip_with_options(gfa_path, opts, bgfa_path)

        # 2: Dump the BGFA content to a sidecar .dump.txt file
        dump_path = bgfa_path + ".dump.txt"
        f = io.StringIO()
        with redirect_stdout(f):
            dump_bgfa(bgfa_path)
        with open(dump_path, "w") as f_out:
            f_out.write(f.getvalue())

        # 3: Structural equality
        _assert_structural_equality(g_orig, g_round)


# ---------------------------------------------------------------------------
# Structural equality assertion
# ---------------------------------------------------------------------------

def _true_sequences(gfa_obj):
    data = dict(gfa_obj.nodes_iter(data=True))
    return {n: data[n].get("sequence", "*") for n in gfa_obj.nodes()}


def _link_set(gfa_obj):
    links = set()
    for u, v, key, data in gfa_obj.edges_iter(data=True, keys=True):
        links.add((
            data.get("from_node", u),
            data.get("from_orn", "+"),
            data.get("to_node", v),
            data.get("to_orn", "+"),
            data.get("alignment", "*"),
        ))
    return links


def _path_set(gfa_obj):
    """Return a frozenset of (name, segments_tuple, overlaps_tuple) for paths.

    Normalises ``('*',)`` overlaps to ``()`` so that empty-overlap paths roundtrip
    consistently.
    """
    paths = gfa_obj.paths()
    result = set()
    for name, p in paths.items():
        segs = tuple(p.get("segments", []))
        ovs_raw = tuple(p.get("overlaps", []))
        ovs = () if ovs_raw == ("*",) else ovs_raw
        result.add((name, segs, ovs))
    return frozenset(result)


def _assert_structural_equality(g, h) -> None:
    assert sorted(g.nodes()) == sorted(h.nodes()), "Segment names differ"

    g_seqs = _true_sequences(g)
    h_seqs = _true_sequences(h)
    for n in g.nodes():
        assert n in h_seqs, f"Node {n} missing after round-trip"
        assert g_seqs[n] == h_seqs[n], (
            f"Sequence mismatch for node {n}: {g_seqs[n]!r} vs {h_seqs[n]!r}"
        )

    assert _link_set(g) == _link_set(h), (
        f"Link mismatch.\n  Missing: {_link_set(g) - _link_set(h)}\n"
        f"  Extra: {_link_set(h) - _link_set(g)}"
    )

    g_paths = _path_set(g)
    h_paths = _path_set(h)
    if g_paths or h_paths:
        assert g_paths == h_paths, (
            f"Path mismatch.\n  Missing: {g_paths - h_paths}\n"
            f"  Extra: {h_paths - g_paths}"
        )


# ---------------------------------------------------------------------------
# Roundtrip helper
# ---------------------------------------------------------------------------

def _roundtrip_with_options(gfa_path: str, compression_options: dict, bgfa_path: str):
    g = GFA.from_gfa(gfa_path)
    g.to_bgfa(
        bgfa_path,
        block_size=1024,
        compression_options=compression_options,
        use_heuristic=False,
        verbose=False,
        debug=False,
        logfile=None,
    )
    assert os.path.exists(bgfa_path), "BGFA file was not created"
    assert os.path.getsize(bgfa_path) > 0, "BGFA file is empty"
    h = GFA.from_bgfa(bgfa_path, verbose=False, debug=False, logfile=None)
    return g, h


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if HAS_PYTEST:
        pytest.main([__file__, "-v", "-s"])
    else:
        print("pytest not available. Run with pytest to execute tests.")