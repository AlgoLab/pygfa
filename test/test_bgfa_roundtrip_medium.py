#!/usr/bin/env python3
"""Round-trip tests (medium tier): files requiring between 4 and 16 GB memory.

Tests that converting a GFA file to BGFA and back produces an identical GFA.
Only runs on GFA files tagged with `# benchmark: roundtrip_medium`.
"""

import glob
import os
import sys
import tempfile

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from pygfa.gfa import GFA  # noqa: E402
from test_utils import should_run_benchmark_for_gfa  # noqa: E402
from pygfa.encoding import INTEGER_ENCODINGS as _ALL_INT_ENCODINGS, STRING_ENCODINGS as _ALL_STR_ENCODINGS  # noqa: E402

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

BENCHMARK_NAME = "roundtrip_medium"


def _roundtrip_file(gfa_path, block_size=1024, compression_options=None, test_output_dir=None):
    """Load a GFA file, convert to BGFA and back, return (original, roundtrip) GFA objects."""
    if compression_options is None:
        compression_options = {}

    bgfa_path = tempfile.mktemp(suffix=".bgfa")

    try:
        g = GFA.from_gfa(gfa_path)
        g.to_bgfa(bgfa_path, block_size, compression_options, verbose=False, debug=False, logfile=None)
        assert os.path.exists(bgfa_path), f"BGFA file was not created: {bgfa_path}"
        assert os.path.getsize(bgfa_path) > 0, f"BGFA file is empty: {bgfa_path}"
        h = GFA.from_bgfa(bgfa_path, verbose=False, debug=False, logfile=None)
        return g, h
    finally:
        if os.path.exists(bgfa_path):
            os.unlink(bgfa_path)


ALL_ROUNDTRIP_FILES = [
    f for f in glob.glob("data/**/*.gfa", recursive=True) if should_run_benchmark_for_gfa(BENCHMARK_NAME, f)
]


def _gfa_test_id(gfa_path):
    return f"[{gfa_path}]"


def _encoding_test_id(params):
    if isinstance(params, (list, tuple)) and len(params) == 4:
        gfa_path, int_encoding, str_encoding, block_size = params
        return f"[{gfa_path}]-{int_encoding}-{str_encoding}-{block_size}"
    return str(params)


def pytest_generate_tests(metafunc):
    if "gfa_path" in metafunc.fixturenames and metafunc.cls is TestStructuralRoundtrip:
        gfa_file = metafunc.config.getoption("--gfa-file")

        if gfa_file:
            test_files = (
                [gfa_file]
                if (os.path.exists(gfa_file) and should_run_benchmark_for_gfa(BENCHMARK_NAME, gfa_file))
                else []
            )
        else:
            test_files = ALL_ROUNDTRIP_FILES

        if not test_files:
            pytest.skip(f"No matching GFA files found for {BENCHMARK_NAME}. Use --gfa-file to specify a file.")

        metafunc.parametrize("gfa_path", test_files, ids=_gfa_test_id)


def pytest_collection_modifyitems(items):
    """Group all medium-tier tests so at most one runs at a time with pytest-xdist."""
    marker = pytest.mark.xdist_group("roundtrip_medium")
    for item in items:
        item.add_marker(marker)


