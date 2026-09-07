import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from .audience_models import ConversationAudienceSet
from .core_models import Conversation


class ConversationPointKind(models.TextChoices):
    INFORMATION = "information", "Information"
    QUESTION = "question", "Question"
    CONFIRMATION = "confirmation", "Confirmation"
    POLL = "poll", "Sondage"
    REQUEST = "request", "Demande"
    FORM_REQUEST = "form_request", "Formulaire"
    EXCHANGE = "exchange", "Échange"


class ConversationPointResponseMode(models.TextChoices):
    NONE = "none", "Aucune réponse"
    FREE_TEXT = "free_text", "Texte libre"
    BOOLEAN = "boolean", "Oui / non"
    SINGLE_CHOICE = "single_choice", "Choix unique"
    MULTIPLE_CHOICE = "multiple_choice", "Choix multiples"
    NUMBER = "number", "Nombre"
    DATE = "date", "Date"
    DATETIME = "datetime", "Date et heure"
    FILE = "file", "Fichier"
    VOICE = "voice", "Vocal"


class ConversationPointResolutionPolicy(models.TextChoices):
    MANUAL = "manual", "Manuelle"
    PLURALITY = "plurality", "Pluralité"
    ABSOLUTE_MAJORITY = "absolute_majority", "Majorité absolue"
    UNANIMITY = "unanimity", "Unanimité"
    THRESHOLD = "threshold", "Seuil"
    FIRST_VALID = "first_valid", "Première réponse valide"
    NO_OUTCOME = "no_outcome", "Sans résultat"


class ConversationPointLifecycle(models.TextChoices):
    DRAFT = "draft", "Brouillon"
    OPEN = "open", "Ouvert"
    RESPONSE_CLOSED = "response_closed", "Réponses closes"
    RESOLVED = "resolved", "Résolu"
    EXPIRED = "expired", "Expiré"
    CANCELLED = "cancelled", "Annulé"
    SUPERSEDED = "superseded", "Remplacé"


class ConversationPointImportance(models.TextChoices):
    NORMAL = "normal", "Normale"
    IMPORTANT = "important", "Importante"
    CRITICAL = "critical", "Critique"


class ConversationResponseVisibility(models.TextChoices):
    AUTHORITIES_ONLY = "authorities_only", "Autorités uniquement"
    RESPONDENT_AND_AUTHORITIES = "respondent_and_authorities", "Répondant et autorités"
    AGGREGATE = "aggregate", "Résultats agrégés"
    POINT_VIEWERS = "point_viewers", "Personnes pouvant voir le Point"


class ConversationPointResponseStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    SUPERSEDED = "superseded", "Remplacée"
    WITHDRAWN = "withdrawn", "Retirée"


class ConversationPointResolutionMethod(models.TextChoices):
    MANUAL = "manual", "Manuelle"
    AUTOMATIC = "automatic", "Automatique"
    DOMAIN_EVENT = "domain_event", "Événement métier"


class ConversationExchangeModerationState(models.TextChoices):
    VISIBLE = "visible", "Visible"
    HIDDEN = "hidden", "Masquée"
    REMOVED = "removed", "Retirée"


