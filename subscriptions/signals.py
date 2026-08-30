from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models.signals import post_migrate, post_save
from django.dispatch import receiver

from organizations.models import Organization

from .catalog_defaults import ensure_default_catalog
from .runtime_services import ensure_subscription_for_profile, ensure_subscription_for_space


User = get_user_model()


@receiver(post_save, sender=User, dispatch_uid="subscriptions.bootstrap.profile")
def bootstrap_profile_subscription(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        ensure_subscription_for_profile(instance)


@receiver(post_save, sender=Organization, dispatch_uid="subscriptions.bootstrap.space")
def bootstrap_space_subscription(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        ensure_subscription_for_space(instance)


def restore_subscription_catalog_after_migrate(sender, **kwargs):
    # Django TransactionTestCase flush emits post_migrate; keep the technical
    # catalogue deterministic there as well as on normal fresh installs.
    if sender.name == "subscriptions":
        ensure_default_catalog()


post_migrate.connect(
    restore_subscription_catalog_after_migrate,
    dispatch_uid="subscriptions.restore.default.catalog",
)
