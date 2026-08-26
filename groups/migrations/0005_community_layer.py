import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


def preserve_legacy_visibility(apps, schema_editor):
    Group = apps.get_model("groups", "Group")
    Group.objects.filter(visibility="space").update(discoverability="space_only")
    Group.objects.filter(visibility="private").update(discoverability="hidden")


def reverse_legacy_visibility(apps, schema_editor):
    Group = apps.get_model("groups", "Group")
    Group.objects.filter(discoverability="space_only", space__isnull=False).update(
        visibility="space"
    )
    Group.objects.exclude(discoverability="space_only").update(visibility="private")


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("activities", "0003_activity_owner_profile"),
        ("groups", "0004_align_invitation_identity_constraint"),
    ]

    operations = [
        migrations.AlterField(
            model_name="group",
            name="visibility",
            field=models.CharField(
                choices=[("private", "Privé"), ("space", "Visible dans l’Espace")],
                default="private",
                help_text="Champ historique pré-T27. Utiliser discoverability pour les nouvelles surfaces.",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="group",
            name="discoverability",
            field=models.CharField(
                choices=[
                    ("listed", "Trouvable dans Makolo"),
                    ("unlisted", "Uniquement avec le lien"),
                    ("hidden", "Uniquement les personnes autorisées"),
                    ("space_only", "Dans cet Espace"),
                ],
                default="hidden",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="group",
            name="membership_policy",
            field=models.CharField(
                choices=[
                    ("open", "Tout le monde"),
                    ("request", "Sur demande"),
                    ("invite_only", "Sur invitation"),
                ],
                default="invite_only",
                max_length=16,
            ),
        ),
        migrations.RunPython(preserve_legacy_visibility, reverse_legacy_visibility),
        migrations.AlterField(
            model_name="groupmembership",
            name="source",
            field=models.CharField(
                choices=[
                    ("manual", "Ajout manuel"),
                    ("import", "Import CSV"),
                    ("invitation", "Invitation"),
                    ("claim", "Rattachement vérifié"),
                    ("self_join", "Adhésion directe"),
                    ("request", "Demande approuvée"),
                ],
                default="manual",
                max_length=16,
            ),
        ),
        migrations.CreateModel(
            name="GroupJoinRequest",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "En attente"),
                            ("approved", "Approuvée"),
                            ("rejected", "Refusée"),
                            ("cancelled", "Annulée"),
                        ],
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("message", models.CharField(blank=True, max_length=500)),
                ("requested_at", models.DateTimeField(default=timezone.now)),
                ("decided_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "decided_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="group_join_requests_decided",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="join_requests",
                        to="groups.group",
                    ),
                ),
                (
                    "profile",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="group_join_requests",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-requested_at", "id"]},
        ),
        migrations.CreateModel(
            name="ActivityGroupEligibility",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("requested", "Demandée"),
                            ("approved", "Approuvée"),
                            ("rejected", "Refusée"),
                            ("revoked", "Révoquée"),
                        ],
                        default="requested",
                        max_length=16,
                    ),
                ),
                ("requested_at", models.DateTimeField(default=timezone.now)),
                ("decided_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "activity",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="group_eligibilities",
                        to="activities.activity",
                    ),
                ),
                (
                    "decided_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="activity_group_eligibilities_decided",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="activity_eligibilities",
                        to="groups.group",
                    ),
                ),
                (
                    "requested_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="activity_group_eligibilities_requested",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-requested_at", "id"]},
        ),
        migrations.AddConstraint(
            model_name="groupjoinrequest",
            constraint=models.UniqueConstraint(
                condition=models.Q(("status", "pending")),
                fields=("group", "profile"),
                name="groups_join_pending_unique",
            ),
        ),
        migrations.AddIndex(
            model_name="groupjoinrequest",
            index=models.Index(
                fields=["group", "status", "requested_at"],
                name="groups_join_group_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="groupjoinrequest",
            index=models.Index(
                fields=["profile", "status"],
                name="groups_join_profile_status_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="activitygroupeligibility",
            constraint=models.UniqueConstraint(
                fields=("group", "activity"),
                name="groups_activity_eligibility_unique",
            ),
        ),
        migrations.AddIndex(
            model_name="activitygroupeligibility",
            index=models.Index(
                fields=["group", "status"],
                name="groups_elig_group_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="activitygroupeligibility",
            index=models.Index(
                fields=["activity", "status"],
                name="groups_elig_act_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="group",
            index=models.Index(
                fields=["discoverability", "status"],
                name="groups_group_discover_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="group",
            index=models.Index(
                fields=["membership_policy", "status"],
                name="groups_group_policy_idx",
            ),
        ),
    ]
