import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


class ConversationLifecycle(models.TextChoices):
    DRAFT = "draft", "Brouillon"
    OPEN = "open", "Ouverte"
    CLOSED = "closed", "Fermée"
    ARCHIVED = "archived", "Archivée"


class ConversationModePreset(models.TextChoices):
    ANNOUNCEMENTS = "announcements", "Annonces"
    GUIDED = "guided", "Guidée"
    MIXED = "mixed", "Mixte"
    FREE = "free", "Discussion libre"


class ConversationEntryMode(models.TextChoices):
    DERIVED = "derived", "Accès dérivé"
    JOIN = "join", "Rejoindre"
    REQUEST = "request", "Demander à rejoindre"
    INVITE_ONLY = "invite_only", "Sur invitation"
    DIRECT_CONSENT = "direct_consent", "Consentement direct"


class ConversationDiscoverability(models.TextChoices):
    HIDDEN = "hidden", "Masquée"
    ELIGIBLE = "eligible", "Visible aux personnes éligibles"


class ConversationHistoryPolicy(models.TextChoices):
    CONTEXT_HISTORY = "context_history", "Historique du contexte"
    FROM_JOIN = "from_join", "Depuis l’entrée"


class ConversationContextKind(models.TextChoices):
    SPACE = "space", "Espace"
    GROUP = "group", "Groupe"
    ACTIVITY = "activity", "Activité"
    OCCURRENCE = "occurrence", "Occurrence"
    DOSSIER = "dossier", "Dossier"
    PROJECT = "project", "Projet"
    JOURNEY = "journey", "Démarche"
    ACTION_PROPOSAL = "action_proposal", "Proposition"
    DIRECT = "direct", "Directe"


class ConversationParticipationStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    LEFT = "left", "Quittée"
    REMOVED = "removed", "Retirée"


class ConversationParticipationSource(models.TextChoices):
    MANUAL = "manual", "Ajout explicite"
    JOIN = "join", "Rejoint"
    REQUEST = "request", "Demande approuvée"
    INVITATION = "invitation", "Invitation acceptée"
    DIRECT_CONSENT = "direct_consent", "Consentement direct"


class ConversationInvitationStatus(models.TextChoices):
    PENDING = "pending", "En attente"
    ACCEPTED = "accepted", "Acceptée"
    DECLINED = "declined", "Refusée"
    EXPIRED = "expired", "Expirée"
    CANCELLED = "cancelled", "Annulée"


