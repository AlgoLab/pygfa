# Architecture

This file documents the high-level architecture of pygfa — a Python library for managing GFA (Graphical Fragment Assembly) files used in bioinformatics to represent pangenome graphs.

---

## Directory Layout

| Path | Responsibility |
|---|---|
| `pygfa/` | **Library package.** Public API in `__init__.py`, core graph model, I/O, compression codecs. |
| `pygfa/gfa/` | **GFA graph model** — `BaseGFA` (networkx storage), `GFAElementsMixin` (CRUD), `GFAQueryMixin` (search), `GFAParserMixin` (text/binary parsing). `__init__.py` assembles the final `GFA` class via multiple inheritance. |
| `pygfa/graph_element/` | **Element dataclasses** — `Node`, `Edge`, `Path`, `Walk`, `Subgraph` (frozen, `__slots__`). Each has a `from_line()` classmethod and validation in `__post_init__`. |
| `pygfa/graph_element/parser/` | **Lark grammar** (`gfa.lark`) + per-line-type parser classes (`SegmentV1`, `Link`, `Containment`, `Path`, `Header`), field validation regexes (`field_validator.py`), and the `Line`/`Field`/`OptField` base types. |
| `pygfa/bgfa/` | **Binary GFA (BGFA) format** — `_reader.py` (`ReaderBGFA`, `read_bgfa`, `measure_bgfa`), `_writer.py` (`BGFAWriter`, `to_bgfa`), `_validation.py` (`validate_bgfa`, `dump_bgfa`), `_codec_utils.py` (bit-packing), `_constants.py` (magic bytes, section IDs, encoding constants). |
| `pygfa/encoding/` | **27 compression modules** — integer codecs (varint, delta, streamvbyte, simple8b, pfor_delta, etc.), string codecs (zstd, gzip, lzma, lz4, brotli, huffman, 2bit_dna, arithmetic, bwt_huffman, rle, dictionary, ppm, etc.), enums, heuristics for auto-selection. |
| `pygfa/algorithms/` | **Graph traversal** — `all_simple_paths()` (MultiGraph-aware, custom edge selectors), `dfs_edges()`. |
| `pygfa/graph_operations/` | **Graph transformations** — `compression.py` (merges degree-2 nodes), `overlap_consistency.py` (validates CIGAR vs. real sequence overlap). |
| `pygfa/utils/` | **I/O helpers** — `open_gfa_file()` (transparent .gfa/.gz/.zst/.xz), `sanitize_string()`, `output_manager.py`. |
| `test/` | **Test suite** — ~44 files organized by area (parsing, elements, BGFA roundtrip, encoding, tools). Tests use `unittest.TestCase`. |
| `data/` | **Test input files** — GFA files with `# test: <name>` / `# benchmark: <name>` comments driving auto-discovery. |
| `bin/` | **CLI tool** — `bin/bgfatools` (GFA↔BGFA conversion, measure, validate, dump). |
| `tools/` | **Utility scripts** — `canonical_gfa.py`, `prettify_gfa.py`, `same_gfa.py`. |
| `workflow/` | **Snakemake benchmark pipeline** — Single-parameter sweeps over encoding strategies, parallel execution, zstd-compressed summary. |

---

## Key Types and Relationships

### Core Class Hierarchy

```
object
  └── BaseGFA                  (gfa/base.py)  — networkx.MultiGraph storage, virtual IDs, iteration
       ├── GFAElementsMixin    (gfa/elements.py) — add/remove/query nodes, edges, paths, subgraphs, walks
       ├── GFAQueryMixin      (gfa/query.py) — neighbors(), search(), subgraph()
       └── GFAParserMixin      (gfa/parser.py) — from_gfa(), to_gfa(), from_bgfa(), to_bgfa(), pprint()

GFA (GFAElementsMixin + GFAQueryMixin + GFAParserMixin)  (gfa/__init__.py)
```

### Element Dataclasses (all frozen with `__slots__`)

| Class | File | Key Attributes | Stored In |
|---|---|---|---|
| `Node` | `graph_element/node.py` | `node_id`, `sequence`, `sequence_length`, `opt_fields` | networkx node attributes |
| `Edge` | `graph_element/edge.py` | `edge_id`, `from_node`, `from_orientation`, `to_node`, `to_orientation`, `alignment`, `distance`, `variance`, `opt_fields` | networkx edges (key = edge_id) |
| `Path` | `graph_element/path.py` | `path_id`, `segment_ids`, `overlaps`, `opt_fields` | `GFA._paths` dict |
| `Walk` | `graph_element/walk.py` | `walk_id`, `sample_id`, `haplotype_index`, `sequence_id`, `start`, `end`, `segment_ids`, `opt_fields` | `GFA._walks` dict |
| `Subgraph` | `graph_element/subgraph.py` | `sub_id`, `elements` (OrderedDict), `opt_fields` | `GFA._subgraphs` dict |

