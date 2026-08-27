import base64
from io import BytesIO

import qrcode
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Case, IntegerField, Q, When
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from access.models import AccessStatus, CredentialStatus, CredentialType
from access.services import render_access_credential
from activities.selectors import activities_owned_by
from commerce.models import PaymentMode
from journeys.models import JourneyStatus, RequestStatus, WorkflowKind

from .participant_actions import participant_accept_invitation, participant_decline_invitation
from .participant_presentation import (
    access_status_label,
    journey_progress,
    journey_status_label,
    next_participant_action,
    occurrence_timing,
    payment_mode_label,
    vocabulary_for,
)
from .participant_selectors import (
    participant_access_history,
    participant_access_search,
    participant_accesses_visible_to_buyer,
    participant_actionable_journeys,
    participant_active_accesses,
    participant_active_journeys,
    participant_history_journeys,
    participant_journey_search,
    participant_journeys,
    participant_purchased_accesses_for_others,
    participant_unified_history_accesses,
    participant_unified_history_journeys,
    participant_upcoming_engagements,
)


PERSONAL_SEARCH_MAX_LENGTH = 120
PERSONAL_PAGE_SIZE = 24
HOME_SECTION_LIMIT = 5


def _primary_place(occurrence):
    if not occurrence:
        return None
    links = list(occurrence.place_links.all())
    primary = next((link for link in links if link.role == "primary"), None)
    return (primary or (links[0] if links else None)).place if links else None


def _journey_card(journey):
    order = next(iter(journey.commerce_orders.all()), None)
    access = next(iter(journey.accesses.all()), None)
    return {
        "journey": journey,
        "status_label": journey_status_label(journey.status),
        "next_action": next_participant_action(journey),
        "vocabulary": vocabulary_for(activity=journey.activity, workflow=journey.workflow),
        "place": _primary_place(journey.occurrence),
        "timing": occurrence_timing(journey.occurrence),
        "order": order,
        "access": access,
        "payment_label": payment_mode_label(order.payment_mode) if order else "",
    }


def _access_card(access):
    return {
        "access": access,
        "status_label": access_status_label(access.status),
        "vocabulary": vocabulary_for(activity=access.activity, workflow=getattr(access.journey, "workflow", None)),
        "place": _primary_place(access.occurrence),
        "timing": occurrence_timing(access.occurrence),
        "holder_name": access.beneficiary_display_name,
        "external_holder": access.is_external_beneficiary,
    }


def _history_access_label(access):
    if access.status == AccessStatus.USED:
        return "Participé"
    if access.status == AccessStatus.CANCELLED:
        return "Annulé"
    if access.status == AccessStatus.REVOKED:
        return "Révoqué"
    if access.status == AccessStatus.TRANSFERRED:
        return "Transféré"
    if access.status == AccessStatus.EXPIRED:
        return "Expiré"
    if access.status == AccessStatus.VALID:
        return "Terminé"
    return access_status_label(access.status)


def _history_journey_label(journey):
    labels = {
        JourneyStatus.FULFILLED: "Démarche terminée",
        JourneyStatus.REJECTED: "Demande refusée",
        JourneyStatus.CANCELLED: "Démarche annulée",
        JourneyStatus.EXPIRED: "Démarche expirée",
    }
    return labels.get(journey.status, journey_status_label(journey.status))


def _history_access_item(access):
    return {
        "kind": "access",
        "history_at": getattr(access, "history_at", access.updated_at),
        "label": _history_access_label(access),
        "access_card": _access_card(access),
        "journey_card": _journey_card(access.journey) if access.journey_id else None,
        "activity": access.activity,
    }


def _history_journey_item(journey):
    return {
        "kind": "journey",
        "history_at": journey.updated_at,
        "label": _history_journey_label(journey),
        "access_card": None,
        "journey_card": _journey_card(journey),
        "activity": journey.activity,
    }


def _history_items(*, profile, q="", history_filter="all", offset=0, limit=PERSONAL_PAGE_SIZE, at=None):
    """Compose a bounded unified history window from canonical personal querysets."""
    at = at or timezone.now()
    history_filter = history_filter if history_filter in {"all", "accesses", "journeys"} else "all"
    access_qs = participant_access_search(participant_unified_history_accesses(profile, at=at), q)
    journey_qs = participant_journey_search(participant_unified_history_journeys(profile), q)

    access_count = access_qs.count() if history_filter in {"all", "accesses"} else 0
    journey_count = journey_qs.count() if history_filter in {"all", "journeys"} else 0
    window_end = offset + limit
    candidates = []
    if history_filter in {"all", "accesses"}:
        candidates.extend(_history_access_item(access) for access in access_qs[:window_end])
    if history_filter in {"all", "journeys"}:
        candidates.extend(_history_journey_item(journey) for journey in journey_qs[:window_end])
    candidates.sort(key=lambda item: item["history_at"], reverse=True)
    return candidates[offset:window_end], access_count + journey_count, history_filter


