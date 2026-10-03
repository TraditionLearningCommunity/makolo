#!/usr/bin/env bash
set -euo pipefail

mode="${1:-check}"
dart_bin="${DART_BIN:-dart}"

case "$mode" in
  write)
    args=(format lib test)
    ;;
  check)
    files=(
      lib/features/discovery/discovery_mature_view.dart
      lib/features/me/me_screen.dart
    )
    ;;
  *)
    echo "Usage: bash tool/dart_format.sh [write|check]" >&2
    exit 2
    ;;
esac

if ! command -v "$dart_bin" >/dev/null 2>&1; then
  echo "Dart SDK unavailable. Makolo Mobile requires Flutter 3.47.3 / Dart 3.13.3 for canonical formatting." >&2
  exit 127
fi

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
mobile_dir="$(dirname "$script_dir")"
cd "$mobile_dir"

if [[ "$mode" == "write" ]]; then
  "$dart_bin" "${args[@]}"
  exit
fi

for file in "${files[@]}"; do
  echo "===FORMAT-BEGIN:$file==="
  "$dart_bin" format --output=show "$file"
  echo "===FORMAT-END:$file==="
done

echo "Formatter capture complete; failing intentionally." >&2
exit 1
