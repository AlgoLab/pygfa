#!/usr/bin/env python3
"""Regression tests for BGFA encoding inconsistencies."""

import contextlib
import io
import json
import os
import struct
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest

from pygfa.bgfa._validation import validate_bgfa, dump_bgfa
from pygfa.encoding.enums import IntegerEncoding
from pygfa.exceptions import InvalidEncodingError
from pygfa.gfa import GFA


def _links_block_offset(data: bytes) -> int:
    """Return the offset of the links block (section_id == 3) in *data*.

    Skips the BGFA header and, when present, the segments block.  Shared by
    the dump-corruption tests and the ``compression_fromto`` tests so the
    segments-header arithmetic lives in one place.
    """
    hdr_len = struct.unpack_from("<H", data, 6)[0]
    offset = 8 + hdr_len + 1
    if data[offset] == 2:
        # Segments header: section(1)+record(2)+comp_names(2)+clen_names(8)+
        # ulen_names(8)+comp_str(2)+clen_str(8)+ulen_str(8) = 39 bytes.
        clen_names = struct.unpack_from("<Q", data, offset + 5)[0]
        clen_str = struct.unpack_from("<Q", data, offset + 23)[0]
        offset += 39 + clen_names + clen_str
    if data[offset] != 3:
        raise AssertionError(f"Expected a links block at offset {offset}, got {data[offset]}")
    return offset


class TestValidatorUlenSequences(unittest.TestCase):
    """Bug 1: validate_bgfa uses ulen_names instead of parsed['ulen_sequences']."""

    def setUp(self):
        # Use example_3 which has names="11","12","13"(6 bytes) and
        # sequences="ACCTT","TCAAGG","CTTGATT"(18 bytes) — different lengths.
        self.gfa_path = "data/example_3.gfa"
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

    def test_validator_does_not_falsely_report_sequences_mismatch(self):
        """Bug 1: ulen_sequences mismatch should not be falsely reported."""
        bgfa = self._bgfa_path()
        g = GFA.from_gfa(self.gfa_path)
        g.to_bgfa(bgfa, block_size=1024)

        result = validate_bgfa(bgfa)

        # Check ulen_sequences specifically — should be correct
        found = False
        for block in result.get("blocks", []):
            for fn, fv in block.get("fields", {}).items():
                if fn == "ulen_sequences":
                    found = True
                    self.assertTrue(
                        fv.get("correct", False),
                        f"ulen_sequences falsely reported as incorrect: "
                        f"value={fv.get('value')}, actual={fv.get('actual')}, "
                        f"msg={fv.get('message','')}",
                    )
        self.assertTrue(found, "ulen_sequences field missing from validation output")

    def test_validator_overall_valid_for_good_file(self):
        """A correctly-encoded BGFA file should pass validation.

        Uses example_1.gfa (no paths) to isolate Bug 1 from Bug 2.
        """
        bgfa = self._bgfa_path()
        g = GFA.from_gfa("data/example_1.gfa")
        g.to_bgfa(bgfa, block_size=1024)

        result = validate_bgfa(bgfa)
        if not result.get("valid", True):
            errors = []
            for b in result.get("blocks", []):
                for fn, fv in b.get("fields", {}).items():
                    if not fv.get("correct", True):
                        errors.append(
                            f"b{b['block_index']}{b.get('section_type','?')}.{fn}: "
                            f"{fv.get('message', fv.get('error','?'))}"
                        )
            self.fail(f"Validation failed for a correct file: {'; '.join(errors)}")


