#!/usr/bin/env python3
"""Add metadata columns to a measure CSV file in-place.

Replaces the fragile sed-based column injection in the Snakefile.
"""
import argparse
import csv
import os
import shutil
import tempfile


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add metadata columns to a measure CSV"
    )
    parser.add_argument("--csv", required=True, help="CSV file to modify in-place")
    parser.add_argument("--original-gfa", required=True, help="Path to original GFA file")
    parser.add_argument("--block-size", required=True, help="Block size used")
    parser.add_argument("--option", required=True, help="Compression option name")
    parser.add_argument("--encoding", required=True, help="Encoding value")
    args = parser.parse_args()

    with open(args.csv, "r", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"CSV file {args.csv} has no header")
        fieldnames = list(reader.fieldnames) + [
            "original_gfa",
            "block_size",
            "compression_option",
            "compression_value",
        ]
        rows = [
            dict(
                row,
                original_gfa=args.original_gfa,
                block_size=args.block_size,
                compression_option=args.option,
                compression_value=args.encoding,
            )
            for row in reader
        ]

    fd, tmp_path = tempfile.mkstemp(
        dir=os.path.dirname(args.csv) or ".",
        prefix=".tmp_add_metadata_",
    )
    os.close(fd)
    try:
        with open(tmp_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        shutil.move(tmp_path, args.csv)
    except Exception:
        os.unlink(tmp_path)
        raise


if __name__ == "__main__":
    main()
