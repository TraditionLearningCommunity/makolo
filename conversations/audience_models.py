import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from activities.involvement_models import ActivityInvolvementFunctionKind

from .core_models import Conversation


class ConversationAudienceStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    RETIRED = "retired", "Retirée"


class ConversationAudienceRuleOperation(models.TextChoices):
    INCLUDE = "include", "Inclure"
    EXCLUDE = "exclude", "Exclure"


class ConversationAudienceRuleKind(models.TextChoices):
    ALL_CONVERSATION_VIEWERS = "all_conversation_viewers", "Toutes les personnes légitimes"
    EXPLICIT_PROFILE = "explicit_profile", "Profile explicite"
    CONVERSATION_PARTICIPANTS = "conversation_participants", "Participations explicites"
    CONVERSATION_MANAGERS = "conversation_managers", "Responsables de la Conversation"
    GROUP_MEMBERS = "group_members", "Membres d’un Groupe"
    OCCURRENCE_PARTICIPANTS = "occurrence_participants", "Participants d’une Occurrence"
    ACTIVITY_INVOLVEMENT_FUNCTION = "activity_involvement_function", "Fonction dans une Activity"
    ACTION_PROPOSAL_PARTIES = "action_proposal_parties", "Parties d’une proposition"


class ConversationAudienceSet(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="audience_sets")
    label = models.CharField(max_length=160)
    status = models.CharField(max_length=16, choices=ConversationAudienceStatus.choices, default=ConversationAudienceStatus.ACTIVE)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_conversation_audiences")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["conversation_id", "label", "id"]
        constraints = [models.UniqueConstraint(fields=["conversation", "label"], name="conv_audience_label_unique")]
        indexes = [models.Index(fields=["conversation", "status"], name="conv_aud_conv_status_idx")]

    def save(self, *args, **kwargs):
        self.label = (self.label or "").strip()
        self.full_clean()
        return super().save(*args, **kwargs)


class ConversationAudienceRule(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    audience_set = models.ForeignKey(ConversationAudienceSet, on_delete=models.CASCADE, related_name="rules")
    operation = models.CharField(max_length=16, choices=ConversationAudienceRuleOperation.choices, default=ConversationAudienceRuleOperation.INCLUDE)
    kind = models.CharField(max_length=40, choices=ConversationAudienceRuleKind.choices)
    profile = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="conversation_audience_rules", null=True, blank=True)
    group = models.ForeignKey("groups.Group", on_delete=models.PROTECT, related_name="conversation_audience_rules", null=True, blank=True)
    activity = models.ForeignKey("activities.Activity", on_delete=models.PROTECT, related_name="conversation_audience_rules", null=True, blank=True)
    occurrence = models.ForeignKey("activities.Occurrence", on_delete=models.PROTECT, related_name="conversation_audience_rules", null=True, blank=True)
    action_proposal = models.ForeignKey("social.ActionProposal", on_delete=models.PROTECT, related_name="conversation_audience_rules", null=True, blank=True)
    involvement_function_kind = models.CharField(max_length=24, choices=ActivityInvolvementFunctionKind.choices, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["audience_set_id", "operation", "kind", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(kind=ConversationAudienceRuleKind.ALL_CONVERSATION_VIEWERS, profile__isnull=True, group__isnull=True, activity__isnull=True, occurrence__isnull=True, action_proposal__isnull=True, involvement_function_kind="")
                    | Q(kind=ConversationAudienceRuleKind.EXPLICIT_PROFILE, profile__isnull=False, group__isnull=True, activity__isnull=True, occurrence__isnull=True, action_proposal__isnull=True, involvement_function_kind="")
                    | Q(kind=ConversationAudienceRuleKind.CONVERSATION_PARTICIPANTS, profile__isnull=True, group__isnull=True, activity__isnull=True, occurrence__isnull=True, action_proposal__isnull=True, involvement_function_kind="")
                    | Q(kind=ConversationAudienceRuleKind.CONVERSATION_MANAGERS, profile__isnull=True, group__isnull=True, activity__isnull=True, occurrence__isnull=True, action_proposal__isnull=True, involvement_function_kind="")
                    | Q(kind=ConversationAudienceRuleKind.GROUP_MEMBERS, profile__isnull=True, group__isnull=False, activity__isnull=True, occurrence__isnull=True, action_proposal__isnull=True, involvement_function_kind="")
                    | Q(kind=ConversationAudienceRuleKind.OCCURRENCE_PARTICIPANTS, profile__isnull=True, group__isnull=True, activity__isnull=True, occurrence__isnull=False, action_proposal__isnull=True, involvement_function_kind="")
                    | Q(kind=ConversationAudienceRuleKind.ACTIVITY_INVOLVEMENT_FUNCTION, profile__isnull=True, group__isnull=True, activity__isnull=False, action_proposal__isnull=True) & ~Q(involvement_function_kind="")
                    | Q(kind=ConversationAudienceRuleKind.ACTION_PROPOSAL_PARTIES, profile__isnull=True, group__isnull=True, activity__isnull=True, occurrence__isnull=True, action_proposal__isnull=False, involvement_function_kind="")
                ),
                name="conv_audience_rule_shape_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["audience_set", "operation", "kind"], name="conv_aud_rule_lookup_idx"),
            models.Index(fields=["group", "kind"], name="conv_aud_rule_group_idx"),
            models.Index(fields=["occurrence", "kind"], name="conv_aud_rule_occ_idx"),
            models.Index(fields=["activity", "kind"], name="conv_aud_rule_activity_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.kind == ConversationAudienceRuleKind.ACTIVITY_INVOLVEMENT_FUNCTION:
            if not self.activity_id or not self.involvement_function_kind:
                errors["activity"] = "Une audience par fonction exige une Activity et une fonction."
            if self.occurrence_id and self.occurrence.activity_id != self.activity_id:
                errors["occurrence"] = "L’Occurrence doit appartenir à l’Activity de la règle."
        elif self.occurrence_id and self.kind != ConversationAudienceRuleKind.OCCURRENCE_PARTICIPANTS:
            errors["occurrence"] = "Une Occurrence n’est permise ici que pour une fonction d’Activity ciblée."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
