# Generated manually for contextual Activity/Occurrence involvements.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("activities", "0004_occurrence_temporal_schedule"),
        ("social", "0003_action_network_convergence"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ActivityInvolvement",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("external_kind", models.CharField(blank=True, choices=[("person", "Personne externe"), ("space", "Organisation externe")], default="", max_length=16)),
                ("external_display_name", models.CharField(blank=True, max_length=220)),
                ("contextual_title", models.CharField(blank=True, max_length=220)),
                ("short_description", models.CharField(blank=True, max_length=500)),
                ("visibility", models.CharField(choices=[("context", "Contexte autorisé"), ("public", "Public")], default="context", max_length=16)),
                ("confirmation_basis", models.CharField(choices=[("profile_confirmed", "Confirmé par le Profile"), ("space_confirmed", "Confirmé par le Space"), ("organizer_declared", "Annoncé par l'organisateur")], max_length=24)),
                ("confirmed_at", models.DateTimeField(blank=True, null=True)),
                ("status", models.CharField(choices=[("active", "Actif"), ("removed", "Retiré")], default="active", max_length=16)),
                ("removed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("activity", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="involvements", to="activities.activity")),
                ("occurrence", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="involvements", to="activities.occurrence")),
                ("profile", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="activity_involvements", to=settings.AUTH_USER_MODEL)),
                ("space", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="activity_involvements", to="organizations.organization")),
                ("source_proposal", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="activity_involvement", to="social.actionproposal")),
                ("recorded_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="recorded_activity_involvements", to=settings.AUTH_USER_MODEL)),
                ("confirmed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="confirmed_activity_involvements", to=settings.AUTH_USER_MODEL)),
                ("removed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="removed_activity_involvements", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["activity_id", "occurrence_id", "created_at", "id"]},
        ),
        migrations.AddConstraint(
            model_name="activityinvolvement",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("external_kind", ""), ("profile__isnull", False), ("space__isnull", True)),
                    models.Q(("external_kind", ""), ("profile__isnull", True), ("space__isnull", False)),
                    models.Q(("external_kind__in", ["person", "space"]), ("profile__isnull", True), ("space__isnull", True)),
                    _connector="OR",
                ),
                name="activities_involvement_single_subject",
            ),
        ),
        migrations.AddIndex(model_name="activityinvolvement", index=models.Index(fields=["activity", "status", "visibility"], name="activities_inv_activity_idx")),
        migrations.AddIndex(model_name="activityinvolvement", index=models.Index(fields=["occurrence", "status", "visibility"], name="activities_inv_occ_idx")),
        migrations.AddIndex(model_name="activityinvolvement", index=models.Index(fields=["profile", "activity"], name="activities_inv_profile_idx")),
        migrations.AddIndex(model_name="activityinvolvement", index=models.Index(fields=["space", "activity"], name="activities_inv_space_idx")),
        migrations.CreateModel(
            name="ActivityInvolvementFunction",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("kind", models.CharField(choices=[("performer", "Artiste / performer"), ("speaker", "Intervenant"), ("moderator", "Modération"), ("facilitator", "Facilitation"), ("guest", "Invité"), ("mentor", "Mentor"), ("jury", "Jury"), ("volunteer", "Bénévole"), ("staff", "Équipe"), ("provider", "Prestataire"), ("partner", "Partenaire"), ("sponsor", "Sponsor"), ("co_organizer", "Co-organisateur"), ("other", "Autre")], max_length=24)),
                ("label", models.CharField(blank=True, max_length=180)),
                ("presentation_tier", models.PositiveSmallIntegerField(default=3)),
                ("presentation_order", models.PositiveSmallIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("involvement", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="functions", to="activities.activityinvolvement")),
            ],
            options={"ordering": ["presentation_tier", "presentation_order", "kind", "id"]},
        ),
        migrations.AddConstraint(model_name="activityinvolvementfunction", constraint=models.UniqueConstraint(fields=("involvement", "kind"), name="activities_inv_function_unique")),
        migrations.AddConstraint(model_name="activityinvolvementfunction", constraint=models.CheckConstraint(condition=models.Q(("presentation_tier__gte", 1), ("presentation_tier__lte", 5)), name="activities_inv_tier_valid")),
        migrations.AddIndex(model_name="activityinvolvementfunction", index=models.Index(fields=["kind", "presentation_tier"], name="activities_inv_func_kind_idx")),
        migrations.CreateModel(
            name="ActivityInvolvementNeedConfig",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("function_kind", models.CharField(choices=[("performer", "Artiste / performer"), ("speaker", "Intervenant"), ("moderator", "Modération"), ("facilitator", "Facilitation"), ("guest", "Invité"), ("mentor", "Mentor"), ("jury", "Jury"), ("volunteer", "Bénévole"), ("staff", "Équipe"), ("provider", "Prestataire"), ("partner", "Partenaire"), ("sponsor", "Sponsor"), ("co_organizer", "Co-organisateur"), ("other", "Autre")], max_length=24)),
                ("function_label", models.CharField(blank=True, max_length=180)),
                ("result_visibility", models.CharField(choices=[("context", "Contexte autorisé"), ("public", "Public")], default="context", max_length=16)),
                ("presentation_tier", models.PositiveSmallIntegerField(default=3)),
                ("presentation_order", models.PositiveSmallIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("need", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="activity_involvement_config", to="social.actionneed")),
            ],
        ),
        migrations.AddConstraint(model_name="activityinvolvementneedconfig", constraint=models.CheckConstraint(condition=models.Q(("presentation_tier__gte", 1), ("presentation_tier__lte", 5)), name="activities_inv_need_tier_valid")),
    ]
