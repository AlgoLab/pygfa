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

## Expected Output

```
Encoding Strategy Verification Report
=====================================

Integer Encodings (19):
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

Summary: 720/720 tests passed (100.0%)
Time: 12.3 seconds
```

## Interpreting Results

- **PASS**: Roundtrip (encode → decode → compare) succeeded
- **FAIL**: Roundtrip failed; error message included
- **SKIP**: Incompatible field-encoding combination (type mismatch)
