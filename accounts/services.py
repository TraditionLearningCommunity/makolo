import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from accounts.models import (
    NotificationPreference,
    UserActivity,
    UserDevice,
    UserProfile,
    UserSession,
    VerificationDocument,
)


logger = logging.getLogger("makolo")
User = get_user_model()
DELETED_DISPLAY_NAME = "Compte supprimé"


def blacklist_user_refresh_tokens(user) -> int:
    count = 0
    for token in OutstandingToken.objects.filter(user=user):
        _, created = BlacklistedToken.objects.get_or_create(token=token)
        if created:
            count += 1
    return count


def request_password_reset(*, email: str) -> None:
    """Send a secure reset link without exposing account existence."""
    normalized_email = (email or "").strip().lower()
    user = User.objects.filter(email__iexact=normalized_email, is_active=True).first()
    if not user:
        return

    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    reset_path = reverse(
        "account:password-reset-confirm",
        kwargs={"uid": uid, "token": token},
    )
    reset_url = f"{settings.MAKOLO_PUBLIC_BASE_URL}{reset_path}"
    body = (
        "Une demande de réinitialisation du mot de passe Makolo a été reçue.\n\n"
        "Ouvrez ce lien pour choisir un nouveau mot de passe :\n"
        f"{reset_url}\n\n"
        "Ce lien expire automatiquement. Si vous n’êtes pas à l’origine de cette demande, ignorez cet e-mail."
    )
    try:
        mail.send_mail(
            subject="Makolo — Réinitialisation du mot de passe",
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
    except Exception:
        # Keep the public response enumeration-safe and avoid logging the reset URL/token.
        logger.error("Password reset email delivery failed user_id=%s", user.pk)


def _resolve_password_reset_user(*, uid: str, token: str):
    try:
        user_id = force_str(urlsafe_base64_decode(uid))
        user = User.objects.get(pk=user_id, is_active=True)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist) as exc:
        raise ValidationError({"token": "Le lien de réinitialisation est invalide ou expiré."}) from exc
    if not default_token_generator.check_token(user, token):
        raise ValidationError({"token": "Le lien de réinitialisation est invalide ou expiré."})
    return user


@transaction.atomic
def reset_password(*, uid: str, token: str, new_password: str):
    user = _resolve_password_reset_user(uid=uid, token=token)
    validate_password(new_password, user=user)
    user.set_password(new_password)
    user.save(update_fields=["password", "updated_at"])
    blacklist_user_refresh_tokens(user)
    return user


@transaction.atomic
def change_password(*, user, current_password: str, new_password: str):
    locked = User.objects.select_for_update().get(pk=user.pk)
    if not locked.check_password(current_password):
        raise ValidationError({"current_password": "Le mot de passe actuel est incorrect."})
    validate_password(new_password, user=locked)
    locked.set_password(new_password)
    locked.save(update_fields=["password", "updated_at"])
    blacklist_user_refresh_tokens(locked)
    return locked


def get_account_deletion_blockers(user):
    """Return organizations for which user is the last active owner."""
    from organizations.models import OrganizationMembership, OrganizationRole

    blockers = []
    owner_memberships = OrganizationMembership.objects.filter(
        user=user,
        role=OrganizationRole.OWNER,
        is_active=True,
    ).select_related("organization")
    for membership in owner_memberships:
        has_other_owner = OrganizationMembership.objects.filter(
            organization=membership.organization,
            role=OrganizationRole.OWNER,
            is_active=True,
        ).exclude(pk=membership.pk).exists()
        if not has_other_owner:
            blockers.append(membership.organization)
    return blockers


def _schedule_file_deletions(names):
    unique_names = [name for name in dict.fromkeys(names) if name]
    if not unique_names:
        return

    def delete_files():
        for name in unique_names:
            try:
                default_storage.delete(name)
            except Exception:
                # Account state/anonymization must not be rolled back merely
                # because a storage backend is temporarily unavailable.
                pass

    transaction.on_commit(delete_files)


