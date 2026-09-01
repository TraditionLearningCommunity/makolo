from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import FormRequest
from .services import save_response, submit_response


def _request_for(user, pk):
    return get_object_or_404(
        FormRequest.objects.select_related("journey", "form_version", "form_version__form")
        .prefetch_related("form_version__questions", "response__answers__question"),
        pk=pk,
        journey__beneficiary=user,
    )


def _serialize(form_request):
    response = getattr(form_request, "response", None)
    answers = {answer.question.key: answer.value for answer in response.answers.all()} if response else {}
    return {
        "id": str(form_request.pk),
        "journey_id": str(form_request.journey_id),
        "required": form_request.required,
        "status": form_request.status,
        "opens_at": form_request.opens_at,
        "due_at": form_request.due_at,
        "form_version": {
            "id": str(form_request.form_version_id),
            "form_key": form_request.form_version.form.key,
            "version": form_request.form_version.version,
            "title": form_request.form_version.title,
            "description": form_request.form_version.description,
            "questions": [
                {
                    "key": question.key,
                    "label": question.label,
                    "help_text": question.help_text,
                    "type": question.question_type,
                    "position": question.position,
                    "required": question.required,
                    "min_length": question.min_length,
                    "max_length": question.max_length,
                    "min_value": str(question.min_value) if question.min_value is not None else None,
                    "max_value": str(question.max_value) if question.max_value is not None else None,
                    "choices": question.choices,
                }
                for question in form_request.form_version.questions.all()
            ],
        },
        "response": None if response is None else {
            "id": str(response.pk),
            "status": response.status,
            "submitted_at": response.submitted_at,
            "answers": answers,
        },
    }


class FormRequestListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        rows = (
            FormRequest.objects.filter(journey__beneficiary=request.user)
            .select_related("journey", "form_version", "form_version__form")
            .prefetch_related("form_version__questions", "response__answers__question")
            .order_by("created_at", "id")
        )
        return Response([_serialize(row) for row in rows])


class FormRequestDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        return Response(_serialize(_request_for(request.user, pk)))


class FormResponseSaveAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        form_request = _request_for(request.user, pk)
        answers = request.data.get("answers", {})
        if not isinstance(answers, dict):
            return Response({"detail": "answers doit être un objet."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            save_response(request=form_request, actor=request.user, answers=answers)
        except ValidationError as exc:
            return Response({"errors": exc.message_dict if hasattr(exc, "message_dict") else exc.messages}, status=status.HTTP_400_BAD_REQUEST)
        form_request = _request_for(request.user, pk)
        return Response(_serialize(form_request))


class FormResponseSubmitAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        form_request = _request_for(request.user, pk)
        try:
            submit_response(request=form_request, actor=request.user)
        except ValidationError as exc:
            return Response({"errors": exc.message_dict if hasattr(exc, "message_dict") else exc.messages}, status=status.HTTP_400_BAD_REQUEST)
        form_request = _request_for(request.user, pk)
        return Response(_serialize(form_request))
