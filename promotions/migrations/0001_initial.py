import decimal
import django.core.validators
import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("crm", "0002_followers_tags_fields_templates_attribution"),
        ("events", "0002_event_organization"),
        ("organizations", "0002_organizationfollow"),
        ("tickets", "0003_ticketwaitlistentry_tickettransfer"),
    ]

    operations = [
        migrations.CreateModel(
            name="Promotion",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=160)),
                ("description", models.TextField(blank=True)),
                ("discount_type", models.CharField(choices=[("percent", "Pourcentage"), ("fixed", "Montant fixe")], max_length=16)),
                ("discount_value", models.DecimalField(decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(decimal.Decimal("0.01"))])),
                ("max_discount_amount", models.DecimalField(blank=True, decimal_places=2, help_text="Plafond facultatif pour une remise en pourcentage.", max_digits=12, null=True, validators=[django.core.validators.MinValueValidator(decimal.Decimal("0.01"))])),
                ("min_order_amount", models.DecimalField(decimal_places=2, default=0, max_digits=12, validators=[django.core.validators.MinValueValidator(decimal.Decimal("0.00"))])),
                ("currency", models.CharField(blank=True, max_length=3)),
                ("starts_at", models.DateTimeField(blank=True, null=True)),
                ("ends_at", models.DateTimeField(blank=True, null=True)),
                ("max_redemptions", models.PositiveIntegerField(blank=True, null=True)),
                ("max_redemptions_per_customer", models.PositiveSmallIntegerField(default=1, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(100)])),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_promotions", to=settings.AUTH_USER_MODEL)),
                ("eligible_ticket_types", models.ManyToManyField(blank=True, related_name="eligible_promotions", to="tickets.tickettype")),
                ("event", models.ForeignKey(blank=True, help_text="Laisser vide pour une offre valable sur les événements de l'organisation.", null=True, on_delete=django.db.models.deletion.CASCADE, related_name="promotions", to="events.event")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="promotions", to="organizations.organization")),
            ],
            options={"ordering": ["organization__name", "name"]},
        ),
        migrations.CreateModel(
            name="PromotionCode",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.CharField(max_length=40, unique=True, validators=[django.core.validators.RegexValidator(message="Le code doit contenir 3 à 40 caractères : lettres, chiffres, _ ou -.", regex="^[A-Za-z0-9][A-Za-z0-9_-]{2,39}$")])),
                ("label", models.CharField(blank=True, max_length=120)),
                ("starts_at", models.DateTimeField(blank=True, null=True)),
                ("ends_at", models.DateTimeField(blank=True, null=True)),
                ("max_redemptions", models.PositiveIntegerField(blank=True, null=True)),
                ("is_private", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_promotion_codes", to=settings.AUTH_USER_MODEL)),
                ("crm_campaign", models.ForeignKey(blank=True, help_text="Campagne CRM associée pour mesurer l'usage du code, sans fabriquer une attribution de clic.", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="promotion_codes", to="crm.communicationcampaign")),
                ("promotion", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="codes", to="promotions.promotion")),
            ],
            options={"ordering": ["promotion", "code"]},
        ),
        migrations.CreateModel(
            name="PromotionRedemption",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("customer_email", models.EmailField(max_length=254)),
                ("status", models.CharField(choices=[("reserved", "Réservée"), ("confirmed", "Confirmée"), ("reversed", "Annulée")], default="reserved", max_length=16)),
                ("subtotal_amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("eligible_amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("discount_amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("final_amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("currency", models.CharField(max_length=3)),
                ("reserved_at", models.DateTimeField(auto_now_add=True)),
                ("confirmed_at", models.DateTimeField(blank=True, null=True)),
                ("reversed_at", models.DateTimeField(blank=True, null=True)),
                ("buyer", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="promotion_redemptions", to=settings.AUTH_USER_MODEL)),
                ("code", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="redemptions", to="promotions.promotioncode")),
                ("order", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="promotion_redemption", to="tickets.ticketorder")),
                ("promotion", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="redemptions", to="promotions.promotion")),
            ],
            options={"ordering": ["-reserved_at"]},
        ),
        migrations.AddConstraint(
            model_name="promotion",
            constraint=models.UniqueConstraint(fields=("organization", "name"), name="promotion_org_name_unique"),
        ),
        migrations.AddIndex(
            model_name="promotion",
            index=models.Index(fields=["organization", "is_active"], name="promotion_org_active_idx"),
        ),
        migrations.AddIndex(
            model_name="promotion",
            index=models.Index(fields=["event", "is_active"], name="promotion_event_active_idx"),
        ),
        migrations.AddIndex(
            model_name="promotioncode",
            index=models.Index(fields=["promotion", "is_active"], name="promo_code_promo_active_idx"),
        ),
        migrations.AddIndex(
            model_name="promotioncode",
            index=models.Index(fields=["crm_campaign", "is_active"], name="promo_code_campaign_idx"),
        ),
        migrations.AddIndex(
            model_name="promotionredemption",
            index=models.Index(fields=["promotion", "status", "reserved_at"], name="promo_redemption_offer_idx"),
        ),
        migrations.AddIndex(
            model_name="promotionredemption",
            index=models.Index(fields=["code", "status", "reserved_at"], name="promo_redemption_code_idx"),
        ),
        migrations.AddIndex(
            model_name="promotionredemption",
            index=models.Index(fields=["buyer", "status"], name="promo_redemption_buyer_idx"),
        ),
        migrations.AddIndex(
            model_name="promotionredemption",
            index=models.Index(fields=["customer_email", "status"], name="promo_redemption_email_idx"),
        ),
    ]
