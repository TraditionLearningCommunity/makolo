from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import models
from django.shortcuts import redirect
from django.urls import reverse

from core.mark_orchestration import MARK_TEXT_MAX_LENGTH, mark_web_url, orchestrate_mark
from django.utils import timezone
from django.views.generic import TemplateView

from activities.models import ActivityStatus
from discovery.models import ActivityBookmark, DiscoveryWatch
from funding.models import FundingDetails
from funding.services import can_manage_funding
from groups.selectors import groups_for_profile
from organizations.console_context import authorized_spaces
from organizations.models import OrganizationFollow, ProfileFollow, TeamMembership, TeamMembershipStatus
from objectives.models import DossierLifecycle, ProjectLifecycle
from objectives.selectors import dossiers_for_profile, projects_for_profile
from partners.models import Partner, PartnerStatus
from payments.models import PaymentStatus
from payments.selectors import get_payments_visible_to
from recognition.selectors import account_for_profile, redemptions_requiring_beneficiary_response
from loyalty.selectors import get_accounts_visible_to, get_subscriptions_visible_to
from tickets.models import TransferStatus, WaitlistStatus
from tickets.selectors import get_ticket_transfers_visible_to, get_waitlist_entries_visible_to
from personal_assets.selectors import personal_assets_for_controller
from readiness import ReadinessStatus, resolve_many
from readiness.selectors import readiness_queryset
from topics.models import ProfileInterest, ProfileOpenTo
from trust.credential_selectors import credentials_for_profile
from trust.selectors import proofs_for_profile

from .participant_selectors import participant_active_accesses, participant_active_journeys
from .participant_views import HOME_READINESS_CANDIDATE_LIMIT, _access_card, _journey_card


ONGOING_LIMIT = 18
ME_PREVIEW_LIMIT = 6


def _ongoing_journey_item(card):
    journey = card["journey"]
    readiness = card["readiness"]
    status = readiness.status if readiness is not None else None

    if status == ReadinessStatus.BLOCKED:
        summary = "Quelque chose empêche la suite."
        tone = "attention"
    elif status == ReadinessStatus.ACTION_REQUIRED:
        summary = "Une action de votre part permet d’avancer."
        tone = "action"
    elif status == ReadinessStatus.WAITING:
        summary = "Vous avez fait votre part. Ça suit son cours."
        tone = "calm"
    elif status == ReadinessStatus.READY:
        summary = "Tout est prêt pour la suite."
        tone = "ready"
    else:
        summary = "Cette démarche continue."
        tone = "calm"

    return {
        "kind": "journey",
        "title": journey.activity.title,
        "summary": summary,
        "tone": tone,
        "next_action": card["next_action"] if status in {ReadinessStatus.BLOCKED, ReadinessStatus.ACTION_REQUIRED} else "",
        "timing": card["timing"],
        "place": card["place"],
        "url": reverse("core:participant-journey-detail", kwargs={"pk": journey.pk}),
    }


def _ongoing_access_item(card):
    access = card["access"]
    return {
        "kind": "access",
        "title": access.activity.title,
        "summary": "Votre accès est déjà disponible.",
        "tone": "ready",
        "next_action": "",
        "timing": card["timing"],
        "place": card["place"],
        "url": reverse("core:participant-access-detail", kwargs={"pk": access.pk}),
    }


def _ongoing_dossier_item(dossier):
    return {
        "kind": "dossier",
        "title": dossier.title,
        "summary": "Cet objectif composé continue.",
        "tone": "calm",
        "next_action": "",
        "timing": None,
        "place": None,
        "url": reverse("objectives:dossier-detail", kwargs={"dossier_id": dossier.pk}),
    }


def _ongoing_project_item(project):
    return {
        "kind": "project",
        "title": project.title,
        "summary": "Cet horizon durable est toujours actif.",
        "tone": "calm",
        "next_action": "",
        "timing": None,
        "place": None,
        "url": reverse("objectives:project-detail", kwargs={"project_id": project.pk}),
    }


def _ongoing_waitlist_item(entry):
    offered = entry.status == WaitlistStatus.OFFERED and entry.is_offer_active
    return {
        "kind": "waitlist",
        "title": entry.ticket_type.event.title,
        "summary": "Une place vous est proposée." if offered else "Vous attendez qu’une place se libère.",
        "tone": "action" if offered else "calm",
        "next_action": "Répondre à l’offre" if offered else "",
        "timing": None,
        "place": None,
        "url": reverse("tickets:waitlist-list"),
    }


def _ongoing_transfer_item(transfer, profile):
    incoming = transfer.recipient_id == profile.pk
    return {
        "kind": "transfer",
        "title": transfer.ticket.event.title,
        "summary": "Un transfert attend votre décision." if incoming else "Votre transfert attend la réponse du destinataire.",
        "tone": "action" if incoming else "calm",
        "next_action": "Accepter ou refuser" if incoming else "",
        "timing": None,
        "place": None,
        "url": reverse("tickets:transfer-list"),
    }


