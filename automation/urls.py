from django.urls import path

from .views import EventAutomationPolicyView


app_name = "automation"

urlpatterns = [
    path("events/<slug:slug>/", EventAutomationPolicyView.as_view(), name="event-policy"),
]
