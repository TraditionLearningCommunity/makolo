import hashlib
from collections import Counter, defaultdict
from datetime import timedelta
from decimal import Decimal
from urllib.parse import urlparse

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Avg, Count, Sum
from django.utils import timezone

from automation.models import (
    CRMWorkflow,
    CRMWorkflowAction,
    CRMWorkflowActionKind,
    CRMWorkflowTrigger,
)
from crm.models import CampaignAttribution, CampaignAttributionStatus
from organizations.models import OrganizationFollow
from payments.models import Payment, PaymentStatus, Refund, RefundStatus
from tickets.models import Ticket, TicketOrder, TicketOrderStatus, TicketStatus

from .models import (
    EventFeedback,
    MarketingAttribution,
    MarketingAttributionStatus,
    MarketingLink,
    MarketingLinkVisit,
)
from .permissions import user_can_view_growth_financials


ZERO = Decimal("0.00")
SESSION_LINK_ID = "growth_marketing_link_id"
SESSION_LINK_AT = "growth_marketing_link_at"
SESSION_VISIT_ID = "growth_marketing_visit_id"


PRESET_DEFINITIONS = {
    "welcome_follower": {
        "label": "Bienvenue nouvel abonné",
        "trigger": CRMWorkflowTrigger.FOLLOWED_ORGANIZER,
        "event_required": False,
        "marketing": False,
        "title": "Bienvenue chez {organization}",
        "message": "Merci de suivre {organization} sur Makolo. Vous retrouverez ici ses prochains événements.",
    },
    "reservation_expired": {
        "label": "Relance réservation expirée",
        "trigger": CRMWorkflowTrigger.ORDER_EXPIRED,
        "event_required": False,
        "marketing": False,
        "title": "Votre réservation a expiré",
        "message": "Votre réservation n'a pas été finalisée. Revenez sur Makolo si vous souhaitez vérifier les places encore disponibles.",
    },
    "event_reminder_24h": {
        "label": "Rappel J-1",
        "trigger": CRMWorkflowTrigger.BEFORE_EVENT,
        "event_required": True,
        "marketing": False,
        "offset": 1440,
        "title": "{event} commence demain",
        "message": "Votre événement {event} approche. Gardez votre billet Makolo à portée de main.",
    },
    "post_checkin_thanks": {
        "label": "Remerciement participant",
        "trigger": CRMWorkflowTrigger.CHECKED_IN,
        "event_required": True,
        "marketing": False,
        "title": "Merci d'être venu à {event}",
        "message": "Merci d'avoir participé à {event}. Votre présence a bien été enregistrée sur Makolo.",
    },
    "no_show_reactivation": {
        "label": "Réactivation no-show",
        "trigger": CRMWorkflowTrigger.NO_SHOW,
        "event_required": True,
        "marketing": True,
        "title": "On espère vous voir au prochain événement",
        "message": "Vous n'avez pas pu être présent à {event}. Suivez {organization} pour découvrir les prochaines dates.",
    },
}


def _session_hash(request):
    if not request.session.session_key:
        request.session.save()
    key = request.session.session_key or ""
    return hashlib.sha256(key.encode("utf-8")).hexdigest() if key else ""


def _referrer_domain(request):
    raw = (request.META.get("HTTP_REFERER") or "").strip()
    if not raw:
        return ""
    try:
        return (urlparse(raw).hostname or "")[:255]
    except ValueError:
        return ""


def capture_marketing_link(request, link: MarketingLink):
    if not link.is_active:
        raise ValidationError("Ce lien marketing n'est plus actif.")
    visit = MarketingLinkVisit.objects.create(
        link=link,
        user=request.user if getattr(request.user, "is_authenticated", False) else None,
        session_key_hash=_session_hash(request),
        referrer_domain=_referrer_domain(request),
    )
    request.session[SESSION_LINK_ID] = str(link.pk)
    request.session[SESSION_VISIT_ID] = str(visit.pk)
    request.session[SESSION_LINK_AT] = timezone.now().isoformat()
    request.session.modified = True
    return visit


def get_session_marketing_link(request, *, event):
    raw_id = request.session.get(SESSION_LINK_ID)
    raw_at = request.session.get(SESSION_LINK_AT)
    if not raw_id or not raw_at:
        return None, None
    try:
        visited_at = timezone.datetime.fromisoformat(raw_at)
        if timezone.is_naive(visited_at):
            visited_at = timezone.make_aware(visited_at, timezone.get_current_timezone())
    except (TypeError, ValueError):
        return None, None
    link = MarketingLink.objects.select_related("event", "organization").filter(
        pk=raw_id,
        is_active=True,
        event=event,
    ).first()
    if not link:
        return None, None
    if timezone.now() - visited_at > timedelta(days=link.attribution_window_days):
        return None, None
    visit = MarketingLinkVisit.objects.filter(
        pk=request.session.get(SESSION_VISIT_ID),
        link=link,
    ).first()
    return link, visit


