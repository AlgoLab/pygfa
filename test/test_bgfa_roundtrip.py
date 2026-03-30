#!/usr/bin/env python3
"""Round-trip tests: in-memory GFA -> BGFA -> GFA equality checks.

Tests that converting a GFA to BGFA and back produces an identical GFA.
These tests use small, in-memory GFA constructions and do not require data files.

File-based roundtrip tests are in:
  - test_bgfa_roundtrip_small.py  (at most 4 GB)
  - test_bgfa_roundtrip_medium.py (4-16 GB)
  - test_bgfa_roundtrip_large.py  (16-64 GB)
"""

import os
import sys
import tempfile

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from pygfa.gfa import GFA  # noqa: E402  # Needs sys.path setup first

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


def _roundtrip(gfa_text, block_size=1024, compression_options=None, test_output_dir=None):
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


if __name__ == "__main__":
    if HAS_PYTEST:
        pytest.main([__file__, "-v"])
    else:
        print("pytest not available. Run with pytest to execute tests.")
