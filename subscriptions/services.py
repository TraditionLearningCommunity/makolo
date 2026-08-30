from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .contracts import PlanVersionStatus
from .models import PlanVersion, SubscriptionPlan


class CatalogTransitionError(ValidationError):
    pass


@transaction.atomic
def publish_plan_version(plan_version, *, retire_previous=True):
    version_id = getattr(plan_version, "pk", plan_version)
    version = PlanVersion.objects.select_for_update().select_related("plan").get(pk=version_id)
    plan = SubscriptionPlan.objects.select_for_update().get(pk=version.plan_id)

    if version.status != PlanVersionStatus.DRAFT:
        raise CatalogTransitionError("Seule une PlanVersion draft peut être publiée.")
    if not plan.is_active:
        raise CatalogTransitionError("Un Plan inactif ne peut pas publier une nouvelle version.")
    plan.full_clean()

    current = None
    if plan.current_version_id:
        current = PlanVersion.objects.select_for_update().get(pk=plan.current_version_id)
        if current.plan_id != plan.pk or current.status != PlanVersionStatus.PUBLISHED:
            raise CatalogTransitionError("La version courante du Plan est incohérente.")
        expected_version = current.version + 1
    else:
        expected_version = 1
    if version.version != expected_version:
        raise CatalogTransitionError(
            f"La prochaine version publiable est v{expected_version}, pas v{version.version}."
        )

    version.full_clean()
    for benefit in version.benefits.all():
        benefit.full_clean()
    for requirement in version.requirements.all():
        requirement.full_clean()
    for entitlement in version.entitlements.select_related("feature", "plan_version__plan").prefetch_related("requirements"):
        entitlement.full_clean()
        for requirement in entitlement.requirements.all():
            requirement.full_clean()

    now = timezone.now()
    if current and retire_previous:
        current._allow_status_transition = True
        current.status = PlanVersionStatus.RETIRED
        current.retired_at = now
        current.save(update_fields=["status", "retired_at", "updated_at"])

    version._allow_status_transition = True
    version.status = PlanVersionStatus.PUBLISHED
    version.published_at = now
    version.save(update_fields=["status", "published_at", "updated_at"])

    plan._allow_current_version_change = True
    plan.current_version = version
    plan.save(update_fields=["current_version", "updated_at"])
    return version


@transaction.atomic
def retire_plan_version(plan_version):
    version_id = getattr(plan_version, "pk", plan_version)
    version = PlanVersion.objects.select_for_update().select_related("plan").get(pk=version_id)
    plan = SubscriptionPlan.objects.select_for_update().get(pk=version.plan_id)

    if version.status != PlanVersionStatus.PUBLISHED:
        raise CatalogTransitionError("Seule une PlanVersion publiée peut être retirée.")
    if plan.current_version_id == version.pk:
        raise CatalogTransitionError(
            "Publiez d'abord une version de remplacement avant de retirer la version courante."
        )

    version._allow_status_transition = True
    version.status = PlanVersionStatus.RETIRED
    version.retired_at = timezone.now()
    version.save(update_fields=["status", "retired_at", "updated_at"])
    return version
