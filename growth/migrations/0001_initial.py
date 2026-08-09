import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.core.validators import MaxValueValidator, MinValueValidator
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("organizations", "0002_organizationfollow"),
        ("events", "0002_event_organization"),
        ("tickets", "0003_ticketwaitlistentry_tickettransfer"),
        ("crm", "0002_followers_tags_fields_templates_attribution"),
    ]

    operations = [
        migrations.CreateModel(
            name="MarketingLink",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=160)),
                ("channel", models.CharField(choices=[("whatsapp", "WhatsApp"), ("instagram", "Instagram"), ("facebook", "Facebook"), ("qr", "QR / Affiche"), ("flyer", "Flyer"), ("partner", "Partenaire"), ("email", "E-mail"), ("other", "Autre")], max_length=20)),
                ("code", models.CharField(blank=True, max_length=16, unique=True)),
                ("attribution_window_days", models.PositiveSmallIntegerField(default=30, validators=[MinValueValidator(1), MaxValueValidator(90)])),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_marketing_links", to=settings.AUTH_USER_MODEL)),
                ("crm_campaign", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="marketing_links", to="crm.communicationcampaign")),
                ("event", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="marketing_links", to="events.event")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="marketing_links", to="organizations.organization")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="MarketingLinkVisit",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("session_key_hash", models.CharField(blank=True, max_length=64)),
                ("referrer_domain", models.CharField(blank=True, max_length=255)),
                ("visited_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("link", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="visits", to="growth.marketinglink")),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="marketing_link_visits", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-visited_at"]},
        ),
        migrations.CreateModel(
            name="MarketingAttribution",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("status", models.CharField(choices=[("pending", "En attente"), ("confirmed", "Confirmée"), ("reversed", "Annulée")], default="pending", max_length=16)),
                ("revenue_amount", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("currency", models.CharField(max_length=3)),
                ("attributed_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("confirmed_at", models.DateTimeField(blank=True, null=True)),
                ("reversed_at", models.DateTimeField(blank=True, null=True)),
                ("link", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="attributions", to="growth.marketinglink")),
                ("order", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="marketing_attribution", to="tickets.ticketorder")),
                ("visit", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="attributions", to="growth.marketinglinkvisit")),
            ],
            options={"ordering": ["-attributed_at"]},
        ),
        migrations.CreateModel(
            name="EventFeedback",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("rating", models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])),
                ("comment", models.TextField(blank=True, max_length=2000)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("event", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="private_feedback", to="events.event")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="event_feedback", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="marketinglink",
            index=models.Index(fields=["organization", "is_active"], name="growth_link_org_active_idx"),
        ),
        migrations.AddIndex(
            model_name="marketinglink",
            index=models.Index(fields=["event", "is_active"], name="growth_link_event_active_idx"),
        ),
        migrations.AddIndex(
            model_name="marketinglink",
            index=models.Index(fields=["channel", "created_at"], name="growth_link_channel_idx"),
        ),
        migrations.AddIndex(
            model_name="marketinglinkvisit",
            index=models.Index(fields=["link", "visited_at"], name="growth_visit_link_time_idx"),
        ),
        migrations.AddIndex(
            model_name="marketinglinkvisit",
            index=models.Index(fields=["user", "visited_at"], name="growth_visit_user_time_idx"),
        ),
        migrations.AddIndex(
            model_name="marketingattribution",
            index=models.Index(fields=["link", "status", "attributed_at"], name="growth_attr_link_status_idx"),
        ),
        migrations.AddConstraint(
            model_name="eventfeedback",
            constraint=models.UniqueConstraint(fields=("event", "user"), name="growth_feedback_event_user_uq"),
        ),
        migrations.AddIndex(
            model_name="eventfeedback",
            index=models.Index(fields=["event", "rating"], name="growth_feedback_event_idx"),
        ),
    ]
