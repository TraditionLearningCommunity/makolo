from io import BytesIO
from urllib.parse import urlencode

import qrcode
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView

from accounts.models import UserProfile
from activities.models import Activity, Occurrence
from core.participant_selectors import participant_state_context
from core.web_throttling import allow_web_request, client_rate_identity, value_rate_identity
from discovery.presentation import build_discovery_item, presenter_for
from discovery.search import public_occurrences_for_activities
from journeys.models import Journey
from opportunities.models import Opportunity

from .journey_reuse import accept_journey_share, build_journey_share_snapshot, create_direct_journey_share, evaluate_journey_share, resolve_journey_share_subject
from .models import ShareIntent, ShareSubjectType
from .services import ShareUnavailable, accept_share_delivery, create_activity_share, create_direct_activity_share, create_direct_opportunity_share, create_opportunity_share, decline_share_delivery, resolve_activity_share_subject, resolve_delivery_for_recipient, resolve_opportunity_share_subject, resolve_share_link, share_public_url, share_qr_url

RATE_LIMIT_ERROR = "Trop de partages ont été envoyés récemment. Réessayez plus tard."


def _validation_message(exc):
    if hasattr(exc, "messages"): return "; ".join(exc.messages)
    return "Ce contenu ne peut pas être partagé."


def _share_payload(created, *, title, text):
    return {"url": share_public_url(created.raw_token), "qr_url": share_qr_url(created.raw_token), "title": (title or "Makolo")[:220], "text": (text or "Un contenu Makolo vous a été partagé.")[:320]}


def _direct_payload(created):
    return {"message": "Partage envoyé.", "delivery_url": reverse("sharing:delivery", kwargs={"delivery_id": created.delivery.pk})}


def _requested_intent(request, *, default): return (request.POST.get("intent") or default).strip()


def _recipient_from_request(request):
    recipient_id = (request.POST.get("recipient_id") or "").strip()
    if not recipient_id: return None
    return get_object_or_404(UserProfile.objects.select_related("user").filter(user__is_active=True), pk=recipient_id)


def _allow_direct_share(request, recipient):
    return allow_web_request(request, scope="sharing-direct-minute", limit=12, window_seconds=60, identities=[value_rate_identity("sender", str(request.user.pk))]) and allow_web_request(request, scope="sharing-direct-hour", limit=60, window_seconds=3600, identities=[value_rate_identity("sender", str(request.user.pk))]) and allow_web_request(request, scope="sharing-direct-pair", limit=8, window_seconds=3600, identities=[value_rate_identity("pair", f"{request.user.pk}:{recipient.pk}")])


def _recipient_candidates(request):
    query = (request.GET.get("q") or "").strip()
    if len(query) < 2: return query, []
    profiles = UserProfile.objects.select_related("user").filter(user__is_active=True, searchable=True).exclude(user=request.user).filter(Q(user__first_name__icontains=query) | Q(user__last_name__icontains=query) | Q(user__username__icontains=query)).order_by("user__first_name", "user__last_name", "user__username")[:8]
    return query, list(profiles)


class ShareCreateMixin:
    def _rate_limited(self, request, recipient):
        if recipient is not None and not _allow_direct_share(request, recipient): return JsonResponse({"error": RATE_LIMIT_ERROR}, status=429)
        return None


class ActivityShareCreateView(ShareCreateMixin, LoginRequiredMixin, View):
    login_url = "core:login"
    def post(self, request, activity_id):
        activity = get_object_or_404(Activity, pk=activity_id); recipient = _recipient_from_request(request)
        limited = self._rate_limited(request, recipient)
        if limited: return limited
        try:
            if recipient: return JsonResponse(_direct_payload(create_direct_activity_share(created_by=request.user, recipient=recipient, activity=activity, intent=_requested_intent(request, default=ShareIntent.VIEW))))
            created = create_activity_share(created_by=request.user, activity=activity, intent=_requested_intent(request, default=ShareIntent.VIEW))
        except (ValidationError, PermissionDenied) as exc: return JsonResponse({"error": _validation_message(exc)}, status=400)
        return JsonResponse(_share_payload(created, title=activity.title, text=activity.short_description or activity.description))


