#!/usr/bin/env bash
set -euo pipefail

mode="${1:-check}"
dart_bin="${DART_BIN:-dart}"

case "$mode" in
  write)
    args=(format lib test)
    ;;
  check)
    args=(format --output=none --set-exit-if-changed lib test)
    ;;
  *)
    echo "Usage: bash tool/dart_format.sh [write|check]" >&2
    exit 2
    ;;
esac

if ! command -v "$dart_bin" >/dev/null 2>&1; then
  echo "Dart SDK unavailable. Makolo Mobile requires Flutter 3.47.3 / Dart 3.13.3 for canonical formatting." >&2
  echo "Do not hand-format or use CI-probe commits. Use the repository Mobile Format workflow on the feature branch when the SDK is unavailable." >&2
  exit 127
fi

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
mobile_dir="$(dirname "$script_dir")"
cd "$mobile_dir"

"$dart_bin" "${args[@]}"
