# Quickstart: Encoding Strategy CLI Verification

## Prerequisites

- pygfa installed in pixi environment
- Test GFA files in `/data` directory tagged with `# test: all_encodings`

## Run the Verification Script

```bash
# Run all encoding verification tests
pixi run python test/test_all_encodings.py

# Run with verbose output
pixi run python test/test_all_encodings.py -v

# Run with debug output
pixi run python test/test_all_encodings.py -d
```

## Expected Output (Success)

```
Encoding Strategy Verification Report
====================================

Integer Encodings (20):
-----------------------
PASS: none      on segment_names_header
PASS: varint    on segment_names_header
PASS: fixed16   on segment_names_header
...
PASS: masked_vbyte on walks_payload_end

String Encodings (21):
----------------------
PASS: none      on segments_payload_strings
PASS: zstd      on segments_payload_strings
PASS: huffman   on segments_payload_strings
...
PASS: superstring_ppm on walks_payload_walks

====================================
Summary: 738/738 tests passed (100.0%)
Time: 12.3 seconds
====================================
```

## Expected Output (Failure - Fail-Fast)

When a test fails, the script exits immediately:

```
Encoding Strategy Verification Report
====================================

Integer Encodings (20):
-----------------------
PASS: none      on segment_names_header
PASS: varint    on segment_names_header
FAIL: fixed16   on segment_names_header
  Error: ValueError: invalid compressed data
  Command: bgfatools bgfa input.gfa /tmp/test.bgfa --segment-names-header fixed16-none

====================================
ERROR: Verification failed at fixed16 encoding
====================================
```

Exit code: 1 (non-zero on failure)

## Interpreting Results

- **PASS**: Roundtrip (encode → decode → compare) succeeded
- **FAIL**: Roundtrip failed; error message and command included; script exits immediately
- **SKIP**: Incompatible field-encoding combination (type mismatch); not counted as failure

## Exit Codes

- `0`: All tests passed (100% success)
- `1`: One or more tests failed (fail-fast, exits on first failure)

## Troubleshooting

If tests fail, check:
1. The encoding is supported for that field type (integer vs string)
2. The CLI option format is correct (`int-str` format)
3. The GFA file is valid and contains the expected data
