#!/usr/bin/env bash
set -euo pipefail

export DJANGO_ENV="${DJANGO_ENV:-e2e}"
export DJANGO_DEBUG="${DJANGO_DEBUG:-False}"
export DJANGO_SECRET_KEY="${DJANGO_SECRET_KEY:-makolo-e2e-only-secret-key-never-production-2026}"
export DJANGO_ALLOWED_HOSTS="${DJANGO_ALLOWED_HOSTS:-127.0.0.1,localhost}"
export DJANGO_DB_PATH="${DJANGO_DB_PATH:-/tmp/makolo-e2e.sqlite3}"
export DJANGO_EMAIL_FILE_PATH="${DJANGO_EMAIL_FILE_PATH:-/tmp/makolo-e2e-emails}"
export MAKOLO_PUBLIC_BASE_URL="${MAKOLO_PUBLIC_BASE_URL:-http://127.0.0.1:8000}"
export PAYMENTS_SANDBOX_ENABLED="${PAYMENTS_SANDBOX_ENABLED:-True}"
export PAYMENTS_WEBHOOK_SECRET="${PAYMENTS_WEBHOOK_SECRET:-makolo-e2e-webhook-secret}"
export PLAYWRIGHT_BASE_URL="${PLAYWRIGHT_BASE_URL:-http://127.0.0.1:8000}"
