"""Additional owner-established Space Now signals, without generic inventory.

Each source retains domain ownership and explicit permission gates. Now neither
recomputes readiness nor infers urgency from the mere existence of records.
"""
from __future__ import annotations

from datetime import timedelta
from urllib.parse import urlencode

from django.db.models import Exists, F, OuterRef, Q
from django.urls import reverse

from access.models import AccessUse, AccessUseResult
from authorization.constants import PermissionCode
from authorization.selectors import (
    activity_ids_with_direct_permission,
    has_direct_space_permission,
)
from automation.models import AutomationExecution, DomainAutomationExecutionStatus
from capacity.models import CapacityPool
from capacity.selectors import capacity_availability_many
from commerce.models import CommerceOrder, CommerceOrderStatus
from operations.models import IncidentSeverity, IncidentStatus, OperationsIncident
from payments.models import Payment, PaymentObligation, PaymentObligationStatus, PaymentStatus


SCAN_LIMIT = 100


def _granted(profile, visible, code):
    return visible & set(activity_ids_with_direct_permission(profile, code))


def _web(space, name):
    return reverse(f"organizations:{name}", kwargs={"slug": space.slug})


def select_additional_space_now(
    *, profile, space, visible, observed_at, responsibility_key, make_situation
):
    """Compose only explicit anomaly/decision/monitoring conditions.

    Every owner returns actual facts; no pseudo-task or generic review backlog.
    Returns (situations, truncated) for honest coverage reporting.
    """
    items = []
    truncated = False

    operations = _granted(profile, visible, PermissionCode.ACTIVITY_OPERATIONS_VIEW)
    if operations:
        # High/critical unresolved incidents have an established operator reason.
        qs = (
            OperationsIncident.objects.filter(
                activity_id__in=operations,
                activity__space=space,
                status__in=[IncidentStatus.OPEN, IncidentStatus.INVESTIGATING],
                severity__in=[IncidentSeverity.HIGH, IncidentSeverity.CRITICAL],
            )
            .select_related("activity", "occurrence")
            .order_by("-detected_at", "pk")
        )
        rows = list(qs[: SCAN_LIMIT + 1])
        truncated |= len(rows) > SCAN_LIMIT
        for incident in rows[:SCAN_LIMIT]:
            native_target = "space_work_activity"
            native_id = incident.activity_id
            native_link = (
                f"/space/{space.slug}/retrieval/activity/{incident.activity_id}"
            )
            if incident.occurrence_id and incident.occurrence.is_ongoing:
                native_target = "space_occurrence_day_of"
                native_id = incident.occurrence_id
                native_link = None
            items.append(make_situation(
                space=space, source_kind="operations_incident", source_id=incident.pk,
                activity_id=incident.activity_id,
                human_context=incident.activity.title,
                subject="Incident opérationnel",
                state="Incident prioritaire non résolu",
                why_now="Operations signale un incident important toujours ouvert.",
                reason="operations_incident_unresolved",
                turn="collective", response_type="act",
                destination=native_target, native_id=native_id,
                native_link=native_link,
                web_url=_web(space, "console-operations"),
                observed_at=observed_at, action_label="Examiner dans Operations",
            ))

        # A recent, rejected passage is a documented AccessUse observation,
        # not a claim that the Access/credential is invalid globally.
        access_ids = _granted(profile, visible, PermissionCode.ACTIVITY_ACCESS_VIEW)
        accessible = access_ids & operations
        if accessible:
            # Other wrong-Activity/Occurrence results need the actual
            # scanner target authority; Access ownership alone is insufficient.
            rejected = [AccessUseResult.EXPIRED, AccessUseResult.REVOKED]
            settled_passage = AccessUse.objects.filter(
                access_id=OuterRef("access_id"),
                result=AccessUseResult.ACCEPTED,
                used_at__gt=OuterRef("used_at"),
            )
            qs = (
                AccessUse.objects.filter(
                    access__activity_id__in=accessible,
                    access__occurrence__isnull=False,
                    access__activity__space=space,
                    occurrence_id=F("access__occurrence_id"),
                    used_at__gte=observed_at - timedelta(hours=6),
                    result__in=rejected,
                )
                .annotate(accepted_later=Exists(settled_passage))
                .filter(accepted_later=False)
                .select_related("access__activity", "access__occurrence")
                .order_by("-used_at", "-pk")
            )
            rows = list(qs[: SCAN_LIMIT + 1])
            truncated |= len(rows) > SCAN_LIMIT
            observed_accesses = set()
            for use in rows[:SCAN_LIMIT]:
                if use.access_id in observed_accesses:
                    continue
                observed_accesses.add(use.access_id)
                occurrence = use.access.occurrence
                if not occurrence or not occurrence.is_ongoing:
                    continue
                items.append(make_situation(
                    space=space, source_kind="access_use", source_id=use.pk,
                    activity_id=use.access.activity_id,
                    human_context=use.access.activity.title,
                    subject="Contrôle d'accès",
                    state="Passage refusé pendant le déroulement",
                    why_now="Access a enregistré un refus de passage récent, sans passage accepté ultérieur.",
                    reason="access_use_rejected",
                    turn="collective", response_type="understand",
                    destination="space_occurrence_day_of",
                    native_id=occurrence.pk,
                    web_url=_web(space, "console-access"),
                    observed_at=observed_at, action_label="Examiner les accès",
                ))

    # Capacity is about quantity, not placement. Exhaustion can be a success;
    # only an actual over-allocation is admitted as a corrective anomaly.
    capacity_ids = _granted(profile, visible, PermissionCode.ACTIVITY_CAPACITY_VIEW)
    if capacity_ids:
        pools = list(
            CapacityPool.objects.filter(
                activity_id__in=capacity_ids, activity__space=space,
                is_active=True, total_quantity__isnull=False,
            )
            .select_related("activity", "occurrence")
            .order_by("activity_id", "pk")[: SCAN_LIMIT + 1]
        )
        truncated |= len(pools) > SCAN_LIMIT
        availability = capacity_availability_many(
            pools[:SCAN_LIMIT], now=observed_at,
        )
        commerce_ids = _granted(
            profile, visible, PermissionCode.ACTIVITY_COMMERCE_VIEW
        )
        for pool in pools[:SCAN_LIMIT]:
            fact = availability[pool.pk]
            if fact.total is None or fact.held + fact.committed <= fact.total:
                continue
            target = "space_work_activity"
            target_id = pool.activity_id
            native_link = f"/space/{space.slug}/retrieval/activity/{pool.activity_id}"
            if pool.occurrence_id and pool.activity_id in operations:
                target = "space_occurrence_day_of"
                target_id = pool.occurrence_id
                native_link = None
            web_url = _web(
                space, "console-offers"
                if pool.activity_id in commerce_ids else "console-operations"
                if pool.activity_id in operations else "console-overview",
            )
            items.append(make_situation(
                space=space, source_kind="capacity_pool", source_id=pool.pk,
                activity_id=pool.activity_id,
                human_context=pool.activity.title,
                subject=pool.label or "Capacité",
                state="Capacité engagée au-delà du total",
                why_now=(
                    f"Capacity établit {fact.held + fact.committed} unités retenues "
                    f"ou engagées pour {fact.total} disponibles au total."
                ),
                reason="capacity_overallocated",
                turn="collective", response_type="act",
                destination=target, native_id=target_id,
                native_link=native_link, web_url=web_url,
                observed_at=observed_at, action_label="Examiner la capacité",
            ))

    # The canonical mobile Commerce owner depth itself requires ORDERS_VIEW.
    # Avoid announcing an action if that depth would return a forbidden owner.
    order_scope = has_direct_space_permission(
        profile, space, PermissionCode.ORDERS_VIEW
    )
    finance_scope = has_direct_space_permission(
        profile, space, PermissionCode.FINANCE_VIEW
    )
    if order_scope:
        commerce_ids = visible  # Payee Space + authorized Space mandate.
        failed_orders = set()
        if finance_scope:
            # Failures only matter while Commerce still has a pending order;
            # a later successful/processing attempt supersedes the older failure.
            superseding = Payment.objects.filter(
                commerce_order_id=OuterRef("commerce_order_id"),
            ).filter(
                Q(created_at__gt=OuterRef("created_at"))
                | Q(status=PaymentStatus.SUCCEEDED)
            )
            qs = (
                Payment.objects.filter(
                    commerce_order__payee_space=space,
                    commerce_order__journey__activity_id__in=commerce_ids,
                    commerce_order__journey__activity__space=space,
                    commerce_order__status=CommerceOrderStatus.PENDING,
                    status=PaymentStatus.FAILED,
                    created_at__gte=observed_at - timedelta(days=3),
                )
                .annotate(superseded=Exists(superseding))
                .filter(superseded=False)
                .select_related("commerce_order", "commerce_order__journey__activity")
                .order_by("-created_at", "-pk")
            )
            candidates = list(qs[: SCAN_LIMIT + 1])
            truncated |= len(candidates) > SCAN_LIMIT
            for payment in candidates[:SCAN_LIMIT]:
                order = payment.commerce_order
                if order.pk in failed_orders:
                    continue
                failed_orders.add(order.pk)
                items.append(make_situation(
                    space=space, source_kind="payment", source_id=payment.pk,
                    activity_id=order.journey.activity_id,
                    human_context=f"Commande {order.reference}",
                    subject="Paiement de la commande",
                    state="Dernière tentative de paiement échouée",
                    why_now="Payments constate un échec récent tandis que Commerce garde la commande en attente.",
                    reason="payment_failed_order_pending",
                    turn="external", response_type="monitor",
                    destination="space_commerce_order", native_id=order.pk,
                    native_link=(
                        f"/space/{space.slug}/retrieval/commerce_order/{order.pk}"
                    ),
                    web_url=_web(space, "console-payments"),
                    observed_at=observed_at, action_label="Vérifier le paiement",
                ))

        # An explicit expiry window makes a pending order worth watching;
        # "pending" alone does not. A failed-payment situation supersedes it.
        orders = list(
            CommerceOrder.objects.filter(
                payee_space=space,
                journey__activity_id__in=commerce_ids,
                journey__activity__space=space,
                status=CommerceOrderStatus.PENDING,
                total__gt=0,
                expires_at__gt=observed_at,
                expires_at__lte=observed_at + timedelta(hours=24),
            )
            .select_related("journey__activity")
            .order_by("expires_at", "pk")[: SCAN_LIMIT + 1]
        )
        truncated |= len(orders) > SCAN_LIMIT
        for order in orders[:SCAN_LIMIT]:
            if order.pk in failed_orders:
                continue
            items.append(make_situation(
                space=space, source_kind="commerce_order", source_id=order.pk,
                activity_id=order.journey.activity_id,
                human_context=f"Commande {order.reference}",
                subject="Échéance de confirmation",
                state="Commande payante non confirmée avant échéance",
                why_now=(
                    "Commerce établit une commande payante encore en attente "
                    "et une échéance dans les prochaines 24 heures. "
                    "Aucune décision Space n'est déduite."
                ),
                reason="commerce_order_expiring",
                turn="none", response_type="wait",
                destination="space_commerce_order", native_id=order.pk,
                native_link=(
                    f"/space/{space.slug}/retrieval/commerce_order/{order.pk}"
                ),
                web_url=_web(space, "console-orders"),
                observed_at=observed_at, action_label="Consulter la commande",
                deadline_at=order.expires_at,
            ))

    # Debtor-side Payments: an overdue obligation owed by this institution
    # is not the same as its incoming Commerce payments. The actual Space
    # payer and an authorized Journey context must both be established.
    if finance_scope:
        overdue = list(
            PaymentObligation.objects.filter(
                payer_space=space,
                journey__activity__space=space,
                journey__activity_id__in=visible,
                commerce_order__isnull=True,
                status__in=[
                    PaymentObligationStatus.PENDING,
                    PaymentObligationStatus.PROCESSING,
                ],
                due_at__isnull=False,
                due_at__lt=observed_at,
            )
            .select_related("journey__activity")
            .order_by("due_at", "pk")[: SCAN_LIMIT + 1]
        )
        truncated |= len(overdue) > SCAN_LIMIT
        for obligation in overdue[:SCAN_LIMIT]:
            items.append(make_situation(
                space=space,
                source_kind="payment_obligation",
                source_id=obligation.pk,
                activity_id=obligation.journey.activity_id,
                human_context=obligation.journey.activity.title,
                subject="Obligation financière",
                state="Échéance dépassée, règlement non confirmé",
                why_now=(
                    "Payments établit une obligation échue à la charge "
                    "de cet Espace, sans règlement encore confirmé."
                ),
                reason="space_payment_obligation_overdue",
                turn="none",
                response_type=(
                    "wait" if obligation.status == PaymentObligationStatus.PROCESSING
                    else "understand"
                ),
                destination="space_payment_obligation",
                native_id=obligation.pk,
                native_link=(
                    f"/space/{space.slug}/retrieval/payment_obligation/{obligation.pk}"
                ),
                web_url=(
                    reverse(
                        "organizations:space-payment-obligation",
                        kwargs={"slug": space.slug, "obligation_id": obligation.pk},
                    )
                    + (
                        f"?{urlencode({'responsibility': responsibility_key})}"
                        if responsibility_key and responsibility_key != "all"
                        else ""
                    )
                ),
                observed_at=observed_at,
                action_label="Examiner l'obligation",
                deadline_at=obligation.due_at,
            ))

    # A failed Domain Automation execution is a real owner failure, not a
    # generic notification to fill Now. Scope only to manageable Activities.
    managed = _granted(profile, visible, PermissionCode.ACTIVITY_MANAGE)
    if managed:
        failures = list(
            AutomationExecution.objects.filter(
                rule__space=space, rule__activity_id__in=managed,
                status=DomainAutomationExecutionStatus.FAILED,
                created_at__gte=observed_at - timedelta(days=1),
            )
            .select_related("rule__activity")
            .order_by("-created_at", "pk")[: SCAN_LIMIT + 1]
        )
        truncated |= len(failures) > SCAN_LIMIT
        for execution in failures[:SCAN_LIMIT]:
            activity = execution.rule.activity
            items.append(make_situation(
                space=space, source_kind="automation_execution", source_id=execution.pk,
                activity_id=activity.pk,
                human_context=activity.title,
                subject="Automatisation",
                state="Exécution automatisée échouée",
                why_now="Automation établit un échec récent sur une règle de cette activité.",
                reason="automation_execution_failed",
                turn="collective", response_type="understand",
                destination="space_work_activity", native_id=activity.pk,
                native_link=f"/space/{space.slug}/retrieval/activity/{activity.pk}",
                web_url=_web(space, "console-automation"),
                observed_at=observed_at, action_label="Examiner l'automatisation",
            ))

    return items, truncated
