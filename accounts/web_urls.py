from django.urls import path

from .web_views import (
    AccountDeleteView,
    AccountPasswordChangeView,
    AccountProfileView,
    AccountRegistrationView,
    PasswordForgotView,
    PasswordResetConfirmView,
)


app_name = "account"

urlpatterns = [
    path("register/", AccountRegistrationView.as_view(), name="register"),
    path("profile/", AccountProfileView.as_view(), name="profile"),
    path("password/", AccountPasswordChangeView.as_view(), name="password-change"),
    path("password/forgot/", PasswordForgotView.as_view(), name="password-forgot"),
    path(
        "password/reset/<str:uid>/<str:token>/",
        PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
    path("delete/", AccountDeleteView.as_view(), name="delete"),
]
