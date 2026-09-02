from io import BytesIO
from urllib.parse import urlencode

import qrcode
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView

from activities.models import Activity, Occurrence
from core.participant_selectors import participant_state_context
from discovery.presentation import build_discovery_item, presenter_for
from discovery.search import public_occurrences
from opportunities.models import Opportunity

from .models import ShareIntent, ShareSubjectType
from .services import (
    ShareUnavailable,
    create_activity_share,
    create_opportunity_share,
    resolve_activity_share_subject,
    resolve_opportunity_share_subject,
    resolve_share_link,
    share_public_url,
    share_qr_url,
)


def _validation_message(exc):
    if hasattr(exc, "messages"):
        return "; ".join(exc.messages)
    return "Ce contenu ne peut pas être partagé."


def _share_payload(created, *, title, text):
    return {
        "url": share_public_url(created.raw_token),
        "qr_url": share_qr_url(created.raw_token),
        "title": (title or "Makolo")[:220],
        "text": (text or "Un contenu Makolo vous a été partagé.")[:320],
    }


def _requested_intent(request, *, default):
    return (request.POST.get("intent") or default).strip()


class ActivityShareCreateView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, activity_id):
        activity = get_object_or_404(Activity, pk=activity_id)
        try:
            created = create_activity_share(
                created_by=request.user,
                activity=activity,
                intent=_requested_intent(request, default=ShareIntent.VIEW),
            )
        except ValidationError as exc:
            return JsonResponse({"error": _validation_message(exc)}, status=400)
        return JsonResponse(
            _share_payload(
                created,
                title=activity.title,
                text=activity.short_description or activity.description,
            )
        )


class OccurrenceShareCreateView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, occurrence_id):
        occurrence = get_object_or_404(Occurrence.objects.select_related("activity"), pk=occurrence_id)
        try:
            created = create_activity_share(
                created_by=request.user,
                activity=occurrence.activity,
                occurrence=occurrence,
                intent=_requested_intent(request, default=ShareIntent.VIEW),
            )
        except ValidationError as exc:
            return JsonResponse({"error": _validation_message(exc)}, status=400)
        return JsonResponse(
            _share_payload(
                created,
                title=occurrence.activity.title,
                text=occurrence.activity.short_description or occurrence.activity.description,
            )
        )


class OpportunityShareCreateView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, opportunity_id):
        opportunity = get_object_or_404(
            Opportunity.objects.select_related("current_revision"),
            pk=opportunity_id,
        )
        if opportunity.current_revision is None:
            return JsonResponse({"error": "Cette Opportunity n’est pas partageable."}, status=400)
        try:
            created = create_opportunity_share(
                created_by=request.user,
                opportunity_revision=opportunity.current_revision,
                intent=_requested_intent(request, default=ShareIntent.START_JOURNEY),
            )
        except ValidationError as exc:
            return JsonResponse({"error": _validation_message(exc)}, status=400)
        revision = opportunity.current_revision
        return JsonResponse(
            _share_payload(
                created,
                title=revision.title,
                text=revision.summary,
            )
        )


class ShareLandingView(TemplateView):
    template_name = "sharing/landing.html"

    def get(self, request, token):
        try:
            envelope = resolve_share_link(token)
            context = self._context(envelope, token)
        except ShareUnavailable:
            return render(request, "sharing/unavailable.html", status=404)
        return self.render_to_response(context)

    def _context(self, envelope, token):
        share_url = share_public_url(token)
        base = {
            "envelope": envelope,
            "share_url": share_url,
            "qr_url": share_qr_url(token),
            "action_url": reverse("sharing:action", kwargs={"token": token}),
        }
        if envelope.subject_type == ShareSubjectType.ACTIVITY:
            subject, activity, occurrence = resolve_activity_share_subject(envelope)
            item = None
            if occurrence is not None:
                item = build_discovery_item(
                    occurrence,
                    profile=self.request.user,
                    participant_context=participant_state_context(self.request.user, [occurrence]),
                )
            title = item.title if item else activity.title
            description = item.summary if item else (activity.short_description or activity.description[:320])
            base.update(
                {
                    "subject_kind": "activity",
                    "subject": subject,
                    "activity": activity,
                    "occurrence": occurrence,
                    "item": item,
                    "page_title": title,
                    "page_description": description or "Une Activity Makolo vous a été partagée.",
                    "cta_label": "Participer" if envelope.intent == ShareIntent.PARTICIPATE else "Voir dans Makolo",
                }
            )
            return base
        subject, opportunity, shared_revision, current_revision = resolve_opportunity_share_subject(envelope)
        base.update(
            {
                "subject_kind": "opportunity",
                "subject": subject,
                "opportunity": opportunity,
                "shared_revision": shared_revision,
                "revision": current_revision,
                "revision_changed": shared_revision.pk != current_revision.pk,
                "page_title": current_revision.title,
                "page_description": current_revision.summary or "Une Opportunity Makolo vous a été partagée.",
                "cta_label": "Obtenir de l’aide" if envelope.intent == ShareIntent.START_JOURNEY else "Découvrir l’opportunité",
            }
        )
        return base


class ShareActionView(View):
    AUTH_INTENTS = {ShareIntent.PARTICIPATE, ShareIntent.START_JOURNEY}

    def get(self, request, token):
        try:
            envelope = resolve_share_link(token)
        except ShareUnavailable as exc:
            raise Http404 from exc
        if envelope.intent in self.AUTH_INTENTS and not request.user.is_authenticated:
            next_url = reverse("sharing:action", kwargs={"token": token})
            return redirect(f"{reverse('core:login')}?{urlencode({'next': next_url})}")
        try:
            if envelope.subject_type == ShareSubjectType.ACTIVITY:
                return self._activity_action(request, envelope)
            return self._opportunity_action(envelope)
        except ShareUnavailable as exc:
            raise Http404 from exc

    def _activity_action(self, request, envelope):
        _, activity, occurrence = resolve_activity_share_subject(envelope)
        if envelope.intent == ShareIntent.PARTICIPATE:
            if occurrence is None:
                raise ShareUnavailable
            item = build_discovery_item(
                occurrence,
                profile=request.user,
                participant_context=participant_state_context(request.user, [occurrence]),
            )
            return redirect(item.cta_url or item.url)
        if occurrence is not None:
            return redirect(presenter_for(occurrence).url(occurrence))
        first_occurrence = public_occurrences().filter(activity_id=activity.pk).order_by("start_at", "id").first()
        if first_occurrence is not None:
            return redirect(presenter_for(first_occurrence).url(first_occurrence))
        return redirect("discovery:home")

    def _opportunity_action(self, envelope):
        _, opportunity, _, _ = resolve_opportunity_share_subject(envelope)
        if envelope.intent == ShareIntent.START_JOURNEY:
            destination = reverse("services:list")
            return redirect(f"{destination}?{urlencode({'opportunity': opportunity.pk})}")
        return redirect("opportunities:detail", pk=opportunity.pk)


class ShareQRView(View):
    def get(self, request, token):
        try:
            envelope = resolve_share_link(token)
            if envelope.subject_type == ShareSubjectType.ACTIVITY:
                resolve_activity_share_subject(envelope)
            else:
                resolve_opportunity_share_subject(envelope)
        except ShareUnavailable as exc:
            raise Http404 from exc
        image = qrcode.make(share_public_url(token))
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        response = HttpResponse(buffer.getvalue(), content_type="image/png")
        response["Cache-Control"] = "no-store"
        return response
