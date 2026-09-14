#!/usr/bin/env python3
"""Fail CI when a main-governing workflow uses a mutable external ref."""

from __future__ import annotations

import re
from pathlib import Path


WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"
USES_RE = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)", re.MULTILINE)
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def governs_main(text: str) -> bool:
    """Only enforce workflows that can run for the current main train."""
    return bool(re.search(r"(?m)^\s*-?\s*main\s*$", text))


def main() -> int:
    failures: list[str] = []
    checked: list[str] = []
    skipped: list[str] = []
    for workflow in sorted(WORKFLOWS.glob("*.yml")):
        text = workflow.read_text(encoding="utf-8")
        relative = str(workflow.relative_to(WORKFLOWS.parent.parent))
        if not governs_main(text):
            skipped.append(relative)
            continue
        checked.append(relative)
        for value in USES_RE.findall(text):
            if value.startswith("./"):
                continue
            if "@" not in value:
                failures.append(f"{relative}: missing ref for {value}")
                continue
            action, ref = value.rsplit("@", 1)
            if not SHA_RE.fullmatch(ref):
                failures.append(f"{relative}: {action}@{ref} is mutable; pin a 40-char commit SHA")
    if failures:
        print("Unpinned GitHub Actions references found in main-governing workflows:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(f"Pinned workflow guard passed for {len(checked)} main-governing workflows.")
    if skipped:
        print("Skipped workflows not wired to main: " + ", ".join(skipped))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
