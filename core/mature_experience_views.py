from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.utils import timezone
from django.views.generic import TemplateView

from discovery.models import ActivityBookmark, DiscoveryWatch
from groups.selectors import groups_for_profile
from organizations.console_context import authorized_spaces
from organizations.models import OrganizationFollow, ProfileFollow, TeamMembership, TeamMembershipStatus
from personal_assets.selectors import personal_assets_for_controller
from readiness import ReadinessStatus, resolve_many
from readiness.selectors import readiness_queryset
from topics.models import ProfileInterest, ProfileOpenTo

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

        standalone_accesses = list(
            participant_active_accesses(profile, at=now)
            .filter(journey__isnull=True)
            .order_by("occurrence__start_date", "occurrence__start_time", "id")[:ONGOING_LIMIT]
        )
        access_items = [_ongoing_access_item(_access_card(access)) for access in standalone_accesses]

        context.update(
            {
                "ongoing_items": journey_items + access_items,
                "calendar_mode": self.request.GET.get("view") == "calendar",
            }
        )
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
                "passport_url": reverse("sharing:passport-me"),
            }
        )
        return context


class MakoloMarkView(LoginRequiredMixin, TemplateView):
    template_name = "core/makolo_mark.html"
    login_url = "core:login"
