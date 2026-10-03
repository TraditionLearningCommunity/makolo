# Quickstart: Spec Kit Integrity Guard

## Prerequisites

- Checkout containing the Spec Kit adoption.
- Python available from the repository's supported development/CI environment.
- No network access is required.

## Focused tests

```powershell
python -m unittest scripts.test_check_spec_kit_integrity
```

Expected result: all focused tests pass.

## Validate the real checkout

```powershell
python scripts/check_spec_kit_integrity.py
```

Expected result: exit code `0` and a concise success summary covering both managed manifests.

## Negative-path proof

The focused test suite creates isolated temporary repository fixtures and proves that validation
fails for at least:

- a missing managed file;
- a modified managed file;
- malformed metadata;
- pinned-version drift;
- active-integration drift.

It MUST NOT intentionally corrupt the actual repository checkout.

## CI proof

The existing `CI` workflow exposes a lightweight `spec-kit-integrity` job that runs:

1. focused integrity tests;
2. the verifier against the checked-out repository.

The pilot is not complete until that job is green on its PR after reconciliation with current
`main`.
