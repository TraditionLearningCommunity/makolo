from django.urls import path

from .web_views import AccountPasswordChangeView, AccountProfileView


app_name = "account"

urlpatterns = [
    path("profile/", AccountProfileView.as_view(), name="profile"),
    path("password/", AccountPasswordChangeView.as_view(), name="password-change"),
]
