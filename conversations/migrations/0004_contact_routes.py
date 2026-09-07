import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("conversations", "0003_points"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("organizations", "0004_profilefollow"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProfileContactPolicy",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("mode", models.CharField(choices=[("closed", "Contact fermé"), ("request", "Sur demande"), ("contextual", "Direct dans un contexte légitime"), ("direct", "Contact direct autorisé")], default="request", max_length=16)),
                ("allow_activity_context", models.BooleanField(default=True)),
                ("allow_space_context", models.BooleanField(default=True)),
                ("allow_action_proposal_context", models.BooleanField(default=True)),
                ("allow_other_requests", models.BooleanField(default=False)),
                ("valid_until", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("profile", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="contact_policy", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="ContactRequest",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("intent", models.CharField(choices=[("activity", "Parler d’une activité"), ("collaboration", "Proposer une collaboration"), ("question", "Demander une information"), ("other", "Autre raison")], max_length=24)),
                ("message", models.CharField(max_length=500)),
                ("status", models.CharField(choices=[("pending", "En attente"), ("accepted", "Acceptée"), ("declined", "Refusée"), ("cancelled", "Annulée"), ("expired", "Expirée")], default="pending", max_length=16)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("client_reference", models.CharField(blank=True, max_length=80, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("responded_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("recipient", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="received_contact_requests", to=settings.AUTH_USER_MODEL)),
                ("sender", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="sent_contact_requests", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at", "id"]},
        ),
        migrations.CreateModel(
            name="AdditionalCommunicationEndpoint",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("provider", models.CharField(choices=[("telegram", "Telegram"), ("viber", "Viber"), ("messenger", "Messenger"), ("whatsapp", "WhatsApp"), ("other", "Autre")], max_length=24)),
                ("destination_kind", models.CharField(max_length=32)),
                ("value", models.CharField(max_length=500)),
                ("label", models.CharField(blank=True, max_length=120)),
                ("visibility", models.CharField(choices=[("private", "Privé"), ("contextual", "Contextuel"), ("public", "Public")], default="private", max_length=16)),
                ("status", models.CharField(choices=[("active", "Actif"), ("retired", "Retiré")], default="active", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_additional_communication_endpoints", to=settings.AUTH_USER_MODEL)),
                ("profile", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="additional_communication_endpoints", to=settings.AUTH_USER_MODEL)),
                ("space", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="additional_communication_endpoints", to="organizations.organization")),
            ],
        ),
        migrations.CreateModel(
            name="CommunicationRoute",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("provider", models.CharField(choices=[("whatsapp", "WhatsApp"), ("telegram", "Telegram"), ("messenger", "Messenger"), ("viber", "Viber"), ("sms", "SMS"), ("email", "E-mail"), ("phone", "Téléphone"), ("other", "Autre")], max_length=24)),
                ("destination_kind", models.CharField(choices=[("group_invite", "Invitation de groupe"), ("direct", "Contact direct"), ("thread", "Fil"), ("channel", "Canal"), ("phone", "Téléphone"), ("email", "E-mail"), ("handle", "Identifiant"), ("url", "Lien")], max_length=24)),
                ("label", models.CharField(max_length=160)),
                ("purpose", models.CharField(blank=True, max_length=300)),
                ("destination", models.CharField(max_length=700)),
                ("status", models.CharField(choices=[("active", "Active"), ("retired", "Retirée")], default="active", max_length=16)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("audience", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="communication_routes", to="conversations.conversationaudienceset")),
                ("conversation", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="communication_routes", to="conversations.conversation")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_communication_routes", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(model_name="contactrequest", constraint=models.CheckConstraint(condition=~models.Q(("sender", models.F("recipient"))), name="conv_contact_distinct_profiles")),
        migrations.AddConstraint(model_name="contactrequest", constraint=models.UniqueConstraint(condition=models.Q(("status", "pending")), fields=("sender", "recipient", "intent"), name="conv_contact_pending_unique")),
        migrations.AddConstraint(model_name="contactrequest", constraint=models.UniqueConstraint(condition=models.Q(("client_reference__isnull", False)), fields=("client_reference",), name="conv_contact_client_ref_unique")),
        migrations.AddIndex(model_name="contactrequest", index=models.Index(fields=["recipient", "status", "created_at"], name="conv_contact_recipient_idx")),
        migrations.AddIndex(model_name="contactrequest", index=models.Index(fields=["sender", "status", "created_at"], name="conv_contact_sender_idx")),
        migrations.AddConstraint(model_name="additionalcommunicationendpoint", constraint=models.CheckConstraint(condition=models.Q(profile__isnull=False, space__isnull=True) | models.Q(profile__isnull=True, space__isnull=False), name="conv_endpoint_single_owner")),
        migrations.AddIndex(model_name="additionalcommunicationendpoint", index=models.Index(fields=["provider", "status"], name="conv_endpoint_provider_idx")),
        migrations.AddIndex(model_name="communicationroute", index=models.Index(fields=["conversation", "status"], name="conv_route_conv_status_idx")),
    ]