class OccurrenceShareCreateView(ShareCreateMixin, LoginRequiredMixin, View):
    login_url = "core:login"
    def post(self, request, occurrence_id):
        occurrence = get_object_or_404(Occurrence.objects.select_related("activity"), pk=occurrence_id); recipient = _recipient_from_request(request)
        limited = self._rate_limited(request, recipient)
        if limited: return limited
        try:
            if recipient: return JsonResponse(_direct_payload(create_direct_activity_share(created_by=request.user, recipient=recipient, activity=occurrence.activity, occurrence=occurrence, intent=_requested_intent(request, default=ShareIntent.VIEW))))
            created = create_activity_share(created_by=request.user, activity=occurrence.activity, occurrence=occurrence, intent=_requested_intent(request, default=ShareIntent.VIEW))
        except (ValidationError, PermissionDenied) as exc: return JsonResponse({"error": _validation_message(exc)}, status=400)
        return JsonResponse(_share_payload(created, title=occurrence.activity.title, text=occurrence.activity.short_description or occurrence.activity.description))


class OpportunityShareCreateView(ShareCreateMixin, LoginRequiredMixin, View):
    login_url = "core:login"
    def post(self, request, opportunity_id):
        opportunity = get_object_or_404(Opportunity.objects.select_related("current_revision"), pk=opportunity_id)
        if opportunity.current_revision is None: return JsonResponse({"error": "Cette Opportunity n’est pas partageable."}, status=400)
        recipient = _recipient_from_request(request); limited = self._rate_limited(request, recipient)
        if limited: return limited
        try:
            if recipient: return JsonResponse(_direct_payload(create_direct_opportunity_share(created_by=request.user, recipient=recipient, opportunity_revision=opportunity.current_revision, intent=_requested_intent(request, default=ShareIntent.START_JOURNEY))))
            created = create_opportunity_share(created_by=request.user, opportunity_revision=opportunity.current_revision, intent=_requested_intent(request, default=ShareIntent.START_JOURNEY))
        except (ValidationError, PermissionDenied) as exc: return JsonResponse({"error": _validation_message(exc)}, status=400)
        return JsonResponse(_share_payload(created, title=opportunity.current_revision.title, text=opportunity.current_revision.summary))


class JourneyReuseShareView(LoginRequiredMixin, View):
    login_url = "core:login"; template_name = "sharing/journey_reuse_preview.html"
    def _journey(self, request, journey_id):
        return get_object_or_404(Journey.objects.select_related("activity", "occurrence", "beneficiary", "initiated_by", "service_context", "service_context__service_plan_template", "service_context__opportunity", "service_context__opportunity_revision"), pk=journey_id)
    def _context(self, request, journey, *, error="", sent_to=""):
        snapshot = build_journey_share_snapshot(journey=journey, actor=request.user); query, candidates = _recipient_candidates(request)
        return {"journey": journey, "snapshot": snapshot, "counts": snapshot["counts"], "excluded_policy": snapshot["excluded_policy"], "query": query, "candidates": candidates, "error": error, "sent_to": sent_to}
    def get(self, request, journey_id):
        journey = self._journey(request, journey_id)
        try: context = self._context(request, journey)
        except PermissionDenied: return render(request, "sharing/unavailable.html", status=403)
        except ValidationError as exc: return render(request, self.template_name, {"journey": journey, "error": _validation_message(exc), "unshareable": True}, status=400)
        return render(request, self.template_name, context)
    def post(self, request, journey_id):
        journey = self._journey(request, journey_id); recipient = _recipient_from_request(request)
        if recipient is None:
            try: context = self._context(request, journey, error="Choisissez une personne Makolo.")
            except (PermissionDenied, ValidationError) as exc: return render(request, self.template_name, {"journey": journey, "error": _validation_message(exc)}, status=400)
            return render(request, self.template_name, context, status=400)
        if not _allow_direct_share(request, recipient): return render(request, self.template_name, {"journey": journey, "error": RATE_LIMIT_ERROR}, status=429)
        try:
            create_direct_journey_share(created_by=request.user, recipient=recipient, journey=journey); context = self._context(request, journey, sent_to=recipient.user.full_name or recipient.user.username)
        except PermissionDenied: return render(request, "sharing/unavailable.html", status=403)
        except ValidationError as exc: return render(request, self.template_name, {"journey": journey, "error": _validation_message(exc)}, status=400)
        return render(request, self.template_name, context)


