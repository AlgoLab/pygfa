# Implementation Plan: Encoding Strategy CLI Verification

**Branch**: `001-encoding-cli-options` | **Date**: 2026-03-21 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-encoding-cli-options/spec.md`

## Summary

Create a standalone verification script that tests all 41 encoding strategies (20 integer + 21 string) via roundtrip (encode → decode → compare) on GFA files tagged with `# test: all_encodings`, outputting a human-readable report to stdout with fail-fast behavior.

## Technical Context

**Language/Version**: Python >= 3.14
**Primary Dependencies**: pygfa (existing library), networkx, lark, biopython, numpy, zstandard, lz4, brotli
**Storage**: N/A (file-based, reads GFA/BGFA files from disk)
**Testing**: pytest + unittest.TestCase
**Target Platform**: Linux and macOS only
**Project Type**: CLI tool (standalone script)
**Performance Goals**: Full verification report in under 60 seconds (SC-003)
**Constraints**: Must use pixi for all commands; type-checking before execution (FR-009); only test files tagged with `# test: all_encodings` (FR-010); fail-fast on test failures; test encodings in sequential order by encoding type
**Scale/Scope**: 41 encoding strategies × 18+ field types = 738+ test combinations

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### I. Simplicity First ✅
- Single standalone script, no abstractions for single-use code
- No features beyond what was requested in the spec
- No modifications to existing source code

### II. Test Discipline ✅
- Script follows project conventions: `test/test_*.py` naming
- Uses existing GFA files from `/data` directory
- Implements roundtrip testing (encode → decode → compare)

### III. Specification Compliance ✅
- All encoding strategies tested against documented CLI options
- Fail-fast behavior as specified in clarifications
- Sequential test order by encoding type as specified

### IV. Code Quality ✅
- Will use `pixi run ruff check`
- Google-style docstrings for public functions
- Type hints for public method signatures

### V. Surgical Changes ✅
- Only adding new script to `test/` directory
- Not modifying existing bgfatools code
- Every changed line traces directly to the user's request

## Project Structure

### Documentation (this feature)

```text
specs/001-encoding-cli-options/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # N/A for this feature (CLI tool, no external interfaces)
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
test/
└── test_all_encodings.py    # New: standalone verification script

pygfa/
└── encoding/                # Existing: encoding modules (no changes)
```

**Structure Decision**: Standalone test script in `test/` directory following project conventions. No changes to existing source code.

## Complexity Tracking

> No violations - feature is a standalone script following project conventions.

## Research Notes

### Encoding Strategies to Test

**Integer Encodings (20):**
none, varint, fixed16, fixed32, fixed64, delta, elias_gamma, elias_omega, golomb, rice, streamvbyte, vbyte, pfor_delta, simple8b, group_varint, bit_packing, fibonacci, exp_golomb, byte_packed, masked_vbyte

**String Encodings (21):**
none, zstd, zstd_dict, gzip, lzma, lz4, brotli, huffman, frontcoding, delta, dictionary, rle, cigar, 2bit, arithmetic, bwt_huffman, ppm, superstring_none, superstring_huffman, superstring_2bit, superstring_ppm

### Field Types for Testing

- segment names (names_enc)
- sequences (seq_enc)
- links from/to (links_fromto_enc)
- links cigars (links_cigars_enc)
- paths names (paths_names_enc)
- paths cigars (paths_cigars_enc)
- walks sample IDs (walks_sample_ids_enc)
- walks haplotype indices (walks_hap_indices_enc)
- walks sequence IDs (walks_seq_ids_enc)
- walks start positions (walks_start_enc)
- walks end positions (walks_end_enc)
- walks walk data (walks_walks_enc)

### CLI Option Format

Encoding strategies are specified as `int-str` format, e.g.:
- `--names-enc "varint-none"` for integer-only fields
- `--seq-enc "varint-2bit"` for string fields with combined encoding

### Implementation Approach

1. Discover test files by scanning `/data` for files with `# test: all_encodings` in first 20 lines
2. Build test matrix: for each encoding × applicable field combinations
3. Execute roundtrip: GFA → BGFA (with encoding) → GFA → compare
4. Report results to stdout with fail-fast on first failure
5. Exit with appropriate code (0 for success, non-zero for failure)
