#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
selector="$root/tool/ci_scope.sh"

value_for() {
  local key="$1"
  shift
  printf '%s\n' "$@" | bash "$selector" | awk -F= -v key="$key" '$1 == key { print $2 }'
}

assert_eq() {
  local expected="$1"
  local actual="$2"
  local label="$3"
  if [[ "$expected" != "$actual" ]]; then
    echo "scope test failed: $label expected=$expected actual=$actual" >&2
    exit 1
  fi
}

assert_eq false "$(value_for flutter docs/architecture/mobile-production-infrastructure.md)" "docs skip Flutter"
assert_eq true "$(value_for visual mobile/lib/design/theme.dart)" "design is visual"
assert_eq true "$(value_for golden mobile/assets/brand/makolo-mark-violet.svg)" "asset runs golden"
assert_eq true "$(value_for network mobile/lib/network/makolo_api_client.dart)" "network scope"
assert_eq false "$(value_for android_build mobile/lib/network/makolo_api_client.dart)" "network skips native build"
assert_eq true "$(value_for drift mobile/lib/data/local/tables.dart)" "drift scope"
assert_eq true "$(value_for android_build mobile/pubspec.yaml)" "dependency builds Android"
assert_eq true "$(value_for full_test mobile/pubspec.lock)" "dependency runs full tests"
assert_eq true "$(value_for full mobile/lib/unclassified_core.dart)" "unknown mobile falls back broad"
assert_eq false "$(value_for flutter profiles/models.py)" "backend does not trigger Flutter"

echo "mobile CI scope selector: ok"