class TestValidatorPathsBlockConsumption(unittest.TestCase):
    """Bug 2: validate_bgfa paths block consumption misses walk payload."""

    def setUp(self):
        # example_3 has a path, so the paths block has walk data that might be missed
        self.gfa_path = "data/example_3.gfa"
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

    def test_no_phantom_blocks_after_paths(self):
        """Bug 2: validate_bgfa should not create phantom truncated blocks."""
        bgfa = self._bgfa_path()
        g = GFA.from_gfa(self.gfa_path)
        g.to_bgfa(bgfa, block_size=1024)

        result = validate_bgfa(bgfa)
        blocks = result.get("blocks", [])

        # Expected blocks: segments(1) + links(1) + paths(1) + opt_fields(1) = 4
        expected = 4
        actual = len(blocks)
        self.assertLessEqual(
            actual, expected,
            f"Expected ≤{expected} blocks, got {actual}: "
            f"phantom blocks detected (paths block consumption bug). "
            f"Block types: {[b.get('section_type','?') for b in blocks]}",
        )

        # No block should have "Truncated" errors
        for b in blocks:
            for fn, fv in b.get("fields", {}).items():
                if fv.get("error") == "Truncated":
                    self.fail(
                        f"Block {b['block_index']} {b.get('section_type','?')} "
                        f"field {fn} is Truncated — this indicates the previous "
                        f"block's consumption calculation was wrong."
                    )


