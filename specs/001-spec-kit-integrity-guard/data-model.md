# Data Model: Spec Kit Integrity Guard

This feature creates **no persistent application model and no database state**.

The implementation uses transient validation structures only:

## InstallationState

Repository-local metadata loaded from:

- `.specify/init-options.json`
- `.specify/integration.json`

Relevant values:

- pinned Spec Kit version
- active integration
- default integration
- installed integration names

## ManagedManifest

Repository-local metadata loaded from:

- `.specify/integrations/speckit.manifest.json`
- `.specify/integrations/codex.manifest.json`

Relevant values:

- integration identifier
- manifest version
- mapping of relative managed-file path → expected SHA-256 digest

## IntegrityFinding

Transient diagnostic produced during one validation run.

Fields conceptually required:

- category: malformed metadata, version drift, integration drift, missing file, hash mismatch
- source/path
- human-readable message

Findings are printed and discarded. They are not logged to a database or persisted by the tool.

## State Transitions

None. Validation is a pure read:

```text
repository files
→ parse metadata
→ validate consistency
→ hash managed files
→ findings
→ exit 0 or non-zero
```
