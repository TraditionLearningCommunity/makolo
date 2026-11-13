from django.core.exceptions import ValidationError, PermissionDenied
from django.http import FileResponse, Http404
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.exceptions import ValidationError as DRFValidationError, NotFound
from .media_services import add_questionnaire_media, remove_questionnaire_media, ensure_media_access, serialize_media, media_sections
from .models import FormVersion, FormQuestion, QuestionnaireMedia
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import FormRequest
from .services import save_response, submit_response


def _request_for(user, pk, *, write=False):
    row = get_object_or_404(
        FormRequest.objects.select_related(
            "journey",
            "journey__beneficiary",
            "journey__beneficiary_space",
            "target_profile",
            "form_version",
            "form_version__form",
        ).prefetch_related("form_version__questions", "response__answers__question"),
        pk=pk,
    )
    if row.target_profile_id == user.pk or (
        row.journey_id and row.journey.beneficiary_id == user.pk
    ):
        return row
    if row.journey_id and row.journey.beneficiary_space_id:
        from services.space_beneficiary import can_act_for_space_service_journey

        # Forms contain personal responses. Even a read-only Space mandate
        # must not implicitly disclose their private answers.
        allowed = can_act_for_space_service_journey(user, row.journey)
        if allowed:
            return row
    raise Http404


def _serialize(form_request):
    response = getattr(form_request, "response", None)
    answers = {answer.question.key: answer.value for answer in response.answers.all()} if response else {}
    root_media, by_question, by_choice = media_sections(form_request.form_version)
    return {
        "id": str(form_request.pk),
        "journey_id": str(form_request.journey_id) if form_request.journey_id else None,
        "target_profile_id": str(form_request.target_profile_id) if form_request.target_profile_id else None,
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
            "media": [serialize_media(item) for item in root_media],
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
                    "media": [serialize_media(item) for item in by_question.get(question.pk, [])],
                    "choice_media": [
                        {
                            "index": index, "label": label,
                            "media": [serialize_media(item) for item in by_choice.get((question.pk, index), [])],
                        }
                        for index, label in enumerate(question.choices)
                    ],
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
        from organizations.api.workspace_projection import workspace_spaces
        from services.space_beneficiary import can_act_for_space

        permitted_space_ids = [
            space.pk for space in workspace_spaces(request.user)
            if can_act_for_space(request.user, space)
        ]
        rows = (
            FormRequest.objects.filter(
                Q(journey__beneficiary=request.user)
                | Q(target_profile=request.user)
                | Q(journey__beneficiary_space_id__in=permitted_space_ids)
            )
            .select_related("journey", "journey__beneficiary", "target_profile", "form_version", "form_version__form")
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
        form_request = _request_for(request.user, pk, write=True)
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
        form_request = _request_for(request.user, pk, write=True)
        try:
            submit_response(request=form_request, actor=request.user)
        except ValidationError as exc:
            return Response({"errors": exc.message_dict if hasattr(exc, "message_dict") else exc.messages}, status=status.HTTP_400_BAD_REQUEST)
        form_request = _request_for(request.user, pk)
        return Response(_serialize(form_request))



class QuestionnaireMediaUploadAPIView(APIView):
    """Authoring is restricted to Activity managers and draft FormVersions."""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, version_pk):
        version = get_object_or_404(
            FormVersion.objects.select_related("form__activity"), pk=version_pk,
        )
        files = request.FILES.getlist("file")
        if len(files) != 1:
            raise DRFValidationError({"file": "Un seul média est attendu."})
        try:
            raw_question = request.data.get("question_id")
            question = get_object_or_404(FormQuestion, pk=raw_question) if raw_question else None
            index = request.data.get("choice_index")
            index = int(index) if index not in (None, "") else None
            position = int(request.data.get("position") or 0)
            upload = files[0]
            declared = request.data.get("mime_type")
            if declared and upload.content_type in {"", "application/octet-stream"}:
                upload.content_type = str(declared)
            media = add_questionnaire_media(
                actor=request.user, version=version, question=question,
                choice_index=index, position=position, uploaded_file=upload,
                kind=request.data.get("kind", "file"),
                caption=request.data.get("caption", ""),
            )
        except (TypeError, ValueError):
            raise DRFValidationError({"position": "Index ou position invalide."})
        except ValidationError as exc:
            return Response({
                "errors": exc.message_dict if hasattr(exc, "message_dict") else exc.messages,
            }, status=status.HTTP_400_BAD_REQUEST)
        except PermissionDenied:
            raise
        return Response(serialize_media(media), status=status.HTTP_201_CREATED)



class QuestionnaireMediaManageAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, media_pk):
        media = get_object_or_404(QuestionnaireMedia, pk=media_pk)
        try:
            remove_questionnaire_media(actor=request.user, media=media)
        except PermissionDenied:
            raise
        except ValidationError as exc:
            return Response({
                "errors": exc.message_dict if hasattr(exc, "message_dict") else exc.messages,
            }, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)


class QuestionnaireMediaDownloadAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, media_pk):
        media = get_object_or_404(
            QuestionnaireMedia.objects.select_related(
                "form_version__form__activity", "question",
            ), pk=media_pk,
        )
        try:
            ensure_media_access(request.user, media)
        except PermissionDenied as exc:
            raise NotFound("Média indisponible.") from exc
        # Only browser-safe media and PDF may render inline. Unknown documents
        # remain attachments; the file remains private and no URL is signed.
        inline = (media.mime_type.startswith(("image/", "audio/", "video/"))
                  or media.mime_type in {"application/pdf", "text/plain"})
        response = FileResponse(
            media.file.open("rb"), as_attachment=not inline,
            filename=media.original_name, content_type=media.mime_type,
        )
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        response["Content-Security-Policy"] = "default-src 'none'; sandbox"
        return response
