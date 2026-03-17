#!/usr/bin/env python3
"""Round-trip tests: GFA -> BGFA -> GFA equality checks.

Tests that converting a GFA file to BGFA and back produces an identical GFA.
"""

import glob
import os
import sys
import tempfile

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from pygfa.gfa import GFA  # noqa: E402  # Needs sys.path setup first
from test_utils import should_run_test_for_gfa  # noqa: E402  # Needs sys.path setup first

# Import pytest with fallback for when it's not available
try:
    import pytest

    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False

    # Create a dummy pytest module with the decorators we need
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
# Helpers
# ---------------------------------------------------------------------------


def _roundtrip(gfa_text: str, block_size: int = 1024, compression_options: dict = None, test_output_dir=None):
    """Write gfa_text to a file, load it, convert to BGFA and back, return (original, roundtrip) GFA objects."""
    if compression_options is None:
        compression_options = {}

    # Use system temp directory with unique names for parallel test safety
    # tempfile.NamedTemporaryFile with delete=False ensures unique filenames
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gfa", delete=False) as f:
        f.write(gfa_text)
        gfa_path = f.name

    bgfa_path = gfa_path.replace(".gfa", ".bgfa")

    try:
        g = GFA.from_gfa(gfa_path)
        g.to_bgfa(bgfa_path, block_size, compression_options, verbose=False, debug=False, logfile=None)
        h = GFA.from_bgfa(bgfa_path, verbose=False, debug=False, logfile=None)
        return g, h
    finally:
        for p in (gfa_path, bgfa_path):
            if os.path.exists(p):
                os.unlink(p)


def _roundtrip_file(gfa_path: str, block_size: int = 1024, compression_options: dict = None, test_output_dir=None):
    """Load a GFA file, convert to BGFA and back, return (original, roundtrip) GFA objects."""
    if compression_options is None:
        compression_options = {}

    # Use system temp directory with unique name for parallel test safety
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


# ---------------------------------------------------------------------------
# Strict round-trip: to_gfa() text must be identical
# ---------------------------------------------------------------------------


