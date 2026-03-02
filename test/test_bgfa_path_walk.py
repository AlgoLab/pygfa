import os
import sys
import unittest
import tempfile
import struct

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pygfa.bgfa import ReaderBGFA
from pygfa.gfa import GFA


class TestBGFAPathWalkParsing(unittest.TestCase):
    """Test BGFA path and walk parsing functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.reader = ReaderBGFA()

    def test_decompress_string_list_none(self):
        """Test string list decompression with none encoding."""
        # Create test data: null-terminated strings
        test_strings = ["path1", "path2", "path3"]
        test_data = b"".join([s.encode("ascii") + b"\0" for s in test_strings])

        result = self.reader._decompress_string_list(test_data, 0x0000, len(test_strings))
        self.assertEqual(result, test_strings)

    def test_decompress_string_list_empty(self):
        """Test string list decompression with empty data."""
        result = self.reader._decompress_string_list(b"", 0x0000, 0)
        self.assertEqual(result, [])

    def test_parse_paths_blocks_empty(self):
        """Test parsing empty paths blocks."""
        # Create minimal paths block header with no data
        header = struct.pack(
            "<HHHQQQQ",
            0,  # record_num
            0x0000,  # compression_path_names
            0x0000,  # compression_cigars
            0,  # compressed_len_cigar
            0,  # uncompressed_len_cigar
            0,  # compressed_len_name
            0,  # uncompressed_len_name
        )

        paths, bytes_read = self.reader._parse_paths_blocks(header, {}, [], 0)
        self.assertEqual(paths, [])
        self.assertEqual(bytes_read, 38)  # Expected: 38 bytes (2+2+2+8+8+8+8)

    def test_parse_paths_blocks_with_data(self):
        """Test parsing paths blocks with actual data."""
        # Create test data
        test_names = ["path1", "path2"]
        test_cigars = ["100M", "50M"]

        # Create compressed data (none encoding)
        names_data = b"".join([s.encode("ascii") + b"\0" for s in test_names])
        cigars_data = b"".join([s.encode("ascii") + b"\0" for s in test_cigars])

        # Create paths block header
        header = struct.pack(
            "<HHHQQQQ",
            2,  # record_num
            0x0000,  # compression_path_names
            0x0000,  # compression_cigars
            len(cigars_data),  # compressed_len_cigar
            len(cigars_data),  # uncompressed_len_cigar
            len(names_data),  # compressed_len_name
            len(names_data),  # uncompressed_len_name
        )

        # Combine header and data - cigars first, then names
        bgfa_data = header + cigars_data + names_data

        paths, bytes_read = self.reader._parse_paths_blocks(bgfa_data, {}, [], 0)

        self.assertEqual(len(paths), 2)
        self.assertEqual(paths[0]["name"], "path1")
        self.assertEqual(paths[0]["cigar"], "100M")
        self.assertEqual(paths[1]["name"], "path2")
        self.assertEqual(paths[1]["cigar"], "50M")
        self.assertEqual(bytes_read, len(bgfa_data))

    def test_parse_walks_blocks_empty(self):
        """Test parsing empty walks blocks."""
        # Create minimal walks block header with no data
        header = struct.pack(
            "<HQQQQQQ",
            0,  # record_num
            0,  # compressed_len_sam
            0,  # uncompressed_len_sam
            0,  # compressed_len_seq
            0,  # uncompressed_len_seq
            0,  # compressed_len_walk
            0,  # uncompressed_len_walk
        )

        walks, bytes_read = self.reader._parse_walks_blocks(header, {}, [], 0)
        self.assertEqual(walks, [])
        self.assertEqual(bytes_read, 50)  # Expected: 50 bytes (2+8+8+8+8+8+8)

    def test_parse_walks_blocks_with_data(self):
        """Test parsing walks blocks with actual data."""
        # Create test data
        test_samples = ["sample1", "sample2"]
        test_sequences = ["seq1", "seq2"]
        test_walks = ["walk1", "walk2"]

        # Create compressed data (none encoding)
        samples_data = b"".join([s.encode("ascii") + b"\0" for s in test_samples])
        sequences_data = b"".join([s.encode("ascii") + b"\0" for s in test_sequences])
        walks_data = b"".join([s.encode("ascii") + b"\0" for s in test_walks])

        # Create walks block header
        header = struct.pack(
            "<HQQQQQQ",
            2,  # record_num
            len(samples_data),  # compressed_len_sam
            len(samples_data),  # uncompressed_len_sam
            len(sequences_data),  # compressed_len_seq
            len(sequences_data),  # uncompressed_len_seq
            len(walks_data),  # compressed_len_walk
            len(walks_data),  # uncompressed_len_walk
        )

        # Combine header and data
        bgfa_data = header + samples_data + sequences_data + walks_data

        walks, bytes_read = self.reader._parse_walks_blocks(bgfa_data, {}, [], 0)

        self.assertEqual(len(walks), 2)
        self.assertEqual(walks[0]["sample_id"], "sample1")
        self.assertEqual(walks[0]["sequence_id"], "seq1")
        self.assertEqual(walks[0]["walk"], "walk1")
        self.assertEqual(walks[1]["sample_id"], "sample2")
        self.assertEqual(walks[1]["sequence_id"], "seq2")
        self.assertEqual(walks[1]["walk"], "walk2")
        self.assertEqual(bytes_read, len(bgfa_data))

    def test_bgfa_reader_with_paths_and_walks(self):
        """Test complete BGFA reader with paths and walks."""
        # Create output directory using tempfile
        output_dir = tempfile.mkdtemp(dir="results/test")

        with tempfile.NamedTemporaryFile(delete=False, dir=output_dir) as tmp_file:
            # Create BGFA header (new format: no block_size)
            version = 1
            header_text = "test_header\0"

            # Write file header: version + reserved (34 bytes) + header_text
            tmp_file.write(struct.pack("<H", version))
            tmp_file.write(b"\x00" * 34)  # reserved space
            tmp_file.write(header_text.encode("ascii"))

            # Add segment names block with section_id (empty - record_num = 0 indicates no more blocks)
            seg_names_header = struct.pack(
                "<BHHQQ",
                1,  # section_id = 1 (segment names)
                0,  # record_num = 0 (last block)
                0x0000,  # compression_names
                0,  # compressed_len
                0,  # uncompressed_len
            )
            tmp_file.write(seg_names_header)

            # Add segments block with section_id (empty - record_num = 0 indicates no more blocks)
            seg_header = struct.pack(
                "<BHHQQ",
                2,  # section_id = 2 (segments)
                0,  # record_num = 0 (last block)
                0x0000,  # compression_str
                0,  # compressed_len
                0,  # uncompressed_len
            )
            tmp_file.write(seg_header)

            # Add a simple paths block
            path_name = "test_path"
            path_cigar = "100M"
            names_data = path_name.encode("ascii") + b"\0"
            cigars_data = path_cigar.encode("ascii") + b"\0"

            # Paths block header with section_id (with section_id + 3 compression codes + 4 length fields = 29 bytes)
            paths_header = struct.pack(
                "<BHHHHQQQQ",
                4,  # section_id = 4 (paths)
                1,  # record_num
                0x0000,  # compression_path_names
                0x0000,  # compression_paths
                0x0000,  # compression_cigars
                len(cigars_data),  # compressed_len_cigar
                len(cigars_data),  # uncompressed_len_cigar
                len(names_data),  # compressed_len_name
                len(names_data),  # uncompressed_len_name
            )
            tmp_file.write(paths_header)
            tmp_file.write(cigars_data)
            tmp_file.write(names_data)

            # Add a simple walks block
            sample_id = "test_sample"
            sequence_id = "test_sequence"
            walk_data = "test_walk"
            samples_data = sample_id.encode("ascii") + b"\0"
            sequences_data = sequence_id.encode("ascii") + b"\0"
            walks_data = walk_data.encode("ascii") + b"\0"

            # Walks block header with section_id (section_id + 5 compression codes + 6 length fields = 73 bytes total)
            walks_header = struct.pack(
                "<BHHHHHHQQQQQQ",
                5,  # section_id = 5 (walks)
                1,  # record_num
                0x0000,  # compression_samples
                0x0000,  # compression_hep
                0x0000,  # compression_sequence
                0x0000,  # compression_positions
                0x0000,  # compression_walks
                len(samples_data),  # compressed_len_sam
                len(samples_data),  # uncompressed_len_sam
                len(sequences_data),  # compressed_len_seq
                len(sequences_data),  # uncompressed_len_seq
                len(walks_data),  # compressed_len_walk
                len(walks_data),  # uncompressed_len_walk
            )
            tmp_file.write(walks_header)
            tmp_file.write(samples_data)
            tmp_file.write(sequences_data)
            tmp_file.write(walks_data)

            tmp_file_path = tmp_file.name

        try:
            # Read BGFA file
            gfa = self.reader.read_bgfa(tmp_file_path, verbose=True)

            # Verify that GFA object was created
            self.assertIsInstance(gfa, GFA)

        finally:
            # Clean up
            os.unlink(tmp_file_path)


if __name__ == "__main__":
    unittest.main()
