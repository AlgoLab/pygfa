#!/usr/bin/env python3
"""Regression tests for ENCODING_BUGS.md bugs 7-12 and the lark walk-form bug.

Covers:
  - Bug 7:  bit-level Elias gamma encoder
  - Bug 8:  canonical Elias omega encoder + decoder
  - Bug 9:  RLE per-string layout + loud failure on malformed input
  - Bug 10: dictionary decoder + delimited blob + loud failure
  - Bug 11: walk/path ORIENTATION_STRID writer layout
  - Bug 12: CIGAR STRING decomposition honours the stored integer encoding
  - lark grammar: ``>``/``<`` walk char form parses
"""

import os
import random
import sys
import tempfile
import unittest

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from pygfa.bgfa._reader import ReaderBGFA  # noqa: E402
from pygfa.encoding.dictionary_encoding import (  # noqa: E402
    _decompress_string_dictionary_wrapper,
)
from pygfa.encoding.enums import (  # noqa: E402
    CigarDecomposition,
    IntegerEncoding,
    StringEncoding,
    WalkDecomposition,
)
from pygfa.encoding.integer_list_encoding import (  # noqa: E402
    compress_integer_list_elias_gamma,
    compress_integer_list_elias_omega,
    compress_integer_list_varint,
    decode_integer_list_elias_gamma,
    decode_integer_list_elias_omega,
    decode_integer_list_varint,
)
from pygfa.encoding.rle_encoding import _decompress_string_rle_wrapper  # noqa: E402
from pygfa.encoding.string_encoding import compress_string_list  # noqa: E402
from pygfa.gfa import GFA  # noqa: E402


GFA_TEXT = """H\tVN:Z:1.0
S\t1\tACGT
S\t2\tGGGG
S\t3\tTTTT
L\t1\t+\t2\t+\t4M
L\t2\t+\t3\t-\t4M
P\tp1\t1+,2-,3+\t4M
W\tsample1\t0\tref\t0\t10\t>1<2>3
"""


def _roundtrip_bgfa(gfa_text, out_path, comp_options):
    with tempfile.NamedTemporaryFile("w", suffix=".gfa", delete=False) as f:
        f.write(gfa_text)
        gfa_path = f.name
    try:
        g = GFA.from_gfa(gfa_path)
        g.to_bgfa(out_path, compression_options=comp_options)
        return g, GFA.from_bgfa(out_path)
    finally:
        os.unlink(gfa_path)


class TestEliasGamma( unittest.TestCase):
    """Bug 7: bit-level Elias gamma encoder."""

    def test_roundtrip_small_values(self):
        data = [0, 1, 2, 3, 4, 5, 10, 100, 1000, 0, 1]
        out, consumed = decode_integer_list_elias_gamma(compress_integer_list_elias_gamma(data), len(data))
        self.assertEqual(out, data)
        self.assertEqual(consumed, len(compress_integer_list_elias_gamma(data)))

    def test_roundtrip_range(self):
        data = list(range(0, 2001))
        out, _ = decode_integer_list_elias_gamma(compress_integer_list_elias_gamma(data), len(data))
        self.assertEqual(out, data)

    def test_roundtrip_random(self):
        random.seed(7)
        data = [random.randint(0, 10**6) for _ in range(500)]
        out, _ = decode_integer_list_elias_gamma(compress_integer_list_elias_gamma(data), len(data))
        self.assertEqual(out, data)

    def test_empty(self):
        self.assertEqual(compress_integer_list_elias_gamma([]), b"")
        self.assertEqual(decode_integer_list_elias_gamma(b"", 0), ([], 0))


class TestEliasOmega(unittest.TestCase):
    """Bug 8: canonical Elias omega encoder + decoder."""

    def test_roundtrip_small_values(self):
        data = [0, 1, 2, 3, 4, 5, 10, 100, 1000, 0, 1]
        out, consumed = decode_integer_list_elias_omega(compress_integer_list_elias_omega(data), len(data))
        self.assertEqual(out, data)
        self.assertEqual(consumed, len(compress_integer_list_elias_omega(data)))

    def test_roundtrip_range(self):
        data = list(range(0, 2001))
        out, _ = decode_integer_list_elias_omega(compress_integer_list_elias_omega(data), len(data))
        self.assertEqual(out, data)

    def test_roundtrip_random(self):
        random.seed(7)
        data = [random.randint(0, 10**6) for _ in range(500)]
        out, _ = decode_integer_list_elias_omega(compress_integer_list_elias_omega(data), len(data))
        self.assertEqual(out, data)

    def test_empty(self):
        self.assertEqual(compress_integer_list_elias_omega([]), b"")
        self.assertEqual(decode_integer_list_elias_omega(b"", 0), ([], 0))


