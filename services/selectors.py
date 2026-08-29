from .models import ServiceOutcomeEvent, ServiceSubmission


def submissions_for_context(context):
    return (
        ServiceSubmission.objects.filter(context=context)
        .select_related("context", "context__journey", "receipt_artifact", "submitted_by")
        .order_by("attempt", "created_at", "id")
    )


def latest_submission(context):
    return submissions_for_context(context).order_by("-attempt", "-created_at", "-id").first()


def outcome_timeline(context):
    return (
        ServiceOutcomeEvent.objects.filter(context=context)
        .select_related("context", "recorded_by")
        .order_by("occurred_at", "created_at", "id")
    )


def current_outcome(context):
    return context.current_outcome
