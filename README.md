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
from pygfa import GFA
from pygfa.graph_element import Node, Edge

# Create a new GFA graph
gfa = GFA()

# Add nodes (segments)
gfa.add_node(Node("s1", "ACGT", 4))
gfa.add_node(Node("s2", "TGCA", 4))

# Add edges (links)
gfa.add_edge(Edge("e1", "s1", "+", "s2", "+", (None, None), (None, None), "2M", None, None))

# Read from file (auto-detects .gfa / .gfa.gz / .gfa.zst / .gfa.xz / .bgfa)
gfa = GFA.from_file("example.gfa")

# Serialize to GFA1 text
gfa1_output = gfa.to_gfa()
```

## Roundtrip fidelity

Everything the BGFA format can represent roundtrips exactly: segment names and
sequences, segment lengths (written as `LN:i:<n>` when the sequence is `*`),
links, orientations, CIGAR strings, path segment lists, **every** overlap of a
path, walks, and optional fields.

One GFA1 field set has no BGFA representation:

- **Edge positions and gap fields** — `from_positions`, `to_positions`,
  `distance`, and `variance` are dropped. This is a **GFA1 text-format
  limitation, not a BGFA gap**: GFA1 `L` lines have no columns for them, and
  `Edge.from_line` hard-codes them to `(None, None)` / `None` for both `L` and
  `C` lines. Only programmatically constructed edges can populate them (GFA2 is
  not supported by this library).

Two further differences are normalizations rather than data loss:

- A path whose overlaps field was absent is written back with the explicit
  GFA1 `*` sentinel.
- `two_bit_dna` normalizes lowercase bases to upper case and `U`/`u` to `T`
  (the 2-bit scheme has no case or U/T bit).

The fidelity guarantees are locked by `test/test_bgfa_snapshots.py` (byte-exact
output plus roundtrip) and `test/test_bgfa_roundtrip.py`; the exclusions it
still needs are listed in `test/snapshots/bgfa/README.md`.

## Documentation

See `AGENTS.md` for development guidelines and `docs/` for API documentation.

See [BGFA specifications](https://github.com/AlgoLab/bgfa-spec/blob/main/gfa_binary_format.md) for the complete
specifications of the binary GFA format.

## Testing

```bash
# Run all tests
python -m pytest test/

# Run with coverage
coverage run -p test/run_tests.sh
coverage html
```

### Encoding per-section tests

Iterates over every legitimate BGFA encoding combination on small GFA files in `data/`, writing each BGFA output and its dump to `results/encodings_per_section/`:

```bash
pixi run python -m pytest test/test_bgfa_encodings_per_section.py -v --tb=short
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

See `BENCHMARK.md` for detailed documentation.

## Architecture

The project follows a modular architecture organized around core graph concepts:

```
pygfa/
├── gfa/                 # GFA class: BaseGFA (NetworkX MultiGraph) + elements/query/parser mixins
├── bgfa/                # Binary GFA (BGFA) reader, writer, and validation
├── io.py                # Unified load/save with format auto-detection
├── operations.py        # Graph operations (connected components)
├── graph_element/       # Graph element representations
│   ├── node.py          # Node (segment) representation
│   ├── edge.py          # Edge (link/containment) representation
│   ├── path.py          # Path representation
│   ├── walk.py          # Walk representation
│   ├── subgraph.py      # Subgraph representation
│   └── parser/          # GFA line parsers using Lark grammar
├── graph_operations/    # Graph algorithms (compression, overlap consistency)
├── algorithms/          # Graph traversal algorithms
├── encoding/            # Data encoding utilities (integer, string, CIGAR codecs)
└── utils/               # File opening (gzip/zstd/xz), string helpers
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
