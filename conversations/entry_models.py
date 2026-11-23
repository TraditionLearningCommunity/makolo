"""Subordinate Exchange metadata; no independent messaging domain."""
import uuid
from django.conf import settings
from django.db import models
from django.db.models import F, Q
from .point_models import ConversationPoint, PointExchangeEntry


class ConversationEntryReaction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entry = models.ForeignKey(PointExchangeEntry, on_delete=models.CASCADE, related_name="reactions")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    emoji = models.CharField(max_length=16)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["entry", "actor", "emoji"], name="conv_entry_reaction_unique")]


class ConversationEntryMention(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entry = models.ForeignKey(PointExchangeEntry, on_delete=models.CASCADE, related_name="mentions")
    profile = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["entry", "profile"], name="conv_entry_mention_unique")]


class ConversationEntryRevision(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entry = models.ForeignKey(PointExchangeEntry, on_delete=models.CASCADE, related_name="revisions")
    editor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    from_version = models.PositiveIntegerField()
    to_version = models.PositiveIntegerField()
    old_content_sha256 = models.CharField(max_length=64)
    new_content_sha256 = models.CharField(max_length=64)
    client_reference = models.CharField(max_length=80)
    edited_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["entry", "to_version"], name="conv_entry_revision_unique"),
            models.UniqueConstraint(fields=["entry", "client_reference"], name="conv_entry_revision_ref_unique"),
        ]


class ConversationEntryReceipt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    point = models.ForeignKey(ConversationPoint, on_delete=models.CASCADE, related_name="entry_receipts")
    profile = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    delivered_sequence = models.PositiveBigIntegerField(default=0)
    read_sequence = models.PositiveBigIntegerField(default=0)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["point", "profile"], name="conv_entry_receipt_unique"),
            models.CheckConstraint(condition=Q(read_sequence__lte=F("delivered_sequence")), name="conv_receipt_read_delivered"),
        ]


class ConversationEntryReference(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entry = models.ForeignKey(PointExchangeEntry, on_delete=models.CASCADE, related_name="references")
    journey_artifact = models.ForeignKey("journeys.JourneyArtifact", on_delete=models.PROTECT, null=True, blank=True)
    requirement_definition = models.ForeignKey("requirements.RequirementDefinition", on_delete=models.PROTECT, null=True, blank=True)
    journey_requirement_assessment = models.ForeignKey("requirements.JourneyRequirementAssessment", on_delete=models.PROTECT, null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=(
                Q(journey_artifact__isnull=False, requirement_definition__isnull=True, journey_requirement_assessment__isnull=True)
                | Q(journey_artifact__isnull=True, requirement_definition__isnull=False, journey_requirement_assessment__isnull=True)
                | Q(journey_artifact__isnull=True, requirement_definition__isnull=True, journey_requirement_assessment__isnull=False)
            ), name="conv_entry_reference_one_target"),
            *[models.UniqueConstraint(fields=["entry", target], name=name) for target, name in (
                ("journey_artifact", "conv_entry_ref_artifact_unique"),
                ("requirement_definition", "conv_entry_ref_definition_unique"),
                ("journey_requirement_assessment", "conv_entry_ref_assessment_unique"),
            )],
        ]
