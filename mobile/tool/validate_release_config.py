#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from urllib.parse import urlparse


REQUIRED_TRUE = (
    "MAKOLO_FIREBASE_ENABLED",
    "MAKOLO_SENTRY_ENABLED",
    "MAKOLO_APP_LINKS_ENABLED",
)


def fail(message):
    raise SystemExit(message)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--environment", choices=["beta", "prod"], required=True)
    args = parser.parse_args()

    payload = json.loads(Path(args.config).read_text(encoding="utf-8"))
    expected = args.environment
    actual = str(payload.get("MAKOLO_ENVIRONMENT", "")).strip().lower()
    if actual != expected:
        fail(f"MAKOLO_ENVIRONMENT must be {expected!r}, got {actual!r}.")

    raw_api = str(payload.get("MAKOLO_API_BASE_URL", "")).strip()
    parsed = urlparse(raw_api)
    if parsed.scheme != "https" or not parsed.netloc:
        fail("Release MAKOLO_API_BASE_URL must be an absolute https URL.")

    for key in REQUIRED_TRUE:
        if str(payload.get(key, "")).strip().lower() != "true":
            fail(f"{key}=true is required for beta/prod release.")

    dsn = str(payload.get("MAKOLO_SENTRY_DSN", "")).strip()
    if not dsn:
        fail("MAKOLO_SENTRY_DSN is required when Sentry is enabled.")

    release = str(payload.get("MAKOLO_RELEASE", "")).strip()
    if not release:
        fail("MAKOLO_RELEASE is required for release observability.")

    scheme = str(payload.get("MAKOLO_APP_LINKS_SCHEME", "")).strip().lower()
    host = str(payload.get("MAKOLO_APP_LINKS_HOST", "")).strip()
    if scheme != "https" or not host or "/" in host or "://" in host:
        fail("Release App Links require https and a bare host name.")

    print(f"Makolo {expected} release config: OK")


if __name__ == "__main__":
    main()
