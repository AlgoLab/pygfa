# Single-Parameter Benchmarks

This document describes the single-parameter benchmark system for evaluating BGFA compression strategies. Each benchmark varies only one parameter while keeping all others at their default (identity/none) values.

## Overview

The single-parameter approach allows isolating the effect of each compression strategy, making it easier to:
- Identify the best encoding for each data type
- Understand trade-offs between compression ratio and speed
- Make informed decisions about which encodings to combine

## Quick Start

```bash
# Run all single-parameter benchmarks
snakemake -s workflow/Snakefile_single_param -j 8

# Dry run to see what will be executed
snakemake -s workflow/Snakefile_single_param -n

# Run specific benchmark type
snakemake -s workflow/Snakefile_single_param -j 8 benchmark_int_encoding_only
snakemake -s workflow/Snakefile_single_param -j 8 benchmark_str_encoding_only
snakemake -s workflow/Snakefile_single_param -j 8 benchmark_block_size_only
snakemake -s workflow/Snakefile_single_param -j 8 benchmark_block_specific_only
```

## Benchmark Types and Required Comments

To include a GFA file in a benchmark, add the corresponding comment at the beginning of the file:

| Benchmark Type | Required Comment | Description |
|----------------|------------------|-------------|
| Integer encoding | `# benchmark: int_encoding` | Tests integer encoding strategies |
| String encoding | `# benchmark: str_encoding` | Tests string encoding strategies |
| Block size | `# benchmark: block_size` | Tests different block sizes |
| Block-specific | `# benchmark: block_specific` | Tests per-block compression |
| All single-param | `# benchmark: single_param` | Includes in all 4 benchmarks |

### Example GFA File Header

```gfa
# test: read_gfa
# benchmark: single_param
# benchmark: int_encoding
H	VN:Z:1.0
S	1	ATCG
...
```

## Default Configuration

For all single-parameter benchmarks, non-tested parameters are set to minimize execution time:

| Parameter | Default Value | Description |
|-----------|---------------|-------------|
| Integer encoding | `identity` (none) | No compression |
| String encoding | `identity` (none) | No compression |
| Block size | `1024` | Default block size |

---

## Integer Encoding Benchmark (`# benchmark: int_encoding`)

Tests all 19 integer encoding strategies. All string encodings use `identity`.

### Available Integer Encodings

| Encoding | Description |
|----------|-------------|
| `identity` | No compression (comma-separated ASCII) |
| `varint` | Variable-length integer encoding |
| `fixed16` | Fixed 16-bit integers |
| `fixed32` | Fixed 32-bit integers |
| `fixed64` | Fixed 64-bit integers |
| `delta` | Delta encoding + varint |
| `gamma` | Elias gamma coding |
| `omega` | Elias omega coding |
| `golomb` | Golomb coding (auto-computed divisor) |
| `rice` | Rice coding |
| `streamvbyte` | StreamVByte SIMD-optimized |
| `vbyte` | VByte variable-length |
| `pfor_delta` | Patched Frame of Reference + Delta |
| `simple8b` | Simple-8b encoding |
| `group_varint` | Group varint encoding |
| `bit_packing` | Bit-packed integers |
| `fibonacci` | Fibonacci coding |
| `exp_golomb` | Exponential Golomb coding |
| `byte_packed` | Byte-packed encoding |
| `masked_vbyte` | Masked VByte encoding |

### Output Files

```
results/benchmark/int_encoding/{dataset}/{encoding}.csv
results/benchmark/int_encoding/{dataset}/{encoding}.bgfa
```

---

## String Encoding Benchmark (`# benchmark: str_encoding`)

Tests all 15 string encoding strategies. All integer encodings use `identity`.

### Available String Encodings