class TestStrictRoundtrip:
    """Tests where the full to_gfa() text must be identical after GFA->BGFA->GFA."""

    def test_simple_segments_and_links(self):
        gfa_text = "H\tVN:Z:1.0\nS\t1\tACGT\nS\t2\tTTTT\nS\t3\tGGGG\nL\t1\t+\t2\t+\t2M\nL\t2\t+\t3\t+\t3M\n"
        g, h = _roundtrip(gfa_text)
        assert g.to_gfa() == h.to_gfa()

    def test_star_sequences(self):
        gfa_text = "H\tVN:Z:1.0\nS\t1\t*\nS\t2\tACGT\nS\t3\t*\nL\t1\t+\t2\t+\t*\nL\t2\t+\t3\t+\t5M\n"
        g, h = _roundtrip(gfa_text)
        assert g.to_gfa() == h.to_gfa()

    def test_segments_only(self):
        gfa_text = "H\tVN:Z:1.0\nS\ta\tAAAA\nS\tb\tCCCC\nS\tc\tGGGG\nS\td\tTTTT\n"
        g, h = _roundtrip(gfa_text)
        assert g.to_gfa() == h.to_gfa()

    def test_single_segment(self):
        gfa_text = "H\tVN:Z:1.0\nS\ts1\tACGTACGT\n"
        g, h = _roundtrip(gfa_text)
        assert g.to_gfa() == h.to_gfa()

    def test_many_segments_small_block_size(self):
        """Test that multiple blocks are handled correctly with a small block size."""
        lines = ["H\tVN:Z:1.0"]
        for i in range(10):
            lines.append(f"S\tseg{i}\tACGT")
        for i in range(9):
            lines.append(f"L\tseg{i}\t+\tseg{i + 1}\t+\t2M")
        gfa_text = "\n".join(lines) + "\n"

        g, h = _roundtrip(gfa_text, block_size=4)
        assert g.to_gfa() == h.to_gfa()

    def test_long_sequences(self):
        seq1 = "ACGT" * 250
        seq2 = "TTTT" * 300
        gfa_text = f"H\tVN:Z:1.0\nS\t1\t{seq1}\nS\t2\t{seq2}\nL\t1\t+\t2\t+\t10M\n"
        g, h = _roundtrip(gfa_text)
        assert g.to_gfa() == h.to_gfa()

    def test_complex_cigar(self):
        gfa_text = (
            "H\tVN:Z:1.0\n"
            "S\t1\tACGTACGT\n"
            "S\t2\tTTTTAAAA\n"
            "S\t3\tGGGGCCCC\n"
            "L\t1\t+\t2\t+\t3M1I2M\n"
            "L\t2\t+\t3\t+\t5M2D1M\n"
        )
        g, h = _roundtrip(gfa_text)
        assert g.to_gfa() == h.to_gfa()

    def test_numeric_segment_names(self):
        """Test that numeric segment names are preserved correctly."""
        gfa_text = (
            "H\tVN:Z:1.0\nS\t100\tAAAA\nS\t200\tCCCC\nS\t300\tGGGG\nL\t100\t+\t200\t+\t2M\nL\t200\t+\t300\t+\t2M\n"
        )
        g, h = _roundtrip(gfa_text)
        assert g.to_gfa() == h.to_gfa()

    def test_string_segment_names(self):
        """Test that alphanumeric segment names are preserved."""
        gfa_text = (
            "H\tVN:Z:1.0\n"
            "S\tchr1\tACGTACGT\n"
            "S\tchr2\tTTTTAAAA\n"
            "S\tmito\tGGGGCCCC\n"
            "L\tchr1\t+\tchr2\t+\t4M\n"
            "L\tchr2\t+\tmito\t+\t4M\n"
        )
        g, h = _roundtrip(gfa_text)
        assert g.to_gfa() == h.to_gfa()

    def test_minus_orientations(self):
        """Test that '-' orientations are preserved through BGFA round-trip."""
        gfa_text = "H\tVN:Z:1.0\nS\t1\tACGT\nS\t2\tTTTT\nS\t3\tGGGG\nL\t1\t+\t2\t-\t2M\nL\t2\t-\t3\t+\t3M\n"
        g, h = _roundtrip(gfa_text)
        assert g.to_gfa() == h.to_gfa()

    def test_all_minus_orientations(self):
        """Test links where all orientations are '-'."""
        gfa_text = "H\tVN:Z:1.0\nS\t1\tACGT\nS\t2\tTTTT\nS\t3\tGGGG\nL\t1\t-\t2\t-\t4M\nL\t2\t-\t3\t-\t3M\n"
        g, h = _roundtrip(gfa_text)
        assert g.to_gfa() == h.to_gfa()

    def test_mixed_orientations(self):
        """Test a graph with mixed '+' and '-' orientations on many links."""
        gfa_text = (
            "H\tVN:Z:1.0\n"
            "S\t1\tACGT\n"
            "S\t2\tTTTT\n"
            "S\t3\tGGGG\n"
            "S\t4\tCCCC\n"
            "S\t5\tAAAA\n"
            "L\t1\t+\t2\t+\t2M\n"
            "L\t1\t-\t3\t+\t2M\n"
            "L\t2\t+\t4\t-\t3M\n"
            "L\t3\t-\t4\t-\t3M\n"
            "L\t4\t+\t5\t+\t2M\n"
            "L\t4\t-\t5\t-\t2M\n"
        )
        g, h = _roundtrip(gfa_text)
        assert g.to_gfa() == h.to_gfa()


# ---------------------------------------------------------------------------
# Data file tests with comment-based filtering (all files recursively)
# ---------------------------------------------------------------------------

_ALL_BGFA_ROUNDTRIP_FILES = [
    f for f in glob.glob("data/**/*.gfa", recursive=True) if should_run_test_for_gfa("bgfa_roundtrip", f)
]


def _gfa_test_id(gfa_path):
    """Generate test ID with full GFA file path in brackets."""
    return f"[{gfa_path}]"


