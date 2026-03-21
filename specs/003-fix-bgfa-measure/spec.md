# Feature Specification: Fix BGFA Measure Unicode Error

**Feature Branch**: `003-fix-bgfa-measure`  
**Created**: 2026-03-21  
**Status**: Draft  
**Input**: User description: "Error in rule measure_bgfa: The bgfatools measure command failed with non-zero exit code when processing BGFA files in the benchmark workflow"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - BGFA measurement fails with UnicodeDecodeError (Priority: P1)

When running the benchmark workflow that measures BGFA files created with encodings like "vbyte", the measurement fails with a UnicodeDecodeError because the sequence data contains non-ASCII bytes.

**Why this priority**: This is a critical bug that breaks the entire benchmark pipeline for certain encoding configurations.

**Independent Test**: Can be tested by creating a BGFA file with "vbyte" encoding and attempting to measure it. The test should verify that measure_bgfa successfully reads the BGFA file and outputs correct statistics.

**Acceptance Scenarios**:

1. **Given** a valid BGFA file created with "vbyte" encoding, **When** running `bgfatools measure`, **Then** it should successfully produce a CSV file with block statistics without UnicodeDecodeError.
2. **Given** a BGFA file with sequence data that uses VBYTE integer encoding and NONE string encoding, **When** reading the sequences, **Then** the length integers should be decoded using VBYTE, not stored as raw ASCII.
3. **Given** a GFA file with DNA sequences, **When** converting to BGFA with "vbyte" encoding, **Then** the resulting BGFA file can be read back using measure_bgfa without errors.

---

### User Story 2 - Benchmark workflow completes successfully (Priority: P1)

The snakemake benchmark workflow should complete successfully for all encoding combinations without measurement failures.

**Why this priority**: The benchmark workflow is used to evaluate different BGFA encoding strategies. Failures prevent accurate comparisons.

**Independent Test**: Run the benchmark workflow on a small dataset and verify all measurement outputs are generated.

**Acceptance Scenarios**:

1. **Given** a benchmark configuration with multiple encoding options and block sizes, **When** running the workflow, **Then** all measurement CSV files should be generated successfully.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The measure_bgfa function MUST successfully read BGFA files created with any valid encoding combination without throwing UnicodeDecodeError.
- **FR-002**: When reading sequence data with integer encoding VBYTE (code 0x09) and string encoding NONE (code 0x00), the lengths MUST be decoded using the VBYTE integer decoder, not stored as raw ASCII.
- **FR-003**: The BGFA writer MUST store sequence lengths using the specified integer encoding (e.g., VBYTE) when string encoding is NONE.
- **FR-004**: The measure_bgfa function MUST handle edge cases where sequences may contain non-ASCII characters (e.g., when using DNA 2-bit encoding that produces binary output).

### Key Entities *(include if feature involves data)*

- **BGFA File**: Binary Graphical Fragment Assembly format with compressed segments
- **Sequence Data**: DNA sequences stored in segments
- **Compression Code**: 2-byte code combining integer encoding (high byte) and string encoding (low byte)
- **Integer Decoder**: Function to decode length values from encoded bytes

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Running `bgfatools measure` on any BGFA file created with "vbyte" encoding completes without UnicodeDecodeError
- **SC-002**: The benchmark workflow successfully generates all measurement CSV files for all tested encodings
- **SC-003**: BGFA files created with various encoding combinations can be round-tripped (GFA -> BGFA -> measure) without errors

---

## Assumptions

- The issue only affects BGFA files created with certain encoding combinations (vbyte, streamvbyte, etc.) that use NONE string encoding
- The fix should maintain backward compatibility with existing BGFA files created with other encodings