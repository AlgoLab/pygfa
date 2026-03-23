#!/usr/bin/env python3
"""Test that encoding fields are stored at correct offsets in BGFA files.

This test verifies the fix for fields being stored at incorrect offsets.

The BGFA segment block should have this structure:
- section_id (1 byte)
- record_num (2 bytes) 
- names_enc (2 bytes)  <- at offset +3
- clen_names (8 bytes)
- ulen_names (8 bytes)
- seq_enc (2 bytes)    <- at offset +21
- clen_seq (8 bytes)
- ulen_seq (8 bytes)
- payload

Note: Header is at offset 0, but segment block starts after header.
"""

import os
import struct
import tempfile
import unittest

from pygfa.gfa import GFA
from pygfa.graph_element import node as node_module
from pygfa import bgfa
from pygfa.encoding.enums import IntegerEncoding, StringEncoding, make_compression_code


class TestEncodingFieldOffsets(unittest.TestCase):
    """Test that compression encoding fields are stored at correct offsets."""

    def test_names_enc_stored_at_correct_offset(self):
        """Verify names_enc is stored at the correct position in BGFA file."""
        g = GFA()
        g.add_node(node_module.Node("node1", "ACGT"))
        
        # Use explicit encoding values to verify positions
        names_enc = make_compression_code(IntegerEncoding.VARINT, StringEncoding.BROTLI)  # 0x010d
        seq_enc = make_compression_code(IntegerEncoding.VARINT, StringEncoding.NONE)  # 0x0100
        
        writer = bgfa.BGFAWriter(g, 100, {"names_enc": names_enc, "seq_enc": seq_enc})
        data = writer.to_bgfa()
        
        # Parse like reader does
        # First, find segment block start (after header)
        # Note: header_size includes the null terminator (8 + header_len + 1)
        header_len = struct.unpack("<H", data[6:8])[0]
        seg_start = 8 + header_len + 1  # section_id position (includes null terminator)
        
        # Verify section_id is at expected position (SECTION_ID_SEGMENTS = 2)
        self.assertEqual(data[seg_start], 2)  # SECTION_ID_SEGMENTS = 2
        
        # Read fields at positions where reader expects them
        offset = seg_start + 1  # Skip section_id
        offset += 2  # record_num
        
        comp_names = struct.unpack_from("<H", data, offset)[0]
        offset += 2
        
        # Skip length fields
        offset += 8  # clen_names
        offset += 8  # ulen_names
        
        comp_seq = struct.unpack_from("<H", data, offset)[0]
        
        # Verify values match what was written
        self.assertEqual(comp_names, names_enc, 
            f"names_enc mismatch: got 0x{comp_names:04x}, expected 0x{names_enc:04x}")
        self.assertEqual(comp_seq, seq_enc,
            f"seq_enc mismatch: got 0x{comp_seq:04x}, expected 0x{seq_enc:04x}")

    def test_roundtrip_with_string_encodings(self):
        """Test round-trip with various string encodings."""
        g = GFA()
        g.add_node(node_module.Node("node1", "ACGT"))
        g.add_node(node_module.Node("node2", "TTTT"))
        
        # Test multiple encodings
        test_encodings = [
            ("varint+zstd", "varint+zstd"),
            ("varint+gzip", "varint+gzip"),  
            ("varint+lzma", "varint+lzma"),
            ("varint+lz4", "varint+lz4"),
            ("varint+brotli", "varint+brotli"),
        ]
        
        for name, encoding in test_encodings:
            with self.subTest(encoding=name):
                with tempfile.NamedTemporaryFile(suffix=".bgfa", delete=False) as f:
                    bgfa_path = f.name
                
                try:
                    # Write
                    writer = bgfa.BGFAWriter(g, 100, {"names_enc": encoding})
                    with open(bgfa_path, "wb") as f:
                        f.write(writer.to_bgfa())
                    
                    # Read
                    g2 = bgfa.read_bgfa(bgfa_path)
                    
                    # Verify
                    self.assertIn("node1", g2.nodes())
                    self.assertIn("node2", g2.nodes())
                finally:
                    if os.path.exists(bgfa_path):
                        os.unlink(bgfa_path)

    @unittest.skip("BROTLI roundtrip has separate issue - requires investigation")
    def test_roundtrip_with_brotli_encoding(self):
        """Test round-trip with BROTLI encoding - has separate issue."""
        pass

    def test_parse_compression_strategy_with_underscores(self):
        """Test parsing of composite encoding strings with underscores."""
        test_cases = [
            # Two-part encodings
            ("varint+brotli", make_compression_code(IntegerEncoding.VARINT, StringEncoding.BROTLI)),
            ("bit_packing+brotli", make_compression_code(IntegerEncoding.BIT_PACKING, StringEncoding.BROTLI)),
            ("varint-zstd", make_compression_code(IntegerEncoding.VARINT, StringEncoding.ZSTD)),
            ("varint-gzip", make_compression_code(IntegerEncoding.VARINT, StringEncoding.GZIP)),
            ("varint-lzma", make_compression_code(IntegerEncoding.VARINT, StringEncoding.LZMA)),
            # Single-part string encodings (no delimiter)
            ("brotli", make_compression_code(IntegerEncoding.VARINT, StringEncoding.BROTLI)),
            ("zstd", make_compression_code(IntegerEncoding.VARINT, StringEncoding.ZSTD)),
            ("gzip", make_compression_code(IntegerEncoding.VARINT, StringEncoding.GZIP)),
            # Superstring encodings (underscore in name, single part)
            ("superstring_ppm", make_compression_code(IntegerEncoding.VARINT, StringEncoding.SUPERSTRING_PPM)),
            ("superstring_huffman", make_compression_code(IntegerEncoding.VARINT, StringEncoding.SUPERSTRING_HUFFMAN)),
            ("superstring_none", make_compression_code(IntegerEncoding.VARINT, StringEncoding.SUPERSTRING_NONE)),
            ("superstring_2bit", make_compression_code(IntegerEncoding.VARINT, StringEncoding.SUPERSTRING_2BIT)),
        ]
        
        for encoding_str, expected in test_cases:
            with self.subTest(encoding=encoding_str):
                actual = bgfa.parse_compression_strategy(encoding_str)
                self.assertEqual(actual, expected,
                    f"parse_compression_strategy('{encoding_str}') = 0x{actual:04x}, "
                    f"expected 0x{expected:04x}")


if __name__ == "__main__":
    unittest.main()