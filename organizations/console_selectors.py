from __future__ import annotations

from django.db.models import Count, Min, Prefetch, Q, Sum
from django.utils import timezone

from access.models import Access, AccessStatus, AccessUse
from activities.models import Activity, Occurrence
from automation.models import AutomationExecution, AutomationRule, DomainAutomationExecutionStatus
from authorization.constants import PermissionCode, STANDARD_SPACE_ROLE_CODES
from authorization.models import AuthorityScope
from authorization.selectors import current_mandates
from authorization.services import activity_ids_with_permission
from capacity.models import CapacityPool
from capacity.selectors import capacity_availability
from commerce.models import CommerceOrder, CommerceOrderStatus, Offer
from crm.models import AudienceSegment, CRMContact
from geography.models import SpacePlace
from groups.models import Group
from journeys.models import Journey, JourneyRequest, RequestStatus
from operations.models import IncidentStatus, OperationsIncident
from payments.models import Payment, PaymentStatus
from promotions.models import Promotion


def _visible_modules(context):
    return {item["key"] for group in context.navigation_groups for item in group["items"]}


def _activity_queryset(context):
    queryset = Activity.objects.filter(space=context.space)
    if context.activity_ids is not None:
        queryset = queryset.filter(pk__in=context.activity_ids)
    return queryset


def activities_for_console(context):
    next_occurrences = Occurrence.objects.filter(start_at__gte=timezone.now()).order_by("start_at", "id")
    return (
        _activity_queryset(context)
        .annotate(next_occurrence_at=Min("occurrences__start_at", filter=Q(occurrences__start_at__gte=timezone.now())))
        .prefetch_related(Prefetch("occurrences", queryset=next_occurrences, to_attr="future_occurrences"))
        .order_by("title", "id")
    )


def activities_manageable_for_access(context):
    queryset = Activity.objects.filter(space=context.space)
    allowed = activity_ids_with_permission(context.profile, PermissionCode.ACTIVITY_ACCESS_MANAGE)
    if allowed is not None:
        queryset = queryset.filter(pk__in=allowed)
    return queryset.order_by("title", "id")


def activity_for_console(context, activity_id):
    return (
        activities_for_console(context)
        .prefetch_related("occurrences__place_links__place", "offers", "capacity_pools")
        .filter(pk=activity_id)
        .first()
    )


def upcoming_occurrences(context, *, limit=8):
    return (
        Occurrence.objects.filter(activity__in=_activity_queryset(context), start_at__gte=timezone.now())
        .select_related("activity")
        .prefetch_related("place_links__place")
        .order_by("start_at", "id")[:limit]
    )


def requests_for_console(context):
    return (
        JourneyRequest.objects.filter(journey__activity__in=_activity_queryset(context))
        .select_related("journey", "journey__activity", "journey__occurrence", "journey__beneficiary", "requester", "decided_by")
        .order_by("-submitted_at", "id")
    )


def accesses_for_console(context):
    return (
        Access.objects.filter(activity__in=_activity_queryset(context))
        .select_related("beneficiary", "activity", "occurrence", "journey", "issued_by")
        .prefetch_related("uses")
        .order_by("-created_at", "id")
    )


def access_uses_for_console(context):
    return (
        AccessUse.objects.filter(access__activity__in=_activity_queryset(context))
        .select_related("access", "access__beneficiary", "access__activity", "occurrence", "actor")
        .order_by("-used_at", "id")
    )


def offers_for_console(context):
    return (
        Offer.objects.filter(activity__in=_activity_queryset(context))
        .select_related("activity", "occurrence", "capacity_pool")
        .order_by("activity__title", "unit_price", "name", "id")
    )


def capacity_for_console(context):
    pools = list(
        CapacityPool.objects.filter(activity__in=_activity_queryset(context))
        .select_related("activity", "occurrence")
        .order_by("activity__title", "occurrence__start_at", "label", "id")
    )
    for pool in pools:
        pool.console_availability = capacity_availability(pool)
    return pools


def orders_for_console(context):
    queryset = CommerceOrder.objects.filter(payee_space=context.space)
    if context.activity_ids is not None:
        queryset = queryset.filter(journey__activity_id__in=context.activity_ids)
    return queryset.select_related("buyer", "journey", "journey__activity", "journey__occurrence").prefetch_related("payments").order_by("-created_at", "id")


def payments_for_console(context):
    queryset = Payment.objects.filter(commerce_order__payee_space=context.space, commerce_order__isnull=False)
    if context.activity_ids is not None:
        queryset = queryset.filter(commerce_order__journey__activity_id__in=context.activity_ids)
    return queryset.select_related("commerce_order", "commerce_order__journey", "commerce_order__journey__activity").order_by("-created_at", "id")


