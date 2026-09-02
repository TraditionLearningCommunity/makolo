from django.core.exceptions import PermissionDenied, ValidationError

from journeys.models import Journey
from trust.models import ReportCategory
from trust.services import can_view_space_trust, create_report

from .services import can_view_contribution


def report_contribution_to_trust(*, actor, contribution, description, category=ReportCategory.CONDUCT_ISSUE):
    """Bridge contextual UGC to canonical M4 Reports without weakening M4 policy."""
    if not can_view_contribution(actor, contribution):
        raise PermissionDenied("Cette Contribution n'est pas visible dans votre contexte.")
    description = (description or "").strip()
    if not description:
        raise ValidationError({"description": "Décrivez le problème à signaler."})

    journey = None
    if contribution.activity_id:
        journeys = Journey.objects.filter(
            beneficiary=actor,
            activity=contribution.activity,
        ).order_by("-created_at")
        if contribution.occurrence_id:
            journeys = journeys.filter(occurrence=contribution.occurrence)
        journey = journeys.first()

    report_description = f"Contribution {contribution.pk}: {description}"
    if journey is not None:
        return create_report(
            actor=actor,
            journey=journey,
            category=category,
            description=report_description,
        )
    if contribution.space_id and can_view_space_trust(actor, contribution.space):
        return create_report(
            actor=actor,
            space=contribution.space,
            category=category,
            description=report_description,
        )
    raise PermissionDenied(
        "Le contrat Reports M4 exige une expérience vérifiable ou une autorité Trust sur l'Espace."
    )
