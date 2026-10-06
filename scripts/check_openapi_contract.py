#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(
        description="Verify that the generated OpenAPI schema preserves Makolo's supported v1 client operations."
    )
    parser.add_argument("--schema", required=True)
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()

    schema = load_json(args.schema)
    manifest = load_json(args.manifest)

    openapi_version = str(schema.get("openapi", ""))
    if not openapi_version.startswith("3."):
        raise SystemExit(f"Unsupported or missing OpenAPI version: {openapi_version!r}")

    paths = schema.get("paths") or {}
    missing = []
    for operation in manifest.get("required_operations", []):
        path = operation["path"]
        method = operation["method"].lower()
        path_item = paths.get(path)
        if not isinstance(path_item, dict) or method not in path_item:
            missing.append(f"{operation['method']} {path}")

    if missing:
        print("Breaking API contract regression detected:")
        for item in missing:
            print(f"- missing {item}")
        raise SystemExit(1)

    print(
        f"API contract OK: {len(manifest.get('required_operations', []))} "
        f"required operations preserved ({manifest.get('contract')})."
    )


if __name__ == "__main__":
    main()
