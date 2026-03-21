# Data Model: Encoding Strategy CLI Verification

## Entities

### Encoding Strategy

A named compression method that can be applied to BGFA data fields.

**Attributes**:
- `name` (str): Encoding name (e.g., "varint", "huffman", "zstd")
- `type` (str): "integer" or "string"
- `enum_value` (int): Numeric code from IntegerEncoding/StringEncoding enum
- `function_name` (str): Compression function name in INTEGER_ENCODINGS/STRING_ENCODINGS

**Relationships**: Applied to Field Type via CLI options

### Field Type

A specific component of the BGFA format that can be independently encoded.

**Attributes**:
- `name` (str): Field identifier (e.g., "segment_names_header", "segments_payload_strings")
- `section` (str): BGFA section (segment_names, segments, links, paths, walks)
- `type` (str): "integer" or "string"
- `cli_option` (str): CLI flag name (e.g., "--segment-names-header")

**Relationships**: Accepts Encoding Strategy of matching type

### Verification Result

The outcome of testing an encoding strategy on a field.

**Attributes**:
- `encoding_name` (str): Tested encoding
- `field_name` (str): Target field
- `status` (str): "PASS", "FAIL", or "SKIP"
- `error_message` (str | None): Error details if status is FAIL
- `encode_time_ms` (float): Encoding duration
- `decode_time_ms` (float): Decoding duration
- `roundtrip_match` (bool): Whether decoded output matches original

## Validation Rules

1. Type-checking: Only test integer encodings on integer fields, string encodings on string fields
2. File selection: Only test GFA files tagged with `# test: all_encodings`
3. Roundtrip: Encode → decode → compare must succeed for PASS status
4. Fail-fast: Script exits immediately with non-zero code on first FAIL

## State Transitions

```
[Not Tested] → [Encoding] → [Decoding] → [Comparing] → [PASS/FAIL]
                    ↓              ↓              ↓
                 [FAIL]         [FAIL]         [FAIL]
                      ↓
              [Exit with non-zero code]
```

## Test Matrix Structure

The script builds a test matrix combining:
- 20 integer encodings × applicable integer fields
- 21 string encodings × applicable string fields

Fields are tested in sequential order grouped by encoding type.

## Output Format

Verification report printed to stdout with:
- Encoding name
- Field type
- Status (PASS/FAIL/SKIP)
- Error message (if FAIL)
- Total time per encoding

Exit code: 0 for all PASS, non-zero for any FAIL
