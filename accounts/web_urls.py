from django.urls import path

from topics.web_views import ProfileInterestSettingsView, ProfileOpenToSettingsView

from .activation_views import DismissProfileInterestPromptView, ProfileInterestQuickCaptureView
from .public_views import PublicProfileView
from .web_views import (
    AccountDeleteView, AccountPasswordChangeView, AccountProfileView, AccountRegistrationView,
    AccountSwitcherView, AddAccountView, PasswordForgotView, PasswordResetConfirmView,
    RemoveRememberedAccountView, SwitchRememberedAccountView,
)

app_name = "account"

urlpatterns = [
    path("register/", AccountRegistrationView.as_view(), name="register"),
    path("profile/", AccountProfileView.as_view(), name="profile"),
    path("interests/", ProfileInterestSettingsView.as_view(), name="interests"),
    path("interests/quick-capture/", ProfileInterestQuickCaptureView.as_view(), name="interest-quick-capture"),
    path("interests/prompt/dismiss/", DismissProfileInterestPromptView.as_view(), name="interest-prompt-dismiss"),
    path("open-to/", ProfileOpenToSettingsView.as_view(), name="open-to"),
    path("people/<uuid:profile_id>/", PublicProfileView.as_view(), name="public-profile"),
    path("switch/", AccountSwitcherView.as_view(), name="switcher"),
    path("switch/add/", AddAccountView.as_view(), name="add-account"),
    path("switch/<uuid:user_id>/", SwitchRememberedAccountView.as_view(), name="switch-account"),
    path("switch/<uuid:user_id>/remove/", RemoveRememberedAccountView.as_view(), name="remove-account"),
    path("password/", AccountPasswordChangeView.as_view(), name="password-change"),
    path("password/forgot/", PasswordForgotView.as_view(), name="password-forgot"),
    path("password/reset/<str:uid>/<str:token>/", PasswordResetConfirmView.as_view(), name="password-reset-confirm"),
    path("delete/", AccountDeleteView.as_view(), name="delete"),
]
