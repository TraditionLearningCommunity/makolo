# Tasks: Spec Kit Integrity Guard

**Input**: Design documents from `/specs/001-spec-kit-integrity-guard/`

**Prerequisites**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `quickstart.md`

**Tests**: Required by FR-007 and the Makolo constitution. Test work precedes implementation.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Test Foundation

**Purpose**: Establish the isolated repository-fixture harness before implementation.

- [x] T001 Create temporary-repository fixture helpers and the intact-installation success test in
  `scripts/test_check_spec_kit_integrity.py`.

**Checkpoint**: A focused test exists and fails because the verifier is not implemented yet.

---

## Phase 2: User Story 1 - Verify managed files (Priority: P1)

**Goal**: Validate existence and SHA-256 of every file declared by both managed manifests.

**Independent Test**: Clean fixture passes; missing and modified managed files fail with their paths.

- [x] T002 [US1] Extend `scripts/test_check_spec_kit_integrity.py` with missing-file and
  hash-mismatch tests.
- [x] T003 [US1] Implement manifest parsing, file existence checks, SHA-256 verification,
  aggregate findings and CLI exit behavior in `scripts/check_spec_kit_integrity.py`.

**Checkpoint**: FR-001, FR-002, FR-005 and FR-006 are satisfied by focused tests.

---

## Phase 3: User Story 2 - Detect metadata drift (Priority: P2)

**Goal**: Cross-check pinned version and active Codex integration metadata.

**Independent Test**: Malformed JSON, version drift and integration drift fixtures all fail
deterministically while consistent metadata passes.

- [x] T004 [US2] Add malformed-metadata, version-drift and integration-drift tests to
  `scripts/test_check_spec_kit_integrity.py`.
- [x] T005 [US2] Add cross-file version and active/default/installed Codex validation to
  `scripts/check_spec_kit_integrity.py`, preserving aggregate diagnostics.

**Checkpoint**: FR-003, FR-004 and FR-007 are satisfied by focused tests.

---

## Phase 4: User Story 3 - Enforce in CI (Priority: P3)

**Goal**: Run focused integrity tests and the live verifier automatically.

**Independent Test**: The CI job executes without Django/frontend dependency installation and
passes on the intact checkout.

- [x] T006 [US3] Add a lightweight `spec-kit-integrity` job to
  `.github/workflows/ci.yml` using the repository's already pinned checkout/setup-python actions.
- [x] T007 [US3] In that job run
  `python -m unittest scripts.test_check_spec_kit_integrity` followed by
  `python scripts/check_spec_kit_integrity.py`.

**Checkpoint**: FR-008 is wired without introducing a new workflow or dependency profile.

---

## Phase 5: Validation and Closure

- [x] T008 Run the focused unittest command and the live repository integrity command from
  `specs/001-spec-kit-integrity-guard/quickstart.md`; confirm both are green.
- [x] T009 Review the diff against FR-009 and the constitution; confirm no product runtime,
  migration, API, mobile, UX or domain-semantic files changed.
- [x] T010 Run the Spec Kit convergence assessment against current implementation; append tasks
  only if a real spec/plan/task gap remains.

## Dependencies & Execution Order

- T001 → T002 → T003: same test/implementation surfaces; sequential.
- T003 → T004 → T005: metadata behavior builds on the common verifier.
- T005 → T006 → T007: CI is wired only after local behavior is complete.
- T007 → T008 → T009 → T010: validation and convergence close the feature.
- No implementation tasks are marked parallel because the deliberately small pilot has one
  integrator and overlapping files; false parallelism would not improve delivery.

## Implementation Strategy

Deliver one vertically complete engineering capability:

1. make the focused tests express the contract;
2. implement local verification;
3. extend tests for metadata drift;
4. wire the existing CI;
5. validate the real checkout;
6. converge against the artifacts;
7. reconcile the stacked branch with current `main` only after PR #437 is merged.


---

## Phase 6: Convergence

- [x] T011 Restore the six Spec Kit v1.0.13 managed assets whose repository bytes contradict their
  declared managed-file SHA-256 hashes, using the pinned v1.0.13 generated output rather than
  changing the manifests, per FR-001/FR-002 (contradicts).
