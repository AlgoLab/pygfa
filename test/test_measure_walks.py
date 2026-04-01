#!/usr/bin/env python3
import os
import sys
import struct
import tempfile

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from pygfa.bgfa import measure_bgfa  # noqa: E402

test_file = tempfile.mktemp(suffix=".bgfa")
output_csv = tempfile.mktemp(suffix=".csv")

with open(test_file, "wb") as f:
    # Header
    f.write(b"BGFA")
    f.write(struct.pack("<H", 1))
    header_text = "test header"
    header_len = len(header_text)
    f.write(struct.pack("<H", header_len))
    f.write(header_text.encode("ascii") + b"\x00")

    # Walks block
    f.write(struct.pack("<B", 5))  # section_id
    f.write(struct.pack("<H", 1))  # record_num

    f.write(struct.pack("<H", 0x0000))  # compression_samples
    f.write(struct.pack("<Q", 8))  # compressed_len_samples
    f.write(struct.pack("<Q", 8))  # uncompressed_len_samples

    f.write(struct.pack("<H", 0x0000))  # compression_hep
    f.write(struct.pack("<Q", 8))  # compressed_len_hep
    f.write(struct.pack("<Q", 8))  # uncompressed_len_hep

    f.write(struct.pack("<H", 0x0000))  # compression_sequence
    f.write(struct.pack("<Q", 0))  # compressed_len_sequence
    f.write(struct.pack("<Q", 0))  # uncompressed_len_sequence

    f.write(struct.pack("<H", 0x0000))  # compression_positions
    f.write(struct.pack("<Q", 8))  # compressed_len_positions
    f.write(struct.pack("<Q", 8))  # uncompressed_len_positions

    f.write(struct.pack("<I", 0x0000))  # compression_walks (4 bytes!)
    f.write(struct.pack("<Q", 8))  # compressed_len_walks
    f.write(struct.pack("<Q", 8))  # uncompressed_len_walks

    f.write(b"\x00" * 8)  # payload data (matching compressed_len)

try:
    measure_bgfa(test_file, output_csv)
    print("measure_bgfa succeeded.")
    if os.path.exists(output_csv):
        with open(output_csv, "r") as csvf:
            content = csvf.read()
        print("\nCSV content:")
        print(content)
    else:
        print("CSV file not created!")
finally:
    if os.path.exists(test_file):
        os.remove(test_file)
    if os.path.exists(output_csv):
        os.remove(output_csv)
