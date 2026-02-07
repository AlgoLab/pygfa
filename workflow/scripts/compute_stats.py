#!/usr/bin/env python3
"""
Compute compression statistics for a single BGFA encoding combination.

This script is called by Snakemake and uses the snakemake object to access:
- snakemake.input.gfa: Original GFA file path
- snakemake.input.bgfa: Encoded BGFA file path
- snakemake.input.encode_time: File containing encoding time
- snakemake.input.decode_time: File containing decoding time
- snakemake.output.stats: Output TSV file with statistics
- snakemake.wildcards.dataset: Dataset name
- snakemake.wildcards.int_enc: Integer encoding name
- snakemake.wildcards.str_enc: String encoding name
"""

import os
import sys

# Access Snakemake variables
gfa_path = snakemake.input.gfa
bgfa_path = snakemake.input.bgfa
encode_time_file = snakemake.input.encode_time
decode_time_file = snakemake.input.decode_time
stats_file = snakemake.output.stats

dataset = snakemake.wildcards.dataset
int_enc = snakemake.wildcards.int_enc
str_enc = snakemake.wildcards.str_enc

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
    with open(stats_file, 'w') as f:
        f.write(f"{dataset}\t{int_enc}\t{str_enc}\t{gfa_bytes}\tERROR\t-\t-\t-\n")
    sys.exit(0)

bgfa_bytes = os.path.getsize(bgfa_path)

if decode_time == "ERROR":
    # Encoding succeeded but decoding failed
    compression_ratio = bgfa_bytes / gfa_bytes if gfa_bytes > 0 else 0.0
    with open(stats_file, 'w') as f:
        f.write(f"{dataset}\t{int_enc}\t{str_enc}\t{gfa_bytes}\t{bgfa_bytes}\t{compression_ratio:.4f}\t{encode_time}\tERROR\n")
    sys.exit(0)

# Compute compression ratio
compression_ratio = bgfa_bytes / gfa_bytes if gfa_bytes > 0 else 0.0

# Write stats row (no header, aggregate_results will add header)
with open(stats_file, 'w') as f:
    f.write(f"{dataset}\t{int_enc}\t{str_enc}\t{gfa_bytes}\t{bgfa_bytes}\t{compression_ratio:.4f}\t{encode_time}\t{decode_time}\n")
