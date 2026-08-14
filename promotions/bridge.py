from django.db.models.signals import m2m_changed
from django.dispatch import receiver

from .canonical_models import PromotionOffer, PromotionTargeting
from .models import Promotion


@receiver(m2m_changed, sender=Promotion.eligible_ticket_types.through)
def sync_ticket_type_offer_targets(sender, instance, action, **kwargs):
    if action not in {"post_add", "post_remove", "post_clear"}:
        return
    offer_ids = set(
        instance.eligible_ticket_types.exclude(offer_id__isnull=True).values_list("offer_id", flat=True)
    )
    PromotionOffer.objects.filter(promotion=instance, source="ticket_type").exclude(offer_id__in=offer_ids).delete()
    for offer_id in offer_ids:
        PromotionOffer.objects.get_or_create(
            promotion=instance,
            offer_id=offer_id,
            defaults={"source": "ticket_type"},
        )

    if instance.event_id:
        activity_id = getattr(instance.event, "activity_id", None)
        if activity_id:
            targeting, created = PromotionTargeting.objects.get_or_create(
                promotion=instance,
                defaults={"activity_id": activity_id},
            )
            if created is False and targeting.activity_id is None:
                targeting.activity_id = activity_id
                targeting.full_clean()
                targeting.save(update_fields=["activity", "updated_at"])
