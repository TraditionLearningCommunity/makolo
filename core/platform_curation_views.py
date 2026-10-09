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
            revision_rows=[{"item": row, "version": row.created_at.isoformat()} for row in opportunity.revisions.order_by("-version")[:30]],
            source_rows=[{"item": row, "version": row.updated_at.isoformat()} for row in opportunity.sources.order_by("-is_primary", "source_name")[:30]],
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
                if before == "merged" or (action == "withdraw" and before != "published") or (action == "archive" and before == "archived"):
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


class PlatformSubmissionReviewView(LoginRequiredMixin, TemplateView):
    login_url = "core:login"
    template_name = "platform/submission_review.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not can(request.user, PermissionCode.OPPORTUNITIES_REVIEW_SUBMISSIONS):
            raise PermissionDenied("Permission de revue des propositions Opportunity requise.")
        response = super().dispatch(request, *args, **kwargs)
        response["Cache-Control"] = "private, no-store"
        return response

    def get_context_data(self, **kwargs):
        from opportunities.models import OpportunitySubmission
        from opportunities.staff_forms import OpportunitySubmissionDecisionForm
        context = super().get_context_data(**kwargs)
        obj = get_object_or_404(OpportunitySubmission, pk=self.kwargs["pk"])
        context.update(
            platform_modules=platform_modules_for(self.request.user),
            platform_page="curation",
            platform_heading="Revue de proposition",
            submission=obj,
            version_token=obj.updated_at.isoformat(),
            decision_form=kwargs.get("decision_form", OpportunitySubmissionDecisionForm()),
            error_message=kwargs.get("error_message", ""),
        )
        return context

    def post(self, request, *args, **kwargs):
        from opportunities.models import OpportunitySubmission, OpportunitySubmissionStatus
        from opportunities.staff_forms import OpportunitySubmissionDecisionForm
        from opportunities.services import start_submission_review, decide_opportunity_submission
        reason = (request.POST.get("reason") or "").strip()
        step = request.POST.get("step")
        if (request.POST.get("confirm") != "1" or not 5 <= len(reason) <= 2000
                or step not in {"review", "decide"}):
            return self.render_to_response(self.get_context_data(
                error_message="L'action, la confirmation et une justification explicite sont requises."
            ), status=400)
        form = OpportunitySubmissionDecisionForm(request.POST) if step == "decide" else None
        if form and not form.is_valid():
            return self.render_to_response(self.get_context_data(
                error_message="Décision ou Opportunity canonique invalide.", decision_form=form,
            ), status=400)
        with transaction.atomic():
            obj = get_object_or_404(
                OpportunitySubmission.objects.select_for_update(), pk=self.kwargs["pk"]
            )
            if not can(request.user, PermissionCode.OPPORTUNITIES_REVIEW_SUBMISSIONS):
                raise PermissionDenied("Autorité de revue révoquée.")
            if obj.updated_at.isoformat() != request.POST.get("version_token", ""):
                return self.render_to_response(self.get_context_data(
                    error_message="La proposition a changé ; actualisez avant de décider."
                ), status=409)
            before = obj.status
            if ((step == "review" and before != OpportunitySubmissionStatus.PENDING)
                    or (step == "decide" and before != OpportunitySubmissionStatus.UNDER_REVIEW)):
                return self.render_to_response(self.get_context_data(
                    error_message="Cette transition est déjà traitée ou non autorisée."
                ), status=409)
            try:
                if step == "review":
                    result = start_submission_review(submission=obj, actor=request.user)
                else:
                    data = form.cleaned_data
                    result = decide_opportunity_submission(
                        submission=obj, actor=request.user,
                        decision=data["decision"],
                        resolved_opportunity=data["resolved_opportunity"],
                        review_note=reason,
                    )
            except ValidationError as exc:
                return self.render_to_response(self.get_context_data(
                    error_message="; ".join(exc.messages),
                ), status=409)
            audit_action(
                actor=request.user,
                action=f"platform.opportunity.submission.{step}",
                target_type="opportunity_submission", target_id=obj.pk,
                summary="Revue humaine de proposition Opportunity",
                before={"status": before},
                after={"status": result.status,
                       "resolved_opportunity_id": str(result.resolved_opportunity_id) if result.resolved_opportunity_id else None},
                metadata={"reason": reason},
            )
        messages.success(request, "Proposition traitée par le service Opportunity ; décision auditée.")
        return redirect("platform_web:submission-review", pk=obj.pk)
