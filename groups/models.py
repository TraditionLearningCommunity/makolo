import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify


class GroupStatus(models.TextChoices):
    ACTIVE = "active", "Actif"
    ARCHIVED = "archived", "Archivé"


class GroupVisibility(models.TextChoices):
    """Legacy pre-T27 visibility kept for migration/backward compatibility."""

    PRIVATE = "private", "Privé"
    SPACE = "space", "Visible dans l’Espace"


class GroupDiscoverability(models.TextChoices):
    LISTED = "listed", "Trouvable dans Makolo"
    UNLISTED = "unlisted", "Uniquement avec le lien"
    HIDDEN = "hidden", "Uniquement les personnes autorisées"
    SPACE_ONLY = "space_only", "Dans cet Espace"


class GroupMembershipPolicy(models.TextChoices):
    OPEN = "open", "Tout le monde"
    REQUEST = "request", "Sur demande"
    INVITE_ONLY = "invite_only", "Sur invitation"


class GroupMembershipStatus(models.TextChoices):
    ACTIVE = "active", "Actif"
    SUSPENDED = "suspended", "Suspendu"
    LEFT = "left", "Parti"
    REMOVED = "removed", "Retiré"


class GroupMembershipSource(models.TextChoices):
    MANUAL = "manual", "Ajout manuel"
    IMPORT = "import", "Import CSV"
    INVITATION = "invitation", "Invitation"
    CLAIM = "claim", "Rattachement vérifié"
    SELF_JOIN = "self_join", "Adhésion directe"
    REQUEST = "request", "Demande approuvée"


class GroupInvitationStatus(models.TextChoices):
    PENDING = "pending", "En attente"
    ACCEPTED = "accepted", "Acceptée"
    REVOKED = "revoked", "Révoquée"
    REJECTED = "rejected", "Refusée"
    EXPIRED = "expired", "Expirée"


class GroupJoinRequestStatus(models.TextChoices):
    PENDING = "pending", "En attente"
    APPROVED = "approved", "Approuvée"
    REJECTED = "rejected", "Refusée"
    CANCELLED = "cancelled", "Annulée"


class ActivityGroupEligibilityStatus(models.TextChoices):
    REQUESTED = "requested", "Demandée"
    APPROVED = "approved", "Approuvée"
    REJECTED = "rejected", "Refusée"
    REVOKED = "revoked", "Révoquée"


class Group(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=180)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField(blank=True)
    space = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="collective_groups",
        null=True,
        blank=True,
    )
    owner_profile = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="personal_groups_owned",
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="collective_groups_created",
        null=True,
        blank=True,
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="GroupMembership",
        related_name="collective_group_memberships",
        blank=True,
    )
    status = models.CharField(
        max_length=16,
        choices=GroupStatus.choices,
        default=GroupStatus.ACTIVE,
    )
    visibility = models.CharField(
        max_length=16,
        choices=GroupVisibility.choices,
        default=GroupVisibility.PRIVATE,
        help_text="Champ historique pré-T27. Utiliser discoverability pour les nouvelles surfaces.",
    )
    discoverability = models.CharField(
        max_length=16,
        choices=GroupDiscoverability.choices,
        default=GroupDiscoverability.HIDDEN,
    )
    membership_policy = models.CharField(
        max_length=16,
        choices=GroupMembershipPolicy.choices,
        default=GroupMembershipPolicy.INVITE_ONLY,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "created_at"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(space__isnull=False, owner_profile__isnull=True)
                    | Q(space__isnull=True, owner_profile__isnull=False)
                ),
                name="groups_group_exactly_one_owner",
            )
        ]
        indexes = [
            models.Index(fields=["space", "status"], name="groups_group_space_status_idx"),
            models.Index(fields=["owner_profile", "status"], name="groups_group_owner_status_idx"),
            models.Index(fields=["discoverability", "status"], name="groups_group_discover_idx"),
            models.Index(fields=["membership_policy", "status"], name="groups_group_policy_idx"),
        ]

    def clean(self):
        super().clean()
        if bool(self.space_id) == bool(self.owner_profile_id):
            raise ValidationError(
                "Un Groupe appartient soit à un Espace, soit à un Profil personnel, jamais aux deux."
            )
        if self.space_id is None and self.visibility == GroupVisibility.SPACE:
            raise ValidationError({"visibility": "Un Groupe personnel ne peut pas être visible dans un Espace."})
        if self.space_id is None and self.discoverability == GroupDiscoverability.SPACE_ONLY:
            raise ValidationError(
                {"discoverability": "Un Groupe personnel ne peut pas être limité à un Espace."}
            )

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:180] or "groupe"
            candidate = base
            suffix = 2
            while Group.objects.exclude(pk=self.pk).filter(slug=candidate).exists():
                candidate = f"{base[:200]}-{suffix}"
                suffix += 1
            self.slug = candidate
        super().save(*args, **kwargs)

    @property
    def is_personal(self):
        return self.owner_profile_id is not None

    @property
    def owner_display_name(self):
        if self.space_id:
            return self.space.name
        if self.owner_profile_id:
            return self.owner_profile.full_name or self.owner_profile.username
        return ""

    def __str__(self):
        return self.name


