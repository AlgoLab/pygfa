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
    f.write(b"AFGB")
    f.write(struct.pack("<H", 1))
    header_text = "test header"
    header_len = len(header_text)
    f.write(struct.pack("<H", header_len))
    f.write(header_text.encode("ascii") + b"\x00")

    f.write(struct.pack("<B", 5))
    f.write(struct.pack("<H", 1))

    f.write(struct.pack("<H", 0x0000))
    f.write(struct.pack("<Q", 8))
    f.write(struct.pack("<Q", 8))

    f.write(struct.pack("<H", 0x0000))
    f.write(struct.pack("<Q", 8))

    f.write(struct.pack("<H", 0x0000))
    f.write(struct.pack("<Q", 0))
    f.write(struct.pack("<Q", 0))

    f.write(struct.pack("<H", 0x0000))
    f.write(struct.pack("<Q", 8))

    f.write(struct.pack("<H", 0x0000))
    f.write(struct.pack("<Q", 8))
    f.write(struct.pack("<Q", 8))

    f.write(b"\x00" * 32)

try:
    rows = measure_bgfa(test_file, output_csv)
    print("measure_bgfa succeeded. Rows returned:", len(rows))
    for row in rows:
        print(row)
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
