#!/usr/bin/env bash
set -euo pipefail

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
subject="$script_dir/dart_format.sh"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

fake_dart="$tmp_dir/dart"
log_file="$tmp_dir/args.log"

cat > "$fake_dart" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$@" > "$DART_FORMAT_TEST_LOG"
EOF
chmod +x "$fake_dart"

DART_BIN="$fake_dart" DART_FORMAT_TEST_LOG="$log_file" bash "$subject" check
cat > "$tmp_dir/expected-check.log" <<'EOF'
format
--output=none
--set-exit-if-changed
lib
test
EOF
diff -u "$tmp_dir/expected-check.log" "$log_file"

DART_BIN="$fake_dart" DART_FORMAT_TEST_LOG="$log_file" bash "$subject" write
cat > "$tmp_dir/expected-write.log" <<'EOF'
format
lib
test
EOF
diff -u "$tmp_dir/expected-write.log" "$log_file"

set +e
bash "$subject" unsupported >"$tmp_dir/unsupported.out" 2>&1
unsupported_status=$?
DART_BIN="$tmp_dir/missing-dart" bash "$subject" check >"$tmp_dir/missing.out" 2>&1
missing_status=$?
set -e

if [[ "$unsupported_status" -ne 2 ]]; then
  echo "Expected unsupported mode to exit 2, got $unsupported_status" >&2
  exit 1
fi

if [[ "$missing_status" -ne 127 ]]; then
  echo "Expected missing Dart SDK to exit 127, got $missing_status" >&2
  exit 1
fi

grep -Fq "Usage: bash tool/dart_format.sh [write|check]" "$tmp_dir/unsupported.out"
grep -Fq "Dart SDK unavailable." "$tmp_dir/missing.out"
grep -Fq "Mobile Format workflow" "$tmp_dir/missing.out"

echo "dart_format.sh contract OK"
