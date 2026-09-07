import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("organizations", "0004_profilefollow"),
        ("groups", "0005_community_layer"),
        ("activities", "0005_activity_involvements"),
        ("objectives", "0004_project_projectdossierlink"),
        ("journeys", "0003_services_core_journey_collaboration"),
        ("social", "0003_action_network_convergence"),
    ]

    operations = [
        migrations.CreateModel(
            name="Conversation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title_override", models.CharField(blank=True, max_length=220)),
                ("purpose", models.CharField(blank=True, max_length=500)),
                ("lifecycle", models.CharField(choices=[("draft", "Brouillon"), ("open", "Ouverte"), ("closed", "Fermée"), ("archived", "Archivée")], default="draft", max_length=16)),
                ("mode_preset", models.CharField(choices=[("announcements", "Annonces"), ("guided", "Guidée"), ("mixed", "Mixte"), ("free", "Discussion libre")], default="mixed", max_length=24)),
                ("entry_mode", models.CharField(choices=[("derived", "Accès dérivé"), ("join", "Rejoindre"), ("request", "Demander à rejoindre"), ("invite_only", "Sur invitation"), ("direct_consent", "Consentement direct")], default="derived", max_length=24)),
                ("discoverability", models.CharField(choices=[("hidden", "Masquée"), ("eligible", "Visible aux personnes éligibles")], default="hidden", max_length=16)),
                ("history_policy", models.CharField(choices=[("context_history", "Historique du contexte"), ("from_join", "Depuis l’entrée")], default="context_history", max_length=24)),
                ("client_reference", models.CharField(blank=True, max_length=80, null=True)),
                ("opened_at", models.DateTimeField(blank=True, null=True)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("archived_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_action_conversations", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-updated_at", "id"]},
        ),
        migrations.CreateModel(
            name="ConversationContext",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("kind", models.CharField(choices=[("space", "Espace"), ("group", "Groupe"), ("activity", "Activité"), ("occurrence", "Occurrence"), ("dossier", "Dossier"), ("project", "Projet"), ("journey", "Démarche"), ("action_proposal", "Proposition"), ("direct", "Directe")], max_length=24)),
                ("purpose_key", models.SlugField(default="coordination", max_length=80)),
                ("separation_reason", models.CharField(blank=True, max_length=220)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("action_proposal", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="action_conversation_contexts", to="social.actionproposal")),
                ("activity", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="action_conversation_contexts", to="activities.activity")),
                ("conversation", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="context", to="conversations.conversation")),
                ("direct_profile_a", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="direct_conversation_contexts_a", to=settings.AUTH_USER_MODEL)),
                ("direct_profile_b", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="direct_conversation_contexts_b", to=settings.AUTH_USER_MODEL)),
                ("dossier", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="action_conversation_contexts", to="objectives.dossier")),
                ("group", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="action_conversation_contexts", to="groups.group")),
                ("journey", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="action_conversation_contexts", to="journeys.journey")),
                ("occurrence", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="action_conversation_contexts", to="activities.occurrence")),
                ("project", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="action_conversation_contexts", to="objectives.project")),
                ("space", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="action_conversation_contexts", to="organizations.organization")),
            ],
        ),
        migrations.CreateModel(
            name="ConversationPolicy",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("preset", models.CharField(choices=[("announcements", "Annonces"), ("guided", "Guidée"), ("mixed", "Mixte"), ("free", "Discussion libre")], default="mixed", max_length=24)),
                ("allow_information", models.BooleanField(default=True)),
                ("allow_questions", models.BooleanField(default=True)),
                ("allow_confirmations", models.BooleanField(default=True)),
                ("allow_polls", models.BooleanField(default=True)),
                ("allow_requests", models.BooleanField(default=True)),
                ("allow_form_requests", models.BooleanField(default=True)),
                ("allow_free_exchange", models.BooleanField(default=True)),
                ("allow_voice", models.BooleanField(default=True)),
                ("allow_images", models.BooleanField(default=True)),
                ("allow_video", models.BooleanField(default=False)),
                ("allow_documents", models.BooleanField(default=True)),
                ("allow_links", models.BooleanField(default=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("conversation", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="policy", to="conversations.conversation")),
            ],
        ),
        migrations.CreateModel(
            name="ConversationParticipation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("source", models.CharField(choices=[("manual", "Ajout explicite"), ("join", "Rejoint"), ("request", "Demande approuvée"), ("invitation", "Invitation acceptée"), ("direct_consent", "Consentement direct")], default="manual", max_length=24)),
                ("status", models.CharField(choices=[("active", "Active"), ("left", "Quittée"), ("removed", "Retirée")], default="active", max_length=16)),
                ("joined_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("left_at", models.DateTimeField(blank=True, null=True)),
                ("removed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("conversation", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="explicit_participations", to="conversations.conversation")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_conversation_participations", to=settings.AUTH_USER_MODEL)),
                ("profile", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="action_conversation_participations", to=settings.AUTH_USER_MODEL)),
                ("represented_space", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="represented_conversation_participations", to="organizations.organization")),
            ],
        ),
        migrations.CreateModel(
            name="ConversationInvitation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("status", models.CharField(choices=[("pending", "En attente"), ("accepted", "Acceptée"), ("declined", "Refusée"), ("expired", "Expirée"), ("cancelled", "Annulée")], default="pending", max_length=16)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("responded_at", models.DateTimeField(blank=True, null=True)),
                ("client_reference", models.CharField(blank=True, max_length=80, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("conversation", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="invitations", to="conversations.conversation")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_conversation_invitations", to=settings.AUTH_USER_MODEL)),
                ("invitee", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="conversation_invitations", to=settings.AUTH_USER_MODEL)),
                ("represented_space", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="conversation_invitations", to="organizations.organization")),
            ],
        ),
        migrations.CreateModel(
            name="ConversationJoinRequest",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("status", models.CharField(choices=[("pending", "En attente"), ("approved", "Approuvée"), ("rejected", "Refusée"), ("cancelled", "Annulée")], default="pending", max_length=16)),
                ("responded_at", models.DateTimeField(blank=True, null=True)),
                ("client_reference", models.CharField(blank=True, max_length=80, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("conversation", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="join_requests", to="conversations.conversation")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_conversation_join_requests", to=settings.AUTH_USER_MODEL)),
                ("represented_space", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="conversation_join_requests", to="organizations.organization")),
                ("requester", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="conversation_join_requests", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="ConversationUserState",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("last_opened_at", models.DateTimeField(blank=True, null=True)),
                ("muted_at", models.DateTimeField(blank=True, null=True)),
                ("muted_until", models.DateTimeField(blank=True, null=True)),
                ("hidden_at", models.DateTimeField(blank=True, null=True)),
                ("archived_at", models.DateTimeField(blank=True, null=True)),
                ("pinned_at", models.DateTimeField(blank=True, null=True)),
                ("revisit_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("conversation", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="user_states", to="conversations.conversation")),
                ("profile", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="conversation_user_states", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name="conversation",
            constraint=models.UniqueConstraint(condition=models.Q(("client_reference__isnull", False)), fields=("client_reference",), name="conv_client_ref_unique"),
        ),
        migrations.AddIndex(model_name="conversation", index=models.Index(fields=["lifecycle", "updated_at"], name="conv_lifecycle_updated_idx")),
        migrations.AddIndex(model_name="conversation", index=models.Index(fields=["created_by", "created_at"], name="conv_created_by_idx")),
        migrations.AddConstraint(
            model_name="conversationcontext",
            constraint=models.CheckConstraint(condition=(
                models.Q(kind="space", space__isnull=False, group__isnull=True, activity__isnull=True, occurrence__isnull=True, dossier__isnull=True, project__isnull=True, journey__isnull=True, action_proposal__isnull=True, direct_profile_a__isnull=True, direct_profile_b__isnull=True)
                | models.Q(kind="group", space__isnull=True, group__isnull=False, activity__isnull=True, occurrence__isnull=True, dossier__isnull=True, project__isnull=True, journey__isnull=True, action_proposal__isnull=True, direct_profile_a__isnull=True, direct_profile_b__isnull=True)
                | models.Q(kind="activity", space__isnull=True, group__isnull=True, activity__isnull=False, occurrence__isnull=True, dossier__isnull=True, project__isnull=True, journey__isnull=True, action_proposal__isnull=True, direct_profile_a__isnull=True, direct_profile_b__isnull=True)
                | models.Q(kind="occurrence", space__isnull=True, group__isnull=True, activity__isnull=True, occurrence__isnull=False, dossier__isnull=True, project__isnull=True, journey__isnull=True, action_proposal__isnull=True, direct_profile_a__isnull=True, direct_profile_b__isnull=True)
                | models.Q(kind="dossier", space__isnull=True, group__isnull=True, activity__isnull=True, occurrence__isnull=True, dossier__isnull=False, project__isnull=True, journey__isnull=True, action_proposal__isnull=True, direct_profile_a__isnull=True, direct_profile_b__isnull=True)
                | models.Q(kind="project", space__isnull=True, group__isnull=True, activity__isnull=True, occurrence__isnull=True, dossier__isnull=True, project__isnull=False, journey__isnull=True, action_proposal__isnull=True, direct_profile_a__isnull=True, direct_profile_b__isnull=True)
                | models.Q(kind="journey", space__isnull=True, group__isnull=True, activity__isnull=True, occurrence__isnull=True, dossier__isnull=True, project__isnull=True, journey__isnull=False, action_proposal__isnull=True, direct_profile_a__isnull=True, direct_profile_b__isnull=True)
                | models.Q(kind="action_proposal", space__isnull=True, group__isnull=True, activity__isnull=True, occurrence__isnull=True, dossier__isnull=True, project__isnull=True, journey__isnull=True, action_proposal__isnull=False, direct_profile_a__isnull=True, direct_profile_b__isnull=True)
                | models.Q(kind="direct", space__isnull=True, group__isnull=True, activity__isnull=True, occurrence__isnull=True, dossier__isnull=True, project__isnull=True, journey__isnull=True, action_proposal__isnull=True, direct_profile_a__isnull=False, direct_profile_b__isnull=False)
            ), name="conv_context_shape_valid"),
        ),
        migrations.AddConstraint(model_name="conversationcontext", constraint=models.UniqueConstraint(condition=models.Q(("kind", "space")), fields=("space", "purpose_key"), name="conv_ctx_space_purpose_unique")),
        migrations.AddConstraint(model_name="conversationcontext", constraint=models.UniqueConstraint(condition=models.Q(("kind", "group")), fields=("group", "purpose_key"), name="conv_ctx_group_purpose_unique")),
        migrations.AddConstraint(model_name="conversationcontext", constraint=models.UniqueConstraint(condition=models.Q(("kind", "activity")), fields=("activity", "purpose_key"), name="conv_ctx_activity_purpose_unique")),
        migrations.AddConstraint(model_name="conversationcontext", constraint=models.UniqueConstraint(condition=models.Q(("kind", "occurrence")), fields=("occurrence", "purpose_key"), name="conv_ctx_occ_purpose_unique")),
        migrations.AddConstraint(model_name="conversationcontext", constraint=models.UniqueConstraint(condition=models.Q(("kind", "dossier")), fields=("dossier", "purpose_key"), name="conv_ctx_dossier_purpose_unique")),
        migrations.AddConstraint(model_name="conversationcontext", constraint=models.UniqueConstraint(condition=models.Q(("kind", "project")), fields=("project", "purpose_key"), name="conv_ctx_project_purpose_unique")),
        migrations.AddConstraint(model_name="conversationcontext", constraint=models.UniqueConstraint(condition=models.Q(("kind", "journey")), fields=("journey", "purpose_key"), name="conv_ctx_journey_purpose_unique")),
        migrations.AddConstraint(model_name="conversationcontext", constraint=models.UniqueConstraint(condition=models.Q(("kind", "action_proposal")), fields=("action_proposal", "purpose_key"), name="conv_ctx_proposal_purpose_unique")),
        migrations.AddConstraint(model_name="conversationcontext", constraint=models.UniqueConstraint(condition=models.Q(("kind", "direct")), fields=("direct_profile_a", "direct_profile_b", "purpose_key"), name="conv_ctx_direct_purpose_unique")),
        migrations.AddIndex(model_name="conversationcontext", index=models.Index(fields=["kind", "created_at"], name="conv_context_kind_idx")),
        migrations.AddConstraint(model_name="conversationparticipation", constraint=models.UniqueConstraint(fields=("conversation", "profile"), name="conv_participation_profile_unique")),
        migrations.AddIndex(model_name="conversationparticipation", index=models.Index(fields=["profile", "status"], name="conv_part_profile_status_idx")),
        migrations.AddConstraint(model_name="conversationinvitation", constraint=models.UniqueConstraint(condition=models.Q(("status", "pending")), fields=("conversation", "invitee"), name="conv_invite_pending_unique")),
        migrations.AddConstraint(model_name="conversationinvitation", constraint=models.UniqueConstraint(condition=models.Q(("client_reference__isnull", False)), fields=("client_reference",), name="conv_invite_client_ref_unique")),
        migrations.AddIndex(model_name="conversationinvitation", index=models.Index(fields=["invitee", "status"], name="conv_invitee_status_idx")),
        migrations.AddConstraint(model_name="conversationjoinrequest", constraint=models.UniqueConstraint(condition=models.Q(("status", "pending")), fields=("conversation", "requester"), name="conv_join_pending_unique")),
        migrations.AddConstraint(model_name="conversationjoinrequest", constraint=models.UniqueConstraint(condition=models.Q(("client_reference__isnull", False)), fields=("client_reference",), name="conv_join_client_ref_unique")),
        migrations.AddIndex(model_name="conversationjoinrequest", index=models.Index(fields=["requester", "status"], name="conv_join_requester_idx")),
        migrations.AddConstraint(model_name="conversationuserstate", constraint=models.UniqueConstraint(fields=("conversation", "profile"), name="conv_user_state_unique")),
        migrations.AddIndex(model_name="conversationuserstate", index=models.Index(fields=["profile", "archived_at"], name="conv_user_archived_idx")),
        migrations.AddIndex(model_name="conversationuserstate", index=models.Index(fields=["profile", "pinned_at"], name="conv_user_pinned_idx")),
    ]
