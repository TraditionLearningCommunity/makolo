"""Additive T34B extensions for the canonical configurable Automation engine."""


def install_service_automation_contracts():
    from . import models

    models.AUTOMATION_CONDITION_KEYS = frozenset(models.AUTOMATION_CONDITION_KEYS) | {
        "severity",
        "responsibility",
        "processing_mode",
        "reason",
        "outcome",
    }
    models.AUTOMATION_RECIPIENT_FIELDS = frozenset(models.AUTOMATION_RECIPIENT_FIELDS) | {
        "assigned_profiles",
        "primary_assignee",
    }
    models.AUTOMATION_NOTIFICATION_CATEGORIES = frozenset(models.AUTOMATION_NOTIFICATION_CATEGORIES) | {
        "service",
        "opportunity",
    }
