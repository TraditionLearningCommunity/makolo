import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("organizations", "0004_profilefollow"),
        ("presentations", "0002_presentationasset"),
    ]

    operations = [
        migrations.CreateModel(
            name="SpacePresentationDefault",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("purpose", models.CharField(choices=[("public_page", "Page publique"), ("invitation", "Invitation"), ("access_pass", "Billet / Access"), ("confirmation", "Confirmation"), ("program", "Programme"), ("badge", "Badge")], max_length=24)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("space", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="presentation_defaults", to="organizations.organization")),
                ("template_version", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="space_defaults", to="presentations.presentationtemplateversion")),
                ("theme_version", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="space_defaults", to="presentations.presentationthemeversion")),
                ("updated_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="updated_presentation_defaults", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="PresentationTemplateModeration",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("submitted_at", models.DateTimeField(auto_now_add=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("decision_note", models.TextField(blank=True)),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="reviewed_presentation_templates", to=settings.AUTH_USER_MODEL)),
                ("submitted_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="submitted_presentation_templates", to=settings.AUTH_USER_MODEL)),
                ("version", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="moderation", to="presentations.presentationtemplateversion")),
            ],
        ),
        migrations.AddConstraint(
            model_name="spacepresentationdefault",
            constraint=models.UniqueConstraint(fields=("space", "purpose"), name="mps_space_purpose_default_unique"),
        ),
    ]
