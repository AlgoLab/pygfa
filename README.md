# pygfa

A Python library for managing GFA (Graphical Fragment Assembly) files used in bioinformatics to represent pangenome graphs.

## Features

- **Full GFA Support**: Read, write, and manipulate GFA1 and GFA2 format files
- **Graph Operations**: Connected components, path finding, traversal algorithms
- **Serialization**: Convert between GFA1, GFA2, and binary BGFA formats
- **Compression**: Optional zstd, gzip, and lzma compression for large graphs
- **Dovetail Operations**: Specialized operations for overlap-based connections

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

# Serialize to GFA2
gfa2_output = gfa.to_gfa2()
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

## License

BSD-3-Clause
