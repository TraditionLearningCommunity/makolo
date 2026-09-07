import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from topics.models import ActionMatchKind


class ContributionKind(models.TextChoices):
    UPDATE = "update", "Mise à jour officielle"
    TIP = "tip", "Conseil"
    FIELD_NOTE = "field_note", "Note terrain"
    DISCUSSION = "discussion", "Discussion"
    SHARE = "share", "Partage d'Activity"


class ContributionVisibility(models.TextChoices):
    PUBLIC = "public", "Publique"
    CONTEXT = "context", "Contexte autorisé"


class ContributionStatus(models.TextChoices):
    PUBLISHED = "published", "Publiée"
    HIDDEN = "hidden", "Masquée"
    REMOVED = "removed", "Retirée"


class Contribution(models.Model):
    """UGC anchored to canonical Makolo contexts.

    The model deliberately stores references, not copied Activity/Space/Group
    facts. A Contribution can never be a context-free social post.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    author_profile = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="social_contributions",
    )
    kind = models.CharField(max_length=24, choices=ContributionKind.choices)
    body = models.TextField(max_length=2400, blank=True)
    space = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="social_contributions",
        null=True,
        blank=True,
    )
    group = models.ForeignKey(
        "groups.Group",
        on_delete=models.PROTECT,
        related_name="social_contributions",
        null=True,
        blank=True,
    )
    activity = models.ForeignKey(
        "activities.Activity",
        on_delete=models.PROTECT,
        related_name="social_contributions",
        null=True,
        blank=True,
    )
    occurrence = models.ForeignKey(
        "activities.Occurrence",
        on_delete=models.PROTECT,
        related_name="social_contributions",
        null=True,
        blank=True,
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="replies",
        null=True,
        blank=True,
    )
    visibility = models.CharField(
        max_length=16,
        choices=ContributionVisibility.choices,
        default=ContributionVisibility.CONTEXT,
    )
    status = models.CharField(
        max_length=16,
        choices=ContributionStatus.choices,
        default=ContributionStatus.PUBLISHED,
    )
    edited_at = models.DateTimeField(null=True, blank=True)
    moderated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="moderated_social_contributions",
        null=True,
        blank=True,
    )
    moderated_at = models.DateTimeField(null=True, blank=True)
    moderation_reason = models.CharField(max_length=280, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(space__isnull=False)
                    | Q(group__isnull=False)
                    | Q(activity__isnull=False)
                    | Q(occurrence__isnull=False)
                ),
                name="social_contribution_has_context",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "created_at"], name="social_status_created_idx"),
            models.Index(fields=["group", "status", "created_at"], name="social_group_stream_idx"),
            models.Index(fields=["activity", "status", "created_at"], name="social_activity_stream_idx"),
            models.Index(fields=["space", "status", "created_at"], name="social_space_stream_idx"),
            models.Index(fields=["author_profile", "created_at"], name="social_author_created_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        self.body = (self.body or "").strip()
        self.moderation_reason = (self.moderation_reason or "").strip()
        if not any((self.space_id, self.group_id, self.activity_id, self.occurrence_id)):
            errors["activity"] = "Une Contribution doit être ancrée dans un contexte Makolo."
        if self.kind != ContributionKind.SHARE and not self.body:
            errors["body"] = "Le texte de la Contribution est obligatoire."
        if self.kind == ContributionKind.SHARE and not (self.group_id and self.activity_id):
            errors["kind"] = "Un partage interne doit référencer un Groupe et une Activity."
        if self.group_id and self.visibility == ContributionVisibility.PUBLIC:
            errors["visibility"] = "Le contenu d'un Groupe reste limité aux personnes autorisées."
        if self.occurrence_id:
            if not self.activity_id:
                errors["activity"] = "Une Contribution liée à une Occurrence doit référencer son Activity."
            elif self.occurrence.activity_id != self.activity_id:
                errors["occurrence"] = "L'Occurrence doit appartenir à la même Activity."
        if self.space_id and self.activity_id and self.activity.space_id and self.activity.space_id != self.space_id:
            errors["space"] = "L'Espace explicite doit être cohérent avec l'Activity."
        if self.group_id and self.space_id and self.group.space_id and self.group.space_id != self.space_id:
            errors["space"] = "L'Espace explicite doit être cohérent avec le Groupe."
        if self.parent_id:
            if self.parent_id == self.pk:
                errors["parent"] = "Une Contribution ne peut pas se répondre à elle-même."
            if self.parent.parent_id:
                errors["parent"] = "Les discussions Makolo sont limitées à une profondeur de réponse."
            for field in ("space_id", "group_id", "activity_id", "occurrence_id", "visibility"):
                if getattr(self, field) != getattr(self.parent, field):
                    errors["parent"] = "Une réponse doit conserver exactement le contexte de la Contribution racine."
                    break
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.pk and not self._state.adding and not getattr(self, "_allow_status_transition", False):
            previous = Contribution.objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if previous is not None and previous != self.status:
                raise ValidationError({"status": "Utilisez le service de modération pour changer cet état."})
        result = super().save(*args, **kwargs)
        self._allow_status_transition = False
        return result

    @property
    def is_reply(self):
        return self.parent_id is not None

    def __str__(self):
        return f"{self.get_kind_display()} — {self.author_profile}"


class ActionNeedStatus(models.TextChoices):
    DRAFT = "draft", "Brouillon"
    OPEN = "open", "Ouvert"
    PAUSED = "paused", "En pause"
    FILLED = "filled", "Satisfait"
    CANCELLED = "cancelled", "Annulé"
    EXPIRED = "expired", "Expiré"


class ActionNeedCandidateKind(models.TextChoices):
    PROFILE = "profile", "Profil"
    SPACE = "space", "Espace"
    EITHER = "either", "Profil ou Espace"


class ActionNeedVisibility(models.TextChoices):
    PRIVATE = "private", "Privé"
    MATCHED = "matched", "Candidats compatibles"
    PUBLIC = "public", "Public"


class ActionNeedIntakePolicy(models.TextChoices):
    INVITE_ONLY = "invite_only", "Sur invitation"
    MATCHED = "matched", "Candidats compatibles"
    OPEN = "open", "Ouvert aux propositions"


class ActionNeed(models.Model):
    """A concrete, scoped need in Makolo's bilateral action network."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner_profile = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_action_needs",
        null=True,
        blank=True,
    )
    space = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="action_needs",
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_action_needs",
    )
    title = models.CharField(max_length=220)
    description = models.CharField(max_length=600, blank=True)
    match_kind = models.CharField(max_length=32, choices=ActionMatchKind.choices)
    candidate_kind = models.CharField(
        max_length=16,
        choices=ActionNeedCandidateKind.choices,
        default=ActionNeedCandidateKind.PROFILE,
    )
    topics = models.ManyToManyField("topics.Topic", related_name="action_needs", blank=True)
    activity = models.ForeignKey(
        "activities.Activity",
        on_delete=models.PROTECT,
        related_name="action_needs",
        null=True,
        blank=True,
    )
    occurrence = models.ForeignKey(
        "activities.Occurrence",
        on_delete=models.PROTECT,
        related_name="action_needs",
        null=True,
        blank=True,
    )
    opportunity = models.ForeignKey(
        "opportunities.Opportunity",
        on_delete=models.PROTECT,
        related_name="action_needs",
        null=True,
        blank=True,
    )
    visibility = models.CharField(
        max_length=16,
        choices=ActionNeedVisibility.choices,
        default=ActionNeedVisibility.PRIVATE,
    )
    intake_policy = models.CharField(
        max_length=16,
        choices=ActionNeedIntakePolicy.choices,
        default=ActionNeedIntakePolicy.INVITE_ONLY,
    )
    target_count = models.PositiveIntegerField(null=True, blank=True)
    opens_at = models.DateTimeField(null=True, blank=True)
    closes_at = models.DateTimeField(null=True, blank=True)
    needed_from = models.DateTimeField(null=True, blank=True)
    needed_until = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=ActionNeedStatus.choices, default=ActionNeedStatus.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(owner_profile__isnull=False, space__isnull=True)
                    | Q(owner_profile__isnull=True, space__isnull=False)
                ),
                name="social_action_need_single_owner",
            ),
            models.CheckConstraint(
                condition=Q(target_count__isnull=True) | Q(target_count__gt=0),
                name="social_action_need_target_positive",
            ),
            models.CheckConstraint(
                condition=Q(closes_at__isnull=True) | Q(opens_at__isnull=True) | Q(closes_at__gte=models.F("opens_at")),
                name="social_action_need_intake_window",
            ),
            models.CheckConstraint(
                condition=Q(needed_until__isnull=True) | Q(needed_from__isnull=True) | Q(needed_until__gte=models.F("needed_from")),
                name="social_action_need_needed_window",
            ),
        ]
        indexes = [
            models.Index(fields=["owner_profile", "status", "created_at"], name="social_need_profile_idx"),
            models.Index(fields=["space", "status", "created_at"], name="social_need_space_idx"),
            models.Index(fields=["activity", "status"], name="social_need_activity_idx"),
            models.Index(fields=["occurrence", "status"], name="social_need_occurrence_idx"),
            models.Index(fields=["status", "match_kind"], name="social_need_match_idx"),
            models.Index(fields=["status", "visibility", "intake_policy"], name="social_need_discovery_idx"),
            models.Index(fields=["closes_at"], name="social_need_closes_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        self.title = (self.title or "").strip()
        self.description = (self.description or "").strip()
        if bool(self.owner_profile_id) == bool(self.space_id):
            errors["owner_profile"] = "Un besoin appartient soit à un Profile, soit à un Space, jamais aux deux."
        if self.activity_id:
            if self.owner_profile_id and self.activity.owner_profile_id != self.owner_profile_id:
                errors["activity"] = "L'Activity doit appartenir au même Profile que le besoin."
            if self.space_id and self.activity.space_id != self.space_id:
                errors["activity"] = "L'Activity doit appartenir au même Space que le besoin."
        if self.occurrence_id:
            if not self.activity_id:
                errors["activity"] = "Une Occurrence exige une Activity explicite sur le besoin."
            elif self.occurrence.activity_id != self.activity_id:
                errors["occurrence"] = "L'Occurrence doit appartenir à l'Activity du besoin."
        if self.target_count is not None and self.target_count <= 0:
            errors["target_count"] = "Le nombre recherché doit être strictement positif."
        if self.opens_at and self.closes_at and self.closes_at < self.opens_at:
            errors["closes_at"] = "La fermeture doit être postérieure à l'ouverture."
        if self.needed_from and self.needed_until and self.needed_until < self.needed_from:
            errors["needed_until"] = "La fin du besoin doit être postérieure à son début."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.pk and not self._state.adding and not getattr(self, "_allow_status_transition", False):
            previous = ActionNeed.objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if previous is not None and previous != self.status:
                raise ValidationError({"status": "Utilisez le service ActionNeed pour changer cet état."})
        result = super().save(*args, **kwargs)
        self._allow_status_transition = False
        return result

    @property
    def owner_display_name(self):
        if self.space_id:
            return self.space.name
        if self.owner_profile_id:
            return self.owner_profile.full_name or self.owner_profile.username
        return ""

    @property
    def open_to_kind(self):
        """Compatibility accessor for pre-convergence presentation code."""
        return self.match_kind

    def __str__(self):
        return self.title


class ActionProposalDirection(models.TextChoices):
    OWNER_TO_CANDIDATE = "owner_to_candidate", "Invitation du propriétaire"
    CANDIDATE_TO_OWNER = "candidate_to_owner", "Proposition du candidat"


class ActionProposalStatus(models.TextChoices):
    PENDING = "pending", "En attente"
    ACCEPTED = "accepted", "Acceptée"
    DECLINED = "declined", "Refusée"
    CANCELLED = "cancelled", "Annulée"
    EXPIRED = "expired", "Expirée"


class ActionProposal(models.Model):
    """Explicit bilateral proposal for one candidate to satisfy one ActionNeed."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    need = models.ForeignKey(ActionNeed, on_delete=models.PROTECT, related_name="proposals")
    candidate_profile = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="action_proposals_as_candidate",
        null=True,
        blank=True,
    )
    candidate_space = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="action_proposals_as_candidate",
        null=True,
        blank=True,
    )
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="initiated_action_proposals",
    )
    direction = models.CharField(
        max_length=24,
        choices=ActionProposalDirection.choices,
        default=ActionProposalDirection.OWNER_TO_CANDIDATE,
    )
    status = models.CharField(
        max_length=16,
        choices=ActionProposalStatus.choices,
        default=ActionProposalStatus.PENDING,
    )
    message = models.CharField(max_length=500, blank=True)
    response_message = models.CharField(max_length=500, blank=True)
    responded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="responded_action_proposals",
        null=True,
        blank=True,
    )
    responded_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="cancelled_action_proposals",
        null=True,
        blank=True,
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    client_reference = models.CharField(max_length=80, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(candidate_profile__isnull=False, candidate_space__isnull=True)
                    | Q(candidate_profile__isnull=True, candidate_space__isnull=False)
                ),
                name="social_action_proposal_single_candidate",
            ),
            models.UniqueConstraint(
                fields=["need", "candidate_profile"],
                condition=Q(candidate_profile__isnull=False, status__in=[ActionProposalStatus.PENDING, ActionProposalStatus.ACCEPTED]),
                name="social_prop_profile_active_unique",
            ),
            models.UniqueConstraint(
                fields=["need", "candidate_space"],
                condition=Q(candidate_space__isnull=False, status__in=[ActionProposalStatus.PENDING, ActionProposalStatus.ACCEPTED]),
                name="social_prop_space_active_unique",
            ),
            models.UniqueConstraint(
                fields=["client_reference"],
                condition=Q(client_reference__isnull=False),
                name="social_prop_client_ref_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["need", "status", "created_at"], name="social_prop_need_status_idx"),
            models.Index(fields=["candidate_profile", "status", "created_at"], name="social_prop_profile_idx"),
            models.Index(fields=["candidate_space", "status", "created_at"], name="social_prop_space_idx"),
            models.Index(fields=["initiated_by", "created_at"], name="social_prop_initiator_idx"),
            models.Index(fields=["expires_at"], name="social_prop_expires_idx"),
        ]

    def clean(self):
        super().clean()
        self.message = (self.message or "").strip()
        self.response_message = (self.response_message or "").strip()
        self.client_reference = (self.client_reference or "").strip() or None
        errors = {}
        if bool(self.candidate_profile_id) == bool(self.candidate_space_id):
            errors["candidate_profile"] = "Une proposition vise soit un Profile, soit un Space, jamais les deux."
        if self.need_id:
            if self.candidate_profile_id and self.need.candidate_kind == ActionNeedCandidateKind.SPACE:
                errors["candidate_profile"] = "Ce besoin recherche uniquement un Space."
            if self.candidate_space_id and self.need.candidate_kind == ActionNeedCandidateKind.PROFILE:
                errors["candidate_space"] = "Ce besoin recherche uniquement un Profile."
            if self.need.owner_profile_id and self.need.owner_profile_id == self.candidate_profile_id:
                errors["candidate_profile"] = "Un besoin personnel ne peut pas viser son propre propriétaire."
            if self.need.space_id and self.need.space_id == self.candidate_space_id:
                errors["candidate_space"] = "Un besoin Space ne peut pas viser son propre Space."
            if self._state.adding and self.need.status != ActionNeedStatus.OPEN:
                errors["need"] = "Une nouvelle proposition exige un besoin ouvert."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.pk and not self._state.adding and not getattr(self, "_allow_status_transition", False):
            previous = ActionProposal.objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if previous is not None and previous != self.status:
                raise ValidationError({"status": "Utilisez le service ActionProposal pour répondre ou annuler."})
        result = super().save(*args, **kwargs)
        self._allow_status_transition = False
        return result

    def __str__(self):
        candidate = self.candidate_profile or self.candidate_space
        return f"{self.need} → {candidate} ({self.get_status_display()})"


class ActionNetworkBlock(models.Model):
    """Symmetric matching/contact exclusion initiated by one Profile or Space."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    blocker_profile = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="action_network_blocks_created_as_profile",
        null=True,
        blank=True,
    )
    blocker_space = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="action_network_blocks_created_as_space",
        null=True,
        blank=True,
    )
    blocked_profile = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="action_network_blocks_received_as_profile",
        null=True,
        blank=True,
    )
    blocked_space = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="action_network_blocks_received_as_space",
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_action_network_blocks",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(blocker_profile__isnull=False, blocker_space__isnull=True)
                    | Q(blocker_profile__isnull=True, blocker_space__isnull=False)
                ),
                name="social_block_single_blocker",
            ),
            models.CheckConstraint(
                condition=(
                    Q(blocked_profile__isnull=False, blocked_space__isnull=True)
                    | Q(blocked_profile__isnull=True, blocked_space__isnull=False)
                ),
                name="social_block_single_blocked",
            ),
            models.UniqueConstraint(
                fields=["blocker_profile", "blocked_profile"],
                condition=Q(blocker_profile__isnull=False, blocked_profile__isnull=False),
                name="social_block_profile_profile_unique",
            ),
            models.UniqueConstraint(
                fields=["blocker_profile", "blocked_space"],
                condition=Q(blocker_profile__isnull=False, blocked_space__isnull=False),
                name="social_block_profile_space_unique",
            ),
            models.UniqueConstraint(
                fields=["blocker_space", "blocked_profile"],
                condition=Q(blocker_space__isnull=False, blocked_profile__isnull=False),
                name="social_block_space_profile_unique",
            ),
            models.UniqueConstraint(
                fields=["blocker_space", "blocked_space"],
                condition=Q(blocker_space__isnull=False, blocked_space__isnull=False),
                name="social_block_space_space_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["blocker_profile", "blocked_profile"], name="social_block_pp_idx"),
            models.Index(fields=["blocker_profile", "blocked_space"], name="social_block_ps_idx"),
            models.Index(fields=["blocker_space", "blocked_profile"], name="social_block_sp_idx"),
            models.Index(fields=["blocker_space", "blocked_space"], name="social_block_ss_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if bool(self.blocker_profile_id) == bool(self.blocker_space_id):
            errors["blocker_profile"] = "Un bloc est porté soit par un Profile, soit par un Space."
        if bool(self.blocked_profile_id) == bool(self.blocked_space_id):
            errors["blocked_profile"] = "Un bloc vise soit un Profile, soit un Space."
        if self.blocker_profile_id and self.blocked_profile_id and self.blocker_profile_id == self.blocked_profile_id:
            errors["blocked_profile"] = "Un Profile ne peut pas se bloquer lui-même."
        if self.blocker_space_id and self.blocked_space_id and self.blocker_space_id == self.blocked_space_id:
            errors["blocked_space"] = "Un Space ne peut pas se bloquer lui-même."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


# Compatibility names for pre-convergence callers. New code should use ActionProposal.
ProfileSolicitation = ActionProposal
ProfileSolicitationStatus = ActionProposalStatus
