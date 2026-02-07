# pygfa

A Python library for managing GFA (Graphical Fragment Assembly) files used in bioinformatics to represent pangenome graphs.

## Features

- **GFA1 Support**: Read, write, and manipulate GFA1 format files (including 1.1 and 1.2)
- **Graph Operations**: Connected components, path finding, traversal algorithms
- **Serialization**: Convert to GFA1 format and binary BGFA format
- **Compression**: Optional zstd, gzip, and lzma compression for large graphs
- **Dovetail Operations**: Specialized operations for overlap-based connections
- **Benchmark System**: Filter and run benchmarks on GFA files with `# benchmark: NAME` comments

## Installation

```bash
# Using pip
pip install pygfa

# Using pixi (recommended for development)
pixi install
```

## Quick Start

```python
from pygfa.gfa import GFA

# Create a new GFA graph
gfa = GFA()

# Add nodes (segments)
gfa.add_node(Node("s1", "ACGT", 4))
gfa.add_node(Node("s2", "TGCA", 4))

# Add edges (links)
gfa.add_edge(Edge("e1", "s1", "+", "s2", "+", (None, None), (None, None), "2M", None, None))

# Read from file
gfa.from_file("example.gfa")

# Serialize to GFA1
gfa1_output = gfa.to_gfa1()

# Serialize to GFA1
gfa1_output = gfa.to_gfa1()
```

## Documentation

See `AGENTS.md` for development guidelines and `doc/` for API documentation.

## Testing

```bash
# Run all tests
python -m pytest test/

# Run with coverage
coverage run -p test/run_tests.sh
coverage html
```


### Workflow

1. Add benchmark comments to GFA files
2. Generate configuration: `tools/generate_benchmark_config.py`
3. Run benchmarks: `snakemake -s workflow/Snakefile`

See `docs/benchmark_system.md` for detailed documentation.

## License

BSD-3-Clause