def team_for_console(context):
    team = context.space.teams.filter(is_default=True, is_active=True).first()
    if team is None:
        return []
    memberships = list(team.memberships.select_related("user").order_by("user__email"))
    profile_ids = [membership.user_id for membership in memberships]
    mandates = list(
        current_mandates()
        .filter(profile_id__in=profile_ids)
        .filter(
            Q(scope_type=AuthorityScope.SPACE, space=context.space)
            | Q(scope_type=AuthorityScope.ACTIVITY, activity__space=context.space)
        )
        .select_related("role", "activity", "profile")
        .order_by("profile__email", "activity__title", "role__name", "pk")
    )
    mandates_by_profile = {}
    for mandate in mandates:
        mandates_by_profile.setdefault(mandate.profile_id, []).append(mandate)
    for membership in memberships:
        member_mandates = mandates_by_profile.get(membership.user_id, [])
        space_mandates = [m for m in member_mandates if m.scope_type == AuthorityScope.SPACE]
        membership.console_mandates = space_mandates
        membership.console_standard_space_mandate = next(
            (
                m
                for m in space_mandates
                if m.role.is_system and m.role.code in STANDARD_SPACE_ROLE_CODES
            ),
            None,
        )
        membership.console_custom_space_mandates = [m for m in space_mandates if not m.role.is_system]
        membership.console_activity_mandates = [m for m in member_mandates if m.scope_type == AuthorityScope.ACTIVITY]
    return memberships


def groups_for_console(context):
    return Group.objects.filter(space=context.space).annotate(member_count=Count("memberships", filter=Q(memberships__status="active"))).order_by("name")


def places_for_console(context):
    return SpacePlace.objects.filter(organization=context.space, is_active=True).select_related("place").order_by("position", "role", "place__name")


def contacts_for_console(context):
    return CRMContact.objects.filter(organization=context.space).select_related("user").order_by("name", "email")


def audiences_for_console(context):
    return AudienceSegment.objects.filter(organization=context.space).select_related("event").order_by("name")


def promotions_for_console(context):
    return Promotion.objects.filter(organization=context.space).select_related("event").order_by("name")


def incidents_for_console(context):
    queryset = OperationsIncident.objects.filter(Q(organization=context.space) | Q(activity__space=context.space))
    if context.activity_ids is not None:
        queryset = queryset.filter(activity_id__in=context.activity_ids)
    return queryset.select_related("activity", "occurrence").order_by("-created_at")


def automation_rules_for_console(context):
    queryset = AutomationRule.objects.filter(space=context.space)
    if context.activity_ids is not None:
        queryset = queryset.filter(Q(activity_id__in=context.activity_ids) | Q(activity__isnull=True))
    return queryset.select_related("activity").prefetch_related("executions").order_by("name", "id")


def analytics_summary(context):
    visible = _visible_modules(context)
    activities = _activity_queryset(context)
    summary = {}
    if "activities" in visible:
        summary["activities"] = activities.count()
    if "requests" in visible:
        summary["journeys"] = Journey.objects.filter(activity__in=activities).count()
    if "access" in visible:
        accesses = Access.objects.filter(activity__in=activities)
        summary["accesses"] = accesses.count()
        summary["used_accesses"] = accesses.filter(status=AccessStatus.USED).count()
    if "orders" in visible:
        summary["orders"] = orders_for_console(context).count()
    if "payments" in visible and context.can_view_finance:
        payments = payments_for_console(context)
        summary.update(
            {
                "payments": payments.count(),
                "payments_succeeded": payments.filter(status=PaymentStatus.SUCCEEDED).count(),
                "revenue_by_currency": list(payments.filter(status=PaymentStatus.SUCCEEDED).values("currency").annotate(total=Sum("amount")).order_by("currency")),
            }
        )
    return summary


def overview_for_console(context):
    visible = _visible_modules(context)
    action_items = {}
    pending_requests = JourneyRequest.objects.none()
    open_incidents = OperationsIncident.objects.none()
    critical_capacity = []

    if "requests" in visible:
        pending_requests = requests_for_console(context).filter(status=RequestStatus.PENDING)
        action_items["requests"] = pending_requests.count()
    if "operations" in visible:
        open_incidents = incidents_for_console(context).exclude(status__in={IncidentStatus.RESOLVED, IncidentStatus.DISMISSED})
        action_items["incidents"] = open_incidents.count()
    if "orders" in visible:
        action_items["orders"] = orders_for_console(context).filter(status=CommerceOrderStatus.PENDING).count()
    if "payments" in visible and context.can_view_finance:
        action_items["payments"] = payments_for_console(context).filter(status__in={PaymentStatus.PENDING, PaymentStatus.FAILED}).count()
    if "automation" in visible:
        action_items["automations"] = AutomationExecution.objects.filter(rule__space=context.space, status=DomainAutomationExecutionStatus.FAILED).count()
    if "offers" in visible:
        for pool in capacity_for_console(context):
            availability = pool.console_availability
            if availability.unlimited or availability.total in {None, 0}:
                continue
            if availability.available / availability.total <= 0.15:
                critical_capacity.append(pool)
        action_items["capacity"] = len(critical_capacity)

    occurrences = upcoming_occurrences(context, limit=6) if "activities" in visible else []
    return {
        "action_items": action_items,
        "pending_requests": pending_requests[:5],
        "open_incidents": open_incidents[:5],
        "critical_capacity": critical_capacity[:5],
        "upcoming_occurrences": occurrences,
        "analytics": analytics_summary(context),
    }
