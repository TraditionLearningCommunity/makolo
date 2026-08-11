from django.contrib.auth.views import LogoutView
from django.urls import path

from .views import DashboardView, PublicHomeView, RateLimitedLoginView


app_name = "core"

urlpatterns = [
    path("login/", RateLimitedLoginView.as_view(), name="login"),
    path(
        "logout/",
        LogoutView.as_view(next_page="core:home"),
        name="logout",
    ),
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("", PublicHomeView.as_view(), name="home"),
]
