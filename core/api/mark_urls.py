from django.urls import path

from .mark_views import PersonalMarkAPIView


app_name = "personal-mark"

urlpatterns = [
    path("mark/", PersonalMarkAPIView.as_view(), name="mark"),
]