class ProfileSearchView(LoginRequiredMixin, View):
    login_url = "core:login"
    def get(self, request):
        if not allow_web_request(request, scope="sharing-profile-search", limit=30, window_seconds=60, identities=[value_rate_identity("profile", str(request.user.pk)), client_rate_identity(request)]): return JsonResponse({"error": "Trop de recherches ont été effectuées récemment. Réessayez plus tard."}, status=429)
        query = (request.GET.get("q") or "").strip()
        if len(query) < 2: return JsonResponse({"results": []})
        profiles = UserProfile.objects.select_related("user").filter(user__is_active=True, searchable=True).exclude(user=request.user).filter(Q(user__first_name__icontains=query) | Q(user__last_name__icontains=query) | Q(user__username__icontains=query)).order_by("user__first_name", "user__last_name", "user__username")[:8]
        return JsonResponse({"results": [{"id": str(p.pk), "name": p.user.full_name or p.user.username, "username": p.user.username} for p in profiles]})


class ShareLandingView(TemplateView):
    template_name = "sharing/landing.html"
    def get(self, request, token):
        try: envelope = resolve_share_link(token); context = self._context(envelope, token)
        except ShareUnavailable: return render(request, "sharing/unavailable.html", status=404)
        return self.render_to_response(context)
    def _context(self, envelope, token):
        base = {"envelope": envelope, "share_url": share_public_url(token), "qr_url": share_qr_url(token), "action_url": reverse("sharing:action", kwargs={"token": token})}
        if envelope.subject_type == ShareSubjectType.ACTIVITY:
            subject, activity, occurrence = resolve_activity_share_subject(envelope); item = None
            if occurrence is not None: item = build_discovery_item(occurrence, profile=self.request.user, participant_context=participant_state_context(self.request.user, [occurrence]))
            base.update({"subject_kind": "activity", "subject": subject, "activity": activity, "occurrence": occurrence, "item": item, "page_title": item.title if item else activity.title, "page_description": item.summary if item else (activity.short_description or activity.description[:320]), "cta_label": "Participer" if envelope.intent == ShareIntent.PARTICIPATE else "Voir dans Makolo"}); return base
        if envelope.subject_type == ShareSubjectType.OPPORTUNITY:
            subject, opportunity, shared_revision, current_revision = resolve_opportunity_share_subject(envelope); base.update({"subject_kind": "opportunity", "subject": subject, "opportunity": opportunity, "shared_revision": shared_revision, "revision": current_revision, "revision_changed": shared_revision.pk != current_revision.pk, "page_title": current_revision.title, "page_description": current_revision.summary or "Une Opportunity Makolo vous a été partagée.", "cta_label": "Obtenir de l’aide" if envelope.intent == ShareIntent.START_JOURNEY else "Découvrir l’opportunité"}); return base
        raise ShareUnavailable


class ShareActionView(View):
    AUTH_INTENTS = {ShareIntent.PARTICIPATE, ShareIntent.START_JOURNEY}
    def get(self, request, token):
        try: envelope = resolve_share_link(token)
        except ShareUnavailable as exc: raise Http404 from exc
        if envelope.intent in self.AUTH_INTENTS and not request.user.is_authenticated:
            next_url = reverse("sharing:action", kwargs={"token": token}); return redirect(f"{reverse('core:login')}?{urlencode({'next': next_url})}")
        try: return _redirect_to_subject(request, envelope)
        except ShareUnavailable as exc: raise Http404 from exc


def _redirect_to_subject(request, envelope):
    if envelope.subject_type == ShareSubjectType.ACTIVITY:
        _, activity, occurrence = resolve_activity_share_subject(envelope)
        if envelope.intent == ShareIntent.PARTICIPATE:
            if occurrence is None: raise ShareUnavailable
            item = build_discovery_item(occurrence, profile=request.user, participant_context=participant_state_context(request.user, [occurrence])); return redirect(item.cta_url or item.url)
        if occurrence is not None: return redirect(presenter_for(occurrence).url(occurrence))
        first_occurrence = public_occurrences_for_activities([activity.pk]).first(); return redirect(presenter_for(first_occurrence).url(first_occurrence)) if first_occurrence else redirect("discovery:home")
    if envelope.subject_type == ShareSubjectType.OPPORTUNITY:
        _, opportunity, _, _ = resolve_opportunity_share_subject(envelope)
        if envelope.intent == ShareIntent.START_JOURNEY: return redirect(f"{reverse('services:list')}?{urlencode({'opportunity': opportunity.pk})}")
        return redirect("opportunities:detail", pk=opportunity.pk)
    raise ShareUnavailable


