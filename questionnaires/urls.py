from django.urls import path

from .views import ManageQuestionnairesView, ParticipantFormRequestView


app_name = "questionnaires"

urlpatterns = [
    path("requests/<uuid:pk>/", ParticipantFormRequestView.as_view(), name="request-detail"),
    path("manage/activity/<uuid:activity_id>/", ManageQuestionnairesView.as_view(), name="manage"),
]
