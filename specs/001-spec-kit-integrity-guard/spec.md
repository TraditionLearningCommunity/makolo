# Feature Specification: Spec Kit Integrity Guard

**Feature Branch**: `chore/spec-kit-integrity-pilot`

**Created**: 2026-10-02

**Status**: Ready for planning

**Input**: User description: "Use the first real Spec Kit pilot to protect Makolo's checked-in Spec Kit installation from silent drift, without touching product runtime."

## User Scenarios & Testing

### User Story 1 - Verify the checked-in installation (Priority: P1)

A Makolo maintainer can run one repository-local verification and know whether the checked-in
Spec Kit installation still matches the managed-file hashes declared by its manifests.

**Why this priority**: The adoption is only trustworthy if generated tooling cannot silently drift
from the version and files the repository claims to contain.

**Independent Test**: Run the integrity guard on an intact checkout. It exits successfully and
reports that both managed manifests were validated.

**Acceptance Scenarios**:

1. **Given** an intact checkout, **When** the maintainer runs the guard, **Then** the command exits
   successfully and reports no integrity errors.
2. **Given** a managed Spec Kit or Codex skill file whose content differs from its manifest hash,
   **When** the maintainer runs the guard, **Then** the command exits non-zero and identifies the
   mismatched path.
3. **Given** a managed file that is missing, **When** the maintainer runs the guard, **Then** the
   command exits non-zero and identifies the missing path.

---

### User Story 2 - Detect installation metadata drift (Priority: P2)

A Makolo maintainer can detect when the repository's Spec Kit installation metadata disagrees
about the installed version or active integration.

**Why this priority**: File hashes alone do not detect a repository that claims inconsistent
versions or integration state.

**Independent Test**: Validate a fixture where version/integration metadata is intentionally
inconsistent and confirm that the guard fails with a deterministic diagnostic.

**Acceptance Scenarios**:

1. **Given** manifests and installation state that agree, **When** the guard runs, **Then** no
   metadata error is reported.
2. **Given** a manifest version that differs from the pinned installation version, **When** the
   guard runs, **Then** the command exits non-zero and describes the version mismatch.
3. **Given** an active integration other than the checked-in Codex integration, **When** the guard
   runs, **Then** the command exits non-zero and describes the integration mismatch.

---

### User Story 3 - Enforce the guard in repository CI (Priority: P3)

A Makolo contributor receives automated feedback when a pull request or main-branch change breaks
the checked-in Spec Kit installation.

**Why this priority**: Local verification is useful, but repository protection requires the same
check to run automatically.

**Independent Test**: Run the lightweight guard job in CI on a branch containing the intact
installation and confirm success; its script-level tests must also prove missing/tampered metadata
is rejected.

**Acceptance Scenarios**:

1. **Given** a change that leaves Spec Kit intact, **When** the normal CI workflow runs, **Then**
   the Spec Kit integrity job passes.
2. **Given** a change that tampers with a managed file or installation metadata, **When** the guard
   is executed by its test suite, **Then** the failure is detected without requiring network access.

### Edge Cases

- Extra files that are not declared by a Spec Kit manifest do not cause failure merely by existing.
- Manifest timestamps and JSON key ordering do not affect validation.
- Malformed or unreadable manifest/state JSON causes a clear non-zero failure rather than a stack
  trace presented as success.
- The Makolo constitution is intentionally project-owned and is not falsely expected to be a
  managed upstream file hash unless a manifest explicitly declares it.
- The verifier never downloads upstream Spec Kit or contacts GitHub to repair or compare content.

## Requirements

### Functional Requirements

- **FR-001**: The repository MUST provide one local command that validates the managed files
  declared by both the Spec Kit core manifest and the Codex integration manifest.
- **FR-002**: For every declared managed file, the verifier MUST check that the file exists and its
  SHA-256 digest exactly matches the manifest value.
- **FR-003**: The verifier MUST check that the pinned Spec Kit version agrees across initialization
  metadata, integration metadata, and both managed manifests.
- **FR-004**: The verifier MUST check that the active/default integration is Codex and that Codex
  is listed among installed integrations.
- **FR-005**: The verifier MUST report all detected integrity problems in one run and exit non-zero
  when any problem exists.
- **FR-006**: The verifier MUST use only repository-local data and MUST NOT perform network access,
  auto-upgrade, auto-repair, or mutation.
- **FR-007**: Automated tests MUST cover an intact installation, a missing managed file, a modified
  managed file, malformed metadata, and version/integration drift.
- **FR-008**: The existing CI workflow MUST run the verifier and its focused tests in a lightweight
  job on the same non-ignored changes that trigger the general CI workflow.
- **FR-009**: The feature MUST NOT modify product runtime, business models, migrations, APIs,
  mobile code, product templates, or canonical domain semantics.

## Success Criteria

### Measurable Outcomes

- **SC-001**: An intact repository produces zero integrity findings and a successful exit status.
- **SC-002**: Each required negative fixture (missing file, changed file, malformed metadata,
  version drift, integration drift) produces at least one deterministic finding and a non-zero
  result.
- **SC-003**: The verifier completes using repository-local files only and requires no new runtime
  dependency.
- **SC-004**: CI exposes a dedicated Spec Kit integrity job whose focused tests and live repository
  validation both pass before the pilot is considered complete.
- **SC-005**: The pilot changes only Spec Kit feature artifacts, the integrity tooling/tests, and
  the CI workflow needed to execute the guard.

## Assumptions

- The checked-in manifests remain the authority for which generated Spec Kit/Codex files are
  managed by the pinned installation.
- Makolo intentionally pins Spec Kit rather than automatically following the newest upstream
  release.
- Python from the repository's existing CI environment is sufficient because the verifier only
  needs standard-library functionality.
- The first pilot is an engineering/developer capability; no end-user Makolo UI is required.
