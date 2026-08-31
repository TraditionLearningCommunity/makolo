from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models.signals import post_migrate, post_save, pre_save
from django.dispatch import receiver

from organizations.models import Organization
from payments.models import PaymentObligation

from .billing_models import SubscriptionBillingObligation
from .billing_services import ensure_transition_billing_obligation, transition_billing_is_settled
from .catalog_defaults import ensure_default_catalog
from .contracts import SubscriptionTransitionKind, SubscriptionTransitionStatus
from .runtime_services import ensure_subscription_for_profile, ensure_subscription_for_space
from .transition_models import SubscriptionTransition


User = get_user_model()


@receiver(post_save, sender=User, dispatch_uid="subscriptions.bootstrap.profile")
def bootstrap_profile_subscription(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        ensure_subscription_for_profile(instance)


@receiver(post_save, sender=Organization, dispatch_uid="subscriptions.bootstrap.space")
def bootstrap_space_subscription(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        ensure_subscription_for_space(instance)


@receiver(post_save, sender=SubscriptionTransition, dispatch_uid="subscriptions.f2.ensure_transition_billing")
def ensure_transition_billing(sender, instance, raw=False, **kwargs):
    if raw or instance.kind == SubscriptionTransitionKind.ADDON_REMOVE:
        return
    if instance.status != SubscriptionTransitionStatus.IN_PROGRESS:
        return
    ensure_transition_billing_obligation(transition=instance, actor=instance.requested_by)


@receiver(pre_save, sender=SubscriptionTransition, dispatch_uid="subscriptions.f2.billing_readiness_guard")
def guard_paid_transition_readiness(sender, instance, raw=False, **kwargs):
    if raw or instance.status != SubscriptionTransitionStatus.READY or not instance.pk:
        return
    if SubscriptionBillingObligation.objects.filter(transition_id=instance.pk).exists() and not transition_billing_is_settled(instance):
        instance.status = SubscriptionTransitionStatus.IN_PROGRESS
        instance.ready_at = None


@receiver(post_save, sender=PaymentObligation, dispatch_uid="subscriptions.f2.payment_obligation_sync")
def sync_subscription_payment_obligation(sender, instance, raw=False, **kwargs):
    if raw:
        return
    if SubscriptionBillingObligation.objects.filter(obligation_id=instance.pk).exists():
        from .billing_services import sync_subscription_billing_obligation

        sync_subscription_billing_obligation(obligation=instance)
    if instance.subscription_transition_links.exists():
        from .transition_services import sync_transition_payment_assessment

        sync_transition_payment_assessment(obligation=instance)


def restore_subscription_catalog_after_migrate(sender, **kwargs):
    # Django TransactionTestCase flush emits post_migrate; keep the technical
    # catalogue deterministic there as well as on normal fresh installs.
    if sender.name == "subscriptions":
        ensure_default_catalog()


post_migrate.connect(
    restore_subscription_catalog_after_migrate,
    dispatch_uid="subscriptions.restore.default.catalog",
)