class ConversationJoinRequestStatus(models.TextChoices):
    PENDING = "pending", "En attente"
    APPROVED = "approved", "Approuvée"
    REJECTED = "rejected", "Refusée"
    CANCELLED = "cancelled", "Annulée"


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title_override = models.CharField(max_length=220, blank=True)
    purpose = models.CharField(max_length=500, blank=True)
    lifecycle = models.CharField(
        max_length=16,
        choices=ConversationLifecycle.choices,
        default=ConversationLifecycle.DRAFT,
    )
    mode_preset = models.CharField(
        max_length=24,
        choices=ConversationModePreset.choices,
        default=ConversationModePreset.MIXED,
    )
    entry_mode = models.CharField(
        max_length=24,
        choices=ConversationEntryMode.choices,
        default=ConversationEntryMode.DERIVED,
    )
    discoverability = models.CharField(
        max_length=16,
        choices=ConversationDiscoverability.choices,
        default=ConversationDiscoverability.HIDDEN,
    )
    history_policy = models.CharField(
        max_length=24,
        choices=ConversationHistoryPolicy.choices,
        default=ConversationHistoryPolicy.CONTEXT_HISTORY,
    )
    client_reference = models.CharField(max_length=80, null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_action_conversations",
    )
    opened_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["client_reference"],
                condition=Q(client_reference__isnull=False),
                name="conv_client_ref_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["lifecycle", "updated_at"], name="conv_lifecycle_updated_idx"),
            models.Index(fields=["created_by", "created_at"], name="conv_created_by_idx"),
        ]

    def clean(self):
        super().clean()
        self.title_override = (self.title_override or "").strip()
        self.purpose = (self.purpose or "").strip()
        self.client_reference = (self.client_reference or "").strip() or None
        errors = {}
        if self.lifecycle == ConversationLifecycle.DRAFT:
            if self.closed_at or self.archived_at:
                errors["lifecycle"] = "Une Conversation brouillon ne peut pas être fermée ou archivée."
        elif self.lifecycle == ConversationLifecycle.OPEN:
            if not self.opened_at:
                errors["opened_at"] = "Une Conversation ouverte conserve sa date d’ouverture."
            if self.closed_at or self.archived_at:
                errors["lifecycle"] = "Une Conversation ouverte ne peut pas avoir de date de fermeture ou d’archivage."
        elif self.lifecycle == ConversationLifecycle.CLOSED:
            if not self.opened_at or not self.closed_at:
                errors["lifecycle"] = "Une Conversation fermée conserve ses dates d’ouverture et de fermeture."
            if self.archived_at:
                errors["archived_at"] = "Une Conversation fermée n’est pas encore archivée."
        elif self.lifecycle == ConversationLifecycle.ARCHIVED and not self.archived_at:
            errors["archived_at"] = "Une Conversation archivée conserve sa date d’archivage."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.pk and not self._state.adding and not getattr(self, "_allow_lifecycle_transition", False):
            previous = Conversation.objects.filter(pk=self.pk).values_list("lifecycle", flat=True).first()
            if previous is not None and previous != self.lifecycle:
                raise ValidationError({"lifecycle": "Utilisez le service Conversation pour changer cet état."})
        result = super().save(*args, **kwargs)
        self._allow_lifecycle_transition = False
        return result

    def __str__(self):
        return self.title_override or f"Conversation {self.pk}"


