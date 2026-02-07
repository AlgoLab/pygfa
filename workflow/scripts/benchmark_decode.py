#!/usr/bin/env python3
"""
Benchmark BGFA decoding: BGFA -> GFA with timing.

This script is called by Snakemake and uses the snakemake object to access:
- snakemake.input.bgfa: Input BGFA file path
- snakemake.output.time: Output file for decoding time
"""

import subprocess
import time
import sys
import os

# Access Snakemake variables
bgfa_path = snakemake.input.bgfa
time_file = snakemake.output.time

# Ensure output directory exists
os.makedirs(os.path.dirname(time_file), exist_ok=True)

# Build command - decode to /dev/null to measure timing only
cmd = [
    "pixi", "run", "python", "bin/bgfatools", "cat",
    bgfa_path, "-o", "/dev/null"
]

# Time the decoding
start = time.time()
result = subprocess.run(cmd, capture_output=True, text=True)
elapsed = time.time() - start

# Handle errors - write "ERROR" and exit gracefully
if result.returncode != 0:
    print(f"ERROR: Decoding failed for {bgfa_path}", file=sys.stderr)
    print(f"Command: {' '.join(cmd)}", file=sys.stderr)
    print(f"stdout: {result.stdout}", file=sys.stderr)
    print(f"stderr: {result.stderr}", file=sys.stderr)
    with open(time_file, 'w') as f:
        f.write("ERROR\n")
    sys.exit(0)

# Write elapsed time
with open(time_file, 'w') as f:
    f.write(f"{elapsed:.3f}\n")
