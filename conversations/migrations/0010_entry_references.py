import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("conversations", "0009_exchange_stream"),
        ("journeys", "0006_space_beneficiary"),
        ("requirements", "0003_generic_activity_journey_requirements"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [migrations.CreateModel(
        name="ConversationEntryReference",
        fields=[
            ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
            ("entry", models.ForeignKey(to="conversations.pointexchangeentry", on_delete=django.db.models.deletion.CASCADE, related_name="references")),
            *[(field, models.ForeignKey(to=target, on_delete=django.db.models.deletion.PROTECT, null=True, blank=True)) for field, target in (
                ("journey_artifact", "journeys.journeyartifact"),
                ("requirement_definition", "requirements.requirementdefinition"),
                ("journey_requirement_assessment", "requirements.journeyrequirementassessment"),
            )],
            ("created_by", models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
        ],
        options={"constraints": [
            models.CheckConstraint(condition=(
                Q(journey_artifact__isnull=False, requirement_definition__isnull=True, journey_requirement_assessment__isnull=True)
                | Q(journey_artifact__isnull=True, requirement_definition__isnull=False, journey_requirement_assessment__isnull=True)
                | Q(journey_artifact__isnull=True, requirement_definition__isnull=True, journey_requirement_assessment__isnull=False)
            ), name="conv_entry_reference_one_target"),
            *[models.UniqueConstraint(fields=["entry", field], name=name) for field, name in (
                ("journey_artifact", "conv_entry_ref_artifact_unique"),
                ("requirement_definition", "conv_entry_ref_definition_unique"),
                ("journey_requirement_assessment", "conv_entry_ref_assessment_unique"),
            )],
        ]},
    )]
