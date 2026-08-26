import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q


def backfill_offer_payment_options(apps, schema_editor):
    Offer = apps.get_model("commerce", "Offer")
    OfferPaymentOption = apps.get_model("commerce", "OfferPaymentOption")
    rows = [
        OfferPaymentOption(offer_id=offer_id, mode=payment_mode)
        for offer_id, payment_mode in Offer.objects.values_list("id", "payment_mode").iterator()
    ]
    OfferPaymentOption.objects.bulk_create(rows, ignore_conflicts=True)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("commerce", "0001_initial"),
        ("journeys", "0002_external_beneficiary"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="offer",
            name="payment_mode",
            field=models.CharField(
                choices=[
                    ("none", "Aucun paiement"),
                    ("upfront", "Paiement avant confirmation"),
                    ("after_approval", "Paiement après validation"),
                    ("on_site", "Paiement sur place"),
                    ("later", "Paiement différé"),
                ],
                default="none",
                help_text="Mode par défaut et compatibilité legacy. Les choix supplémentaires vivent dans payment_options.",
                max_length=24,
            ),
        ),
        migrations.CreateModel(
            name="OfferPaymentOption",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("mode", models.CharField(choices=[("none", "Aucun paiement"), ("upfront", "Paiement avant confirmation"), ("after_approval", "Paiement après validation"), ("on_site", "Paiement sur place"), ("later", "Paiement différé")], max_length=24)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("offer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="payment_options", to="commerce.offer")),
            ],
            options={"ordering": ["offer_id", "mode"]},
        ),
        migrations.AddField(
            model_name="commerceorder",
            name="payee_profile",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="payee_commerce_orders", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="commerceorderitem",
            name="external_beneficiary",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="commerce_order_items", to="journeys.externalbeneficiary"),
        ),
        migrations.AddIndex(
            model_name="offerpaymentoption",
            index=models.Index(fields=["mode", "offer"], name="commerce_offer_paymode_idx"),
        ),
        migrations.AddConstraint(
            model_name="offerpaymentoption",
            constraint=models.UniqueConstraint(fields=("offer", "mode"), name="commerce_offer_payment_mode_unique"),
        ),
        migrations.AddIndex(
            model_name="commerceorder",
            index=models.Index(fields=["payee_profile", "status"], name="commerce_order_ppayee_idx"),
        ),
        migrations.AddConstraint(
            model_name="commerceorder",
            constraint=models.CheckConstraint(condition=Q(payee_space__isnull=True) | Q(payee_profile__isnull=True), name="commerce_order_single_payee"),
        ),
        migrations.AddIndex(
            model_name="commerceorderitem",
            index=models.Index(fields=["external_beneficiary"], name="commerce_item_extben_idx"),
        ),
        migrations.AddConstraint(
            model_name="commerceorderitem",
            constraint=models.CheckConstraint(condition=Q(beneficiary__isnull=True) | Q(external_beneficiary__isnull=True), name="commerce_item_single_beneficiary"),
        ),
        migrations.RunPython(backfill_offer_payment_options, noop_reverse),
    ]
