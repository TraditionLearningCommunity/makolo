#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"
source scripts/e2e-env.sh

if [[ "${E2E_SKIP_PREP:-0}" != "1" ]]; then
  bash scripts/prepare-e2e.sh
fi

SERVER_LOG="${E2E_SERVER_LOG:-/tmp/makolo-e2e-server.log}"
python manage.py runserver 127.0.0.1:8000 --noreload >"$SERVER_LOG" 2>&1 &
SERVER_PID=$!
cleanup() {
  kill "$SERVER_PID" 2>/dev/null || true
  wait "$SERVER_PID" 2>/dev/null || true
}
trap cleanup EXIT

python - <<'PY'
import os
import time
from urllib.request import urlopen

url = os.environ.get("PLAYWRIGHT_BASE_URL", "http://127.0.0.1:8000") + "/api/v1/health/"
last_error = None
for _ in range(100):
    try:
        with urlopen(url, timeout=1) as response:
            if response.status == 200:
                raise SystemExit(0)
    except Exception as exc:
        last_error = exc
        time.sleep(0.1)
raise SystemExit(f"Makolo E2E server did not become ready: {last_error}")
PY

npx playwright test "$@"