class ConversationPoint(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="points")
    kind = models.CharField(max_length=24, choices=ConversationPointKind.choices)
    response_mode = models.CharField(max_length=24, choices=ConversationPointResponseMode.choices, default=ConversationPointResponseMode.NONE)
    resolution_policy = models.CharField(max_length=24, choices=ConversationPointResolutionPolicy.choices, default=ConversationPointResolutionPolicy.MANUAL)
    title = models.CharField(max_length=220, blank=True)
    body = models.TextField(blank=True)
    importance = models.CharField(max_length=16, choices=ConversationPointImportance.choices, default=ConversationPointImportance.NORMAL)
    lifecycle = models.CharField(max_length=24, choices=ConversationPointLifecycle.choices, default=ConversationPointLifecycle.DRAFT)
    visibility_audience = models.ForeignKey(ConversationAudienceSet, on_delete=models.PROTECT, related_name="visible_points", null=True, blank=True)
    response_audience = models.ForeignKey(ConversationAudienceSet, on_delete=models.PROTECT, related_name="response_points", null=True, blank=True)
    expected_action_audience = models.ForeignKey(ConversationAudienceSet, on_delete=models.PROTECT, related_name="expected_action_points", null=True, blank=True)
    resolution_audience = models.ForeignKey(ConversationAudienceSet, on_delete=models.PROTECT, related_name="resolution_points", null=True, blank=True)
    response_visibility = models.CharField(max_length=32, choices=ConversationResponseVisibility.choices, default=ConversationResponseVisibility.RESPONDENT_AND_AUTHORITIES)
    requires_acknowledgement = models.BooleanField(default=False)
    opens_at = models.DateTimeField(null=True, blank=True)
    deadline_at = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    allow_response_change = models.BooleanField(default=False)
    threshold_value = models.PositiveIntegerField(null=True, blank=True)
    supersedes = models.ForeignKey("self", on_delete=models.PROTECT, related_name="superseded_by_points", null=True, blank=True)
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="published_conversation_points")
    represented_space = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT, related_name="published_conversation_points", null=True, blank=True)
    shared_pinned_at = models.DateTimeField(null=True, blank=True)
    shared_pinned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="shared_pinned_conversation_points", null=True, blank=True)
    client_reference = models.CharField(max_length=80, null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    response_closed_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    expired_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-published_at", "-created_at", "id"]
        constraints = [
            models.UniqueConstraint(fields=["client_reference"], condition=Q(client_reference__isnull=False), name="conv_point_client_ref_unique"),
            models.CheckConstraint(condition=Q(deadline_at__isnull=True) | Q(opens_at__isnull=True) | Q(deadline_at__gt=models.F("opens_at")), name="conv_point_deadline_after_open"),
            models.CheckConstraint(condition=Q(valid_until__isnull=True) | Q(opens_at__isnull=True) | Q(valid_until__gt=models.F("opens_at")), name="conv_point_valid_after_open"),
        ]
        indexes = [
            models.Index(fields=["conversation", "lifecycle", "published_at"], name="conv_point_state_pub_idx"),
            models.Index(fields=["deadline_at", "lifecycle"], name="conv_point_deadline_idx"),
            models.Index(fields=["importance", "lifecycle"], name="conv_point_importance_idx"),
        ]

    def clean(self):
        super().clean()
        self.title = (self.title or "").strip()
        self.body = (self.body or "").strip()
        self.client_reference = (self.client_reference or "").strip() or None
        errors = {}
        for field in ("visibility_audience", "response_audience", "expected_action_audience", "resolution_audience"):
            audience = getattr(self, field, None)
            if audience and self.conversation_id and audience.conversation_id != self.conversation_id:
                errors[field] = "L’audience doit appartenir à cette Conversation."
        if self.supersedes_id:
            if self.supersedes_id == self.pk:
                errors["supersedes"] = "Un Point ne peut pas se remplacer lui-même."
            elif self.conversation_id and self.supersedes.conversation_id != self.conversation_id:
                errors["supersedes"] = "Un Point ne peut remplacer qu’un Point de la même Conversation."
        if self.kind == ConversationPointKind.INFORMATION and self.response_mode != ConversationPointResponseMode.NONE and not self.requires_acknowledgement:
            errors["response_mode"] = "Une Information sans acknowledgement n’attend pas de réponse structurée."
        if self.kind == ConversationPointKind.EXCHANGE and self.response_mode != ConversationPointResponseMode.FREE_TEXT:
            errors["response_mode"] = "Un Échange utilise le mode texte libre."
        if self.kind == ConversationPointKind.POLL and self.response_mode not in {ConversationPointResponseMode.SINGLE_CHOICE, ConversationPointResponseMode.MULTIPLE_CHOICE}:
            errors["response_mode"] = "Un Sondage utilise un choix unique ou multiple."
        if self.resolution_policy == ConversationPointResolutionPolicy.THRESHOLD and not self.threshold_value:
            errors["threshold_value"] = "Une résolution par seuil exige une valeur positive."
        if self.resolution_policy != ConversationPointResolutionPolicy.THRESHOLD and self.threshold_value is not None:
            errors["threshold_value"] = "Seule une résolution par seuil utilise threshold_value."
        if self.deadline_at and self.opens_at and self.deadline_at <= self.opens_at:
            errors["deadline_at"] = "La deadline doit être postérieure à l’ouverture."
        if self.valid_until and self.opens_at and self.valid_until <= self.opens_at:
            errors["valid_until"] = "La validité doit dépasser l’ouverture."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.pk and not self._state.adding and not getattr(self, "_allow_lifecycle_transition", False):
            previous = ConversationPoint.objects.filter(pk=self.pk).values_list("lifecycle", flat=True).first()
            if previous is not None and previous != self.lifecycle:
                raise ValidationError({"lifecycle": "Utilisez le service Point pour changer cet état."})
        result = super().save(*args, **kwargs)
        self._allow_lifecycle_transition = False
        return result


class ConversationPointOption(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    point = models.ForeignKey(ConversationPoint, on_delete=models.CASCADE, related_name="options")
    label = models.CharField(max_length=220)
    position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(fields=["point", "position"], name="conv_point_option_position_unique"),
            models.UniqueConstraint(fields=["point", "label"], name="conv_point_option_label_unique"),
        ]

    def save(self, *args, **kwargs):
        self.label = (self.label or "").strip()
        if self.point_id and self.point.lifecycle != ConversationPointLifecycle.DRAFT and not self._state.adding:
            previous = ConversationPointOption.objects.filter(pk=self.pk).values("label", "position").first()
            if previous and (previous["label"] != self.label or previous["position"] != self.position):
                raise ValidationError("Les options d’un Point publié sont immuables ; remplacez le Point.")
        self.full_clean()
        return super().save(*args, **kwargs)


class ConversationPointResponse(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    point = models.ForeignKey(ConversationPoint, on_delete=models.PROTECT, related_name="responses")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="conversation_point_responses")
    represented_space = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT, related_name="conversation_point_responses", null=True, blank=True)
    value = models.JSONField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=ConversationPointResponseStatus.choices, default=ConversationPointResponseStatus.ACTIVE)
    supersedes = models.ForeignKey("self", on_delete=models.PROTECT, related_name="superseded_by_responses", null=True, blank=True)
    client_reference = models.CharField(max_length=80, null=True, blank=True)
    submitted_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["point_id", "submitted_at", "id"]
        constraints = [
            models.UniqueConstraint(fields=["point", "actor"], condition=Q(status=ConversationPointResponseStatus.ACTIVE, represented_space__isnull=True), name="conv_resp_actor_active_unique"),
            models.UniqueConstraint(fields=["point", "represented_space"], condition=Q(status=ConversationPointResponseStatus.ACTIVE, represented_space__isnull=False), name="conv_resp_space_active_unique"),
            models.UniqueConstraint(fields=["client_reference"], condition=Q(client_reference__isnull=False), name="conv_resp_client_ref_unique"),
        ]
        indexes = [
            models.Index(fields=["point", "status"], name="conv_resp_point_status_idx"),
            models.Index(fields=["actor", "status"], name="conv_resp_actor_status_idx"),
            models.Index(fields=["represented_space", "status"], name="conv_resp_space_status_idx"),
        ]

    def save(self, *args, **kwargs):
        self.client_reference = (self.client_reference or "").strip() or None
        self.full_clean()
        return super().save(*args, **kwargs)


