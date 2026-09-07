# Generated manually for the action-network convergence.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


def normalize_closed_needs(apps, schema_editor):
    ActionNeed = apps.get_model("social", "ActionNeed")
    ActionNeed.objects.filter(status="closed").update(status="cancelled")


class Migration(migrations.Migration):

    dependencies = [
        ("activities", "0004_occurrence_temporal_schedule"),
        ("social", "0002_bilateral_network"),
        ("topics", "0004_space_open_to_and_match_kinds"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveIndex(model_name="actionneed", name="social_need_open_to_idx"),
        migrations.RemoveConstraint(model_name="profilesolicitation", name="social_solicitation_unique_pending"),
        migrations.RemoveIndex(model_name="profilesolicitation", name="social_sol_need_status_idx"),
        migrations.RemoveIndex(model_name="profilesolicitation", name="social_sol_recipient_idx"),
        migrations.RemoveIndex(model_name="profilesolicitation", name="social_sol_sender_idx"),
        migrations.RenameField(model_name="actionneed", old_name="open_to_kind", new_name="match_kind"),
        migrations.RenameModel(old_name="ProfileSolicitation", new_name="ActionProposal"),
        migrations.RenameField(model_name="actionproposal", old_name="recipient_profile", new_name="candidate_profile"),
        migrations.RenameField(model_name="actionproposal", old_name="sent_by", new_name="initiated_by"),
        migrations.RunPython(normalize_closed_needs, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="actionneed",
            name="match_kind",
            field=models.CharField(choices=[("participate", "Participer"), ("collaborate", "Collaborer"), ("volunteer", "Bénévolat"), ("speak", "Intervenir / prendre la parole"), ("mentor", "Mentorat"), ("organize", "Organiser"), ("provide_service", "Fournir une prestation"), ("partner", "Partenariat"), ("sponsor", "Sponsoring"), ("opportunities", "Recevoir des opportunités")], max_length=32),
        ),
        migrations.AlterField(
            model_name="actionneed",
            name="status",
            field=models.CharField(choices=[("draft", "Brouillon"), ("open", "Ouvert"), ("paused", "En pause"), ("filled", "Satisfait"), ("cancelled", "Annulé"), ("expired", "Expiré")], default="open", max_length=16),
        ),
        migrations.AddField(
            model_name="actionneed",
            name="candidate_kind",
            field=models.CharField(choices=[("profile", "Profil"), ("space", "Espace"), ("either", "Profil ou Espace")], default="profile", max_length=16),
        ),
        migrations.AddField(
            model_name="actionneed",
            name="visibility",
            field=models.CharField(choices=[("private", "Privé"), ("matched", "Candidats compatibles"), ("public", "Public")], default="private", max_length=16),
        ),
        migrations.AddField(
            model_name="actionneed",
            name="intake_policy",
            field=models.CharField(choices=[("invite_only", "Sur invitation"), ("matched", "Candidats compatibles"), ("open", "Ouvert aux propositions")], default="invite_only", max_length=16),
        ),
        migrations.AddField(model_name="actionneed", name="target_count", field=models.PositiveIntegerField(blank=True, null=True)),
        migrations.AddField(model_name="actionneed", name="opens_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="actionneed", name="closes_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="actionneed", name="needed_from", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="actionneed", name="needed_until", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(
            model_name="actionneed",
            name="occurrence",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="action_needs", to="activities.occurrence"),
        ),
        migrations.AddConstraint(model_name="actionneed", constraint=models.CheckConstraint(condition=models.Q(("target_count__isnull", True), ("target_count__gt", 0), _connector="OR"), name="social_action_need_target_positive")),
        migrations.AddConstraint(model_name="actionneed", constraint=models.CheckConstraint(condition=models.Q(("closes_at__isnull", True), ("opens_at__isnull", True), ("closes_at__gte", models.F("opens_at")), _connector="OR"), name="social_action_need_intake_window")),
        migrations.AddConstraint(model_name="actionneed", constraint=models.CheckConstraint(condition=models.Q(("needed_until__isnull", True), ("needed_from__isnull", True), ("needed_until__gte", models.F("needed_from")), _connector="OR"), name="social_action_need_needed_window")),
        migrations.AddIndex(model_name="actionneed", index=models.Index(fields=["activity", "status"], name="social_need_activity_idx")),
        migrations.AddIndex(model_name="actionneed", index=models.Index(fields=["occurrence", "status"], name="social_need_occurrence_idx")),
        migrations.AddIndex(model_name="actionneed", index=models.Index(fields=["status", "match_kind"], name="social_need_match_idx")),
        migrations.AddIndex(model_name="actionneed", index=models.Index(fields=["status", "visibility", "intake_policy"], name="social_need_discovery_idx")),
        migrations.AddIndex(model_name="actionneed", index=models.Index(fields=["closes_at"], name="social_need_closes_idx")),
        migrations.AlterField(model_name="actionproposal", name="need", field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="proposals", to="social.actionneed")),
        migrations.AlterField(model_name="actionproposal", name="candidate_profile", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="action_proposals_as_candidate", to=settings.AUTH_USER_MODEL)),
        migrations.AlterField(model_name="actionproposal", name="initiated_by", field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="initiated_action_proposals", to=settings.AUTH_USER_MODEL)),
        migrations.AlterField(model_name="actionproposal", name="status", field=models.CharField(choices=[("pending", "En attente"), ("accepted", "Acceptée"), ("declined", "Refusée"), ("cancelled", "Annulée"), ("expired", "Expirée")], default="pending", max_length=16)),
        migrations.AddField(model_name="actionproposal", name="direction", field=models.CharField(choices=[("owner_to_candidate", "Invitation du propriétaire"), ("candidate_to_owner", "Proposition du candidat")], default="owner_to_candidate", max_length=24)),
        migrations.AddField(model_name="actionproposal", name="candidate_space", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="action_proposals_as_candidate", to="organizations.organization")),
        migrations.AddField(model_name="actionproposal", name="response_message", field=models.CharField(blank=True, max_length=500)),
        migrations.AddField(model_name="actionproposal", name="responded_by", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="responded_action_proposals", to=settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name="actionproposal", name="cancelled_by", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="cancelled_action_proposals", to=settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name="actionproposal", name="expires_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="actionproposal", name="client_reference", field=models.CharField(blank=True, max_length=80, null=True)),
        migrations.AddConstraint(model_name="actionproposal", constraint=models.CheckConstraint(condition=models.Q(models.Q(("candidate_profile__isnull", False), ("candidate_space__isnull", True)), models.Q(("candidate_profile__isnull", True), ("candidate_space__isnull", False)), _connector="OR"), name="social_action_proposal_single_candidate")),
        migrations.AddConstraint(model_name="actionproposal", constraint=models.UniqueConstraint(condition=models.Q(("candidate_profile__isnull", False), ("status__in", ["pending", "accepted"])), fields=("need", "candidate_profile"), name="social_prop_profile_active_unique")),
        migrations.AddConstraint(model_name="actionproposal", constraint=models.UniqueConstraint(condition=models.Q(("candidate_space__isnull", False), ("status__in", ["pending", "accepted"])), fields=("need", "candidate_space"), name="social_prop_space_active_unique")),
        migrations.AddConstraint(model_name="actionproposal", constraint=models.UniqueConstraint(condition=models.Q(("client_reference__isnull", False)), fields=("client_reference",), name="social_prop_client_ref_unique")),
        migrations.AddIndex(model_name="actionproposal", index=models.Index(fields=["need", "status", "created_at"], name="social_prop_need_status_idx")),
        migrations.AddIndex(model_name="actionproposal", index=models.Index(fields=["candidate_profile", "status", "created_at"], name="social_prop_profile_idx")),
        migrations.AddIndex(model_name="actionproposal", index=models.Index(fields=["candidate_space", "status", "created_at"], name="social_prop_space_idx")),
        migrations.AddIndex(model_name="actionproposal", index=models.Index(fields=["initiated_by", "created_at"], name="social_prop_initiator_idx")),
        migrations.AddIndex(model_name="actionproposal", index=models.Index(fields=["expires_at"], name="social_prop_expires_idx")),
        migrations.CreateModel(
            name="ActionNetworkBlock",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("blocked_profile", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="action_network_blocks_received_as_profile", to=settings.AUTH_USER_MODEL)),
                ("blocked_space", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="action_network_blocks_received_as_space", to="organizations.organization")),
                ("blocker_profile", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="action_network_blocks_created_as_profile", to=settings.AUTH_USER_MODEL)),
                ("blocker_space", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="action_network_blocks_created_as_space", to="organizations.organization")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_action_network_blocks", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at", "id"]},
        ),
        migrations.AddConstraint(model_name="actionnetworkblock", constraint=models.CheckConstraint(condition=models.Q(models.Q(("blocker_profile__isnull", False), ("blocker_space__isnull", True)), models.Q(("blocker_profile__isnull", True), ("blocker_space__isnull", False)), _connector="OR"), name="social_block_single_blocker")),
        migrations.AddConstraint(model_name="actionnetworkblock", constraint=models.CheckConstraint(condition=models.Q(models.Q(("blocked_profile__isnull", False), ("blocked_space__isnull", True)), models.Q(("blocked_profile__isnull", True), ("blocked_space__isnull", False)), _connector="OR"), name="social_block_single_blocked")),
        migrations.AddConstraint(model_name="actionnetworkblock", constraint=models.UniqueConstraint(condition=models.Q(("blocked_profile__isnull", False), ("blocker_profile__isnull", False)), fields=("blocker_profile", "blocked_profile"), name="social_block_profile_profile_unique")),
        migrations.AddConstraint(model_name="actionnetworkblock", constraint=models.UniqueConstraint(condition=models.Q(("blocked_space__isnull", False), ("blocker_profile__isnull", False)), fields=("blocker_profile", "blocked_space"), name="social_block_profile_space_unique")),
        migrations.AddConstraint(model_name="actionnetworkblock", constraint=models.UniqueConstraint(condition=models.Q(("blocked_profile__isnull", False), ("blocker_space__isnull", False)), fields=("blocker_space", "blocked_profile"), name="social_block_space_profile_unique")),
        migrations.AddConstraint(model_name="actionnetworkblock", constraint=models.UniqueConstraint(condition=models.Q(("blocked_space__isnull", False), ("blocker_space__isnull", False)), fields=("blocker_space", "blocked_space"), name="social_block_space_space_unique")),
        migrations.AddIndex(model_name="actionnetworkblock", index=models.Index(fields=["blocker_profile", "blocked_profile"], name="social_block_pp_idx")),
        migrations.AddIndex(model_name="actionnetworkblock", index=models.Index(fields=["blocker_profile", "blocked_space"], name="social_block_ps_idx")),
        migrations.AddIndex(model_name="actionnetworkblock", index=models.Index(fields=["blocker_space", "blocked_profile"], name="social_block_sp_idx")),
        migrations.AddIndex(model_name="actionnetworkblock", index=models.Index(fields=["blocker_space", "blocked_space"], name="social_block_ss_idx")),
    ]