def _encoding_test_id(params):
    """Generate test ID for encoding tests: [gfa_path]-int_encoding-str_encoding-block_size"""
    if isinstance(params, (list, tuple)) and len(params) == 4:
        gfa_path, int_encoding, str_encoding, block_size = params
        return f"[{gfa_path}]-{int_encoding}-{str_encoding}-{block_size}"
    return str(params)


def pytest_generate_tests(metafunc):
    """Dynamically generate tests based on --gfa-file option."""
    if "gfa_path" in metafunc.fixturenames and metafunc.cls is TestStructuralRoundtrip:
        gfa_file = metafunc.config.getoption("--gfa-file")

        if gfa_file:
            # Use only the specified file
            test_files = (
                [gfa_file] if (os.path.exists(gfa_file) and should_run_test_for_gfa("bgfa_roundtrip", gfa_file)) else []
            )
        else:
            # Use all matching files
            test_files = _ALL_BGFA_ROUNDTRIP_FILES

        if not test_files:
            pytest.skip("No matching GFA files found. Use --gfa-file to specify a file.")

        metafunc.parametrize("gfa_path", test_files, ids=_gfa_test_id)


ALL_BGFA_ROUNDTRIP_FILES = _ALL_BGFA_ROUNDTRIP_FILES


class TestStructuralRoundtrip:
    """Compare graph components individually for files with paths.

    Known limitation: paths are not read back from BGFA (reader stub).
    """

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
# Block size variation tests
# ---------------------------------------------------------------------------


class TestBlockSizes:
    """Test that different block sizes produce identical round-trip results."""

    GFA_TEXT = (
        "H\tVN:Z:1.0\n"
        + "".join(f"S\ts{i}\tACGT\n" for i in range(20))
        + "".join(f"L\ts{i}\t+\ts{i + 1}\t+\t2M\n" for i in range(19))
    )

    @pytest.mark.parametrize("block_size", [1, 2, 4, 8, 16, 32, 1024])
    def test_block_size(self, block_size):
        g, h = _roundtrip(self.GFA_TEXT, block_size=block_size)
        assert g.to_gfa() == h.to_gfa()

    GFA_TEXT_MIXED_ORN = (
        "H\tVN:Z:1.0\n"
        + "".join(f"S\ts{i}\tACGT\n" for i in range(20))
        + "".join(
            f"L\ts{i}\t{'+' if i % 2 == 0 else '-'}\ts{i + 1}\t{'-' if i % 3 == 0 else '+'}\t2M\n" for i in range(19)
        )
    )

    @pytest.mark.parametrize("block_size", [1, 3, 7, 16, 1024])
    def test_block_size_mixed_orientations(self, block_size):
        g, h = _roundtrip(self.GFA_TEXT_MIXED_ORN, block_size=block_size)
        assert g.to_gfa() == h.to_gfa()


# ---------------------------------------------------------------------------
# Encoding parametrized tests for all bgfa_roundtrip files
# ---------------------------------------------------------------------------

INT_ENCODINGS = [
    ("none", 0x00),
    ("varint", 0x01),
    ("delta", 0x03),
]
STR_ENCODINGS = [
    ("none", 0x00),
    ("zstd", 0x01),
    ("gzip", 0x02),
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
    for gfa_path in ALL_BGFA_ROUNDTRIP_FILES
    for int_name, _, str_name, _, bs in ENCODING_COMBINATIONS
]


def _build_compression_options(int_encoding_name: str, str_encoding_name: str) -> dict:
    """Build compression_options dict with encoding for all applicable fields."""
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


@pytest.mark.parametrize(
    "gfa_path,int_encoding,str_encoding,block_size", ALL_ENCODING_TEST_PARAMS, ids=_encoding_test_id
)
class TestEncodingRoundtrip:
    """Test round-trip with different encoding combinations for all bgfa_roundtrip files."""

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


if __name__ == "__main__":
    if HAS_PYTEST:
        pytest.main([__file__, "-v"])
    else:
        print("pytest not available. Run with pytest to execute tests.")
