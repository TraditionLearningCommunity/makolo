# Generated for Makolo Groups bounded context.

import django.db.models.deletion
import django.utils.timezone
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("organizations", "0003_team_teammembership"),
    ]

    operations = [
        migrations.CreateModel(
            name="Group",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=180)),
                ("slug", models.SlugField(max_length=220, unique=True)),
                ("description", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("active", "Actif"), ("archived", "Archivé")], default="active", max_length=16)),
                ("visibility", models.CharField(choices=[("private", "Privé"), ("space", "Visible dans l’Espace")], default="private", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="collective_groups_created", to=settings.AUTH_USER_MODEL)),
                ("owner_profile", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="personal_groups_owned", to=settings.AUTH_USER_MODEL)),
                ("space", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="collective_groups", to="organizations.organization")),
            ],
            options={"ordering": ["name", "created_at"]},
        ),
        migrations.CreateModel(
            name="GroupMembership",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("status", models.CharField(choices=[("active", "Actif"), ("suspended", "Suspendu"), ("left", "Parti"), ("removed", "Retiré")], default="active", max_length=16)),
                ("source", models.CharField(choices=[("manual", "Ajout manuel"), ("import", "Import CSV"), ("invitation", "Invitation"), ("claim", "Rattachement vérifié")], default="manual", max_length=16)),
                ("joined_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("external_reference", models.CharField(blank=True, max_length=160)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("group", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="memberships", to="groups.group")),
                ("profile", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="collective_group_membership_records", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["group__name", "profile__email"]},
        ),
        migrations.AddField(
            model_name="group",
            name="members",
            field=models.ManyToManyField(blank=True, related_name="collective_group_memberships", through="groups.GroupMembership", to=settings.AUTH_USER_MODEL),
        ),
        migrations.CreateModel(
            name="GroupInvitation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("phone", models.CharField(blank=True, max_length=40)),
                ("external_reference", models.CharField(blank=True, max_length=160)),
                ("first_name", models.CharField(blank=True, max_length=100)),
                ("last_name", models.CharField(blank=True, max_length=100)),
                ("status", models.CharField(choices=[("pending", "En attente"), ("accepted", "Acceptée"), ("revoked", "Révoquée"), ("rejected", "Refusée"), ("expired", "Expirée")], default="pending", max_length=16)),
                ("expires_at", models.DateTimeField()),
                ("token_digest", models.CharField(max_length=64, unique=True)),
                ("accepted_at", models.DateTimeField(blank=True, null=True)),
                ("rejected_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("group", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="invitations", to="groups.group")),
                ("invited_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="collective_group_invitations_sent", to=settings.AUTH_USER_MODEL)),
                ("profile", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="collective_group_invitations", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="GroupSnapshot",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=180)),
                ("member_count", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="collective_group_snapshots_created", to=settings.AUTH_USER_MODEL)),
                ("group", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="snapshots", to="groups.group")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="GroupSnapshotMember",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("external_reference", models.CharField(blank=True, max_length=160)),
                ("joined_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("profile", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="collective_group_snapshot_records", to=settings.AUTH_USER_MODEL)),
                ("snapshot", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="members", to="groups.groupsnapshot")),
            ],
            options={"ordering": ["profile__email"]},
        ),
        migrations.AddConstraint(
            model_name="group",
            constraint=models.CheckConstraint(condition=models.Q(models.Q(("owner_profile__isnull", True), ("space__isnull", False)), models.Q(("owner_profile__isnull", False), ("space__isnull", True)), _connector="OR"), name="groups_group_exactly_one_owner"),
        ),
        migrations.AddIndex(model_name="group", index=models.Index(fields=["space", "status"], name="groups_group_space_status_idx")),
        migrations.AddIndex(model_name="group", index=models.Index(fields=["owner_profile", "status"], name="groups_group_owner_status_idx")),
        migrations.AddConstraint(model_name="groupmembership", constraint=models.UniqueConstraint(fields=("group", "profile"), name="groups_membership_group_profile_unique")),
        migrations.AddConstraint(model_name="groupmembership", constraint=models.UniqueConstraint(condition=models.Q(("external_reference", ""), _negated=True), fields=("group", "external_reference"), name="groups_membership_external_ref_unique")),
        migrations.AddIndex(model_name="groupmembership", index=models.Index(fields=["group", "status"], name="groups_member_group_status_idx")),
        migrations.AddIndex(model_name="groupmembership", index=models.Index(fields=["profile", "status"], name="groups_member_prof_status_idx")),
        migrations.AddConstraint(
            model_name="groupinvitation",
            constraint=models.CheckConstraint(condition=models.Q(models.Q(("profile__isnull", False)), models.Q(("email", ""), _negated=True), models.Q(("phone", ""), _negated=True), models.Q(("external_reference", ""), _negated=True), _connector="OR"), name="groups_invitation_has_identity"),
        ),
        migrations.AddIndex(model_name="groupinvitation", index=models.Index(fields=["group", "status"], name="groups_inv_group_status_idx")),
        migrations.AddIndex(model_name="groupinvitation", index=models.Index(fields=["email", "status"], name="groups_inv_email_status_idx")),
        migrations.AddIndex(model_name="groupinvitation", index=models.Index(fields=["phone", "status"], name="groups_inv_phone_status_idx")),
        migrations.AddIndex(model_name="groupinvitation", index=models.Index(fields=["expires_at"], name="groups_inv_expires_idx")),
        migrations.AddIndex(model_name="groupsnapshot", index=models.Index(fields=["group", "created_at"], name="groups_snapshot_group_date_idx")),
        migrations.AddConstraint(model_name="groupsnapshotmember", constraint=models.UniqueConstraint(fields=("snapshot", "profile"), name="groups_snapshot_member_unique")),
        migrations.AddIndex(model_name="groupsnapshotmember", index=models.Index(fields=["snapshot", "profile"], name="groups_snap_member_lookup_idx")),
    ]
