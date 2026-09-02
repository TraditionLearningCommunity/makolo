import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("activities", "0003_activity_owner_profile"),
        ("groups", "0005_community_layer"),
        ("organizations", "0004_profilefollow"),
    ]

    operations = [
        migrations.CreateModel(
            name="Contribution",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("kind", models.CharField(choices=[("update", "Mise à jour officielle"), ("tip", "Conseil"), ("field_note", "Note terrain"), ("discussion", "Discussion"), ("share", "Partage d'Activity")], max_length=24)),
                ("body", models.TextField(blank=True, max_length=2400)),
                ("visibility", models.CharField(choices=[("public", "Publique"), ("context", "Contexte autorisé")], default="context", max_length=16)),
                ("status", models.CharField(choices=[("published", "Publiée"), ("hidden", "Masquée"), ("removed", "Retirée")], default="published", max_length=16)),
                ("edited_at", models.DateTimeField(blank=True, null=True)),
                ("moderated_at", models.DateTimeField(blank=True, null=True)),
                ("moderation_reason", models.CharField(blank=True, max_length=280)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("activity", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="social_contributions", to="activities.activity")),
                ("author_profile", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="social_contributions", to=settings.AUTH_USER_MODEL)),
                ("group", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="social_contributions", to="groups.group")),
                ("moderated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="moderated_social_contributions", to=settings.AUTH_USER_MODEL)),
                ("occurrence", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="social_contributions", to="activities.occurrence")),
                ("parent", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="replies", to="social.contribution")),
                ("space", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="social_contributions", to="organizations.organization")),
            ],
            options={"ordering": ["-created_at", "id"]},
        ),
        migrations.AddConstraint(
            model_name="contribution",
            constraint=models.CheckConstraint(
                condition=(models.Q(space__isnull=False) | models.Q(group__isnull=False) | models.Q(activity__isnull=False) | models.Q(occurrence__isnull=False)),
                name="social_contribution_has_context",
            ),
        ),
        migrations.AddIndex(model_name="contribution", index=models.Index(fields=["status", "created_at"], name="social_status_created_idx")),
        migrations.AddIndex(model_name="contribution", index=models.Index(fields=["group", "status", "created_at"], name="social_group_stream_idx")),
        migrations.AddIndex(model_name="contribution", index=models.Index(fields=["activity", "status", "created_at"], name="social_activity_stream_idx")),
        migrations.AddIndex(model_name="contribution", index=models.Index(fields=["space", "status", "created_at"], name="social_space_stream_idx")),
        migrations.AddIndex(model_name="contribution", index=models.Index(fields=["author_profile", "created_at"], name="social_author_created_idx")),
    ]
