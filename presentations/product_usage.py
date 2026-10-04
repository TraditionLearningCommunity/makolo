from journeys.models import WorkflowKind

from core.product_language import vocabulary_for

from .enums import PresentationPurpose


ACTIVITY_OUTPUT_PURPOSES = {
    PresentationPurpose.INVITATION,
    PresentationPurpose.PROGRAM,
}


def access_presentation_purpose(access):
    """Resolve the MPS purpose from canonical Access context."""
    workflow = getattr(getattr(access, "journey", None), "workflow", None)
    if workflow == WorkflowKind.INVITATION:
        return PresentationPurpose.INVITATION

    vocabulary = vocabulary_for(activity=access.activity, workflow=workflow)
    if workflow == WorkflowKind.REGISTRATION or vocabulary.vertical in {"service", "funding"}:
        return PresentationPurpose.CONFIRMATION
    return PresentationPurpose.ACCESS_PASS
