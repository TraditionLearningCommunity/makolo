"""Consent-based links to canonical Spaces and Groups, not copied memberships."""
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from .core_models import Conversation


class ConversationCollectiveStatus(models.TextChoices):
    PENDING = "pending", "En attente"
    ACTIVE = "active", "Acceptée"
    DECLINED = "declined", "Refusée"
    REVOKED = "revoked", "Retirée"
    EXPIRED = "expired", "Expirée"


class ConversationCollectiveAccess(models.Model):
    """Link a consenting collective; active members remain derived at read time.

    Neither a GroupMembership nor a TeamMembership is mirrored here.
    The accepting manager gains no new Mandate through this link.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="collective_accesses",
    )
    space = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT,
        null=True, blank=True, related_name="conversation_accesses",
    )
    group = models.ForeignKey(
        "groups.Group", on_delete=models.PROTECT,
        null=True, blank=True, related_name="conversation_accesses",
    )
    status = models.CharField(
        max_length=16, choices=ConversationCollectiveStatus.choices,
        default=ConversationCollectiveStatus.PENDING,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="created_conversation_collective_links",
    )
    responded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="decided_conversation_collective_links",
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(space__isnull=False, group__isnull=True)
                    | Q(space__isnull=True, group__isnull=False)
                ),
                name="conv_collective_exactly_one_target",
            ),
            models.UniqueConstraint(
                fields=["conversation", "space"],
                condition=Q(space__isnull=False),
                name="conv_collective_unique_space",
            ),
            models.UniqueConstraint(
                fields=["conversation", "group"],
                condition=Q(group__isnull=False),
                name="conv_collective_unique_group",
            ),
        ]
        indexes = [
            models.Index(
                fields=["conversation", "status"],
                name="conv_collective_conv_status_idx",
            ),
        ]

    def clean(self):
        super().clean()
        if bool(self.space_id) == bool(self.group_id):
            raise ValidationError(
                "Un lien collectif vise un Espace ou un Groupe, jamais les deux."
            )
        if self.status == ConversationCollectiveStatus.ACTIVE and not self.responded_by_id:
            raise ValidationError("Un collectif doit accepter avant de participer.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
