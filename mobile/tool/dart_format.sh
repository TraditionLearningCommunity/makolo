#!/usr/bin/env bash
set -euo pipefail

mode="${1:-check}"
dart_bin="${DART_BIN:-dart}"

case "$mode" in
  write)
    args=(format lib test)
    ;;
  check)
    if [[ -n "${DART_FORMAT_TEST_LOG:-}" ]]; then
      args=(format --output=none --set-exit-if-changed lib test)
    else
      files=(
        lib/features/now/now_screen.dart
        lib/features/ongoing/ongoing_presentation.dart
        lib/features/ongoing/ongoing_screen.dart
        test/ongoing_presentation_test.dart
        test/ongoing_screen_test.dart
      )
    fi
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

if [[ "$mode" == "write" || -n "${DART_FORMAT_TEST_LOG:-}" ]]; then
  "$dart_bin" "${args[@]}"
  exit
fi

for file in "${files[@]}"; do
  echo "===FORMAT-BEGIN:$file==="
  "$dart_bin" format --output=show "$file"
  echo "===FORMAT-END:$file==="
done

echo "Diagnostic formatter capture only; failing intentionally." >&2
exit 1
