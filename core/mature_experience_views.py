from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core import signing
from django.http import HttpResponseBadRequest
from django.db import models
from django.shortcuts import redirect
from django.urls import reverse

from core.mark_orchestration import MARK_TEXT_MAX_LENGTH, mark_web_url, orchestrate_mark
from core.web.fragments import FragmentTemplateMixin
from core.web.request_context import get_request_context
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
from readiness.presentation import readiness_next_action_label
from readiness.selectors import readiness_queryset
from topics.models import ProfileInterest, ProfileOpenTo
from trust.credential_selectors import credentials_for_profile
from trust.selectors import proofs_for_profile

from .participant_selectors import participant_active_accesses, participant_active_journeys
from core.api.personal_projections import (
    build_personal_ongoing_projection,
    _ongoing_n1_when,
    ongoing_continuation_offset,
)
from core.api.me_projection import build_personal_me_data, build_personal_considerations_data
from .participant_presentation import occurrence_timing
from .participant_views import HOME_READINESS_CANDIDATE_LIMIT, _access_card, _primary_place


ONGOING_LIMIT = 18
ME_PREVIEW_LIMIT = 6


def _ongoing_journey_item(journey, readiness):
    """Present only the Journey facts that En cours actually renders."""
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
        "next_action": (
            readiness_next_action_label(readiness)
            if status in {ReadinessStatus.BLOCKED, ReadinessStatus.ACTION_REQUIRED}
            else ""
        ),
        "timing": occurrence_timing(journey.occurrence),
        "place": _primary_place(journey.occurrence),
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


