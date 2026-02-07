# AGENTS.md - Guide for AI Coding Agents

This file provides guidelines for AI agents working on the pygfa codebase.

## Project Overview

pygfa is a Python library for managing GFA (Graphical Fragment Assembly) files used in bioinformatics to represent pangenome graphs. The library uses:
- **Python**: >= 3.14
- **Build system**: hatchling (via pyproject.toml)
- **Dependency management**: pixi and pip
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

```bash
# Run all tests
pixi run python -m pytest test/

# Run a single test file
pixi run python -m pytest test/test_graph_element.py -v

# Run a single test
pixi run python -m pytest test/test_graph_element.py::TestGraphElement::test_node -v

# Run with coverage
pixi run coverage run -p test/run_tests.sh
pixi run coverage combine
pixi run coverage html --omit=/usr/*
```

The input files for each test are in the `/data` directory.

Each `*.gfa*` file has one or more comments of the form `# test: TESTNAME` where `TESTNAME` is the filename of the
`/test` directory containing some tests. The comment `# test: TESTNAME` means that the gfa file must be used as a test
case of the `/test/test_TESTNAME.py` or the `/test/TESTNAME.py` script.
Those comments must be at the beginning of the file.
There can be multiple such comments in each gfa file.


### Development Tools

```bash
# Run the demo script
python demo.py

# Run compression utility
python compress.py -f <gfa_file>
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

### Specification

The complete description of the BGFA format is in the file `../bgfatools/spec/gfa_binary_format.md`

### Environment

This project will run only on Linux and MacOS systems. Drop any support for Windows

### Testing

- Tests use `unittest.TestCase`
- Put tests in `test/` directory with `test_*.py` naming
- Tests add `../` to `sys.path` for imports
- Use descriptive test method names: `test_node_creation_with_valid_input`
- Use `assertRaises` for error cases

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

