"""Test BGFA path and walk parsing functionality.

These tests verify that paths and walks parsing is implemented and functional.
"""

import os
import sys
import unittest
import tempfile
import struct

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pygfa.bgfa import ReaderBGFA, compress_integer_list_varint
from pygfa.gfa import GFA


class TestBGFAPathWalkParsing(unittest.TestCase):
    """Test BGFA path and walk parsing functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.reader = ReaderBGFA()

    def test_decompress_string_list_empty(self):
        """Test string list decompression with empty data."""
        result = self.reader._decompress_string_list(b"", 0x0000, 0)
        self.assertEqual(result, [])

    def test_parse_paths_blocks_basic(self):
        """Test basic paths block parsing with minimal data."""
        # Create a minimal paths block
        test_names = ["path1"]
        test_cigars = ["100M"]

        names_data = b"".join([s.encode("ascii") for s in test_names])
        cigars_data = b"".join([s.encode("ascii") for s in test_cigars])
        names_metadata = compress_integer_list_varint([len(s) for s in test_names])
        cigars_metadata = compress_integer_list_varint([len(s) for s in test_cigars])

        # Header format: section_id(B) + record_num(H) + comp_names(H) + comp_paths(I) +
        #                comp_cigars(H) + clen_cigars(Q) + ulen_cigars(Q) + clen_names(Q) + ulen_names(Q)
        header = struct.pack(
            "<BHHIHQQQQ",
            4,  # section_id
            1,  # record_num
            0x0100,  # compression_path_names
            0x00000000,  # compression_paths (empty walks)
            0x0100,  # compression_cigars
            len(cigars_metadata) + len(cigars_data),
            len(cigars_data),
            len(names_metadata) + len(names_data),
            len(names_data),
        )

        bgfa_data = header + names_metadata + names_data + cigars_metadata + cigars_data
        paths, bytes_read = self.reader._parse_paths_blocks(bgfa_data, 0, [])

        self.assertEqual(len(paths), 1)
        self.assertEqual(paths[0]["path_name"], "path1")

    def test_parse_walks_blocks_basic(self):
        """Test basic walks block parsing with minimal data."""
        test_samples = ["sample1"]
        test_sequences = ["seq1"]
        test_hap_indices = [0]
        test_starts = [100]
        test_ends = [500]

        samples_data = b"".join([s.encode("ascii") for s in test_samples])
        sequences_data = b"".join([s.encode("ascii") for s in test_sequences])
        samples_metadata = compress_integer_list_varint([len(s) for s in test_samples])
        sequences_metadata = compress_integer_list_varint([len(s) for s in test_sequences])

        hep_data = compress_integer_list_varint(test_hap_indices)
        starts_data = compress_integer_list_varint(test_starts)
        ends_data = compress_integer_list_varint(test_ends)
        positions_data = starts_data + ends_data

        # Header format per spec (grouped layout):
        # section_id(B) + record_num(H) + 4x compression(H) + comp_walks(I) +
        # 5x (clen(Q) + ulen(Q)) for samples/hep/seq/positions/walks
        # Total: 1 + 2 + 12 + 80 = 95 bytes
        header = struct.pack(
            "<BHHHHHIQQQQQQQQQQ",
            5,  # section_id
            1,  # record_num
            0x0100,  # compression_samples
            0x0100,  # compression_hep
            0x0100,  # compression_sequence
            0x0100,  # compression_positions
            0x00000000,  # compression_walks (empty)
            len(samples_metadata) + len(samples_data),  # clen_samples
            len(samples_data),  # ulen_samples
            len(hep_data),  # clen_hep
            len(hep_data),  # ulen_hep
            len(sequences_metadata) + len(sequences_data),  # clen_sequence
            len(sequences_data),  # ulen_sequence
            len(positions_data),  # clen_positions
            len(positions_data),  # ulen_positions
            0,  # clen_walks
            0,  # ulen_walks
        )

        bgfa_data = (
            header + samples_metadata + samples_data + hep_data + sequences_metadata + sequences_data + positions_data
        )
        walks, bytes_read = self.reader._parse_walks_blocks(bgfa_data, 0, [])

        self.assertEqual(len(walks), 1)
        self.assertEqual(walks[0]["sample_id"], "sample1")
        self.assertEqual(walks[0]["sequence_id"], "seq1")
        self.assertEqual(walks[0]["haplotype_index"], 0)

    def test_bgfa_reader_integration(self):
        """Test BGFA reader integration with paths and walks sections."""
        output_dir = tempfile.mkdtemp()

        with tempfile.NamedTemporaryFile(delete=False, dir=output_dir) as tmp_file:
            # Write BGFA header
            magic = 0x41464742
            version = 1
            header_text = "test"
            header_len = len(header_text)

            tmp_file.write(struct.pack("<IHH", magic, version, header_len))
            tmp_file.write(header_text.encode("ascii") + b"\0")

            # Write empty segment names block
            tmp_file.write(struct.pack("<BHHQQ", 1, 0, 0x0000, 0, 0))

            # Write empty segments block
            tmp_file.write(struct.pack("<BHHQQ", 2, 0, 0x0000, 0, 0))

            # Write empty paths block
            tmp_file.write(struct.pack("<BHHIHQQQQ", 4, 0, 0x0000, 0x00000000, 0x0000, 0, 0, 0, 0))

            # Write empty walks block
            tmp_file.write(
                struct.pack(
                    "<BHHHHHIQQQQQQQQQQ", 5, 0, 0x0000, 0x0000, 0x0000, 0x0000, 0x00000000, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
                )
            )

            tmp_file_path = tmp_file.name

        try:
            gfa = self.reader.read_bgfa(tmp_file_path)
            self.assertIsInstance(gfa, GFA)
            self.assertEqual(gfa._header_info["version"], 1)
        finally:
            os.unlink(tmp_file_path)
            import shutil

            shutil.rmtree(output_dir, ignore_errors=True)

    def test_decode_walk_empty(self):
        """Test walk decoding with empty data."""
        result = self.reader._decode_walk(b"", 0, 0, lambda x, y: ([], 0), [])
        self.assertEqual(result, [])

    def test_decode_walk_no_compression(self):
        """Test walk decoding with no compression (compression=0)."""
        result = self.reader._decode_walk(b"", 2, 0, lambda x, y: ([], 0), [])
        self.assertEqual(result, [[], []])  # Two empty walks


if __name__ == "__main__":
    unittest.main()