class TestStructuralRoundtrip:
    """Compare graph components individually."""

    def test_segment_names_match(self, gfa_path, test_output_dir):
        print(f"\n--- Testing file: {gfa_path} ---")
        if not os.path.exists(gfa_path):
            pytest.skip(f"Test file not found: {gfa_path}")
        g, h = _roundtrip_file(gfa_path, test_output_dir=test_output_dir)
        assert sorted(g.nodes()) == sorted(h.nodes())

    def test_segment_sequences_match(self, gfa_path, test_output_dir):
        print(f"\n--- Testing file: {gfa_path} ---")
        if not os.path.exists(gfa_path):
            pytest.skip(f"Test file not found: {gfa_path}")
        g, h = _roundtrip_file(gfa_path, test_output_dir=test_output_dir)
        g_data = dict(g.nodes_iter(data=True))
        h_data = dict(h.nodes_iter(data=True))
        for node_id in g.nodes():
            assert node_id in h_data, f"Node {node_id} missing after round-trip"
            g_seq = g_data[node_id].get("sequence", "*")
            h_seq = h_data[node_id].get("sequence", "*")
            assert g_seq == h_seq, f"Sequence mismatch for node {node_id}: {g_seq!r} vs {h_seq!r}"

    def test_links_match(self, gfa_path, test_output_dir):
        """Check that links (including orientations) are preserved."""
        print(f"\n--- Testing file: {gfa_path} ---")
        if not os.path.exists(gfa_path):
            pytest.skip(f"Test file not found: {gfa_path}")
        g, h = _roundtrip_file(gfa_path, test_output_dir=test_output_dir)

        def _link_set(gfa_obj):
            links = set()
            for u, v, key, data in gfa_obj.edges_iter(data=True, keys=True):
                from_node = data.get("from_node", u)
                from_orn = data.get("from_orn", "+")
                to_node = data.get("to_node", v)
                to_orn = data.get("to_orn", "+")
                alignment = data.get("alignment", "*")
                links.add((from_node, from_orn, to_node, to_orn, alignment))
            return links

        g_links = _link_set(g)
        h_links = _link_set(h)
        assert g_links == h_links, f"Link mismatch.\n  Missing: {g_links - h_links}\n  Extra: {h_links - g_links}"


# ---------------------------------------------------------------------------
# Encoding parametrized tests
# ---------------------------------------------------------------------------

INT_IDENTITY_CODE = 0x00
STR_IDENTITY_CODE = 0x00

ALL_INT_ENCODING_NAMES = sorted([name for name in _ALL_INT_ENCODINGS.keys() if name])
# Exclude placeholder encodings that have no decompressor implementation
_NO_DECOMPRESSOR = {"frontcoding", "delta"}
ALL_STR_ENCODING_NAMES = sorted([name for name in _ALL_STR_ENCODINGS.keys() if name and name not in _NO_DECOMPRESSOR])

INT_ENCODINGS = [
    ("none", 0x00),
    ("varint", 0x01),
    ("fixed16", 0x02),
    ("fixed32", 0x0A),
    ("fixed64", 0x0B),
    ("delta", 0x03),
    ("gamma", 0x04),
    ("omega", 0x05),
    ("golomb", 0x06),
    ("rice", 0x07),
    ("streamvbyte", 0x08),
    ("vbyte", 0x09),
    ("pfor_delta", 0x0C),
    ("simple8b", 0x0D),
    ("group_varint", 0x0E),
    ("bit_packing", 0x0F),
    ("fibonacci", 0x10),
    ("exp_golomb", 0x11),
    ("byte_packed", 0x12),
    ("masked_vbyte", 0x13),
]
STR_ENCODINGS = [
    ("none", 0x00),
    ("zstd", 0x01),
    ("zstd_dict", 0x0B),
    ("gzip", 0x02),
    ("lzma", 0x03),
    ("lz4", 0x0C),
    ("brotli", 0x0D),
    ("huffman", 0x04),
    ("2bit", 0x05),
    ("arithmetic", 0x06),
    ("bwt_huffman", 0x07),
    ("rle", 0x08),
    ("cigar", 0x09),
    ("dictionary", 0x0A),
    ("ppm", 0x0E),
    ("superstring_none", 0xF0),
    ("superstring_huffman", 0xF4),
    ("superstring_2bit", 0xF5),
    ("superstring_ppm", 0xF1),
]
BLOCK_SIZES = [512, 1024, 4096]

ENCODING_COMBINATIONS = [
    (int_name, int_code, str_name, str_code, bs)
    for int_name, int_code in INT_ENCODINGS
    for str_name, str_code in STR_ENCODINGS
    for bs in BLOCK_SIZES
]

