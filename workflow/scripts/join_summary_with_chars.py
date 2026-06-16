#!/usr/bin/env python3
"""Join benchmark summary CSV with dataset characterization data.

Reads summary CSV from stdin, characterization JSONs from a directory,
and writes the joined CSV to stdout.

Usage:
    pixi run python workflow/scripts/join_summary_with_chars.py <chardir>
"""

import csv
import json
import os
import sys


CHARACTERIZATION_FIELDS = [
    "avg_seq_len",
    "max_seq_len",
    "gc_content",
    "unique_chars_seq",
    "unique_chars_names",
    "avg_cigar_len",
    "cigar_present_ratio",
    "avg_path_depth",
    "max_path_depth",
    "num_segments",
    "num_links",
    "num_paths",
    "num_walks",
    "file_size_bytes",
]


def load_characterizations(chardir: str) -> dict[str, dict]:
    """Load all characterization JSON files, keyed by original_gfa path."""
    result = {}
    if not os.path.isdir(chardir):
        return result

    for fname in os.listdir(chardir):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(chardir, fname)
        with open(fpath) as f:
            data = json.load(f)
        file_key = data.get("file", "")
        if file_key:
            result[file_key] = data
    return result


def join_csv(reader: csv.DictReader, chars: dict[str, dict], output):
    """Join rows with characterization data and write to output."""
    fieldnames = reader.fieldnames + CHARACTERIZATION_FIELDS
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()

    for row in reader:
        gfa_path = row.get("original_gfa", "")
        char_data = chars.get(gfa_path, {})
        for field in CHARACTERIZATION_FIELDS:
            row[field] = char_data.get(field, "")
        writer.writerow(row)


def main():
    if len(sys.argv) < 2:
        print("Usage: join_summary_with_chars.py <chardir>", file=sys.stderr)
        sys.exit(1)

    chardir = sys.argv[1]
    chars = load_characterizations(chardir)
    reader = csv.DictReader(sys.stdin)
    join_csv(reader, chars, sys.stdout)


if __name__ == "__main__":
    main()