class GroupMembership(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="memberships")
    profile = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="collective_group_membership_records",
    )
    status = models.CharField(
        max_length=16,
        choices=GroupMembershipStatus.choices,
        default=GroupMembershipStatus.ACTIVE,
    )
    source = models.CharField(
        max_length=16,
        choices=GroupMembershipSource.choices,
        default=GroupMembershipSource.MANUAL,
    )
    joined_at = models.DateTimeField(default=timezone.now)
    verified_at = models.DateTimeField(null=True, blank=True)
    external_reference = models.CharField(max_length=160, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["group__name", "profile__email"]
        constraints = [
            models.UniqueConstraint(
                fields=["group", "profile"],
                name="groups_membership_group_profile_unique",
            ),
            models.UniqueConstraint(
                fields=["group", "external_reference"],
                condition=~Q(external_reference=""),
                name="groups_membership_external_ref_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["group", "status"], name="groups_member_group_status_idx"),
            models.Index(fields=["profile", "status"], name="groups_member_prof_status_idx"),
        ]

    def save(self, *args, **kwargs):
        self.external_reference = (self.external_reference or "").strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.group} — {self.profile}"


class GroupJoinRequest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="join_requests")
    profile = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="group_join_requests",
    )
    status = models.CharField(
        max_length=16,
        choices=GroupJoinRequestStatus.choices,
        default=GroupJoinRequestStatus.PENDING,
    )
    message = models.CharField(max_length=500, blank=True)
    requested_at = models.DateTimeField(default=timezone.now)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="group_join_requests_decided",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-requested_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["group", "profile"],
                condition=Q(status=GroupJoinRequestStatus.PENDING),
                name="groups_join_pending_unique",
            )
        ]
        indexes = [
            models.Index(fields=["group", "status", "requested_at"], name="groups_join_group_status_idx"),
            models.Index(fields=["profile", "status"], name="groups_join_profile_status_idx"),
        ]

    def __str__(self):
        return f"{self.group} — {self.profile} — {self.status}"


class GroupInvitation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="invitations")
    profile = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="collective_group_invitations",
        null=True,
        blank=True,
    )
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    external_reference = models.CharField(max_length=160, blank=True)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="collective_group_invitations_sent",
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=16,
        choices=GroupInvitationStatus.choices,
        default=GroupInvitationStatus.PENDING,
    )
    expires_at = models.DateTimeField()
    token_digest = models.CharField(max_length=64, unique=True)
    verification_digest = models.CharField(max_length=64, blank=True)
    verification_expires_at = models.DateTimeField(null=True, blank=True)
    identity_verified_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(profile__isnull=False)
                    | ~Q(email="")
                    | ~Q(phone="")
                    | ~Q(external_reference="")
                ),
                name="groups_invitation_has_identity",
            )
        ]
        indexes = [
            models.Index(fields=["group", "status"], name="groups_inv_group_status_idx"),
            models.Index(fields=["email", "status"], name="groups_inv_email_status_idx"),
            models.Index(fields=["phone", "status"], name="groups_inv_phone_status_idx"),
            models.Index(fields=["expires_at"], name="groups_inv_expires_idx"),
        ]

    def clean(self):
        super().clean()
        self.email = (self.email or "").strip().lower()
        self.phone = (self.phone or "").strip()
        self.external_reference = (self.external_reference or "").strip()
        if not any((self.profile_id, self.email, self.phone, self.external_reference)):
            raise ValidationError("Une invitation doit cibler au moins une identité.")

    @property
    def is_expired(self):
        return self.expires_at <= timezone.now()

    def __str__(self):
        return f"{self.group} — {self.status}"


class GroupSnapshot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="snapshots")
    name = models.CharField(max_length=180)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="collective_group_snapshots_created",
        null=True,
        blank=True,
    )
    member_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["group", "created_at"], name="groups_snapshot_group_date_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.pk and GroupSnapshot.objects.filter(pk=self.pk).exists():
            raise ValidationError("Un snapshot est immuable après sa création.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Un snapshot historique ne peut pas être supprimé individuellement.")

    def __str__(self):
        return f"{self.group} — {self.name}"


class GroupSnapshotMember(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    snapshot = models.ForeignKey(
        GroupSnapshot,
        on_delete=models.CASCADE,
        related_name="members",
    )
    profile = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="collective_group_snapshot_records",
    )
    external_reference = models.CharField(max_length=160, blank=True)
    joined_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["profile__email"]
        constraints = [
            models.UniqueConstraint(
                fields=["snapshot", "profile"],
                name="groups_snapshot_member_unique",
            )
        ]
        indexes = [
            models.Index(fields=["snapshot", "profile"], name="groups_snap_member_lookup_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.pk and GroupSnapshotMember.objects.filter(pk=self.pk).exists():
            raise ValidationError("Un membre de snapshot est immuable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Un membre de snapshot historique ne peut pas être supprimé individuellement.")

    def __str__(self):
        return f"{self.snapshot} — {self.profile}"


class ActivityGroupEligibility(models.Model):
    """Explicit Group↔Activity eligibility and cross-owner consent relation."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="activity_eligibilities")
    activity = models.ForeignKey(
        "activities.Activity",
        on_delete=models.CASCADE,
        related_name="group_eligibilities",
    )
    status = models.CharField(
        max_length=16,
        choices=ActivityGroupEligibilityStatus.choices,
        default=ActivityGroupEligibilityStatus.REQUESTED,
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="activity_group_eligibilities_requested",
        null=True,
        blank=True,
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="activity_group_eligibilities_decided",
        null=True,
        blank=True,
    )
    requested_at = models.DateTimeField(default=timezone.now)
    decided_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-requested_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["group", "activity"],
                name="groups_activity_eligibility_unique",
            )
        ]
        indexes = [
            models.Index(fields=["group", "status"], name="groups_elig_group_status_idx"),
            models.Index(fields=["activity", "status"], name="groups_elig_act_status_idx"),
        ]

    def __str__(self):
        return f"{self.activity} ↔ {self.group} — {self.status}"
