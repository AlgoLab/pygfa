#!/usr/bin/env python3
"""
Compute compression statistics for a single BGFA encoding combination.

Environment variables:
- INPUT_GFA: Original GFA file path
- INPUT_BGFA: Encoded BGFA file path
- INPUT_ENCODE_TIME: File containing encoding time
- INPUT_DECODE_TIME: File containing decoding time
- OUTPUT_STATS: Output TSV file with statistics
- DATASET: Dataset name
- INT_ENC: Integer encoding name
- STR_ENC: String encoding name
"""

import os
import sys

# Read environment variables
gfa_path = os.environ["INPUT_GFA"]
bgfa_path = os.environ["INPUT_BGFA"]
encode_time_file = os.environ["INPUT_ENCODE_TIME"]
decode_time_file = os.environ["INPUT_DECODE_TIME"]
stats_file = os.environ["OUTPUT_STATS"]

dataset = os.environ["DATASET"]
int_enc = os.environ["INT_ENC"]
str_enc = os.environ["STR_ENC"]

# Ensure output directory exists
os.makedirs(os.path.dirname(stats_file), exist_ok=True)

# Read timing data
with open(encode_time_file) as f:
    encode_time = f.read().strip()

with open(decode_time_file) as f:
    decode_time = f.read().strip()

# Get file sizes
gfa_bytes = os.path.getsize(gfa_path)

# Check if encoding/decoding failed
if encode_time == "ERROR":
    # Write error row
    with open(stats_file, "w") as f:
        f.write(f"{dataset}\t{int_enc}\t{str_enc}\t{gfa_bytes}\tERROR\t-\t-\t-\n")
    sys.exit(0)

bgfa_bytes = os.path.getsize(bgfa_path)

if decode_time == "ERROR":
    # Encoding succeeded but decoding failed
    compression_ratio = bgfa_bytes / gfa_bytes if gfa_bytes > 0 else 0.0
    with open(stats_file, "w") as f:
        f.write(
            f"{dataset}\t{int_enc}\t{str_enc}\t{gfa_bytes}\t{bgfa_bytes}\t{compression_ratio:.4f}\t{encode_time}\tERROR\n"
        )
    sys.exit(0)

# Compute compression ratio
compression_ratio = bgfa_bytes / gfa_bytes if gfa_bytes > 0 else 0.0

# Write stats row (no header, aggregate_results will add header)
with open(stats_file, "w") as f:
    f.write(
        f"{dataset}\t{int_enc}\t{str_enc}\t{gfa_bytes}\t{bgfa_bytes}\t{compression_ratio:.4f}\t{encode_time}\t{decode_time}\n"
    )
