import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("journeys", "0003_services_core_journey_collaboration"),
        ("organizations", "0004_profilefollow"),
    ]

    operations = [
        migrations.CreateModel(
            name="Dossier",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=220)),
                ("description", models.TextField(blank=True)),
                ("deadline", models.DateField(blank=True, null=True)),
                ("lifecycle", models.CharField(choices=[("draft", "Brouillon"), ("active", "Actif"), ("completed", "Terminé"), ("cancelled", "Annulé"), ("archived", "Archivé")], default="draft", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_dossiers", to=settings.AUTH_USER_MODEL)),
                ("owner_profile", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="owned_dossiers", to=settings.AUTH_USER_MODEL)),
                ("owning_space", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="dossiers", to="organizations.organization")),
            ],
            options={"ordering": ["-updated_at", "id"]},
        ),
        migrations.CreateModel(
            name="DossierJourneyLink",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("linked_at", models.DateTimeField(auto_now_add=True)),
                ("is_active", models.BooleanField(default=True)),
                ("unlinked_at", models.DateTimeField(blank=True, null=True)),
                ("dossier", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="journey_links", to="objectives.dossier")),
                ("journey", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="dossier_links", to="journeys.journey")),
                ("linked_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="dossier_journey_links_created", to=settings.AUTH_USER_MODEL)),
                ("unlinked_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="dossier_journey_links_removed", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["linked_at", "id"]},
        ),
        migrations.AddConstraint(
            model_name="dossier",
            constraint=models.CheckConstraint(
                condition=(models.Q(owner_profile__isnull=False, owning_space__isnull=True) | models.Q(owner_profile__isnull=True, owning_space__isnull=False)),
                name="dossier_exactly_one_owner_context",
            ),
        ),
        migrations.AddConstraint(
            model_name="dossierjourneylink",
            constraint=models.UniqueConstraint(condition=models.Q(is_active=True), fields=("dossier", "journey"), name="dossier_journey_one_active_link"),
        ),
        migrations.AddIndex(model_name="dossier", index=models.Index(fields=["owner_profile", "lifecycle"], name="dossier_owner_lifecycle_idx")),
        migrations.AddIndex(model_name="dossier", index=models.Index(fields=["owning_space", "lifecycle"], name="dossier_space_lifecycle_idx")),
        migrations.AddIndex(model_name="dossierjourneylink", index=models.Index(fields=["dossier", "is_active"], name="dossier_link_active_idx")),
        migrations.AddIndex(model_name="dossierjourneylink", index=models.Index(fields=["journey", "is_active"], name="journey_dossier_active_idx")),
    ]
