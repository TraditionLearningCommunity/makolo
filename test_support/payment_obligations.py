"""Cross-domain payment fixtures used only by integration tests."""

from django.core.files.uploadedfile import SimpleUploadedFile

from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role
from journeys.collaboration_models import JourneyArtifactKind, JourneyAssignmentResponsibility
from journeys.collaboration_services import assign_journey, create_artifact
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
    journey = create_service_journey(
        service=service,
        initiated_by=beneficiary,
        beneficiary=beneficiary,
    )
    assign_journey(
        journey=journey,
        profile=manager,
        responsibility=JourneyAssignmentResponsibility.LEAD,
        is_primary=True,
        assigned_by=manager,
    )
    return journey


def make_payment_receipt_artifact(*, journey, uploaded_by, marker=b"receipt"):
    upload = SimpleUploadedFile(
        "receipt.pdf",
        b"%PDF-1.4\n" + marker + b"\n%%EOF",
        content_type="application/pdf",
    )
    return create_artifact(
        journey=journey,
        uploaded_file=upload,
        uploaded_by=uploaded_by,
        kind=JourneyArtifactKind.PAYMENT_RECEIPT,
        title="Payment receipt fixture",
    )
