#!/usr/bin/env python3
"""Fail CI when a GitHub Actions workflow uses a mutable external ref."""

from __future__ import annotations

import re
import sys
from pathlib import Path


WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"
USES_RE = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)", re.MULTILINE)
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def main() -> int:
    failures: list[str] = []
    for workflow in sorted(WORKFLOWS.glob("*.yml")):
        text = workflow.read_text(encoding="utf-8")
        for value in USES_RE.findall(text):
            if value.startswith("./"):
                continue
            if "@" not in value:
                failures.append(f"{workflow.relative_to(WORKFLOWS.parent.parent)}: missing ref for {value}")
                continue
            action, ref = value.rsplit("@", 1)
            if not SHA_RE.fullmatch(ref):
                failures.append(
                    f"{workflow.relative_to(WORKFLOWS.parent.parent)}: {action}@{ref} is mutable; pin a 40-char commit SHA"
                )
    if failures:
        print("Unpinned GitHub Actions references found:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("All external GitHub Actions references are pinned to immutable commit SHAs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
