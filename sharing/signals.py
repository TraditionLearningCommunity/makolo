from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from organizations.models import Organization

from .models import PublicIdentifier, PublicSubjectKind

User = get_user_model()


def _assert_identifier_available(identifier, *, profile_id=None, space_id=None):
    qs = PublicIdentifier.objects.filter(identifier__iexact=(identifier or "").strip().lower())
    if profile_id:
        qs = qs.exclude(profile_id=profile_id)
    if space_id:
        qs = qs.exclude(space_id=space_id)
    if qs.exists():
        raise ValidationError({"identifier": "Cet identifiant public Makolo est déjà utilisé."})


@receiver(pre_save, sender=User)
def protect_profile_public_identifier(sender, instance, **kwargs):
    if instance.username:
        _assert_identifier_available(instance.username, profile_id=instance.pk)


@receiver(post_save, sender=User)
def sync_profile_public_identifier(sender, instance, **kwargs):
    if not instance.username:
        return
    PublicIdentifier.objects.update_or_create(
        profile=instance,
        defaults={
            "identifier": instance.username,
            "subject_kind": PublicSubjectKind.PROFILE,
            "space": None,
        },
    )


@receiver(pre_save, sender=Organization)
def protect_space_public_identifier(sender, instance, **kwargs):
    if instance.slug:
        _assert_identifier_available(instance.slug, space_id=instance.pk)


@receiver(post_save, sender=Organization)
def sync_space_public_identifier(sender, instance, **kwargs):
    if not instance.slug:
        return
    PublicIdentifier.objects.update_or_create(
        space=instance,
        defaults={
            "identifier": instance.slug,
            "subject_kind": PublicSubjectKind.SPACE,
            "profile": None,
        },
    )
