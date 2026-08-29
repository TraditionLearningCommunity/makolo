from django.core.exceptions import ValidationError

from .contracts import PlanVersionStatus, SubscriptionPlanType, SubscriptionSubjectType
from .models import SubscriptionPlan


def get_current_default_base_plan(subject_type):
    if subject_type not in SubscriptionSubjectType.values:
        raise ValidationError({"subject_type": "Type de sujet Subscription inconnu."})
    return (
        SubscriptionPlan.objects.select_related("current_version")
        .filter(
            subject_type=subject_type,
            plan_type=SubscriptionPlanType.BASE,
            is_default=True,
            is_active=True,
            current_version__status=PlanVersionStatus.PUBLISHED,
        )
        .first()
    )
