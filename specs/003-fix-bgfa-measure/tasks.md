# Tasks: Fix BGFA Measure Unicode Error

**Input**: Design documents from `/specs/003-fix-bgfa-measure/`
**Prerequisites**: plan.md (completed), spec.md (completed)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

---

## Phase 1: Root Cause Analysis

**Purpose**: Understand the exact issue in the BGFA encoding/decoding pipeline

- [x] T001 Analyze the compress_string_list function in pygfa/encoding/string_encoding.py to verify it correctly uses the integer encoder for sequence lengths
- [x] T002 Analyze the _parse_segments_block function in pygfa/bgfa.py to verify it correctly uses the integer decoder for sequence lengths
- [x] T003 Verify the VBYTE integer encoding/decoding functions in pygfa/bgfa.py work correctly

---

## Phase 2: Implementation

**Purpose**: Fix the encoding/decoding mismatch for sequence lengths

- [x] T004 [P] Fix compress_integer_list_vbyte in pygfa/encoding/integer_list_encoding.py (the encoder was producing incorrect byte sequences for values >= 64)
- [x] T005 [P] Fix decode_integer_list_vbyte in pygfa/bgfa.py (the decoder was correctly implemented, only encoder was broken)
- [x] T006 [P] Add test case in test/test_bgfa.py for vbyte encoding round-trip (GFA -> BGFA with vbyte -> measure should succeed)

---

## Phase 3: Verification

**Purpose**: Ensure the fix works and doesn't break existing functionality

- [x] T007 Run `pixi run ruff check` to ensure lint passes
- [x] T008 Run `pixi run python -m pytest test/test_bgfa.py -v` to verify existing tests still pass (901 tests passed)
- [x] T009 Test the specific failing case: `pixi run python bin/bgfatools measure results/benchmark/segments_header/DRB4-3126.fa.bab52bb.34ee7b1.6c8dee8.smooth.fix/vbyte_32768.bgfa /tmp/test.csv` - SUCCESS

---

## Phase 4: Polish

**Purpose**: Final cleanup and verification

- [x] T010 Update docstrings for modified functions if needed (added docstring to compress_integer_list_vbyte)
- [x] T011 Run full test suite to ensure no regressions (2102 tests passed)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Analysis)**: No dependencies - understand the issue first
- **Phase 2 (Implementation)**: Depends on Phase 1 completion
- **Phase 3 (Verification)**: Depends on Phase 2 completion
- **Phase 4 (Polish)**: Depends on Phase 3 completion

### Within Each Phase

- Phase 1 tasks should be done sequentially to build understanding
- Phase 2 tasks marked [P] can be done in parallel (different files)
- Phase 3 tasks can be done in parallel

---

## Parallel Opportunities

```bash
# Phase 2: Fix both writer and reader in parallel (different files)
Task: "Fix compress_integer_list_vbyte in pygfa/encoding/integer_list_encoding.py"
Task: "Fix decode_integer_list_vbyte in pygfa/bgfa.py"

# Phase 2: Add test case
Task: "Add test case in test/test_bgfa.py"

# Phase 3: Verification tasks can run in parallel
Task: "Run ruff check"
Task: "Run pytest tests"
```

---

## Implementation Strategy

### Recommended Order

1. **Phase 1 (Analysis)**: Understand the exact issue in both encoding and decoding
2. **Phase 2 (Implementation)**: Fix both writer and reader, add test
3. **Phase 3 (Verification)**: Run lint and tests
4. **Phase 4 (Polish)**: Final cleanup

### MVP Scope

User Story 1 (fix vbyte encoding) is the MVP. User Story 2 (benchmark workflow) is automatically satisfied once the fix is complete.

---

## Notes

- Both user stories (BGFA measurement + benchmark workflow) are satisfied by fixing the single root cause
- No new project structure or dependencies needed
- The fix is surgical - only affects VBYTE integer encoding in BGFA files
- Backward compatibility maintained - existing BGFA files with other encodings continue to work
- Root cause: The VBYTE encoder was using an incorrect byte format that didn't match the decoder's expectations