"""Test-only helpers for consumers of the canonical Payments contracts.

This module deliberately keeps Service/Journey fixture construction outside
consumer domains such as subscriptions. Runtime consumer code must never use
this helper.
"""

from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role
from services.models import ServiceKind
from services.services import create_service_details, create_service_journey


def make_payment_obligation_journey(*, manager, beneficiary=None, title="Payment obligation fixture"):
    beneficiary = beneficiary or manager
    activity = Activity.objects.create(owner_profile=manager, created_by=manager, title=title)
    grant_activity_role(
        profile=manager,
        activity=activity,
        role_code=SystemRoleCode.ACTIVITY_SERVICE_MANAGER,
    )
    service = create_service_details(
        activity=activity,
        actor=manager,
        service_kind=ServiceKind.APPLICATION_SUPPORT,
    )
    return create_service_journey(
        service=service,
        initiated_by=beneficiary,
        beneficiary=beneficiary,
    )
