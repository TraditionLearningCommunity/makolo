from datetime import datetime
from uuid import uuid4

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, JsonResponse
from rest_framework.exceptions import NotFound
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from .core_models import Conversation, ConversationInvitation, ConversationInvitationStatus
from .composing import can_ensure_context_conversation, composer_capabilities, contribute_text, publish_composed_point
from .rich_services import publish_conversation_form, readable_exchange_entries, serialize_attachment, upload_conversation_media
from .services import ensure_context_conversation
from .core_models import ConversationContext, ConversationContextKind
from organizations.models import Organization
from .point_models import ConversationPoint, ConversationPointResponseMode
from .point_services import acknowledge_point, create_exchange_entry, submit_point_response
from .presentation import (
    catch_up_summary,
    conversation_context_label,
    conversation_rows_for_profile,
    conversations_for_context,
    essential_points_for_profile,
    now_points_for_profile,
    other_visible_points_for_profile,
    search_conversation,
    search_conversations_for_profile,
)
from .services import can_view_conversation, respond_to_conversation_invitation, update_personal_conversation_state


class ConversationAccessMixin(LoginRequiredMixin):
    login_url = "core:login"

    def get_conversation(self):
        conversation = get_object_or_404(Conversation.objects.select_related("context"), pk=self.kwargs["pk"])
        if not can_view_conversation(self.request.user, conversation):
            raise PermissionDenied("Cette Conversation n’est pas accessible.")
        return conversation


class ConversationListView(LoginRequiredMixin, TemplateView):
    template_name = "conversations/list.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tab = (self.request.GET.get("tab") or "all").strip().lower()
        if tab not in {"for-me", "all", "archived"}:
            tab = "for-me"
        q = (self.request.GET.get("q") or "").strip()[:120]
        invitations = []
        if not q and tab != "archived":
            invitations = list(
                ConversationInvitation.objects.filter(
                    invitee=self.request.user,
                    status=ConversationInvitationStatus.PENDING,
                )
                .select_related("conversation")
                .order_by("created_at", "id")[:50]
            )
        context.update(
            {
                "tab": tab,
                "q": q,
                "pending_invitations": invitations,
                "rows": conversation_rows_for_profile(
                    self.request.user,
                    archived=tab == "archived",
                    only_attention=tab == "for-me",
                ) if not q else [],
                "search_results": self._deduplicated_search(q) if q else [],
            }
        )
        return context

    def _deduplicated_search(self, query):
        seen = set()
        results = []
        for result in search_conversations_for_profile(self.request.user, query):
            if result.conversation.pk in seen:
                continue
            seen.add(result.conversation.pk)
            results.append(result)
        return results


class ConversationDetailView(ConversationAccessMixin, TemplateView):
    template_name = "conversations/detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        conversation = self.get_conversation()
        previous_state = conversation.user_states.filter(profile=self.request.user).first()
        previous_open = previous_state.last_opened_at if previous_state else None
        q = (self.request.GET.get("q") or "").strip()[:120]
        now_rows = now_points_for_profile(self.request.user, conversation)
        seen = {row["point"].pk for row in now_rows}
        essential = [
            point for point in essential_points_for_profile(self.request.user, conversation)
            if point.pk not in seen
        ]
        seen.update(point.pk for point in essential)
        elsewhere = other_visible_points_for_profile(
            self.request.user, conversation, excluded_ids=seen,
        )
        seen.update(point.pk for point in elsewhere)
        focused_point = None
        focus = (self.request.GET.get("focus") or "").strip()
        if focus:
            try:
                candidate = ConversationPoint.objects.get(pk=focus, conversation=conversation)
            except (ConversationPoint.DoesNotExist, ValueError, ValidationError):
                candidate = None
            if candidate is not None:
                from .point_services import point_visible_to
                if point_visible_to(self.request.user, candidate) and candidate.pk not in seen:
                    focused_point = candidate
        context.update(
            {
                "conversation": conversation,
                "context_label": conversation_context_label(conversation, self.request.user),
                "my_points": [
                    row for row in now_rows
                    if row["section"] == "pour_moi" or row["reason"] == "resolve"
                ],
                "known_points": [
                    row for row in now_rows
                    if row["section"] != "pour_moi" and row["reason"] != "resolve"
                ],
                "elsewhere_points": elsewhere,
                "essential_points": essential,
                "focused_point": focused_point,
                "q": q,
                "search_results": search_conversation(self.request.user, conversation, q) if q else [],
                "catch_up": catch_up_summary(self.request.user, conversation, since=previous_open),
                "composer": composer_capabilities(self.request.user, conversation),
                "compose_refs": {
                    key: str(uuid4()) for key in (
                        "text", "information", "poll", "confirmation",
                        "question", "request", "exchange",
                        "form", "voice", "file", "image",
                    )
                },
                "compose_error": getattr(self, "compose_error", None),
                "compose_draft": getattr(self, "compose_draft", {}),

            }
        )
        update_personal_conversation_state(actor=self.request.user, conversation=conversation, opened=True)
        return context