def _ongoing_payment_item(payment):
    return {
        "kind": "payment",
        "title": "Paiement en cours",
        "summary": f"{payment.amount} {payment.currency} · {payment.get_status_display()}",
        "tone": "calm",
        "next_action": "",
        "timing": None,
        "place": None,
        "url": reverse("payments:detail", kwargs={"pk": payment.pk}),
    }


def _ongoing_funding_item(funding):
    target = f" · objectif {funding.target_amount} {funding.currency}" if funding.target_amount else ""
    return {
        "kind": "funding",
        "title": funding.activity.title,
        "summary": f"Financement {funding.activity.get_status_display().lower()}{target}",
        "tone": "calm",
        "next_action": "",
        "timing": None,
        "place": None,
        "url": reverse("funding:manage", kwargs={"pk": funding.pk}),
    }


class MatureParticipantOngoingView(LoginRequiredMixin, TemplateView):
    template_name = "core/participant_ongoing.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = self.request.user
        now = timezone.now()

        journeys = list(
            readiness_queryset(
                participant_active_journeys(profile).order_by("-updated_at", "-created_at", "id")
            )[:HOME_READINESS_CANDIDATE_LIMIT]
        )
        readiness_by_id = resolve_many(journeys, viewer=profile, observed_at=now)
        journey_items = [
            _ongoing_journey_item(_journey_card(journey, readiness=readiness_by_id[journey.pk]))
            for journey in journeys[:ONGOING_LIMIT]
        ]

        active_accesses = list(
            participant_active_accesses(profile, at=now)
            .order_by("occurrence__start_date", "occurrence__start_time", "id")[:ONGOING_LIMIT]
        )
        access_items = [_ongoing_access_item(_access_card(access)) for access in active_accesses]

        personal_dossiers = list(
            dossiers_for_profile(profile)
            .filter(owner_profile=profile, lifecycle__in={DossierLifecycle.DRAFT, DossierLifecycle.ACTIVE})
            .order_by("-updated_at", "id")[:ONGOING_LIMIT]
        )
        dossier_items = [_ongoing_dossier_item(dossier) for dossier in personal_dossiers]

        personal_projects = list(
            projects_for_profile(profile)
            .filter(owner_profile=profile, lifecycle__in={ProjectLifecycle.DRAFT, ProjectLifecycle.ACTIVE})
            .order_by("-updated_at", "id")[:ONGOING_LIMIT]
        )
        project_items = [_ongoing_project_item(project) for project in personal_projects]

        waitlist_entries = list(
            get_waitlist_entries_visible_to(profile)
            .filter(user=profile, status__in={WaitlistStatus.WAITING, WaitlistStatus.OFFERED})
            .order_by("created_at", "id")[:ONGOING_LIMIT]
        )
        waitlist_items = [_ongoing_waitlist_item(entry) for entry in waitlist_entries]

        transfers = list(
            get_ticket_transfers_visible_to(profile)
            .filter(status=TransferStatus.PENDING)
            .filter(models.Q(sender=profile) | models.Q(recipient=profile))
            .order_by("-created_at", "id")[:ONGOING_LIMIT]
        )
        transfer_items = [_ongoing_transfer_item(transfer, profile) for transfer in transfers if transfer.is_pending_active]

        standalone_payments = list(
            get_payments_visible_to(profile)
            .filter(
                initiated_by=profile,
                status__in={PaymentStatus.PENDING, PaymentStatus.PROCESSING},
                commerce_order__journey__isnull=True,
                obligation__journey__isnull=True,
                order__journey__isnull=True,
            )
            .order_by("-created_at", "id")[:ONGOING_LIMIT]
        )
        payment_items = [_ongoing_payment_item(payment) for payment in standalone_payments]

        personal_fundings = [
            funding
            for funding in FundingDetails.objects.select_related("activity")
            .filter(
                activity__owner_profile=profile,
                activity__space__isnull=True,
                activity__status__in={ActivityStatus.DRAFT, ActivityStatus.PUBLISHED},
            )
            .order_by("-activity__updated_at", "-id")[:ONGOING_LIMIT]
            if can_manage_funding(profile, funding)
        ]
        funding_items = [_ongoing_funding_item(funding) for funding in personal_fundings]

        context["ongoing_items"] = (
            journey_items
            + access_items
            + dossier_items
            + project_items
            + waitlist_items
            + transfer_items
            + payment_items
            + funding_items
        )[:ONGOING_LIMIT]
        context["has_personal_dossiers"] = bool(personal_dossiers)
        context["has_personal_projects"] = bool(personal_projects)
        context["has_waitlist"] = bool(waitlist_entries)
        context["has_transfers"] = bool(transfers)
        context["has_personal_fundings"] = bool(personal_fundings)
        return context


