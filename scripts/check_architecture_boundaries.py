#!/usr/bin/env python3
"""Static architecture guards for Makolo's modular monolith.

The goal is not to ban cross-domain composition. Makolo is a modular monolith
and read models legitimately compose canonical owners. The guard protects the
direction of dependencies instead:

owner -> selector/service -> read model/projection -> orchestration -> presentation

It deliberately ignores tests, migrations, management commands and template tags.
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

IGNORED_PARTS = {
    "migrations",
    "management",
    "templatetags",
    "__pycache__",
}

HIGH_LEVEL_CORE_PREFIXES = (
    "core.home_presentation",
    "core.history_presentation",
    "core.participant_presentation",
    "core.product_language",
    "core.mature_experience_views",
    "core.participant_views",
    "core.views",
)

MUTATING_MANAGER_METHODS = {
    "create",
    "get_or_create",
    "update_or_create",
    "bulk_create",
    "bulk_update",
}


@dataclass(frozen=True)
class Violation:
    path: Path
    line: int
    message: str

    def render(self) -> str:
        relative = self.path.relative_to(ROOT)
        return f"{relative}:{self.line}: {self.message}"


def _is_production_python(path: Path) -> bool:
    if path.suffix != ".py":
        return False
    relative = path.relative_to(ROOT)
    if any(part in IGNORED_PARTS for part in relative.parts):
        return False
    name = path.name
    if name.startswith("test") or "/tests/" in relative.as_posix():
        return False
    return True


def _module_from_import(node: ast.AST) -> str | None:
    if isinstance(node, ast.ImportFrom):
        return node.module or ""
    if isinstance(node, ast.Import):
        return node.names[0].name if node.names else ""
    return None


def _layer(path: Path) -> str | None:
    relative = path.relative_to(ROOT).as_posix()
    name = path.name
    if relative.startswith("core/read_models/"):
        return "read_model"
    if relative.startswith("core/api/") and (
        "projection" in name or name in {"personal_projections.py", "detail_projections.py"}
    ):
        return "projection"
    if name.endswith("_orchestration.py"):
        return "orchestration"
    if name.endswith("_presentation.py") or name in {
        "home_presentation.py",
        "history_presentation.py",
        "participant_presentation.py",
    }:
        return "presentation"
    return None


def _call_name(node: ast.Call) -> tuple[str | None, str]:
    func = node.func
    if not isinstance(func, ast.Attribute):
        return None, ""
    try:
        base = ast.unparse(func.value)
    except Exception:
        base = ""
    return func.attr, base


def inspect_file(path: Path) -> list[Violation]:
    layer = _layer(path)
    relative = path.relative_to(ROOT).as_posix()
    if layer is None and relative.startswith("core/"):
        return []
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (OSError, SyntaxError) as exc:
        return [Violation(path, getattr(exc, "lineno", 1) or 1, f"cannot parse: {exc}")]

    violations: list[Violation] = []
    is_core = relative.startswith("core/")

    for node in ast.walk(tree):
        module = _module_from_import(node)
        if module is not None:
            line = getattr(node, "lineno", 1)

            if layer in {"read_model", "projection"}:
                if (
                    module.startswith("django.shortcuts")
                    or module.startswith("rest_framework")
                    or module.endswith(".views")
                    or ".views." in module
                    or module.endswith(".urls")
                    or ".urls." in module
                    or "presentation" in module
                    or "orchestration" in module
                ):
                    violations.append(
                        Violation(
                            path,
                            line,
                            f"{layer} imports higher-level module {module!r}",
                        )
                    )

            if layer == "orchestration" and (
                "presentation" in module
                or module.endswith(".views")
                or ".views." in module
                or module.endswith(".urls")
                or ".urls." in module
            ):
                violations.append(
                    Violation(
                        path,
                        line,
                        f"orchestration imports presentation/view module {module!r}",
                    )
                )

            if not is_core and module.startswith(HIGH_LEVEL_CORE_PREFIXES):
                violations.append(
                    Violation(
                        path,
                        line,
                        f"domain/runtime module depends on high-level core surface {module!r}",
                    )
                )

        if layer in {"read_model", "projection", "presentation"} and isinstance(node, ast.Call):
            method, base = _call_name(node)
            line = getattr(node, "lineno", 1)
            if method in {"save", "delete"}:
                violations.append(
                    Violation(
                        path,
                        line,
                        f"{layer} performs ORM-like mutation via .{method}()",
                    )
                )
            if method in MUTATING_MANAGER_METHODS and (
                base.endswith(".objects") or ".objects." in base
            ):
                violations.append(
                    Violation(
                        path,
                        line,
                        f"{layer} performs ORM manager mutation via {method}()",
                    )
                )

    return violations


def scan(root: Path = ROOT) -> list[Violation]:
    violations: list[Violation] = []
    for path in sorted(root.rglob("*.py")):
        if not _is_production_python(path):
            continue
        relative = path.relative_to(root).as_posix()
        if relative.startswith(".venv/"):
            continue
        if relative.startswith("core/") or not relative.startswith(
            ("scripts/", "config/", "frontend/", "mobile/")
        ):
            violations.extend(inspect_file(path))
    return violations


def main() -> int:
    violations = scan()
    if violations:
        print("Makolo architecture boundary violations:")
        for violation in violations:
            print(f"- {violation.render()}")
        return 1
    print("Makolo architecture boundaries: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
