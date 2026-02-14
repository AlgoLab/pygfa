#!/usr/bin/env python3
"""
Benchmark BGFA decoding: BGFA -> GFA with timing.

Environment variables:
- INPUT_BGFA: Input BGFA file path
- OUTPUT_TIME: Output file for decoding time
"""

import os
import subprocess
import sys
import time
from pathlib import Path

# Add project root to path (script is in workflow/scripts/)
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from pygfa.utils.output_manager import OutputManager  # noqa: E402

# Read environment variables
bgfa_path = os.environ["INPUT_BGFA"]
time_file = os.environ["OUTPUT_TIME"]

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
