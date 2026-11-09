#!/usr/bin/env python3
"""Static guard for the Group 3 Makolo Interaction Grammar migration.

The guard checks presentation adoption only. Domain capabilities, network
mutations, CSRF, Flutter widgets and accessibility require scenario tests too.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

WEB_CONTROLS = (
    "templates/organizations/console/access_grant.html",
    "templates/organizations/console/activity_detail.html",
    "templates/organizations/console/analytics.html",
    "templates/organizations/console/audiences.html",
    "templates/organizations/console/automation.html",
    "templates/organizations/console/capability_hub.html",
    "templates/organizations/console/control.html",
    "templates/organizations/console/crm.html",
    "templates/organizations/console/funding.html",
    "templates/organizations/console/groups.html",
    "templates/organizations/console/member_responsibilities.html",
    "templates/organizations/console/pagination.html",
    "templates/organizations/console/places.html",
    "templates/organizations/console/promotions.html",
    "templates/organizations/console/subscription_billing.html",
    "templates/organizations/console/subscription_history.html",
    "templates/organizations/console/team_form.html",
    "templates/organizations/console/team_member_form.html",
    "templates/scanner/assignment_form.html",
    "templates/scanner/assignment_list.html",
    "templates/scanner/gate_form.html",
    "templates/scanner/gate_list.html",
    "templates/scanner/live_access.html",
    "templates/organizations/space/relationships.html",
    "templates/organizations/space/us_resources.html",
    "templates/organizations/space/pilot.html",
    "templates/organizations/space/mark_ws5.html",
    "templates/organizations/space/us.html",
)
FLUTTER_CONTROLS = (
    "mobile/lib/features/space/space_shell_routes.dart",
    "mobile/lib/features/space/space_create_screen.dart",
    "mobile/lib/features/space/space_work_collection_screen.dart",
    "mobile/lib/features/space/space_work_g1_realizations.dart",
    "mobile/lib/features/continuity/dossier_workspace_screen.dart",
    "mobile/lib/features/continuity/project_workspace_screen.dart",
)
MATERIAL_ACTIONS = re.compile(
    r"\b(?:TextButton|OutlinedButton|FilledButton|ElevatedButton|IconButton)"
    r"(?:\.icon)?\s*\("
)
LEGACY_BUTTON = re.compile(r'<(?:a|button)\b[^>]*class="[^"]*\bmk-btn\b')
ACTION = re.compile(r'<(?:a|button)\b[^>]*class="[^"]*\bmk-action-button\b')


def inspect(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    for relative in WEB_CONTROLS:
        file = root / relative
        if not file.is_file():
            errors.append(f"{relative}: file missing")
            continue
        source = file.read_text(encoding="utf-8")
        if not ACTION.search(source):
            errors.append(f"{relative}: shared action absent")
        if LEGACY_BUTTON.search(source):
            errors.append(f"{relative}: legacy mk-btn control remains")
    for relative in FLUTTER_CONTROLS:
        file = root / relative
        if not file.is_file():
            errors.append(f"{relative}: file missing")
            continue
        source = file.read_text(encoding="utf-8")
        if "design/action_controls.dart" not in source:
            errors.append(f"{relative}: canonical action import missing")
        if "MakoloActionButton(" not in source:
            errors.append(f"{relative}: shared actions absent")
        if MATERIAL_ACTIONS.search(source):
            errors.append(f"{relative}: direct Material button remains")
    us_template = (root / "templates/organizations/space/us.html").read_text(
        encoding="utf-8"
    )
    us_css = (root / "static/css/space-us-n1.css").read_text(encoding="utf-8")
    if 'class="mk-interaction-tabs"' not in us_template:
        errors.append("Space Nous: view switch does not use shared tabs")
    if "mk-us-n1-layout-switch" in us_css:
        errors.append("Space Nous: duplicate local view-switch button styles")
    # The Dossier and Projet view selectors are shared tabs. Their CSS may
    # still position the tabs but must not recreate selected/button skins.
    for template, selector in (
        ("objectives/templates/objectives/dossier_detail.html", "mk-dossier__tabs"),
        ("objectives/templates/objectives/project_detail.html", "mk-project__view-switch"),
    ):
        source = (root / template).read_text(encoding="utf-8")
        if f'class="{selector} mk-interaction-tabs"' not in source:
            errors.append(f"{template}: view selector must adopt shared tabs")
    for stylesheet, old_prefix in (
        ("static/css/dossier-workspace.css", "mk-dossier"),
        ("static/css/project-workspace.css", "mk-project"),
    ):
        source = (root / stylesheet).read_text(encoding="utf-8")
        if ":not(.mk-action-button)" in source:
            errors.append(f"{stylesheet}: duplicate button skin remains")
        if f".{old_prefix}__tabs button[aria-pressed" in source or f".{old_prefix}__view-switch button[aria-pressed" in source:
            errors.append(f"{stylesheet}: duplicate selected-tab skin remains")
    for js_file, expected in (
        ("static/js/dossier-workspace.js", "button.dataset.variant"),
        ("static/js/project-workspace.js", "confirm.dataset.variant"),
    ):
        source = (root / js_file).read_text(encoding="utf-8")
        if expected not in source or "mk-action-button" not in source:
            errors.append(f"{js_file}: generated owner controls lack shared skin")
    for stylesheet in ("static/css/notifications-inbox.css",):
        source = (root / stylesheet).read_text(encoding="utf-8")
        if ".mk-notification-actions button{" in source:
            errors.append(f"{stylesheet}: local action skin overrides shared actions")
    for relative in (
        "templates/organizations/console/access_grant.html",
        "templates/organizations/console/team_form.html",
        "templates/organizations/console/team_member_form.html",
        "templates/scanner/assignment_form.html",
        "templates/scanner/gate_form.html",
        "templates/organizations/space/mark_ws5.html",
    ):
        if "{% csrf_token %}" not in (root / relative).read_text(encoding="utf-8"):
            errors.append(f"{relative}: owner POST CSRF marker absent")
    return errors


if __name__ == "__main__":
    problems = inspect()
    if problems:
        for item in problems:
            print("Group 3 Interaction Grammar:", item)
        raise SystemExit(1)
    print("Group 3 shared Web and Flutter interaction presentation markers present.")
