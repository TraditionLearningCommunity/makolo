from __future__ import annotations

from functools import wraps

from django.core.exceptions import PermissionDenied

from authorization.constants import PermissionCode
from authorization.services import can


OPPORTUNITY_PERMISSIONS = {
    PermissionCode.OPPORTUNITIES_MANAGE,
    PermissionCode.OPPORTUNITIES_REVIEW_SUBMISSIONS,
    PermissionCode.OPPORTUNITIES_SOURCES_VERIFY,
    PermissionCode.OPPORTUNITIES_MERGE,
}


def _require(actor, permission_code):
    if not getattr(actor, "is_authenticated", False) or not can(actor, permission_code):
        raise PermissionDenied("Permission Opportunity insuffisante.")


def install_opportunity_authorization_policy():
    from . import services

    if getattr(services, "_t34b_opportunity_policy_installed", False):
        return

    def ensure_curator(actor):
        if not getattr(actor, "is_authenticated", False):
            raise PermissionDenied("Authentification requise pour la curation Opportunity.")
        if not any(can(actor, code) for code in OPPORTUNITY_PERMISSIONS):
            raise PermissionDenied("Une permission Opportunity plateforme est requise.")

    services._ensure_curator = ensure_curator

    def wrap(name, permission_code, *, actor_key="actor", allow_none=False):
        original = getattr(services, name)

        @wraps(original)
        def guarded(*args, **kwargs):
            actor = kwargs.get(actor_key)
            if actor is not None or not allow_none:
                _require(actor, permission_code)
            return original(*args, **kwargs)

        setattr(services, name, guarded)

    for name in (
        "create_opportunity",
        "create_opportunity_revision",
        "add_opportunity_zone",
        "add_requirement",
        "create_opportunity_source",
        "publish_opportunity_revision",
        "withdraw_opportunity",
        "archive_opportunity",
    ):
        wrap(name, PermissionCode.OPPORTUNITIES_MANAGE)

    wrap(
        "record_source_check",
        PermissionCode.OPPORTUNITIES_SOURCES_VERIFY,
        actor_key="checked_by",
        allow_none=True,
    )
    for name in ("start_submission_review", "decide_opportunity_submission"):
        wrap(name, PermissionCode.OPPORTUNITIES_REVIEW_SUBMISSIONS)
    wrap("merge_opportunities", PermissionCode.OPPORTUNITIES_MERGE)

    services._t34b_opportunity_policy_installed = True