class ConversationContext(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.OneToOneField(
        Conversation,
        on_delete=models.CASCADE,
        related_name="context",
    )
    kind = models.CharField(max_length=24, choices=ConversationContextKind.choices)
    space = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="action_conversation_contexts",
        null=True,
        blank=True,
    )
    group = models.ForeignKey(
        "groups.Group",
        on_delete=models.PROTECT,
        related_name="action_conversation_contexts",
        null=True,
        blank=True,
    )
    activity = models.ForeignKey(
        "activities.Activity",
        on_delete=models.PROTECT,
        related_name="action_conversation_contexts",
        null=True,
        blank=True,
    )
    occurrence = models.ForeignKey(
        "activities.Occurrence",
        on_delete=models.PROTECT,
        related_name="action_conversation_contexts",
        null=True,
        blank=True,
    )
    dossier = models.ForeignKey(
        "objectives.Dossier",
        on_delete=models.PROTECT,
        related_name="action_conversation_contexts",
        null=True,
        blank=True,
    )
    project = models.ForeignKey(
        "objectives.Project",
        on_delete=models.PROTECT,
        related_name="action_conversation_contexts",
        null=True,
        blank=True,
    )
    journey = models.ForeignKey(
        "journeys.Journey",
        on_delete=models.PROTECT,
        related_name="action_conversation_contexts",
        null=True,
        blank=True,
    )
    action_proposal = models.ForeignKey(
        "social.ActionProposal",
        on_delete=models.PROTECT,
        related_name="action_conversation_contexts",
        null=True,
        blank=True,
    )
    direct_profile_a = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="direct_conversation_contexts_a",
        null=True,
        blank=True,
    )
    direct_profile_b = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="direct_conversation_contexts_b",
        null=True,
        blank=True,
    )
    purpose_key = models.SlugField(max_length=80, default="coordination")
    separation_reason = models.CharField(max_length=220, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(kind=ConversationContextKind.SPACE, space__isnull=False, group__isnull=True, activity__isnull=True, occurrence__isnull=True, dossier__isnull=True, project__isnull=True, journey__isnull=True, action_proposal__isnull=True, direct_profile_a__isnull=True, direct_profile_b__isnull=True)
                    | Q(kind=ConversationContextKind.GROUP, space__isnull=True, group__isnull=False, activity__isnull=True, occurrence__isnull=True, dossier__isnull=True, project__isnull=True, journey__isnull=True, action_proposal__isnull=True, direct_profile_a__isnull=True, direct_profile_b__isnull=True)
                    | Q(kind=ConversationContextKind.ACTIVITY, space__isnull=True, group__isnull=True, activity__isnull=False, occurrence__isnull=True, dossier__isnull=True, project__isnull=True, journey__isnull=True, action_proposal__isnull=True, direct_profile_a__isnull=True, direct_profile_b__isnull=True)
                    | Q(kind=ConversationContextKind.OCCURRENCE, space__isnull=True, group__isnull=True, activity__isnull=True, occurrence__isnull=False, dossier__isnull=True, project__isnull=True, journey__isnull=True, action_proposal__isnull=True, direct_profile_a__isnull=True, direct_profile_b__isnull=True)
                    | Q(kind=ConversationContextKind.DOSSIER, space__isnull=True, group__isnull=True, activity__isnull=True, occurrence__isnull=True, dossier__isnull=False, project__isnull=True, journey__isnull=True, action_proposal__isnull=True, direct_profile_a__isnull=True, direct_profile_b__isnull=True)
                    | Q(kind=ConversationContextKind.PROJECT, space__isnull=True, group__isnull=True, activity__isnull=True, occurrence__isnull=True, dossier__isnull=True, project__isnull=False, journey__isnull=True, action_proposal__isnull=True, direct_profile_a__isnull=True, direct_profile_b__isnull=True)
                    | Q(kind=ConversationContextKind.JOURNEY, space__isnull=True, group__isnull=True, activity__isnull=True, occurrence__isnull=True, dossier__isnull=True, project__isnull=True, journey__isnull=False, action_proposal__isnull=True, direct_profile_a__isnull=True, direct_profile_b__isnull=True)
                    | Q(kind=ConversationContextKind.ACTION_PROPOSAL, space__isnull=True, group__isnull=True, activity__isnull=True, occurrence__isnull=True, dossier__isnull=True, project__isnull=True, journey__isnull=True, action_proposal__isnull=False, direct_profile_a__isnull=True, direct_profile_b__isnull=True)
                    | Q(kind=ConversationContextKind.DIRECT, space__isnull=True, group__isnull=True, activity__isnull=True, occurrence__isnull=True, dossier__isnull=True, project__isnull=True, journey__isnull=True, action_proposal__isnull=True, direct_profile_a__isnull=False, direct_profile_b__isnull=False)
                ),
                name="conv_context_shape_valid",
            ),
            models.UniqueConstraint(fields=["space", "purpose_key"], condition=Q(kind=ConversationContextKind.SPACE), name="conv_ctx_space_purpose_unique"),
            models.UniqueConstraint(fields=["group", "purpose_key"], condition=Q(kind=ConversationContextKind.GROUP), name="conv_ctx_group_purpose_unique"),
            models.UniqueConstraint(fields=["activity", "purpose_key"], condition=Q(kind=ConversationContextKind.ACTIVITY), name="conv_ctx_activity_purpose_unique"),
            models.UniqueConstraint(fields=["occurrence", "purpose_key"], condition=Q(kind=ConversationContextKind.OCCURRENCE), name="conv_ctx_occ_purpose_unique"),
            models.UniqueConstraint(fields=["dossier", "purpose_key"], condition=Q(kind=ConversationContextKind.DOSSIER), name="conv_ctx_dossier_purpose_unique"),
            models.UniqueConstraint(fields=["project", "purpose_key"], condition=Q(kind=ConversationContextKind.PROJECT), name="conv_ctx_project_purpose_unique"),
            models.UniqueConstraint(fields=["journey", "purpose_key"], condition=Q(kind=ConversationContextKind.JOURNEY), name="conv_ctx_journey_purpose_unique"),
            models.UniqueConstraint(fields=["action_proposal", "purpose_key"], condition=Q(kind=ConversationContextKind.ACTION_PROPOSAL), name="conv_ctx_proposal_purpose_unique"),
            models.UniqueConstraint(fields=["direct_profile_a", "direct_profile_b", "purpose_key"], condition=Q(kind=ConversationContextKind.DIRECT), name="conv_ctx_direct_purpose_unique"),
        ]
        indexes = [
            models.Index(fields=["kind", "created_at"], name="conv_context_kind_idx"),
        ]

    TARGET_FIELDS = {
        ConversationContextKind.SPACE: ("space",),
        ConversationContextKind.GROUP: ("group",),
        ConversationContextKind.ACTIVITY: ("activity",),
        ConversationContextKind.OCCURRENCE: ("occurrence",),
        ConversationContextKind.DOSSIER: ("dossier",),
        ConversationContextKind.PROJECT: ("project",),
        ConversationContextKind.JOURNEY: ("journey",),
        ConversationContextKind.ACTION_PROPOSAL: ("action_proposal",),
        ConversationContextKind.DIRECT: ("direct_profile_a", "direct_profile_b"),
    }

    def _normalize_direct_pair(self):
        if self.kind != ConversationContextKind.DIRECT or not self.direct_profile_a_id or not self.direct_profile_b_id:
            return
        if str(self.direct_profile_a_id) > str(self.direct_profile_b_id):
            self.direct_profile_a_id, self.direct_profile_b_id = self.direct_profile_b_id, self.direct_profile_a_id

    def clean(self):
        super().clean()
        self.purpose_key = (self.purpose_key or "coordination").strip().lower()
        self.separation_reason = (self.separation_reason or "").strip()
        self._normalize_direct_pair()
        errors = {}
        expected = set(self.TARGET_FIELDS.get(self.kind, ()))
        all_fields = {field for fields in self.TARGET_FIELDS.values() for field in fields}
        for field in all_fields:
            present = bool(getattr(self, f"{field}_id", None))
            if field in expected and not present:
                errors[field] = "Ce contexte exige cette cible."
            if field not in expected and present:
                errors[field] = "Cette cible n’appartient pas à ce type de contexte."
        if self.kind == ConversationContextKind.DIRECT and self.direct_profile_a_id == self.direct_profile_b_id:
            errors["direct_profile_b"] = "Une Conversation directe exige deux Profiles distincts."
        if self.purpose_key != "coordination" and not self.separation_reason:
            errors["separation_reason"] = "Une Conversation séparée du flux de coordination doit expliquer sa finalité distincte."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self._normalize_direct_pair()
        self.full_clean()
        return super().save(*args, **kwargs)


