#!/usr/bin/env python3
"""Validate that collectstatic produced manifest entries for Makolo's critical assets."""

from __future__ import annotations

import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
STATIC_ROOT = Path(os.environ.get("MAKOLO_STATIC_ROOT", ROOT / "staticfiles"))
MANIFEST = STATIC_ROOT / "staticfiles.json"
CRITICAL_ASSETS = (
    "dist/makolo.css",
    "dist/makolo.js",
    "dist/theme-init.js",
    "dist/scanner.js",
    "dist/qr-scanner.umd.min.js",
    "dist/qr-scanner-worker.min.js",
    "css/makolo-ui.css",
    "css/makolo-compat.css",
    "css/makolo-brand.css",
)


def main() -> int:
    if not MANIFEST.exists():
        print(f"Missing static manifest: {MANIFEST}")
        return 1

    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    paths = payload.get("paths", {})
    failures: list[str] = []

    for asset in CRITICAL_ASSETS:
        hashed = paths.get(asset)
        if not hashed:
            failures.append(f"missing manifest entry: {asset}")
            continue
        if not (STATIC_ROOT / hashed).exists():
            failures.append(f"manifest target does not exist: {asset} -> {hashed}")

    if failures:
        print("Static manifest validation failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print(f"Static manifest validation passed for {len(CRITICAL_ASSETS)} critical assets.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