def _desired_attribution_status(order):
    if order.status == TicketOrderStatus.CONFIRMED:
        return MarketingAttributionStatus.CONFIRMED
    if order.status in {TicketOrderStatus.CANCELLED, TicketOrderStatus.EXPIRED}:
        return MarketingAttributionStatus.REVERSED
    return MarketingAttributionStatus.PENDING


def sync_marketing_attribution(order):
    attribution = MarketingAttribution.objects.filter(order=order).first()
    if not attribution:
        return None
    desired = _desired_attribution_status(order)
    now = timezone.now()
    changed = []
    if attribution.status != desired:
        attribution.status = desired
        changed.append("status")
    if desired == MarketingAttributionStatus.CONFIRMED and not attribution.confirmed_at:
        attribution.confirmed_at = order.confirmed_at or now
        attribution.reversed_at = None
        changed.extend(["confirmed_at", "reversed_at"])
    elif desired == MarketingAttributionStatus.REVERSED and not attribution.reversed_at:
        attribution.reversed_at = now
        changed.append("reversed_at")
    if changed:
        attribution.save(update_fields=list(dict.fromkeys(changed)))
    return attribution


@transaction.atomic
def attribute_order_from_marketing(*, order, request=None, marketing_code=None):
    if MarketingAttribution.objects.filter(order=order).exists():
        return MarketingAttribution.objects.get(order=order)
    link = None
    visit = None
    if marketing_code:
        link = MarketingLink.objects.select_related("event", "organization").filter(
            code=marketing_code,
            is_active=True,
        ).first()
        if not link:
            raise ValidationError("Code source marketing invalide ou inactif.")
        if link.event_id != order.event_id:
            raise ValidationError("Ce lien marketing ne peut pas attribuer cette commande.")
    elif request is not None:
        link, visit = get_session_marketing_link(request, event=order.event)
    if not link:
        return None

    status = _desired_attribution_status(order)
    attribution = MarketingAttribution(
        order=order,
        link=link,
        visit=visit,
        status=status,
        revenue_amount=order.total_amount,
        currency=order.currency,
        confirmed_at=(order.confirmed_at or timezone.now()) if status == MarketingAttributionStatus.CONFIRMED else None,
        reversed_at=timezone.now() if status == MarketingAttributionStatus.REVERSED else None,
    )
    attribution.full_clean()
    attribution.save()
    return attribution


def can_submit_feedback(user, event):
    if not getattr(user, "is_authenticated", False):
        return False
    if event.end_at > timezone.now():
        return False
    return TicketOrder.objects.filter(
        event=event,
        buyer=user,
        status=TicketOrderStatus.CONFIRMED,
    ).exists() or Ticket.objects.filter(
        event=event,
        owner=user,
        order__status=TicketOrderStatus.CONFIRMED,
    ).exists()


@transaction.atomic
def submit_event_feedback(*, user, event, rating, comment=""):
    if not can_submit_feedback(user, event):
        raise PermissionDenied("Le feedback est réservé aux participants après la fin de l'événement.")
    try:
        rating = int(rating)
    except (TypeError, ValueError) as exc:
        raise ValidationError("La note doit être comprise entre 1 et 5.") from exc
    if rating < 1 or rating > 5:
        raise ValidationError("La note doit être comprise entre 1 et 5.")
    feedback, _ = EventFeedback.objects.update_or_create(
        event=event,
        user=user,
        defaults={"rating": rating, "comment": (comment or "").strip()[:2000]},
    )
    return feedback


def _buyer_identity(row):
    if row["buyer_id"]:
        return f"user:{row['buyer_id']}"
    email = (row["customer_email"] or "").strip().lower()
    return f"email:{email}" if email else None


def _currency_totals(rows, amount_key="amount"):
    totals = defaultdict(lambda: ZERO)
    for row in rows:
        totals[(row["currency"] or "").upper()] += row[amount_key] or ZERO
    return {currency: amount for currency, amount in sorted(totals.items()) if currency}