ALL_ENCODING_TEST_PARAMS = [
    (gfa_path, int_name, str_name, bs)
    for gfa_path in ALL_ROUNDTRIP_FILES
    for int_name, _, str_name, _, bs in ENCODING_COMBINATIONS
]


def _build_compression_options(int_encoding_name, str_encoding_name):
    int_code = dict(INT_ENCODINGS).get(int_encoding_name, 0x00)
    str_code = dict(STR_ENCODINGS).get(str_encoding_name, 0x00)
    return {
        "segment_names_int_encoding": int_code,
        "segment_names_str_encoding": str_code,
        "segments_int_encoding": int_code,
        "segments_str_encoding": str_code,
        "links_fromto_int_encoding": int_code,
        "links_cigars_int_encoding": int_code,
        "links_cigars_str_encoding": str_code,
        "paths_names_int_encoding": int_code,
        "paths_names_str_encoding": str_code,
        "paths_cigars_int_encoding": int_code,
        "paths_cigars_str_encoding": str_code,
        "walks_sample_ids_str_encoding": str_code,
        "walks_hap_indices_int_encoding": int_code,
        "walks_seq_ids_int_encoding": int_code,
        "walks_seq_ids_str_encoding": str_code,
        "walks_start_int_encoding": int_code,
        "walks_end_int_encoding": int_code,
    }


def _build_isolated_int_encoding_options(encoding_name):
    encoding_code = 0x00
    for name, code in INT_ENCODINGS:
        if name == encoding_name:
            encoding_code = code
            break

    return {
        "segment_names_int_encoding": encoding_code,
        "segment_names_str_encoding": STR_IDENTITY_CODE,
        "segments_int_encoding": encoding_code,
        "segments_str_encoding": STR_IDENTITY_CODE,
        "links_fromto_int_encoding": encoding_code,
        "links_cigars_int_encoding": encoding_code,
        "links_cigars_str_encoding": STR_IDENTITY_CODE,
        "paths_names_int_encoding": encoding_code,
        "paths_names_str_encoding": STR_IDENTITY_CODE,
        "paths_cigars_int_encoding": encoding_code,
        "paths_cigars_str_encoding": STR_IDENTITY_CODE,
        "walks_sample_ids_str_encoding": STR_IDENTITY_CODE,
        "walks_hap_indices_int_encoding": encoding_code,
        "walks_seq_ids_int_encoding": encoding_code,
        "walks_seq_ids_str_encoding": STR_IDENTITY_CODE,
        "walks_start_int_encoding": encoding_code,
        "walks_end_int_encoding": encoding_code,
    }


def _build_isolated_str_encoding_options(encoding_name):
    encoding_code = 0x00
    for name, code in STR_ENCODINGS:
        if name == encoding_name:
            encoding_code = code
            break

    return {
        "segment_names_int_encoding": INT_IDENTITY_CODE,
        "segment_names_str_encoding": encoding_code,
        "segments_int_encoding": INT_IDENTITY_CODE,
        "segments_str_encoding": encoding_code,
        "links_fromto_int_encoding": INT_IDENTITY_CODE,
        "links_cigars_int_encoding": INT_IDENTITY_CODE,
        "links_cigars_str_encoding": encoding_code,
        "paths_names_int_encoding": INT_IDENTITY_CODE,
        "paths_names_str_encoding": encoding_code,
        "paths_cigars_int_encoding": INT_IDENTITY_CODE,
        "paths_cigars_str_encoding": encoding_code,
        "walks_sample_ids_str_encoding": encoding_code,
        "walks_hap_indices_int_encoding": INT_IDENTITY_CODE,
        "walks_seq_ids_int_encoding": INT_IDENTITY_CODE,
        "walks_seq_ids_str_encoding": encoding_code,
        "walks_start_int_encoding": INT_IDENTITY_CODE,
        "walks_end_int_encoding": INT_IDENTITY_CODE,
    }