### Exception Hierarchy (`pygfa/exceptions.py`)

```
GFAError
  ├── InvalidNodeError
  ├── InvalidEdgeError
  ├── InvalidPathError / InvalidWalkError / InvalidSubgraphError
  ├── InvalidLineError / InvalidElementError
  ├── InvalidSearchParameters
  ├── InvalidEncodingError / InvalidCompressionError
  ├── FileFormatError
  └── DictionaryTrainingError
```

### BGFA Section Types (`pygfa/bgfa/_constants.py`)

- `SECTION_ID_SEGMENTS = 2`, `SECTION_ID_LINKS = 3`, `SECTION_ID_PATHS = 4`, `SECTION_ID_WALKS = 5`
- Encoding codes packed into 4-byte codes via `make_4byte_code()` / `split_4byte_code()`

### Integer Encoding Enum (`pygfa/encoding/enums.py`)

`IntegerEncoding`: `NONE`, `VARINT`, `FIXED16/32/64`, `DELTA`, `ELIAS_GAMMA`, `ELIAS_OMEGA`, `GOLOMB`, `RICE`, `STREAMVBYTE`, `VBYTE`, `PFOR_DELTA`, `SIMPLE8B`, `GROUP_VARINT`, `BIT_PACKING`, `FIBONACCI`, `EXP_GOLOMB`, `BYTE_PACKED`, `MASKED_VBYTE`

### String Encoding Enum (`pygfa/encoding/enums.py`)

`StringEncoding`: `NONE`, `IDENTITY`, `ZSTD`, `ZSTD_DICT`, `GZIP`, `LZMA`, `LZ4`, `BROTLI`, `HUFFMAN`, `NIBBLE_HUFFMAN`, `TWO_BIT_DNA`, `ARITHMETIC`, `BWT_HUFFMAN`, `RLE`, `DICTIONARY`, `PPM`, `FRONTCODING`, `DELTA`

---

## Control Flow

### Loading GFA (text or binary)

```
[.gfa file] -> pygfa.io.load() -> check extension
  +-- .gfa -> GFAParserMixin.from_gfa()
  |    -> Lark grammar (gfa.lark) -> per-type parsers (SegmentV1, Link, ...)
  |    -> element dataclass (Node, Edge, ...)
  |    -> GFAElementsMixin.add_*() -> GFA object
  +-- .bgfa -> ReaderBGFA.read_bgfa()
       -> parse header -> decompress section blocks -> reconstruct elements -> GFA object
```

### Saving GFA (text or binary)

```
[GFA object]
  +-- to_gfa() -> sort elements canonically -> serialize to text lines -> .gfa file
  +-- to_bgfa() -> BGFAWriter.encode_header()
       -> encode + compress each section block (segments/links/paths/walks)
       -> per-field compression using chosen strategy -> .bgfa file
```

### CLI Subcommand Dispatch (`bin/bgfatools`)

| Subcommand | Action | Key Library Call |
|---|---|---|
| `bgfa` | GFA -> BGFA | `GFA.from_gfa(in)` -> `GFA.to_bgfa(out, comp_options)` |
| `cat` | BGFA -> GFA (text) | `GFA.from_bgfa(in)` -> `gfa.to_gfa()` |
| `measure` | Block statistics -> CSV | `pygfa.bgfa.measure_bgfa(path)` |
| `validate` | Validate structure -> JSON | `pygfa.bgfa.validate_bgfa(path)` |
| `dump` | Human-readable dump | `pygfa.bgfa.dump_bgfa(path)` |
| `show-full-encodings` | List available codecs | `pygfa.encoding.show_full_encodings()` |

---

## Data Flow

### Encoding Pipeline (per-field in BGFA)

```
raw values (strings or integers)
  -> IntegerEncoding.compress() / StringEncoding.compress()
  -> compressed bytes
  -> IntegerEncoding.decompress() / StringEncoding.decompress()
  -> reconstructed values
```

### Auto-Encoding Heuristic (`pygfa/encoding/heuristic.py`)

`select_encoding(data, context)` samples data, measures compression ratio for each available codec, picks the best. Used when no explicit strategy is given.

### Graph Compression (`pygfa/graph_operations/compression.py`)

`compression_graph_by_nodes()` / `compression_graph_by_edges()` iteratively merges degree-2 nodes, updating sequences, CIGAR strings, and orientations — reducing graph complexity while preserving topology.

---

## Design Decisions

1. **networkx.MultiGraph as backbone** — Reuses a mature graph library for traversal, isomorphism, connected components. MultiGraph allows parallel edges (multiple links between same nodes with different IDs). Nodes = segments, edges = links/containments.

