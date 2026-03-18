import unittest
from pygfa.bgfa import ReaderBGFA
import struct
import tempfile
import os


class TestBGFAHeaderValidation(unittest.TestCase):
    def setUp(self):
        self.reader = ReaderBGFA()

    def create_valid_header(self, version=1, header_text="VN:Z:1.0\n"):
        """Create a valid BGFA header with correct magic number, version, and null terminator."""
        header_len = len(header_text)
        magic_number = 0x41464742  # AFGB

        header_data = struct.pack("<I", magic_number)
        header_data += struct.pack("<H", version)
        header_data += struct.pack("<H", header_len)
        header_data += header_text.encode("ascii")
        header_data += b"\x00"  # null terminator

        return header_data

    def test_valid_header(self):
        """Test a valid BGFA header with correct magic number and structure."""
        header_data = self.create_valid_header()

        # Verify the header can be parsed without errors
        header = self.reader._parse_header(header_data)
        self.assertEqual(header["version"], 1)
        self.assertEqual(header["header_text"], "VN:Z:1.0\n")
        self.assertEqual(header["header_size"], len(header_data))

    def test_missing_magic_number(self):
        """Test header with missing magic number (file too short)."""
        header_data = b""

        with self.assertRaises(struct.error) as context:
            self.reader._parse_header(header_data)
        self.assertIn("requires a buffer of at least", str(context.exception))

    def test_invalid_magic_number(self):
        """Test header with invalid magic number."""
        header_data = self.create_valid_header()
        # Corrupt the magic number by changing first byte
        corrupted_data = b"\x00" + header_data[1:]

        # _parse_header should now validate magic number
        with self.assertRaises(ValueError) as context:
            self.reader._parse_header(corrupted_data)
        self.assertIn("Invalid magic number", str(context.exception))

    def test_missing_null_terminator(self):
        """Test header missing null terminator."""
        header_data = self.create_valid_header()
        # Remove the null terminator
        header_data = header_data[:-1]

        with self.assertRaises(ValueError) as context:
            self.reader._parse_header(header_data)
        self.assertIn("missing null terminator", str(context.exception))

    def test_invalid_header_len(self):
        """Test header with invalid header_len that points beyond file end."""
        # Create valid header but with header_len larger than actual data
        header_data = self.create_valid_header(header_text="VN:Z:1.0")
        # Change header_len to be larger than actual header text
        corrupted_data = bytearray(header_data)
        struct.pack_into("<H", corrupted_data, 6, 100)  # Set invalid header_len

        with self.assertRaises(ValueError) as context:
            self.reader._parse_header(corrupted_data)
        self.assertIn("incomplete", str(context.exception))

    def test_empty_header_text(self):
        """Test header with empty header text (valid case)."""
        header_data = self.create_valid_header(header_text="")

        header = self.reader._parse_header(header_data)
        self.assertEqual(header["header_text"], "")
        self.assertEqual(header["header_size"], 9)  # magic(4) + version(2) + header_len(2) + null terminator(1)

    def test_large_header_text(self):
        """Test header with large header text."""
        large_text = "VN:Z:1.0\n" * 100
        header_data = self.create_valid_header(header_text=large_text)

        header = self.reader._parse_header(header_data)
        self.assertEqual(header["header_text"], large_text)
        self.assertEqual(header["header_size"], 4 + 2 + 2 + len(large_text) + 1)

    def test_version_validation(self):
        """Test different version numbers (validation not strict)."""
        header_data = self.create_valid_header(version=2)

        header = self.reader._parse_header(header_data)
        self.assertEqual(header["version"], 2)

    def test_header_with_special_characters(self):
        """Test header with special characters in header text."""
        special_text = "VN:Z:1.0\nLN:i:100\n\t\n\x01\x02"
        header_data = self.create_valid_header(header_text=special_text)

        header = self.reader._parse_header(header_data)
        self.assertEqual(header["header_text"], special_text)

    def test_header_boundary_conditions(self):
        """Test boundary conditions for header parsing."""
        # Test minimum valid header
        min_header = struct.pack("<I", 0x41464742) + struct.pack("<H", 1) + struct.pack("<H", 0) + b"\x00"
        header = self.reader._parse_header(min_header)
        self.assertEqual(header["header_text"], "")
        self.assertEqual(header["header_size"], 9)

        # Test maximum header length that fits in uint16
        max_text = "A" * 65535
        header_data = (
            struct.pack("<I", 0x41464742)
            + struct.pack("<H", 1)
            + struct.pack("<H", 65535)
            + max_text.encode("ascii")
            + b"\x00"
        )
        header = self.reader._parse_header(header_data)
        self.assertEqual(len(header["header_text"]), 65535)

    def test_integration_with_reader(self):
        """Test that header validation works when reading full BGFA file."""
        # Create a minimal valid BGFA file (only header)
        header_data = self.create_valid_header()

        output_dir = os.path.join("results", "test", "bgfa_header")
        os.makedirs(output_dir, exist_ok=True)

        with tempfile.NamedTemporaryFile(delete=False, dir=output_dir) as temp_file:
            temp_file.write(header_data)
            temp_file_path = temp_file.name

        try:
            # Should succeed with valid header
            gfa = self.reader.read_bgfa(temp_file_path, verbose=False, debug=False)
            self.assertIsNotNone(gfa)
        finally:
            os.unlink(temp_file_path)

        # Test with invalid magic number
        corrupted_data = b"\x00" + header_data[1:]
        with tempfile.NamedTemporaryFile(delete=False, dir=output_dir) as temp_file:
            temp_file.write(corrupted_data)
            temp_file_path = temp_file.name

        try:
            with self.assertRaises(ValueError) as context:
                self.reader.read_bgfa(temp_file_path, verbose=False, debug=False)
            self.assertIn("Invalid magic number", str(context.exception))
        finally:
            os.unlink(temp_file_path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
