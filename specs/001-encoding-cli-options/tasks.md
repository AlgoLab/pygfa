---

description: "Task list for encoding strategy CLI verification feature"
---

# Tasks: Encoding Strategy CLI Verification

**Input**: Design documents from `/specs/001-encoding-cli-options/`
**Prerequisites**: plan.md (required), spec.md (required), data-model.md, research.md

**Tests**: This feature IS the verification test. No additional test tasks needed.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Create test script skeleton in test/test_all_encodings.py with argparse for -v/--verbose and -d/--debug flags

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T002 [P] Implement GFA file discovery function to find files tagged with `# test: all_encodings` in first 20 lines in test/test_all_encodings.py
- [x] T003 [P] Implement encoding enumeration function to load all 20 integer encodings and 21 string encodings from pygfa.encoding in test/test_all_encodings.py
- [x] T004 [P] Implement field type mapping from section encodings (names_enc, seq_enc, links_fromto_enc, links_cigars_enc, etc.) in test/test_all_encodings.py
- [x] T005 [P] Implement type-checking function to validate integer encodings only apply to integer fields and string encodings to string fields in test/test_all_encodings.py

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Verify All Integer Encodings via CLI (Priority: P1)

**Goal**: Test all 20 integer encoding strategies via roundtrip on tagged GFA files

**Independent Test**: Run `pixi run python test/test_all_encodings.py --int-only` and verify all integer encodings report PASS

### Implementation for User Story 1

- [x] T006 [US1] Implement single_encoding_test function to run GFA → BGFA → GFA roundtrip in test/test_all_encodings.py
- [x] T007 [US1] Implement bgfatools CLI invocation with --names-enc, --seq-enc, etc. for integer encoding fields in test/test_all_encodings.py
- [x] T008 [US1] Implement result comparison to verify decoded output matches original GFA in test/test_all_encodings.py
- [x] T009 [US1] Implement integer encoding test matrix (20 encodings × applicable fields) with sequential order by encoding type in test/test_all_encodings.py

**Checkpoint**: User Story 1 should be fully functional - all 20 integer encodings tested

---

## Phase 4: User Story 2 - Verify All String Encodings via CLI (Priority: P1)

**Goal**: Test all 21 string encoding strategies via roundtrip on tagged GFA files

**Independent Test**: Run `pixi run python test/test_all_encodings.py --str-only` and verify all string encodings report PASS

### Implementation for User Story 2

- [x] T010 [US2] Implement string encoding test matrix (21 encodings × applicable fields) with sequential order by encoding type in test/test_all_encodings.py
- [x] T011 [US2] Implement bgfatools CLI invocation with string encoding options (--seq-enc "varint-2bit" format) in test/test_all_encodings.py
- [x] T012 [US2] Integrate string encoding tests with existing roundtrip and comparison logic in test/test_all_encodings.py

**Checkpoint**: User Stories 1 AND 2 should both work independently

---

## Phase 5: User Story 3 - Automated Verification Script (Priority: P2)

**Goal**: Combine all tests into a single script that outputs a human-readable report to stdout with fail-fast behavior

**Independent Test**: Run `pixi run python test/test_all_encodings.py` and verify complete report output

### Implementation for User Story 3

- [x] T013 [US3] Implement human-readable report output to stdout with table format (encoding, field, status, error) in test/test_all_encodings.py
- [x] T014 [US3] Implement fail-fast behavior: exit immediately with non-zero code on first test failure in test/test_all_encodings.py
- [x] T015 [US3] Implement summary statistics (total tests, pass/fail counts, timing) at end of report in test/test_all_encodings.py
- [x] T016 [US3] Implement validation for missing encodings: fail-fast with error if encoding in enum but not in test matrix in test/test_all_encodings.py

**Checkpoint**: All user stories should now be independently functional

---

## Phase N: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [x] T017 Add Google-style docstrings to all public functions in test/test_all_encodings.py
- [x] T018 Run `pixi run ruff check` and fix any linting issues in test/test_all_encodings.py
- [ ] T019 Verify script completes in under 60 seconds on standard test files per SC-003 (pending: full test run takes ~2 min for 530 tests)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P1 → P2)
- **Polish (Final Phase)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 3 (P2)**: Can start after Foundational (Phase 2) - Depends on US1 and US2 patterns but independently testable

### Within Each User Story

- Implementation tasks in order
- Story complete before moving to next priority

### Parallel Opportunities

- All Foundational tasks marked [P] can run in parallel (within Phase 2)
- User Stories 1 and 2 can run in parallel (both P1, no dependencies)

---

## Parallel Example: Foundational Phase

```bash
# Launch these together:
Task: "Implement encoding enumeration function to load all 20 integer and 21 string encodings from pygfa.encoding in test/test_all_encodings.py"
Task: "Implement field type mapping from section encodings in test/test_all_encodings.py"
Task: "Implement type-checking function for integer/string encoding validation in test/test_all_encodings.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1 (integer encodings - 20 total)
4. **STOP and VALIDATE**: Test integer encodings independently
5. Commit if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 (integer encodings - 20 total) → Test independently
3. Add User Story 2 (string encodings - 21 total) → Test independently
4. Add User Story 3 (full report with fail-fast) → Test independently
5. Polish and lint

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (integer encodings)
   - Developer B: User Story 2 (string encodings)
3. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Fail-fast behavior: script exits immediately with non-zero code on first failure
- Test order: sequential by encoding type (group all variants of each encoding together)