class MatureParticipantMeView(LoginRequiredMixin, TemplateView):
    template_name = "core/participant_me.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = self.request.user

        interests = list(
            ProfileInterest.objects.filter(profile=profile)
            .select_related("topic")
            .order_by("topic__label", "created_at")[:ME_PREVIEW_LIMIT]
        )
        open_to = list(
            ProfileOpenTo.objects.filter(profile=profile, is_active=True)
            .select_related("topic")
            .order_by("kind", "created_at")[:ME_PREVIEW_LIMIT]
        )
        watches = list(
            DiscoveryWatch.objects.filter(owner=profile)
            .select_related("dossier")
            .order_by("-updated_at", "id")[:ME_PREVIEW_LIMIT]
        )
        bookmarks = list(
            ActivityBookmark.objects.filter(user=profile)
            .select_related("activity")
            .order_by("-created_at")[:ME_PREVIEW_LIMIT]
        )
        followed_spaces = list(
            OrganizationFollow.objects.filter(user=profile)
            .select_related("organization")
            .order_by("-followed_at")[:ME_PREVIEW_LIMIT]
        )
        followed_profiles = list(
            ProfileFollow.objects.filter(user=profile)
            .select_related("organizer_profile")
            .order_by("-followed_at")[:ME_PREVIEW_LIMIT]
        )
        team_memberships = list(
            TeamMembership.objects.filter(user=profile, status=TeamMembershipStatus.ACTIVE)
            .select_related("team__organization")
            .order_by("team__organization__name", "team__name")[:ME_PREVIEW_LIMIT]
        )
        spaces = list(authorized_spaces(profile)[:ME_PREVIEW_LIMIT])
        groups = list(groups_for_profile(profile)[:ME_PREVIEW_LIMIT])
        resources = list(personal_assets_for_controller(profile)[:ME_PREVIEW_LIMIT])
        credentials = list(credentials_for_profile(profile)[:ME_PREVIEW_LIMIT])
        proofs = list(proofs_for_profile(profile)[:ME_PREVIEW_LIMIT])

        support_links = []
        recognition_account = account_for_profile(profile)
        if recognition_account is not None or redemptions_requiring_beneficiary_response(profile).exists():
            support_links.append(
                {
                    "label": "Reconnaissance",
                    "detail": "Voir ce que vos contributions ont rendu disponible.",
                    "url": reverse("recognition:dashboard"),
                }
            )
        if get_accounts_visible_to(profile).filter(user=profile).exists() or get_subscriptions_visible_to(profile).filter(user=profile).exists():
            support_links.append(
                {
                    "label": "Mes avantages",
                    "detail": "Retrouver vos relations de fidélité organisation par organisation.",
                    "url": reverse("loyalty:dashboard"),
                }
            )
        personal_partners = list(
            Partner.objects.filter(user=profile, status=PartnerStatus.ACTIVE)
            .select_related("organization")
            .order_by("organization__name", "name")[:ME_PREVIEW_LIMIT]
        )
        for partner in personal_partners:
            support_links.append(
                {
                    "label": partner.organization.name,
                    "detail": "Ma relation partenaire",
                    "url": reverse("partners:my-detail", kwargs={"pk": partner.pk}),
                }
            )

        context.update(
            {
                "interests": interests,
                "open_to": open_to,
                "watches": watches,
                "bookmarks": bookmarks,
                "followed_spaces": followed_spaces,
                "followed_profiles": followed_profiles,
                "team_memberships": team_memberships,
                "authorized_spaces": spaces,
                "my_groups": groups,
                "resources": resources,
                "credentials": credentials,
                "proofs": proofs,
                "passport_url": reverse("sharing:passport-me"),
                "support_links": support_links,
            }
        )
        return context


class MakoloMarkView(LoginRequiredMixin, TemplateView):
    template_name = "core/makolo_mark.html"
    login_url = "core:login"

    def post(self, request, *args, **kwargs):
        text = (request.POST.get("intent") or "").strip()[:MARK_TEXT_MAX_LENGTH]
        if not text:
            context = self.get_context_data(
                mark_error="Dites simplement ce que vous voulez faire."
            )
            return self.render_to_response(context, status=400)

        result = orchestrate_mark(
            profile=request.user,
            input_kind="text",
            value=text,
            context={},
        )
        target = mark_web_url(result)
        if target:
            return redirect(target)

        context = self.get_context_data(
            mark_text=text,
            mark_needs_clarification=result["state"] in {
                "needs_clarification",
                "unknown",
                "unsupported",
                "forbidden",
            },
            mark_result=result,
        )
        return self.render_to_response(context)