class MatureParticipantOngoingView(FragmentTemplateMixin, LoginRequiredMixin, TemplateView):
    template_name = "core/participant_ongoing.html"
    fragment_template_name = "core/participant_ongoing_fragment.html"
    login_url = "core:login"

    def get_template_names(self):
        if (
            self.request.GET.get("continuation")
            and self.request.headers.get("X-Makolo-Continuation") == "1"
        ):
            return ["core/_ongoing_page_fragment.html"]
        return super().get_template_names()

    def get(self, request, *args, **kwargs):
        token = request.GET.get("continuation")
        if token:
            try:
                ongoing_continuation_offset(token, profile=request.user)
            except (signing.BadSignature, KeyError, ValueError, TypeError):
                return HttpResponseBadRequest("Suite de résultats indisponible.")
        response = super().get(request, *args, **kwargs)
        response["Cache-Control"] = "private, no-store"
        return response

    @staticmethod
    def _web_item(item):
        """N1 web uses exactly the API's semantic and media projection."""
        n1 = item.get("n1") or {}
        media = next(
            (
                binding.get("resource") or {}
                for binding in item.get("media_bindings") or []
                if binding.get("purpose") == "RECOGNIZE"
                and (binding.get("resource") or {}).get("url")
            ),
            {},
        )
        links = item.get("links") or {}
        labels = {
            "journey": "Continuer la démarche",
            "access": "Voir mon accès",
            "dossier": "Ouvrir le dossier",
            "project": "Voir le projet",
            "waitlist": "Suivre ma liste d’attente",
            "transfer": "Voir le transfert",
            "payment": "Suivre le paiement",
            "funding": "Gérer le financement",
        }
        return {
            "primary_label": labels.get(item.get("kind"), "Voir la suite"),
            "id": item.get("id"),
            "title": item.get("human_context") or item.get("title") or "",
            "summary": item.get("synthesis") or item.get("summary") or "",
            "tone": n1.get("tone") or "calm",
            "cue": n1.get("cue"),
            "next_action": n1.get("supporting"),
            "when": n1.get("when_label"),
            "place": n1.get("place_label"),
            "image_url": media.get("url"),
            "image_alt": media.get("alt_text") or "",
            "media_gallery": [
                binding["resource"]
                for binding in item.get("media_bindings") or []
                if binding.get("purpose") == "RECOGNIZE"
                and isinstance(binding.get("resource"), dict)
                and binding["resource"].get("mime_type") in {"image/jpeg", "image/png"}
                and binding["resource"].get("url")
            ],
            "resources": [
                resource for resource in item.get("resources") or []
                if isinstance(resource, dict) and resource.get("title")
            ],
            "temporal_facts": [
                {
                    **fact,
                    "display_when": _ongoing_n1_when({
                        "start_at": fact.get("at"),
                        "start_date": fact.get("date"),
                        "timezone": fact.get("timezone"),
                    }),
                }
                for fact in item.get("temporal_facts") or []
                if isinstance(fact, dict) and (fact.get("at") or fact.get("date"))
            ],
            "url": links.get("web"),
            "possibility": n1.get("possibility"),
            "can_save": bool(n1.get("possibility") and (
                {"save", "unsave"} & set(
                    n1["possibility"].get("capabilities") or []
                )
            )),
            "can_share": bool(n1.get("possibility") and
                "share" in (n1["possibility"].get("capabilities") or [])),
            "details": tuple(
                (label, tuple(value for value in entries if isinstance(value, str) and value.strip()))
                for label, values in (
                    ("Déjà réglé", item.get("settled") or []),
                    ("De votre côté", item.get("my_side") or []),
                    ("En attente", item.get("elsewhere") or []),
                    ("Préparé par Makolo", item.get("makolo") or []),
                    ("À venir", item.get("system_or_time") or []),
                    ("À suivre", item.get("next_items") or []),
                    ("À relier", item.get("relation_projections") or []),
                    ("Résultat", [item["outcome"]] if item.get("outcome") else []),
                    ("Ce qui bloque", [item["blocker"]] if item.get("blocker") else []),
                    ("À vérifier", [item["unknown"]] if item.get("unknown") else []),
                )
                if (entries := [
                    entry if isinstance(entry, str)
                    else entry.get("label") or entry.get("title") or entry.get("summary")
                    if isinstance(entry, dict) else None
                    for entry in values
                ])
                and any(isinstance(value, str) and value.strip() for value in entries)
            ),
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = self.request.user
        observed_at = get_request_context(self.request).observed_at
        try:
            offset = ongoing_continuation_offset(
                self.request.GET.get("continuation"),
                profile=profile,
            )
        except (signing.BadSignature, KeyError, TypeError, ValueError):
            offset = 0
        data = build_personal_ongoing_projection(
            profile,
            observed_at=observed_at,
            continuation_offset=offset,
        )
        context["ongoing_next_token"] = (data.get("continuation") or {}).get("token")
        context["ongoing_end_reached"] = (data.get("continuation") or {}).get("state") == "end"
        context["ongoing_page_offset"] = offset
        items = data.get("items", [])
        ongoing_items = [self._web_item(item) for item in items]
        kinds = {item.get("kind") for item in items}

        context["ongoing_items"] = ongoing_items
        context["has_personal_dossiers"] = "dossier" in kinds
        context["has_personal_projects"] = "project" in kinds
        context["has_waitlist"] = "waitlist" in kinds
        context["has_transfers"] = "transfer" in kinds
        context["has_personal_fundings"] = "funding" in kinds
        return context


class MatureParticipantMeView(LoginRequiredMixin, TemplateView):
    """Web N1 consumes the same bounded private projection as Flutter."""

    template_name = "core/participant_me.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = self.request.user
        me_projection = build_personal_me_data(
            profile=profile,
            request=self.request,
        )
        context["me_projection"] = me_projection
        context["passport_url"] = reverse("sharing:passport-me")

        support = me_projection.get("support") or {}
        support_links = []
        if (support.get("recognition") or {}).get("available"):
            support_links.append(
                {
                    "label": "Reconnaissance",
                    "url": reverse("recognition:dashboard"),
                }
            )
        if (support.get("loyalty") or {}).get("available"):
            support_links.append(
                {
                    "label": "Mes avantages",
                    "url": reverse("loyalty:dashboard"),
                }
            )

        # Partner details remain an owner route, not an API link or a
        # second copy of the partnership in the N1 projection.
        if (support.get("partners") or {}).get("available"):
            personal_partners = (
                Partner.objects.filter(user=profile, status=PartnerStatus.ACTIVE)
                .select_related("organization")
                .order_by("organization__name", "name")[:ME_PREVIEW_LIMIT]
            )
            for partner in personal_partners:
                support_links.append(
                    {
                        "label": partner.organization.name,
                        "url": reverse("partners:my-detail", kwargs={"pk": partner.pk}),
                    }
                )

        context["support_links"] = support_links
        return context

class MatureParticipantConsiderationsView(LoginRequiredMixin, TemplateView):
    """Web entry to the same owner-managed personal choices as native Flutter."""

    template_name = "core/participant_me_considerations.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["choices"] = build_personal_considerations_data(
            self.request.user, limit=24,
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