@transaction.atomic
def delete_account(*, user, current_password: str):
    """Deactivate and anonymize one account while preserving audit history.

    Financial/ticket/scanner records are retained. Direct personal identifiers
    owned by the account are removed or replaced with non-reversible placeholders.
    Foreign keys that form part of audit history keep pointing at the now
    anonymized, inactive user row. Deletion is blocked while the user is the
    last active owner of an organization so no workspace is orphaned silently.
    """
    from crm.models import CRMContact, MarketingConsent
    from notifications.models import Notification
    from organizations.models import OrganizationFollow, OrganizationMembership
    from partners.models import Partner
    from payments.models import Payment, Refund
    from promotions.models import PromotionRedemption
    from tickets.models import Ticket, TicketOrder, TicketTransfer, TicketWaitlistEntry

    locked = User.objects.select_for_update().get(pk=user.pk)
    if not locked.check_password(current_password):
        raise ValidationError({"password": "Le mot de passe est incorrect."})
    if not locked.is_active:
        return {"status": "deleted"}

    blockers = get_account_deletion_blockers(locked)
    if blockers:
        names = ", ".join(organization.name for organization in blockers[:5])
        if len(blockers) > 5:
            names += "…"
        raise ValidationError(
            {
                "account": (
                    "Transférez d’abord la propriété des organisations dont vous êtes le dernier propriétaire actif : "
                    f"{names}."
                )
            }
        )

    suffix = locked.pk.hex
    anonymized_email = f"deleted+{suffix}@deleted.invalid"
    anonymized_username = f"deleted-{suffix}"
    file_names = []
    if locked.avatar:
        file_names.append(locked.avatar.name)

    order_ids = list(
        TicketOrder.objects.filter(buyer=locked).values_list("pk", flat=True)
    )

    # Historical commercial records keep amounts, currencies and references,
    # while participant snapshots are anonymized.
    TicketOrder.objects.filter(pk__in=order_ids).update(
        buyer=None,
        customer_name=DELETED_DISPLAY_NAME,
        customer_email=anonymized_email,
    )
    Ticket.objects.filter(owner=locked).update(
        owner=None,
        holder_name=DELETED_DISPLAY_NAME,
        holder_email=anonymized_email,
    )
    Payment.objects.filter(order_id__in=order_ids).update(
        payer_name=DELETED_DISPLAY_NAME,
        payer_email=anonymized_email,
        payer_phone="",
    )
    Payment.objects.filter(initiated_by=locked).update(initiated_by=None)
    Refund.objects.filter(requested_by=locked).update(requested_by=None)
    PromotionRedemption.objects.filter(buyer=locked).update(
        buyer=None,
        customer_email=anonymized_email,
    )
    TicketTransfer.objects.filter(recipient=locked).update(
        recipient_email=anonymized_email
    )
    TicketWaitlistEntry.objects.filter(user=locked).delete()

    # Marketing/CRM identity is organizer-scoped: unlink and anonymize each
    # contact without altering historic campaign/order attribution.
    for contact in CRMContact.objects.select_for_update().filter(user=locked):
        contact.user = None
        contact.email = f"deleted+{contact.pk.hex}@deleted.invalid"
        contact.name = DELETED_DISPLAY_NAME
        contact.phone = ""
        contact.marketing_consent = MarketingConsent.UNSUBSCRIBED
        contact.consent_source = "account_deletion"
        contact.consent_updated_at = timezone.now()
        contact.metadata = {}
        contact.save(
            update_fields=[
                "user",
                "email",
                "name",
                "phone",
                "marketing_consent",
                "consent_source",
                "consent_updated_at",
                "metadata",
                "updated_at",
            ]
        )

    OrganizationFollow.objects.filter(user=locked).delete()
    OrganizationMembership.objects.filter(user=locked).update(is_active=False)
    Partner.objects.filter(user=locked).update(user=None)
    Partner.objects.filter(created_by=locked).update(created_by=None)
    Notification.objects.filter(recipient=locked).delete()
    NotificationPreference.objects.filter(user=locked).delete()

    UserDevice.objects.filter(user=locked).delete()
    UserSession.objects.filter(user=locked).update(active=False, ended_at=timezone.now())
    UserActivity.objects.filter(user=locked).update(
        ip_address=None,
        user_agent="",
        metadata={},
    )
    for document in VerificationDocument.objects.filter(user=locked):
        if document.file:
            file_names.append(document.file.name)
    VerificationDocument.objects.filter(user=locked).delete()

    UserProfile.objects.filter(user=locked).update(
        company_name=None,
        organization_name=None,
        profession=None,
        country=None,
        city=None,
        address=None,
        latitude=None,
        longitude=None,
        public_profile=False,
        searchable=False,
        profile_completed=False,
    )

    locked.roles.clear()
    locked.permission_groups.clear()
    blacklist_user_refresh_tokens(locked)
    locked.set_unusable_password()
    locked.email = anonymized_email
    locked.username = anonymized_username
    locked.first_name = ""
    locked.last_name = ""
    locked.phone = None
    locked.birth_date = None
    locked.gender = None
    locked.bio = None
    locked.avatar = None
    locked.website = None
    locked.linkedin_url = None
    locked.facebook_url = None
    locked.instagram_url = None
    locked.x_url = None
    locked.metadata = {}
    locked.preferences = {}
    locked.settings_data = {}
    locked.analytics_data = {}
    locked.is_active = False
    locked.is_staff = False
    locked.is_superuser = False
    locked.is_organizer = False
    locked.is_scanner_agent = False
    locked.require_2fa = False
    locked.failed_login_attempts = 0
    locked.account_locked_until = None
    locked.save()

    _schedule_file_deletions(file_names)
    return {"status": "deleted"}