| Encoding | Description |
|----------|-------------|
| `identity` | No compression (raw bytes) |
| `zstd` | Zstandard compression |
| `gzip` | Gzip compression |
| `lzma` | LZMA/XZ compression |
| `lz4` | LZ4 compression |
| `brotli` | Brotli compression |
| `huffman` | Huffman coding |
| `rle` | Run-length encoding |
| `dictionary` | Dictionary-based encoding |
| `arithmetic` | Adaptive arithmetic coding |
| `bwt_huffman` | BWT + Move-to-Front + Huffman |
| `ppm` | Prediction by Partial Matching |
| `2bit` | 2-bit DNA encoding (A=00, C=01, G=10, T=11) |
| `cigar` | CIGAR-specific encoding |
| `zstd_dict` | Zstd with trained dictionary |

### Output Files

```
results/benchmark/str_encoding/{dataset}/{encoding}.csv
results/benchmark/str_encoding/{dataset}/{encoding}.bgfa
```

---

## Block Size Benchmark (`# benchmark: block_size`)

Tests different block sizes (number of records per block). All encodings use `identity`.

### Block Sizes Tested

| Size | Description |
|------|-------------|
| `64` | Small blocks |
| `128` | |
| `256` | |
| `512` | |
| `1024` | Default |
| `2048` | |
| `4096` | |
| `8192` | |
| `16384` | Large blocks |
| `32768` | Very large blocks |

### Output Files

```
results/benchmark/block_size/{dataset}/{size}.csv
results/benchmark/block_size/{dataset}/{size}.bgfa
```

---

## Block-Specific Benchmark (`# benchmark: block_specific`)

Tests compression strategies on individual block types (segments, links, paths, walks). This isolates which compression works best for each data type.

### Block Types

| Block Type | Description | Primary Data |
|------------|-------------|--------------|
| `segments` | Sequence segments | DNA strings, lengths |
| `links` | Edge connections | Node IDs, CIGAR strings |
| `paths` | Named paths | Path names, segment lists |
| `walks` | Walk traversals | Sample IDs, haplotype info |

### Test Matrix

For each block type, test encodings relevant to that data:

| Block Type | Integer Encodings | String Encodings |
|------------|-------------------|------------------|
| `segments` | identity, varint, delta | identity, zstd, 2bit |
| `links` | identity, varint, delta | identity, zstd, cigar |
| `paths` | identity, varint, delta | identity, zstd |
| `walks` | identity, varint, delta | identity, zstd |

### Output Files

```
results/benchmark/block_specific/{dataset}/{block_type}_{int_enc}_{str_enc}.csv
results/benchmark/block_specific/{dataset}/{block_type}_{int_enc}_{str_enc}.bgfa
```

---

## Running Benchmarks

### All Benchmarks

```bash
snakemake -s workflow/Snakefile_single_param -j 8
```

### Specific Benchmark Type

```bash
# Integer encodings only
snakemake -s workflow/Snakefile_single_param -j 8 benchmark_int_encoding_only

# String encodings only
snakemake -s workflow/Snakefile_single_param -j 8 benchmark_str_encoding_only

# Block sizes only
snakemake -s workflow/Snakefile_single_param -j 8 benchmark_block_size_only

# Block-specific tests only
snakemake -s workflow/Snakefile_single_param -j 8 benchmark_block_specific_only
```

### With Custom Configuration

```bash
snakemake -s workflow/Snakefile_single_param --configfile workflow/config_single_param.yaml -j 8
```

### Dry Run

```bash
snakemake -s workflow/Snakefile_single_param -n
```

---

## Output Files

### Directory Structure

```
results/benchmark/
├── int_encoding/
│   └── {dataset}/
│       ├── identity.csv
│       ├── identity.bgfa
│       ├── varint.csv
│       ├── varint.bgfa
│       └── ... (19 encodings)
├── str_encoding/
│   └── {dataset}/
│       ├── identity.csv
│       ├── zstd.csv
│       └── ... (15 encodings)
├── block_size/
│   └── {dataset}/
│       ├── 64.csv
│       ├── 128.csv
│       └── ... (10 sizes)
├── block_specific/
│   └── {dataset}/
│       ├── segments_identity_identity.csv
│       ├── segments_varint_zstd.csv
│       └── ...
└── summary-single-parameter.csv.zstd
```

### Summary File

The `summary-single-parameter.csv.zstd` file concatenates all benchmark results:

