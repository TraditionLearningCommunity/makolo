from django.contrib.auth import get_user_model
from django.db.models.signals import pre_save
from django.dispatch import receiver

from access.models import Access
from payments.models import Payment

from .emergency_controls import require_operational_control
from .models import OperationalControlCode


User = get_user_model()


def _is_new(instance) -> bool:
    return bool(getattr(getattr(instance, "_state", None), "adding", False))


@receiver(pre_save, sender=User, dispatch_uid="operations.guard_user_signups")
def guard_user_creation(sender, instance, raw=False, **kwargs):
    if raw or not _is_new(instance):
        return
    # Emergency signup suspension must not prevent platform recovery accounts.
    if getattr(instance, "is_staff", False) or getattr(instance, "is_superuser", False):
        return
    require_operational_control(OperationalControlCode.USER_SIGNUPS)


@receiver(pre_save, sender=Access, dispatch_uid="operations.guard_access_issuance")
def guard_access_creation(sender, instance, raw=False, **kwargs):
    if raw or not _is_new(instance):
        return
    require_operational_control(OperationalControlCode.ACCESS_ISSUANCE)


@receiver(pre_save, sender=Payment, dispatch_uid="operations.guard_payment_creation")
def guard_payment_creation(sender, instance, raw=False, **kwargs):
    if raw or not _is_new(instance):
        return
    require_operational_control(OperationalControlCode.PAYMENT_CREATION)