class ShareDeliveryLandingView(LoginRequiredMixin, View):
    login_url = "core:login"
    def get(self, request, delivery_id):
        try: delivery = resolve_delivery_for_recipient(delivery_id=delivery_id, user=request.user, mark_opened=True); context = self._context(request, delivery)
        except PermissionDenied: return render(request, "sharing/unavailable.html", status=403)
        except ShareUnavailable: return render(request, "sharing/unavailable.html", status=404)
        return render(request, "sharing/delivery.html", context)
    def _context(self, request, delivery):
        envelope = delivery.envelope; sender_name = (envelope.created_by.full_name or envelope.created_by.username) if envelope.created_by else "Une personne"
        context = {"delivery": delivery, "envelope": envelope, "sender_name": sender_name, "accept_url": reverse("sharing:delivery-accept", kwargs={"delivery_id": delivery.pk}), "decline_url": reverse("sharing:delivery-decline", kwargs={"delivery_id": delivery.pk}), "go_url": reverse("sharing:delivery-go", kwargs={"delivery_id": delivery.pk})}
        if envelope.subject_type == ShareSubjectType.ACTIVITY:
            _, activity, occurrence = resolve_activity_share_subject(envelope); context.update({"subject_kind": "activity", "activity": activity, "occurrence": occurrence, "page_title": activity.title, "page_description": activity.short_description or activity.description[:320], "cta_label": "Participer" if envelope.intent == ShareIntent.PARTICIPATE else "Voir"})
        elif envelope.subject_type == ShareSubjectType.OPPORTUNITY:
            _, opportunity, _, revision = resolve_opportunity_share_subject(envelope); context.update({"subject_kind": "opportunity", "opportunity": opportunity, "revision": revision, "page_title": revision.title, "page_description": revision.summary, "cta_label": "Commencer" if envelope.intent == ShareIntent.START_JOURNEY else "Découvrir"})
        elif envelope.subject_type == ShareSubjectType.JOURNEY:
            subject, source_journey = resolve_journey_share_subject(envelope); context.update({"subject_kind": "journey", "source_journey": source_journey, "page_title": source_journey.activity.title, "page_description": f"{sender_name} vous permet de repartir d’un chemin déjà préparé.", "cta_label": "Utiliser ce parcours", "journey_reuse": evaluate_journey_share(subject)})
        else: raise ShareUnavailable
        context["actionable"] = envelope.intent != ShareIntent.VIEW; return context


class ShareDeliveryGoView(LoginRequiredMixin, View):
    login_url = "core:login"
    def get(self, request, delivery_id):
        try:
            delivery = resolve_delivery_for_recipient(delivery_id=delivery_id, user=request.user)
            if delivery.envelope.subject_type == ShareSubjectType.JOURNEY: return redirect("sharing:delivery", delivery_id=delivery.pk)
            return _redirect_to_subject(request, delivery.envelope)
        except PermissionDenied: return render(request, "sharing/unavailable.html", status=403)
        except ShareUnavailable: return render(request, "sharing/unavailable.html", status=404)


class ShareDeliveryAcceptView(LoginRequiredMixin, View):
    login_url = "core:login"
    def post(self, request, delivery_id):
        try:
            delivery = resolve_delivery_for_recipient(delivery_id=delivery_id, user=request.user)
            if delivery.envelope.subject_type == ShareSubjectType.JOURNEY:
                result = accept_journey_share(delivery_id=delivery_id, user=request.user); return redirect("core:participant-journey-detail", pk=result.journey.pk)
            return _redirect_to_subject(request, accept_share_delivery(delivery_id=delivery_id, user=request.user).envelope)
        except PermissionDenied: return render(request, "sharing/unavailable.html", status=403)
        except (ShareUnavailable, ValidationError): return render(request, "sharing/unavailable.html", status=404)


class ShareDeliveryDeclineView(LoginRequiredMixin, View):
    login_url = "core:login"
    def post(self, request, delivery_id):
        try: decline_share_delivery(delivery_id=delivery_id, user=request.user)
        except PermissionDenied: return render(request, "sharing/unavailable.html", status=403)
        except (ShareUnavailable, ValidationError): return render(request, "sharing/unavailable.html", status=404)
        return redirect("notifications:list")


class ShareQRView(View):
    def get(self, request, token):
        try:
            envelope = resolve_share_link(token)
            if envelope.subject_type == ShareSubjectType.ACTIVITY: resolve_activity_share_subject(envelope)
            elif envelope.subject_type == ShareSubjectType.OPPORTUNITY: resolve_opportunity_share_subject(envelope)
            else: raise ShareUnavailable
        except ShareUnavailable as exc: raise Http404 from exc
        image = qrcode.make(share_public_url(token)); buffer = BytesIO(); image.save(buffer, format="PNG")
        response = HttpResponse(buffer.getvalue(), content_type="image/png"); response["Cache-Control"] = "no-store"; return response
