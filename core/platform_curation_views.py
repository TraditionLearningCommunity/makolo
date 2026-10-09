"""Opportunity curation as Platform presentation over canonical Opportunity owners."""
from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import TemplateView

from authorization.constants import PermissionCode
from authorization.services import can
from core.platform_presentation import platform_modules_for
from operations.services import audit_action
from opportunities.models import Opportunity, OpportunityRevision, OpportunitySource
from opportunities.services import (
    archive_opportunity, publish_opportunity_revision, record_source_check,
    withdraw_opportunity,
)
from opportunities.staff_forms import OpportunitySourceCheckForm


class CurationDecisionForm(forms.Form):
    action = forms.ChoiceField(choices=(
        ("withdraw", "Retirer"), ("archive", "Archiver"),
        ("publish_revision", "Publier une révision"),
        ("check_source", "Enregistrer un contrôle de source"),
    ))
    expected_state = forms.CharField(max_length=20)
    expected_version = forms.CharField(max_length=100)
    target_id = forms.UUIDField(required=False)
    target_version = forms.CharField(max_length=100, required=False)
    source_result = forms.CharField(max_length=20, required=False)
    reason = forms.CharField(min_length=5, max_length=2000)
    confirm = forms.BooleanField()


class PlatformCurationDetailView(LoginRequiredMixin, TemplateView):
    login_url = "core:login"
    template_name = "platform/curation_detail.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        allowed = any(can(request.user, code) for code in (
            PermissionCode.OPPORTUNITIES_MANAGE,
            PermissionCode.OPPORTUNITIES_REVIEW_SUBMISSIONS,
            PermissionCode.OPPORTUNITIES_SOURCES_VERIFY,
            PermissionCode.OPPORTUNITIES_MERGE,
        ))
        if not allowed:
            raise PermissionDenied("Autorité Opportunity Curation requise.")
        response = super().dispatch(request, *args, **kwargs)
        response["Cache-Control"] = "private, no-store"
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        opportunity = get_object_or_404(
            Opportunity.objects.select_related("current_revision", "merged_into"), pk=self.kwargs["pk"]
        )
        context.update(
            platform_modules=platform_modules_for(self.request.user),
            platform_page="curation",
            platform_heading="Dossier de curation",
            opportunity=opportunity,
            revision_rows=opportunity.revisions.order_by("-version")[:30],
            source_rows=opportunity.sources.order_by("-is_primary", "source_name")[:30],
            can_manage=can(self.request.user, PermissionCode.OPPORTUNITIES_MANAGE),
            can_check_source=can(self.request.user, PermissionCode.OPPORTUNITIES_SOURCES_VERIFY),
            can_merge=can(self.request.user, PermissionCode.OPPORTUNITIES_MERGE),
            source_check_choices=OpportunitySourceCheckForm().fields["result"].choices,
            version_token=opportunity.updated_at.isoformat(),
            error_message=kwargs.get("error_message", ""),
        )
        return context


class PlatformCurationDecisionView(PlatformCurationDetailView):
    def post(self, request, *args, **kwargs):
        form = CurationDecisionForm(request.POST)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(
                error_message="Action, état initial, raison et confirmation sont obligatoires."
            ), status=400)
        data = form.cleaned_data
        action = data["action"]
        code = (PermissionCode.OPPORTUNITIES_SOURCES_VERIFY if action == "check_source"
                else PermissionCode.OPPORTUNITIES_MANAGE)
        if not can(request.user, code):
            raise PermissionDenied("Cette action Opportunity n'est pas autorisée.")
        if action in {"check_source", "publish_revision"} and (
            not data["target_id"] or not data["target_version"]
        ):
            return self.render_to_response(self.get_context_data(
                error_message="Choisissez une source ou révision actuellement visible."
            ), status=400)
        with transaction.atomic():
            op = get_object_or_404(
                Opportunity.objects.select_for_update(), pk=self.kwargs["pk"]
            )
            if not can(request.user, code):
                raise PermissionDenied("L'autorité de curation a changé.")
            if (op.publication_status != data["expected_state"]
                    or op.updated_at.isoformat() != data["expected_version"]):
                return self.render_to_response(self.get_context_data(
                    error_message="L'Opportunity a changé depuis votre lecture."
                ), status=409)
            before = op.publication_status
            target = None
            if action in {"withdraw", "archive"}:
                if before in ("withdrawn", "archived", "merged"):
                    return self.render_to_response(self.get_context_data(
                        error_message="La transition a déjà été appliquée ou n'est plus autorisée."
                    ), status=409)
            else:
                if action == "publish_revision":
                    target = get_object_or_404(
                        OpportunityRevision.objects.select_for_update(),
                        pk=data["target_id"], opportunity=op,
                    )
                    if target.published_at or target.created_at.isoformat() != data["target_version"]:
                        return self.render_to_response(self.get_context_data(
                            error_message="La révision a déjà été publiée ou remplacée."
                        ), status=409)
                else:
                    target = get_object_or_404(
                        OpportunitySource.objects.select_for_update(),
                        pk=data["target_id"], opportunity=op,
                    )
                    if target.updated_at.isoformat() != data["target_version"]:
                        return self.render_to_response(self.get_context_data(
                            error_message="La source a été modifiée depuis son contrôle."
                        ), status=409)
                    check = OpportunitySourceCheckForm({
                        "result": data["source_result"], "note": data["reason"]
                    })
                    if not check.is_valid():
                        return self.render_to_response(self.get_context_data(
                            error_message="Le résultat du contrôle de source est invalide."
                        ), status=400)
            try:
                if action == "withdraw":
                    withdraw_opportunity(opportunity=op, actor=request.user)
                elif action == "archive":
                    archive_opportunity(opportunity=op, actor=request.user)
                elif action == "publish_revision":
                    publish_opportunity_revision(opportunity=op, revision=target, actor=request.user)
                else:
                    record_source_check(
                        source=target, result=data["source_result"],
                        checked_by=request.user, note=data["reason"],
                    )
            except ValidationError as exc:
                detail = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
                return self.render_to_response(self.get_context_data(
                    error_message=str(detail),
                ), status=409)
            op.refresh_from_db()
            audit_action(
                actor=request.user, action=f"platform.opportunity.{action}",
                target_type="opportunity", target_id=op.pk,
                summary=f"Décision de curation : {action}",
                before={"state": before},
                after={"state": op.publication_status, "owner_target": str(target.pk) if target else None},
                metadata={"reason": data["reason"]},
            )
        messages.success(request, "Décision enregistrée par le domaine Opportunity et auditée.")
        return redirect("platform_web:curation-detail", pk=op.pk)
