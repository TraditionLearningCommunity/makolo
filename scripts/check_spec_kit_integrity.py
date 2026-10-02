#!/usr/bin/env python3
"""Validate the checked-in Spec Kit installation without network access."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INIT_OPTIONS = Path(".specify/init-options.json")
INTEGRATION_STATE = Path(".specify/integration.json")
MANIFESTS = (
    (Path(".specify/integrations/speckit.manifest.json"), "speckit"),
    (Path(".specify/integrations/codex.manifest.json"), "codex"),
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class ValidationResult:
    findings: list[str]
    manifests_checked: int
    files_checked: int
    version: str | None = None


def _load_json(root: Path, relative: Path, findings: list[str]) -> dict[str, Any] | None:
    path = root / relative
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        findings.append(f"{relative.as_posix()}: cannot read metadata ({exc})")
        return None

    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        findings.append(
            f"{relative.as_posix()}: invalid JSON at line {exc.lineno}, column {exc.colno}"
        )
        return None

    if not isinstance(value, dict):
        findings.append(f"{relative.as_posix()}: expected a JSON object")
        return None
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _managed_path(
    root: Path,
    relative_text: object,
    source: Path,
    findings: list[str],
) -> Path | None:
    if not isinstance(relative_text, str) or not relative_text.strip():
        findings.append(f"{source.as_posix()}: managed file path must be a non-empty string")
        return None

    relative = Path(relative_text)
    if relative.is_absolute() or ".." in relative.parts:
        findings.append(f"{source.as_posix()}: unsafe managed path {relative_text!r}")
        return None

    root_resolved = root.resolve()
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError:
        findings.append(f"{source.as_posix()}: managed path escapes repository: {relative_text}")
        return None
    return candidate


def validate_repository(root: Path = ROOT) -> ValidationResult:
    """Return all integrity findings for the Spec Kit installation under *root*."""

    root = root.resolve()
    findings: list[str] = []
    files_checked = 0
    manifests_checked = 0

    init_options = _load_json(root, INIT_OPTIONS, findings)
    integration_state = _load_json(root, INTEGRATION_STATE, findings)

    manifest_values: list[tuple[Path, str, dict[str, Any]]] = []
    for relative, expected_integration in MANIFESTS:
        manifest = _load_json(root, relative, findings)
        if manifest is None:
            continue
        manifests_checked += 1
        manifest_values.append((relative, expected_integration, manifest))

        actual_integration = manifest.get("integration")
        if actual_integration != expected_integration:
            findings.append(
                f"{relative.as_posix()}: integration mismatch "
                f"(expected {expected_integration!r}, got {actual_integration!r})"
            )

        files = manifest.get("files")
        if not isinstance(files, dict):
            findings.append(f"{relative.as_posix()}: 'files' must be a JSON object")
            continue

        for managed_relative, expected_digest in files.items():
            files_checked += 1
            managed = _managed_path(root, managed_relative, relative, findings)
            if managed is None:
                continue
            if not isinstance(expected_digest, str) or not SHA256_RE.fullmatch(
                expected_digest.lower()
            ):
                findings.append(
                    f"{relative.as_posix()}: invalid SHA-256 for {managed_relative!r}"
                )
                continue
            if not managed.is_file():
                findings.append(f"{managed_relative}: missing managed file")
                continue

            actual_digest = _sha256(managed)
            if actual_digest != expected_digest.lower():
                findings.append(
                    f"{managed_relative}: hash mismatch "
                    f"(expected {expected_digest.lower()}, got {actual_digest})"
                )

    pinned_version: str | None = None
    if init_options is not None:
        raw_version = init_options.get("speckit_version")
        if isinstance(raw_version, str) and raw_version.strip():
            pinned_version = raw_version.strip()
        else:
            findings.append(
                f"{INIT_OPTIONS.as_posix()}: missing non-empty 'speckit_version'"
            )

        for key in ("ai", "integration"):
            if init_options.get(key) != "codex":
                findings.append(
                    f"{INIT_OPTIONS.as_posix()}: {key} must be 'codex', "
                    f"got {init_options.get(key)!r}"
                )

    if integration_state is not None:
        active = integration_state.get("integration")
        default = integration_state.get("default_integration")
        installed = integration_state.get("installed_integrations")

        if active != "codex":
            findings.append(
                f"{INTEGRATION_STATE.as_posix()}: active integration must be 'codex', "
                f"got {active!r}"
            )
        if default != "codex":
            findings.append(
                f"{INTEGRATION_STATE.as_posix()}: default integration must be 'codex', "
                f"got {default!r}"
            )
        if not isinstance(installed, list) or "codex" not in installed:
            findings.append(
                f"{INTEGRATION_STATE.as_posix()}: installed integrations must include 'codex'"
            )

    if pinned_version is not None:
        version_sources: list[tuple[Path, object]] = []
        if integration_state is not None:
            version_sources.append((INTEGRATION_STATE, integration_state.get("version")))
        for relative, _expected_integration, manifest in manifest_values:
            version_sources.append((relative, manifest.get("version")))

        for source, actual_version in version_sources:
            if actual_version != pinned_version:
                findings.append(
                    f"{source.as_posix()}: version mismatch "
                    f"(expected {pinned_version!r}, got {actual_version!r})"
                )

    return ValidationResult(
        findings=findings,
        manifests_checked=manifests_checked,
        files_checked=files_checked,
        version=pinned_version,
    )


def main() -> int:
    result = validate_repository()
    if result.findings:
        print(f"Spec Kit integrity: FAILED ({len(result.findings)} finding(s))")
        for finding in result.findings:
            print(f"- {finding}")
        return 1

    print(
        "Spec Kit integrity: ok "
        f"({result.manifests_checked} manifests, {result.files_checked} managed files, "
        f"version {result.version}, integration codex)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
