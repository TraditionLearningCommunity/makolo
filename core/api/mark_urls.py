from django.urls import path

from .mark_views import PersonalMarkAPIView
from .mark_audio_transcription_views import PersonalMarkAudioTranscriptionAPIView


app_name = "personal-mark"

urlpatterns = [
    path("mark/", PersonalMarkAPIView.as_view(), name="mark"),
    path("mark/transcription/", PersonalMarkAudioTranscriptionAPIView.as_view(), name="mark-transcription"),
]
