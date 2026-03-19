# Implementation Plan: Encoding Strategy CLI Verification

**Branch**: `001-encoding-cli-options` | **Date**: 2026-03-19 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-encoding-cli-options/spec.md`

## Summary

Create a standalone verification script that tests all 40 encoding strategies (19 integer + 21 string) via roundtrip (encode → decode → compare) on GFA files tagged with `# test: all_encodings`, outputting a human-readable report to stdout.

## Technical Context

**Language/Version**: Python ≥ 3.14
**Primary Dependencies**: networkx, lark, biopython, numpy, pygfa (existing library)
**Storage**: N/A (file-based, reads GFA/BGFA files from disk)
**Testing**: pytest + unittest.TestCase
**Target Platform**: Linux and macOS
**Project Type**: CLI tool (standalone script)
**Performance Goals**: Full verification report in under 60 seconds (SC-003)
**Constraints**: Must use pixi for all commands; type-checking before execution (FR-009); only test files tagged with `# test: all_encodings` (FR-010)
**Scale/Scope**: 40 encoding strategies × 18+ field types = 720+ test combinations

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### I. Simplicity First ✅
- Single standalone script, no abstractions for single-use code
- No features beyond what was requested in the spec

### II. Surgical Changes ✅
- Adding new script to `test/` directory
- Not modifying existing bgfatools code

### III. Goal-Driven Execution ✅
- Clear success criteria: 100% encoding strategies reachable via CLI
- Measurable outcomes: roundtrip verification, timing targets

### IV. Test Discipline ✅
- Script follows project conventions: `test/test_*.py` naming
- Uses existing GFA files from `/data` directory

### V. Code Style & Linting ✅
- Will use `pixi run ruff check`
- Google-style docstrings for public functions

## Project Structure

### Documentation (this feature)

```text
specs/001-encoding-cli-options/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # N/A for this feature
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
test/
└── test_all_encodings.py    # New: verification script

pygfa/
└── encoding/                # Existing: encoding modules (no changes)
```

**Structure Decision**: Standalone test script in `test/` directory following project conventions. No changes to existing source code.

## Complexity Tracking

> No violations - feature is a standalone script following project conventions.
