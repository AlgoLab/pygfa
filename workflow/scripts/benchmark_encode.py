#!/usr/bin/env python3
"""
Benchmark BGFA encoding: GFA -> BGFA with timing.

This script is called by Snakemake and uses the snakemake object to access:
- snakemake.input.gfa: Input GFA file path
- snakemake.output.bgfa: Output BGFA file path
- snakemake.output.time: Output file for encoding time
- snakemake.wildcards.int_enc: Integer encoding name
- snakemake.wildcards.str_enc: String encoding name
- snakemake.params.int_flag: Integer encoding flag ("" or encoding name)
- snakemake.params.str_flag: String encoding flag ("" or encoding name)
"""

import subprocess
import time
import sys
import os

# Access Snakemake variables
gfa_path = snakemake.input.gfa
bgfa_path = snakemake.output.bgfa
time_file = snakemake.output.time

int_flag = snakemake.params.int_flag
str_flag = snakemake.params.str_flag

# Ensure output directory exists
os.makedirs(os.path.dirname(bgfa_path), exist_ok=True)
os.makedirs(os.path.dirname(time_file), exist_ok=True)

# Measure GFA file size before encoding
gfa_bytes = os.path.getsize(gfa_path)

# Build command - mirroring bash script flags
cmd = [
    "pixi",
    "run",
    "python",
    "bin/bgfatools",
    "bgfa",
    gfa_path,
    bgfa_path,
    "--segment-names-payload-lengths",
    int_flag,
    "--segment-names-payload-names",
    str_flag,
    "--segments-payload-lengths",
    int_flag,
    "--segments-payload-strings",
    str_flag,
    "--links-payload-from",
    int_flag,
    "--links-payload-to",
    int_flag,
    "--links-payload-cigar-lengths",
    int_flag,
    "--links-payload-cigar",
    str_flag,
    "--paths-payload-names",
    str_flag,
    "--paths-payload-segment-lengths",
    int_flag,
    "--paths-payload-cigar-lengths",
    int_flag,
    "--paths-payload-cigar",
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
]

# Time the encoding
start = time.time()
result = subprocess.run(cmd, capture_output=True, text=True)
elapsed = time.time() - start

# Handle errors - write "ERROR" and exit gracefully (don't fail Snakemake rule)
if result.returncode != 0:
    print(f"ERROR: Encoding failed for {gfa_path}", file=sys.stderr)
    print(f"Command: {' '.join(cmd)}", file=sys.stderr)
    print(f"stdout: {result.stdout}", file=sys.stderr)
    print(f"stderr: {result.stderr}", file=sys.stderr)
    with open(time_file, "w") as f:
        f.write("ERROR\n")
    # Create empty BGFA file to satisfy Snakemake
    with open(bgfa_path, "w") as f:
        f.write("")
    sys.exit(0)

# Write elapsed time
with open(time_file, "w") as f:
    f.write(f"{elapsed:.3f}\n")
