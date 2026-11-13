#!/usr/bin/env python3
"""Prevent principal Makolo surfaces from recreating shared action components.

This validates the Group 1 migration contract without interpreting permissions.
The runtime CSS, DOM behavior and owner commands have separate integration tests.
"""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

WEB_SURFACES: dict[str, tuple[str, ...]] = {
    "templates/core/participant_home.html": ("data-mk-surface=\"now\"", "mk-action-button"),
    "templates/core/_now_stream_items.html": ("mk-action-button", "mk-disclosure-trigger"),
    "templates/discovery/home.html": ("data-mk-surface=\"discover\"", "mk-action-button"),
    "templates/discovery/_universal_card.html": ("mk-action-button",),
    "templates/core/_participant_ongoing_content.html": (
        "data-mk-surface=\"ongoing\"",
        "mk-action-button",
    ),
    "templates/core/_ongoing_unit.html": ("mk-action-button", "mk-disclosure-trigger"),
    "templates/core/participant_me.html": ("data-mk-surface=\"me\"", "mk-action-button"),
    "templates/core/makolo_mark.html": ("data-mk-surface=\"mark\"", "mk-action-button"),
}

FLUTTER_SURFACES = (
    "mobile/lib/features/now/now_screen.dart",
    "mobile/lib/features/discovery/discovery_screens.dart",
    "mobile/lib/features/discovery/discovery_mature_view.dart",
    "mobile/lib/features/ongoing/ongoing_screen.dart",
    "mobile/lib/features/me/me_screen.dart",
    "mobile/lib/features/mark/mark_screen.dart",
)

LEGACY_BUTTON = re.compile(r'class="[^"]*\bmk-btn\b[^"]*"')


def inspect(root: Path = ROOT) -> list[str]:
    errors: list[str] = []

    for path, markers in WEB_SURFACES.items():
        source = (root / path).read_text(encoding="utf-8")
        for marker in markers:
            # Discovery delegates its actions to a partial. Require the exact
            # include and shared control in that partial, rather than a second
            # button or a non-functional marker in the parent template.
            in_included_action_bar = (
                path == "templates/discovery/_universal_card.html"
                and marker == "mk-action-button"
                and "{% include 'discovery/_action_bar.html' with card=card detail=False %}"
                in source
                and marker
                in (root / "templates/discovery/_action_bar.html").read_text(
                    encoding="utf-8"
                )
            )
            if marker not in source and not in_included_action_bar:
                errors.append(f"{path}: shared control marker missing: {marker}")

    for path in (
        "templates/discovery/home.html",
        "templates/discovery/_universal_card.html",
    ):
        if LEGACY_BUTTON.search((root / path).read_text(encoding="utf-8")):
            errors.append(f"{path}: legacy mk-btn skin remains in Group 1")

    for path in FLUTTER_SURFACES:
        source = (root / path).read_text(encoding="utf-8")
        if "import '../../design/action_controls.dart';" not in source:
            errors.append(f"{path}: shared action-controls import missing")
        if not any(
            marker in source
            for marker in ("MakoloActionButton(", "MakoloIconActionButton(")
        ):
            errors.append(f"{path}: screen does not consume a shared action")

    for path in ("templates/base/app.html", "templates/base/public.html"):
        source = (root / path).read_text(encoding="utf-8")
        for name in (
            "css/makolo-interactions.css",
            "js/makolo-interactions.js",
            "js/makolo-interactions-f2.js",
        ):
            if source.count(name) != 1:
                errors.append(f"{path}: expected exactly one global {name}")

    local_css = (root / "static/css/me-n1.css").read_text(encoding="utf-8")
    if re.search(r"\.mk-action-button\b|\.mk-btn(?:\b|-)", local_css):
        errors.append("static/css/me-n1.css: action styling must stay shared")

    common_css = (root / "static/css/makolo-interactions.css").read_text(
        encoding="utf-8"
    )
    for selector in (".mk-action-button", ".mk-disclosure-trigger"):
        if selector not in common_css:
            errors.append(f"static/css/makolo-interactions.css: missing {selector}")

    if not (root / "mobile/lib/design/action_controls.dart").exists():
        errors.append("mobile/lib/design/action_controls.dart: shared controls missing")

    return errors


def main() -> int:
    errors = inspect()
    if errors:
        print("Group 1 interaction contract failed:")
        for error in errors:
            print(f" - {error}")
        return 1
    print("Group 1 interaction contract passed across Web and Flutter surfaces.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