class TestRLEListEncoding(unittest.TestCase):
    """Bug 9: RLE per-string layout + loud failure."""

    def test_roundtrip_various_lists(self):
        for string_list in [
            ["AAAA", "GGGGCCCC", "ABCD"],
            ["AA", "A", "AAA", "A", "ABC"],
            ["hello", "", "world", ""],
            [""],
            ["", ""],
            ["TTTTTTTTTTTT"],
        ]:
            payload = compress_string_list(string_list, compress_integer_list_varint, "rle")
            out = _decompress_string_rle_wrapper(payload, len(string_list), decode_integer_list_varint)
            self.assertEqual([b.decode("ascii") for b in out], string_list)

    def test_malformed_payload_raises(self):
        payload = compress_string_list(["AAAA", "GGGG"], compress_integer_list_varint, "rle")
        # Truncating anywhere before the end must raise, never fall back to
        # identity decoding and silently return wrong data.
        for cut in range(1, len(payload)):
            with self.assertRaises((ValueError, IndexError)):
                _decompress_string_rle_wrapper(payload[:cut], 2, decode_integer_list_varint)


class TestDictionaryEncoding(unittest.TestCase):
    """Bug 10: dictionary decoder + delimited blob + loud failure."""

    def test_roundtrip_various_lists(self):
        for string_list in [
            ["sample_001", "sample_002", "sample_001", "x"],
            ["a", "a", "a"],
            ["only"],
            [],
            ["", "a", ""],
        ]:
            payload = compress_string_list(string_list, compress_integer_list_varint, "dictionary")
            out = _decompress_string_dictionary_wrapper(payload, len(string_list), decode_integer_list_varint)
            self.assertEqual([b.decode("ascii") for b in out], string_list)

    def test_malformed_payload_raises(self):
        with self.assertRaises(ValueError):
            _decompress_string_dictionary_wrapper(b"\x01\x01", 1, decode_integer_list_varint)


class TestCigarStringDecomposition(unittest.TestCase):
    """Bug 12: CIGAR STRING decomposition honours the stored integer encoding."""

    def test_roundtrip_fixed16_int_enc(self):
        code = (StringEncoding.NONE << 24) | (IntegerEncoding.FIXED16 << 8) | CigarDecomposition.STRING
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "c.bgfa")
            g, h = _roundtrip_bgfa(GFA_TEXT, out, {"use_heuristic": False, "link_cigars_enc": code})
        self.assertEqual(
            sorted((e.get("from_node"), e.get("to_node"), e.get("alignment")) for *_, e in h.edges(data=True)),
            sorted((e.get("from_node"), e.get("to_node"), e.get("alignment")) for *_, e in g.edges(data=True)),
        )

    def test_roundtrip_gzip_string_enc(self):
        code = (StringEncoding.GZIP << 24) | (IntegerEncoding.VARINT << 8) | CigarDecomposition.STRING
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "c.bgfa")
            g, h = _roundtrip_bgfa(GFA_TEXT, out, {"use_heuristic": False, "link_cigars_enc": code})
        self.assertEqual(
            sorted((e.get("from_node"), e.get("to_node"), e.get("alignment")) for *_, e in h.edges(data=True)),
            sorted((e.get("from_node"), e.get("to_node"), e.get("alignment")) for *_, e in g.edges(data=True)),
        )

    def test_roundtrip_paths_cigars(self):
        code = (StringEncoding.NONE << 24) | (IntegerEncoding.FIXED16 << 8) | CigarDecomposition.STRING
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "c.bgfa")
            g, h = _roundtrip_bgfa(GFA_TEXT, out, {"use_heuristic": False, "paths_cigars_enc": code})
        self.assertEqual(
            {k: v.get("overlaps") for k, v in h.paths().items()},
            {k: v.get("overlaps") for k, v in g.paths().items()},
        )


