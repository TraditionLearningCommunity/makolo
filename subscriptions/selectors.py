from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from organizations.models import Organization

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


def get_subscription_for_subject(subject):
    from .runtime_models import Subscription

    User = get_user_model()
    if isinstance(subject, User):
        return Subscription.objects.select_related("profile").filter(profile=subject).first()
    if isinstance(subject, Organization):
        return Subscription.objects.select_related("space").filter(space=subject).first()
    raise ValidationError("Le sujet doit être un Profile ou un Space canonique.")


def resolve_activity_entitlement_subject(activity):
    if activity.space_id and not activity.owner_profile_id:
        return activity.space
    if activity.owner_profile_id and not activity.space_id:
        return activity.owner_profile
    raise ValidationError("L'Activity n'a pas un propriétaire logique Profile XOR Space valide.")


def resolve_activity_subscription(activity):
    subject = resolve_activity_entitlement_subject(activity)
    subscription = get_subscription_for_subject(subject)
    if subscription is None:
        raise ValidationError("Le propriétaire logique de l'Activity n'a pas de Subscription canonique.")
    return subscription
