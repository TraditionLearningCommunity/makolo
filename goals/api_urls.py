from django.urls import path

from .api_views import GoalsAPIView, GoalStatusAPIView

urlpatterns = [
    path("", GoalsAPIView.as_view(), name="goals-api"),
    path("<uuid:pk>/status/", GoalStatusAPIView.as_view(), name="goal-status-api"),
]