class ConversationContextOpenView(LoginRequiredMixin, View):
    login_url = "core:login"

    def get(self, request, kind, context_pk):
        try:
            candidates = conversations_for_context(request.user, kind, context_pk)
        except NotFound as exc:
            raise Http404("Conversation introuvable.") from exc
        if not candidates:
            if can_ensure_context_conversation(request.user, kind, context_pk):
                return render(
                    request, "conversations/context_choices.html",
                    {"conversations": [], "can_ensure": True, "kind": kind, "context_pk": context_pk},
                )
            raise Http404("Aucune Conversation accessible.")
        if len(candidates) == 1:
            return redirect("conversations:detail", pk=candidates[0].pk)
        return render(
            request, "conversations/context_choices.html",
            {"conversations": [
                {"conversation": item, "label": conversation_context_label(item, request.user)}
                for item in candidates
            ]},
        )


class ConversationContextEnsureView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, kind, context_pk):
        if not can_ensure_context_conversation(request.user, kind, context_pk):
            raise PermissionDenied("Ouverture non autorisée.")
        field = ConversationContext.TARGET_FIELDS[kind][0]
        model = ConversationContext._meta.get_field(field).remote_field.model
        try:
            target = model.objects.get(pk=context_pk)
        except (model.DoesNotExist, TypeError, ValueError, ValidationError) as exc:
            raise Http404("Contexte introuvable.") from exc
        conversation = ensure_context_conversation(
            actor=request.user, kind=kind, **{field: target},
        )
        if not can_view_conversation(request.user, conversation):
            raise Http404("Conversation introuvable.")
        return redirect("conversations:detail", pk=conversation.pk)


class ConversationComposeView(ConversationDetailView):
    """Failure keeps the submitted draft and reference on the same Web surface."""

    def post(self, request, pk):
        conversation = self.get_conversation()
        mode = (request.POST.get("mode") or "text").strip()
        ref = request.POST.get("client_reference")
        space_raw = request.POST.get("represented_space_id")
        represented_space = None
        try:
            if space_raw:
                try:
                    represented_space = Organization.objects.get(pk=space_raw)
                except (Organization.DoesNotExist, ValidationError, ValueError, TypeError) as exc:
                    raise PermissionDenied("Espace non autorisé.") from exc
            if mode == "text":
                _, _, point_id = contribute_text(
                    actor=request.user, conversation=conversation,
                    body=request.POST.get("body"),
                    point_id=request.POST.get("point_id") or None,
                    audience_id=request.POST.get("audience_id") or None,
                    represented_space=represented_space, client_reference=ref,
                )
            elif mode == "form":
                questions = [
                    line.strip() for line in request.POST.get("questions", "").splitlines()
                    if line.strip()
                ] if not request.POST.get("form_version_id") else None
                point = publish_conversation_form(
                    actor=request.user, conversation=conversation,
                    title=request.POST.get("title", ""),
                    form_version_id=request.POST.get("form_version_id") or None,
                    questions=questions, audience_id=request.POST.get("audience_id") or None,
                    represented_space=represented_space,
                    client_reference=ref,
                )
                point_id = point.pk
            elif mode == "point":
                kind = request.POST.get("kind")
                options = [
                    line.strip() for line in request.POST.get("options", "").splitlines()
                    if line.strip()
                ] if kind == "poll" else []
                point = publish_composed_point(
                    actor=request.user, conversation=conversation,
                    kind=kind,
                    title=request.POST.get("title", ""),
                    body=request.POST.get("body", ""),
                    audience_id=request.POST.get("audience_id") or None,
                    options=options, represented_space=represented_space,
                    client_reference=ref,
                )
                point_id = point.pk
            else:
                raise ValidationError("Action indisponible.")
        except (ValidationError, PermissionDenied) as exc:
            self.compose_error = (
                "Vous n’êtes pas autorisé à publier dans cette Conversation."
                if isinstance(exc, PermissionDenied) else str(exc)
            )
            self.compose_draft = request.POST
            return self.get(request, pk=pk)
        return redirect(
            f"{reverse('conversations:detail', kwargs={'pk': conversation.pk})}"
            f"?focus={point_id}#point-{point_id}"
        )


