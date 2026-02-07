# BGFA Benchmark Workflow - Usage Examples

## Basic Usage

### Run complete benchmark (110 combinations)

```bash
# Using all CPU cores
snakemake -s workflow/Snakefile -j $(nproc)

# Using 8 cores
snakemake -s workflow/Snakefile -j 8

# Single core (sequential)
snakemake -s workflow/Snakefile -j 1
```

### Preview what will run (dry run)

```bash
snakemake -s workflow/Snakefile -n
```

### View workflow summary

```bash
snakemake -s workflow/Snakefile --summary
```

### Generate workflow visualization

```bash
# Requires graphviz
snakemake -s workflow/Snakefile --dag | dot -Tpng > workflow_dag.png
```

## Incremental Execution

One of the main advantages of Snakemake is incremental execution. If a job fails or you interrupt the workflow, you can resume where you left off:

```bash
# Run benchmark
snakemake -s workflow/Snakefile -j 8

# Workflow interrupted or some jobs failed...

# Resume - only missing/failed jobs will run
snakemake -s workflow/Snakefile -j 8
```

## Selective Execution

### Test single encoding combination

```bash
# Test none_none encoding on medium_example dataset
snakemake -s workflow/Snakefile \
    benchmark/medium_example/none_none.stats.tsv -j 1

# Test varint_zstd encoding
snakemake -s workflow/Snakefile \
    benchmark/atcc_staggered.assembly_graph_with_scaffolds/varint_zstd.stats.tsv -j 1
```

### Test all combinations for one dataset

```bash
# Create a custom config with only one dataset
cat > workflow/test_config.yaml <<EOF
datasets:
  medium_example: data/medium_example.gfa
int_encodings:
  - none
  - varint
str_encodings:
  - none
  - zstd
EOF

# Run with custom config (4 combinations only)
snakemake -s workflow/Snakefile -j 4 --configfile workflow/test_config.yaml
```

### Test subset of encodings

```bash
# Edit config.yaml to include only desired encodings
cat > workflow/test_config.yaml <<EOF
datasets:
  medium_example: data/medium_example.gfa
int_encodings:
  - none
  - varint
  - delta
str_encodings:
  - none
  - zstd
EOF

snakemake -s workflow/Snakefile -j 4 --configfile workflow/test_config.yaml
```

## Re-running Failed Jobs

If some combinations fail (e.g., decode errors), you can:

1. **View failed jobs:**
   ```bash
   grep ERROR benchmark/summary.tsv
   ```

2. **Force re-run specific job:**
   ```bash
   # Remove output files for failed combination
   rm benchmark/medium_example/varint_zstd.*

   # Re-run
   snakemake -s workflow/Snakefile \
       benchmark/medium_example/varint_zstd.stats.tsv -j 1
   ```

3. **Force re-run all:**
   ```bash
   snakemake -s workflow/Snakefile -j 8 --forceall
   ```

## Cleaning Outputs

### Remove all benchmark results

```bash
snakemake -s workflow/Snakefile --delete-all-output
```

### Manual cleanup

```bash
# Remove specific dataset results
rm -rf benchmark/medium_example/

# Remove entire benchmark directory
rm -rf benchmark/

# Clean Snakemake metadata
rm -rf .snakemake/
```

## Debugging

### Verbose output

```bash
snakemake -s workflow/Snakefile -j 1 --verbose
```

### Print shell commands

```bash
snakemake -s workflow/Snakefile -j 1 --printshellcmds
```

### Keep going on errors

```bash
# Don't stop on first error, run as many jobs as possible
snakemake -s workflow/Snakefile -j 8 --keep-going
```

### Detailed reason for re-running

```bash
snakemake -s workflow/Snakefile -n --reason
```

## Production Workflow

### Complete benchmark with error handling

```bash
#!/bin/bash
# production_benchmark.sh

# Run with all cores, continue on errors, verbose output
snakemake -s workflow/Snakefile \
    -j $(nproc) \
    --keep-going \
    --printshellcmds \
    2>&1 | tee benchmark_log.txt

# Generate summary report
echo "=== Benchmark Summary ==="
echo "Total combinations: $(tail -n +2 benchmark/summary.tsv | wc -l)"
echo "Successful: $(grep -v ERROR benchmark/summary.tsv | tail -n +2 | wc -l)"
echo "Failed: $(grep ERROR benchmark/summary.tsv | wc -l)"

# Display results
column -t -s $'\t' benchmark/summary.tsv | head -20
```

## Custom Output Directory

```bash
# Use custom output location
snakemake -s workflow/Snakefile -j 8 \
    --config output_dir=results/run_$(date +%Y%m%d)
```

## Integration with Global Workflow

If you have a global Snakemake workflow, include this as a module:

```python
# In global Snakefile at /home/gianluca/Devel/pangenome/Snakefile

module pygfa_benchmark:
    snakefile: "pygfa/workflow/Snakefile"
    config: config

use rule * from pygfa_benchmark as pygfa_*

# Then run from global directory:
# snakemake -j 8 pygfa_benchmark
```

## Performance Tuning

### Estimate resource usage

```bash
# Dry run with timing
time snakemake -s workflow/Snakefile -n

# Actual run time (1 job)
time snakemake -s workflow/Snakefile -j 1

# Parallel speedup (8 jobs)
time snakemake -s workflow/Snakefile -j 8
```

### Monitor progress

```bash
# In separate terminal
watch -n 1 'find benchmark/ -name "*.stats.tsv" | wc -l'

# Or with more detail
watch -n 2 'echo "Progress: $(find benchmark/ -name "*.stats.tsv" | wc -l)/110 combinations complete"'
```

## Troubleshooting

### Workflow is locked

```bash
# If previous run was interrupted
snakemake -s workflow/Snakefile --unlock
```

### Permission errors

```bash
# Ensure output directory is writable
mkdir -p benchmark
chmod 755 benchmark
```

### Missing input files

```bash
# Verify GFA files exist
ls -lh data/*.gfa
```

### Python/pixi environment issues

```bash
# Test bgfatools manually
pixi run python bin/bgfatools --help

# Verify pixi environment
pixi info
```
