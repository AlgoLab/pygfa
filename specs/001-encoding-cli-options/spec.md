# Feature Specification: Encoding Strategy CLI Verification

**Feature Branch**: `001-encoding-cli-options`  
**Created**: 2026-03-19  
**Status**: Draft  
**Input**: User description: "check if all encoding strategies can be activated with a command line option"

## Clarifications

### Session 2026-03-19

- Q: What is the expected output format for the verification report? → A: stdout only (human-readable, no file artifact)
- Q: What test GFA files should be used for verification? → A: GFA files from `/data` tagged with `# test: all_encodings`
- Q: Should the verification test encoding+decoding roundtrip or just encoding success? → A: Roundtrip (encode → decode → compare with original)
- Q: What should happen when an encoding is valid but incompatible with a field type? → A: Only test valid combinations (enforce type-checking before execution)
- Q: Should the verification be a new bgfatools subcommand or a standalone script? → A: Standalone script

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Verify All Integer Encodings via CLI (Priority: P1)

A user wants to confirm that every integer encoding strategy defined in the system can be activated and applied successfully through the command line tool.

**Why this priority**: Integer encodings are fundamental to BGFA compression. If any encoding cannot be activated via CLI, users cannot leverage the full compression capability, and benchmarks become incomplete.

**Independent Test**: Run the CLI tool with each integer encoding strategy (none, varint, fixed16, fixed32, fixed64, delta, gamma, omega, golomb, rice, streamvbyte, vbyte, pfor_delta, simple8b, group_varint, bit_packing, fibonacci, exp_golomb, byte_packed, masked_vbyte) on GFA files from the `/data` directory that contain `# test: all_encodings` in the first 20 lines, and verify the command succeeds without errors.

**Test Tag**: `all_encodings`

**Acceptance Scenarios**:

1. **Given** a valid GFA file, **When** the CLI is invoked with `--names-enc "varint-none"` (or equivalent option), **Then** the conversion succeeds and the decoded output matches the original input.
2. **Given** a valid GFA file, **When** the CLI is invoked with `--seq-enc "fixed16-none"` (or equivalent option), **Then** the conversion succeeds and the decoded output matches the original input.
3. **Given** a valid GFA file, **When** the CLI is invoked with any integer encoding from the defined set applied to any applicable field, **Then** the roundtrip (encode → decode) succeeds and output matches input.

---

### User Story 2 - Verify All String Encodings via CLI (Priority: P1)

A user wants to confirm that every string encoding strategy defined in the system can be activated and applied successfully through the command line tool.

**Why this priority**: String encodings are critical for compressing GFA sequence data. If any encoding cannot be activated via CLI, users miss compression opportunities and the encoding library is incomplete.

**Independent Test**: Run the CLI tool with each string encoding strategy (none, zstd, zstd_dict, gzip, lzma, lz4, brotli, huffman, frontcoding, delta, dictionary, rle, cigar, 2bit, arithmetic, bwt_huffman, ppm, superstring_none, superstring_huffman, superstring_2bit, superstring_ppm) on GFA files from the `/data` directory that contain `# test: all_encodings` in the first 20 lines, and verify the command succeeds.

**Test Tag**: `all_encodings`

**Acceptance Scenarios**:

1. **Given** a valid GFA file, **When** the CLI is invoked with `--names-enc "none-zstd"` (or equivalent option), **Then** the conversion succeeds and the decoded output matches the original input.
2. **Given** a valid GFA file, **When** the CLI is invoked with `--seq-enc "varint-2bit"` (or equivalent option), **Then** the conversion succeeds and the decoded output matches the original input.
3. **Given** a valid GFA file, **When** the CLI is invoked with any string encoding from the defined set applied to any applicable field, **Then** the roundtrip (encode → decode) succeeds and output matches input.

---

### User Story 3 - Automated Verification Script (Priority: P2)

