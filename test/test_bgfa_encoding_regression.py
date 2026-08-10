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
from pygfa.gfa import GFA


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
        # Links block: section_id(1) + record_num(2) + comp_fromto(2) +
        # clen_fromto(8) + comp_cigars(4) + clen_cigars(8) + ulen_cigars(8).
        import struct
        hdr_len = int.from_bytes(data[6:8], "little")
        offset = 8 + hdr_len + 1
        # Skip the segments block (section_id=2) to reach the links block.
        # Segments header: section(1)+record(2)+comp_names(2)+clen_names(8)+
        # ulen_names(8)+comp_str(2)+clen_str(8)+ulen_str(8) = 39 bytes.
        if data[offset] == 2:
            clen_names = struct.unpack_from("<Q", data, offset + 5)[0]
            clen_str = struct.unpack_from("<Q", data, offset + 23)[0]
            offset += 39 + clen_names + clen_str
        if data[offset] != 3:
            self.fail(f"Expected a links block (section_id=3) at offset {offset}, got {data[offset]}")
        struct.pack_into("<Q", data, offset + 17, 99999)
        self.assertEqual(
            struct.unpack_from("<Q", data, offset + 17)[0], 99999,
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
        hdr_len = int.from_bytes(data[6:8], "little")
        seg_start = 8 + hdr_len + 1
        clen_names = struct.unpack_from("<Q", data, seg_start + 5)[0]
        clen_str = struct.unpack_from("<Q", data, seg_start + 23)[0]
        links_start = seg_start + 39 + clen_names + clen_str
        # Keep only section_id + record_num + comp_fromto (5 bytes) of the links header.
        truncated = data[: links_start + 5]

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


if __name__ == "__main__":
    unittest.main()
