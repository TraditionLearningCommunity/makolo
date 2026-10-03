# Implementation Plan: Spec Kit Integrity Guard

**Branch**: `chore/spec-kit-integrity-pilot` | **Date**: 2026-10-02 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-spec-kit-integrity-guard/spec.md`

## Summary

Add a repository-local, dependency-free integrity verifier for Makolo's checked-in Spec Kit
installation. The verifier will validate the two managed manifests, managed-file SHA-256 hashes,
and cross-file installation metadata, with focused standard-library tests. A lightweight job in
the existing CI workflow will run both the focused tests and live repository validation.

This is the first Spec Kit pilot. It is intentionally engineering-only and does not touch product
runtime.

## Work Item Contract

- **User problem**: maintainers currently have no repository-native proof that checked-in Spec Kit
  generated files still match their manifests and pinned installation metadata.
- **Owner**: single Spec Kit pilot integrator on this branch.
- **Stacked base**: `33f9bfafe35fa123a6c4e01366fa2f55c793a63b` (PR #437 head).
- **Main observed when pilot started**: `63a7de0beaba98290c27eb3c27c909bf1bd7186e`.
- **Dependency**: PR #437 must merge before this pilot is finally reconciled/integrated.
- **In scope**: `scripts/check_spec_kit_integrity.py`, focused tests, one lightweight job in
  `.github/workflows/ci.yml`, and this feature's `specs/001-...` artifacts.
- **Forbidden**: Django/business code, migrations, APIs, mobile, UX templates, domain model,
  automatic Spec Kit upgrades/repairs, network verification.
- **Acceptance**: FR-001..FR-009 and SC-001..SC-005 from the feature spec.
- **Evidence**: focused unit tests, live integrity command, CI job, final Spec Kit convergence pass.
- **Merge gate**: PR #437 merged; pilot reconciled with then-current `main`; focused tests green;
  live guard green; required PR CI green.

## Technical Context

**Language/Version**: Python 3.10+ as already exercised by Makolo CI.

**Primary Dependencies**: Python standard library only; existing GitHub Actions checkout/setup-python.

**Storage**: Repository files only; no database or persistent application state.

**Testing**: Python `unittest` focused tests plus live validation against the checkout.

**Target Platform**: Local developer checkout on supported desktop environments and GitHub Actions
Ubuntu runners.

**Project Type**: Internal repository tooling / CI guard.

**Performance Goals**: Validate the current managed Spec Kit file set in well under one second on a
normal local checkout, excluding CI setup overhead.

**Constraints**: No network; no mutation; no new dependency; deterministic diagnostics; collect
multiple findings in one run.

**Scale/Scope**: Two managed manifests and the files they declare (currently a few dozen paths).

## Brownfield Evidence and Collision Audit

Before planning:

- Current Makolo architecture and agent governance already require current-main verification,
  production-first completeness and explicit collision audits.
- The adoption branch adds only `.specify/**`, `.agents/skills/speckit-*/**` and
  `docs/operations/spec-kit-adoption.md`.
- Open PRs #429, #431 and #432 write Space web surfaces; #438 writes Mayele knowledge files; #439
  writes Mobile Space files.
- None of those open PRs writes `scripts/check_spec_kit_integrity.py`,
  `scripts/test_check_spec_kit_integrity.py`, this feature directory, or
  `.github/workflows/ci.yml`.
- No model, migration, API or permission surface is involved.

Collision result: **LOW**, with a single integrator retained because the verifier and its CI wiring
form one small coherent surface.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Result | Evidence |
|---|---|---|
| Runtime Authority / brownfield evidence | PASS | Current main, adoption head and open PR write surfaces were checked. |
| Canonical domain ownership | PASS | No business/domain state is added. |
| Identity / authority | PASS | No authorization behavior is touched. |
| Composition / privacy | PASS | Tool reads repository metadata only; no secrets/PII. |
| Projection / state discipline | PASS | No product state or projection is introduced. |
| Production-first completeness | PASS | Pilot includes real failure handling, tests and CI enforcement. |
| Tests / migrations / operations | PASS | Focused tests required; no migrations; no operational runtime change. |
| Git / parallelism | PASS | Dedicated stacked branch, explicit base, low collision, final reconciliation required. |
| Product experience doctrine | PASS | No product UX or engagement surface. |
| Agent / Spec Kit governance | PASS | Spec Kit remains process/tooling only and does not override Makolo truths. |

No constitutional exception is required.

## Project Structure

### Documentation (this feature)

```text
specs/001-spec-kit-integrity-guard/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

No external interface contract is created because this is an internal repository tool.

### Source Code (repository root)

```text
scripts/
├── check_spec_kit_integrity.py
└── test_check_spec_kit_integrity.py

.github/workflows/
└── ci.yml
```

**Structure Decision**: Reuse Makolo's existing `scripts/` convention for repository guards and
the existing general CI workflow. Do not create a new package, app or workflow file.

## Phase 0: Research Decisions

See [research.md](research.md). All implementation unknowns are resolved without external research
because the checked-in manifests and existing Makolo CI conventions are sufficient.

## Phase 1: Design

See [data-model.md](data-model.md) for the non-persistent file/validation structures and
[quickstart.md](quickstart.md) for end-to-end validation.

No API/CLI schema contract file is necessary beyond the simple documented command:
`python scripts/check_spec_kit_integrity.py`.

## Post-Design Constitution Re-check

PASS. The final design remains repository-local, dependency-free, non-mutating, bounded to
engineering tooling, covered by focused negative-path tests, and integrated through existing CI.
There are no new domain owners, persistent states, permissions, migrations or runtime services.

## Complexity Tracking

No constitutional violations or exceptional complexity.
