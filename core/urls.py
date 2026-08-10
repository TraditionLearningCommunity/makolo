from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from .views import DashboardView, PublicHomeView


app_name = "core"

urlpatterns = [
    path(
        "login/",
        LoginView.as_view(
            template_name="auth/login.html",
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path(
        "logout/",
        LogoutView.as_view(next_page="core:home"),
        name="logout",
    ),
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("", PublicHomeView.as_view(), name="home"),
]
