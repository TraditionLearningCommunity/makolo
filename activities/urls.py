from django.urls import path

from .views import ActivityCreateView


app_name = "activities"

urlpatterns = [
    path("new/", ActivityCreateView.as_view(), name="create"),
]
