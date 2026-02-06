#!/usr/bin/env python3
"""
Round-trip tests: GFA -> BGFA -> GFA equality checks.

Tests that converting a GFA file to BGFA and back produces an identical GFA.
"""

import os
import sys
import tempfile

import pytest

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from pygfa.gfa import GFA


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _roundtrip(gfa_text: str, block_size: int = 1024, compression_options: dict = None):
    """Write gfa_text to a file, load it, convert to BGFA and back, return (original, roundtrip) GFA objects."""
    if compression_options is None:
        compression_options = {}

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


def _roundtrip_file(gfa_path: str, block_size: int = 1024, compression_options: dict = None):
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


# ---------------------------------------------------------------------------
# Strict round-trip: to_gfa() text must be identical
# ---------------------------------------------------------------------------

class TestStrictRoundtrip:
    """Tests where the full to_gfa() text must be identical after GFA->BGFA->GFA."""

    def test_simple_segments_and_links(self):
        gfa_text = (
            "H\tVN:Z:1.0\n"
            "S\t1\tACGT\n"
            "S\t2\tTTTT\n"
            "S\t3\tGGGG\n"
            "L\t1\t+\t2\t+\t2M\n"
            "L\t2\t+\t3\t+\t3M\n"
        )
        g, h = _roundtrip(gfa_text)
        assert g.to_gfa() == h.to_gfa()

    def test_star_sequences(self):
        gfa_text = (
            "H\tVN:Z:1.0\n"
            "S\t1\t*\n"
            "S\t2\tACGT\n"
            "S\t3\t*\n"
            "L\t1\t+\t2\t+\t*\n"
            "L\t2\t+\t3\t+\t5M\n"
        )
        g, h = _roundtrip(gfa_text)
        assert g.to_gfa() == h.to_gfa()

    def test_segments_only(self):
        gfa_text = (
            "H\tVN:Z:1.0\n"
            "S\ta\tAAAA\n"
            "S\tb\tCCCC\n"
            "S\tc\tGGGG\n"
            "S\td\tTTTT\n"
        )
        g, h = _roundtrip(gfa_text)
        assert g.to_gfa() == h.to_gfa()

    def test_single_segment(self):
        gfa_text = (
            "H\tVN:Z:1.0\n"
            "S\ts1\tACGTACGT\n"
        )
        g, h = _roundtrip(gfa_text)
        assert g.to_gfa() == h.to_gfa()

    def test_many_segments_small_block_size(self):
        """Test that multiple blocks are handled correctly with a small block size."""
        lines = ["H\tVN:Z:1.0"]
        for i in range(10):
            lines.append(f"S\tseg{i}\tACGT")
        for i in range(9):
            lines.append(f"L\tseg{i}\t+\tseg{i+1}\t+\t2M")
        gfa_text = "\n".join(lines) + "\n"

        g, h = _roundtrip(gfa_text, block_size=4)
        assert g.to_gfa() == h.to_gfa()

    def test_long_sequences(self):
        seq1 = "ACGT" * 250
        seq2 = "TTTT" * 300
        gfa_text = (
            "H\tVN:Z:1.0\n"
            f"S\t1\t{seq1}\n"
            f"S\t2\t{seq2}\n"
            "L\t1\t+\t2\t+\t10M\n"
        )
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
            "H\tVN:Z:1.0\n"
            "S\t100\tAAAA\n"
            "S\t200\tCCCC\n"
            "S\t300\tGGGG\n"
            "L\t100\t+\t200\t+\t2M\n"
            "L\t200\t+\t300\t+\t2M\n"
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


# ---------------------------------------------------------------------------
# Structural round-trip: compare individual components for data files
# ---------------------------------------------------------------------------

DATA_FILES = [
    "data/example_1.gfa",
    "data/example_2.gfa",
    "data/example_3.gfa",
]


@pytest.mark.parametrize("gfa_path", DATA_FILES)
class TestStructuralRoundtrip:
    """Compare graph components individually, accounting for known BGFA limitations.

    Known limitations:
    - Link orientations are not preserved (reader always returns '+')
    - Paths are not read back from BGFA (reader stub)
    - Optional fields on segments (LN:i, RC:i, etc.) are not preserved
    """

    def test_segment_names_match(self, gfa_path):
        if not os.path.exists(gfa_path):
            pytest.skip(f"Test file not found: {gfa_path}")
        g, h = _roundtrip_file(gfa_path)
        assert sorted(g.nodes()) == sorted(h.nodes())

    def test_segment_sequences_match(self, gfa_path):
        if not os.path.exists(gfa_path):
            pytest.skip(f"Test file not found: {gfa_path}")
        g, h = _roundtrip_file(gfa_path)
        for node_id in g.nodes():
            g_data = dict(g.nodes_iter(data=True))
            h_data = dict(h.nodes_iter(data=True))
            assert node_id in h_data, f"Node {node_id} missing after round-trip"
            g_seq = g_data[node_id].get("sequence", "*")
            h_seq = h_data[node_id].get("sequence", "*")
            assert g_seq == h_seq, f"Sequence mismatch for node {node_id}: {g_seq!r} vs {h_seq!r}"

    def test_edge_count_matches(self, gfa_path):
        if not os.path.exists(gfa_path):
            pytest.skip(f"Test file not found: {gfa_path}")
        g, h = _roundtrip_file(gfa_path)
        assert len(g.edges()) == len(h.edges())

    def test_link_endpoints_match(self, gfa_path):
        """Check that link endpoints (ignoring orientation) are preserved."""
        if not os.path.exists(gfa_path):
            pytest.skip(f"Test file not found: {gfa_path}")
        g, h = _roundtrip_file(gfa_path)

        def _link_set(gfa_obj):
            links = set()
            for u, v, key, data in gfa_obj.edges_iter(data=True, keys=True):
                from_node = data.get("from_node", u)
                to_node = data.get("to_node", v)
                alignment = data.get("alignment", "*")
                links.add((from_node, to_node, alignment))
            return links

        g_links = _link_set(g)
        h_links = _link_set(h)
        assert g_links == h_links, (
            f"Link endpoint mismatch.\n"
            f"  Missing: {g_links - h_links}\n"
            f"  Extra: {h_links - g_links}"
        )


# ---------------------------------------------------------------------------
# Block size variation tests
# ---------------------------------------------------------------------------

class TestBlockSizes:
    """Test that different block sizes produce identical round-trip results."""

    GFA_TEXT = (
        "H\tVN:Z:1.0\n"
        + "".join(f"S\ts{i}\tACGT\n" for i in range(20))
        + "".join(f"L\ts{i}\t+\ts{i+1}\t+\t2M\n" for i in range(19))
    )

    @pytest.mark.parametrize("block_size", [1, 2, 4, 8, 16, 32, 1024])
    def test_block_size(self, block_size):
        g, h = _roundtrip(self.GFA_TEXT, block_size=block_size)
        assert g.to_gfa() == h.to_gfa()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