class TestWalkStridDecomposition(unittest.TestCase):
    """Bug 11: walk/path ORIENTATION_STRID writer layout."""

    def _strid_walk_code(self, names_str, walk_int):
        return (
            (WalkDecomposition.ORIENTATION_STRID << 24)
            | (IntegerEncoding.VARINT << 16)
            | (names_str << 8)
            | walk_int
        )

    def test_walk_roundtrip_identity_names(self):
        code = self._strid_walk_code(StringEncoding.NONE, IntegerEncoding.VARINT)
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "w.bgfa")
            g, h = _roundtrip_bgfa(GFA_TEXT, out, {"use_heuristic": False, "walk_steps_enc": code})
        self.assertEqual(
            {k: v.get("walk") for k, v in h.walks().items()},
            {k: v.get("walk") for k, v in g.walks().items()},
        )

    def test_walk_roundtrip_compressed_names(self):
        code = self._strid_walk_code(StringEncoding.GZIP, IntegerEncoding.FIXED16)
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "w.bgfa")
            g, h = _roundtrip_bgfa(GFA_TEXT, out, {"use_heuristic": False, "walk_steps_enc": code})
        self.assertEqual(
            {k: v.get("walk") for k, v in h.walks().items()},
            {k: v.get("walk") for k, v in g.walks().items()},
        )

    def test_path_roundtrip(self):
        code = (WalkDecomposition.ORIENTATION_STRID << 24) | IntegerEncoding.VARINT
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "p.bgfa")
            g, h = _roundtrip_bgfa(GFA_TEXT, out, {"use_heuristic": False, "paths_walk_enc": code})
        self.assertEqual(
            {k: v.get("segments") for k, v in h.paths().items()},
            {k: v.get("segments") for k, v in g.paths().items()},
        )

    def test_decode_walk_consumed_matches_payload(self):
        # The STRID branch must report exactly the payload length so that
        # multi-block paths (unbounded walk payload) advance correctly.
        from pygfa.bgfa._codec_utils import pack_bits_lsb
        from pygfa.bgfa._writer import _compress_string_for_bgfa

        comp_walks = self._strid_walk_code(StringEncoding.NONE, IntegerEncoding.VARINT)
        str_code = (comp_walks >> 8) & 0xFFFF
        p_walk_lengths = compress_integer_list_varint([3])
        p_seg_names = _compress_string_for_bgfa(["1", "2", "3"], str_code)
        p_orientations = pack_bits_lsb([0, 1, 0])
        payload = p_walk_lengths + p_seg_names + p_orientations

        reader = ReaderBGFA(use_numpy=False)
        walks, consumed = reader._decode_walk(
            payload, 1, comp_walks, decode_integer_list_varint, ["1", "2", "3"]
        )
        self.assertEqual(walks, [["1+", "2-", "3+"]])
        self.assertEqual(consumed, len(payload))


class TestLarkWalkCharForm(unittest.TestCase):
    """Lark grammar: ``>``/``<`` walk char form."""

    def test_char_form_parses(self):
        with tempfile.NamedTemporaryFile("w", suffix=".gfa", delete=False) as f:
            f.write(GFA_TEXT)
            gfa_path = f.name
        g = GFA.from_gfa(gfa_path)
        self.assertEqual(g.walks()["sample1_0_ref"].get("walk"), "1+2-3+")

    def test_sign_form_still_parses(self):
        text = GFA_TEXT.replace(">1<2>3", "1+2-3+")
        with tempfile.NamedTemporaryFile("w", suffix=".gfa", delete=False) as f:
            f.write(text)
            gfa_path = f.name
        g = GFA.from_gfa(gfa_path)
        self.assertEqual(g.walks()["sample1_0_ref"].get("walk"), "1+2-3+")

    def test_char_form_roundtrip_bgfa(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "w.bgfa")
            g, h = _roundtrip_bgfa(GFA_TEXT, out, {"use_heuristic": False})
        self.assertEqual(
            {k: v.get("walk") for k, v in h.walks().items()},
            {k: v.get("walk") for k, v in g.walks().items()},
        )


if __name__ == "__main__":
    unittest.main()
