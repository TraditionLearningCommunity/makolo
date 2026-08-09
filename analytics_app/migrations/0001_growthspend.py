import uuid
from decimal import Decimal

from django.conf import settings
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("crm", "0002_followers_tags_fields_templates_attribution"),
        ("events", "0002_event_organization"),
        ("loyalty", "0001_initial"),
        ("organizations", "0002_organizationfollow"),
        ("partners", "0001_initial"),
        ("promotions", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="GrowthSpend",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "channel",
                    models.CharField(
                        choices=[
                            ("crm", "CRM"),
                            ("partners", "Partenaires"),
                            ("promotions", "Promotions"),
                            ("loyalty", "Fidélité"),
                            ("other", "Autre"),
                        ],
                        default="other",
                        max_length=20,
                    ),
                ),
                ("label", models.CharField(max_length=180)),
                (
                    "amount",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=12,
                        validators=[django.core.validators.MinValueValidator(Decimal("0.01"))],
                    ),
                ),
                ("currency", models.CharField(max_length=3)),
                ("incurred_at", models.DateField(default=django.utils.timezone.localdate)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="created_growth_spends",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "crm_campaign",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="growth_spends",
                        to="crm.communicationcampaign",
                    ),
                ),
                (
                    "event",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="growth_spends",
                        to="events.event",
                    ),
                ),
                (
                    "loyalty_program",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="growth_spends",
                        to="loyalty.loyaltyprogram",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="growth_spends",
                        to="organizations.organization",
                    ),
                ),
                (
                    "partner_campaign",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="growth_spends",
                        to="partners.affiliatecampaign",
                    ),
                ),
                (
                    "promotion",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="growth_spends",
                        to="promotions.promotion",
                    ),
                ),
            ],
            options={"ordering": ["-incurred_at", "-created_at"]},
        ),
        migrations.AddIndex(
            model_name="growthspend",
            index=models.Index(
                fields=["organization", "channel", "incurred_at"],
                name="growth_spend_org_channel_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="growthspend",
            index=models.Index(
                fields=["organization", "currency", "incurred_at"],
                name="growth_spend_org_currency_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="growthspend",
            index=models.Index(
                fields=["event", "currency"],
                name="growth_spend_event_currency_idx",
            ),
        ),
    ]
