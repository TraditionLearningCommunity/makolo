import uuid

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


def backfill_public_identifiers(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    Organization = apps.get_model("organizations", "Organization")
    PublicIdentifier = apps.get_model("sharing", "PublicIdentifier")

    used = set()
    for user in User.objects.exclude(username="").order_by("created_at", "pk"):
        identifier = user.username.strip().lower()
        if not identifier or identifier in used:
            continue
        PublicIdentifier.objects.create(
            identifier=identifier,
            subject_kind="profile",
            profile_id=user.pk,
        )
        used.add(identifier)

    for space in Organization.objects.exclude(slug="").order_by("created_at", "pk"):
        original = space.slug.strip().lower()
        identifier = original
        if not identifier:
            continue
        if identifier in used:
            base = (identifier[:190] or "space") + "-space"
            identifier = base[:200]
            suffix = 2
            while identifier in used:
                tail = f"-{suffix}"
                identifier = f"{base[:200-len(tail)]}{tail}"
                suffix += 1
            Organization.objects.filter(pk=space.pk).update(slug=identifier)
        PublicIdentifier.objects.create(
            identifier=identifier,
            subject_kind="space",
            space_id=space.pk,
        )
        used.add(identifier)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0008_passport_public_defaults"),
        ("organizations", "0007_organization_searchable"),
        ("sharing", "0004_inbound_capture"),
    ]

    operations = [
        migrations.CreateModel(
            name="PublicIdentifier",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("identifier", models.CharField(db_index=True, max_length=200, unique=True)),
                ("subject_kind", models.CharField(choices=[("profile", "Profil"), ("space", "Space")], max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("profile", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="public_identifier_record", to="accounts.user")),
                ("space", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="public_identifier_record", to="organizations.organization")),
            ],
            options={"ordering": ["identifier"]},
        ),
        migrations.CreateModel(
            name="PassportSnapshot",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("subject_kind", models.CharField(choices=[("profile", "Profil"), ("space", "Space")], max_length=16)),
                ("public_identifier", models.CharField(max_length=200)),
                ("variant", models.CharField(max_length=24)),
                ("payload", models.JSONField()),
                ("payload_hash", models.CharField(db_index=True, max_length=64)),
                ("generated_at", models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("profile", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="passport_snapshots", to="accounts.user")),
                ("space", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="passport_snapshots", to="organizations.organization")),
            ],
            options={
                "ordering": ["-generated_at", "id"],
                "indexes": [models.Index(fields=["subject_kind", "public_identifier", "generated_at"], name="passport_subject_generated_idx")],
            },
        ),
        migrations.AddConstraint(
            model_name="publicidentifier",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("profile__isnull", False), ("space__isnull", True), ("subject_kind", "profile"))
                    | models.Q(("profile__isnull", True), ("space__isnull", False), ("subject_kind", "space"))
                ),
                name="sharing_public_identifier_one_subject",
            ),
        ),
        migrations.AddConstraint(
            model_name="passportsnapshot",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("profile__isnull", False), ("space__isnull", True), ("subject_kind", "profile"))
                    | models.Q(("profile__isnull", True), ("space__isnull", False), ("subject_kind", "space"))
                ),
                name="sharing_passport_snapshot_one_subject",
            ),
        ),
        migrations.RunPython(backfill_public_identifiers, migrations.RunPython.noop),
    ]
