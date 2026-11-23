from django.urls import path

from .mark_views import PersonalMarkAPIView
from .mark_audio_transcription_views import PersonalMarkAudioTranscriptionAPIView
from .mark_intake_views import PersonalMarkIntakeAPIView, PersonalMarkReceiptAPIView


app_name = "personal-mark"

urlpatterns = [
    path("mark/", PersonalMarkAPIView.as_view(), name="mark"),
    path("mark/intake/", PersonalMarkIntakeAPIView.as_view(), name="mark-intake"),
    path("mark/intake/<uuid:receipt_id>/", PersonalMarkReceiptAPIView.as_view(), name="mark-receipt"),
    path("mark/transcription/", PersonalMarkAudioTranscriptionAPIView.as_view(), name="mark-transcription"),
]
