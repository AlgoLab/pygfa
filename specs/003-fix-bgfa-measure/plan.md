# Implementation Plan: Fix BGFA Measure Unicode Error

**Branch**: `003-fix-bgfa-measure` | **Date**: 2026-03-21 | **Spec**: [specs/003-fix-bgfa-measure/spec.md](spec.md)

## Summary

Fix the UnicodeDecodeError that occurs when measuring BGFA files created with encodings like "vbyte". The root cause is that sequence lengths are stored as raw ASCII text instead of using the specified integer encoding (e.g., VBYTE). When reading, the code attempts to decode lengths using VBYTE but receives invalid data, then tries to decode sequence bytes as ASCII which fails.

**Technical Approach**: 
- Fix the BGFA writer to properly encode sequence lengths using the specified integer encoding (e.g., VBYTE) when string encoding is NONE
- Fix the measure_bgfa function to correctly use the integer decoder for lengths regardless of string encoding
- This is a surgical fix - only two locations need changes: writer and reader

## Technical Context

**Language/Version**: Python >= 3.14  
**Primary Dependencies**: networkx, lark, biopython, numpy, zstandard, lz4, brotli  
**Storage**: N/A (file-based, reads GFA/BGFA files from disk)  
**Testing**: pytest  
**Target Platform**: Linux and macOS  
**Project Type**: Python library (pygfa)  
**Performance Goals**: N/A (bug fix)  
**Constraints**: Must maintain backward compatibility with existing BGFA files  
**Scale/Scope**: N/A (single bug fix)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Gate Validation**:

| Principle | Status | Notes |
|------------|--------|-------|
| I. Simplicity First | PASS | Surgical fix - minimal code changes |
| II. Test Discipline | PASS | Existing tests cover BGFA operations; will add specific test for vbyte encoding |
| III. Specification Compliance | PASS | Fix ensures BGFA format is correctly read/written per spec |
| IV. Code Quality | PASS | Will use ruff/mypy, follow naming conventions |
| V. Surgical Changes | PASS | Only changes to affected code paths - writer and measure function |

**Violation Check**: None - this is a focused bug fix requiring minimal changes.

## Project Structure

### Documentation (this feature)

```text
specs/003-fix-bgfa-measure/
├── plan.md              # This file
├── research.md          # Not needed - issue already understood
├── data-model.md        # Not needed - simple bug fix, no new entities
├── quickstart.md        # Not needed - no API changes
├── contracts/           # Not needed - no external interfaces
└── tasks.md             # Created by /speckit.tasks
```

### Source Code (repository root)

```text
pygfa/                    # Existing library structure
├── bgfa.py              # Target file for fix
└── ...                  # Other modules unchanged

test/
├── test_bgfa.py         # Will add test case for vbyte encoding
└── ...                  # Other tests unchanged
```

**Structure Decision**: Simple bug fix in existing pygfa library. No new files or directories needed.

## Complexity Tracking

N/A - This is a focused bug fix with no architectural complexity. The issue is well-understood and requires minimal, surgical changes to two locations in the codebase.
