from django import template

from trust.models import Feedback, Proof, Report
from trust.services import can_submit_feedback


register = template.Library()


@register.inclusion_tag("trust/_journey_actions.html", takes_context=True)
def trust_journey_actions(context, journey):
    request = context.get("request")
    actor = getattr(request, "user", None)
    is_owner = bool(actor and actor.is_authenticated and journey.beneficiary_id == actor.pk)
    feedback = None
    reports = Report.objects.none()
    proofs = Proof.objects.none()
    if is_owner:
        feedback = Feedback.objects.filter(journey=journey, author=actor).first()
        reports = Report.objects.filter(journey=journey, reporter=actor).order_by("-created_at")[:3]
        proofs = Proof.objects.filter(journey=journey, subject_profile=actor).order_by("-issued_at")
    return {
        "journey": journey,
        "can_submit_feedback": is_owner and feedback is None and can_submit_feedback(journey=journey, actor=actor),
        "feedback": feedback,
        "reports": reports,
        "proofs": proofs,
        "is_owner": is_owner,
    }
