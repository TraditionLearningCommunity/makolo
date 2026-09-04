import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("social", "0001_initial"),
        ("topics", "0003_profile_open_to"),
        ("opportunities", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ActionNeed",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=220)),
                ("description", models.CharField(blank=True, max_length=600)),
                ("open_to_kind", models.CharField(choices=[("participate", "Participer"), ("collaborate", "Collaborer"), ("volunteer", "Bénévolat"), ("speak", "Intervenir / prendre la parole"), ("mentor", "Mentorat"), ("organize", "Organiser"), ("opportunities", "Recevoir des opportunités")], max_length=32)),
                ("status", models.CharField(choices=[("open", "Ouvert"), ("closed", "Fermé")], default="open", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("activity", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="action_needs", to="activities.activity")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_action_needs", to=settings.AUTH_USER_MODEL)),
                ("opportunity", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="action_needs", to="opportunities.opportunity")),
                ("owner_profile", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="owned_action_needs", to=settings.AUTH_USER_MODEL)),
                ("space", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="action_needs", to="organizations.organization")),
                ("topics", models.ManyToManyField(blank=True, related_name="action_needs", to="topics.topic")),
            ],
            options={"ordering": ["-created_at", "id"]},
        ),
        migrations.CreateModel(
            name="ProfileSolicitation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("status", models.CharField(choices=[("pending", "En attente"), ("accepted", "Acceptée"), ("declined", "Refusée"), ("cancelled", "Annulée")], default="pending", max_length=16)),
                ("message", models.CharField(blank=True, max_length=500)),
                ("responded_at", models.DateTimeField(blank=True, null=True)),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("need", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="solicitations", to="social.actionneed")),
                ("recipient_profile", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="received_profile_solicitations", to=settings.AUTH_USER_MODEL)),
                ("sent_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="sent_profile_solicitations", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at", "id"]},
        ),
        migrations.AddConstraint(
            model_name="actionneed",
            constraint=models.CheckConstraint(condition=(models.Q(("owner_profile__isnull", False), ("space__isnull", True)) | models.Q(("owner_profile__isnull", True), ("space__isnull", False))), name="social_action_need_single_owner"),
        ),
        migrations.AddIndex(model_name="actionneed", index=models.Index(fields=["owner_profile", "status", "created_at"], name="social_need_profile_idx")),
        migrations.AddIndex(model_name="actionneed", index=models.Index(fields=["space", "status", "created_at"], name="social_need_space_idx")),
        migrations.AddIndex(model_name="actionneed", index=models.Index(fields=["status", "open_to_kind"], name="social_need_open_to_idx")),
        migrations.AddConstraint(
            model_name="profilesolicitation",
            constraint=models.UniqueConstraint(condition=models.Q(("status", "pending")), fields=("need", "recipient_profile"), name="social_solicitation_unique_pending"),
        ),
        migrations.AddIndex(model_name="profilesolicitation", index=models.Index(fields=["need", "status", "created_at"], name="social_sol_need_status_idx")),
        migrations.AddIndex(model_name="profilesolicitation", index=models.Index(fields=["recipient_profile", "status", "created_at"], name="social_sol_recipient_idx")),
        migrations.AddIndex(model_name="profilesolicitation", index=models.Index(fields=["sent_by", "status", "created_at"], name="social_sol_sender_idx")),
    ]
