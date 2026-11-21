"""Space billing details: Subscription view authority is not Payments authority."""
from authorization.constants import PermissionCode
from authorization.services import space_ids_with_permission
from payments.selectors import obligations_visible_to

from .billing_presentation import subscription_billing_obligations


def space_billing_for_actor(actor, subscription, *, offset=0, limit=20):
    if subscription.space_id is None:
        raise ValueError("Space billing requires a Space subscriber")
    finance_spaces = space_ids_with_permission(actor, PermissionCode.FINANCE_VIEW)
    if finance_spaces is not None and subscription.space_id not in finance_spaces:
        return {"items": [], "next_offset": None, "visibility": "restricted"}
    payload = subscription_billing_obligations(subscription, offset=offset, limit=limit)
    payload["visibility"] = "visible"
    accessible = {
        str(pk)
        for pk in obligations_visible_to(actor)
        .filter(pk__in=[row["id"] for row in payload["items"]])
        .values_list("pk", flat=True)
    }
    for row in payload["items"]:
        row["can_open_detail"] = row["id"] in accessible
    return payload