class TestOptFieldTypePreservation(unittest.TestCase):
    """Bug 3: GFA parser discards opt field value type information."""

    def test_parser_preserves_integer_opt_field_type(self):
        """Parsing a segment with LN:i:6871 should preserve type information."""
        gfa_content = (
            "H\tVN:Z:1.0\n"
            "S\t1\tACCTT\tLN:i:100\tRC:i:42\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".gfa", delete=False) as f:
            f.write(gfa_content)
            tmp_gfa = f.name

        try:
            g = GFA.from_gfa(tmp_gfa)
            output = g.to_gfa()
            # The serialized output should contain LN:i:100 and RC:i:42
            self.assertIn("LN:i:100", output, "Integer opt field LN should be type i")
            self.assertIn("RC:i:42", output, "Integer opt field RC should be type i")
        finally:
            os.unlink(tmp_gfa)

    def test_parser_preserves_string_opt_field_type(self):
        """Parsing a link with ID:Z:xyz should preserve type information."""
        gfa_content = (
            "H\tVN:Z:1.0\n"
            "S\t1\tACCTT\n"
            "S\t2\tGGCCA\n"
            "L\t1\t+\t2\t+\t10M\tID:Z:my_link\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".gfa", delete=False) as f:
            f.write(gfa_content)
            tmp_gfa = f.name

        try:
            g = GFA.from_gfa(tmp_gfa)
            output = g.to_gfa()
            self.assertIn("ID:Z:my_link", output, "String opt field ID should be type Z")
        finally:
            os.unlink(tmp_gfa)

    def test_parser_preserves_float_opt_field_type(self):
        """Parsing a segment with GC:f:1.5 should preserve type information."""
        gfa_content = (
            "H\tVN:Z:1.0\n"
            "S\t1\tACCTT\tGC:f:1.5\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".gfa", delete=False) as f:
            f.write(gfa_content)
            tmp_gfa = f.name

        try:
            g = GFA.from_gfa(tmp_gfa)
            output = g.to_gfa()
            self.assertIn("GC:f:1.5", output, "Float opt field GC should be type f")
        finally:
            os.unlink(tmp_gfa)


class TestBGFARoundtripOptFields(unittest.TestCase):
    """Bug 4: BGFA roundtrip loses all opt fields on segments."""

    def setUp(self):
        self._tmp_files = []

    def tearDown(self):
        for p in self._tmp_files:
            try:
                os.unlink(p)
            except OSError:
                pass

    def _make_temp(self, suffix):
        fd, path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        self._tmp_files.append(path)
        return path

    def test_bgfa_roundtrip_preserves_segment_opt_fields(self):
        """BGFA roundtrip should preserve opt fields on segments."""
        gfa_content = (
            "H\tVN:Z:1.0\n"
            "S\t1\tACCTT\tLN:i:100\tRC:i:42\tAB:Z:test\n"
            "S\t2\tGGCCA\tLN:i:200\n"
            "L\t1\t+\t2\t+\t10M\n"
        )
        tmp_gfa = self._make_temp(".gfa")
        with open(tmp_gfa, "w") as f:
            f.write(gfa_content)

        tmp_bgfa = self._make_temp(".bgfa")

        g = GFA.from_gfa(tmp_gfa)
        g.to_bgfa(tmp_bgfa, block_size=1024)

        h = GFA.from_bgfa(tmp_bgfa)
        output = h.to_gfa()

        # Check that opt fields survived the roundtrip
        for line in output.splitlines():
            if line.startswith("S\t1\t"):
                self.assertIn("LN:i:100", line,
                              "Opt field LN:i:100 lost in BGFA roundtrip")
                self.assertIn("RC:i:42", line,
                              "Opt field RC:i:42 lost in BGFA roundtrip")
                self.assertIn("AB:Z:test", line,
                              "Opt field AB:Z:test lost in BGFA roundtrip")
                break
        else:
            self.fail("Segment 1 not found in roundtripped GFA")

    def test_bgfa_roundtrip_preserves_link_opt_fields(self):
        """BGFA roundtrip should preserve opt fields on links."""
        gfa_content = (
            "H\tVN:Z:1.0\n"
            "S\t1\tACCTT\n"
            "S\t2\tGGCCA\n"
            "L\t1\t+\t2\t+\t10M\tID:Z:my_link\tNM:i:5\n"
        )
        tmp_gfa = self._make_temp(".gfa")
        with open(tmp_gfa, "w") as f:
            f.write(gfa_content)

        tmp_bgfa = self._make_temp(".bgfa")

        g = GFA.from_gfa(tmp_gfa)
        g.to_bgfa(tmp_bgfa, block_size=1024)

        h = GFA.from_bgfa(tmp_bgfa)
        output = h.to_gfa()

        link_found = False
        for line in output.splitlines():
            if line.startswith("L\t1\t"):
                self.assertIn("ID:Z:my_link", line,
                              "Opt field ID:Z:my_link lost in BGFA roundtrip")
                self.assertIn("NM:i:5", line,
                              "Opt field NM:i:5 lost in BGFA roundtrip")
                link_found = True
                break
        self.assertTrue(link_found, "Link not found in roundtripped GFA")

    def test_bool_opt_field_roundtrip(self):
        """A bool opt field must not crash the BGFA roundtrip (bool is an int subclass)."""
        from pygfa.graph_element.node import Node

        g = GFA()
        g.add_node(Node("1", "ACCTT", 5, opt_fields={"FLAG": True}))

        tmp_bgfa = self._make_temp(".bgfa")
        g.to_bgfa(tmp_bgfa, block_size=1024)

        h = GFA.from_bgfa(tmp_bgfa)
        output = h.to_gfa()
        self.assertIn("FLAG:Z:True", output, "Bool opt field should round-trip as Z")

    def test_no_opt_fields_block_when_empty(self):
        """A graph with no opt fields must not emit a section-6 block."""
        gfa_content = (
            "H\tVN:Z:1.0\n"
            "S\t1\tACCTT\n"
            "S\t2\tGGCCA\n"
            "L\t1\t+\t2\t+\t10M\n"
        )
        tmp_gfa = self._make_temp(".gfa")
        with open(tmp_gfa, "w") as f:
            f.write(gfa_content)

        tmp_bgfa = self._make_temp(".bgfa")
        g = GFA.from_gfa(tmp_gfa)
        g.to_bgfa(tmp_bgfa, block_size=1024)

        result = validate_bgfa(tmp_bgfa)
        for block in result.get("blocks", []):
            self.assertNotEqual(
                block.get("section_type"), "opt_fields",
                "No opt_fields block should be emitted when no element has opt fields",
            )

    def test_read_bgfa_without_opt_fields_block(self):
        """Reading a BGFA file without an opt_fields block yields empty opt fields."""
        gfa_content = (
            "H\tVN:Z:1.0\n"
            "S\t1\tACCTT\n"
            "S\t2\tGGCCA\n"
            "L\t1\t+\t2\t+\t10M\n"
        )
        tmp_gfa = self._make_temp(".gfa")
        with open(tmp_gfa, "w") as f:
            f.write(gfa_content)

        tmp_bgfa = self._make_temp(".bgfa")
        g = GFA.from_gfa(tmp_gfa)
        g.to_bgfa(tmp_bgfa, block_size=1024)

        h = GFA.from_bgfa(tmp_bgfa)
        for _nid, data in h.nodes(data=True):
            # Reader expands opt fields into the attr dict; with no opt-fields
            # block there must be no extra keys beyond the core node attributes.
            self.assertEqual(set(data), {"nid", "sequence", "slen"})
        for _u, _v, _k, data in h.edges(data=True, keys=True):
            self.assertNotIn("NM", data)
            self.assertNotIn("ID", data)

    def test_opt_fields_multi_block_links(self):
        """Link opt fields survive a roundtrip when links span multiple blocks."""
        lines = ["H\tVN:Z:1.0", "S\t1\tACCTT", "S\t2\tGGCCA"]
        for i in range(50):
            lines.append(f"L\t1\t+\t2\t+\t10M\tNM:i:{i}")
        gfa_content = "\n".join(lines) + "\n"

        tmp_gfa = self._make_temp(".gfa")
        with open(tmp_gfa, "w") as f:
            f.write(gfa_content)

        tmp_bgfa = self._make_temp(".bgfa")
        g = GFA.from_gfa(tmp_gfa)
        g.to_bgfa(tmp_bgfa, block_size=8)

        h = GFA.from_bgfa(tmp_bgfa)
        output = h.to_gfa()
        for i in range(50):
            self.assertIn(f"NM:i:{i}", output, f"Link opt field NM:i:{i} lost in roundtrip")


class TestBGFARoundtripPathWalkOptFields(unittest.TestCase):
    """Bug 4 residual: opt fields on paths and walks must survive a BGFA roundtrip."""

    def setUp(self):
        self._tmp_files = []

    def tearDown(self):
        for p in self._tmp_files:
            try:
                os.unlink(p)
            except OSError:
                pass

    def _make_temp(self, suffix):
        fd, path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        self._tmp_files.append(path)
        return path

    def test_path_opt_fields_roundtrip(self):
        """Opt fields on P lines must survive GFA -> BGFA -> GFA."""
        gfa_content = (
            "H\tVN:Z:1.0\n"
            "S\t1\tACCTT\n"
            "S\t2\tGGCCA\n"
            "P\tp1\t1+,2+\t10M\tXX:Z:foo\tYY:i:7\n"
        )
        tmp_gfa = self._make_temp(".gfa")
        with open(tmp_gfa, "w") as f:
            f.write(gfa_content)

        tmp_bgfa = self._make_temp(".bgfa")
        g = GFA.from_gfa(tmp_gfa)
        g.to_bgfa(tmp_bgfa, block_size=1024)

        h = GFA.from_bgfa(tmp_bgfa)
        p = h.paths("p1")
        self.assertIsNotNone(p)
        self.assertEqual(p.get("XX"), "foo")
        self.assertEqual(p.get("YY"), 7)
        output = h.to_gfa()
        self.assertIn("XX:Z:foo", output)
        self.assertIn("YY:i:7", output)

    def test_walk_opt_fields_roundtrip(self):
        """Opt fields on W lines must survive GFA -> BGFA -> GFA."""
        gfa_content = (
            "H\tVN:Z:1.0\n"
            "S\t1\tACCTT\n"
            "S\t2\tGGCCA\n"
            "W\tsample1\t0\tchr1\t0\t10\t>1>2\tZZ:Z:bar\tNN:f:1.5\n"
        )
        tmp_gfa = self._make_temp(".gfa")
        with open(tmp_gfa, "w") as f:
            f.write(gfa_content)

        tmp_bgfa = self._make_temp(".bgfa")
        g = GFA.from_gfa(tmp_gfa)
        g.to_bgfa(tmp_bgfa, block_size=1024)

        h = GFA.from_bgfa(tmp_bgfa)
        w = h.walks("sample1_0_chr1")
        self.assertIsNotNone(w)
        self.assertEqual(w.get("ZZ"), "bar")
        self.assertEqual(w.get("NN"), 1.5)
        output = h.to_gfa()
        self.assertIn("ZZ:Z:bar", output)
        self.assertIn("NN:f:1.5", output)

    def test_no_block_when_only_path_walk_opts_absent(self):
        """A graph whose paths/walks carry no opt fields must not emit a section-6 block."""
        gfa_content = (
            "H\tVN:Z:1.0\n"
            "S\t1\tACCTT\n"
            "S\t2\tGGCCA\n"
            "P\tp1\t1+,2+\t10M\n"
            "W\tsample1\t0\tchr1\t0\t10\t>1>2\n"
        )
        tmp_gfa = self._make_temp(".gfa")
        with open(tmp_gfa, "w") as f:
            f.write(gfa_content)

        tmp_bgfa = self._make_temp(".bgfa")
        g = GFA.from_gfa(tmp_gfa)
        g.to_bgfa(tmp_bgfa, block_size=1024)

        result = validate_bgfa(tmp_bgfa)
        for block in result.get("blocks", []):
            self.assertNotEqual(
                block.get("section_type"), "opt_fields",
                "No opt_fields block should be emitted when no element has opt fields",
            )


class TestDumpValidation(unittest.TestCase):
    """Bug 5: dump_bgfa's validate_field is a no-op (compares value against itself)."""

    def setUp(self):
        self._tmp_files = []

    def tearDown(self):
        for p in self._tmp_files:
            try:
                os.unlink(p)
            except OSError:
                pass

    def _make_temp(self, suffix):
        fd, path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        self._tmp_files.append(path)
        return path

    def test_dump_does_not_crash(self):
        """dump_bgfa should produce valid output without errors."""
        tmp_gfa = self._make_temp(".gfa")
        with open(tmp_gfa, "w") as f:
            f.write("H\tVN:Z:1.0\nS\t1\tACCTT\n")

        tmp_bgfa = self._make_temp(".bgfa")

        g = GFA.from_gfa(tmp_gfa)
        g.to_bgfa(tmp_bgfa, block_size=1024)

        # dump_bgfa should run without error
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            dump_bgfa(tmp_bgfa)
        output = f.getvalue()
        self.assertTrue(len(output) > 0, "dump_bgfa produced no output")
        # Should be valid JSON
        parsed = json.loads(output)
        self.assertIn("header", parsed)
        self.assertIn("blocks", parsed)

    def test_dump_validate_field_detects_corruption(self):
        """Bug 5: dump_bgfa's validate_field should detect when stored length differs from actual.

        Currently validate_field compares a value against itself, so it never
        detects corruption. This test verifies the fix by corrupting a BGFA file
        and checking that dump_bgfa reports an error for the corrupted field.
        """
        tmp_gfa = self._make_temp(".gfa")
        with open(tmp_gfa, "w") as f:
            f.write("H\tVN:Z:1.0\nS\t1\tACCTT\nS\t2\tGGCCA\nL\t1\t+\t2\t+\t10M\n")

        tmp_bgfa = self._make_temp(".bgfa")

        g = GFA.from_gfa(tmp_gfa)
        g.to_bgfa(tmp_bgfa, block_size=1024)

        # Read the BGFA file and corrupt the clen_names field
        with open(tmp_bgfa, "rb") as f:
            data = bytearray(f.read())

        # Find the segments block (section_id=2) and corrupt clen_names
        # Header: magic(4) + version(2) + hdr_len(2) + hdr_text + null(1)
        hdr_len = int.from_bytes(data[6:8], "little")
        offset = 8 + hdr_len + 1  # skip to first block

        if data[offset] == 2:  # SECTION_ID_SEGMENTS
            # clen_names is at offset+5 (after section_id(1) + record_num(2) + comp_names(2))
            # It's an 8-byte uint64. Set it to a wrong value.
            import struct
            wrong_clen = 99999
            struct.pack_into("<Q", data, offset + 5, wrong_clen)

            with open(tmp_bgfa, "wb") as f:
                f.write(data)

        # Now dump — should detect the corruption in the field
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            dump_bgfa(tmp_bgfa)
        output = f.getvalue()
        parsed = json.loads(output)

        # Find the segments block and check for error in clen_names field
        found_error = False
        for block in parsed.get("blocks", []):
            if block.get("section_type") == "segments":
                fields = block.get("fields", {})
                # Check both possible field names (the dump uses verbose names)
                for field_name in ["compressed_segment_names_length_bytes", "compressed_segment_names_length"]:
                    field_data = fields.get(field_name, {})
                    if "error" in field_data:
                        found_error = True
                        break
                if found_error:
                    break

        self.assertTrue(
            found_error,
            "dump_bgfa should report an error when clen_names is corrupted, "
            "but no error was found in the segments block fields",
        )

    def test_dump_valid_file_no_field_errors(self):
        """A valid multi-block BGFA file's dump must contain no field errors."""
        gfa_content = (
            "H\tVN:Z:1.0\n"
            "S\t1\tACCTT\n"
            "S\t2\tGGCCA\n"
            "S\t3\tTTGCA\n"
            "L\t1\t+\t2\t+\t10M\n"
            "L\t2\t+\t3\t+\t10M\n"
            "P\tp1\t1+,2+,3+\t10M,10M\n"
        )
        tmp_gfa = self._make_temp(".gfa")
        with open(tmp_gfa, "w") as f:
            f.write(gfa_content)

        tmp_bgfa = self._make_temp(".bgfa")
        g = GFA.from_gfa(tmp_gfa)
        g.to_bgfa(tmp_bgfa, block_size=1024)

        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            dump_bgfa(tmp_bgfa)
        parsed = json.loads(f.getvalue())

        errors = []
        for block in parsed.get("blocks", []):
            for field_name, field_data in block.get("fields", {}).items():
                if "error" in field_data:
                    errors.append(f"{block.get('section_type','?')}.{field_name}: {field_data['error']}")
        self.assertEqual(errors, [], f"Valid file produced dump field errors: {errors}")

    def test_dump_does_not_crash_on_corrupted_clen(self):
        """dump_bgfa must not crash when a block's clen is corrupted past EOF."""
        tmp_gfa = self._make_temp(".gfa")
        with open(tmp_gfa, "w") as f:
            f.write("H\tVN:Z:1.0\nS\t1\tACCTT\nS\t2\tGGCCA\nL\t1\t+\t2\t+\t10M\n")

        tmp_bgfa = self._make_temp(".bgfa")
        g = GFA.from_gfa(tmp_gfa)
        g.to_bgfa(tmp_bgfa, block_size=1024)

        with open(tmp_bgfa, "rb") as f:
            data = bytearray(f.read())

        # Corrupt the links block clen_cigars to a value past EOF.
        # Links block: section_id(1) + record_num(2) + comp_fromto(1) +
        # clen_fromto(8) + comp_cigars(4) + clen_cigars(8) + ulen_cigars(8).
        offset = _links_block_offset(data)
        struct.pack_into("<Q", data, offset + 16, 99999)
        self.assertEqual(
            struct.unpack_from("<Q", data, offset + 16)[0], 99999,
            "Failed to corrupt links block clen_cigars",
        )
        with open(tmp_bgfa, "wb") as f:
            f.write(data)

        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            dump_bgfa(tmp_bgfa)  # must not raise
        parsed = json.loads(f.getvalue())

        # The corrupted links block should carry an error (either the field
        # bounds check or the parse failure), not crash the dump.
        links_blocks = [b for b in parsed.get("blocks", []) if b.get("section_type") == "links"]
        self.assertTrue(links_blocks, "No links block in dump output")
        has_error = any(
            "error" in b
            or any("error" in fv for fv in b.get("fields", {}).values())
            for b in links_blocks
        )
        self.assertTrue(has_error, "Corrupted links block should report an error in the dump")

    def test_dump_does_not_crash_on_truncated_header(self):
        """dump_bgfa must not crash when a block header is truncated mid-parse."""
        tmp_gfa = self._make_temp(".gfa")
        with open(tmp_gfa, "w") as f:
            f.write("H\tVN:Z:1.0\nS\t1\tACCTT\nS\t2\tGGCCA\nL\t1\t+\t2\t+\t10M\n")

        tmp_bgfa = self._make_temp(".bgfa")
        g = GFA.from_gfa(tmp_gfa)
        g.to_bgfa(tmp_bgfa, block_size=1024)

        with open(tmp_bgfa, "rb") as f:
            data = bytearray(f.read())

        # Truncate the file in the middle of the links block header.
        links_start = _links_block_offset(data)
        # Keep only section_id + record_num + comp_fromto (4 bytes) of the links header.
        truncated = data[: links_start + 4]

        tmp_trunc = self._make_temp(".bgfa")
        with open(tmp_trunc, "wb") as f:
            f.write(truncated)

        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            dump_bgfa(tmp_trunc)  # must not raise
        parsed = json.loads(f.getvalue())

        # The truncated links block should carry an error, not crash the dump.
        links_blocks = [b for b in parsed.get("blocks", []) if b.get("section_type") == "links"]
        self.assertTrue(links_blocks, "No links block in dump output")
        self.assertTrue(
            any("error" in b for b in links_blocks),
            "Truncated links block should report an error in the dump",
        )


class TestOptFieldParsing(unittest.TestCase):
    """parse_opt_fields should reject malformed payloads with a clear error."""

    def test_malformed_payload_raises(self):
        from pygfa.bgfa._codec_utils import parse_opt_fields

        with self.assertRaises(ValueError):
            parse_opt_fields("TAG:i:notanint")

    def test_malformed_field_structure_raises(self):
        from pygfa.bgfa._codec_utils import parse_opt_fields

        with self.assertRaises(ValueError):
            parse_opt_fields("no_colons_here")

    def test_valid_payload_parses(self):
        from pygfa.bgfa._codec_utils import parse_opt_fields

        result = parse_opt_fields("LN:i:100\tGC:f:1.5\tAB:Z:test")
        self.assertEqual(result, {"LN": 100, "GC": 1.5, "AB": "test"})


class TestValidatorLinksBlockConsumption(unittest.TestCase):
    """Verify that links block consumption is correctly calculated."""

    def setUp(self):
        self._tmp_files = []

    def tearDown(self):
        for p in self._tmp_files:
            try:
                os.unlink(p)
            except OSError:
                pass

    def _make_temp(self, suffix):
        fd, path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        self._tmp_files.append(path)
        return path

    def test_links_block_consumption_no_phantom_blocks(self):
        """File with only segments+links should have exactly 2 blocks."""
        gfa_content = (
            "H\tVN:Z:1.0\n"
            "S\t1\tACCTT\n"
            "S\t2\tGGCCA\n"
            "L\t1\t+\t2\t+\t10M\n"
        )
        tmp_gfa = self._make_temp(".gfa")
        with open(tmp_gfa, "w") as f:
            f.write(gfa_content)

        tmp_bgfa = self._make_temp(".bgfa")

        g = GFA.from_gfa(tmp_gfa)
        g.to_bgfa(tmp_bgfa, block_size=1024)

        result = validate_bgfa(tmp_bgfa)
        blocks = result.get("blocks", [])

        # No opt fields in this file, so the opt_fields block is skipped:
        # segments(1) + links(1) = 2 blocks
        self.assertEqual(
            len(blocks), 2,
            f"Expected 2 blocks (segments+links), got {len(blocks)}. "
            f"Types: {[b.get('section_type','?') for b in blocks]}"
        )


class TestLinksFromtoSingleByte(unittest.TestCase):
    """``compression_fromto`` is a single byte holding the integer encoding.

    Per the BGFA spec the links block header is::

        section_id(1) record_num(2) compression_fromto(1)
        clen_fromto(8) comp_cigars(4) clen_cigars(8) ulen_cigars(8)
    """

    def setUp(self):
        self._tmp_files = []

    def tearDown(self):
        for p in self._tmp_files:
            try:
                os.unlink(p)
            except OSError:
                pass

    def _make_temp(self, suffix):
        fd, path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        self._tmp_files.append(path)
        return path

    def _write_bgfa(self, n_links=4, **options):
        """Write a segments+links BGFA file and return its bytes."""
        tmp_gfa = self._make_temp(".gfa")
        with open(tmp_gfa, "w") as f:
            f.write("H\tVN:Z:1.0\n")
            for i in range(1, n_links + 2):
                f.write(f"S\ts{i}\tACGT\n")
            for i in range(1, n_links + 1):
                f.write(f"L\ts{i}\t+\ts{i + 1}\t+\t4M\n")

        tmp_bgfa = self._make_temp(".bgfa")
        g = GFA.from_gfa(tmp_gfa)
        g.to_bgfa(tmp_bgfa, block_size=1024, use_heuristic=False, **options)
        with open(tmp_bgfa, "rb") as f:
            return f.read(), tmp_bgfa

    def test_compression_fromto_is_one_byte(self):
        """The field is one byte and holds the integer encoding value."""
        for name, expected in [
            ("none+none", IntegerEncoding.NONE),
            ("varint+none", IntegerEncoding.VARINT),
            ("vbyte+none", IntegerEncoding.VBYTE),
            ("bit_packing+none", IntegerEncoding.BIT_PACKING),
        ]:
            with self.subTest(encoding=name):
                data, _ = self._write_bgfa(link_endpoints_enc=name)
                offset = _links_block_offset(data)
                self.assertEqual(
                    struct.unpack_from("<B", data, offset + 3)[0],
                    int(expected),
                    f"compression_fromto byte mismatch for {name}",
                )

    def test_clen_fromto_follows_the_single_byte(self):
        """clen_fromto sits at offset+4 and the header is 32 bytes long."""
        data, _ = self._write_bgfa(link_endpoints_enc="varint+none")
        offset = _links_block_offset(data)
        clen_fromto = struct.unpack_from("<Q", data, offset + 4)[0]
        clen_cigars = struct.unpack_from("<Q", data, offset + 16)[0]
        self.assertGreater(clen_fromto, 0)
        self.assertGreater(clen_cigars, 0)
        # section_id(1)+record_num(2)+comp_fromto(1)+clen_fromto(8)
        # +comp_cigars(4)+clen_cigars(8)+ulen_cigars(8) == 32 bytes of header.
        self.assertLessEqual(offset + 32 + clen_fromto + clen_cigars, len(data))

    def test_roundtrip_every_integer_encoding(self):
        """Every integer encoding roundtrips the link endpoints."""
        for enc in IntegerEncoding:
            with self.subTest(encoding=enc.name):
                data, tmp_bgfa = self._write_bgfa(link_endpoints_enc=f"{enc.name.lower()}+none")
                offset = _links_block_offset(data)
                self.assertEqual(struct.unpack_from("<B", data, offset + 3)[0], int(enc))
                h = GFA.from_bgfa(tmp_bgfa)
                links = {
                    (d.get("from_node", u), d.get("to_node", v), d.get("alignment", "*"))
                    for u, v, d in h.edges(data=True)
                }
                self.assertEqual(
                    links,
                    {(f"s{i}", f"s{i + 1}", "4M") for i in range(1, 5)},
                    f"Link roundtrip failed for {enc.name}",
                )

    def test_validate_reports_single_byte_code(self):
        """validate_bgfa reports the bare integer encoding byte."""
        _, tmp_bgfa = self._write_bgfa(link_endpoints_enc="bit_packing+none")
        result = validate_bgfa(tmp_bgfa)
        links_blocks = [b for b in result["blocks"] if b.get("section_type") == "links"]
        self.assertTrue(links_blocks, "No links block in validation output")
        self.assertEqual(links_blocks[0]["fields"]["comp_fromto"]["value"], 0x0F)

    def test_dump_describes_single_byte_code(self):
        """dump_bgfa describes the field as a bare integer encoding."""
        _, tmp_bgfa = self._write_bgfa(link_endpoints_enc="bit_packing+none")
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            dump_bgfa(tmp_bgfa)
        parsed = json.loads(f.getvalue())
        links_blocks = [b for b in parsed["blocks"] if b.get("section_type") == "links"]
        self.assertTrue(links_blocks, "No links block in dump output")
        field = links_blocks[0]["fields"]["link_endpoints_compression_code"]
        self.assertEqual(field["value"], "0x0F")
        self.assertEqual(field["description"], "bit packing")

    def test_show_full_encodings_uses_fromto_key(self):
        """The compression option is named ``compression_fromto``."""
        from pygfa.encoding import show_full_encodings

        encodings = show_full_encodings()
        self.assertIn("compression_fromto", encodings)
        self.assertNotIn("compression_from", encodings)
        self.assertNotIn("compression_to", encodings)
        self.assertIn("varint", encodings["compression_fromto"])

    def test_string_encoding_for_integer_only_field_raises(self):
        """A string encoding for the integer-only fromto field is rejected."""
        for bad in ("none+huffman", "huffman", "varint+zstd"):
            with self.subTest(encoding=bad):
                with self.assertRaises(InvalidEncodingError):
                    self._write_bgfa(link_endpoints_enc=bad)


if __name__ == "__main__":
    unittest.main()
