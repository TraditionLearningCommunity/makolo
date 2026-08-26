import base64
from io import BytesIO

import qrcode
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView

from access.models import CredentialStatus, CredentialType
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
    participant_accesses_visible_to_buyer,
    participant_actionable_journeys,
    participant_active_accesses,
    participant_active_journeys,
    participant_history_journeys,
    participant_journeys,
    participant_purchased_accesses_for_others,
    participant_upcoming_accesses,
)


PERSONAL_SEARCH_MAX_LENGTH = 120
PERSONAL_PAGE_SIZE = 24


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


def _search_value(request):
    return (request.GET.get("q") or "").strip()[:PERSONAL_SEARCH_MAX_LENGTH]


def _journey_search(queryset, q):
    if not q:
        return queryset
    return queryset.filter(
        Q(activity__title__icontains=q)
        | Q(activity__space__name__icontains=q)
        | Q(activity__owner_profile__first_name__icontains=q)
        | Q(activity__owner_profile__last_name__icontains=q)
        | Q(activity__owner_profile__username__icontains=q)
        | Q(occurrence__place_links__place__name__icontains=q)
        | Q(occurrence__place_links__place__locality__icontains=q)
        | Q(activity__transport_service__route__name__icontains=q)
        | Q(activity__transport_service__route__stops__place__name__icontains=q)
        | Q(activity__transport_service__route__stops__place__locality__icontains=q)
    ).distinct()


def _access_search(queryset, q, *, include_external_holder=False):
    if not q:
        return queryset
    lookup = (
        Q(activity__title__icontains=q)
        | Q(activity__space__name__icontains=q)
        | Q(activity__owner_profile__first_name__icontains=q)
        | Q(activity__owner_profile__last_name__icontains=q)
        | Q(activity__owner_profile__username__icontains=q)
        | Q(occurrence__place_links__place__name__icontains=q)
        | Q(occurrence__place_links__place__locality__icontains=q)
        | Q(activity__transport_service__route__name__icontains=q)
        | Q(activity__transport_service__route__stops__place__name__icontains=q)
        | Q(activity__transport_service__route__stops__place__locality__icontains=q)
    )
    if include_external_holder:
        lookup |= Q(external_beneficiary__display_name__icontains=q)
    return queryset.filter(lookup).distinct()


def _pagination_query(request, *page_keys):
    params = request.GET.copy()
    for key in page_keys:
        params.pop(key, None)
    return params.urlencode()


class ParticipantHomeView(LoginRequiredMixin, TemplateView):
    template_name = "core/participant_home.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = self.request.user
        actionable = list(participant_actionable_journeys(profile)[:5])
        upcoming_accesses = list(participant_upcoming_accesses(profile)[:5])
        context.update(
            {
                "actionable": [_journey_card(j) for j in actionable],
                "upcoming": [_access_card(a) for a in upcoming_accesses],
                "active_accesses": [_access_card(a) for a in upcoming_accesses],
                "recent_journeys": [_journey_card(j) for j in participant_journeys(profile)[:5]],
                "organized_activities": list(activities_owned_by(profile)[:5]),
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

        active = _journey_search(active, q).order_by("-updated_at", "-created_at", "id")
        history = _journey_search(participant_history_journeys(profile), q).order_by("-updated_at", "-created_at", "id")
        active_page = Paginator(active, PERSONAL_PAGE_SIZE).get_page(self.request.GET.get("active_page"))
        history_page = Paginator(history, PERSONAL_PAGE_SIZE).get_page(self.request.GET.get("history_page"))
        context.update(
            {
                "q": q,
                "status_filter": status_filter,
                "active_journeys": [_journey_card(j) for j in active_page.object_list],
                "history_journeys": [_journey_card(j) for j in history_page.object_list],
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
        pending_request = next((r for r in journey.requests.all() if r.status == RequestStatus.PENDING), None)
        rejected_request = next((r for r in journey.requests.all() if r.status == RequestStatus.REJECTED), None)
        order = card["order"]
        payment_url = None
        if order and journey.status == JourneyStatus.PENDING_PAYMENT and order.payment_mode in {PaymentMode.UPFRONT, PaymentMode.AFTER_APPROVAL}:
            payment_url = reverse("payments:commerce-start", kwargs={"order_pk": order.pk})
        context.update(
            {
                **card,
                "progress": journey_progress(journey),
                "pending_request": pending_request,
                "rejected_request": rejected_request,
                "payment_url": payment_url,
                "can_respond_invitation": journey.workflow == WorkflowKind.INVITATION and journey.status == JourneyStatus.SUBMITTED,
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
        active = _access_search(participant_active_accesses(profile), q).order_by("occurrence__start_at", "-created_at", "id")
        history = _access_search(participant_access_history(profile), q).order_by("-created_at", "id")
        purchased = _access_search(
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
                "active_accesses": [_access_card(a) for a in active_page.object_list],
                "history_accesses": [_access_card(a) for a in history_page.object_list],
                "purchased_for_others": [_access_card(a) for a in purchased_page.object_list],
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
            (c for c in access.credentials.all() if c.status == CredentialStatus.ACTIVE and c.credential_type == CredentialType.QR),
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