class ConversationPolicy(models.Model):
    conversation = models.OneToOneField(Conversation, on_delete=models.CASCADE, related_name="policy")
    preset = models.CharField(max_length=24, choices=ConversationModePreset.choices, default=ConversationModePreset.MIXED)
    allow_information = models.BooleanField(default=True)
    allow_questions = models.BooleanField(default=True)
    allow_confirmations = models.BooleanField(default=True)
    allow_polls = models.BooleanField(default=True)
    allow_requests = models.BooleanField(default=True)
    allow_form_requests = models.BooleanField(default=True)
    allow_free_exchange = models.BooleanField(default=True)
    allow_voice = models.BooleanField(default=True)
    allow_images = models.BooleanField(default=True)
    allow_video = models.BooleanField(default=False)
    allow_documents = models.BooleanField(default=True)
    allow_links = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class ConversationParticipation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="explicit_participations")
    profile = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="action_conversation_participations")
    represented_space = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="represented_conversation_participations",
        null=True,
        blank=True,
    )
    source = models.CharField(max_length=24, choices=ConversationParticipationSource.choices, default=ConversationParticipationSource.MANUAL)
    status = models.CharField(max_length=16, choices=ConversationParticipationStatus.choices, default=ConversationParticipationStatus.ACTIVE)
    joined_at = models.DateTimeField(default=timezone.now)
    left_at = models.DateTimeField(null=True, blank=True)
    removed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_conversation_participations")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["conversation", "profile"], name="conv_participation_profile_unique")]
        indexes = [models.Index(fields=["profile", "status"], name="conv_part_profile_status_idx")]

    def clean(self):
        super().clean()
        errors = {}
        if self.status == ConversationParticipationStatus.ACTIVE and (self.left_at or self.removed_at):
            errors["status"] = "Une participation active ne peut pas être marquée quittée ou retirée."
        if self.status == ConversationParticipationStatus.LEFT and not self.left_at:
            errors["left_at"] = "Une participation quittée conserve sa date de sortie."
        if self.status == ConversationParticipationStatus.REMOVED and not self.removed_at:
            errors["removed_at"] = "Une participation retirée conserve sa date de retrait."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class ConversationInvitation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="invitations")
    invitee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="conversation_invitations")
    represented_space = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT, related_name="conversation_invitations", null=True, blank=True)
    status = models.CharField(max_length=16, choices=ConversationInvitationStatus.choices, default=ConversationInvitationStatus.PENDING)
    expires_at = models.DateTimeField(null=True, blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    client_reference = models.CharField(max_length=80, null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_conversation_invitations")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["conversation", "invitee"], condition=Q(status=ConversationInvitationStatus.PENDING), name="conv_invite_pending_unique"),
            models.UniqueConstraint(fields=["client_reference"], condition=Q(client_reference__isnull=False), name="conv_invite_client_ref_unique"),
        ]
        indexes = [models.Index(fields=["invitee", "status"], name="conv_invitee_status_idx")]

    def save(self, *args, **kwargs):
        self.client_reference = (self.client_reference or "").strip() or None
        self.full_clean()
        return super().save(*args, **kwargs)


class ConversationJoinRequest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="join_requests")
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="conversation_join_requests")
    represented_space = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT, related_name="conversation_join_requests", null=True, blank=True)
    status = models.CharField(max_length=16, choices=ConversationJoinRequestStatus.choices, default=ConversationJoinRequestStatus.PENDING)
    responded_at = models.DateTimeField(null=True, blank=True)
    client_reference = models.CharField(max_length=80, null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_conversation_join_requests")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["conversation", "requester"], condition=Q(status=ConversationJoinRequestStatus.PENDING), name="conv_join_pending_unique"),
            models.UniqueConstraint(fields=["client_reference"], condition=Q(client_reference__isnull=False), name="conv_join_client_ref_unique"),
        ]
        indexes = [models.Index(fields=["requester", "status"], name="conv_join_requester_idx")]

    def save(self, *args, **kwargs):
        self.client_reference = (self.client_reference or "").strip() or None
        self.full_clean()
        return super().save(*args, **kwargs)


class ConversationUserState(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="user_states")
    profile = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversation_user_states")
    last_opened_at = models.DateTimeField(null=True, blank=True)
    muted_at = models.DateTimeField(null=True, blank=True)
    muted_until = models.DateTimeField(null=True, blank=True)
    hidden_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    pinned_at = models.DateTimeField(null=True, blank=True)
    revisit_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["conversation", "profile"], name="conv_user_state_unique")]
        indexes = [
            models.Index(fields=["profile", "archived_at"], name="conv_user_archived_idx"),
            models.Index(fields=["profile", "pinned_at"], name="conv_user_pinned_idx"),
        ]

    def clean(self):
        super().clean()
        if self.muted_until and not self.muted_at:
            raise ValidationError({"muted_at": "Une sourdine temporaire doit conserver sa date de début."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
