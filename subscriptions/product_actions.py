from django.shortcuts import get_object_or_404

from .contracts import (
    AcquisitionMode,
    CatalogVisibility,
    PlanVersionStatus,
    SubscriptionItemStatus,
    SubscriptionPlanType,
    SubscriptionTransitionKind,
)
from .models import PlanVersion
from .runtime_models import SubscriptionItem


def get_self_service_target(subscription, plan_version_id):
    """Resolve only an acquirable, public target for this exact Subscription subject type."""
    return get_object_or_404(
        PlanVersion.objects.select_related("plan"),
        pk=plan_version_id,
        status=PlanVersionStatus.PUBLISHED,
        catalog_visibility=CatalogVisibility.PUBLIC,
        acquisition_mode=AcquisitionMode.SELF_SERVICE,
        plan__is_active=True,
        plan__subject_type=subscription.subject_type,
    )


def transition_kind_for_target(target):
    return (
        SubscriptionTransitionKind.BASE_SWITCH
        if target.plan.plan_type == SubscriptionPlanType.BASE
        else SubscriptionTransitionKind.ADDON_ADD
    )


def get_active_addon(subscription, item_id):
    return get_object_or_404(
        SubscriptionItem.objects.select_related("plan", "plan_version"),
        pk=item_id,
        subscription=subscription,
        status=SubscriptionItemStatus.ACTIVE,
        item_type=SubscriptionPlanType.ADDON,
    )
