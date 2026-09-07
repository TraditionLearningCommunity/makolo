import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("conversations", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("groups", "0005_community_layer"),
        ("activities", "0005_activity_involvements"),
        ("social", "0003_action_network_convergence"),
    ]

    operations = [
        migrations.CreateModel(
            name="ConversationAudienceSet",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("label", models.CharField(max_length=160)),
                ("status", models.CharField(choices=[("active", "Active"), ("retired", "Retirée")], default="active", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("conversation", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="audience_sets", to="conversations.conversation")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_conversation_audiences", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["conversation_id", "label", "id"]},
        ),
        migrations.CreateModel(
            name="ConversationAudienceRule",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("operation", models.CharField(choices=[("include", "Inclure"), ("exclude", "Exclure")], default="include", max_length=16)),
                ("kind", models.CharField(choices=[("all_conversation_viewers", "Toutes les personnes légitimes"), ("explicit_profile", "Profile explicite"), ("conversation_participants", "Participations explicites"), ("conversation_managers", "Responsables de la Conversation"), ("group_members", "Membres d’un Groupe"), ("occurrence_participants", "Participants d’une Occurrence"), ("activity_involvement_function", "Fonction dans une Activity"), ("action_proposal_parties", "Parties d’une proposition")], max_length=40)),
                ("involvement_function_kind", models.CharField(blank=True, choices=[("performer", "Artiste / performer"), ("speaker", "Intervenant"), ("moderator", "Modération"), ("facilitator", "Facilitation"), ("guest", "Invité"), ("mentor", "Mentor"), ("jury", "Jury"), ("volunteer", "Bénévole"), ("staff", "Équipe"), ("provider", "Prestataire"), ("partner", "Partenaire"), ("sponsor", "Sponsor"), ("co_organizer", "Co-organisateur"), ("other", "Autre")], default="", max_length=24)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("action_proposal", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="conversation_audience_rules", to="social.actionproposal")),
                ("activity", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="conversation_audience_rules", to="activities.activity")),
                ("audience_set", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="rules", to="conversations.conversationaudienceset")),
                ("group", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="conversation_audience_rules", to="groups.group")),
                ("occurrence", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="conversation_audience_rules", to="activities.occurrence")),
                ("profile", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="conversation_audience_rules", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["audience_set_id", "operation", "kind", "id"]},
        ),
        migrations.AddConstraint(model_name="conversationaudienceset", constraint=models.UniqueConstraint(fields=("conversation", "label"), name="conv_audience_label_unique")),
        migrations.AddIndex(model_name="conversationaudienceset", index=models.Index(fields=["conversation", "status"], name="conv_aud_conv_status_idx")),
        migrations.AddConstraint(
            model_name="conversationaudiencerule",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(kind="all_conversation_viewers", profile__isnull=True, group__isnull=True, activity__isnull=True, occurrence__isnull=True, action_proposal__isnull=True, involvement_function_kind="")
                    | models.Q(kind="explicit_profile", profile__isnull=False, group__isnull=True, activity__isnull=True, occurrence__isnull=True, action_proposal__isnull=True, involvement_function_kind="")
                    | models.Q(kind="conversation_participants", profile__isnull=True, group__isnull=True, activity__isnull=True, occurrence__isnull=True, action_proposal__isnull=True, involvement_function_kind="")
                    | models.Q(kind="conversation_managers", profile__isnull=True, group__isnull=True, activity__isnull=True, occurrence__isnull=True, action_proposal__isnull=True, involvement_function_kind="")
                    | models.Q(kind="group_members", profile__isnull=True, group__isnull=False, activity__isnull=True, occurrence__isnull=True, action_proposal__isnull=True, involvement_function_kind="")
                    | models.Q(kind="occurrence_participants", profile__isnull=True, group__isnull=True, activity__isnull=True, occurrence__isnull=False, action_proposal__isnull=True, involvement_function_kind="")
                    | (models.Q(kind="activity_involvement_function", profile__isnull=True, group__isnull=True, activity__isnull=False, action_proposal__isnull=True) & ~models.Q(involvement_function_kind=""))
                    | models.Q(kind="action_proposal_parties", profile__isnull=True, group__isnull=True, activity__isnull=True, occurrence__isnull=True, action_proposal__isnull=False, involvement_function_kind="")
                ),
                name="conv_audience_rule_shape_valid",
            ),
        ),
        migrations.AddIndex(model_name="conversationaudiencerule", index=models.Index(fields=["audience_set", "operation", "kind"], name="conv_aud_rule_lookup_idx")),
        migrations.AddIndex(model_name="conversationaudiencerule", index=models.Index(fields=["group", "kind"], name="conv_aud_rule_group_idx")),
        migrations.AddIndex(model_name="conversationaudiencerule", index=models.Index(fields=["occurrence", "kind"], name="conv_aud_rule_occ_idx")),
        migrations.AddIndex(model_name="conversationaudiencerule", index=models.Index(fields=["activity", "kind"], name="conv_aud_rule_activity_idx")),
    ]
