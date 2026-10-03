from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.check_spec_kit_integrity import validate_repository


VERSION = "1.0.13"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _build_fixture(root: Path) -> dict[str, Path]:
    template = root / ".specify" / "templates" / "spec-template.md"
    skill = root / ".agents" / "skills" / "speckit-specify" / "SKILL.md"
    template.parent.mkdir(parents=True, exist_ok=True)
    skill.parent.mkdir(parents=True, exist_ok=True)
    template.write_text("spec template\n", encoding="utf-8")
    skill.write_text("codex skill\n", encoding="utf-8")

    init_options = root / ".specify" / "init-options.json"
    integration_state = root / ".specify" / "integration.json"
    speckit_manifest = root / ".specify" / "integrations" / "speckit.manifest.json"
    codex_manifest = root / ".specify" / "integrations" / "codex.manifest.json"

    _write_json(
        init_options,
        {
            "ai": "codex",
            "ai_skills": True,
            "feature_numbering": "sequential",
            "here": True,
            "integration": "codex",
            "script": "ps",
            "speckit_version": VERSION,
        },
    )
    _write_json(
        integration_state,
        {
            "version": VERSION,
            "integration_state_schema": 1,
            "installed_integrations": ["codex"],
            "integration_settings": {"codex": {"script": "ps", "invoke_separator": "-"}},
            "integration": "codex",
            "default_integration": "codex",
        },
    )
    _write_json(
        speckit_manifest,
        {
            "integration": "speckit",
            "version": VERSION,
            "installed_at": "fixture",
            "files": {
                ".specify/templates/spec-template.md": _sha256(template),
            },
        },
    )
    _write_json(
        codex_manifest,
        {
            "integration": "codex",
            "version": VERSION,
            "installed_at": "fixture",
            "files": {
                ".agents/skills/speckit-specify/SKILL.md": _sha256(skill),
            },
        },
    )

    return {
        "template": template,
        "skill": skill,
        "init_options": init_options,
        "integration_state": integration_state,
        "speckit_manifest": speckit_manifest,
        "codex_manifest": codex_manifest,
    }


class SpecKitIntegrityTests(unittest.TestCase):
    def test_clean_installation_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _build_fixture(root)

            result = validate_repository(root)

            self.assertEqual(result.findings, [])
            self.assertEqual(result.manifests_checked, 2)
            self.assertEqual(result.files_checked, 2)

    def test_missing_managed_file_fails_with_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = _build_fixture(root)
            paths["skill"].unlink()

            result = validate_repository(root)

            self.assertTrue(any("missing managed file" in item for item in result.findings))
            self.assertTrue(any(".agents/skills/speckit-specify/SKILL.md" in item for item in result.findings))

    def test_modified_managed_file_fails_with_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = _build_fixture(root)
            paths["template"].write_text("tampered\n", encoding="utf-8")

            result = validate_repository(root)

            self.assertTrue(any("hash mismatch" in item for item in result.findings))
            self.assertTrue(any(".specify/templates/spec-template.md" in item for item in result.findings))

    def test_malformed_metadata_fails_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = _build_fixture(root)
            paths["init_options"].write_text("{not-json", encoding="utf-8")

            result = validate_repository(root)

            self.assertTrue(any("invalid JSON" in item for item in result.findings))
            self.assertTrue(any(".specify/init-options.json" in item for item in result.findings))

    def test_version_drift_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = _build_fixture(root)
            manifest = json.loads(paths["codex_manifest"].read_text(encoding="utf-8"))
            manifest["version"] = "1.0.12"
            _write_json(paths["codex_manifest"], manifest)

            result = validate_repository(root)

            self.assertTrue(any("version mismatch" in item for item in result.findings))
            self.assertTrue(any("codex.manifest.json" in item for item in result.findings))

    def test_integration_drift_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = _build_fixture(root)
            state = json.loads(paths["integration_state"].read_text(encoding="utf-8"))
            state["integration"] = "claude"
            state["default_integration"] = "claude"
            state["installed_integrations"] = ["claude"]
            _write_json(paths["integration_state"], state)

            result = validate_repository(root)

            self.assertTrue(any("active integration" in item for item in result.findings))
            self.assertTrue(any("default integration" in item for item in result.findings))
            self.assertTrue(any("installed integrations" in item for item in result.findings))


if __name__ == "__main__":
    unittest.main()
