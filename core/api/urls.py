from django.urls import path

from .personal_views import PersonalNowAPIView, PersonalOngoingAPIView


app_name = "personal-projections"

urlpatterns = [
    path("now/", PersonalNowAPIView.as_view(), name="now"),
    path("ongoing/", PersonalOngoingAPIView.as_view(), name="ongoing"),
]
