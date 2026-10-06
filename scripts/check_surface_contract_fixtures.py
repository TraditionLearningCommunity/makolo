#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path

COMMON_RESPONSE_KEYS = {
    "surface", "actor", "viewer", "generated_at", "freshness", "selection",
    "capabilities", "handoffs", "items", "continuation", "terminal",
}

def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def normalize_path(path):
    return re.sub(
        r"(/api/v1/organizations/workspaces/)[^/]+(/)",
        r"\1{slug}\2",
        path,
        count=1,
    )

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", required=True)
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()
    fixtures = load(args.fixtures)
    manifest = load(args.manifest)
    supported = {
        (op["method"].upper(), op["path"])
        for op in manifest.get("required_operations", [])
    }

    errors = []
    for name, fixture in (fixtures.get("fixtures") or {}).items():
        method = str(fixture.get("method", "")).upper()
        path = normalize_path(str(fixture.get("path", "")))
        if (method, path) not in supported:
            errors.append(
                f"{name}: operation {method} {path} is not in supported-client-contract-v1.json"
            )
        response = fixture.get("response")
        if not isinstance(response, dict):
            errors.append(f"{name}: response must be an object")
            continue
        missing = sorted(COMMON_RESPONSE_KEYS - set(response))
        if missing:
            errors.append(
                f"{name}: response missing common keys: {', '.join(missing)}"
            )
        freshness = (response.get("freshness") or {}).get("state")
        if freshness not in {"fresh", "stale", "partial", "unavailable"}:
            errors.append(f"{name}: invalid freshness.state {freshness!r}")
        selection = (response.get("selection") or {}).get("state")
        if selection not in {"ready", "empty", "partial", "unavailable"}:
            errors.append(f"{name}: invalid selection.state {selection!r}")

    if errors:
        print("C0 surface fixture contract errors:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)

    print(f"C0 surface fixtures OK: {len(fixtures.get('fixtures') or {})} examples")

if __name__ == "__main__":
    main()