def build_growth_v1_dashboard(organization, user):
    finance_visible = user_can_view_growth_financials(user, organization)
    order_rows = list(
        TicketOrder.objects.filter(
            event__organization=organization,
            status=TicketOrderStatus.CONFIRMED,
        ).values("buyer_id", "customer_email", "currency", "total_amount")
    )
    identities = [identity for identity in (_buyer_identity(row) for row in order_rows) if identity]
    frequency = Counter(identities)
    buyers = len(frequency)
    repeat_buyers = sum(count >= 2 for count in frequency.values())

    confirmed_tickets = Ticket.objects.filter(
        event__organization=organization,
        order__status=TicketOrderStatus.CONFIRMED,
    ).exclude(status=TicketStatus.CANCELLED)
    ticket_count = confirmed_tickets.count()
    used_count = confirmed_tickets.filter(status=TicketStatus.USED).count()
    attendance_rate = round((used_count / ticket_count) * 100, 1) if ticket_count else None

    link_rows = []
    for link in MarketingLink.objects.filter(organization=organization).select_related("event", "crm_campaign"):
        visits = link.visits.count()
        conversions = link.attributions.filter(status=MarketingAttributionStatus.CONFIRMED).count()
        revenue = _currency_totals(
            link.attributions.filter(status=MarketingAttributionStatus.CONFIRMED).values(
                "currency", "revenue_amount"
            ),
            amount_key="revenue_amount",
        )
        link_rows.append(
            {
                "link": link,
                "visits": visits,
                "conversions": conversions,
                "conversion_rate": round((conversions / visits) * 100, 1) if visits else None,
                "revenue": revenue if finance_visible else {},
            }
        )
    link_rows.sort(key=lambda row: (-row["conversions"], -row["visits"], row["link"].name))

    feedback = EventFeedback.objects.filter(event__organization=organization)
    feedback_summary = feedback.aggregate(count=Count("id"), average=Avg("rating"))

    crm_confirmed = CampaignAttribution.objects.filter(
        campaign__organization=organization,
        status=CampaignAttributionStatus.CONFIRMED,
    )
    crm_revenue = _currency_totals(
        crm_confirmed.values("currency", "revenue_amount"), amount_key="revenue_amount"
    ) if finance_visible else {}

    revenue_by_currency = _currency_totals(
        ({"currency": row["currency"], "amount": row["total_amount"]} for row in order_rows)
    ) if finance_visible else {}

    return {
        "organization": organization,
        "finance_visible": finance_visible,
        "followers": OrganizationFollow.objects.filter(organization=organization).count(),
        "buyers": buyers,
        "repeat_buyers": repeat_buyers,
        "repeat_rate": round((repeat_buyers / buyers) * 100, 1) if buyers else None,
        "tickets_sold": ticket_count,
        "attendance_rate": attendance_rate,
        "revenue_by_currency": revenue_by_currency,
        "crm_conversions": crm_confirmed.count(),
        "crm_revenue": crm_revenue,
        "marketing_links": link_rows,
        "marketing_visits": sum(row["visits"] for row in link_rows),
        "marketing_conversions": sum(row["conversions"] for row in link_rows),
        "feedback_count": feedback_summary["count"] or 0,
        "feedback_average": round(float(feedback_summary["average"]), 1) if feedback_summary["average"] else None,
    }


def available_crm_presets(organization):
    rows = []
    for key, definition in PRESET_DEFINITIONS.items():
        rows.append({"key": key, **definition})
    return rows


@transaction.atomic
def activate_crm_preset(*, organization, actor, preset_key, event=None):
    definition = PRESET_DEFINITIONS.get(preset_key)
    if not definition:
        raise ValidationError("Preset CRM inconnu.")
    if definition.get("event_required"):
        if not event:
            raise ValidationError("Ce preset nécessite un événement.")
        if event.organization_id != organization.pk:
            raise ValidationError("L'événement doit appartenir à cette organisation.")
    elif event and event.organization_id != organization.pk:
        raise ValidationError("L'événement doit appartenir à cette organisation.")

    event_suffix = f" — {event.title}" if event else ""
    workflow_name = f"Preset · {definition['label']}{event_suffix}"[:160]
    existing = CRMWorkflow.objects.filter(organization=organization, name=workflow_name).first()
    if existing:
        if not existing.is_active:
            existing.is_active = True
            existing.save(update_fields=["is_active", "updated_at"])
        return existing, False

    workflow = CRMWorkflow(
        organization=organization,
        name=workflow_name,
        description="Preset Growth V1 Makolo. Modifiable ensuite depuis CRM Automation.",
        trigger=definition["trigger"],
        event=event if definition.get("event_required") else None,
        event_offset_minutes=definition.get("offset", 0),
        trigger_grace_minutes=180 if definition["trigger"] == CRMWorkflowTrigger.BEFORE_EVENT else 60,
        is_active=True,
        created_by=actor,
    )
    workflow.full_clean()
    workflow.save()

    title = definition["title"].format(
        organization=organization.name,
        event=event.title if event else "votre événement",
    )
    message = definition["message"].format(
        organization=organization.name,
        event=event.title if event else "votre événement",
    )
    action = CRMWorkflowAction(
        workflow=workflow,
        position=1,
        kind=CRMWorkflowActionKind.IN_APP_NOTIFICATION,
        delay_minutes=0,
        title=title,
        message=message,
        marketing_action=definition.get("marketing", False),
        is_active=True,
    )
    action.full_clean()
    action.save()
    return workflow, True
