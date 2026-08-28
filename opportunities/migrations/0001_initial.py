# Generated for T32 Opportunities & Requirement Engine.
import django.db.models.deletion
import django.utils.timezone
import uuid

from django.conf import settings
from django.db import migrations, models

import geography.validators


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("geography", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Opportunity",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("kind", models.CharField(choices=[("job", "Emploi"), ("scholarship", "Bourse"), ("internship", "Stage"), ("education", "Études"), ("grant", "Financement"), ("competition", "Concours"), ("program", "Programme"), ("volunteering", "Volontariat"), ("other", "Autre")], max_length=24)),
                ("publication_status", models.CharField(choices=[("draft", "Brouillon"), ("published", "Publiée"), ("withdrawn", "Retirée"), ("archived", "Archivée"), ("merged", "Fusionnée")], default="draft", max_length=16)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_opportunities", to=settings.AUTH_USER_MODEL)),
                ("merged_into", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="merged_duplicates", to="opportunities.opportunity")),
            ],
            options={"ordering": ["-created_at", "id"]},
        ),
        migrations.CreateModel(
            name="OpportunityRevision",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("version", models.PositiveIntegerField()),
                ("title", models.CharField(max_length=240)),
                ("summary", models.TextField(blank=True)),
                ("issuer_name", models.CharField(max_length=220)),
                ("opens_at", models.DateTimeField(blank=True, null=True)),
                ("deadline_at", models.DateTimeField(blank=True, null=True)),
                ("timezone", models.CharField(max_length=100, validators=[geography.validators.validate_timezone_name])),
                ("application_instructions", models.TextField(blank=True)),
                ("remote_allowed", models.BooleanField(blank=True, null=True)),
                ("change_summary", models.TextField(blank=True)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_opportunity_revisions", to=settings.AUTH_USER_MODEL)),
                ("opportunity", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="revisions", to="opportunities.opportunity")),
            ],
            options={"ordering": ["opportunity", "version"]},
        ),
        migrations.AddField(model_name="opportunity", name="current_revision", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to="opportunities.opportunityrevision")),
        migrations.CreateModel(
            name="OpportunitySource",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("source_type", models.CharField(choices=[("official", "Officielle"), ("trusted_partner", "Partenaire de confiance"), ("aggregator", "Agrégateur"), ("user_supplied", "Fournie par un utilisateur")], max_length=24)),
                ("source_name", models.CharField(max_length=220)),
                ("url", models.URLField(max_length=1000)),
                ("external_reference", models.CharField(blank=True, max_length=240)),
                ("is_primary", models.BooleanField(default=False)),
                ("status", models.CharField(choices=[("active", "Active"), ("changed", "Modifiée"), ("unreachable", "Inaccessible"), ("removed", "Supprimée à la source")], default="active", max_length=16)),
                ("discovered_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("last_checked_at", models.DateTimeField(blank=True, null=True)),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("opportunity", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sources", to="opportunities.opportunity")),
                ("verified_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="verified_opportunity_sources", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="OpportunitySourceCheck",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("result", models.CharField(choices=[("unchanged", "Inchangée"), ("changed", "Modifiée"), ("unreachable", "Inaccessible"), ("removed", "Supprimée")], max_length=16)),
                ("checked_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("fingerprint", models.CharField(blank=True, max_length=128)),
                ("note", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("checked_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="opportunity_source_checks", to=settings.AUTH_USER_MODEL)),
                ("source", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="checks", to="opportunities.opportunitysource")),
            ],
            options={"ordering": ["-checked_at", "-created_at", "id"]},
        ),
        migrations.CreateModel(
            name="OpportunityZone",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("role", models.CharField(choices=[("location", "Localisation"), ("eligibility", "Éligibilité")], max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("revision", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="zones", to="opportunities.opportunityrevision")),
                ("zone", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="opportunity_relations", to="geography.zone")),
            ],
        ),
        migrations.CreateModel(
            name="OpportunityRequirement",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("kind", models.CharField(choices=[("eligibility", "Éligibilité"), ("education", "Études"), ("experience", "Expérience"), ("document", "Document"), ("language", "Langue"), ("location", "Localisation"), ("age", "Âge"), ("financial", "Financier"), ("deadline", "Échéance"), ("other", "Autre")], max_length=20)),
                ("title", models.CharField(max_length=220)),
                ("description", models.TextField(blank=True)),
                ("is_mandatory", models.BooleanField(default=True)),
                ("position", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("revision", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="requirements", to="opportunities.opportunityrevision")),
            ],
            options={"ordering": ["revision", "position", "created_at", "id"]},
        ),
        migrations.CreateModel(
            name="OpportunitySave",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("opportunity", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="saves", to="opportunities.opportunity")),
                ("profile", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="opportunity_saves", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="OpportunitySubmission",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("url", models.URLField(max_length=1000)),
                ("title", models.CharField(blank=True, max_length=240)),
                ("comment", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("pending", "En attente"), ("under_review", "En revue"), ("accepted", "Acceptée"), ("rejected", "Rejetée"), ("duplicate", "Doublon")], default="pending", max_length=20)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("review_note", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("resolved_opportunity", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="resolved_submissions", to="opportunities.opportunity")),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reviewed_opportunity_submissions", to=settings.AUTH_USER_MODEL)),
                ("submitted_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="opportunity_submissions", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at", "id"]},
        ),
        migrations.AddConstraint(model_name="opportunity", constraint=models.CheckConstraint(condition=models.Q(models.Q(("merged_into__isnull", False), ("publication_status", "merged")), models.Q(models.Q(("publication_status", "merged"), _negated=True), ("merged_into__isnull", True)), _connector="OR"), name="opp_merged_target_consistent")),
        migrations.AddConstraint(model_name="opportunity", constraint=models.CheckConstraint(condition=models.Q(("merged_into__isnull", True), models.Q(("id", models.F("merged_into")), _negated=True), _connector="OR"), name="opp_merge_not_self")),
        migrations.AddIndex(model_name="opportunity", index=models.Index(fields=["publication_status", "kind"], name="opp_status_kind_idx")),
        migrations.AddIndex(model_name="opportunity", index=models.Index(fields=["current_revision"], name="opp_current_revision_idx")),
        migrations.AddIndex(model_name="opportunity", index=models.Index(fields=["merged_into"], name="opp_merged_into_idx")),
        migrations.AddConstraint(model_name="opportunityrevision", constraint=models.UniqueConstraint(fields=("opportunity", "version"), name="opp_revision_version_unique")),
        migrations.AddConstraint(model_name="opportunityrevision", constraint=models.CheckConstraint(condition=models.Q(("version__gte", 1)), name="opp_revision_version_positive")),
        migrations.AddIndex(model_name="opportunityrevision", index=models.Index(fields=["opportunity", "version"], name="opp_revision_lookup_idx")),
        migrations.AddIndex(model_name="opportunityrevision", index=models.Index(fields=["opens_at"], name="opp_revision_opens_idx")),
        migrations.AddIndex(model_name="opportunityrevision", index=models.Index(fields=["deadline_at"], name="opp_revision_deadline_idx")),
        migrations.AddConstraint(model_name="opportunitysource", constraint=models.UniqueConstraint(condition=models.Q(("is_primary", True), ("status", "active")), fields=("opportunity",), name="opp_one_primary_active_source")),
        migrations.AddIndex(model_name="opportunitysource", index=models.Index(fields=["opportunity", "status"], name="opp_source_status_idx")),
        migrations.AddIndex(model_name="opportunitysource", index=models.Index(fields=["is_primary", "status"], name="opp_source_primary_idx")),
        migrations.AddIndex(model_name="opportunitysourcecheck", index=models.Index(fields=["source", "checked_at"], name="opp_source_check_idx")),
        migrations.AddConstraint(model_name="opportunityzone", constraint=models.UniqueConstraint(fields=("revision", "zone", "role"), name="opp_zone_revision_role_unique")),
        migrations.AddIndex(model_name="opportunityzone", index=models.Index(fields=["zone", "role"], name="opp_zone_role_idx")),
        migrations.AddIndex(model_name="opportunityrequirement", index=models.Index(fields=["revision", "position"], name="opp_req_revision_pos_idx")),
        migrations.AddIndex(model_name="opportunityrequirement", index=models.Index(fields=["revision", "kind"], name="opp_req_revision_kind_idx")),
        migrations.AddConstraint(model_name="opportunitysave", constraint=models.UniqueConstraint(fields=("profile", "opportunity"), name="opp_save_profile_unique")),
        migrations.AddIndex(model_name="opportunitysave", index=models.Index(fields=["profile", "created_at"], name="opp_save_profile_idx")),
        migrations.AddIndex(model_name="opportunitysubmission", index=models.Index(fields=["status", "created_at"], name="opp_submission_status_idx")),
    ]