2. **Multiple inheritance with mixins** — `GFA` assembles from `BaseGFA` (storage), `GFAElementsMixin` (CRUD), `GFAQueryMixin` (search), `GFAParserMixin` (I/O). Separates concerns without deep inheritance chains. Source: `pygfa/gfa/__init__.py`.

3. **Frozen dataclasses with `__slots__`** for elements — Immutable by default (hashable for networkx), memory-efficient, with `__post_init__` validation. Source: `pygfa/graph_element/`.

4. **Parsing via Lark** — Formal grammar (`gfa.lark`) instead of hand-written regex. Enables precise error messages and simpler spec evolution. Source: `pygfa/graph_element/parser/gfa.lark`.

5. **Per-field configurable compression** — Each BGFA payload field uses its own (integer_codec, string_codec) pair. The 4-byte compression code packs integer strategy + string strategy + decomposition. Source: `pygfa/bgfa/_constants.py`.

6. **BGFA binary spec first** — The binary format drove codec design. Codecs in `pygfa/encoding/` are self-contained and independently testable. Source: `pygfa/encoding/__init__.py`.

7. **Tiered test memory requirements** — Roundtrip tests are tagged (`small`, `medium`, `large`) by memory footprint, letting CI skip large tests when constrained. Source: `test/test_bgfa_roundtrip*.py`.

8. **File comment annotations** — GFA files carry `# test: NAME` and `# benchmark: NAME` comments for automatic test/benchmark discovery without external config. Source: `test/test_utils.py`.

9. **pixi-only dependency management** — Uses `pixi` instead of pip/conda directly, pulling from conda-forge + bioconda. Ensures reproducible environments. Source: `pyproject.toml`.

10. **No Windows support** — Project targets Linux and macOS only. All encoding/decoding uses little-endian byte order.

---

## External Dependencies and Usage

| Library | Usage | Source File(s) |
|---|---|---|
| **networkx** | Core graph storage (`MultiGraph`), connected components, DFS | `pygfa/gfa/base.py`, `operations.py`, `algorithms/` |
| **lark** | GFA text format grammar parsing | `pygfa/graph_element/parser/gfa.lark` |
| **biopython** | Reverse complement, FASTA I/O for overlap checking | `pygfa/graph_operations/` |
| **numpy** | Array-backed compression (masked_vbyte, pfor_delta) | `pygfa/encoding/` |
| **zstandard** | ZSTD string compression + dictionary training | `pygfa/encoding/string_encoding.py`, `zstd_dict.py` |
| **lz4** | LZ4 string compression | `pygfa/encoding/lz4_codec.py` |
| **brotli** | Brotli string compression | `pygfa/encoding/brotli_codec.py` |

---

## Entry Points

| Entry Point | Command | Description |
|---|---|---|
| **Library API** | `from pygfa import GFA; gfa = GFA.from_gfa("file.gfa")` | Programmatic usage. Exports: `GFA`, `load`/`save`, `Node`, `Edge`, `Path`, `Walk`, `subgraph`, all exceptions. |
| **CLI — GFA↔BGFA** | `pixi run python bin/bgfatools bgfa in.gfa out.bgfa` | Convert GFA to compressed binary. Per-field encoding flags available. |
| **CLI — BGFA→GFA** | `pixi run python bin/bgfatools cat in.bgfa out.gfa` | Decompress BGFA to GFA text. |
| **CLI — Measure** | `pixi run python bin/bgfatools measure in.bgfa --output stats.csv` | Report per-section block statistics. |
| **CLI — Validate** | `pixi run python bin/bgfatools validate in.bgfa` | Validate BGFA structure + decompression. |
| **CLI — Dump** | `pixi run python bin/bgfatools dump in.bgfa` | Human-readable dump of binary structure. |
| **CLI — Encodings** | `pixi run python bin/bgfatools show-full-encodings` | List all available compression codec combinations. |
| **Demo** | `pixi run python demo.py -f file.gfa` | Quick graph visualization / GFA version conversion. |
| **Compression** | `pixi run python compress.py -f file.gfa` | Simple GFA→BGFA conversion with defaults. |
| **Canonicalize** | `pixi run python tools/canonical_gfa.py in.gfa [out.gfa]` | Re-sort GFA in canonical order. |
| **Pretty-print** | `pixi run python tools/prettify_gfa.py file.gfa` | Structured terminal dump. |
| **Compare** | `pixi run python tools/same_gfa.py f1.gfa f2.gfa` | Compare two GFA files (structural + isomorphism). |
| **Benchmark** | `pixi run snakemake -s workflow/Snakefile -j8` | Sweep encoding strategies, measure size/speed. |

All entry points are thin wrappers over the `pygfa.gfa.GFA` programmatic API. The design ensures the CLI and scripts delegate to the same library functions available to end-user code.
