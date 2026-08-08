# Generated manually for Makolo partners affiliation domain.

import decimal
import django.core.validators
import django.db.models.deletion
import django.utils.timezone
import uuid
from django.conf import settings
from django.db import migrations, models


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
            name="Partner",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("kind", models.CharField(choices=[("ambassador", "Ambassadeur"), ("influencer", "Influenceur / Créateur"), ("agency", "Agence"), ("media", "Média"), ("community", "Communauté"), ("business", "Entreprise / Partenaire"), ("other", "Autre")], default="ambassador", max_length=24)),
                ("status", models.CharField(choices=[("invited", "Invité"), ("active", "Actif"), ("paused", "En pause"), ("closed", "Clôturé")], default="active", max_length=16)),
                ("name", models.CharField(max_length=180)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("phone", models.CharField(blank=True, max_length=40)),
                ("public_label", models.CharField(blank=True, max_length=180)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="partners_created", to=settings.AUTH_USER_MODEL)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="partners", to="organizations.organization")),
                ("user", models.ForeignKey(blank=True, help_text="Compte Makolo lié au partenaire, si disponible.", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="partner_profiles", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["organization__name", "name"]},
        ),
        migrations.CreateModel(
            name="AffiliateCampaign",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=180)),
                ("status", models.CharField(choices=[("draft", "Brouillon"), ("active", "Active"), ("paused", "En pause"), ("ended", "Terminée")], default="draft", max_length=16)),
                ("commission_type", models.CharField(choices=[("percentage", "Pourcentage"), ("fixed", "Montant fixe")], default="percentage", max_length=16)),
                ("commission_value", models.DecimalField(decimal_places=2, default=decimal.Decimal("0.00"), max_digits=12, validators=[django.core.validators.MinValueValidator(decimal.Decimal("0.00"))])),
                ("commission_currency", models.CharField(default="USD", max_length=3)),
                ("attribution_window_days", models.PositiveSmallIntegerField(default=30, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(90)])),
                ("starts_at", models.DateTimeField(blank=True, null=True)),
                ("ends_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="affiliate_campaigns_created", to=settings.AUTH_USER_MODEL)),
                ("event", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="affiliate_campaigns", to="events.event")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="affiliate_campaigns", to="organizations.organization")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="PartnerPayout",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("currency", models.CharField(max_length=3)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(decimal.Decimal("0.01"))])),
                ("status", models.CharField(choices=[("draft", "Brouillon"), ("paid", "Payé"), ("cancelled", "Annulé")], default="draft", max_length=16)),
                ("reference", models.CharField(blank=True, max_length=120)),
                ("notes", models.TextField(blank=True)),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="partner_payouts_created", to=settings.AUTH_USER_MODEL)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="partner_payouts", to="organizations.organization")),
                ("paid_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="partner_payouts_paid", to=settings.AUTH_USER_MODEL)),
                ("partner", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="payouts", to="partners.partner")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="ReferralCode",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.CharField(blank=True, max_length=40, unique=True)),
                ("is_active", models.BooleanField(default=True)),
                ("commission_type_override", models.CharField(blank=True, choices=[("percentage", "Pourcentage"), ("fixed", "Montant fixe")], max_length=16)),
                ("commission_value_override", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, validators=[django.core.validators.MinValueValidator(decimal.Decimal("0.00"))])),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("campaign", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="referral_codes", to="partners.affiliatecampaign")),
                ("partner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="referral_codes", to="partners.partner")),
            ],
            options={"ordering": ["partner__name", "code"]},
        ),
        migrations.CreateModel(
            name="ReferralVisit",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("visitor_id", models.UUIDField()),
                ("landing_path", models.CharField(blank=True, max_length=255)),
                ("referrer_domain", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("referral_code", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="visits", to="partners.referralcode")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="ReferralAttribution",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("visitor_id", models.UUIDField(blank=True, null=True)),
                ("status", models.CharField(choices=[("pending", "En attente"), ("confirmed", "Confirmée"), ("reversed", "Annulée / inversée")], default="pending", max_length=16)),
                ("attributed_at", models.DateTimeField(auto_now_add=True)),
                ("confirmed_at", models.DateTimeField(blank=True, null=True)),
                ("reversed_at", models.DateTimeField(blank=True, null=True)),
                ("campaign", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="attributions", to="partners.affiliatecampaign")),
                ("order", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="referral_attribution", to="tickets.ticketorder")),
                ("partner", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="attributions", to="partners.partner")),
                ("referral_code", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="attributions", to="partners.referralcode")),
            ],
            options={"ordering": ["-attributed_at"]},
        ),
        migrations.CreateModel(
            name="PartnerCommission",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(decimal.Decimal("0.00"))])),
                ("currency", models.CharField(max_length=3)),
                ("commission_type", models.CharField(choices=[("percentage", "Pourcentage"), ("fixed", "Montant fixe")], max_length=16)),
                ("commission_value", models.DecimalField(decimal_places=2, max_digits=12)),
                ("status", models.CharField(choices=[("earned", "Acquise"), ("reversed", "Annulée"), ("paid", "Payée")], default="earned", max_length=16)),
                ("earned_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("reversed_at", models.DateTimeField(blank=True, null=True)),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("attribution", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="commission", to="partners.referralattribution")),
                ("campaign", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="commissions", to="partners.affiliatecampaign")),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="partner_commissions", to="tickets.ticketorder")),
                ("partner", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="commissions", to="partners.partner")),
                ("payout", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="commissions", to="partners.partnerpayout")),
            ],
            options={"ordering": ["-earned_at"]},
        ),
        migrations.AddConstraint(model_name="partner", constraint=models.UniqueConstraint(condition=models.Q(("user__isnull", False)), fields=("organization", "user"), name="partner_unique_org_user")),
        migrations.AddIndex(model_name="partner", index=models.Index(fields=["organization", "status"], name="partner_org_status_idx")),
        migrations.AddIndex(model_name="partner", index=models.Index(fields=["user", "status"], name="partner_user_status_idx")),
        migrations.AddConstraint(model_name="affiliatecampaign", constraint=models.UniqueConstraint(fields=("organization", "event", "name"), name="affiliate_campaign_unique_name")),
        migrations.AddIndex(model_name="affiliatecampaign", index=models.Index(fields=["organization", "status"], name="affiliate_campaign_org_idx")),
        migrations.AddIndex(model_name="affiliatecampaign", index=models.Index(fields=["event", "status"], name="affiliate_campaign_event_idx")),
        migrations.AddIndex(model_name="partnerpayout", index=models.Index(fields=["organization", "status", "created_at"], name="partner_payout_org_idx")),
        migrations.AddIndex(model_name="partnerpayout", index=models.Index(fields=["partner", "currency", "status"], name="partner_payout_partner_idx")),
        migrations.AddConstraint(model_name="referralcode", constraint=models.UniqueConstraint(fields=("campaign", "partner"), name="referral_code_unique_campaign_partner")),
        migrations.AddIndex(model_name="referralcode", index=models.Index(fields=["code", "is_active"], name="referral_code_lookup_idx")),
        migrations.AddConstraint(model_name="referralvisit", constraint=models.UniqueConstraint(fields=("referral_code", "visitor_id"), name="referral_visit_unique_visitor_code")),
        migrations.AddIndex(model_name="referralvisit", index=models.Index(fields=["referral_code", "created_at"], name="referral_visit_code_time_idx")),
        migrations.AddIndex(model_name="referralattribution", index=models.Index(fields=["campaign", "status", "attributed_at"], name="ref_attr_campaign_idx")),
        migrations.AddIndex(model_name="referralattribution", index=models.Index(fields=["partner", "status", "attributed_at"], name="ref_attr_partner_idx")),
        migrations.AddIndex(model_name="partnercommission", index=models.Index(fields=["partner", "status", "currency"], name="partner_comm_partner_idx")),
        migrations.AddIndex(model_name="partnercommission", index=models.Index(fields=["campaign", "status", "earned_at"], name="partner_comm_campaign_idx")),
    ]
