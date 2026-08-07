from django.urls import include, path

from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    LoginAPIView,
    LogoutAPIView,
    MeAPIView,
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
    path(
        "auth/register/",
        RegisterAPIView.as_view(),
        name="register",
    ),
    path(
        "auth/login/",
        LoginAPIView.as_view(),
        name="login",
    ),
    path(
        "auth/refresh/",
        TokenRefreshView.as_view(),
        name="token_refresh",
    ),
    path(
        "auth/logout/",
        LogoutAPIView.as_view(),
        name="logout",
    ),
    path(
        "auth/me/",
        MeAPIView.as_view(),
        name="me",
    ),
    path(
        "auth/profile/update/",
        UpdateProfileAPIView.as_view(),
        name="profile-update",
    ),
    path("", include(router.urls)),
]