A user wants a standalone script that iterates through all encoding strategies, tests each one via roundtrip, and outputs a clear report to stdout of which strategies work and which fail.

**Why this priority**: Manual testing of 20+ integer encodings and 20+ string encodings across multiple fields is time-consuming. An automated report enables quick identification of gaps and regression detection.

**Independent Test**: Execute a verification script that tests all encodings on GFA files tagged with `all_encodings` and outputs a pass/fail matrix to stdout showing which encoding-field combinations succeed.

**Test Tag**: `all_encodings`

**Acceptance Scenarios**:

1. **Given** GFA files from the `/data` directory tagged with `# test: all_encodings`, **When** the verification script is executed, **Then** it produces a human-readable report to stdout listing each encoding strategy with roundtrip success/failure status.
2. **Given** the verification report, **When** any encoding roundtrip fails, **Then** the report includes the specific error message and the command that was attempted.
3. **Given** the verification report, **When** all encoding roundtrips pass, **Then** the report clearly indicates 100% success.

---

### Edge Cases

- How does the system handle encoding names that exist in the enum but are not implemented as callable functions?
- What happens when the CLI option format is incorrect (e.g., missing the dash separator in "int-str" format)?
- How does the system respond when an encoding strategy produces larger output than the input (negative compression)?

### Assumptions

- The verification process enforces type-checking before execution: only integer encodings are tested on integer fields, and only string encodings are tested on string fields. Incompatible field-encoding combinations are excluded from the test matrix.
- GFA files used for verification are selected by the `# test: all_encodings` tag in the first 20 lines of the file.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Users MUST be able to specify any integer encoding strategy via the CLI for each applicable field (segment names, sequences, link coordinates, path segment lengths, walk indices).
- **FR-002**: Users MUST be able to specify any string encoding strategy via the CLI for each applicable field (segment name strings, sequence strings, CIGAR strings, path names, walk data).
- **FR-003**: The CLI MUST accept encoding strategies in the format `int-str` (e.g., "varint-huffman") for combined integer and string encoding specification.
- **FR-004**: The system MUST validate that the specified encoding strategy exists and is implemented before attempting conversion.
- **FR-005**: When an invalid encoding strategy is specified, the system MUST provide a clear error message listing all valid options.
- **FR-006**: The system MUST provide a subcommand or mode that lists all available encoding strategies with their descriptions.
- **FR-007**: The verification process MUST be implemented as a standalone script that tests each encoding strategy independently with a full roundtrip (encode → decode → compare) to isolate failures.
- **FR-008**: The verification report MUST be output to stdout and include the encoding name, field type, roundtrip success/failure status, and error details for each test.
- **FR-009**: The verification MUST enforce type-checking: only test integer encodings on integer fields and string encodings on string fields. Incompatible combinations MUST be excluded from the test matrix.
- **FR-010**: The verification script MUST only test GFA files from the `/data` directory that are tagged with `# test: all_encodings` in the first 20 lines.

### Key Entities *(include if feature involves data)*

- **Encoding Strategy**: A named compression method (integer or string) that can be applied to BGFA data fields. Defined in the IntegerEncoding and StringEncoding enums.
- **Field Type**: A specific component of the BGFA format that can be independently encoded (e.g., segment_names_header, segments_payload_strings, links_payload_from).
- **Verification Result**: The outcome of testing an encoding strategy on a field, including success/failure status, execution time, and any error messages.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 19 integer encoding strategies defined in IntegerEncoding enum can be successfully roundtripped (encode → decode) via CLI options.
- **SC-002**: All 21 string encoding strategies defined in StringEncoding enum can be successfully roundtripped (encode → decode) via CLI options.
- **SC-003**: The verification report is output to stdout and generated in under 60 seconds for a standard test file with all encoding combinations.
- **SC-004**: 100% of defined encoding strategies are reachable via documented CLI options.
- **SC-005**: When an invalid encoding is specified, the error message lists all valid encoding names within 2 seconds.
