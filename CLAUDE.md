# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

pygfa is a Python library for managing GFA (Graphical Fragment Assembly) files used in bioinformatics to represent pangenome graphs. It supports GFA1/GFA2 formats with binary BGFA serialization and compression.

## Build and Test Commands

All commands must be prefixed with `pixi run` (project uses pixi environment):

```bash
# Run all tests
pixi run python -m pytest test/

# Run single test file
pixi run python -m pytest test/test_graph_element.py -v

# Run specific test
pixi run python -m pytest test/test_graph_element.py::TestGraphElement::test_node -v

# Linting
pixi run ruff check pygfa/

# Type checking
pixi run mypy pygfa/

# Formatting
pixi run ruff format pygfa/
```

## Architecture

### Core Components

- **`pygfa/gfa.py`** - Main `GFA` class built on `networkx.MultiGraph`. Central interface for all graph operations.
- **`pygfa/graph_element/`** - Core abstractions (Node, Edge, Subgraph) with parser submodule using Lark grammar (`gfa.lark`)
- **`pygfa/serializer/`** - GFA1/GFA2 output formatting
- **`pygfa/bgfa.py`** - Binary GFA serialization
- **`pygfa/encoding/`** - Compression algorithms (varint, delta, zstd, gzip, lzma, Huffman)
- **`pygfa/algorithms/`** and **`pygfa/dovetail_operations/`** - Graph traversal and path algorithms

### Key Design Patterns

- **Duck typing**: Use `is_node()`, `is_edge()`, `is_subgraph()` predicates instead of `isinstance()`
- **Virtual IDs**: Auto-generated `virtual_#` IDs for edges without explicit identifiers
- **Class methods for parsing**: `from_line(cls, line)` pattern on all graph elements
- **Lark parser**: GFA syntax defined in `pygfa/graph_element/parser/gfa.lark`

### GFA Line Types

GFA1: H (header), S (segment), L (link), C (containment), P (path)
GFA2: adds E (edge), G (gap), F (fragment), O/U (groups), W (walk)

## Code Style

- Line length: 100 characters
- Type hints: use `Optional[T]` over `T | None`
- Custom exceptions for domain errors (e.g., `InvalidNodeError`)
- Google-style docstrings with `:param`, `:return`, `:raises`
- Module-level loggers: `GRAPH_LOGGER = logging.getLogger(__name__)`
- Logging flags: `-v` for INFO, `-d` for DEBUG
