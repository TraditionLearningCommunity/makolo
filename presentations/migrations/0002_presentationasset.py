import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("organizations", "0004_profilefollow"),
        ("presentations", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PresentationAsset",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("provenance", models.CharField(choices=[("makolo", "Makolo"), ("user", "Utilisateur"), ("space", "Espace")], max_length=16)),
                ("file", models.FileField(upload_to="presentations/assets/%Y/%m/")),
                ("mime_type", models.CharField(max_length=80)),
                ("size", models.PositiveIntegerField()),
                ("checksum", models.CharField(max_length=64)),
                ("width", models.PositiveIntegerField(blank=True, null=True)),
                ("height", models.PositiveIntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("owner_profile", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="presentation_assets", to=settings.AUTH_USER_MODEL)),
                ("owner_space", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="presentation_assets", to="organizations.organization")),
                ("uploaded_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="uploaded_presentation_assets", to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
