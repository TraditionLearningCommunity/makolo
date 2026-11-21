"""Web participant management for the canonical Conversation owner services."""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import TemplateView

from .collective_models import ConversationCollectiveAccess
from .core_models import (
    Conversation, ConversationInvitation, ConversationJoinRequest,
    ConversationParticipation, ConversationParticipationStatus,
)
from .detail_presentation import conversation_members_for_profile
from .participant_services import (
    answer_collective_invitation, collective_invitation_inbox,
    invite_identifier, revoke_collective_access,
)
from .services import (
    can_manage_conversation, can_view_conversation, context_base_eligible,
    create_join_request, join_conversation, leave_conversation,
    remove_participation, respond_to_join_request, withdraw_join_request,
)


class ConversationParticipantsWebView(LoginRequiredMixin, TemplateView):
    login_url = "core:login"
    template_name = "conversations/participants.html"

    def get_conversation(self):
        conversation = get_object_or_404(
            Conversation.objects.select_related("context"), pk=self.kwargs["pk"],
        )
        if not can_view_conversation(self.request.user, conversation):
            raise Http404("Conversation inaccessible.")
        return conversation

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        conversation = self.get_conversation()
        managing = can_manage_conversation(self.request.user, conversation)
        eligible = context_base_eligible(self.request.user, conversation.context)
        active = ConversationParticipation.objects.filter(
            conversation=conversation, profile=self.request.user,
            status=ConversationParticipationStatus.ACTIVE,
        ).exists()
        requested = ConversationJoinRequest.objects.filter(
            conversation=conversation, requester=self.request.user,
            status="pending",
        ).exists()
        join_requests = list(
            ConversationJoinRequest.objects.filter(
                conversation=conversation, status="pending",
            ).select_related("requester").order_by("created_at")[:60]
        ) if managing else []
        for item in join_requests:
            item.can_approve = bool(
                conversation.lifecycle == "open"
                and conversation.entry_mode == "request"
                and item.requester.is_active
                and context_base_eligible(item.requester, conversation.context)
            )
        context.update({
            "can_join": (
                eligible and not active and conversation.lifecycle == "open"
                and conversation.entry_mode == "join"
            ),
            "can_request_entry": (
                eligible and not active and not requested
                and conversation.lifecycle == "open"
                and conversation.entry_mode == "request"
            ),
            "entry_request_pending": requested,
            "conversation": conversation,
            "members": conversation_members_for_profile(
                self.request.user, conversation,
            ),
            "can_manage": managing,
            "can_leave": ConversationParticipation.objects.filter(
                conversation=conversation, profile=self.request.user,
                status=ConversationParticipationStatus.ACTIVE,
            ).exists(),
            "join_requests": join_requests,
        })
        return context

    def post(self, request, pk):
        conversation = self.get_conversation()
        action = (request.POST.get("action") or "").strip()
        managing = can_manage_conversation(request.user, conversation)
        try:
            if action == "invite" and managing:
                kind, item = invite_identifier(
                    actor=request.user, conversation=conversation,
                    kind=request.POST.get("kind"),
                    identifier=request.POST.get("identifier"),
                )
                messages.success(
                    request, "Invitation en attente d'acceptation."
                    if item.status == "pending" else "Accès collectif déjà accepté.",
                )
            elif action == "remove" and managing:
                participation = get_object_or_404(
                    ConversationParticipation, conversation=conversation,
                    pk=request.POST.get("participation_id"),
                )
                remove_participation(actor=request.user, participation=participation)
                messages.success(request, "Participation retirée.")
            elif action == "cancel" and managing:
                from django.db import transaction
                from django.utils import timezone
                with transaction.atomic():
                    invitation = get_object_or_404(
                        ConversationInvitation.objects.select_for_update(),
                        conversation=conversation,
                        pk=request.POST.get("invitation_id"),
                    )
                    if invitation.status == "pending":
                        invitation.status = "cancelled"
                        invitation.responded_at = timezone.now()
                        invitation.save(update_fields=["status", "responded_at", "updated_at"])
                if invitation.status != "cancelled":
                    raise ValidationError("Cette invitation a changé. Actualisez son état.")
                messages.success(request, "Invitation annulée.")
            elif action == "revoke" and managing:
                access = get_object_or_404(
                    ConversationCollectiveAccess, conversation=conversation,
                    pk=request.POST.get("collective_id"),
                )
                revoked = revoke_collective_access(actor=request.user, access=access)
                if revoked.status != "revoked":
                    raise ValidationError("Cet accès a changé. Actualisez son état.")
                messages.success(request, "Accès collectif retiré.")
            elif action in {"approve", "reject"} and managing:
                pending = get_object_or_404(
                    ConversationJoinRequest, conversation=conversation,
                    pk=request.POST.get("join_request_id"),
                )
                result = respond_to_join_request(
                    actor=request.user, join_request=pending,
                    approve=action == "approve",
                )
                expected = "approved" if action == "approve" else "rejected"
                if result.status != expected:
                    raise ValidationError("Cette demande a changé. Actualisez son état.")
                messages.success(request, "Demande traitée.")
            elif action == "leave":
                leave_conversation(actor=request.user, conversation=conversation)
                messages.success(request, "Participation explicite quittée.")
            elif action == "join":
                join_conversation(actor=request.user, conversation=conversation)
                messages.success(request, "Conversation rejointe.")
            elif action == "request":
                create_join_request(actor=request.user, conversation=conversation)
                messages.success(request, "Demande d'entrée transmise.")
            else:
                raise PermissionDenied("Action non autorisée.")
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, "; ".join(getattr(exc, "messages", [str(exc)])))
        if action == "leave" and not can_view_conversation(request.user, conversation):
            return redirect("conversations:list")
        return redirect("conversations:participants", pk=conversation.pk)


class ConversationWithdrawJoinRequestWebView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, join_request_pk):
        personal_request = get_object_or_404(
            ConversationJoinRequest,
            pk=join_request_pk, requester=request.user,
        )
        try:
            withdraw_join_request(
                actor=request.user, join_request=personal_request,
            )
            messages.success(request, "Demande retirée.")
        except (ValidationError, PermissionDenied) as exc:
            messages.error(
                request, "; ".join(getattr(exc, "messages", [str(exc)])),
            )
        return redirect("conversations:list")


class ConversationCollectiveRespondWebView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, access_pk):
        access = get_object_or_404(ConversationCollectiveAccess, pk=access_pk)
        decision = request.POST.get("decision")
        if decision not in {"accept", "decline"}:
            messages.error(request, "Choisissez Accepter ou Refuser.")
        else:
            try:
                result = answer_collective_invitation(
                    actor=request.user, access=access,
                    accept=decision == "accept",
                )
                expected = "active" if decision == "accept" else "declined"
                if result.status == "expired":
                    messages.info(request, "Cette invitation a expiré.")
                elif result.status != expected:
                    raise ValidationError("Cette invitation a changé. Actualisez son état.")
                else:
                    messages.success(request, "Décision enregistrée.")
            except (ValidationError, PermissionDenied) as exc:
                messages.error(request, "; ".join(getattr(exc, "messages", [str(exc)])))
        return redirect("conversations:list")
