# BGFA Benchmarking Snakemake Workflow

This workflow benchmarks all combinations of BGFA encoding strategies on GFA files.

## Overview

- **110 combinations**: 11 integer encodings × 5 string encodings × 2 GFA files
- **Parallel execution**: Use `-j N` to run N jobs in parallel
- **Incremental**: Only re-runs failed/missing combinations
- **Output**: `benchmark/summary.tsv` with compression and timing statistics

## Usage

### Run the full benchmark

```bash
# From pygfa directory
snakemake -s workflow/Snakefile -j 8

# Dry run (preview what will be executed)
snakemake -s workflow/Snakefile -n

# Run with all available cores
snakemake -s workflow/Snakefile -j $(nproc)

# Use custom configuration file
snakemake -s workflow/Snakefile -j 8 --configfile workflow/config.yaml

# Run with custom output directory
snakemake -s workflow/Snakefile -j 8 --config output_dir=results
```

### Run specific combinations

```bash
# Test single encoding combination
snakemake -s workflow/Snakefile benchmark/medium_example/varint_zstd.stats.tsv

# Test all combinations for one dataset
snakemake -s workflow/Snakefile -j 4 --until aggregate_results --forceall
```

### Clean outputs

```bash
# Remove all generated files
snakemake -s workflow/Snakefile --delete-all-output

# Remove specific outputs
rm -rf benchmark/
```

## Integration with Global Workflow

This workflow can be included in a parent Snakemake workflow:

```python
# In global Snakefile
module pygfa_benchmark:
    snakefile: "pygfa/workflow/Snakefile"

use rule * from pygfa_benchmark as pygfa_*
```

Or via simple inclusion:

```python
include: "pygfa/workflow/Snakefile"
```

## Workflow Structure

```
workflow/
├── Snakefile              # Main workflow definition
├── scripts/
│   ├── benchmark_encode.py    # Encode GFA → BGFA with timing
│   ├── benchmark_decode.py    # Decode BGFA → GFA with timing
│   └── compute_stats.py       # Compute compression statistics
└── README.md              # This file

benchmark/                 # Output directory (created by workflow)
├── <dataset>/
│   ├── <int_enc>_<str_enc>.bgfa
│   ├── <int_enc>_<str_enc>.encode_time.txt
│   ├── <int_enc>_<str_enc>.decode_time.txt
│   └── <int_enc>_<str_enc>.stats.tsv
└── summary.tsv           # Final aggregated results
```

## Configuration

Edit `workflow/Snakefile` to customize:

- **`DATASETS`**: Add/remove GFA files to benchmark
- **`INT_ENCODINGS`**: Integer encoding strategies
- **`STR_ENCODINGS`**: String encoding strategies

## Output Format

The `benchmark/summary.tsv` file contains:

| Column | Description |
|--------|-------------|
| dataset | Dataset name (without .gfa extension) |
| int_encoding | Integer encoding strategy (none, varint, etc.) |
| str_encoding | String encoding strategy (none, zstd, etc.) |
| gfa_bytes | Original GFA file size in bytes |
| bgfa_bytes | Compressed BGFA file size in bytes |
| compression_ratio | Ratio (bgfa_bytes / gfa_bytes) |
| encode_seconds | Time to encode GFA → BGFA |
| decode_seconds | Time to decode BGFA → GFA |

Error values are marked as "ERROR" in the respective column.

## Advantages over bash script

1. **Parallelization**: Run multiple combinations simultaneously
2. **Incremental**: Only re-run failed combinations
3. **Dependency tracking**: Automatic handling of file dependencies
4. **Integration**: Part of larger pangenome workflow ecosystem
5. **Reproducibility**: Declarative workflow definition
6. **Error recovery**: Failed jobs don't block others
7. **Intermediate files**: Preserved for analysis (not deleted like in bash script)

## Requirements

- Snakemake (installed globally or via conda/mamba)
- pixi environment (for running bgfatools)
- GFA files in `data/` directory

## Migration from bash script

This workflow replaces `bin/benchmark_bgfa.sh`. Key differences:

- **Parallelization**: Bash script was sequential; Snakemake runs jobs in parallel
- **Intermediate files**: Bash script deleted BGFA files; Snakemake preserves them
- **Error handling**: Both mark errors gracefully without stopping the workflow
- **Output format**: Same TSV format for compatibility
