from domain_events.services import emit_domain_event


def emit_payment_domain_event(payment, *, event_type):
    commerce_order = payment.commerce_order
    journey = commerce_order.journey if commerce_order is not None else None
    if journey is not None:
        activity_id = journey.activity_id
        occurrence_id = journey.occurrence_id
        space_id = journey.activity.space_id
        beneficiary_id = journey.beneficiary_id
        buyer_id = commerce_order.buyer_id
        payment_mode = commerce_order.payment_mode
    elif payment.order_id and getattr(payment.order.event, "activity_id", None):
        activity = payment.order.event.activity
        activity_id = activity.pk
        occurrence = getattr(payment.order.event, "occurrence", None)
        occurrence_id = getattr(occurrence, "pk", None)
        space_id = activity.space_id
        beneficiary_id = payment.order.buyer_id
        buyer_id = payment.order.buyer_id
        payment_mode = None
    else:
        activity_id = None
        occurrence_id = None
        space_id = None
        beneficiary_id = None
        buyer_id = None
        payment_mode = None

    suffix = event_type.rsplit(".", 1)[-1]
    return emit_domain_event(
        event_type=event_type,
        source_type="payment",
        source_id=payment.pk,
        idempotency_key=f"payment:{payment.pk}:{suffix}",
        space_id=space_id,
        activity_id=activity_id,
        payload={
            "payment_id": str(payment.pk),
            "commerce_order_id": str(payment.commerce_order_id) if payment.commerce_order_id else None,
            "journey_id": str(journey.pk) if journey else None,
            "activity_id": str(activity_id) if activity_id else None,
            "occurrence_id": str(occurrence_id) if occurrence_id else None,
            "beneficiary_id": str(beneficiary_id) if beneficiary_id else None,
            "buyer_id": str(buyer_id) if buyer_id else None,
            "payment_mode": payment_mode,
            "amount": str(payment.amount),
            "currency": payment.currency,
            "status": payment.status,
        },
    )
