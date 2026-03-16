# AGENTS.md - Guide for AI Coding Agents

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

# Guidelines specific for the pygfa codebase.

## Project Overview

pygfa is a Python library for managing GFA (Graphical Fragment Assembly) files used in bioinformatics to represent pangenome graphs. The library uses:
- **Python**: >= 3.14
- **Build system**: hatchling (via pyproject.toml)
- **Dependency management**: pixi only
- **Key dependencies**: networkx, lark, biopython, numpy

## Build, Lint, and Test Commands

## Environment

This project is inside a pixi environment, therefore all commands should be
prefixed by 
```pixi run```


### Installation

```bash
# Install in editable mode
pip install -e .

# Using pixi (preferred for dev)
pixi install
```

### Running Tests

All commands output to terminal for immediate debugging visibility.

```bash
# Run all tests (verbose, full trace, no capture)
pixi run python -m pytest test/ -v -s --full-trace --tb=long

# Run specific test file with maximum detail
pixi run python -m pytest test/test_graph_element.py -v -s --full-trace --tb=long

# Run single test with full context
pixi run python -m pytest test/test_graph_element.py::TestGraphElement::test_node -v -s --full-trace --tb=long

# Run tests showing all output (no capture) for debugging print statements
pixi run python -m pytest test/test_encoding.py -v -s --full-trace

# Run with debug logging enabled
pixi run python -m pytest test/ -v -s --full-trace --tb=long --log-cli-level=DEBUG
```

All tests must pass.

The input files for each test are in the `/data` directory.

Each `*.gfa*` file has one or more comments of the form `# test: TESTNAME` where `TESTNAME` is the filename of the
`/test` directory containing some tests. The comment `# test: TESTNAME` means that the gfa file must be used as a test
case of the `/test/test_TESTNAME.py` or the `/test/TESTNAME.py` script.
Those comments must be at the beginning of the file.
There can be multiple such comments in each gfa file.

### Running Tests on Specific GFA Files

Tests that operate on GFA files can be run on a specific file or all matching files:

```bash
# Run test on all GFA files with matching # test: comment (auto-discover)
python test/test_compression.py

# With pytest - run on specific file
pytest test/test_bgfa.py --gfa-file data/test_compression.gfa -v

# With pytest - run on all matching files
pytest test/test_bgfa.py -v

# With pytest - run on specific file for roundtrip tests
pytest test/test_bgfa_roundtrip.py --gfa-file data/test_compression.gfa -v
```

### Development Tools

```bash
# Run the demo script
python demo.py

# Run compression utility
python compress.py -f <gfa_file>
```

## Benchmark System

The benchmark system allows filtering GFA files based on `# benchmark: NAME` comments and running automated benchmarks.

### Output Locations

All benchmark outputs are stored in `results/benchmark/`:
- Individual benchmark results: `results/benchmark/{benchmark_type}/{dataset}/`
- Combined results: `results/benchmark/summary.csv.zstd`

### Benchmark Comments

Add benchmark comments to GFA files:
```gfa
# benchmark: bgfa_compression
H	VN:Z:1.0
S	1	AT
```

- `# benchmark: NAME`: File used only for benchmark `NAME`
- `# benchmark:` (no name): File used for ALL benchmarks
- Comments must be at file beginning (only other comments can precede)
- Files can have multiple benchmark comments

### Usage

```bash
# List all benchmark files
pixi run python test/benchmark_filter.py --list

# Filter by benchmark name
pixi run python test/benchmark_filter.py --list --benchmark-name bgfa_compression

# Generate Snakemake configuration
pixi run python test/benchmark_filter.py --config --benchmark-name bgfa_compression

# Run benchmark workflow
pixi run snakemake -s workflow/Snakefile --configfile workflow/config.yaml -j 8
```


## Code Style Guidelines

### Imports

- Use absolute imports: `from pygfa.graph_element import node`
- Avoid wildcard imports (`from module import *`) except in `__init__.py` for public API
- Group imports: stdlib first, then third-party, then local
- Use `from __future__ import annotations` for Python 3.7+ compatibility
- Use `TYPE_CHECKING` guard for imports only needed for type hints

```python
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pygfa.gfa import GFA

import networkx as nx
import lark
```

### Naming Conventions

- **Classes**: PascalCase (e.g., `GFA`, `InvalidNodeError`, `Edge`)
- **Functions/methods**: snake_case (e.g., `from_line`, `is_node`)
- **Variables**: snake_case (e.g., `node_id`, `opt_fields`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `GRAPH_LOGGER`)
- **Private attributes**: Leading underscore (e.g., `_graph`, `_nid`)
- **Type variables**: PascalCase (e.g., `T`, `U`)

### Type Hints

- Use type hints for function signatures when clear
- Use `Optional[T]` instead of `T | None` for compatibility
- Return types should be specified for public methods
- No strict enforcement - use hints where they add clarity
- No type hints for tests

### Error Handling

- Create custom exception classes for domain errors:
  ```python
  class InvalidNodeError(Exception):
      pass
  ```
- Use specific exceptions rather than generic `Exception`
- Validate inputs early and raise descriptive errors
- Use f-strings for error messages: `f"Invalid value: {value}"`

### Code Structure

- One class per file unless tightly related (exceptions can be grouped)
- Keep files under 500 lines when possible
- Use properties for attribute access with validation
- Use `@classmethod` for alternative constructors (e.g., `from_line`)
- Private methods use leading underscore: `_helper_method()`

### Docstrings

Use Google-style docstrings for public classes and methods:

```python
class Node:
    """A Node object that abstracts the GFA1 Sequence concept.

    GFA graphs will operate on Nodes by adding them directly to their
    structures.

    :param node_id: A node id given as a string.
    :param sequence: A GFA1 sequence.
    :param length: The length of the sequence. Can be `None`.
    :raises InvalidNodeError: If node_id or sequence are invalid.
    """

    def __init__(self, node_id, sequence, length, opt_fields={}):
        # ...
```

### Lint

Always run `pixi run ruff check` and incorporate all its suggestions. The code must be lint clean.
The exceptions are the suggestions involving snakemake, since we use the global snakemake, not one inside pixi.

### Specification

The complete description of the BGFA format is in the file `spec/gfa_binary_format.md`

### Environment

This project will run only on Linux and MacOS systems. Drop any support for Windows

### Testing

-  After a code change, you MUST NOT run any test. The exception is, if the code change originates from a test failure,
   run only the failed test and no other tests.
-  Tests use `unittest.TestCase`
-  Put tests in `test/` directory with `test_*.py` naming
-  Tests add `../` to `sys.path` for imports
-  Use descriptive test method names: `test_node_creation_with_valid_input`
-  Use `assertRaises` for error cases

### Logging

Use module-level loggers:

```python
import logging

GRAPH_LOGGER = logging.getLogger(__name__)
```

*  Use '-v' to activate the default INFO log level option
*  Use '-d' to activate the DEBUG log level option. If both `-d` and `-v` options are given, we activate `-d`

### Graph Element Pattern

Graph elements (Node, Edge, Subgraph) follow a consistent pattern:

1. Validate inputs in `__init__`
2. Use `@property` for read-only attributes
3. Provide `from_line(cls, line)` class method for parsing
4. Implement `__eq__` and `__str__`
5. Raise custom exceptions for validation errors

### Common Patterns

- Virtual IDs for edges without explicit IDs: `virtual_#`
- Use `networkx.MultiGraph` as base structure
- Use lark for parsing GFA line formats

