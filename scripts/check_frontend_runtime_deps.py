#!/usr/bin/env python3
"""Fail when essential frontend runtime dependencies leak back into templates."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIRS = [ROOT / "templates"] + [
    path for path in ROOT.iterdir() if path.is_dir() and (path / "templates").exists()
]
FORBIDDEN = (
    "cdn.tailwindcss.com",
    "unpkg.com",
    "cdn.jsdelivr.net",
    "fonts.googleapis.com",
    "fonts.gstatic.com",
)
INLINE_SCRIPT = re.compile(r"<script\b(?![^>]*\bsrc\s*=)[^>]*>", re.IGNORECASE)
INLINE_EVENT_HANDLER = re.compile(
    r"\son(?:abort|auxclick|beforeinput|beforetoggle|blur|cancel|canplay|change|click|close|contextmenu|copy|cut|dblclick|drag|drop|error|focus|input|keydown|keypress|keyup|load|mousedown|mouseenter|mouseleave|mousemove|mouseout|mouseover|mouseup|paste|pause|play|pointerdown|pointerup|reset|resize|scroll|submit|toggle|touchstart|touchend|wheel)\s*=",
    re.IGNORECASE,
)


def iter_templates():
    seen = set()
    for template_dir in TEMPLATE_DIRS:
        for path in template_dir.rglob("*.html"):
            resolved = path.resolve()
            if resolved not in seen:
                seen.add(resolved)
                yield path


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def main() -> int:
    failures: list[str] = []
    for path in sorted(iter_templates()):
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(ROOT)
        lowered = text.lower()
        for forbidden in FORBIDDEN:
            start = 0
            needle = forbidden.lower()
            while True:
                index = lowered.find(needle, start)
                if index < 0:
                    break
                failures.append(f"{rel}:{line_number(text, index)} forbidden runtime dependency: {forbidden}")
                start = index + len(needle)
        for match in INLINE_SCRIPT.finditer(text):
            tag = match.group(0).lower()
            if 'type="application/json"' in tag or "type='application/json'" in tag:
                continue
            failures.append(f"{rel}:{line_number(text, match.start())} inline JavaScript is incompatible with script-src 'self'")
        for match in INLINE_EVENT_HANDLER.finditer(text):
            failures.append(
                f"{rel}:{line_number(text, match.start())} inline event handler is incompatible with script-src 'self'"
            )

    if failures:
        print("Frontend runtime dependency check failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print("Frontend runtime dependency check passed: no critical CDN, inline-script or inline-handler regressions found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