```bash
# Decompress to view
zstd -d results/benchmark/summary-single-parameter.csv.zstd -o summary.csv

# Or view directly
zstd -d -c results/benchmark/summary-single-parameter.csv.zstd | less
```

### CSV Format

Each CSV file contains block-level statistics:

| Column | Description |
|--------|-------------|
| `original_gfa` | Path to source GFA file |
| `filename` | BGFA filename |
| `block_type` | Block type (header/segment_names/segments/links/paths/walks) |
| `block_index` | Block number (0-indexed) |
| `block_size` | Records per block |
| `record_count` | Records in this block |
| `offset_start` | Start byte offset |
| `offset_end` | End byte offset |
| `size_bytes` | Total block size |
| `compression_ratio` | compressed/uncompressed |
| `encoding_high` | Integer encoding hex code |
| `encoding_low` | String encoding hex code |
| `compressed_size` | Compressed payload size |
| `uncompressed_size` | Original payload size |

---

## Adding New Test Data

To include a new GFA file in the benchmarks:

### 1. Add Benchmark Comments

At the beginning of the GFA file, add one or more benchmark comments:

```gfa
# test: your_test_name
# benchmark: single_param
# benchmark: int_encoding
# benchmark: str_encoding
# benchmark: block_size
# benchmark: block_specific
H	VN:Z:1.0
S	1	ATCG
...
```

### 2. Quick Options

| Comment | Effect |
|---------|--------|
| `# benchmark: single_param` | Includes file in ALL single-parameter benchmarks |
| `# benchmark: int_encoding` | Includes only in integer encoding benchmark |
| `# benchmark: str_encoding` | Includes only in string encoding benchmark |
| `# benchmark: block_size` | Includes only in block size benchmark |
| `# benchmark: block_specific` | Includes only in block-specific benchmark |

### 3. Verify Detection

```bash
# List files for a specific benchmark
pixi run python test/benchmark_filter.py --list --benchmark-name int_encoding

# List all single-param benchmark files
pixi run python test/benchmark_filter.py --list --benchmark-name int_encoding
pixi run python test/benchmark_filter.py --list --benchmark-name str_encoding
pixi run python test/benchmark_filter.py --list --benchmark-name block_size
pixi run python test/benchmark_filter.py --list --benchmark-name block_specific
```

---

## Interpreting Results

### Compression Ratio

Lower `compression_ratio` is better:
- `< 0.5`: Excellent compression (50%+ size reduction)
- `0.5 - 0.8`: Good compression
- `0.8 - 1.0`: Modest compression
- `1.0`: No compression (identity)

### Best Practices

1. **Start with single-param benchmarks** to understand individual encoding performance
2. **Use block-specific results** to choose different encodings for different block types
3. **Combine best performers** in the full-factorial benchmark (`bgfa_compression`)
4. **Consider speed vs. compression** - some encodings (zstd, lz4) are faster than others (lzma, ppm)

### Example Analysis

```bash
# Find best integer encoding for compression ratio
zstd -d -c results/benchmark/summary-single-parameter.csv.zstd | \
  awk -F',' 'NR>1 {sum+=$10; count++} END {print $1, sum/count}' | \
  sort -k2 -n | head -5

# Find best string encoding
zstd -d -c results/benchmark/summary-single-parameter.csv.zstd | \
  grep "str_encoding" | \
  awk -F',' '{print $2, $10}' | \
  sort -t'/' -k2 -n | head -5
```

---

## Comparison with Full-Factorial Benchmark

| Aspect | Single-Parameter | Full-Factorial (`bgfa_compression`) |
|--------|------------------|-------------------------------------|
| Combinations per dataset | 19 + 15 + 10 + ~40 = ~84 | 19 × 15 = 285 |
| Total runs (3 datasets) | ~252 | ~855 |
| Purpose | Isolate individual effects | Find optimal combinations |
| Time | Faster | Slower |
| Output | Separate directories | Combined in benchmark_type/ |

Use single-parameter benchmarks for exploration, then validate combinations with full-factorial.
