#!/usr/bin/env python3
"""
Benchmark BGFA decoding: BGFA -> GFA with timing.

This script is called by Snakemake and uses snakemake object to access:
- snakemake.input.bgfa: Input BGFA file path
- snakemake.output.time: Output file for decoding time
"""

import subprocess
import time
import sys
import os
from pathlib import Path

# Add project root to path (script is in workflow/scripts/)
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from pygfa.utils.output_manager import OutputManager  # noqa: E402

# Access Snakemake variables
# snakemake provides these variables at runtime

bgfa_path = snakemake.input.bgfa  # noqa: F821
time_file = snakemake.output.time  # noqa: F821

output_mgr = OutputManager()
os.makedirs(output_mgr.ensure_dir(os.path.dirname(time_file)), exist_ok=True)

# Build command - decode to /dev/null to measure timing only
cmd = ["pixi", "run", "python", "bin/bgfatools", "cat", bgfa_path, "-o", "/dev/null"]

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
    with open(time_file, "w") as f:
        f.write("ERROR\n")
    sys.exit(0)

# Write elapsed time
with open(time_file, "w") as f:
    f.write(f"{elapsed:.3f}\n")
