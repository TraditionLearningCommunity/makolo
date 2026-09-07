from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import TemplateView

from .core_models import Conversation
from .point_models import ConversationPoint, ConversationPointResponseMode
from .point_services import acknowledge_point, create_exchange_entry, submit_point_response
from .presentation import (
    catch_up_summary,
    conversation_context_label,
    conversation_rows_for_profile,
    essential_points_for_profile,
    now_points_for_profile,
    search_conversation,
    search_conversations_for_profile,
)
from .services import can_view_conversation, update_personal_conversation_state


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
        tab = (self.request.GET.get("tab") or "for-me").strip().lower()
        if tab not in {"for-me", "all", "archived"}:
            tab = "for-me"
        q = (self.request.GET.get("q") or "").strip()[:120]
        context.update(
            {
                "tab": tab,
                "q": q,
                "rows": conversation_rows_for_profile(
                    self.request.user,
                    archived=tab == "archived",
                    only_attention=tab == "for-me",
                ) if not q else [],
                "search_results": search_conversations_for_profile(self.request.user, q) if q else [],
            }
        )
        return context


class ConversationDetailView(ConversationAccessMixin, TemplateView):
    template_name = "conversations/detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        conversation = self.get_conversation()
        previous_state = conversation.user_states.filter(profile=self.request.user).first()
        previous_open = previous_state.last_opened_at if previous_state else None
        q = (self.request.GET.get("q") or "").strip()[:120]
        context.update(
            {
                "conversation": conversation,
                "context_label": conversation_context_label(conversation, self.request.user),
                "now_rows": now_points_for_profile(self.request.user, conversation),
                "essential_points": essential_points_for_profile(self.request.user, conversation),
                "q": q,
                "search_results": search_conversation(self.request.user, conversation, q) if q else [],
                "catch_up": catch_up_summary(self.request.user, conversation, since=previous_open),
            }
        )
        update_personal_conversation_state(actor=self.request.user, conversation=conversation, opened=True)
        return context


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
        return redirect("conversations:detail", pk=point.conversation_id)
