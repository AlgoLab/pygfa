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

- [X] T001 Create test script skeleton in test/test_all_encodings.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**CRITICAL**: No user story work can begin until this phase is complete

- [X] T002 Implement GFA file discovery function to find files tagged with `# test: all_encodings` in test/test_all_encodings.py
- [X] T003 [P] Implement encoding enumeration function to load all integer and string encodings from pygfa.encoding in test/test_all_encodings.py
- [X] T004 [P] Implement field type mapping from SECTION_INT_ENCODINGS and SECTION_STR_ENCODINGS in test/test_all_encodings.py

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Verify All Integer Encodings via CLI (Priority: P1)

**Goal**: Test all 19 integer encoding strategies via roundtrip on tagged GFA files

**Independent Test**: Run `pixi run python test/test_all_encodings.py --int-only` and verify all integer encodings report PASS

### Implementation for User Story 1

- [X] T005 [US1] Implement integer encoding roundtrip test function in test/test_all_encodings.py
- [X] T006 [US1] Implement bgfatools invocation for integer encodings on integer fields in test/test_all_encodings.py
- [X] T007 [US1] Implement result comparison (decode output matches original) in test/test_all_encodings.py

**Checkpoint**: User Story 1 should be fully functional - all 19 integer encodings tested

---

## Phase 4: User Story 2 - Verify All String Encodings via CLI (Priority: P1)

**Goal**: Test all 21 string encoding strategies via roundtrip on tagged GFA files

**Independent Test**: Run `pixi run python test/test_all_encodings.py --str-only` and verify all string encodings report PASS

### Implementation for User Story 2

- [X] T008 [US2] Implement string encoding roundtrip test function in test/test_all_encodings.py
- [X] T009 [US2] Implement bgfatools invocation for string encodings on string fields in test/test_all_encodings.py
- [X] T010 [US2] Integrate string encoding tests with existing result tracking in test/test_all_encodings.py

**Checkpoint**: User Stories 1 AND 2 should both work independently

---

## Phase 5: User Story 3 - Automated Verification Script (Priority: P2)

**Goal**: Combine all tests into a single script that outputs a human-readable report to stdout

**Independent Test**: Run `pixi run python test/test_all_encodings.py` and verify complete report output

### Implementation for User Story 3

- [X] T011 [US3] Implement human-readable report output to stdout in test/test_all_encodings.py
- [X] T012 [US3] Implement summary statistics (pass/fail counts, timing) in test/test_all_encodings.py
- [X] T013 [US3] Add command-line options for filtering (--int-only, --str-only, --verbose) in test/test_all_encodings.py

**Checkpoint**: All user stories should now be independently functional

---

## Phase N: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [X] T014 Add Google-style docstrings to all public functions in test/test_all_encodings.py
- [X] T015 Run `pixi run ruff check` and fix any linting issues in test/test_all_encodings.py
- [X] T016 Verify script completes in under 60 seconds on standard test files

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
Task: "Implement encoding enumeration function in test/test_all_encodings.py"
Task: "Implement field type mapping in test/test_all_encodings.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1 (integer encodings)
4. **STOP and VALIDATE**: Test integer encodings independently
5. Commit if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 (integer encodings) → Test independently
3. Add User Story 2 (string encodings) → Test independently
4. Add User Story 3 (full report) → Test independently
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
