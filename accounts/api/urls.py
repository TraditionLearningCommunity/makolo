from django.urls import include, path

from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    AccountDeleteAPIView,
    LoginAPIView,
    LogoutAPIView,
    MeAPIView,
    NotificationPreferencesAPIView,
    PasswordChangeAPIView,
    PasswordForgotAPIView,
    PasswordResetAPIView,
    PermissionGroupViewSet,
    RegisterAPIView,
    RoleViewSet,
    UpdateProfileAPIView,
    UserViewSet,
)


router = DefaultRouter()
router.register(r"users", UserViewSet, basename="users")
router.register(r"roles", RoleViewSet, basename="roles")
router.register(
    r"permission-groups",
    PermissionGroupViewSet,
    basename="permission-groups",
)

urlpatterns = [
    path("auth/register/", RegisterAPIView.as_view(), name="register"),
    path("auth/login/", LoginAPIView.as_view(), name="login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/logout/", LogoutAPIView.as_view(), name="logout"),
    path("auth/password/forgot/", PasswordForgotAPIView.as_view(), name="password-forgot"),
    path("auth/password/reset/", PasswordResetAPIView.as_view(), name="password-reset"),
    path("auth/password/change/", PasswordChangeAPIView.as_view(), name="password-change"),
    path("auth/me/", MeAPIView.as_view(), name="me"),
    path("auth/profile/update/", UpdateProfileAPIView.as_view(), name="profile-update"),
    path(
        "notification-preferences/",
        NotificationPreferencesAPIView.as_view(),
        name="notification-preferences",
    ),
    path("account/delete/", AccountDeleteAPIView.as_view(), name="account-delete"),
    path("", include(router.urls)),
]
