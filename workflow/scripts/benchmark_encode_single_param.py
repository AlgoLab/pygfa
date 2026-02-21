#!/usr/bin/env python3
"""
Single-parameter benchmark BGFA encoding: GFA -> BGFA with block statistics.

This script is specialized for single-parameter benchmarks where only one
aspect of encoding is varied at a time.

Environment variables:
- INPUT_GFA: Input GFA file path
- OUTPUT_BGFA: Output BGFA file path
- OUTPUT_CSV: Output CSV file for block statistics
- INT_FLAG: Integer encoding flag ("" or encoding name)
- STR_FLAG: String encoding flag ("" or encoding name)
- BLOCK_SIZE: Block size (default: 1024)
- BLOCK_TYPE: Block type for block-specific tests (segments, links, paths, walks)
"""

import os
import subprocess
import sys

gfa_path = os.environ["INPUT_GFA"]
bgfa_path = os.environ["OUTPUT_BGFA"]
csv_file = os.environ["OUTPUT_CSV"]
int_flag = os.environ.get("INT_FLAG", "")
str_flag = os.environ.get("STR_FLAG", "")
block_size = os.environ.get("BLOCK_SIZE", "1024")
block_type = os.environ.get("BLOCK_TYPE", None)

os.makedirs(os.path.dirname(bgfa_path), exist_ok=True)
os.makedirs(os.path.dirname(csv_file), exist_ok=True)

cmd = [
    "pixi",
    "run",
    "python",
    "bin/bgfatools",
    "bgfa",
    gfa_path,
    bgfa_path,
    "--block-size",
    block_size,
]

if block_type is None:
    cmd.extend(
        [
            "--segment-names-header",
            str_flag,
            "--segment-names-payload-lengths",
            int_flag,
            "--segment-names-payload-names",
            str_flag,
            "--segments-header",
            str_flag,
            "--segments-payload-lengths",
            int_flag,
            "--segments-payload-strings",
            str_flag,
            "--links-header",
            str_flag,
            "--links-payload-from",
            int_flag,
            "--links-payload-to",
            int_flag,
            "--links-payload-cigar-lengths",
            int_flag,
            "--links-payload-cigar",
            str_flag,
            "--paths-header",
            str_flag,
            "--paths-payload-names",
            str_flag,
            "--paths-payload-segment-lengths",
            int_flag,
            "--paths-payload-path-ids",
            str_flag,
            "--paths-payload-cigar-lengths",
            int_flag,
            "--paths-payload-cigar",
            str_flag,
            "--walks-header",
            str_flag,
            "--walks-payload-sample-ids",
            str_flag,
            "--walks-payload-hep-indices",
            int_flag,
            "--walks-payload-sequence-ids",
            str_flag,
            "--walks-payload-start",
            int_flag,
            "--walks-payload-end",
            int_flag,
            "--walks-payload-walks",
            str_flag,
        ]
    )
elif block_type == "segments":
    cmd.extend(
        [
            "--segments-header",
            str_flag,
            "--segments-payload-lengths",
            int_flag,
            "--segments-payload-strings",
            str_flag,
        ]
    )
elif block_type == "links":
    cmd.extend(
        [
            "--links-header",
            str_flag,
            "--links-payload-from",
            int_flag,
            "--links-payload-to",
            int_flag,
            "--links-payload-cigar-lengths",
            int_flag,
            "--links-payload-cigar",
            str_flag,
        ]
    )
elif block_type == "paths":
    cmd.extend(
        [
            "--paths-header",
            str_flag,
            "--paths-payload-names",
            str_flag,
            "--paths-payload-segment-lengths",
            int_flag,
            "--paths-payload-path-ids",
            str_flag,
            "--paths-payload-cigar-lengths",
            int_flag,
            "--paths-payload-cigar",
            str_flag,
        ]
    )
elif block_type == "walks":
    cmd.extend(
        [
            "--walks-header",
            str_flag,
            "--walks-payload-sample-ids",
            str_flag,
            "--walks-payload-hep-indices",
            int_flag,
            "--walks-payload-sequence-ids",
            str_flag,
            "--walks-payload-start",
            int_flag,
            "--walks-payload-end",
            int_flag,
            "--walks-payload-walks",
            str_flag,
        ]
    )

result = subprocess.run(cmd, capture_output=True, text=True)

if result.returncode != 0:
    print(f"ERROR: Encoding failed for {gfa_path}", file=sys.stderr)
    print(f"Command: {' '.join(cmd)}", file=sys.stderr)
    print(f"stdout: {result.stdout}", file=sys.stderr)
    print(f"stderr: {result.stderr}", file=sys.stderr)
    sys.exit(1)

measure_cmd = [
    "pixi",
    "run",
    "python",
    "bin/bgfatools",
    "measure",
    bgfa_path,
    csv_file,
    "--original-gfa",
    gfa_path,
]

measure_result = subprocess.run(measure_cmd, capture_output=True, text=True)

if measure_result.returncode != 0:
    print(f"ERROR: Measurement failed for {bgfa_path}", file=sys.stderr)
    print(f"Command: {' '.join(measure_cmd)}", file=sys.stderr)
    print(f"stdout: {measure_result.stdout}", file=sys.stderr)
    print(f"stderr: {measure_result.stderr}", file=sys.stderr)
    sys.exit(1)

print(f"Successfully encoded {gfa_path} -> {bgfa_path}")
print(f"Block statistics written to {csv_file}")
