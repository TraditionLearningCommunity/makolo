from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import TemplateView

from activities.models import Activity
from authorization.constants import PermissionCode
from authorization.services import can
from journeys.models import Journey

from .models import Form, FormQuestion, FormRequest, FormResponse, FormVersion, QuestionType
from .services import (
    add_question,
    create_form,
    create_form_version,
    publish_form_version,
    request_form,
    save_response,
    submit_response,
)


def _participant_request(user, pk):
    return get_object_or_404(
        FormRequest.objects.select_related("journey", "journey__activity", "form_version", "form_version__form")
        .prefetch_related("form_version__questions", "response__answers__question"),
        pk=pk,
        journey__beneficiary=user,
    )


def _answers_from_post(request, form_request):
    values = {}
    for question in form_request.form_version.questions.all():
        name = f"q_{question.key}"
        if question.question_type == QuestionType.MULTIPLE_CHOICE:
            values[question.key] = request.POST.getlist(name)
        elif question.question_type == QuestionType.BOOLEAN:
            values[question.key] = request.POST.get(name) == "true"
        else:
            values[question.key] = request.POST.get(name, "")
    return values


class ParticipantFormRequestView(LoginRequiredMixin, TemplateView):
    template_name = "questionnaires/request_detail.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form_request = _participant_request(self.request.user, kwargs["pk"])
        response = getattr(form_request, "response", None)
        existing = {answer.question_id: answer.value for answer in response.answers.all()} if response else {}
        rows = [{"question": q, "value": existing.get(q.pk)} for q in form_request.form_version.questions.all()]
        context.update({"form_request": form_request, "form_response": response, "question_rows": rows})
        return context

    def post(self, request, *args, **kwargs):
        form_request = _participant_request(request.user, kwargs["pk"])
        try:
            save_response(request=form_request, actor=request.user, answers=_answers_from_post(request, form_request))
            if request.POST.get("action") == "submit":
                submit_response(request=form_request, actor=request.user)
                messages.success(request, "Formulaire soumis.")
            else:
                messages.success(request, "Brouillon enregistré.")
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, "; ".join(getattr(exc, "messages", [str(exc)])))
        return redirect("questionnaires:request-detail", pk=form_request.pk)


class ManageQuestionnairesView(LoginRequiredMixin, TemplateView):
    template_name = "questionnaires/manage.html"
    login_url = "core:login"

    def _activity(self):
        activity = get_object_or_404(Activity, pk=self.kwargs["activity_id"])
        if not can(self.request.user, PermissionCode.ACTIVITY_MANAGE, activity=activity):
            raise PermissionDenied("La gestion des questionnaires n’est pas autorisée.")
        return activity

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        activity = self._activity()
        forms = Form.objects.filter(activity=activity).prefetch_related("versions__questions")
        requests = (
            FormRequest.objects.filter(journey__activity=activity)
            .select_related("journey", "journey__beneficiary", "form_version", "form_version__form")
            .prefetch_related("response__answers__question")
        )
        context.update({"activity": activity, "forms": forms, "form_requests": requests})
        return context

    def post(self, request, *args, **kwargs):
        activity = self._activity()
        action = request.POST.get("action")
        try:
            if action == "create_form":
                form = create_form(
                    activity=activity,
                    key=request.POST.get("key", ""),
                    title=request.POST.get("title", ""),
                    description=request.POST.get("description", ""),
                    actor=request.user,
                )
                create_form_version(form=form, actor=request.user)
                messages.success(request, "Formulaire créé avec une version brouillon.")
            elif action == "new_version":
                form = get_object_or_404(Form, pk=request.POST.get("form_id"), activity=activity)
                create_form_version(form=form, actor=request.user)
                messages.success(request, "Nouvelle version brouillon créée.")
            elif action == "add_question":
                version = get_object_or_404(FormVersion.objects.select_related("form"), pk=request.POST.get("version_id"), form__activity=activity)
                choices = [item.strip() for item in request.POST.get("choices", "").splitlines() if item.strip()]
                add_question(
                    form_version=version,
                    actor=request.user,
                    key=request.POST.get("key", ""),
                    label=request.POST.get("label", ""),
                    question_type=request.POST.get("question_type", QuestionType.SHORT_TEXT),
                    position=int(request.POST.get("position", 0)),
                    required=request.POST.get("required") == "on",
                    choices=choices,
                )
                messages.success(request, "Question ajoutée.")
            elif action == "publish":
                version = get_object_or_404(FormVersion.objects.select_related("form"), pk=request.POST.get("version_id"), form__activity=activity)
                publish_form_version(form_version=version, actor=request.user)
                messages.success(request, "Version publiée.")
            elif action == "request":
                version = get_object_or_404(FormVersion.objects.select_related("form"), pk=request.POST.get("version_id"), form__activity=activity)
                journey = get_object_or_404(Journey, pk=request.POST.get("journey_id"), activity=activity)
                request_form(
                    form_version=version,
                    journey=journey,
                    actor=request.user,
                    required=request.POST.get("required") == "on",
                )
                messages.success(request, "Formulaire demandé dans la Journey.")
            else:
                raise ValidationError("Action questionnaire inconnue.")
        except (ValidationError, PermissionDenied, ValueError) as exc:
            messages.error(request, "; ".join(getattr(exc, "messages", [str(exc)])))
        return redirect("questionnaires:manage", activity_id=activity.pk)
