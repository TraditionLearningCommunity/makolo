from django.urls import path

from .api_views import FormRequestDetailAPIView, FormRequestListAPIView, FormResponseSaveAPIView, FormResponseSubmitAPIView


urlpatterns = [
    path("requests/", FormRequestListAPIView.as_view(), name="questionnaire-request-list"),
    path("requests/<uuid:pk>/", FormRequestDetailAPIView.as_view(), name="questionnaire-request-detail"),
    path("requests/<uuid:pk>/save/", FormResponseSaveAPIView.as_view(), name="questionnaire-response-save"),
    path("requests/<uuid:pk>/submit/", FormResponseSubmitAPIView.as_view(), name="questionnaire-response-submit"),
]
