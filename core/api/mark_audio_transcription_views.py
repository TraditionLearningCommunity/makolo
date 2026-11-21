"""Authenticated, opt-in transcription of a previously recorded Mark audio.

Does not create a business fact, Resource, Proof or server-stored attachment.
A transcription engine must be configured explicitly by deployment.
"""
from django.utils import timezone
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from core.api.me_views import PersonalProjectionAPIView
from core.mark_audio_transcription import (
    ACCEPTED_AUDIO_TYPES,
    MAX_MARK_AUDIO_BYTES,
    MAX_MARK_TRANSCRIPT_CHARS,
    configured_mark_audio_transcriber,
)


class PersonalMarkAudioTranscriptionAPIView(PersonalProjectionAPIView):
    projection_code = "personal.mark.audio_transcription"
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        self._guard_personal_scope(request)
        return self._response(
            {"available": configured_mark_audio_transcriber() is not None},
            observed_at=timezone.now(),
        )

    def post(self, request):
        self._guard_personal_scope(request, include_body=True)
        engine = configured_mark_audio_transcriber()
        if engine is None:
            return Response(
                {"detail": "Transcription indisponible pour le moment."},
                status=503,
                headers={"Cache-Control": "private, no-store"},
            )
        audio = request.FILES.get("audio")
        if audio is None:
            return Response({"audio": ["Enregistrement manquant."]}, status=400)
        if audio.size <= 0 or audio.size > MAX_MARK_AUDIO_BYTES:
            return Response({"audio": ["Enregistrement trop volumineux."]}, status=413)
        media_type = str(getattr(audio, "content_type", "")).split(";")[0].lower()
        if media_type not in ACCEPTED_AUDIO_TYPES:
            return Response({"audio": ["Format audio non accepté."]}, status=415)
        try:
            recognized = engine(audio)
        except Exception:
            # Never expose the transcriber's internal service, file path or key.
            return Response(
                {"detail": "Transcription indisponible. Réessayez."},
                status=503,
                headers={"Cache-Control": "private, no-store"},
            )
        if not isinstance(recognized, str) or not recognized.strip():
            return Response(
                {"detail": "Aucun texte reconnu."},
                status=422,
                headers={"Cache-Control": "private, no-store"},
            )
        if len(recognized) > MAX_MARK_TRANSCRIPT_CHARS:
            return Response(
                {"detail": "Texte trop long pour cette transcription."},
                status=413,
                headers={"Cache-Control": "private, no-store"},
            )
        return self._response(
            {"text": recognized.strip()},
            observed_at=timezone.now(),
        )
