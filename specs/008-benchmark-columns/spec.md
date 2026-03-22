# Feature Specification: Benchmark Output Columns

**Feature Branch**: `008-benchmark-columns`  
**Created**: 2026-03-22  
**Status**: Draft  
**Input**: User description: "The output of the benchmark must have a column `block_index` (segment names, segnments, links, etc.) and a column `option` which is the encoding option, and a column `value` that is the value of the option (for example varint). The benchmark is designed to determine which value should be the default for each option, so I need detailed data that will be then explored using pandas. The exploration is performed with a program in a different repo. You do not have to write that program. You must update @workflow/Snakefile"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Add Descriptive Block Names (Priority: P1)

As a data analyst, I need the benchmark CSV output to include descriptive block names (like "segment_names", "segments", "links", "paths") instead of numeric section IDs, so that I can easily understand and filter the data by block type during pandas analysis.

**Why this priority**: Clear block identification is fundamental to analyzing which encoding values work best for each data type.

**Independent Test**: Run a single benchmark measurement and inspect the CSV output for the block_index column.

**Acceptance Scenarios**:

1. **Given** a BGFA file with multiple block types, **When** running `bgfatools measure`, **Then** the CSV output includes a `block_index` column with descriptive names like "segment_names", "segments", "links", "paths", "walks".

---

### User Story 2 - Add Encoding Option Column (Priority: P1)

As a data analyst, I need the benchmark CSV output to include an `option` column that identifies which encoding option was tested, so that I can group and compare results by option during pandas analysis.

**Why this priority**: The benchmark tests many encoding options; without an `option` column, it is impossible to know which option produced each measurement row.

**Independent Test**: Run a single benchmark measurement and verify the CSV includes the `option` column.

**Acceptance Scenarios**:

1. **Given** a benchmark configuration testing `segment_names_payload_lengths` option, **When** running the Snakefile workflow, **Then** the CSV output includes `option` column with value "segment_names_payload_lengths".

---

### User Story 3 - Add Encoding Value Column (Priority: P1)

As a data analyst, I need the benchmark CSV output to include a `value` column that identifies the specific encoding value tested (e.g., "varint", "zstd", "none"), so that I can compare compression effectiveness across different encoding values.

**Why this priority**: The goal of the benchmark is to determine the best encoding value for each option; without a `value` column, this analysis is impossible.

**Independent Test**: Run a single benchmark measurement and verify the CSV includes the `value` column.

**Acceptance Scenarios**:

1. **Given** a benchmark configuration testing `segment_names_payload_lengths` option with value "varint", **When** running the Snakefile workflow, **Then** the CSV output includes `value` column with value "varint".

---

### Edge Cases

- What happens when multiple encoding options affect the same block type?
- How should the Snakefile handle cases where the option name doesn't match a known block type?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Benchmark CSV output MUST include a `block_index` column with descriptive block names (e.g., "segment_names", "segments", "links", "paths", "walks").
- **FR-002**: Benchmark CSV output MUST include an `option` column identifying the encoding option being tested.
- **FR-003**: Benchmark CSV output MUST include a `value` column identifying the encoding value (e.g., "varint", "zstd", "none").
- **FR-004**: Changes MUST be made to `workflow/Snakefile` to add these columns to the CSV output.
- **FR-005**: Changes MUST be made to `pygfa/bgfa.py` measure_bgfa function to include descriptive block names.
- **FR-006**: The CSV columns MUST be in order: original_gfa, option, value, block_index, section_id, section_type, record_num, compressed_length, uncompressed_length.

### Key Entities

- **Benchmark CSV**: Output file with columns for pandas analysis. Columns: original_gfa, block_index, section_id, section_type, record_num, compressed_length, uncompressed_length, option, value.
- **Block Index**: Descriptive name for each block type (segment_names, segments, links, paths, walks).
- **Option**: The encoding option being tested (e.g., segment_names_payload_lengths, segments_payload_strings).
- **Value**: The encoding value (e.g., varint, zstd, none).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every row in the benchmark CSV has a non-empty `block_index` column with descriptive name (segments, links, paths, walks).
- **SC-002**: Every row in the benchmark CSV has a non-empty `option` column matching the tested option (from Snakefile wildcards).
- **SC-003**: Every row in the benchmark CSV has a non-empty `value` column with the encoding value (e.g., varint, zstd).
- **SC-004**: The Snakefile workflow completes successfully with all new columns present.
- **SC-005**: The summary.csv.zst file contains all new columns and can be loaded into pandas for analysis.

## Implementation Notes

### Changes to `pygfa/bgfa.py`

Updated `measure_bgfa` function to use descriptive block names:
- Changed `block_index` from numeric to descriptive: "segments", "links", "paths", "walks"

### Changes to `workflow/Snakefile`

Updated `measure_bgfa` rule to add option and value columns:
- Added `params` block with `option` and `encoding` from wildcards
- Modified awk command to prepend columns: `original_gfa,option,value,`

### CSV Output Format

```
original_gfa,option,value,block_index,section_id,section_type,record_num,compressed_length,uncompressed_length
test.gfa,segments_payload_lengths,varint,segments,1,segments,10,1024,2048
test.gfa,segments_payload_lengths,varint,links,2,links,5,512,1024
```
