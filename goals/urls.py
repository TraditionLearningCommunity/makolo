from django.urls import path

from .views import GoalCreateView, GoalListView, GoalStatusView

app_name = "goals"

urlpatterns = [
    path("me/goals/", GoalListView.as_view(), name="list"),
    path("me/goals/create/", GoalCreateView.as_view(), name="create"),
    path("me/goals/<uuid:pk>/status/", GoalStatusView.as_view(), name="status"),
]
