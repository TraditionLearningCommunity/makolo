import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("activities", "0003_activity_owner_profile"),
        ("opportunities", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ShareEnvelope",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("subject_type", models.CharField(choices=[("activity", "Activity"), ("opportunity", "Opportunity")], max_length=24)),
                ("intent", models.CharField(choices=[("view", "Voir"), ("participate", "Participer"), ("start_journey", "Commencer")], default="view", max_length=24)),
                ("status", models.CharField(choices=[("active", "Actif"), ("revoked", "Révoqué"), ("expired", "Expiré")], default="active", max_length=16)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="share_envelopes_created", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at", "id"]},
        ),
        migrations.CreateModel(
            name="ShareLink",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("token_hash", models.CharField(editable=False, max_length=64, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("envelope", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="link", to="sharing.shareenvelope")),
            ],
            options={"ordering": ["-created_at", "id"]},
        ),
        migrations.CreateModel(
            name="ActivityShareSubject",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("activity", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="share_subjects", to="activities.activity")),
                ("envelope", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="activity_subject", to="sharing.shareenvelope")),
                ("occurrence", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="share_subjects", to="activities.occurrence")),
            ],
        ),
        migrations.CreateModel(
            name="OpportunityShareSubject",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("envelope", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="opportunity_subject", to="sharing.shareenvelope")),
                ("opportunity_revision", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="share_subjects", to="opportunities.opportunityrevision")),
            ],
        ),
        migrations.AddIndex(
            model_name="shareenvelope",
            index=models.Index(fields=["status", "created_at"], name="sharing_env_status_created_idx"),
        ),
        migrations.AddIndex(
            model_name="shareenvelope",
            index=models.Index(fields=["expires_at"], name="sharing_env_expires_idx"),
        ),
    ]
