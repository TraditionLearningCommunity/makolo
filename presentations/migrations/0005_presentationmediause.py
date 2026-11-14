import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("activities", "0001_initial"),
        ("presentations", "0004_theme_slug_constraints"),
    ]

    operations = [
        migrations.CreateModel(
            name="PresentationMediaUse",
            fields=[
                ("id", models.UUIDField(primary_key=True, serialize=False, default=uuid.uuid4, editable=False)),
                ("purpose", models.CharField(max_length=16, choices=[("recognize", "Reconnaître"), ("understand", "Comprendre"), ("establish", "Établir"), ("prepare", "Préparer"), ("act", "Agir")])),
                ("position", models.PositiveIntegerField(default=0)),
                ("state", models.CharField(max_length=16, choices=[("draft", "Brouillon"), ("published", "Publié"), ("retired", "Retiré")], default="draft")),
                ("alt_text", models.CharField(max_length=280)),
                ("published_at", models.DateTimeField(null=True, blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("activity", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="presentation_media_uses", to="activities.activity")),
                ("occurrence", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="presentation_media_uses", to="activities.occurrence", null=True, blank=True)),
                ("asset", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="uses", to="presentations.presentationasset")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_presentation_media_uses", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["position", "created_at", "id"],
                "indexes": [
                    models.Index(fields=["activity", "state", "purpose"], name="mps_media_act_state_purp_idx"),
                    models.Index(fields=["occurrence", "state", "purpose"], name="mps_media_occ_state_purp_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=["activity", "asset", "purpose"], condition=Q(occurrence__isnull=True) & ~Q(state="retired"), name="mps_media_activity_asset_purpose_unique"),
                    models.UniqueConstraint(fields=["occurrence", "asset", "purpose"], condition=Q(occurrence__isnull=False) & ~Q(state="retired"), name="mps_media_occ_asset_purpose_unique"),
                    models.CheckConstraint(condition=Q(state="published", published_at__isnull=False) | ~Q(state="published"), name="mps_media_published_has_date"),
                ],
            },
        ),
    ]
