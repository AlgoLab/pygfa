# pygfa

A Python library for managing GFA (Graphical Fragment Assembly) files used in bioinformatics to represent pangenome graphs.

## Features

- **GFA1 Support**: Read, write, and manipulate GFA1 format files (including 1.1 and 1.2)
- **Graph Operations**: Connected components, path finding, traversal algorithms
- **Serialization**: Convert to GFA1 format and binary BGFA format
- **Compression**: Optional zstd, gzip, and lzma compression for large graphs
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

The Snakemake workflow now **automatically discovers** all GFA files with benchmark comments in the `/data` directory:

```bash
# 1. Add benchmark comments to your GFA files (e.g., at the top):
# # benchmark: bgfa_compression
# # benchmark: bgfa_roundtrip

# 2. Run benchmarks with automatic discovery:
snakemake -s workflow/Snakefile -j 8

# 3. Dry run to see discovered datasets:
snakemake -s workflow/Snakefile -n
```

**Features**:
- 🔍 **Dynamic discovery**: Finds all GFA files with `# benchmark:` comments automatically
- 🏷️ **Combined naming**: Files with multiple benchmark comments get combined names (e.g., `file_bgfa_compression_bgfa_roundtrip`)
- 📁 **Benchmark-type directories**: Output organized by benchmark type (`benchmark/bgfa_compression/dataset/`, `benchmark/bgfa_roundtrip/dataset/`)
- ✅ **Early validation**: Comprehensive error checking before execution
- 🌐 **Universal benchmarks**: Files with `# benchmark:` appear in ALL benchmark types

**No more manual configuration files needed** - the workflow automatically discovers and structures benchmark runs based on file comments!

See `docs/benchmark_system.md` for detailed documentation.

## Architecture

The project follows a modular architecture organized around core graph concepts:

```
pygfa/
├── gfa.py               # Main GFA class - core graph data structure (NetworkX MultiGraph)
├── bgfa.py              # Binary GFA format support
├── operations.py        # Graph operations (connected components)
├── graph_element/       # Graph element representations
│   ├── node.py          # Node (segment) representation
│   ├── edge.py          # Edge (link/containment) representation
│   ├── subgraph.py      # Subgraph/path representation
│   └── parser/          # GFA line parsers using Lark grammar
├── graph_operations/    # Graph algorithms (compression, overlap consistency)
├── algorithms/          # Graph traversal algorithms
├── serializer/          # Output format serializers (GFA1)
└── encoding/            # Data encoding utilities
```

### Key Components

- **GFA Class**: Central graph container using NetworkX MultiGraph as the underlying structure. Manages nodes, edges, paths, walks, and subgraphs.
- **Graph Elements**: Node (segments), Edge (links/containments), and Subgraph (paths/groups) abstractions
- **Parser**: Uses Lark grammar to parse GFA1 format files
- **BGFA**: Binary GFA format for efficient storage with zstd compression
- **Operations**: Graph analysis including connected components and path finding

### Data Flow

```
GFA File → Lark Parser → Graph Elements → GFA Class (NetworkX) → Operations/Serialization
                                    ↓
                              BGFA Binary Format
```

## License

BSD-3-Clause
