#!/usr/bin/env python3
"""Regression tests for BGFA walk writing (Bug 6: walks were silently dropped)."""

import contextlib
import io
import json
import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pygfa.bgfa._constants import SECTION_ID_WALKS
from pygfa.bgfa._reader import ReaderBGFA
from pygfa.bgfa._validation import dump_bgfa, validate_bgfa
from pygfa.exceptions import GFAError
from pygfa.gfa import GFA


def _section_ids(data: bytes) -> list[int]:
    """Return the section ids of all blocks in a BGFA file."""
    header_len = struct.unpack_from("<H", data, 6)[0]
    offset = 8 + header_len + 1
    reader = ReaderBGFA()
    ids = []
    while offset < len(data):
        ids.append(data[offset])
        _, consumed = reader._skip_block(data, offset)
        offset += consumed
    return ids


class TestBGFAWalkRoundtrip(unittest.TestCase):
    """Walks must survive GFA -> BGFA -> GFA."""

    def setUp(self):
        self.gfa_path = "data/test_walks.gfa"
        self._tmp_files = []

    def tearDown(self):
        for p in self._tmp_files:
            try:
                os.unlink(p)
            except OSError:
                pass

    def _bgfa_path(self):
        fd, path = tempfile.mkstemp(suffix=".bgfa")
        os.close(fd)
        self._tmp_files.append(path)
        return path

    def test_gfa_parsing_preserves_walks(self):
        """The fixture must parse with both walks intact (sign form)."""
        g = GFA.from_gfa(self.gfa_path)
        self.assertEqual(len(g.walks()), 2)
        w1 = g.walks("sample1_0_seqA")
        self.assertEqual(w1["walk"], "1+2+3+")
        self.assertEqual(w1["seq_start"], 1)
        self.assertEqual(w1["seq_end"], 10)
        w2 = g.walks("sample2_1_seqB")
        self.assertEqual(w2["walk"], "1-2+3+")
        self.assertEqual(w2["seq_start"], 5)
        self.assertEqual(w2["seq_end"], 20)

    def test_writer_emits_walks_block(self):
        """The BGFA output must contain a section-5 (walks) block."""
        bgfa = self._bgfa_path()
        g = GFA.from_gfa(self.gfa_path)
        g.to_bgfa(bgfa)
        with open(bgfa, "rb") as f:
            data = f.read()
        self.assertIn(SECTION_ID_WALKS, _section_ids(data))

    def test_walk_roundtrip_preserves_walks(self):
        """Walks must survive GFA -> BGFA -> GFA with all fields intact."""
        bgfa = self._bgfa_path()
        g = GFA.from_gfa(self.gfa_path)
        g.to_bgfa(bgfa)
        h = GFA.from_bgfa(bgfa)
        self.assertEqual(len(h.walks()), 2)
        for key, expected in g.walks().items():
            actual = h.walks(key)
            self.assertIsNotNone(actual, f"walk {key} missing after roundtrip")
            for field in ("sample_id", "hapindex", "seq_id", "seq_start", "seq_end", "walk"):
                self.assertEqual(
                    actual[field], expected[field], f"walk {key} field {field} differs"
                )

    def test_cat_preserves_walks(self):
        """to_gfa() text output must contain the W lines."""
        bgfa = self._bgfa_path()
        g = GFA.from_gfa(self.gfa_path)
        g.to_bgfa(bgfa)
        h = GFA.from_bgfa(bgfa)
        text = h.to_gfa()
        self.assertIn("W\tsample1\t0\tseqA\t1\t10\t1+2+3+", text)
        self.assertIn("W\tsample2\t1\tseqB\t5\t20\t1-2+3+", text)

    def test_no_walks_no_block(self):
        """A GFA without walks must produce a BGFA with no section-5 block."""
        bgfa = self._bgfa_path()
        g = GFA.from_gfa("data/example_3.gfa")
        self.assertEqual(len(g.walks()), 0)
        g.to_bgfa(bgfa)
        with open(bgfa, "rb") as f:
            data = f.read()
        self.assertNotIn(SECTION_ID_WALKS, _section_ids(data))

    def test_walk_roundtrip_with_encodings(self):
        """Walks must roundtrip with non-default compression codes."""
        bgfa = self._bgfa_path()
        g = GFA.from_gfa(self.gfa_path)
        g.to_bgfa(
            bgfa,
            walk_sample_ids_enc="varint+zstd",
            walk_haplotype_indices_enc="varint+none",
            walk_sequence_ids_enc="varint+zstd",
            walk_positions_start_enc="varint+none",
            walk_positions_end_enc="varint+none",
            walk_steps_enc="varint+none",
        )
        h = GFA.from_bgfa(bgfa)
        self.assertEqual(len(h.walks()), 2)
        for key, expected in g.walks().items():
            actual = h.walks(key)
            for field in ("sample_id", "hapindex", "seq_id", "seq_start", "seq_end", "walk"):
                self.assertEqual(actual[field], expected[field], f"walk {key} field {field} differs")

    def test_walk_roundtrip_multi_block(self):
        """All walks must survive when they span multiple blocks (block_size=1)."""
        bgfa = self._bgfa_path()
        g = GFA.from_gfa(self.gfa_path)
        g.to_bgfa(bgfa, block_size=1)
        with open(bgfa, "rb") as f:
            data = f.read()
        # One walks block per walk proves none were dropped across chunks.
        self.assertEqual(_section_ids(data).count(SECTION_ID_WALKS), 2)
        h = GFA.from_bgfa(bgfa)
        self.assertEqual(len(h.walks()), 2)
        for key, expected in g.walks().items():
            actual = h.walks(key)
            self.assertIsNotNone(actual, f"walk {key} missing after roundtrip")
            for field in ("sample_id", "hapindex", "seq_id", "seq_start", "seq_end", "walk"):
                self.assertEqual(actual[field], expected[field], f"walk {key} field {field} differs")

    def test_validate_bgfa_accepts_walks(self):
        """validate_bgfa must report a walks-bearing BGFA as valid."""
        bgfa = self._bgfa_path()
        g = GFA.from_gfa(self.gfa_path)
        g.to_bgfa(bgfa)
        result = validate_bgfa(bgfa)
        self.assertTrue(result["valid"], f"validate_bgfa rejected a valid walks file: {result}")

    def test_dump_bgfa_walks(self):
        """dump_bgfa must show the walks with the correct field values."""
        bgfa = self._bgfa_path()
        g = GFA.from_gfa(self.gfa_path)
        g.to_bgfa(bgfa)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            dump_bgfa(bgfa)
        dumped = json.loads(buf.getvalue())
        walk_blocks = [b for b in dumped["blocks"] if b.get("section_type") == "walks"]
        self.assertEqual(len(walk_blocks), 1)
        walks = walk_blocks[0]["walks"]
        self.assertEqual(len(walks), 2)
        self.assertEqual(walks[0]["sample_id"], "sample1")
        self.assertEqual(walks[0]["haplotype_index"], 0)
        self.assertEqual(walks[0]["sequence_id"], "seqA")
        self.assertEqual(walks[0]["start_position"], 1)
        self.assertEqual(walks[0]["end_position"], 10)
        self.assertEqual(walks[0]["oriented_segment_ids"], "1+2+3+")

    def test_walk_unknown_segment_raises(self):
        """A walk referencing a missing segment must raise GFAError, not corrupt data."""
        g = GFA.from_gfa(self.gfa_path)
        g.add_walk(
            {
                "sample_id": "sample3",
                "hapindex": 0,
                "seq_id": "seqC",
                "seq_start": 1,
                "seq_end": 5,
                "walk": "1+99+",
            }
        )
        with self.assertRaises(GFAError):
            g.to_bgfa(self._bgfa_path())


if __name__ == "__main__":
    unittest.main()