class ConversationPointResolution(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    point = models.OneToOneField(ConversationPoint, on_delete=models.PROTECT, related_name="resolution")
    method = models.CharField(max_length=16, choices=ConversationPointResolutionMethod.choices)
    summary = models.CharField(max_length=500)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="resolved_conversation_points", null=True, blank=True)
    resolved_at = models.DateTimeField()
    result_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.summary = (self.summary or "").strip()
        self.full_clean()
        return super().save(*args, **kwargs)


class ConversationPointResolutionOption(models.Model):
    resolution = models.ForeignKey(ConversationPointResolution, on_delete=models.CASCADE, related_name="selected_option_links")
    option = models.ForeignKey(ConversationPointOption, on_delete=models.PROTECT, related_name="resolution_links")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["resolution", "option"], name="conv_resolution_option_unique")]

    def clean(self):
        super().clean()
        if self.resolution_id and self.option_id and self.resolution.point_id != self.option.point_id:
            raise ValidationError({"option": "L’option doit appartenir au Point résolu."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class ConversationPointUserState(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    point = models.ForeignKey(ConversationPoint, on_delete=models.CASCADE, related_name="user_states")
    profile = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversation_point_user_states")
    seen_at = models.DateTimeField(null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    pinned_at = models.DateTimeField(null=True, blank=True)
    revisit_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["point", "profile"], name="conv_point_user_state_unique")]
        indexes = [
            models.Index(fields=["profile", "acknowledged_at"], name="conv_point_user_ack_idx"),
            models.Index(fields=["profile", "revisit_at"], name="conv_point_user_revisit_idx"),
        ]


class PointExchangeEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    point = models.ForeignKey(ConversationPoint, on_delete=models.PROTECT, related_name="exchange_entries")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="conversation_exchange_entries")
    represented_space = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT, related_name="conversation_exchange_entries", null=True, blank=True)
    body = models.TextField(blank=True)
    reply_to = models.ForeignKey("self", on_delete=models.PROTECT, related_name="replies", null=True, blank=True)
    moderation_state = models.CharField(max_length=16, choices=ConversationExchangeModerationState.choices, default=ConversationExchangeModerationState.VISIBLE)
    client_reference = models.CharField(max_length=80, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    removed_at = models.DateTimeField(null=True, blank=True)
    removed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="removed_conversation_exchange_entries", null=True, blank=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [models.UniqueConstraint(fields=["client_reference"], condition=Q(client_reference__isnull=False), name="conv_exchange_client_ref_unique")]
        indexes = [models.Index(fields=["point", "created_at"], name="conv_exchange_point_idx")]

    def clean(self):
        super().clean()
        self.body = (self.body or "").strip()
        self.client_reference = (self.client_reference or "").strip() or None
        if self.reply_to_id and self.reply_to.point_id != self.point_id:
            raise ValidationError({"reply_to": "Une réponse doit rester dans le même Point d’échange."})
        if not self.body:
            raise ValidationError({"body": "Un échange texte ne peut pas être vide."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
