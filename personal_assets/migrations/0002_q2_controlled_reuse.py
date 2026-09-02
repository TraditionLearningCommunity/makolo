import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("journeys", "0003_services_core_journey_collaboration"),
        ("personal_assets", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="personalassetversion",
            name="source_journey_artifact",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="saved_personal_asset_versions", to="journeys.journeyartifact"),
        ),
        migrations.CreateModel(
            name="PersonalAssetUse",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("used_at", models.DateTimeField(auto_now_add=True)),
                ("asset_version", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="journey_uses", to="personal_assets.personalassetversion")),
                ("journey_artifact", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="personal_asset_use", to="journeys.journeyartifact")),
                ("used_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="personal_asset_uses", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-used_at", "id"]},
        ),
        migrations.AddIndex(
            model_name="personalassetuse",
            index=models.Index(fields=["asset_version", "used_at"], name="pers_asset_use_ver_idx"),
        ),
    ]
