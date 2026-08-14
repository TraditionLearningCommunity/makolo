import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


def backfill_commerce_targets(apps, schema_editor):
    Promotion = apps.get_model("promotions", "Promotion")
    PromotionTargeting = apps.get_model("promotions", "PromotionTargeting")
    PromotionOffer = apps.get_model("promotions", "PromotionOffer")

    for promotion in Promotion.objects.select_related("event").iterator():
        activity_id = None
        if promotion.event_id:
            activity_id = getattr(promotion.event, "activity_id", None)
        if activity_id:
            PromotionTargeting.objects.get_or_create(
                promotion_id=promotion.pk,
                defaults={"activity_id": activity_id},
            )
        for ticket_type in promotion.eligible_ticket_types.all():
            offer_id = getattr(ticket_type, "offer_id", None)
            if offer_id:
                PromotionOffer.objects.get_or_create(
                    promotion_id=promotion.pk,
                    offer_id=offer_id,
                )


class Migration(migrations.Migration):
    dependencies = [
        ("activities", "0002_occurrence_place"),
        ("commerce", "0001_initial"),
        ("crm", "0003_canonical_contacts_audiences"),
        ("events", "0005_backfill_activity_occurrence"),
        ("promotions", "0001_initial"),
        ("tickets", "0008_backfill_commerce_capacity"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PromotionTargeting",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("activity", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="promotion_targetings", to="activities.activity")),
                ("audience", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="promotion_targetings", to="crm.audience")),
                ("promotion", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="canonical_targeting", to="promotions.promotion")),
            ],
        ),
        migrations.AddIndex(model_name="promotiontargeting", index=models.Index(fields=["activity"], name="promo_target_activity_idx")),
        migrations.CreateModel(
            name="PromotionOffer",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("offer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="promotion_targets", to="commerce.offer")),
                ("promotion", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="offer_targets", to="promotions.promotion")),
            ],
        ),
        migrations.AddConstraint(model_name="promotionoffer", constraint=models.UniqueConstraint(fields=("promotion", "offer"), name="promotion_offer_unique")),
        migrations.AddIndex(model_name="promotionoffer", index=models.Index(fields=["offer"], name="promotion_offer_offer_idx")),
        migrations.CreateModel(
            name="CommercePromotionRedemption",
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
                ("buyer", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="commerce_promotion_redemptions", to=settings.AUTH_USER_MODEL)),
                ("code", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="commerce_redemptions", to="promotions.promotioncode")),
                ("commerce_order", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="promotion_redemption", to="commerce.commerceorder")),
                ("promotion", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="commerce_redemptions", to="promotions.promotion")),
            ],
            options={"ordering": ["-reserved_at"]},
        ),
        migrations.AddIndex(model_name="commercepromotionredemption", index=models.Index(fields=["promotion", "status", "reserved_at"], name="promo_comm_red_promo_idx")),
        migrations.AddIndex(model_name="commercepromotionredemption", index=models.Index(fields=["code", "status", "reserved_at"], name="promo_comm_red_code_idx")),
        migrations.AddIndex(model_name="commercepromotionredemption", index=models.Index(fields=["buyer", "status"], name="promo_comm_red_buyer_idx")),
        migrations.AddIndex(model_name="commercepromotionredemption", index=models.Index(fields=["customer_email", "status"], name="promo_comm_red_email_idx")),
        migrations.RunPython(backfill_commerce_targets, migrations.RunPython.noop),
    ]
