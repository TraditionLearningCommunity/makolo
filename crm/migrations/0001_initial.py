import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("organizations", "0001_initial"),
        ("events", "0002_event_organization"),
        ("tickets", "0003_ticketwaitlistentry_tickettransfer"),
    ]

    operations = [
        migrations.CreateModel(
            name="CRMContact",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("email", models.EmailField(max_length=254)),
                ("name", models.CharField(blank=True, max_length=180)),
                ("phone", models.CharField(blank=True, max_length=40)),
                ("source", models.CharField(choices=[("ticket_order", "Commande"), ("ticket", "Billet"), ("waitlist", "Liste d’attente"), ("manual", "Manuel")], default="ticket_order", max_length=24)),
                ("marketing_consent", models.CharField(choices=[("unknown", "Non renseigné"), ("subscribed", "Abonné"), ("unsubscribed", "Désabonné")], default="unknown", max_length=16)),
                ("consent_source", models.CharField(blank=True, max_length=120)),
                ("consent_updated_at", models.DateTimeField(blank=True, null=True)),
                ("first_seen_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("last_seen_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="crm_contacts", to="organizations.organization")),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="crm_contact_profiles", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["name", "email"],
                "indexes": [
                    models.Index(fields=["organization", "marketing_consent"], name="crm_contact_consent_idx"),
                    models.Index(fields=["organization", "last_seen_at"], name="crm_contact_seen_idx"),
                    models.Index(fields=["user", "organization"], name="crm_contact_user_org_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("organization", "email"), name="crm_contact_org_email_unique"),
                ],
            },
        ),
        migrations.CreateModel(
            name="AudienceSegment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=160)),
                ("description", models.TextField(blank=True)),
                ("audience_kind", models.CharField(choices=[("all", "Tous les contacts"), ("confirmed_buyers", "Acheteurs confirmés"), ("ticket_holders", "Détenteurs de billets"), ("attendees", "Participants présents"), ("no_shows", "Absents / no-show"), ("waitlist", "Liste d’attente"), ("partner_referred", "Acquisition partenaire")], default="all", max_length=32)),
                ("marketing_consent_only", models.BooleanField(default=False)),
                ("city", models.CharField(blank=True, max_length=120)),
                ("country", models.CharField(blank=True, max_length=120)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_crm_segments", to=settings.AUTH_USER_MODEL)),
                ("event", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="crm_segments", to="events.event")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="crm_segments", to="organizations.organization")),
                ("ticket_type", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="crm_segments", to="tickets.tickettype")),
            ],
            options={
                "ordering": ["name"],
                "indexes": [
                    models.Index(fields=["organization", "is_active"], name="crm_segment_org_active_idx"),
                    models.Index(fields=["event", "audience_kind"], name="crm_segment_event_kind_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("organization", "name"), name="crm_segment_org_name_unique"),
                ],
            },
        ),
        migrations.CreateModel(
            name="CommunicationCampaign",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=160)),
                ("kind", models.CharField(choices=[("marketing", "Marketing"), ("event_update", "Information événement")], default="marketing", max_length=20)),
                ("subject", models.CharField(max_length=180)),
                ("preview_text", models.CharField(blank=True, max_length=220)),
                ("body", models.TextField()),
                ("cta_label", models.CharField(blank=True, max_length=80)),
                ("cta_url", models.URLField(blank=True)),
                ("status", models.CharField(choices=[("draft", "Brouillon"), ("scheduled", "Planifiée"), ("sending", "En cours"), ("sent", "Envoyée"), ("cancelled", "Annulée")], default="draft", max_length=16)),
                ("scheduled_at", models.DateTimeField(blank=True, null=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_crm_campaigns", to=settings.AUTH_USER_MODEL)),
                ("event", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="crm_campaigns", to="events.event")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="crm_campaigns", to="organizations.organization")),
                ("segment", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="campaigns", to="crm.audiencesegment")),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["organization", "status", "created_at"], name="crm_campaign_org_status_idx"),
                    models.Index(fields=["status", "scheduled_at"], name="crm_campaign_due_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="CampaignRecipient",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("email", models.EmailField(max_length=254)),
                ("name", models.CharField(blank=True, max_length=180)),
                ("status", models.CharField(choices=[("queued", "En attente"), ("processing", "En cours"), ("sent", "Envoyé"), ("failed", "Échoué"), ("skipped", "Ignoré")], default="queued", max_length=16)),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("max_attempts", models.PositiveSmallIntegerField(default=3)),
                ("scheduled_for", models.DateTimeField(default=django.utils.timezone.now)),
                ("last_error", models.TextField(blank=True)),
                ("skipped_reason", models.CharField(blank=True, max_length=255)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("campaign", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="recipients", to="crm.communicationcampaign")),
                ("contact", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="campaign_recipients", to="crm.crmcontact")),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="crm_campaign_recipients", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["created_at"],
                "indexes": [
                    models.Index(fields=["status", "scheduled_for"], name="crm_recipient_due_idx"),
                    models.Index(fields=["campaign", "status"], name="crm_recipient_campaign_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("campaign", "contact"), name="crm_recipient_campaign_contact_unique"),
                ],
            },
        ),
        migrations.CreateModel(
            name="CRMContactNote",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("body", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("author", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="crm_contact_notes", to=settings.AUTH_USER_MODEL)),
                ("contact", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notes", to="crm.crmcontact")),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["contact", "created_at"], name="crm_note_contact_idx"),
                ],
            },
        ),
    ]