class ConversationMediaWebView(ConversationDetailView):
    def post(self, request, pk):
        conversation = self.get_conversation()
        try:
            raw_space = request.POST.get("represented_space_id")
            represented = Organization.objects.get(pk=raw_space) if raw_space else None
            point, attachment = upload_conversation_media(
                actor=request.user, conversation=conversation,
                uploaded_file=request.FILES.get("file"),
                kind=request.POST.get("kind", "file"),
                body=request.POST.get("body", ""),
                audience_id=request.POST.get("audience_id") or None,
                point_id=request.POST.get("point_id") or None,
                represented_space=represented,
                client_reference=request.POST.get("client_reference"),
            )
        except (ValidationError, PermissionDenied, Organization.DoesNotExist) as exc:
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"detail": str(exc)}, status=403 if isinstance(exc, PermissionDenied) else 400)
            self.compose_error = "Pièce non envoyée. " + str(exc)
            self.compose_draft = request.POST
            return self.get(request, pk=pk)
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({
                "point_id": str(point.pk), "attachment": serialize_attachment(attachment),
            })
        return redirect(
            f"{reverse('conversations:detail', kwargs={'pk': conversation.pk})}"
            f"?focus={point.pk}#point-{point.pk}"
        )


class ConversationExchangeDepthView(LoginRequiredMixin, TemplateView):
    login_url = "core:login"
    template_name = "conversations/exchange.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        point = get_object_or_404(
            ConversationPoint.objects.select_related("conversation__context"), pk=self.kwargs["point_pk"],
        )
        from .point_services import point_visible_to, point_response_allowed
        if not point_visible_to(self.request.user, point) or point.kind != "exchange":
            raise Http404("Échange inaccessible.")
        try:
            entries, cursor = readable_exchange_entries(
                self.request.user, point, cursor=self.request.GET.get("cursor"),
            )
        except ValidationError as exc:
            raise Http404("Curseur invalide.") from exc
        context.update({
            "conversation": point.conversation, "point": point,
            "entries": entries, "next_cursor": cursor,
            "can_contribute": bool(point_response_allowed(self.request.user, point) and
                point.lifecycle == "open" and
                (point.opens_at is None or point.opens_at <= timezone.now()) and
                (point.deadline_at is None or point.deadline_at > timezone.now()) and
                (point.valid_until is None or point.valid_until > timezone.now())),
            "client_reference": str(uuid4()),
        })
        return context


class ConversationInvitationRespondView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, invitation_pk):
        invitation = get_object_or_404(
            ConversationInvitation.objects.select_related("conversation", "conversation__context"),
            pk=invitation_pk,
            invitee=request.user,
        )
        decision = request.POST.get("decision")
        if decision not in {"accept", "decline"}:
            messages.error(request, "Réponse d’invitation invalide.")
            return redirect("conversations:list")
        try:
            invitation = respond_to_conversation_invitation(
                actor=request.user,
                invitation=invitation,
                accept=decision == "accept",
            )
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, str(exc))
            return redirect("conversations:list")
        if invitation.status == ConversationInvitationStatus.ACCEPTED:
            messages.success(request, "Invitation acceptée.")
            return redirect("conversations:detail", pk=invitation.conversation_id)
        if invitation.status == ConversationInvitationStatus.DECLINED:
            messages.success(request, "Invitation refusée.")
        elif invitation.status == ConversationInvitationStatus.EXPIRED:
            messages.info(request, "Cette invitation a expiré.")
        return redirect("conversations:list")


class PointRespondView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, point_pk):
        point = get_object_or_404(ConversationPoint, pk=point_pk)
        if point.response_mode == ConversationPointResponseMode.MULTIPLE_CHOICE:
            value = request.POST.getlist("choices")
        elif point.response_mode == ConversationPointResponseMode.SINGLE_CHOICE:
            value = request.POST.get("choice")
        elif point.response_mode == ConversationPointResponseMode.BOOLEAN:
            raw = request.POST.get("value")
            value = True if raw == "true" else False if raw == "false" else raw
        elif point.response_mode == ConversationPointResponseMode.DATETIME:
            raw = request.POST.get("value")
            try:
                parsed = datetime.fromisoformat(raw) if raw else None
            except ValueError:
                parsed = None
            value = (
                timezone.make_aware(parsed, timezone.get_current_timezone())
                if parsed is not None and timezone.is_naive(parsed)
                else parsed or raw
            )
        else:
            value = request.POST.get("value")
        try:
            submit_point_response(
                actor=request.user,
                point=point,
                value=value,
                client_reference=request.POST.get("client_reference") or None,
            )
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Votre réponse a été enregistrée.")
        return redirect("conversations:detail", pk=point.conversation_id)


class PointAcknowledgeView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, point_pk):
        point = get_object_or_404(ConversationPoint, pk=point_pk)
        try:
            acknowledge_point(actor=request.user, point=point)
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, str(exc))
        return redirect("conversations:detail", pk=point.conversation_id)


class PointExchangeView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, point_pk):
        point = get_object_or_404(ConversationPoint, pk=point_pk)
        try:
            create_exchange_entry(
                actor=request.user,
                point=point,
                body=request.POST.get("body", ""),
                client_reference=request.POST.get("client_reference") or None,
            )
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, str(exc))
        return redirect("conversations:exchange-detail", point_pk=point.pk)
