import logging
import re


_PASSWORD_RESET_PATH_RE = re.compile(
    r"(/account/password-reset/)[^/\s?]+/[^/\s?]+",
    re.IGNORECASE,
)
_KEY_VALUE_SECRET_RE = re.compile(
    r"(?i)\b(authorization|password|passwd|token|secret|signature|cookie|sessionid)"
    r"(\s*[:=]\s*)([^\s,;&]+)"
)
_BEARER_RE = re.compile(r"(?i)\b(Bearer)\s+[A-Za-z0-9._~+/=-]+")


def redact_sensitive_text(value: str) -> str:
    text = str(value)
    text = _PASSWORD_RESET_PATH_RE.sub(r"\1[redacted]/[redacted]", text)
    text = _BEARER_RE.sub(r"\1 [redacted]", text)
    return _KEY_VALUE_SECRET_RE.sub(r"\1\2[redacted]", text)


class SensitiveDataFilter(logging.Filter):
    """Best-effort log redaction for common secrets and reset-token URLs."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            rendered = record.getMessage()
        except Exception:
            return True
        record.msg = redact_sensitive_text(rendered)
        record.args = ()
        return True
