# Research: Encoding Strategy CLI Verification

## Decision: CLI Interface Architecture

**Rationale**: The `bgfatools` CLI uses `int-str` format (e.g., `varint-huffman`) for combined integer and string encoding specification. The verification script will use the same format for consistency.

**Alternatives considered**:
- Separate `--int-enc` and `--str-enc` flags: Rejected because existing CLI uses combined format
- Configuration file approach: Rejected per spec clarification (stdout only, no file artifact)

## Decision: Integer Encodings (19 strategies)

From `IntegerEncoding` enum in `pygfa/encoding/enums.py`:

| Encoding | Value | Notes |
|----------|-------|-------|
| none | 0x00 | Identity/no compression |
| varint | 0x01 | Variable-length integer |
| fixed16 | 0x02 | Fixed 16-bit |
| fixed32 | 0x0A | Fixed 32-bit |
| fixed64 | 0x0B | Fixed 64-bit |
| delta | 0x03 | Delta encoding |
| gamma | 0x04 | Elias gamma |
| omega | 0x05 | Elias omega |
| golomb | 0x06 | Golomb coding |
| rice | 0x07 | Rice coding |
| streamvbyte | 0x08 | StreamVByte |
| vbyte | 0x09 | Variable byte |
| pfor_delta | 0x0C | PForDelta |
| simple8b | 0x0D | Simple-8b |
| group_varint | 0x0E | Group varint |
| bit_packing | 0x0F | Bit packing |
| fibonacci | 0x10 | Fibonacci coding |
| exp_golomb | 0x11 | Exp-Golomb |
| byte_packed | 0x12 | Byte packed |
| masked_vbyte | 0x13 | Masked VByte |

**Rationale**: These are defined in the `IntegerEncoding` IntEnum and mapped in `INTEGER_ENCODINGS` dict.

## Decision: String Encodings (21 strategies)

From `StringEncoding` enum in `pygfa/encoding/enums.py`:

| Encoding | Value | Notes |
|----------|-------|-------|
| none | 0x00 | Identity/no compression |
| zstd | 0x01 | Zstandard |
| zstd_dict | 0x0B | Zstandard with dictionary |
| gzip | 0x02 | Gzip |
| lzma | 0x03 | LZMA |
| lz4 | 0x0C | LZ4 |
| brotli | 0x0D | Brotli |
| huffman | 0x04 | Huffman coding |
| frontcoding | N/A | Front coding |
| delta | N/A | Delta encoding for strings |
| dictionary | 0x0A | Dictionary encoding |
| rle | 0x08 | Run-length encoding |
| cigar | 0x09 | CIGAR-specific encoding |
| 2bit | 0x05 | 2-bit DNA encoding |
| arithmetic | 0x06 | Arithmetic coding |
| bwt_huffman | 0x07 | BWT + Huffman |
| ppm | 0x0E | PPM coding |
| superstring_none | 0xF0 | Superstring (none) |
| superstring_huffman | 0xF4 | Superstring (huffman) |
| superstring_2bit | 0xF5 | Superstring (2bit) |
| superstring_ppm | 0xF1 | Superstring (PPM) |

**Rationale**: These are defined in the `StringEncoding` IntEnum and mapped in `STRING_ENCODINGS` dict.

## Decision: Test File Selection

**Rationale**: GFA files tagged with `# test: all_encodings` in the first 20 lines will be used. This follows the project convention where files have `# test: TESTNAME` comments linking them to test scripts.

**Alternatives considered**:
- Use all files in `/data`: Rejected per user clarification (too slow, includes complex files)
- Create new minimal test file: Rejected per user clarification (use existing tagged files)

## Decision: Roundtrip Verification

**Rationale**: Encode → decode → compare ensures encoding correctness, not just "no crash." This matches the spec requirement (FR-007).

**Alternatives considered**:
- Encode-only: Rejected per spec clarification (would miss decode bugs)
- Encode + measure size: Not sufficient for correctness validation

## Decision: Type-Checking Before Execution

**Rationale**: Only test integer encodings on integer fields, string encodings on string fields. This reduces the test matrix from 40×18 (720) to the valid combinations only.

**Implementation**: Use `SECTION_INT_ENCODINGS` and `SECTION_STR_ENCODINGS` from `benchmark_encode_single_param.py` as reference for which fields take which type.

## Decision: Output Format

**Rationale**: Human-readable stdout output per spec clarification. No file artifact.

**Format**: Table with columns: Encoding, Field, Status (PASS/FAIL), Error (if any)

## Decision: Script Location

**Rationale**: `test/test_all_encodings.py` follows project convention for test scripts.

**Alternatives considered**:
- New bgfatools subcommand: Rejected per spec clarification (standalone script)
- Top-level script: Would not follow project test conventions

## Decision: Fail-Fast Behavior

**Decision**: Exit with non-zero code on first failure

**Rationale**:
- Enables quick identification of broken encodings
- Suitable for CI/CD integration
- Clear signal for automation
- Matches "fail-fast" expectation for verification tools

**Alternatives considered**:
- Report mode (continue testing, exit 0): Rejected - user can run multiple times to find all issues
- Collect-then-fail (test all, then exit non-zero): Rejected - more complex, slower feedback

## Decision: Test Order

**Decision**: Sequential by encoding type (group all variants of each encoding together)

**Rationale**:
- Easier to spot patterns in output (all variants of one encoding)
- Logical grouping matches enum organization
- Easier to understand failure reports

**Alternatives considered**:
- Random order: Rejected - non-deterministic, harder to debug
- Field type order: Rejected - less intuitive for encoding verification

## Decision: Missing Encoding Handling

**Decision**: Fail-fast with error message when encoding is in enum but missing from test matrix

**Rationale**:
- Detects incomplete implementation early
- Prevents silent gaps in verification
- Clear signal for developers

## Integer Encoding Count Update

**Note**: The spec mentioned 19 integer encodings, but inspection of the enum shows 20:
- none, varint, fixed16, fixed32, fixed64, delta, gamma, omega, golomb, rice, streamvbyte, vbyte, pfor_delta, simple8b, group_varint, bit_packing, fibonacci, exp_golomb, byte_packed, masked_vbyte

SC-001 has been updated to reflect the correct count of 20.