def _recent_history_items(profile, *, at=None, limit=HOME_SECTION_LIMIT):
    items, _, _ = _history_items(profile=profile, offset=0, limit=limit, at=at)
    return items


def _search_value(request):
    return (request.GET.get("q") or "").strip()[:PERSONAL_SEARCH_MAX_LENGTH]


def _pagination_query(request, *page_keys):
    params = request.GET.copy()
    for key in page_keys:
        params.pop(key, None)
    return params.urlencode()


def _prioritized_actionable(profile):
    return (
        participant_actionable_journeys(profile)
        .annotate(
            attention_priority=Case(
                When(status=JourneyStatus.PENDING_PAYMENT, then=1),
                When(status=JourneyStatus.SUBMITTED, workflow=WorkflowKind.INVITATION, then=2),
                When(status=JourneyStatus.PENDING_APPROVAL, then=3),
                When(status=JourneyStatus.DRAFT, then=4),
                default=5,
                output_field=IntegerField(),
            )
        )
        .order_by("attention_priority", "updated_at", "created_at", "id")
    )


class ParticipantHomeView(LoginRequiredMixin, TemplateView):
    template_name = "core/participant_home.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = self.request.user
        now = timezone.now()
        actionable = list(_prioritized_actionable(profile)[:HOME_SECTION_LIMIT])
        upcoming = list(participant_upcoming_engagements(profile, at=now)[:HOME_SECTION_LIMIT])
        active_access_count = participant_active_accesses(profile, at=now).count()
        context.update(
            {
                "actionable": [_journey_card(journey) for journey in actionable],
                "upcoming": [_access_card(access) for access in upcoming],
                "active_access_count": active_access_count,
                "recent_history": _recent_history_items(profile, at=now),
                "organized_activities": list(activities_owned_by(profile)[:HOME_SECTION_LIMIT]),
            }
        )
        return context


class ParticipantHistoryView(LoginRequiredMixin, TemplateView):
    template_name = "core/participant_history.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = self.request.user
        q = _search_value(self.request)
        requested_filter = (self.request.GET.get("type") or "all").strip().lower()
        page_number = self.request.GET.get("page") or 1

        # Use a cheap count-only paginator to calculate offset/links, then replace
        # the page's object_list with a bounded cross-domain history window.
        access_qs = participant_access_search(participant_unified_history_accesses(profile), q)
        journey_qs = participant_journey_search(participant_unified_history_journeys(profile), q)
        if requested_filter == "accesses":
            total_count = access_qs.count()
        elif requested_filter == "journeys":
            total_count = journey_qs.count()
        else:
            requested_filter = "all"
            total_count = access_qs.count() + journey_qs.count()

        paginator = Paginator(range(total_count), PERSONAL_PAGE_SIZE)
        page_obj = paginator.get_page(page_number)
        offset = (page_obj.number - 1) * PERSONAL_PAGE_SIZE
        items, _, history_filter = _history_items(
            profile=profile,
            q=q,
            history_filter=requested_filter,
            offset=offset,
            limit=PERSONAL_PAGE_SIZE,
        )
        page_obj.object_list = items
        context.update(
            {
                "q": q,
                "history_filter": history_filter,
                "history_items": items,
                "page_obj": page_obj,
                "pagination_query": _pagination_query(self.request, "page"),
            }
        )
        return context


class ParticipantJourneyListView(LoginRequiredMixin, TemplateView):
    template_name = "core/participant_journey_list.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = self.request.user
        q = _search_value(self.request)
        status_filter = (self.request.GET.get("status") or "all").strip().lower()

        active = participant_active_journeys(profile)
        if status_filter == "action":
            active = participant_actionable_journeys(profile)
        elif status_filter == "pending":
            active = active.filter(status__in={JourneyStatus.SUBMITTED, JourneyStatus.PENDING_APPROVAL})
        elif status_filter == "payment":
            active = active.filter(status=JourneyStatus.PENDING_PAYMENT)
        elif status_filter != "all":
            status_filter = "all"

        active = participant_journey_search(active, q).order_by("-updated_at", "-created_at", "id")
        history = participant_journey_search(participant_history_journeys(profile), q).order_by(
            "-updated_at", "-created_at", "id"
        )
        active_page = Paginator(active, PERSONAL_PAGE_SIZE).get_page(self.request.GET.get("active_page"))
        history_page = Paginator(history, PERSONAL_PAGE_SIZE).get_page(self.request.GET.get("history_page"))
        context.update(
            {
                "q": q,
                "status_filter": status_filter,
                "active_journeys": [_journey_card(journey) for journey in active_page.object_list],
                "history_journeys": [_journey_card(journey) for journey in history_page.object_list],
                "active_page_obj": active_page,
                "history_page_obj": history_page,
                "pagination_query": _pagination_query(self.request, "active_page", "history_page"),
            }
        )
        return context