@pytest.mark.parametrize(
    "gfa_path,int_encoding,str_encoding,block_size", ALL_ENCODING_TEST_PARAMS, ids=_encoding_test_id
)
class TestEncodingRoundtrip:
    def test_roundtrip_with_encoding(self, gfa_path, int_encoding, str_encoding, block_size, test_output_dir):
        print(
            f"\n--- Testing file: {gfa_path} with encoding: {int_encoding}/{str_encoding}, block_size: {block_size} ---"
        )
        if not os.path.exists(gfa_path):
            pytest.skip(f"Test file not found: {gfa_path}")

        compression_options = _build_compression_options(int_encoding, str_encoding)
        g, h = _roundtrip_file(
            gfa_path, block_size=block_size, compression_options=compression_options, test_output_dir=test_output_dir
        )

        assert sorted(g.nodes()) == sorted(h.nodes()), f"Nodes mismatch with {int_encoding}/{str_encoding}/{block_size}"

        g_data = dict(g.nodes_iter(data=True))
        h_data = dict(h.nodes_iter(data=True))
        for node_id in g.nodes():
            assert node_id in h_data, f"Node {node_id} missing after round-trip"
            g_seq = g_data[node_id].get("sequence", "*")
            h_seq = h_data[node_id].get("sequence", "*")
            assert g_seq == h_seq, f"Sequence mismatch for node {node_id}: {g_seq!r} vs {h_seq!r}"

        def _link_set(gfa_obj):
            links = set()
            for u, v, key, data in gfa_obj.edges_iter(data=True, keys=True):
                from_node = data.get("from_node", u)
                from_orn = data.get("from_orn", "+")
                to_node = data.get("to_node", v)
                to_orn = data.get("to_orn", "+")
                alignment = data.get("alignment", "*")
                links.add((from_node, from_orn, to_node, to_orn, alignment))
            return links

        g_links = _link_set(g)
        h_links = _link_set(h)
        assert g_links == h_links, f"Link mismatch with {int_encoding}/{str_encoding}/{block_size}"


# ---------------------------------------------------------------------------
# Isolated encoding tests
# ---------------------------------------------------------------------------


def _isolated_int_test_id(params):
    if isinstance(params, (list, tuple)) and len(params) == 3:
        gfa_path, encoding_name, block_size = params
        return f"[{gfa_path}]-int-{encoding_name}-{block_size}"
    return str(params)


def _isolated_str_test_id(params):
    if isinstance(params, (list, tuple)) and len(params) == 3:
        gfa_path, encoding_name, block_size = params
        return f"[{gfa_path}]-str-{encoding_name}-{block_size}"
    return str(params)


ISOLATED_INT_TEST_PARAMS = [
    (gfa_path, encoding_name, bs)
    for gfa_path in ALL_ROUNDTRIP_FILES
    for encoding_name in ALL_INT_ENCODING_NAMES
    for bs in BLOCK_SIZES
]

ISOLATED_STR_TEST_PARAMS = [
    (gfa_path, encoding_name, bs)
    for gfa_path in ALL_ROUNDTRIP_FILES
    for encoding_name in ALL_STR_ENCODING_NAMES
    for bs in BLOCK_SIZES
]


