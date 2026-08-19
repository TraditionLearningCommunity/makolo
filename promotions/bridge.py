from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver

from .canonical_models import PromotionOffer, PromotionTargeting
from .models import Promotion


def _sync_activity_target(promotion):
    activity_id = None
    if promotion.event_id:
        activity_id = getattr(promotion.event, "activity_id", None)

    targeting = PromotionTargeting.objects.filter(promotion=promotion).first()
    if targeting is None:
        if activity_id is None:
            return None
        targeting = PromotionTargeting(promotion=promotion, activity_id=activity_id)
        targeting.full_clean()
        targeting.save()
        return targeting

    if targeting.activity_id != activity_id:
        targeting.activity_id = activity_id
        targeting.full_clean()
        targeting.save(update_fields=["activity", "updated_at"])
    return targeting


@receiver(post_save, sender=Promotion, dispatch_uid="promotions.sync_activity_target")
def sync_promotion_activity_target(sender, instance, **kwargs):
    _sync_activity_target(instance)


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
    _sync_activity_target(instance)
