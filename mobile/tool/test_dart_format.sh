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
printf '%s\n' "$@" >> "$DART_FORMAT_TEST_LOG"
EOF
chmod +x "$fake_dart"

set +e
DART_BIN="$fake_dart" DART_FORMAT_TEST_LOG="$log_file" bash "$subject" check >/dev/null 2>&1
check_status=$?
set -e

if [[ "$check_status" -ne 1 ]]; then
  echo "Expected diagnostic formatter capture to exit 1, got $check_status" >&2
  exit 1
fi

grep -Fq "lib/features/discovery/discovery_mature_view.dart" "$log_file"
grep -Fq "lib/features/me/me_screen.dart" "$log_file"

: > "$log_file"
DART_BIN="$fake_dart" DART_FORMAT_TEST_LOG="$log_file" bash "$subject" write
cat > "$tmp_dir/expected-write.log" <<'EOF'
format
lib
test
EOF
diff -u "$tmp_dir/expected-write.log" "$log_file"

echo "dart_format.sh diagnostic contract OK"