@pytest.mark.parametrize("gfa_path,encoding_name,block_size", ISOLATED_INT_TEST_PARAMS, ids=_isolated_int_test_id)
class TestIsolatedIntEncodingRoundtrip:
    def test_int_encoding_roundtrip(self, gfa_path, encoding_name, block_size, test_output_dir):
        print(f"\n--- Testing int encoding: {encoding_name} on {gfa_path} (block_size={block_size}) ---")
        if not os.path.exists(gfa_path):
            pytest.skip(f"Test file not found: {gfa_path}")

        compression_options = _build_isolated_int_encoding_options(encoding_name)
        g, h = _roundtrip_file(
            gfa_path, block_size=block_size, compression_options=compression_options, test_output_dir=test_output_dir
        )

        assert sorted(g.nodes()) == sorted(h.nodes()), (
            f"Node mismatch for int encoding '{encoding_name}' on {gfa_path} (block_size={block_size})"
        )

        g_data = dict(g.nodes_iter(data=True))
        h_data = dict(h.nodes_iter(data=True))
        for node_id in g.nodes():
            assert node_id in h_data, f"Node {node_id} missing after round-trip"
            g_seq = g_data[node_id].get("sequence", "*")
            h_seq = h_data[node_id].get("sequence", "*")
            assert g_seq == h_seq, (
                f"Sequence mismatch for node {node_id} with int encoding '{encoding_name}': {g_seq!r} vs {h_seq!r}"
            )

        def _link_set(gfa_obj):
            links = set()
            for u, v, key, data in gfa_obj.edges_iter(data=True, keys=True):
                from_node = data.get("from_node", u)
                from_orn = data.get("from_orn", "+")
                to_node = data.get("to_node", v)
                to_orn = data.get("to_orn", "+")
                alignment = data.get("alignment", "*")
                links.add((from_node, from_orn, to_node, to_orn, alignment))
            return links

        g_links = _link_set(g)
        h_links = _link_set(h)
        assert g_links == h_links, (
            f"Link mismatch for int encoding '{encoding_name}' on {gfa_path} "
            f"(block_size={block_size}). Missing: {g_links - h_links}, Extra: {h_links - g_links}"
        )


@pytest.mark.parametrize("gfa_path,encoding_name,block_size", ISOLATED_STR_TEST_PARAMS, ids=_isolated_str_test_id)
class TestIsolatedStrEncodingRoundtrip:
    def test_str_encoding_roundtrip(self, gfa_path, encoding_name, block_size, test_output_dir):
        print(f"\n--- Testing str encoding: {encoding_name} on {gfa_path} (block_size={block_size}) ---")
        if not os.path.exists(gfa_path):
            pytest.skip(f"Test file not found: {gfa_path}")

        compression_options = _build_isolated_str_encoding_options(encoding_name)
        g, h = _roundtrip_file(
            gfa_path, block_size=block_size, compression_options=compression_options, test_output_dir=test_output_dir
        )

        assert sorted(g.nodes()) == sorted(h.nodes()), (
            f"Node mismatch for str encoding '{encoding_name}' on {gfa_path} (block_size={block_size})"
        )

        g_data = dict(g.nodes_iter(data=True))
        h_data = dict(h.nodes_iter(data=True))
        for node_id in g.nodes():
            assert node_id in h_data, f"Node {node_id} missing after round-trip"
            g_seq = g_data[node_id].get("sequence", "*")
            h_seq = h_data[node_id].get("sequence", "*")
            assert g_seq == h_seq, (
                f"Sequence mismatch for node {node_id} with str encoding '{encoding_name}': {g_seq!r} vs {h_seq!r}"
            )

        def _link_set(gfa_obj):
            links = set()
            for u, v, key, data in gfa_obj.edges_iter(data=True, keys=True):
                from_node = data.get("from_node", u)
                from_orn = data.get("from_orn", "+")
                to_node = data.get("to_node", v)
                to_orn = data.get("to_orn", "+")
                alignment = data.get("alignment", "*")
                links.add((from_node, from_orn, to_node, to_orn, alignment))
            return links

        g_links = _link_set(g)
        h_links = _link_set(h)
        assert g_links == h_links, (
            f"Link mismatch for str encoding '{encoding_name}' on {gfa_path} "
            f"(block_size={block_size}). Missing: {g_links - h_links}, Extra: {h_links - g_links}"
        )


if __name__ == "__main__":
    if HAS_PYTEST:
        pytest.main([__file__, "-v"])
    else:
        print("pytest not available. Run with pytest to execute tests.")
