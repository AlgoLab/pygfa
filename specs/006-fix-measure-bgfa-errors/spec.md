# Feature Specification: Fix measure_bgfa failure for PPM encoding

**Feature Branch**: `006-fix-measure-bgfa-errors`  
**Created**: 2026-03-22  
**Status**: Completed  
**Input**: User description: "Snakemake measure_bgfa rule fails with non-zero exit code for BGFA files"

## Clarifications

### Session 2026-03-22

- Q: How to handle edge cases for PPM decompression? → A: Focus only on zero-length strings; document empty data as out of scope

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Decompress BGFA files with PPM-encoded segment names (Priority: P1)

The benchmark system should successfully measure BGFA files that use PPM (Prediction by Partial Matching) encoding for segment names.

**Why this priority**: The measure_bgfa rule is a critical part of the benchmark workflow and is currently failing for all files using PPM encoding.

**Independent Test**: Can be fully tested by running `pixi run python bin/bgfatools measure` on a BGFA file with PPM-encoded segment names and verifying it produces valid CSV output without errors.

**Acceptance Scenarios**:

1. **Given** a valid BGFA file with PPM-encoded segment names, **When** the measure command is executed, **Then** it should produce a CSV file with block statistics without raising any exceptions.

2. **Given** a BGFA file with superstring_ppm encoding, **When** the measure command is executed, **Then** it should successfully parse all segments, links, paths, and walks blocks.

---

### Edge Cases

- **Zero-length strings in non-empty payload**: When the lengths list contains zeros (e.g., `[0] * record_num`), the decompressor must handle this gracefully by allowing zstd to auto-determine output size.
- **Corrupt or truncated PPM data**: This is out of scope for this fix; existing error handling is sufficient.
- **Empty data payload**: Existing check `if not data: return []` handles this case; documented as out of scope for this specific fix.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The `decompress_string_ppm` function MUST handle the case where the provided lengths list contains zeros (from `[0] * record_num`).
- **FR-002**: The measure_bgfa command MUST successfully process BGFA files using PPM encoding without raising zstandard.ZstdError.
- **FR-003**: The decompressed strings MUST be correctly split according to their original lengths when lengths are provided.

### Key Entities *(include if data involved)*

- **BGFA File**: Binary Graphical Fragment Assembly format file containing compressed graph data
- **PPM Encoding**: Prediction by Partial Matching compression using zstd
- **Segment Names**: Node identifiers stored in BGFA segments block

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All BGFA files with PPM encoding can be measured without errors
- **SC-002**: The benchmark Snakemake workflow completes successfully for all encoding options including ppm and superstring_ppm
- **SC-003**: Zero occurrences of "error determining content size from frame header" during measure operations
- **SC-004**: All existing tests continue to pass after the fix

## Assumptions

- The zstandard library allows `max_output_size=None` to auto-determine output size
- The fix should not affect other encoding types (zstd, gzip, lz4, brotli)
- The decompressed data size can always be determined from the PPM/zstd frame header

## Root Cause Analysis

### Initial Hypothesis (Incorrect)

The initial assumption was that `max_output_size=original_len` was the problem when `original_len=0`. The proposed fix was to pass `max_output_size=None` to zstd.

### Actual Root Cause

The BGFA format stores integer-encoded lengths BEFORE the PPM data, but `decompress_string_ppm` expected the PPM header to be at the start of the data.

**BGFA format for PPM encoding**:
```
[VARINT-encoded lengths][uint32: total_len][uint8: order][zstd_compressed_data]
```

**Standalone PPM format**:
```
[uint32: total_len][uint8: order][zstd_compressed_data]
```

The lambda in `bgfa.py`:
```python
STRING_ENCODING_PPM: lambda p, rn, id: decompress_string_ppm(p, [0] * rn)
```

The `[0] * rn` placeholder was meant to signal the function to use `int_decoder` to extract the actual lengths from the data. However, the `decompress_string_ppm` function was ignoring the `int_decoder` parameter (which was not even passed).

### The Fix

1. **In `pygfa/bgfa.py`**: Pass `id` (the `int_decoder`) to `decompress_string_ppm`:
   ```python
   STRING_ENCODING_PPM: lambda p, rn, id: decompress_string_ppm(p, [0] * rn, id)
   ```

2. **In `pygfa/encoding/ppm_coding.py`**: 
   - Added `int_decoder` parameter to `decompress_string_ppm`
   - When `lengths[0] == 0` (indicating actual lengths should be decoded), use `int_decoder` to extract them
   - Skip past the integer-encoded lengths before reading the PPM header
