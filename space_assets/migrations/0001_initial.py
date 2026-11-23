import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import journeys.storage
import space_assets.models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("organizations", "0007_organization_searchable"),
        ("journeys", "0003_services_core_journey_collaboration"),
    ]

    operations = [
        migrations.CreateModel(
            name="SpaceDocument",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("title", models.CharField(max_length=220)),
                ("kind", models.CharField(max_length=32, choices=[("cv", "CV"), ("cover_letter", "Lettre de motivation"), ("certificate", "Certificat"), ("transcript", "Relevé"), ("recommendation", "Recommandation"), ("identity_document", "Document d’identité"), ("form", "Formulaire"), ("payment_receipt", "Reçu de paiement"), ("other", "Autre")], default="other")),
                ("visibility", models.CharField(max_length=16, choices=[("internal", "Équipe autorisée"), ("restricted", "Confidentiel")], default="restricted")),
                ("archived_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("archived_by", models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT, null=True, blank=True, related_name="institutional_documents_archived")),
                ("created_by", models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT, related_name="institutional_documents_created")),
                ("space", models.ForeignKey(to="organizations.organization", on_delete=django.db.models.deletion.PROTECT, related_name="institutional_documents")),
            ],
            options={
                "ordering": ("-updated_at", "id"),
                "indexes": [models.Index(fields=("space", "archived_at"), name="sp_doc_space_arch_idx")],
            },
        ),
        migrations.CreateModel(
            name="SpaceDocumentVersion",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("version", models.PositiveIntegerField()),
                ("file", models.FileField(storage=journeys.storage.PrivateArtifactStorage(), upload_to=space_assets.models.space_document_file_path, max_length=500)),
                ("mime_type", models.CharField(max_length=180)),
                ("size", models.PositiveBigIntegerField()),
                ("content_hash", models.CharField(max_length=64)),
                ("issued_at", models.DateField(null=True, blank=True)),
                ("expires_at", models.DateField(null=True, blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT, related_name="institutional_document_versions_created")),
                ("document", models.ForeignKey(to="space_assets.spacedocument", on_delete=django.db.models.deletion.PROTECT, related_name="versions")),
                ("supersedes", models.OneToOneField(to="space_assets.spacedocumentversion", on_delete=django.db.models.deletion.PROTECT, null=True, blank=True, related_name="superseded_by")),
            ],
            options={
                "ordering": ("-version", "id"),
                "constraints": [
                    models.UniqueConstraint(fields=("document", "version"), name="sp_doc_version_unique"),
                    models.CheckConstraint(condition=models.Q(version__gte=1), name="sp_doc_version_positive"),
                ],
            },
        ),
        migrations.CreateModel(
            name="SpaceDocumentUse",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("used_at", models.DateTimeField(auto_now_add=True)),
                ("document_version", models.ForeignKey(to="space_assets.spacedocumentversion", on_delete=django.db.models.deletion.PROTECT, related_name="uses")),
                ("journey_artifact", models.OneToOneField(to="journeys.journeyartifact", on_delete=django.db.models.deletion.PROTECT, related_name="institutional_document_use")),
                ("used_by", models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT, related_name="institutional_document_uses")),
            ],
            options={"ordering": ("-used_at", "id")},
        ),
    ]