class ParticipantJourneyDetailView(LoginRequiredMixin, TemplateView):
    template_name = "core/participant_journey_detail.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        journey = get_object_or_404(participant_journeys(self.request.user), pk=kwargs["pk"])
        card = _journey_card(journey)
        pending_request = next((request for request in journey.requests.all() if request.status == RequestStatus.PENDING), None)
        rejected_request = next((request for request in journey.requests.all() if request.status == RequestStatus.REJECTED), None)
        order = card["order"]
        payment_url = None
        if order and journey.status == JourneyStatus.PENDING_PAYMENT and order.payment_mode in {
            PaymentMode.UPFRONT,
            PaymentMode.AFTER_APPROVAL,
        }:
            payment_url = reverse("payments:commerce-start", kwargs={"order_pk": order.pk})
        context.update(
            {
                **card,
                "progress": journey_progress(journey),
                "pending_request": pending_request,
                "rejected_request": rejected_request,
                "payment_url": payment_url,
                "can_respond_invitation": journey.workflow == WorkflowKind.INVITATION
                and journey.status == JourneyStatus.SUBMITTED,
            }
        )
        return context


class ParticipantInvitationAcceptView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        journey = get_object_or_404(participant_journeys(request.user), pk=pk)
        try:
            _, access = participant_accept_invitation(journey=journey, actor=request.user)
        except ValidationError:
            messages.error(request, "Cette invitation ne peut plus être acceptée.")
            return redirect("core:participant-journey-detail", pk=journey.pk)
        messages.success(request, "Invitation acceptée. Votre accès est disponible.")
        return redirect("core:participant-access-detail", pk=access.pk)


class ParticipantInvitationDeclineView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        journey = get_object_or_404(participant_journeys(request.user), pk=pk)
        try:
            participant_decline_invitation(journey=journey, actor=request.user)
        except ValidationError:
            messages.error(request, "Cette invitation ne peut plus être refusée.")
        else:
            messages.success(request, "Invitation refusée.")
        return redirect("core:participant-journey-detail", pk=journey.pk)


class ParticipantAccessListView(LoginRequiredMixin, TemplateView):
    template_name = "core/participant_access_list.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = self.request.user
        q = _search_value(self.request)
        active = participant_access_search(participant_active_accesses(profile), q).order_by(
            "occurrence__start_at", "-created_at", "id"
        )
        history = participant_access_search(participant_access_history(profile), q).order_by("-created_at", "id")
        purchased = participant_access_search(
            participant_purchased_accesses_for_others(profile),
            q,
            include_external_holder=True,
        )
        active_page = Paginator(active, PERSONAL_PAGE_SIZE).get_page(self.request.GET.get("active_page"))
        history_page = Paginator(history, PERSONAL_PAGE_SIZE).get_page(self.request.GET.get("history_page"))
        purchased_page = Paginator(purchased, PERSONAL_PAGE_SIZE).get_page(self.request.GET.get("purchased_page"))
        context.update(
            {
                "q": q,
                "active_accesses": [_access_card(access) for access in active_page.object_list],
                "history_accesses": [_access_card(access) for access in history_page.object_list],
                "purchased_for_others": [_access_card(access) for access in purchased_page.object_list],
                "active_page_obj": active_page,
                "history_page_obj": history_page,
                "purchased_page_obj": purchased_page,
                "pagination_query": _pagination_query(
                    self.request,
                    "active_page",
                    "history_page",
                    "purchased_page",
                ),
            }
        )
        return context


class ParticipantAccessDetailView(LoginRequiredMixin, TemplateView):
    template_name = "core/participant_access_detail.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        access = get_object_or_404(participant_accesses_visible_to_buyer(self.request.user), pk=kwargs["pk"])
        card = _access_card(access)
        credential = next(
            (
                credential
                for credential in access.credentials.all()
                if credential.status == CredentialStatus.ACTIVE and credential.credential_type == CredentialType.QR
            ),
            None,
        )
        qr_data = None
        if credential:
            token = render_access_credential(credential)
            image = qrcode.make(token)
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            qr_data = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
        context.update(
            {
                **card,
                "credential": credential,
                "qr_data": qr_data,
                "viewing_as_buyer": access.beneficiary_id != self.request.user.pk,
                "operator_name": access.activity.operator_display_name,
            }
        )
        return context
